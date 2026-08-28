import pytest
from sqlalchemy import text

from src.services.db import get_engine, run_migrations


@pytest.mark.integration
def test_postgres_khong_co_config_vietnamese():
    """Xác nhận giả định của spec: phải dùng simple + unaccent."""
    with get_engine().connect() as c:
        cfgs = {r[0] for r in c.execute(text("SELECT cfgname FROM pg_ts_config")).all()}
    assert "vietnamese" not in cfgs, "nếu có config vietnamese thì spec cần cập nhật"
    assert "simple" in cfgs


@pytest.mark.integration
def test_klaw_tsv_bo_dau_de_khop_khong_dau():
    run_migrations()
    with get_engine().connect() as c:
        hit = c.execute(text(
            "SELECT klaw_tsv('thời gian thử việc') @@ plainto_tsquery('simple', unaccent('thu viec'))"
        )).scalar_one()
    assert hit is True, "unaccent chưa hoạt động — 'thu viec' phải khớp 'thử việc'"


@pytest.mark.integration
def test_trigger_tu_cap_nhat_tsv_khi_insert():
    run_migrations()
    with get_engine().begin() as c:
        pid = c.execute(text("SELECT id FROM provisions LIMIT 1")).scalar_one()
        cid = c.execute(text(
            "INSERT INTO chunks (provision_id, noi_dung_embed, embedding_model, embedding_dim)"
            " VALUES (:p, 'thời gian thử việc tối đa', 'test', 4) RETURNING id"
        ), {"p": pid}).scalar_one()
        tsv = c.execute(text("SELECT tsv FROM chunks WHERE id = :i"), {"i": cid}).scalar_one()
        c.execute(text("DELETE FROM chunks WHERE id = :i"), {"i": cid})
    assert tsv, "trigger không chạy — tsv rỗng sau INSERT"


@pytest.mark.integration
def test_trigger_tu_cap_nhat_tsv_khi_update():
    """Task 6 ghi hàng loạt rồi có thể UPDATE lại `noi_dung_embed` về sau — nếu
    trigger chỉ bắt INSERT thì `tsv` cũ bị bỏ quên lại: sai âm thầm, không lỗi."""
    run_migrations()
    with get_engine().begin() as c:
        pid = c.execute(text("SELECT id FROM provisions LIMIT 1")).scalar_one()
        cid = c.execute(text(
            "INSERT INTO chunks (provision_id, noi_dung_embed, embedding_model, embedding_dim)"
            " VALUES (:p, 'nội dung ban đầu không liên quan', 'test', 4) RETURNING id"
        ), {"p": pid}).scalar_one()
        c.execute(text(
            "UPDATE chunks SET noi_dung_embed = 'thời gian thử việc tối đa' WHERE id = :i"
        ), {"i": cid})
        tsv_text, hit = c.execute(text(
            "SELECT tsv::text, tsv @@ plainto_tsquery('simple', unaccent('thu viec'))"
            " FROM chunks WHERE id = :i"
        ), {"i": cid}).one()
        c.execute(text("DELETE FROM chunks WHERE id = :i"), {"i": cid})
    assert hit is True, f"tsv không cập nhật theo UPDATE (còn giữ nội dung cũ): {tsv_text}"


@pytest.mark.integration
def test_migration_idempotent_tren_bang_chunks_co_du_lieu():
    """`test_migration_idempotent_chay_hai_lan_khong_loi` (test_migrations.py) chỉ
    chứng minh được idempotency trên bảng RỖNG. Bài học Plan 1: lỗi DROP+ADD
    constraint chỉ lộ ra khi bảng CÓ dữ liệu để CHECK phải kiểm thật. `006` không
    có ADD CONSTRAINT nào, nhưng vẫn phải tự chứng minh trên bảng `chunks` có sẵn
    một dòng — chạy lại hai lần không được phá dữ liệu đã có."""
    run_migrations()
    eng = get_engine()
    with eng.begin() as c:
        pid = c.execute(text("SELECT id FROM provisions LIMIT 1")).scalar_one()
        cid = c.execute(text(
            "INSERT INTO chunks (provision_id, noi_dung_embed, embedding_model, embedding_dim)"
            " VALUES (:p, 'thời gian thử việc tối đa', 'test', 4) RETURNING id"
        ), {"p": pid}).scalar_one()
    try:
        run_migrations()
        run_migrations()
        with eng.connect() as c:
            tsv_text = c.execute(text("SELECT tsv::text FROM chunks WHERE id = :i"), {"i": cid}).scalar_one()
        assert tsv_text, "tsv của dòng cũ bị mất sau khi chạy lại migration trên bảng có dữ liệu"
    finally:
        with eng.begin() as c:
            c.execute(text("DELETE FROM chunks WHERE id = :i"), {"i": cid})


@pytest.mark.integration
def test_006_backfill_tsv_null_khi_chay_lai():
    """M1: trigger chỉ chạy khi INSERT/UPDATE noi_dung_embed. Dòng tồn tại TRƯỚC
    khi `006` được áp giữ `tsv` NULL vĩnh viễn — vô hình với BM25, không lỗi,
    không cảnh báo. `006` phải tự chữa, và phải idempotent."""
    run_migrations()
    eng = get_engine()
    with eng.begin() as c:
        pid = c.execute(text("SELECT id FROM provisions LIMIT 1")).scalar_one()
        cid = c.execute(text(
            "INSERT INTO chunks (provision_id, noi_dung_embed, embedding_model, embedding_dim)"
            " VALUES (:p, 'thời gian thử việc tối đa', 'test-backfill', 4) RETURNING id"
        ), {"p": pid}).scalar_one()
        # UPDATE cột tsv KHÔNG kích trigger (trigger nghe `UPDATE OF noi_dung_embed`)
        # → tái tạo đúng dòng "tồn tại trước khi 006 chạy".
        c.execute(text("UPDATE chunks SET tsv = NULL WHERE id = :i"), {"i": cid})
    try:
        run_migrations()
        run_migrations()
        with eng.connect() as c:
            tsv_text = c.execute(text("SELECT tsv::text FROM chunks WHERE id = :i"), {"i": cid}).scalar_one()
        assert tsv_text, "006 không backfill tsv NULL"
    finally:
        with eng.begin() as c:
            c.execute(text("DELETE FROM chunks WHERE id = :i"), {"i": cid})
