"""Đầu-cuối: soạn thảo trong chat qua `POST /api/v1/tra-cuu` (Task 19).

Graph THẬT (không patch `routes._g` bằng một double toàn phần như các file
khác) — chỉ hai chỗ bị thay: `graph_tra_cuu.llm_from_settings` (route VÀ
gom_du_kien dùng CHUNG một `llm`) và `graph_tra_cuu.graph_soan_thao_cached`
(để không chạy `draft_generate`/`draft_audit` thật). `routes._graph` phải bị
reset về `None` trước mỗi test: nó là một singleton module-level, và `llm`
được chốt LÚC BUILD graph — monkeypatch `llm_from_settings` sau khi graph đã
build một lần (ở một test khác) sẽ không có tác dụng gì.

`LlmGia` trả JSON theo HÌNH DẠNG `json_schema` nhận được, đúng cách brief mô
tả: có `dang_tra_loi` → JSON router, đúng `intent` bằng `llm.router_intent`
(đổi được giữa các lượt); có `van_ban` → JSON `schema_hieu` của
`hieu_tai_lieu`, tức một bản thảo tổng quát soạn được (Phase 14); có `du` →
JSON dữ kiện (đếm số lần gọi để mô phỏng "lần đầu thiếu, lần sau đủ"); có
`cau_hoi_day_du` → JSON giải nghĩa (một câu cố định, không số/Điều nào để
không vướng lưới `dinh_danh_bia`); còn lại → một JSON trung tính (đủ cho
`hoi_lai` degrade sạch qua nhánh lỗi của nó khi `intent` router trả là một ý
định KHÔNG phải `soan_thao` và lượt đó rơi vào một ngõ cụt tra cứu thường).

Đúng MỘT chỗ double đọc chữ của prompt: dấu "# Bản thảo đang có"
(`MOC_BAN_THAO_DANG_CO`) để chọn `tao_van_ban` hay `sua_ban_thao` — xem chú
thích tại nhánh đó, đây là quyết định mô hình THẬT cũng đọc từ prompt mà ra.

Phase 14 (D14-B): một yêu cầu soạn MỚI trong chat không còn đi `gom_du_kien`
nữa mà đi `hieu_tai_lieu` → `dung_ban_thao_tong_quat`, và phiên được lưu là
`ban_thao_tong_quat_dang_mo` (dòng bảng `ban_thao`, `routes.py:293`) chứ không
phải `hoi_thoai.soan_thao_cua_phien`. `gom_du_kien`/`soan_thao_cua_phien` vẫn
sống cho một checklist ĐANG mở dở — hai test giữa file này là phép đo của
đường ấy.

Review fix (state coordinator): `_re_sau_route`/`assemble` từng tự ý xét
THÊM trạng thái soạn của phiên bên cạnh `intent` router vừa đoán, nên một bản
thảo còn mở sẽ ép MỌI lượt sau — kể cả một câu hỏi luật thật — vào nhánh soạn
thảo. Cả hai chỗ đó giờ CHỈ gác trên `intent`; hai test cuối file này khoá
đúng phân biệt đó ở tầng HTTP.
"""

import json
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from src.agents import graph_tra_cuu as g
from src.agents.nodes.assemble import MOI_BIEU_MAU
from src.services import ban_thao, bao_ve, hoi_thoai
from src.services.db import get_engine
from src.services.llm import Usage
from tests.test_api.test_xac_thuc_han_muc import _URL as SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration


class _KetAuditGia:
    """Đủ thuộc tính để `ban_thao.tu_state_soan_thao` đọc — KHÔNG phải `{}` trần:
    hàm đó truy cập `.dat`/`.completeness`/`.so_dieu_khoan`/`.self_audit`/
    `.findings` (thuộc tính, không phải khoá dict) trên chính giá trị này."""

    dat = True
    completeness = 1.0
    so_dieu_khoan = 0
    self_audit = True
    findings: list = []


class _GraphSoanThaoGia:
    """Thay `graph_soan_thao_cached()` — `ainvoke` giữ nguyên `loai`/`facts` của
    đầu vào (như một node LangGraph thật luôn `{**st, ...}`) và thêm đúng
    những khoá `ban_thao.tu_state_soan_thao` cần để dựng `ket`."""

    async def ainvoke(self, st):
        return {**st, "clauses": [], "audit_report": _KetAuditGia(), "db_provisions": {}, "traces": {}}


