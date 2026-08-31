"""Tuyến phía client phải trả HTML, không phải 404.

`StaticFiles(html=True)` chỉ phục vụ file có thật và `index.html` cho THƯ MỤC.
Mọi tuyến do router phía client giữ (`/tra-cuu`, `/mien-tru`, `/van-ban/:id`…)
không tương ứng file nào trên đĩa, nên nó ném 404 thật. Hậu quả không nằm ở
SEO: bấm F5, mở bookmark, hay bấm một link được chia sẻ đều ra trang lỗi.

Mã trạng thái phải nói THẬT: tuyến có thật → 200; đường dẫn không tồn tại →
404 NHƯNG vẫn kèm HTML để React dựng trang 404 tử tế. Trả 200 cho mọi thứ là
nói dối với máy tìm kiếm; trả 404 rỗng là nói dối với người dùng.
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app

TUYEN_THAT = ["/", "/tra-cuu", "/soan-thao", "/soat", "/huong-dan", "/pham-vi", "/mien-tru"]


@pytest.fixture
def c():
    return TestClient(app)


@pytest.mark.parametrize("duong_dan", TUYEN_THAT)
def test_tuyen_client_tra_html_200(c, duong_dan):
    r = c.get(duong_dan)
    assert r.status_code == 200, f"{duong_dan} phải là trang thật, không phải 404"
    assert "text/html" in r.headers["content-type"]
    assert '<div id="root">' in r.text


def test_tuyen_dong_van_ban_tra_html_200(c):
    r = c.get("/van-ban/95942")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]


def test_duong_dan_la_tra_404_NHUNG_kem_html(c):
    r = c.get("/khong-he-ton-tai")
    assert r.status_code == 404, "404 phải là 404 thật — trả 200 cho mọi thứ là nói dối với crawler"
    assert "text/html" in r.headers["content-type"], "…nhưng vẫn phải có HTML để React dựng trang 404"


def test_api_va_health_KHONG_bi_vo_boc_static_che(c):
    assert c.get("/health").status_code == 200
    assert c.post("/api/v1/tra-cuu", json={}).status_code == 422, "phải là lỗi validate, không phải 404 của static"


def test_asset_khong_ton_tai_tra_404_KHONG_kem_html(c):
    # Một asset thiếu phải hỏng RÕ RÀNG. Trả index.html cho file .js không tồn
    # tại làm trình duyệt nuốt HTML như JavaScript và báo lỗi cú pháp khó hiểu.
    r = c.get("/assets/khong-co-that-12345.js")
    assert r.status_code == 404
    assert "text/html" not in r.headers.get("content-type", "")
