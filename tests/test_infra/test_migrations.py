import pytest
from sqlalchemy import inspect, text

from src.services.db import get_engine, run_migrations

BANG_BAT_BUOC = {
    "documents", "provisions", "references", "chunks",
    "verified_provisions", "verified_documents", "traces",
}


@pytest.mark.integration
def test_migration_tao_du_7_bang():
    run_migrations()
    names = set(inspect(get_engine()).get_table_names())
    assert BANG_BAT_BUOC <= names, f"thiếu: {BANG_BAT_BUOC - names}"


@pytest.mark.integration
def test_migration_idempotent_chay_hai_lan_khong_loi():
    run_migrations()
    run_migrations()


@pytest.mark.integration
def test_provisions_co_index_tren_duong_dan_va_document_id():
    run_migrations()
    idx = {i["name"] for i in inspect(get_engine()).get_indexes("provisions")}
    assert "ix_provisions_duong_dan" in idx
    assert "ix_provisions_document_id" in idx


@pytest.mark.integration
def test_chunks_mang_embedding_model_de_chay_nhieu_bo_song_song():
    run_migrations()
    cols = {c["name"] for c in inspect(get_engine()).get_columns("chunks")}
    assert {"embedding_model", "embedding_dim"} <= cols


@pytest.mark.integration
def test_bang_references_dung_duoc_ten_khoa_sql():
    # "references" là từ khóa SQL — phải quote được
    run_migrations()
    with get_engine().connect() as c:
        c.execute(text('SELECT count(*) FROM "references"'))
