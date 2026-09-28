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


@pytest.mark.integration
def test_ingest_dung_lai_canh_cap_dieu_khoan():
    """`ingest` phải tự dựng lại dẫn chiếu cấp điều khoản, không chờ ai gọi tay.

    Trước bản này `xref.resolve_all` KHÔNG được gọi từ chỗ nào trong `src/` hay
    `scripts/` — 2.971 cạnh cấp điều khoản trong DB tồn tại thuần tuý vì có
    người đã chạy `tests/test_services/test_xref.py`. Một lần triển khai sạch
    nạp xong sẽ có 0 cạnh, và `/van-ban/{id}/lien-quan` bình thản báo "0 dẫn
    chiếu nội bộ" cho mọi văn bản — trông y hệt một câu trả lời đúng.

    Nặng hơn: `ingest` XOÁ mọi cạnh của một văn bản trước khi nạp lại nó
    (`DELETE FROM "references" WHERE from_document_id = :id`), nên nạp lại một
    văn bản đang âm thầm phá dẫn chiếu của chính nó.

    Test XOÁ trước rồi mới nạp: chỉ đếm thôi thì nó xanh nhờ đúng cái tác dụng
    phụ đang bị vá, và không chứng minh gì cả.
    """
    if not (SEED / "documents.jsonl").exists():
        pytest.skip("chạy `python -m scripts.build_seed` trước")

    from sqlalchemy import text as _text

    from src.services.db import get_engine

    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(_text('DELETE FROM "references" WHERE from_provision_id IS NOT NULL'))
        assert conn.execute(
            _text('SELECT count(*) FROM "references" WHERE from_provision_id IS NOT NULL')
        ).scalar_one() == 0

    ingest(SEED)

    with eng.connect() as conn:
        con_lai = conn.execute(
            _text('SELECT count(*) FROM "references" WHERE from_provision_id IS NOT NULL')
        ).scalar_one()
    assert con_lai > 2000, f"ingest phải dựng lại cạnh cấp điều khoản, chỉ thấy {con_lai}"


# ══ Nâng tầng nông TẠI CHỖ — không DELETE văn bản đã có hàng shallow ══

_ID_NANG = "__k1_nang_tai_cho__"


