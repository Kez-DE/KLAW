"""Migration 041 — `viec_doc_tai_lieu.nguon` (thiết kế `khuon-mau-thiet-ke.md` §3).

Ca tích hợp chỉ chạy ở bước Integrate, bằng đường dẫn tệp gõ rõ: áp SẠCH và
IDEMPOTENT, đúng kiểu, mặc định `tai_len`, CHECK chỉ nhận hai giá trị. Chỉ DDL và
catalog — không ghi dòng nào.
"""

import pytest
from sqlalchemy import text

from src.main import MIGRATIONS_KHOI_DONG
from src.services.db import get_engine, run_migrations


def test_041_nam_trong_migration_khoi_dong():
    assert "041" in MIGRATIONS_KHOI_DONG


@pytest.mark.integration
def test_041_ap_sach_idempotent_cot_mac_dinh_va_check():
    run_migrations("041")
    run_migrations("041")
    with get_engine().connect() as c:
        cot = (
            c.execute(
                text(
                    "SELECT data_type, is_nullable, column_default FROM information_schema.columns"
                    " WHERE table_name = 'viec_doc_tai_lieu' AND column_name = 'nguon'"
                )
            )
            .mappings()
            .one()
        )
        check = (
            c.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                    " WHERE conrelid = 'viec_doc_tai_lieu'::regclass AND conname = 'ck_viec_doc_nguon'"
                )
            )
            .scalars()
            .all()
        )
    assert (cot["data_type"], cot["is_nullable"]) == ("text", "NO")
    assert cot["column_default"].startswith("'tai_len'")
    assert len(check) == 1, "chạy lại migration không được nhân ràng buộc"
    assert "'tai_len'" in check[0] and "'khuon_mau'" in check[0]