# Dấu của khối "# Bản thảo đang có" (`hieu_tai_lieu._khoi_ban_thao_dang_co`)
# trong prompt. Khối ấy chỉ có mặt khi `routes._chuan_bi` đã kèm
# `ban_thao_tong_quat_dang_mo` (routes.py:293) vào state — nên nó là dấu THẬT,
# đọc được từ phía mô hình, để phân biệt một lượt dựng mới với một lượt sửa.
#
# Xuống dòng ở HAI đầu, không chỉ tiêu đề trần: `hieu_tai_lieu.KHONG_TAI_LIEU`
# (khối `{tai_lieu}` của MỌI lượt soạn tự do) nhắc chính tiêu đề ấy trong một
# câu văn — khớp trần thì lượt DỰNG ĐẦU TIÊN nào cũng trông như một lượt sửa.
MOC_BAN_THAO_DANG_CO = "\n# Bản thảo đang có\n"

# Mục DUY NHẤT của bản thảo double soạn ra. Chỉ đường soạn THẬT mới có nó:
# nhánh lỗi của `hieu_tai_lieu` trả `soan_thao_hoi` không mang `clauses` nào,
# nên khẳng định trên tên mục này là thứ phân biệt được "đã soạn" với "đã
# degrade sạch qua nhánh lỗi" — đúng bẫy `max_tokens` từng giăng ra.
TEN_MUC_SOAN = "Nội dung thỏa thuận"


class LlmGia:
    def __init__(self):
        self.lan_gom = 0
        self.lan_soan = 0
        # Ý định router trả cho LƯỢT KẾ TIẾP — test đổi giá trị này giữa các
        # lượt để mô phỏng `route` đoán khác nhau qua từng tin nhắn, đúng cách
        # `_re_sau_route`/`assemble` giờ CHỈ tin vào phán đoán này (không còn
        # tự ý xét thêm `soan_thao_dang_mo` của phiên).
        self.router_intent = "soan_thao"

    def chat(self, model, messages, json_schema=None, max_tokens=None):
        # `max_tokens` (Phase 16, `llm.chat`) KHÔNG dùng ở đây nhưng PHẢI có
        # mặt: `hieu_tai_lieu` truyền nó, và một double thiếu tham số sẽ nổ
        # TypeError ngay trong `try` của node đó — node nuốt lỗi, degrade sạch,
        # nên test vẫn "đi qua" mà thật ra đang đo nhánh LỖI chứ không phải
        # đường soạn. Chữ ký của double phải theo chữ ký thật.
        props = (json_schema or {}).get("properties", {})
        if "dang_tra_loi" in props:  # route.v3
            la_soan = self.router_intent == "soan_thao"
            return json.dumps(
                {
                    "intent": self.router_intent,
                    "loai_van_ban": "hdld" if la_soan else "khong_ro",
                    "thay_the": [],
                    "ly_do": "",
                    "dang_tra_loi": "van_xuoi",
                    "y_dinh_phu": "khong",
                }
            ), Usage(1, 1, 0.0)
        if "van_ban" in props:  # hieu_tai_lieu (`schema_hieu`) — đường soạn tổng quát
            self.lan_soan += 1
            # Mô hình THẬT chọn `tao_van_ban` hay `sua_ban_thao` bằng chính
            # khối "# Bản thảo đang có" của prompt; double đọc đúng dấu ấy chứ
            # KHÔNG nhận lệnh từ test. Nhờ vậy, nếu `ban_thao_tong_quat_dang_mo`
            # thôi không tới được prompt nữa, lượt sửa bằng lời sẽ dựng một bản
            # thảo THỨ HAI và test thấy ngay — test tự ép `sua_ban_thao` thì
            # đoạn đường đó từ `routes` vào prompt không còn ai đo.
            co_ban_thao = any(MOC_BAN_THAO_DANG_CO in (m.get("content") or "") for m in messages)
            return json.dumps(
                {
                    "muc_dich": "sua_ban_thao" if co_ban_thao else "tao_van_ban",
                    "mo_ta": "",
                    "tra_loi_ngan": "",
                    "quan_sat": [],
                    "suy_luan": [],
                    "can_du_kien": [],
                    "phep_tinh": [],
                    "truong": [],
                    "khac_biet": [],
                    "dieu_khoan": [],
                    "van_ban": {
                        "tieu_de": "Hợp đồng lao động",
                        "muc": [
                            {
                                "ten": TEN_MUC_SOAN,
                                "vung": "than",
                                # Chữ đổi theo TỪNG lượt gọi: `doi_muc` so `khoi`
                                # của phiên bản cũ với bản mới, nên hai lượt trả
                                # cùng một câu sẽ cho `doi_so_voi_truoc` rỗng và
                                # phép đo "sửa bằng lời có đổi được gì không"
                                # thành vô nghĩa. KHÔNG chữ số: `lam_sach_van_ban`
                                # thay mọi cụm có số không tra ngược được về
                                # nguồn bằng `[…]`, và hai bản thảo cùng bị thay
                                # sẽ trông giống hệt nhau trở lại.
                                "khoi": [
                                    {
                                        "noi_dung": "Hai bên thống nhất các nội dung nêu tại mục này."
                                        + " Đã soạn lại." * (self.lan_soan - 1),
                                        "bang": [],
                                    }
                                ],
                            }
                        ],
                    },
                }
            ), Usage(1, 1, 0.0)
        if "du" in props:  # gom_du_kien
            self.lan_gom += 1
            du = self.lan_gom >= 2
            ra = {"du": du, "ghi_chu": ""}
            if du:
                # Giá trị mang SỐ LẦN GỌI để mỗi lượt "đủ" khác lượt trước —
                # `ban_thao.doi_so_voi` (sửa bằng lời, phiên bản 2) cần thấy
                # facts thật sự đổi, không phải cùng một giá trị lặp lại.
                for k in props:
                    if k not in ("du", "ghi_chu"):
                        ra[k] = f"x{self.lan_gom}"
            return json.dumps(ra), Usage(1, 1, 0.0)
        if "cau_hoi_day_du" in props:  # giai_nghia — lượt nối tiếp
            return json.dumps({"cau_hoi_day_du": "tiếp tục", "ly_do": ""}), Usage(1, 1, 0.0)
        return json.dumps({"claims": [], "insufficient_evidence": True}), Usage(1, 1, 0.0)


