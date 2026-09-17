"""Handler `Exception` toàn cục (`src/main.py`, Task 2 plan
`ban-thao-tong-quat.md`) — một lỗi CHƯA AI BẮT phải trả JSON 500 CÓ header
CORS, không phải một 500 thoát ra ngoài `CORSMiddleware` qua
`ServerErrorMiddleware` (xem docstring `main.BatLoiMayChu`).

Route ném lỗi được gắn TẠM vào `app` thật rồi gỡ ngay sau test (không thêm
route debug thường trực vào `src/api/`, đúng Global Constraints của plan) —
dùng đúng `app` production để không trôi lệch với middleware/CORS thật.
"""

import pytest

from src.main import LOI_MAY_CHU_KHONG_XU_LY_DUOC, app

_DUONG_DAN = "/__kiem_tra_loi_toan_cuc"


@pytest.fixture
def route_nem_loi():
    async def _nem():
        raise RuntimeError("loi-gia-de-kiem-tra-500-toan-cuc")

    app.add_api_route(_DUONG_DAN, _nem, methods=["GET"])
    yield _DUONG_DAN
    app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != _DUONG_DAN]


async def test_loi_chua_bat_tra_500_kem_cors(client, route_nem_loi):
    r = await client.get(route_nem_loi, headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 500
    assert r.json() == {"detail": LOI_MAY_CHU_KHONG_XU_LY_DUOC}
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    # Không lộ tên exception lẫn message ra ngoài.
    assert "RuntimeError" not in r.text
    assert "loi-gia-de-kiem-tra-500-toan-cuc" not in r.text


async def test_http_exception_khong_bi_nuot(client):
    """`HTTPException` (401 của `nguoi_dung_bat_buoc`) vẫn hành xử y hệt —
    handler mới không được đổi hành vi của route bình thường."""
    r = await client.get("/api/v1/ban-thao")
    assert r.status_code == 401
