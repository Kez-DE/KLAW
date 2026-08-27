from pathlib import Path

import pytest
from sqlalchemy import text

from scripts.ingest import ingest
from src.services.db import get_engine, run_migrations

SEED = Path("data/seed")


@pytest.mark.integration
def test_ingest_ghi_du_va_parent_id_tro_dung_provision_that():
    run_migrations()
    if not (SEED / "provisions.jsonl").exists():
        pytest.skip("chạy `python -m scripts.build_seed` trước")
    ingest(SEED)
    with get_engine().connect() as c:
        n_dieu = c.execute(text(
            "SELECT count(*) FROM provisions WHERE document_id='139264' AND cap='dieu'"
        )).scalar_one()
        orphan = c.execute(text(
            "SELECT count(*) FROM provisions p WHERE p.parent_id IS NOT NULL"
            " AND NOT EXISTS (SELECT 1 FROM provisions q WHERE q.id = p.parent_id)"
        )).scalar_one()
    assert n_dieu == 220, f"BLLĐ có {n_dieu} Điều, phải 220"
    assert orphan == 0, f"{orphan} provision có parent_id trỏ vào hư không"


@pytest.mark.integration
def test_ingest_lan_hai_khong_nhan_doi_du_lieu():
    run_migrations()
    if not (SEED / "provisions.jsonl").exists():
        pytest.skip("chạy build_seed trước")
    ingest(SEED)
    with get_engine().connect() as c:
        before = {
            table: c.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()
            for table in ("documents", "provisions", "references")
        }
    ingest(SEED)
    with get_engine().connect() as c:
        after = {
            table: c.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one()
            for table in ("documents", "provisions", "references")
        }
    assert before == after, f"ingest không idempotent — checksum không chặn được: {before} != {after}"
    assert all(n > 0 for n in before.values()), f"bảng rỗng sau ingest lần 1: {before}"


@pytest.mark.integration
def test_hai_van_ban_bay_hieu_luc_co_trong_db():
    run_migrations()
    if not (SEED / "documents.jsonl").exists():
        pytest.skip("chạy build_seed trước")
    ingest(SEED)
    with get_engine().connect() as c:
        rows = dict(c.execute(text(
            "SELECT id, tinh_trang FROM documents WHERE id IN ('168670','139094')"
        )).all())
    assert set(rows) == {"168670", "139094"}, "tập bẫy hiệu lực bị lọc mất"