@pytest.fixture
def graph_that_llm_gia(monkeypatch):
    from src.api import routes

    llm = LlmGia()
    monkeypatch.setattr(g, "llm_from_settings", lambda: llm)
    monkeypatch.setattr(g, "graph_soan_thao_cached", lambda: _GraphSoanThaoGia())
    # Task 25: nhánh sửa của `n_dung_ban_thao` nay đi qua `ban_thao.dung_lai`,
    # hàm đó tự import `graph_soan_thao_cached` VÀO NAMESPACE CỦA NÓ — patch
    # `g.graph_soan_thao_cached` một mình không còn chặn được lời gọi graph
    # thật ở nhánh sửa. Thiếu dòng dưới đây, "sửa bằng lời" trong test sẽ lặng
    # lẽ gọi graph SOẠN THẢO THẬT (và qua đó, LLM thật trả phí) thay vì double.
    monkeypatch.setattr(ban_thao, "graph_soan_thao_cached", lambda: _GraphSoanThaoGia())
    monkeypatch.setattr(routes, "_graph", None)
    return llm


@pytest.fixture
def don_dep():
    subs: list[str] = []
    yield subs
    if subs:
        with get_engine().begin() as c:
            c.execute(text("DELETE FROM ban_thao WHERE user_sub = ANY(CAST(:s AS uuid[]))"), {"s": subs})
            c.execute(text("DELETE FROM traces WHERE user_sub = ANY(:s)"), {"s": subs})
            c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = ANY(CAST(:s AS uuid[]))"), {"s": subs})
            c.execute(text("DELETE FROM users WHERE sub = ANY(:s)"), {"s": subs})


def _dem_trace(sub: str, endpoint: str) -> int:
    with get_engine().connect() as c:
        return c.execute(
            text("SELECT count(*) FROM traces WHERE user_sub = :s AND endpoint = :ep"),
            {"s": sub, "ep": endpoint},
        ).scalar_one()


def _anh_ban_thao(sub: str, bt_id: str) -> tuple:
    """Những gì một lượt KHÔNG-soạn (rẽ tắt, câu hỏi luật, lượt bị chặn) không
    được phép đụng tới. So cả bốn chứ không chỉ `phien_ban`: ghi đè nội dung mà
    quên tăng số phiên bản cũng là mất bản thảo, chỉ im lặng hơn."""
    bt = ban_thao.chi_tiet(sub, bt_id)
    return (bt["phien_ban"], bt["clauses"], bt["document"], bt["so_lan_sua"])


