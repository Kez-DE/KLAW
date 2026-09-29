"""Migration 038 — `documents.hieu_luc_kiem_luc` (quyết định 2026-09-28, mục 6).

Áp dụng SẠCH và IDEMPOTENT (lifespan chạy lại ở mỗi lần khởi động), đúng kiểu,
cho NULL (dòng chưa từng đọc từ gateway), và nằm trong `MIGRATIONS_KHOI_DONG`.
"""

import pytest
from sqlalchemy import text

from src.main import MIGRATIONS_KHOI_DONG
from src.services.db import get_engine, run_migrations


def test_038_nam_trong_migration_khoi_dong():
    assert "038" in MIGRATIONS_KHOI_DONG


@pytest.mark.integration
def test_038_ap_dung_sach_idempotent_timestamptz_cho_null():
    run_migrations("038")
    run_migrations("038")
    with get_engine().connect() as c:
        cot = c.execute(
            text(
                "SELECT data_type, is_nullable FROM information_schema.columns"
                " WHERE table_name = 'documents' AND column_name = 'hieu_luc_kiem_luc'"
            )
        ).one()
    assert tuple(cot) == ("timestamp with time zone", "YES")
