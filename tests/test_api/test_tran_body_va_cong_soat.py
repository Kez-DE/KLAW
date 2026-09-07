"""H3 + M1 — trần kích thước body, không phản chiếu payload, và cổng cho `/soat`.

Ba lỗ trên cùng một đường:

1. Không có trần kích thước request. Đo được trên máy chủ dev: gửi 50 MB tới
   `POST /api/v1/soat` → **422 kèm phản hồi 50,00 MB**. Handler mặc định của
   FastAPI cho `RequestValidationError` trả nguyên `input` — tức toàn bộ payload
   bị từ chối được PHẢN CHIẾU lại. Một kẻ gọi biến mỗi byte upload thành một
   byte download, và làm thế mà không cần một dòng `traces` nào.

2. `exc.errors()` mang khoá `input`. Ngay cả với payload nhỏ, đó là dữ liệu
   người dùng vừa gửi đi vòng lại qua log của mọi proxy trên đường.

3. `POST /soat` KHÔNG có một `Depends` nào. Nó tách clause và chạy cả rule
   engine (tốn CPU, đồng bộ) rồi ghi một dòng `traces` — tức nó tiêu tài nguyên
   và ghi vào bảng số liệu của khoá luận mà không qua cổng nào.
"""

import json

import pytest

from src.config import Settings
from src.services import bao_ve

_HOP_LE = {"loai_van_ban": "hdld", "text": "Điều 1. Thời gian thử việc" * 5, "facts": {}}


@pytest.fixture
def cai_dat(monkeypatch):
    def dat(**kw):
        mac_dinh = {"rate_limit_so_luot": 0, "tran_chi_phi_ngay_usd": 0.0}
        s = Settings(_env_file=None, **{**mac_dinh, **kw})
        monkeypatch.setattr(bao_ve, "get_settings", lambda: s)
        return s

    return dat


# ══ 1. Trần kích thước body ═════════════════════════════════════════════════


async def test_body_qua_lon_thi_413_va_phan_hoi_NGAN(client):
    """413 TRƯỚC khi pydantic chạy, và phản hồi không mang theo payload.

    Đại lượng đáng khoá là TỈ LỆ khuếch đại: gửi lớn phải nhận nhỏ.
    """
    body = json.dumps({"loai_van_ban": "hdld", "text": "X" * (3 * 1024 * 1024)}).encode()
    r = await client.post(
        "/api/v1/soat", content=body, headers={"content-type": "application/json"}
    )
    assert r.status_code == 413
    assert len(r.content) < 1024, f"phản hồi {len(r.content)} byte cho một request bị từ chối"


async def test_body_vua_du_nho_van_qua_duoc_cong_kich_thuoc(client, cai_dat):
    """Trần không được chặn nhầm payload hợp lệ: `SoatRequest.text` tối đa 500k
    ký tự, nên mọi request đúng đắn đều nhỏ hơn 2 MB rất nhiều."""
    cai_dat(api_key="khoa-that")  # dừng ở cổng API key = đã qua cổng kích thước
    body = json.dumps({"loai_van_ban": "hdld", "text": "X" * 500_000, "facts": {}}).encode()
    r = await client.post(
        "/api/v1/soat", content=body, headers={"content-type": "application/json"}
    )
    assert r.status_code != 413


async def test_chunked_KHONG_di_vong_duoc_qua_tran(client):
    """`Transfer-Encoding: chunked` là cách duy nhất gửi body mà không khai
    `Content-Length` — tức là cách duy nhất đi vòng qua cổng ở trên. 411."""
    r = await client.post(
        "/api/v1/soat",
        content=b'{"loai_van_ban":"hdld"}',
        headers={"content-type": "application/json", "transfer-encoding": "chunked"},
    )
    assert r.status_code == 411


# ══ 2. 422 KHÔNG phản chiếu payload ═════════════════════════════════════════


async def test_422_KHONG_tra_lai_noi_dung_nguoi_dung_vua_gui(client):
    # Ngắn hơn `min_length=20` để chắc chắn rơi vào 422 — dấu nhận riêng chỉ
    # có ý nghĩa nếu request THẬT SỰ bị từ chối.
    dau = "DAU_NHAN_RIENG"
    r = await client.post("/api/v1/soat", json={"loai_van_ban": "hdld", "text": dau})
    assert r.status_code == 422
    assert dau not in r.text
    # Vẫn phải nói được SAI Ở ĐÂU — bỏ `input` không được biến 422 thành câm.
    assert "text" in r.text


async def test_422_van_giu_duoc_vi_tri_va_loai_loi(client):
    r = await client.post("/api/v1/soat", json={"loai_van_ban": "khong_ton_tai", "text": "x" * 30})
    assert r.status_code == 422
    chi_tiet = r.json()["detail"]
    assert any("loai_van_ban" in (d.get("loc") or []) for d in chi_tiet)
    assert all("input" not in d for d in chi_tiet)


# ══ 3. `/soat` có cổng ══════════════════════════════════════════════════════


async def test_soat_bat_API_key_khi_da_cau_hinh(client, cai_dat):
    cai_dat(api_key="khoa-that")
    assert (await client.post("/api/v1/soat", json=_HOP_LE)).status_code == 401


async def test_soat_di_qua_cong_rate_limit(client, cai_dat, monkeypatch):
    """`/soat` tốn CPU đồng bộ và ghi `traces`; một vòng `curl` không cổng làm
    treo tiến trình một-worker cho mọi người dùng khác."""
    cai_dat(api_key="")
    goi = []

    def chan(ip):
        goi.append(ip)
        raise bao_ve.HTTPException(status_code=429, detail="quá nhịp")

    monkeypatch.setattr(bao_ve, "kiem_rate_limit", chan)
    r = await client.post("/api/v1/soat", json=_HOP_LE)
    assert r.status_code == 429
    assert goi, "kiem_rate_limit không hề được gọi trên đường /soat"


async def test_soat_KHONG_tru_han_muc_cua_tai_khoan(client, cai_dat, monkeypatch):
    """`ENDPOINT_TON_LLM` cố ý loại `/soat` — nó không gọi LLM một lần nào, và
    trừ lượt của người dùng cho nó là bán cho họ thứ hệ thống không hề mua."""
    cai_dat(api_key="khoa-that")
    monkeypatch.setattr(
        bao_ve, "kiem_han_muc",
        lambda *a: pytest.fail("/soat không được đụng tới hạn mức của tài khoản"),
    )
    await client.post("/api/v1/soat", json=_HOP_LE)
    assert "/api/v1/soat" not in bao_ve.ENDPOINT_TON_LLM
