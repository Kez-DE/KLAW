"""Đầu-cuối: soạn thảo trong chat qua `POST /api/v1/tra-cuu` (Task 19).

Graph THẬT (không patch `routes._g` bằng một double toàn phần như các file
khác) — chỉ hai chỗ bị thay: `graph_tra_cuu.llm_from_settings` (route VÀ
gom_du_kien dùng CHUNG một `llm`) và `graph_tra_cuu.graph_soan_thao_cached`
(để không chạy `draft_generate`/`draft_audit` thật). `routes._graph` phải bị
reset về `None` trước mỗi test: nó là một singleton module-level, và `llm`
được chốt LÚC BUILD graph — monkeypatch `llm_from_settings` sau khi graph đã
build một lần (ở một test khác) sẽ không có tác dụng gì.

`LlmGia` không đọc nội dung prompt thật — nó trả JSON theo HÌNH DẠNG
`json_schema` nhận được, đúng cách brief mô tả: có `dang_tra_loi` → JSON
router, đúng `intent` bằng `llm.router_intent` (đổi được giữa các lượt); có
`du` → JSON dữ kiện (đếm số lần gọi để mô phỏng "lần đầu thiếu, lần sau đủ");
có `cau_hoi_day_du` → JSON giải nghĩa (một câu cố định, không số/Điều nào để
không vướng lưới `dinh_danh_bia`); còn lại → một JSON trung tính (đủ cho
`hoi_lai` degrade sạch qua nhánh lỗi của nó khi `intent` router trả là một ý
định KHÔNG phải `soan_thao` và lượt đó rơi vào một ngõ cụt tra cứu thường).

Review fix (state coordinator): `_re_sau_route`/`assemble` từng tự ý xét
THÊM `soan_thao_dang_mo` của phiên bên cạnh `intent` router vừa đoán, nên một
draft còn mở sẽ ép MỌI lượt sau — kể cả một câu hỏi luật thật — vào nhánh
soạn thảo. Cả hai chỗ đó giờ CHỈ gác trên `intent`; các test cuối file này
(`..._router_dua_ra_tra_cuu...`, `..._router_dua_ra_y_dinh_re_tat...`) khoá
đúng phân biệt đó ở tầng HTTP.
"""

import json
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from src.agents import graph_tra_cuu as g
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


class LlmGia:
    def __init__(self):
        self.lan_gom = 0
        # Ý định router trả cho LƯỢT KẾ TIẾP — test đổi giá trị này giữa các
        # lượt để mô phỏng `route` đoán khác nhau qua từng tin nhắn, đúng cách
        # `_re_sau_route`/`assemble` giờ CHỈ tin vào phán đoán này (không còn
        # tự ý xét thêm `soan_thao_dang_mo` của phiên).
        self.router_intent = "soan_thao"

    def chat(self, model, messages, json_schema=None):
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