@pytest.mark.integration
def test_nang_tang_nong_TAI_CHO_giu_canh_va_thay_mo_dau_gia():
    """Một văn bản `shallow` (tên + một hàng `mo_dau`, cạnh hiệu lực trỏ vào và
    đi ra) có toàn văn → phải lên `deep` TẠI CHỖ. Nhánh DELETE-rồi-INSERT của
    `ingest` CASCADE xoá cạnh đi ra (`references_from_document_fk`) và chunk
    của nó: cạnh loai 22 "văn bản X quy định tôi hết hiệu lực" là chứng từ hiệu
    lực của chính văn bản này, mất nó là `effectivity` tụt phán quyết mà không
    ai thấy. Cạnh loai 22 còn sống sau lời gọi = văn bản KHÔNG bị xoá.

    Chạy trong một transaction rồi ROLLBACK: không để lại gì trong DB dùng chung.
    """
    from sqlalchemy import text as _text

    from scripts.ingest import _ghi_van_ban
    from src.services.db import get_engine

    sk = "999/2099/NĐ-CP"
    with get_engine().connect() as conn:
        tx = conn.begin()
        try:
            conn.execute(_text(
                "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, depth, checksum)"
                " VALUES (:i, :sk, 'Nghị định', 'Nghị định số 999/2099/NĐ-CP thử nâng tầng',"
                "         'chua_xac_dinh', 'shallow', 'metadata-only')"), {"i": _ID_NANG, "sk": sk})
            gia = conn.execute(_text(
                "INSERT INTO provisions (document_id, cap, so_hieu_cap, noi_dung, duong_dan, thu_tu)"
                " VALUES (:i, 'mo_dau', '', 'Nghị định số 999/2099/NĐ-CP thử nâng tầng', :dd, 0)"
                " RETURNING id"), {"i": _ID_NANG, "dd": f"{sk} > Mở đầu"}).scalar_one()
            conn.execute(_text(
                'INSERT INTO "references" (from_document_id, to_document_id, loai, raw_text) VALUES'
                " (:i, '139264', 22, 'Văn bản quy định hết hiệu lực'),"
                " ('139264', :i, 21, 'Thay thế')"), {"i": _ID_NANG})

            d = {"id": _ID_NANG, "so_ky_hieu": sk, "loai_van_ban": "Nghị định",
                 "ten": "Nghị định số 999/2099/NĐ-CP thử nâng tầng", "co_quan_ban_hanh": "Chính phủ",
                 "ngay_ban_hanh": "2099-01-01", "ngay_hieu_luc": "2099-02-01",
                 "ngay_het_hieu_luc": None, "tinh_trang": "HHL", "nguoi_ky": None,
                 "chuc_danh_nguoi_ky": None, "linh_vuc": None, "depth": "deep",
                 "nguon_url": f"vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/{_ID_NANG}",
                 "checksum": "toan-van"}
            mine = [
                {"local_id": 0, "parent_local_id": None, "cap": "mo_dau", "so_hieu_cap": "",
                 "tieu_de": "", "noi_dung": "CHÍNH PHỦ Căn cứ Bộ luật Lao động;", "duong_dan":
                 f"{sk} > Mở đầu", "source_node_id": None, "thu_tu": 0, "document_id": _ID_NANG},
                {"local_id": 1, "parent_local_id": None, "cap": "dieu", "so_hieu_cap": "1",
                 "tieu_de": "Điều 1", "noi_dung": "Điều 1. Phạm vi", "duong_dan":
                 f"{sk} > Điều 1", "source_node_id": "a1", "thu_tu": 1, "document_id": _ID_NANG},
                {"local_id": 2, "parent_local_id": 1, "cap": "khoan", "so_hieu_cap": "1",
                 "tieu_de": "Khoản 1", "noi_dung": "1. Nội dung khoản một.", "duong_dan":
                 f"{sk} > Điều 1 > Khoản 1", "source_node_id": None, "thu_tu": 2,
                 "document_id": _ID_NANG},
            ]
            refs = [{"from_document_id": _ID_NANG, "to_document_id": "139264", "loai": 12,
                     "raw_text": "45/2019/QH14"}]

            assert _ghi_van_ban(conn, d, mine, refs, "shallow") == (3, 1)

            doc = conn.execute(_text(
                "SELECT depth, checksum, co_quan_ban_hanh, tinh_trang FROM documents WHERE id = :i"),
                {"i": _ID_NANG}).one()
            assert tuple(doc) == ("deep", "toan-van", "Chính phủ", "HHL")
            mo_dau = conn.execute(_text(
                "SELECT id, noi_dung FROM provisions WHERE document_id = :i AND cap = 'mo_dau'"),
                {"i": _ID_NANG}).all()
            assert len(mo_dau) == 1 and mo_dau[0].id != gia, "hàng mo_dau giả phải nhường chỗ lời mở đầu thật"
            assert mo_dau[0].noi_dung.startswith("CHÍNH PHỦ")
            khoan_cha = conn.execute(_text(
                "SELECT c.duong_dan FROM provisions k JOIN provisions c ON c.id = k.parent_id"
                " WHERE k.document_id = :i AND k.cap = 'khoan'"), {"i": _ID_NANG}).scalar_one()
            assert khoan_cha == f"{sk} > Điều 1"
            canh = set(conn.execute(_text(
                'SELECT from_document_id, to_document_id, loai FROM "references"'
                " WHERE :i IN (from_document_id, to_document_id)"), {"i": _ID_NANG}).all())
            assert canh == {(_ID_NANG, "139264", 22), ("139264", _ID_NANG, 21),
                            (_ID_NANG, "139264", 12)}, canh
        finally:
            tx.rollback()
