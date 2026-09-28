"""H1 — không hàm nào được giữ một kết nối rồi xin kết nối thứ hai.

`_tim_kiem_sync` mở kết nối #1 (`with get_engine().connect() as c`) rồi, KHI VẪN
ĐANG GIỮ nó, gọi `danh_gia_toan_bo(get_engine(), as_of)` — hàm này tự mở kết nối
#2. Pool mặc định của SQLAlchemy là 5 + 10 overflow = 15, nên mỗi request cần
HAI suất trong một pool 15 suất: quá 7 request đồng thời là pool cạn, và
`pool_timeout` mặc định 30 giây biến mọi request còn lại thành 30 giây chờ rồi
500.

Đo được trên máy chủ dev (concurrency 24, `/api/v1/tim-kiem`):
  * median 30,181s, lẫn cả mã 500
  * `/api/v1/bo-loc` — một endpoint KHÔNG liên quan, bình thường 0,005s — đo
    được 29,832s TRONG lúc bão: cạn pool không giới hạn ở endpoint gây ra nó,
    nó làm chết đói toàn bộ tầng DB.

Test dưới đây không đo thời gian (một test thời gian là một test chớp tắt): nó
ĐẾM số kết nối đang mở tại đúng thời điểm `danh_gia_toan_bo` được gọi.
"""

from datetime import date

import pytest

from src.api import routes_tim_kiem


class _KetQua:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def one(self):
        return self._rows[0]

    def all(self):
        return self._rows

    def __iter__(self):
        # `hien_thi.tap_hien_thi` duyệt thẳng kết quả trên CÙNG kết nối #1.
        return iter(self._rows)


class _KetNoi:
    def __init__(self, engine):
        self._engine = engine

    def execute(self, sql, tham_so=None):
        # `_SQL_TONG` là câu duy nhất mà `_tim_kiem_sync` đọc kết quả có cấu
        # trúc; trang kết quả trả rỗng để test không phải giả lập shape của
        # `KetQuaTimKiem` — thứ nó đang khoá là THỨ TỰ mở kết nối, không phải
        # phép dựng response.
        if "count" in str(sql).lower():
            return _KetQua([{"tong_dieu_khoan": 0, "tong_van_ban": 0}])
        return _KetQua([])

    def __enter__(self):
        self._engine.dang_mo += 1
        self._engine.dinh_cao = max(self._engine.dinh_cao, self._engine.dang_mo)
        return self

    def __exit__(self, *a):
        self._engine.dang_mo -= 1
        return False


class _EngineGiaLap:
    """Đếm kết nối đang mở. `.connect()` trả một context manager thật."""

    def __init__(self):
        self.dang_mo = 0
        self.dinh_cao = 0

    def connect(self):
        return _KetNoi(self)


@pytest.fixture
def engine_dem(monkeypatch):
    eng = _EngineGiaLap()
    monkeypatch.setattr(routes_tim_kiem, "get_engine", lambda: eng)
    monkeypatch.setattr(
        routes_tim_kiem, "embedder_from_settings", lambda: type("E", (), {"model": "m"})()
    )
    return eng


def test_tim_kiem_KHONG_giu_ket_noi_khi_xin_ket_noi_thu_hai(engine_dem, monkeypatch):
    """`danh_gia_toan_bo` phải chạy khi TAY ĐANG KHÔNG cầm kết nối nào.

    Đây là điều kiện đủ để một request chỉ bao giờ chiếm MỘT suất pool tại một
    thời điểm — tức số request đồng thời chịu được bằng cỡ pool, không bằng
    một nửa nó.
    """
    thay = []
    monkeypatch.setattr(
        routes_tim_kiem, "danh_gia_toan_bo",
        lambda engine, as_of: thay.append(engine_dem.dang_mo) or {},
    )

    routes_tim_kiem._tim_kiem_sync(
        "thử việc", None, None, None, None, "lien_quan", 20, 0, date(2026, 1, 1)
    )

    assert thay == [0], f"đang giữ {thay} kết nối lúc gọi danh_gia_toan_bo"


def test_mot_request_tim_kiem_chi_chiem_MOT_suat_pool(engine_dem, monkeypatch):
    """Đỉnh cao số kết nối đồng thời của MỘT request phải là 1.

    Khoá chính đại lượng quyết định: pool 15 suất phục vụ 15 request đồng thời,
    không phải 7.
    """
    monkeypatch.setattr(
        routes_tim_kiem, "danh_gia_toan_bo",
        # `danh_gia_toan_bo` thật mở kết nối của nó — mô phỏng đúng việc đó.
        lambda engine, as_of: _mo_roi_dong(engine) or {},
    )

    routes_tim_kiem._tim_kiem_sync(
        "thử việc", None, None, None, None, "lien_quan", 20, 0, date(2026, 1, 1)
    )

    assert engine_dem.dinh_cao == 1, f"một request chiếm tới {engine_dem.dinh_cao} suất pool"


def _mo_roi_dong(engine):
    with engine.connect():
        pass


def test_engine_dat_pool_TUONG_MINH():
    """Mặc định 5 + 10 là mặc định của thư viện, không phải một quyết định của
    dự án — và `pool_timeout` 30 giây mặc định biến cạn pool thành 30 giây treo
    thay vì một lỗi nhanh."""
    from src.services.db import get_engine

    pool = get_engine().pool
    assert pool.size() == 20
    assert pool._max_overflow == 20
    assert pool._timeout == 5
    assert pool._pre_ping is True