@pytest.mark.asyncio
async def test_hoi_du_kien_dung_va_sua_bang_loi(client, cai_dat, khoa_ky, graph_that_llm_gia, don_dep):
    """Kịch bản chính (brief §Step 5): hỏi lần đầu thiếu dữ kiện, lần hai đủ thì
    dựng bản thảo, lần ba sửa bằng lời thì ra phiên bản mới — cùng một phiên,
    cùng một endpoint HTTP, không đụng gì tới `/api/v1/soan-thao` trực tiếp."""
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
    assert d1["result_type"] == "soan_thao_hoi"
    assert d1["soan_thao_hoi"]["con_thieu"], "phải còn dữ kiện bắt buộc để hỏi tiếp"
    pid = r1.headers["X-Hoi-Thoai-Id"]
    assert hoi_thoai.soan_thao_cua_phien(sub, pid)["loai"] == "hdld"

    r2 = await client.post(
        "/api/v1/tra-cuu",
        json={"query": "tên tôi là Nguyễn Văn A", "hoi_thoai_id": pid},
        headers=h,
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["result_type"] == "ban_thao"
    assert d2["ban_thao"]["phien_ban"] == 1
    bt_id = d2["ban_thao"]["id"]
    assert ban_thao.chi_tiet(sub, bt_id) is not None
    assert _dem_trace(sub, "/api/v1/soan-thao") == 1
    assert _dem_trace(sub, "/api/v1/soan-thao/sua") == 0

    r3 = await client.post(
        "/api/v1/tra-cuu",
        json={"query": "đổi lương thành 12 triệu", "hoi_thoai_id": pid},
        headers=h,
    )
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["result_type"] == "ban_thao"
    assert d3["ban_thao"]["id"] == bt_id
    assert d3["ban_thao"]["phien_ban"] == 2
    assert d3["ban_thao"]["doi_so_voi_truoc"], "sửa bằng lời phải đổi được ít nhất một trường"
    # Sửa KHÔNG thêm dòng trace `/api/v1/soan-thao` (đó là hạn mức DỰNG lần
    # đầu) — dòng mới của lần sửa mang endpoint `/sua`, một giỏ hạn mức khác.
    assert _dem_trace(sub, "/api/v1/soan-thao") == 1
    assert _dem_trace(sub, "/api/v1/soan-thao/sua") == 1


@pytest.mark.asyncio
async def test_het_lan_sua_thi_hoi_lai_khong_dung_lai_ban_thao(
    client,
    cai_dat,
    khoa_ky,
    graph_that_llm_gia,
    don_dep,
):
    """Trần sửa (`ban_thao.TRAN_SUA`) — sửa tiếp một bản thảo đã chạm trần
    không được dựng lại (không gọi `graph_soan_thao`, không thêm dòng trace
    `/api/v1/soan-thao/sua`); người dùng nhận `soan_thao_hoi` với thông điệp
    hết lượt, không phải một 500 hay một bản thảo âm thầm sai."""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    h = _bearer(khoa_ky, sub)

    r1 = await client.post(
        "/api/v1/tra-cuu",
        json={"query": f"soạn hợp đồng lao động {uuid.uuid4()}"},
        headers=h,
    )
    pid = r1.headers["X-Hoi-Thoai-Id"]
    r2 = await client.post(
        "/api/v1/tra-cuu",
        json={"query": "tên tôi là Nguyễn Văn A", "hoi_thoai_id": pid},
        headers=h,
    )
    assert r2.json()["result_type"] == "ban_thao"

    sd = hoi_thoai.soan_thao_cua_phien(sub, pid)
    hoi_thoai.ghi_soan_thao(sub, pid, {**sd, "so_lan_sua": ban_thao.TRAN_SUA})
    truoc = _dem_trace(sub, "/api/v1/soan-thao/sua")

    r3 = await client.post(
        "/api/v1/tra-cuu",
        json={"query": "đổi thời hạn thành 2 năm", "hoi_thoai_id": pid},
        headers=h,
    )
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["result_type"] == "soan_thao_hoi"
    assert d3["soan_thao_hoi"]["het_han_muc"] == ban_thao.LOI_HET_LAN_SUA
    assert _dem_trace(sub, "/api/v1/soan-thao/sua") == truoc, "chạm trần thì không được dựng thêm gì"


@pytest.mark.asyncio
async def test_het_han_muc_dung_lan_dau_thi_hoi_lai_khong_tao_ban_thao(
    client,
    cai_dat,
    khoa_ky,
    graph_that_llm_gia,
    don_dep,
    monkeypatch,
):
    """Hạn mức NGÀY/THÁNG (`bao_ve.kiem_han_muc`, chỉ kiểm khi DỰNG lần đầu —
    xem `n_dung_ban_thao`) hết thì không có bản thảo nào được tạo, không có
    dòng trace `/api/v1/soan-thao` nào, và người dùng nhận lại đúng thông
    điệp 429 của cổng hạn mức, không phải một 500."""
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


# ── Review fix: draft mở KHÔNG được tự nó ép lượt sau vào nhánh soạn thảo —
# CHỈ ý định `route` đoán cho LƯỢT ĐÓ mới quyết định (`_re_sau_route`/
# `assemble`, cả hai cùng sửa). Ba test dưới đây khoá đúng phân biệt đó ở
# tầng HTTP, cùng một phiên xuyên suốt. ─────────────────────────────────────


@pytest.mark.asyncio
async def test_y_dinh_re_tat_giua_luc_dang_soan_van_re_tat_va_giu_nguyen_draft(
    client,
    cai_dat,
    khoa_ky,
    graph_that_llm_gia,
    don_dep,
):
    """`route` đoán một ý định RẼ TẮT (`gioi_thieu`) ở lượt thứ hai, giữa lúc
    phiên đang có draft mở — phải nhận đúng câu trả lời rẽ tắt của `gioi_thieu`,
    KHÔNG bị kéo vào `gom_du_kien` (không thêm dòng trace `/api/v1/soan-thao`),
    và draft đang mở vẫn còn nguyên cho lượt sau."""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    h = _bearer(khoa_ky, sub)
    llm: LlmGia = graph_that_llm_gia

    r1 = await client.post("/api/v1/tra-cuu", json={"query": f"soạn hợp đồng lao động {uuid.uuid4()}"}, headers=h)
    assert r1.json()["result_type"] == "soan_thao_hoi"
    pid = r1.headers["X-Hoi-Thoai-Id"]
    facts_truoc = hoi_thoai.soan_thao_cua_phien(sub, pid)["facts"]

    llm.router_intent = "gioi_thieu"
    r2 = await client.post("/api/v1/tra-cuu", json={"query": "bạn là ai", "hoi_thoai_id": pid}, headers=h)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["result_type"] == "gioi_thieu"
    assert d2["soan_thao_hoi"] is None and d2["ban_thao"] is None
    assert _dem_trace(sub, "/api/v1/soan-thao") == 0, "gioi_thieu không được chạm nhánh soạn thảo"

    # Draft vẫn còn nguyên — không bị ghi đè bởi lượt gioi_thieu.
    assert hoi_thoai.soan_thao_cua_phien(sub, pid)["facts"] == facts_truoc


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
    phiên đang có draft mở — phải đi HẾT đường tra cứu bình thường (không phải
    `soan_thao_hoi`/`ban_thao`), không thêm dòng trace `/api/v1/soan-thao`, và
    draft vẫn còn nguyên để lượt ba quay lại soạn tiếp không mất dữ kiện đã
    cho. Truy hồi bị khống chế trả rỗng (giống khuôn `test_tra_cuu.py`'s
    `test_partial_coverage_...`) để không gọi embedding thật — lượt này chỉ
    cần khoá ĐƯỜNG ĐI, không cần một câu trả lời tra cứu thật sự đúng."""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    h = _bearer(khoa_ky, sub)
    llm: LlmGia = graph_that_llm_gia

    r1 = await client.post("/api/v1/tra-cuu", json={"query": f"soạn hợp đồng lao động {uuid.uuid4()}"}, headers=h)
    assert r1.json()["result_type"] == "soan_thao_hoi"
    pid = r1.headers["X-Hoi-Thoai-Id"]
    facts_truoc = hoi_thoai.soan_thao_cua_phien(sub, pid)["facts"]

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
    assert _dem_trace(sub, "/api/v1/soan-thao") == 0, "câu hỏi luật thật không được chạm nhánh soạn thảo"

    # Draft sống sót qua lượt hỏi-luật-thật xen giữa — không mất dữ kiện đã gom.
    assert hoi_thoai.soan_thao_cua_phien(sub, pid)["facts"] == facts_truoc

    # Lượt ba quay lại soạn (router lại đoán soan_thao) — vẫn dùng đúng draft cũ.
    llm.router_intent = "soan_thao"
    r3 = await client.post("/api/v1/tra-cuu", json={"query": "tên tôi là Nguyễn Văn A", "hoi_thoai_id": pid}, headers=h)
    assert r3.status_code == 200
    assert r3.json()["result_type"] == "ban_thao"
