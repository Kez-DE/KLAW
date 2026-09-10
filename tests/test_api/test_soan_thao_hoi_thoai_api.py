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
router; có `du` → JSON dữ kiện (đếm số lần gọi để mô phỏng "lần đầu thiếu,
lần sau đủ"); có `cau_hoi_day_du` → JSON giải nghĩa (một câu cố định, không
số/Điều nào để không vướng lưới `dinh_danh_bia`); còn lại → một JSON trung
tính không nhánh nào trong kịch bản này thật sự cần tới.
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

    def chat(self, model, messages, json_schema=None):
        props = (json_schema or {}).get("properties", {})
        if "dang_tra_loi" in props:  # route.v3
            return json.dumps(
                {
                    "intent": "soan_thao",
                    "loai_van_ban": "hdld",
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
