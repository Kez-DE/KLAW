"""Ẩn danh hoá `traces` sau một thời hạn — không xoá dòng.

Nghĩa vụ này do lượt auth tạo ra: trước khi có `user_sub`, `traces.query` là
dữ liệu không gắn tên — một câu hỏi không biết của ai. Thêm `user_sub` biến nó
thành dữ liệu **gắn tên**, trong một bảng chưa từng có thời hạn xoá.

Ẩn danh hoá, không xoá, vì hai nửa của bảng này có bản chất khác nhau:

- **Số liệu** (`latency_ms`, `cost_usd`, `result_type`, số claim qua từng tầng,
  tên model, `cache_hit`) là bằng chứng đo được cho khóa luận. Không phải dữ
  liệu cá nhân. Xoá chúng là phá bằng chứng để giải một vấn đề chúng không gây ra.
- **Dữ liệu cá nhân** (`query`, `user_sub`) không cần cho bất kỳ số liệu nào ở trên.

Nên bỏ đúng nửa thứ hai và giữ trọn nửa thứ nhất.

Chạy bằng `scripts/an_danh_traces.py`. **Chưa có bộ hẹn giờ nào gọi nó** — đó là
việc lúc deploy, và nó được nêu trong `frontend/src/pages/DuLieu.tsx` như một
điều chưa có, chứ không im lặng.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine

# `query IS NOT NULL OR user_sub IS NOT NULL` giữ tính idempotent: lượt chạy thứ
# hai đếm 0 thay vì đếm lại cùng số dòng. Một cron báo "đã ẩn danh 4.000 dòng"
# mỗi đêm cho cùng 4.000 dòng là một cảnh báo mất tác dụng sau một tuần.
_SQL = text(
    "UPDATE traces SET query = NULL, user_sub = NULL"
    " WHERE ts < now() - make_interval(days => :sau_ngay)"
    "   AND (query IS NOT NULL OR user_sub IS NOT NULL)"
)


def an_danh_traces(engine: Engine, sau_ngay: int) -> int:
    """Bỏ `query` và `user_sub` của các dòng cũ hơn `sau_ngay`. Trả số dòng đã sửa.

    `sau_ngay <= 0` nghĩa là **TẮT**, không phải "ẩn danh mọi thứ ngay" — giữ
    đúng quy ước `0 = tắt` mà các bộ đếm khác trong dự án đã dùng. Hiểu ngược
    lại là mất trắng dữ liệu vì một số 0 trong cấu hình.
    """
    if sau_ngay <= 0:
        return 0
    with engine.begin() as conn:
        return conn.execute(_SQL, {"sau_ngay": sau_ngay}).rowcount
