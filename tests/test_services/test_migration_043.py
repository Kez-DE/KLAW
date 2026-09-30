"""Migration 043 — `bai_bo_dieu_khoan` (quyết định 2026-09-30 mục 9).

Áp dụng SẠCH và IDEMPOTENT (lifespan chạy lại ở mỗi lần khởi động), nằm trong
`MIGRATIONS_KHOI_DONG`, CASCADE theo `provisions`, và các CHECK chặn ở tầng DB. Ca
integration chỉ chạy bằng đường dẫn tệp tường minh; mọi dòng thử nằm trong một giao dịch
bị ROLLBACK.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.main import MIGRATIONS_KHOI_DONG
from src.services.db import get_engine, run_migrations


def test_043_nam_trong_migration_khoi_dong():
    assert "043" in MIGRATIONS_KHOI_DONG


def _ghi(c, trich: str = "Bãi bỏ Điều 16 Nghị định số 11/2013/NĐ-CP", url: str = "https://vbpl.vn/van-ban/chi-tiet/1"):
    pid, doc = c.execute(text("SELECT id, document_id FROM provisions WHERE cap = 'dieu' LIMIT 1")).one()
    c.execute(
        text(
            "INSERT INTO bai_bo_dieu_khoan (provision_id, boi_document_id, boi_dieu_khoan, trich, url, tu_ngay,"
            " kiem_boi, kiem_luc) VALUES (:p, :d, 'Điều 3 khoản 4', :t, :u, '2025-07-01', 'thu', now())"
        ),
        {"p": pid, "d": doc, "t": trich, "u": url},
    )
    return pid


@pytest.mark.integration
def test_043_ap_dung_sach_idempotent_va_khoa_ngoai_cascade():
    run_migrations("043")
    run_migrations("043")
    with get_engine().connect() as c, c.begin() as tx:
        _ghi(c)
        xoa = c.execute(
            text(
                "SELECT confrelid::regclass::text, confdeltype FROM pg_constraint"
                " WHERE conrelid = 'bai_bo_dieu_khoan'::regclass AND contype = 'f' ORDER BY 1"
            )
        ).all()
        tx.rollback()
    assert [tuple(r) for r in xoa] == [("documents", "c"), ("provisions", "c")]


@pytest.mark.integration
@pytest.mark.parametrize(
    ("trich", "url"),
    [("x" * 2001, "https://vbpl.vn/x"), ("câu trích", "http://vbpl.vn/x")],
    ids=["trich-qua-2000", "url-khong-https"],
)
def test_043_check_chan_trich_dai_va_url_khong_https(trich, url):
    run_migrations("043")
    with get_engine().connect() as c, c.begin() as tx:
        with pytest.raises(IntegrityError):
            _ghi(c, trich, url)
        tx.rollback()
