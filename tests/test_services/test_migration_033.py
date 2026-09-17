"""Migration 033 — `ban_thao.phien_ban_ke_tiep` (spec 2026-09-17 Phase 4, D11
R1): bộ đếm số phiên bản KHÔNG BAO GIỜ cấp lại, tách khỏi cột `phien_ban` (cột
đó `lui` vẫn kéo NGƯỢC được). File này chứng minh migration áp dụng SẠCH trên
một DB đã có 024–032 và IDEMPOTENT, và rằng công thức backfill (`phien_ban +
1`) không để hàng nào bắt đầu SAU chính lịch sử của nó.
"""

import pytest
from sqlalchemy import text

from src.services.db import get_engine, run_migrations

pytestmark = pytest.mark.integration


def test_033_ap_dung_sach_tren_db_da_co_024_den_032_va_idempotent():
    run_migrations()
    run_migrations()
    with get_engine().connect() as c:
        cot = (
            c.execute(
                text(
                    "SELECT is_nullable, column_default FROM information_schema.columns"
                    " WHERE table_name = 'ban_thao' AND column_name = 'phien_ban_ke_tiep'"
                )
            )
            .mappings()
            .one()
        )
    assert cot["is_nullable"] == "NO", "phải NOT NULL sau backfill"
    assert cot["column_default"] == "2", "bản thảo mới luôn khởi tạo phien_ban=1, số kế tiếp phải là 2"


def test_033_backfill_khong_cap_lai_so_dang_song():
    """R1's bất biến trên MỌI hàng đã tồn tại từ trước: `phien_ban_ke_tiep`
    phải LỚN HƠN `phien_ban` đang sống — nếu không, lần `sua` đầu tiên sau
    migration này sẽ cấp lại đúng số của bản đang sống ngay lập tức."""
    run_migrations()
    with get_engine().connect() as c:
        vi_pham = c.execute(text("SELECT count(*) FROM ban_thao WHERE phien_ban_ke_tiep <= phien_ban")).scalar_one()
    assert vi_pham == 0
