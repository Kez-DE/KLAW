import pytest
from sqlalchemy import text

from scripts.build_chunks import run
from src.services.db import get_engine


@pytest.mark.integration
def test_dry_run_khong_ghi_gi_va_bao_so_chunk():
    with get_engine().connect() as c:
        before = c.execute(text("SELECT count(*) FROM chunks")).scalar_one()
    r = run(dry_run=True)
    with get_engine().connect() as c:
        after = c.execute(text("SELECT count(*) FROM chunks")).scalar_one()
    assert before == after
    assert r["chunks"] > 0


@pytest.mark.integration
def test_chay_lai_cung_model_thi_thay_the_khong_nhan_doi():
    run()
    with get_engine().connect() as c:
        n1 = c.execute(
            text("SELECT count(*) FROM chunks WHERE embedding_model = :m"), {"m": "baai/bge-m3"}
        ).scalar_one()
    run()
    with get_engine().connect() as c:
        n2 = c.execute(
            text("SELECT count(*) FROM chunks WHERE embedding_model = :m"), {"m": "baai/bge-m3"}
        ).scalar_one()
    assert n1 == n2, "chạy lại phải DELETE bộ cũ rồi ghi lại, không cộng dồn"


@pytest.mark.integration
def test_moi_chunk_co_provision_id_ton_tai_va_co_embedding():
    run()
    with get_engine().connect() as c:
        orphan = c.execute(
            text(
                "SELECT count(*) FROM chunks ch"
                " WHERE NOT EXISTS (SELECT 1 FROM provisions p WHERE p.id = ch.provision_id)"
            )
        ).scalar_one()
        thieu = c.execute(
            text("SELECT count(*) FROM chunks WHERE embedding IS NULL AND embedding_model = :m"), {"m": "baai/bge-m3"}
        ).scalar_one()
    assert orphan == 0
    assert thieu == 0, "có chunk không có vector — embed thất bại mà không báo"
