import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

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


@pytest.mark.integration
def test_check_chan_tinh_trang_sai_chinh_ta():
    run_migrations()
    with pytest.raises(IntegrityError):
        with get_engine().begin() as c:
            c.execute(text(
                "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, checksum)"
                " VALUES ('__bad__', 'x/2020', 'Luật', 'x', 'hhl', 'c')"))


@pytest.mark.integration
def test_fk_chan_reference_tu_van_ban_khong_ton_tai():
    run_migrations()
    with pytest.raises(IntegrityError):
        with get_engine().begin() as c:
            c.execute(text(
                'INSERT INTO "references" (from_document_id, loai) VALUES (\'__khong_co__\', 4)'))


@pytest.mark.integration
def test_gia_tri_task8_se_ghi_deu_duoc_chap_nhan():
    """chua_xac_dinh và loai=0 là giá trị Task 8 THỰC SỰ ghi — CHECK phải cho qua.

    Test này ghim hợp đồng giữa Task 3 và Task 8; nếu nó đỏ thì ingest sẽ nổ.
    """
    run_migrations()
    with get_engine().begin() as c:
        c.execute(text(
            "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, checksum)"
            " VALUES ('__t8__', 'x/2020', 'Luật', 'x', 'chua_xac_dinh', 'c')"))
        c.execute(text('INSERT INTO "references" (from_document_id, loai) VALUES (\'__t8__\', 0)'))
        c.execute(text("DELETE FROM documents WHERE id = '__t8__'"))
