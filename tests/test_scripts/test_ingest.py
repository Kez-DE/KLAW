import json
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


# ══ Kênh hỏng âm thầm: sửa provisions.jsonl mà không chạm documents.jsonl ══

TEP = ("documents.jsonl", "provisions.jsonl", "references.jsonl", "checksums.json")


def _seed_tam(tmp_path: Path) -> Path:
    for n in TEP:
        (tmp_path / n).write_text((SEED / n).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_ingest_RAISE_khi_seed_bi_sua_ma_checksums_khong_doi(tmp_path):
    """21 checksum trong `documents.jsonl` băm HTML + prov_rows, nên sửa TAY
    `provisions.jsonl` mà không chạm `documents.jsonl` để lại checksum không đổi
    → `ingest` `continue` cả 21 văn bản → trả `0/0/0`, KHÔNG PHÂN BIỆT ĐƯỢC với
    một lần re-run idempotent lành. Dữ liệu hỏng nằm trong git, không bao giờ vào
    DB, không ai biết. Và `checksums.json` thì không dòng Python nào đọc.

    Phép kiểm toàn vẹn chạy MỘT LẦN lúc bắt đầu, TRƯỚC vòng lặp document và
    trước cả `run_migrations()` — nên test này không cần Postgres."""
    seed = _seed_tam(tmp_path)
    p = seed / "provisions.jsonl"
    p.write_text(p.read_text(encoding="utf-8").replace("Điều 1", "Điều 1 BỊ SỬA", 1),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="provisions.jsonl"):
        ingest(seed)


def test_ingest_RAISE_khi_checksums_json_thieu_muc_cho_mot_file_seed(tmp_path):
    """Thiếu mục cũng là lỗi — bỏ qua im lặng thì phép kiểm chỉ là trang trí."""
    seed = _seed_tam(tmp_path)
    cs = json.loads((seed / "checksums.json").read_text(encoding="utf-8"))
    cs.get("files", {}).pop("provisions.jsonl", None)
    (seed / "checksums.json").write_text(json.dumps(cs, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="provisions.jsonl"):
        ingest(seed)


def test_ingest_CHAP_NHAN_seed_da_commit(tmp_path):
    """Mặt còn lại: phép kiểm phải xanh trên seed thật, nếu không nó chặn cả
    đường lành. Chỉ chạy phép kiểm toàn vẹn, không cần DB."""
    from scripts.ingest import _kiem_toan_ven
    _kiem_toan_ven(_seed_tam(tmp_path))
