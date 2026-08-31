"""`so_ky_hieu` KHÔNG duy nhất trên toàn bộ `documents` — chỉ trong tầng sâu.

Global Constraint của dự án viết "định danh văn bản bằng `so_ky_hieu`, không bao
giờ bằng tên". Câu đó **đúng một nửa**, và agent làm định dạng trích dẫn tìm ra
nửa còn lại: `65/2006/QH11` thuộc HAI văn bản khác nhau — `Nghị quyết số
65/2006/QH11 Về việc thi hành Luật Luật sư` (id 15074) và `Luật sư số
65/2006/QH11` (id 15076).

Cả hai nằm ở tầng **metadata** (0 điều khoản), nên trích dẫn không bị ảnh hưởng —
trích dẫn chỉ sinh từ tầng sâu. Nhưng `/pham-vi` và `nguon` của
`partial_coverage` CÓ chạm tầng nông, nên mọi chỗ đó phải khoá theo `doc_id`,
không theo `so_ky_hieu`.

Hai test dưới đây khoá lại đúng ranh giới đó. Nếu một lần seed sau đưa trùng
`so_ky_hieu` vào tầng sâu, test đầu đỏ — và lúc ấy nó là lỗi thật, vì hai điều
luật khác nhau sẽ hiển thị cùng một địa chỉ trích dẫn.
"""

import pytest
from sqlalchemy import text

from src.services.db import get_engine

_SQL_TRUNG = text(
    "SELECT d.so_ky_hieu, count(DISTINCT d.id) AS n, string_agg(DISTINCT d.id, ',') AS ids"
    " FROM documents d {join}"
    " GROUP BY d.so_ky_hieu HAVING count(DISTINCT d.id) > 1"
)


@pytest.mark.integration
def test_tang_sau_moi_so_ky_hieu_la_duy_nhat():
    """Bất biến THẬT SỰ mà trích dẫn dựa vào."""
    with get_engine().connect() as c:
        trung = c.execute(
            text(str(_SQL_TRUNG).replace("{join}", "JOIN provisions p ON p.document_id = d.id"))
        ).mappings().all()
    assert not trung, (
        "hai văn bản CÓ ĐIỀU KHOẢN dùng chung so_ky_hieu → hai điều luật khác nhau sẽ hiển thị "
        f"cùng một địa chỉ trích dẫn: {[(r['so_ky_hieu'], r['ids']) for r in trung]}"
    )


@pytest.mark.integration
def test_tang_metadata_co_trung_so_ky_hieu_va_do_la_su_that_da_biet():
    """Ghi lại sự thật, không phải ước muốn.

    Test này KHÔNG khẳng định trùng lặp là tốt. Nó khoá lại rằng ta ĐÃ BIẾT có
    trùng, để không ai viết code coi `so_ky_hieu` là khoá trên toàn bảng.
    """
    with get_engine().connect() as c:
        trung = c.execute(text(str(_SQL_TRUNG).replace("{join}", ""))).mappings().all()
    assert trung, (
        "nếu test này đỏ thì trùng lặp đã được dọn — cập nhật docstring và có thể "
        "nâng `so_ky_hieu` thành khoá toàn bảng"
    )
    assert any(r["so_ky_hieu"] == "65/2006/QH11" for r in trung), (
        f"ca đã biết biến mất; các ca trùng hiện tại: {[r['so_ky_hieu'] for r in trung]}"
    )
