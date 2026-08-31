"""`traces` phải có thời hạn — nghĩa vụ do CHÍNH lượt auth tạo ra.

Trước khi có `user_sub`, `traces.query` là dữ liệu không gắn tên: một câu hỏi
không biết của ai. Thêm `user_sub` biến nó thành dữ liệu **gắn tên**, trong một
bảng chưa từng có thời hạn xoá. Agent làm auth xếp việc này TRÊN cả việc bật
auth — đúng, vì chính thay đổi đó sinh ra nghĩa vụ.

Cách giải KHÔNG phải xoá dòng. Số liệu chứng minh khóa luận — chi phí, độ trễ,
`result_type`, số claim qua từng tầng, tên model — **không phải dữ liệu cá
nhân**. Dữ liệu cá nhân là `query` và `user_sub`, và chúng **không cần** cho số
liệu. Nên: ẩn danh hoá sau N ngày, giữ nguyên phần đo được.

Xoá dòng sẽ phá số liệu của khóa luận để giải một vấn đề mà ẩn danh hoá giải
được trọn vẹn.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from src.services.db import get_engine
from src.services.traces_an_danh import an_danh_traces

_CHEN = text(
    "INSERT INTO traces (id, ts, endpoint, query, config_name, result_type,"
    " latency_ms, cost_usd, user_sub)"
    " VALUES (:id, :ts, '/api/v1/tra-cuu', :q, 'test-an-danh', 'answer',"
    " 1234, 0.0042, :sub)"
)


@pytest.fixture
def hai_dong():
    cu = datetime.now(UTC) - timedelta(days=400)
    moi = datetime.now(UTC) - timedelta(days=1)
    with get_engine().begin() as c:
        c.execute(_CHEN, {"id": "an-danh-cu", "ts": cu, "q": "câu hỏi cũ của một người thật",
                          "sub": "11111111-1111-1111-1111-111111111111"})
        c.execute(_CHEN, {"id": "an-danh-moi", "ts": moi, "q": "câu hỏi mới",
                          "sub": "22222222-2222-2222-2222-222222222222"})
    yield
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM traces WHERE config_name = 'test-an-danh'"))


def _doc(id_: str) -> dict:
    with get_engine().connect() as c:
        return dict(c.execute(
            text("SELECT query, user_sub, latency_ms, cost_usd, result_type, endpoint"
                 " FROM traces WHERE id = :id"), {"id": id_}).mappings().one())


@pytest.mark.integration
def test_dong_qua_han_bi_an_danh_nhung_so_lieu_con_nguyen(hai_dong):
    n = an_danh_traces(get_engine(), sau_ngay=90)
    assert n >= 1
    r = _doc("an-danh-cu")
    assert r["query"] is None, "nội dung câu hỏi phải mất"
    assert r["user_sub"] is None, "định danh người dùng phải mất"
    # Số liệu của khóa luận PHẢI còn — đây là nửa còn lại của quyết định.
    assert r["latency_ms"] == 1234 and float(r["cost_usd"]) == 0.0042
    assert r["result_type"] == "answer" and r["endpoint"] == "/api/v1/tra-cuu"


@pytest.mark.integration
def test_dong_trong_han_khong_bi_dung(hai_dong):
    an_danh_traces(get_engine(), sau_ngay=90)
    r = _doc("an-danh-moi")
    assert r["query"] == "câu hỏi mới" and r["user_sub"] is not None


@pytest.mark.integration
def test_chay_hai_lan_cho_cung_ket_qua(hai_dong):
    lan1 = an_danh_traces(get_engine(), sau_ngay=90)
    lan2 = an_danh_traces(get_engine(), sau_ngay=90)
    assert lan1 >= 1
    assert lan2 == 0, "lượt hai không được đếm lại dòng đã ẩn danh — nếu đếm, cron sẽ báo động mãi"


@pytest.mark.integration
def test_sau_ngay_0_la_TAT_khong_phai_xoa_sach(hai_dong):
    """`0` ở các bộ đếm khác trong dự án nghĩa là TẮT. Giữ đúng quy ước đó —
    hiểu `0` thành "ẩn danh mọi thứ ngay" là mất trắng dữ liệu vì một số 0."""
    assert an_danh_traces(get_engine(), sau_ngay=0) == 0
    assert _doc("an-danh-cu")["query"] is not None
