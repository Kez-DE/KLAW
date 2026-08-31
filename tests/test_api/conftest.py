"""Fixture dùng chung cho `tests/test_api/`.

`cai_dat` (bật/tắt auth qua `Settings.supabase_url`) và `khoa_ky` (khoá EC tự
sinh + JWKS giả lập) được viết cho `test_xac_thuc_han_muc.py` và đã có test
riêng chứng minh chúng đúng. Tái xuất Ở ĐÂY thay vì chép sang file thứ hai:
một bản sao của khối JWKS giả lập là một bản sao sẽ lệch pha khi PyJWT đổi chỗ
ghi cache — đúng cái bẫy mà docstring của `khoa_ky` đã phải giải thích một lần.

Import trong conftest chứ không trong từng file test: pytest hiểu tham số fixture
lấy từ conftest mà không cần tên đó có mặt trong module test, nên không sinh
F811 (ruff đọc `def test_x(cai_dat)` là định nghĩa lại tên đã import).
"""

from tests.test_api.test_xac_thuc_han_muc import (  # noqa: F401
    cai_dat,
    khoa_ky,
)
