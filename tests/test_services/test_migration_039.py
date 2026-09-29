"""Migration 039 — `canh_doi_chieu` (quyết định 2026-09-28, mục 12).

Áp dụng SẠCH và IDEMPOTENT (lifespan chạy lại ở mỗi lần khởi động), nằm trong
`MIGRATIONS_KHOI_DONG`, khoá ngoại CASCADE theo `"references"`, và hai CHECK (câu
trích ≤ 400 ký tự, url https) chặn ở tầng DB. Mọi dòng thử nằm trong một giao
dịch bị ROLLBACK.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.main import MIGRATIONS_KHOI_DONG
from src.services.db import get_engine, run_migrations


def test_039_nam_trong_migration_khoi_dong():
    assert "039" in MIGRATIONS_KHOI_DONG


def _mot_canh(c) -> int:
    doc = c.execute(text("SELECT id FROM documents LIMIT 1")).scalar_one()
    return c.execute(
        text('INSERT INTO "references" (from_document_id, to_document_id, loai) VALUES (:d, :d, 21) RETURNING id'),
        {"d": doc},
    ).scalar_one()


def _ghi(
    c, rid: int, trich: str = "Nghị định số 12/2022/NĐ-CP ... hết hiệu lực", url: str = "https://congbao.chinhphu.vn/x"
):
    c.execute(
        text(
            "INSERT INTO canh_doi_chieu (reference_id, dieu_khoan, trich, url, kiem_boi, kiem_luc)"
            " VALUES (:r, 'Điều 66 khoản 4', :t, :u, 'thu', now())"
        ),
        {"r": rid, "t": trich, "u": url},
    )


@pytest.mark.integration
def test_039_ap_dung_sach_idempotent_va_xoa_canh_thi_xoa_bang_chung():
    run_migrations("039")
    run_migrations("039")
    with get_engine().connect() as c, c.begin() as tx:
        rid = _mot_canh(c)
        _ghi(c, rid)
        c.execute(text('DELETE FROM "references" WHERE id = :r'), {"r": rid})
        con = c.execute(text("SELECT count(*) FROM canh_doi_chieu WHERE reference_id = :r"), {"r": rid}).scalar_one()
        tx.rollback()
    assert con == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    ("trich", "url"),
    [("x" * 401, "https://congbao.chinhphu.vn/x"), ("câu trích", "http://congbao.chinhphu.vn/x")],
    ids=["trich-qua-400", "url-khong-https"],
)
def test_039_check_chan_trich_dai_va_url_khong_https(trich, url):
    run_migrations("039")
    with get_engine().connect() as c, c.begin() as tx:
        rid = _mot_canh(c)
        with pytest.raises(IntegrityError):
            _ghi(c, rid, trich, url)
        tx.rollback()
