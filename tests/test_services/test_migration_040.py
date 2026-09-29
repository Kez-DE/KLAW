"""Migration 040 — `documents.link_pdf_ban_ky` và `anh_van_ban` (quyết định
2026-09-28, mục 9).

Áp dụng SẠCH và IDEMPOTENT, nằm trong `MIGRATIONS_KHOI_DONG`; link bản ký chỉ
nhận `https://datafiles.chinhphu.vn/`; ảnh trang 1 có trần 300 KB, kích thước khai
phải bằng bytes thật, và đi theo văn bản khi văn bản bị xoá. Mọi dòng thử nằm
trong một giao dịch bị ROLLBACK.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.main import MIGRATIONS_KHOI_DONG
from src.services.db import get_engine, run_migrations

_DOC = (
    "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, depth, checksum)"
    " VALUES ('thu-040', '1/2026/NĐ-CP', 'Nghị định', 'thử', 'CHL', 'metadata', 'thu')"
)
_ANH = "INSERT INTO anh_van_ban (doc_id, png, so_byte) VALUES ('thu-040', :png, :n)"


def test_040_nam_trong_migration_khoi_dong():
    assert "040" in MIGRATIONS_KHOI_DONG


@pytest.mark.integration
def test_040_ap_dung_sach_idempotent_va_xoa_van_ban_thi_xoa_anh():
    run_migrations("040")
    run_migrations("040")
    with get_engine().connect() as c, c.begin() as tx:
        c.execute(text(_DOC))
        c.execute(
            text(
                "UPDATE documents SET link_pdf_ban_ky = 'https://datafiles.chinhphu.vn/cpp/files/vbpq/x.signed.pdf'"
                " WHERE id = 'thu-040'"
            )
        )
        c.execute(text(_ANH), {"png": b"\x89PNG", "n": 4})
        c.execute(text("DELETE FROM documents WHERE id = 'thu-040'"))
        con = c.execute(text("SELECT count(*) FROM anh_van_ban WHERE doc_id = 'thu-040'")).scalar_one()
        tx.rollback()
    assert con == 0


@pytest.mark.integration
def test_040_link_ban_ky_chi_nhan_datafiles_chinhphu():
    run_migrations("040")
    with get_engine().connect() as c, c.begin() as tx:
        c.execute(text(_DOC))
        with pytest.raises(IntegrityError):
            c.execute(text("UPDATE documents SET link_pdf_ban_ky = 'https://vbpl.vn/x.pdf' WHERE id = 'thu-040'"))
        tx.rollback()


@pytest.mark.integration
@pytest.mark.parametrize(
    ("png", "n"),
    [(b"", 0), (b"x" * 307201, 307201), (b"\x89PNG", 5)],
    ids=["rong", "qua-300KB", "so-byte-lech"],
)
def test_040_check_kich_thuoc_anh(png, n):
    run_migrations("040")
    with get_engine().connect() as c, c.begin() as tx:
        c.execute(text(_DOC))
        with pytest.raises(IntegrityError):
            c.execute(text(_ANH), {"png": png, "n": n})
        tx.rollback()