@pytest.mark.asyncio
async def test_soan_ngay_roi_sua_bang_loi_tren_chinh_ban_thao_do(
    client,
    cai_dat,
    khoa_ky,
    graph_that_llm_gia,
    don_dep,
):
    """Kịch bản chính sau Phase 14 (D14-B): một yêu cầu soạn MỚI trong chat dựng
    bản thảo NGAY — không hỏi checklist trước — và lượt sau sửa bằng lời phải
    rơi vào ĐÚNG bản thảo vừa dựng, không mở một bản thứ hai. Cùng một phiên,
    cùng một endpoint HTTP, không đụng gì tới `/api/v1/soan-thao` trực tiếp.

    Lượt đầu khoá luôn R3: "hợp đồng lao động" khớp `hdld`, một trong 29 mẫu —
    KLAW MỜI biểu mẫu (`assemble.MOI_BIEU_MAU`) ngay trong câu trả lời đã kèm
    bản thảo. Mời, không chặn: bản thảo vẫn ra ở chính lượt đó."""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    h = _bearer(khoa_ky, sub)

    r1 = await client.post(
        "/api/v1/tra-cuu",
        json={"query": f"soạn hợp đồng lao động {uuid.uuid4()}"},
        headers=h,
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["result_type"] == "ban_thao", "yêu cầu soạn mới phải ra bản thảo, không hỏi checklist"
    pid = r1.headers["X-Hoi-Thoai-Id"]
    bt_id = d1["ban_thao"]["id"]
    assert d1["ban_thao"]["phien_ban"] == 1
    # Mục THẬT của lượt soạn — nhánh lỗi của `hieu_tai_lieu` trả `soan_thao_hoi`
    # không `clauses` nào, nên dòng này là thứ tách "đã soạn" khỏi "đã degrade".
    assert [c["ten"] for c in d1["ban_thao"]["clauses"]] == [TEN_MUC_SOAN]
    # D14-A: nhãn thôi hiện, nhưng BẢN GHI vẫn nói thật bản thảo này chưa qua
    # checklist/rule/audit.
    assert d1["ban_thao"]["audit_report"]["muc_kiem"] == "tong_quat"
    # R3 — nhận ra một trong 29 thì mời biểu mẫu, và chỉ mời. (`soan_thao` là
    # tên trường của `soan_thao_goi_y` ở `TraCuuResponse`.)
    assert d1["soan_thao"]["loai"] == "hdld"
    assert MOI_BIEU_MAU.format(ten=d1["soan_thao"]["ten"]) in d1["answer"]
    assert _dem_trace(sub, "/api/v1/soan-thao") == 1

    r2 = await client.post(
        "/api/v1/tra-cuu",
        json={"query": "đổi lương thành 12 triệu", "hoi_thoai_id": pid},
        headers=h,
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["result_type"] == "ban_thao"
    assert d2["ban_thao"]["id"] == bt_id, "sửa bằng lời phải rơi vào bản thảo đang mở"
    assert d2["ban_thao"]["phien_ban"] == 2
    assert d2["ban_thao"]["doi_so_voi_truoc"] == [TEN_MUC_SOAN], "phải gọi tên đúng mục vừa đổi"
    # Lượt SỬA không tiêu hạn mức DỰNG: `dung_ban_thao_tong_quat` chỉ ghi dòng
    # `traces` ở nhánh dựng lần đầu, trần của lượt sửa là `TRAN_SUA` trên chính
    # bản thảo (test ngay dưới). Đường tổng quát KHÔNG có dòng `/sua` nào —
    # đó là endpoint HTTP riêng của drawer, không phải của lượt sửa bằng lời.
    assert _dem_trace(sub, "/api/v1/soan-thao") == 1


@pytest.mark.asyncio
async def test_het_tran_sua_thi_noi_ro_va_khong_ghi_de_ban_thao(
    client,
    cai_dat,
    khoa_ky,
    graph_that_llm_gia,
    don_dep,
):
    """Trần sửa (`ban_thao.TRAN_SUA`) trên đường soạn tổng quát — sửa tiếp một
    bản thảo đã chạm trần thì người dùng nhận `soan_thao_hoi` với đúng câu hết
    lượt, không phải một 500; và DÒNG bản thảo không đổi một chữ nào.

    `test_ban_thao_tong_quat.test_het_tran_sua_chan_bang_dung_bo_dem_cua_ban_thao`
    đã khoá phần node (`ban_thao_ket is None` + `LOI_HET_LAN_SUA`). Phép đo
    THÊM ở đây là hai thứ nó không chạm: hợp đồng HTTP của lượt bị chặn, và
    trạng thái DB sau đó — "không âm thầm dựng lại" là một khẳng định về dòng
    bản thảo, không về giá trị trả về của node."""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    h = _bearer(khoa_ky, sub)

    r1 = await client.post(
        "/api/v1/tra-cuu",
        json={"query": f"soạn hợp đồng lao động {uuid.uuid4()}"},
        headers=h,
    )
    assert r1.json()["result_type"] == "ban_thao"
    pid = r1.headers["X-Hoi-Thoai-Id"]
    bt_id = r1.json()["ban_thao"]["id"]

    # `ban_thao.kiem_tran_sua` kiểm trần trên CỘT ĐƠN ĐIỆU `so_lan_sua` của
    # DÒNG THẬT của bản thảo (migration 025) — không phải độ dài
    # `phien_ban_truoc` (ngăn xếp hoàn tác, `lui` bớt đi được). Mô phỏng "đã
    # chạm trần" vì thế phải ghi đúng cột đó (cùng khuôn
    # `test_ban_thao_api._cham_tran`).
    with get_engine().begin() as c:
        c.execute(
            text("UPDATE ban_thao SET so_lan_sua = :n WHERE id = CAST(:id AS uuid)"),
            {"n": ban_thao.TRAN_SUA, "id": bt_id},
        )
    truoc = _anh_ban_thao(sub, bt_id)

    r2 = await client.post(
        "/api/v1/tra-cuu",
        json={"query": "đổi thời hạn thành 2 năm", "hoi_thoai_id": pid},
        headers=h,
    )
    assert r2.status_code == 200, "chạm trần là một lời từ chối, không phải một 500"
    d2 = r2.json()
    assert d2["result_type"] == "soan_thao_hoi"
    assert d2["soan_thao_hoi"]["het_han_muc"] == ban_thao.LOI_HET_LAN_SUA
    assert _anh_ban_thao(sub, bt_id) == truoc, "chạm trần thì không được ghi đè gì"
    # Và lượt bị chặn không được lách thành một lượt DỰNG mới: đúng một dòng
    # hạn mức, của lần dựng đầu tiên.
    assert _dem_trace(sub, "/api/v1/soan-thao") == 1


@pytest.mark.asyncio
async def test_het_han_muc_dung_lan_dau_thi_hoi_lai_khong_tao_ban_thao(
    client,
    cai_dat,
    khoa_ky,
    graph_that_llm_gia,
    don_dep,
    monkeypatch,
):
    """Hạn mức NGÀY/THÁNG (`bao_ve.kiem_han_muc`, chỉ kiểm khi DỰNG lần đầu)
    hết thì không có bản thảo nào được tạo, không có dòng trace
    `/api/v1/soan-thao` nào, và người dùng nhận lại đúng thông điệp 429 của
    cổng hạn mức, không phải một 500.

    Từ Phase 14 lượt này đi đường soạn TỔNG QUÁT (`dung_ban_thao_tong_quat`),
    không còn `n_dung_ban_thao` — cổng hạn mức phải đứng ở CẢ HAI đường, nếu
    không đường mới thành lối vòng qua nó."""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    h = _bearer(khoa_ky, sub)

    goc_kiem_han_muc = bao_ve.kiem_han_muc

    def het(sub, plan, endpoint):
        # Chỉ chặn ĐÚNG giỏ soạn thảo — cổng HTTP (`cong_bao_ve_khach`) cũng gọi
        # hàm này cho `/api/v1/tra-cuu` (giỏ hỏi-đáp) TRƯỚC khi graph chạy, và
        # chặn cả hai giỏ sẽ cho 429 ở tầng auth, không phải ở `n_dung_ban_thao`.
        if endpoint == bao_ve.EP_SOAN_THAO:
            raise HTTPException(status_code=429, detail="Bạn đã dùng hết hạn mức soạn thảo hôm nay.")
        return goc_kiem_han_muc(sub, plan, endpoint)

    monkeypatch.setattr(bao_ve, "kiem_han_muc", het)

    # "cứ soạn" ép `du=True` ngay từ lượt đầu (Python phủ quyết `du` của model
    # khi còn trường bắt buộc trống, TRỪ KHI người dùng nói vậy) — một round
    # trip là đủ để chạm nhánh DỰNG LẦN ĐẦU của `n_dung_ban_thao`.
    r = await client.post(
        "/api/v1/tra-cuu",
        json={"query": f"soạn hợp đồng lao động {uuid.uuid4()}, cứ soạn giúp tôi luôn"},
        headers=h,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["result_type"] == "soan_thao_hoi"
    assert "hạn mức" in d["soan_thao_hoi"]["het_han_muc"]
    assert _dem_trace(sub, "/api/v1/soan-thao") == 0


# ── Checklist ĐANG MỞ DỞ: đường sống sót sau Phase 14 ─────────────────────
#
# Phase 14 (D14-B) bỏ checklist khỏi lượt soạn ĐẦU TIÊN của chat: một yêu cầu
# soạn mới đi thẳng `hieu_tai_lieu` → `dung_ban_thao_tong_quat`. Nó KHÔNG xoá
# cuộc hội thoại gom dữ kiện — người vào từ `/tai-lieu/hoi-thoai/{id}/
# sang-soan-thao` (hoặc còn dở từ trước) vẫn có `soan_thao_dang_mo`, và
# `_re_sau_route` vẫn đưa họ về `gom_du_kien`.
#
# Đường ấy MẤT phép đo ở tầng HTTP khi các test đầu file chuyển sang đo đường
# mới: cả bốn điều nó phải giữ — hỏi tiếp phần thiếu, dựng được bản thảo, ghi
# đúng một dòng hạn mức, giữ nguyên phiên soạn — không còn test nào chạm tới.
# Hai test dưới đây là phép đo đó, seed `soan_thao_dang_mo` đúng như màn hình
# chuyên dụng ghi xuống, không giả định lượt đầu mở checklist hộ.


@pytest.mark.asyncio
async def test_checklist_dang_mo_van_hoi_phan_thieu_roi_dung_ban_thao(
    client,
    cai_dat,
    khoa_ky,
    graph_that_llm_gia,
    don_dep,
):
    """Người ĐANG gom dữ kiện: vẫn được hỏi phần còn thiếu, vẫn nhận bản thảo
    khi đủ, lượt dựng vẫn ghi đúng một dòng hạn mức, và phiên soạn vẫn còn sau
    cả hai lượt."""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    h = _bearer(khoa_ky, sub)
    llm: LlmGia = graph_that_llm_gia

    llm.router_intent = "gioi_thieu"
    r0 = await client.post("/api/v1/tra-cuu", json={"query": "bạn là ai"}, headers=h)
    pid = r0.headers["X-Hoi-Thoai-Id"]
    assert hoi_thoai.ghi_soan_thao(sub, pid, {"loai": "hdld", "facts": {}, "ban_thao_id": None, "so_lan_sua": 0})

    llm.router_intent = "soan_thao"
    r1 = await client.post(
        "/api/v1/tra-cuu", json={"query": "tên tôi là Nguyễn Văn A", "hoi_thoai_id": pid}, headers=h
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["result_type"] == "soan_thao_hoi"
    assert d1["soan_thao_hoi"]["con_thieu"], "checklist mở dở phải hỏi tiếp phần còn thiếu"
    assert hoi_thoai.soan_thao_cua_phien(sub, pid)["loai"] == "hdld"
    assert _dem_trace(sub, "/api/v1/soan-thao") == 0, "lượt HỎI chưa dựng gì thì chưa trừ lượt"

    r2 = await client.post(
        "/api/v1/tra-cuu", json={"query": "lương 10 triệu, thời hạn 1 năm", "hoi_thoai_id": pid}, headers=h
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["result_type"] == "ban_thao"
    assert d2["ban_thao"]["phien_ban"] == 1
    assert ban_thao.chi_tiet(sub, d2["ban_thao"]["id"]) is not None
    assert _dem_trace(sub, "/api/v1/soan-thao") == 1
    assert hoi_thoai.soan_thao_cua_phien(sub, pid)["ban_thao_id"] == d2["ban_thao"]["id"]


@pytest.mark.asyncio
async def test_checklist_dang_mo_het_han_muc_thi_noi_ro_han_muc(
    client,
    cai_dat,
    khoa_ky,
    graph_that_llm_gia,
    don_dep,
    monkeypatch,
):
    """Cùng người ấy, hết hạn mức: nhận đúng câu của cổng hạn mức, không bản
    thảo nào được dựng, không dòng nào được ghi. (Đường soạn tổng quát có phép
    đo song sinh ở `test_het_han_muc_dung_lan_dau_...` ngay trên.)"""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    h = _bearer(khoa_ky, sub)
    llm: LlmGia = graph_that_llm_gia

    llm.router_intent = "gioi_thieu"
    r0 = await client.post("/api/v1/tra-cuu", json={"query": "bạn là ai"}, headers=h)
    pid = r0.headers["X-Hoi-Thoai-Id"]
    hoi_thoai.ghi_soan_thao(sub, pid, {"loai": "hdld", "facts": {}, "ban_thao_id": None, "so_lan_sua": 0})

    goc_kiem_han_muc = bao_ve.kiem_han_muc

    def het(sub, plan, endpoint):
        if endpoint == bao_ve.EP_SOAN_THAO:
            raise HTTPException(status_code=429, detail="Bạn đã dùng hết hạn mức soạn thảo hôm nay.")
        return goc_kiem_han_muc(sub, plan, endpoint)

    monkeypatch.setattr(bao_ve, "kiem_han_muc", het)
    llm.router_intent = "soan_thao"
    # `lan_gom = 1` để lượt gom KẾ TIẾP trả `du=True` — tức lượt này chạm đúng
    # nhánh DỰNG của `n_dung_ban_thao`, nơi cổng hạn mức đứng. Không dùng "cứ
    # soạn": đây là lượt NỐI TIẾP nên `giai_nghia` chạy trước và thay câu hỏi
    # bằng bản đã giải nghĩa, cụm ép `du` trong câu gốc không còn để regex
    # `gom_du_kien._RE_CU_SOAN` bắt.
    llm.lan_gom = 1
    r1 = await client.post(
        "/api/v1/tra-cuu", json={"query": "lương 10 triệu, thời hạn 1 năm", "hoi_thoai_id": pid}, headers=h
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["result_type"] == "soan_thao_hoi"
    assert "hạn mức" in d1["soan_thao_hoi"]["het_han_muc"]
    assert _dem_trace(sub, "/api/v1/soan-thao") == 0


# ── Review fix: bản thảo mở KHÔNG được tự nó ép lượt sau vào nhánh soạn thảo —
# CHỈ ý định `route` đoán cho LƯỢT ĐÓ mới quyết định (`_re_sau_route`/
# `assemble`, cả hai cùng sửa). Hai test dưới đây khoá đúng phân biệt đó ở
# tầng HTTP, cùng một phiên xuyên suốt. Phase 14 chỉ dời TIỀN ĐỀ: bản thảo mở
# nay là dòng `ban_thao` tổng quát của hội thoại, không còn là checklist đang
# gom dở — rủi ro và phép đo giữ nguyên. ────────────────────────────────────


@pytest.mark.asyncio
async def test_y_dinh_re_tat_giua_luc_dang_soan_van_re_tat_va_giu_nguyen_draft(
    client,
    cai_dat,
    khoa_ky,
    graph_that_llm_gia,
    don_dep,
):
    """`route` đoán một ý định RẼ TẮT (`gioi_thieu`) ở lượt thứ hai, giữa lúc
    phiên đang có bản thảo mở — phải nhận đúng câu trả lời rẽ tắt của
    `gioi_thieu`, KHÔNG bị kéo vào nhánh soạn thảo (không thêm dòng trace
    `/api/v1/soan-thao`), và bản thảo đang mở vẫn còn nguyên cho lượt sau.

    Phase 14 chỉ dời tiền đề: bản thảo đang mở nay là dòng `ban_thao` tổng quát
    (`ban_thao_tong_quat_dang_mo`), không còn là `soan_thao_cua_phien`. Rủi ro
    y nguyên — một bản thảo còn mở không được tự nó ép lượt sau vào nhánh
    soạn."""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    h = _bearer(khoa_ky, sub)
    llm: LlmGia = graph_that_llm_gia

    r1 = await client.post("/api/v1/tra-cuu", json={"query": f"soạn hợp đồng lao động {uuid.uuid4()}"}, headers=h)
    d1 = r1.json()
    assert d1["result_type"] == "ban_thao"
    assert [c["ten"] for c in d1["ban_thao"]["clauses"]] == [TEN_MUC_SOAN]
    pid = r1.headers["X-Hoi-Thoai-Id"]
    bt_id = d1["ban_thao"]["id"]
    truoc = _anh_ban_thao(sub, bt_id)

    llm.router_intent = "gioi_thieu"
    r2 = await client.post("/api/v1/tra-cuu", json={"query": "bạn là ai", "hoi_thoai_id": pid}, headers=h)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["result_type"] == "gioi_thieu"
    assert d2["soan_thao_hoi"] is None and d2["ban_thao"] is None
    assert _dem_trace(sub, "/api/v1/soan-thao") == 1, "gioi_thieu không được chạm nhánh soạn thảo"

    # Bản thảo vẫn còn nguyên — không bị ghi đè bởi lượt gioi_thieu.
    assert _anh_ban_thao(sub, bt_id) == truoc


@pytest.mark.asyncio
async def test_cau_hoi_that_giua_luc_dang_soan_duoc_tra_loi_binh_thuong_va_giu_nguyen_draft(
    client,
    cai_dat,
    khoa_ky,
    graph_that_llm_gia,
    don_dep,
    monkeypatch,
):
    """`route` đoán `tra_cuu` (câu hỏi luật thật) ở lượt thứ hai, giữa lúc
    phiên đang có bản thảo mở — phải đi HẾT đường tra cứu bình thường (không
    phải `soan_thao_hoi`/`ban_thao`), không thêm dòng trace `/api/v1/soan-thao`,
    và bản thảo vẫn còn nguyên để lượt ba sửa tiếp đúng nó, không mở bản thứ
    hai. Truy hồi bị khống chế trả rỗng (giống khuôn `test_tra_cuu.py`'s
    `test_partial_coverage_...`) để không gọi embedding thật — lượt này chỉ
    cần khoá ĐƯỜNG ĐI, không cần một câu trả lời tra cứu thật sự đúng."""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    h = _bearer(khoa_ky, sub)
    llm: LlmGia = graph_that_llm_gia

    r1 = await client.post("/api/v1/tra-cuu", json={"query": f"soạn hợp đồng lao động {uuid.uuid4()}"}, headers=h)
    d1 = r1.json()
    assert d1["result_type"] == "ban_thao"
    assert [c["ten"] for c in d1["ban_thao"]["clauses"]] == [TEN_MUC_SOAN]
    pid = r1.headers["X-Hoi-Thoai-Id"]
    bt_id = d1["ban_thao"]["id"]
    truoc = _anh_ban_thao(sub, bt_id)

    monkeypatch.setattr(g.Retriever, "hybrid", lambda self, q: [])
    monkeypatch.setattr(g.Retriever, "provision_ids", lambda self, hits: [])
    llm.router_intent = "tra_cuu"
    r2 = await client.post(
        "/api/v1/tra-cuu", json={"query": "thử việc tối đa bao nhiêu ngày", "hoi_thoai_id": pid}, headers=h
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["result_type"] not in ("soan_thao_hoi", "ban_thao")
    assert d2["soan_thao_hoi"] is None and d2["ban_thao"] is None
    assert _dem_trace(sub, "/api/v1/soan-thao") == 1, "câu hỏi luật thật không được chạm nhánh soạn thảo"

    # Bản thảo sống sót qua lượt hỏi-luật-thật xen giữa.
    assert _anh_ban_thao(sub, bt_id) == truoc

    # Lượt ba quay lại soạn (router lại đoán soan_thao) — sửa ĐÚNG bản thảo cũ,
    # không mở bản thứ hai: lượt tra cứu xen giữa không được cắt đứt đường
    # `ban_thao_tong_quat_dang_mo` của hội thoại.
    llm.router_intent = "soan_thao"
    r3 = await client.post("/api/v1/tra-cuu", json={"query": "đổi lương thành 12 triệu", "hoi_thoai_id": pid}, headers=h)
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["result_type"] == "ban_thao"
    assert d3["ban_thao"]["id"] == bt_id
    assert d3["ban_thao"]["phien_ban"] == 2
