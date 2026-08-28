import unicodedata

import pytest
from sqlalchemy import text

from src.services.db import get_engine, run_migrations
from src.services.xref import find_xrefs, resolve_all

# ══ Unit tests — find_xrefs, no DB (brief Step 1) ══════════════════════════


def test_bat_dieu_don_le():
    hits = find_xrefs("Theo quy định tại Điều 35 của Bộ luật này")
    assert len(hits) == 1
    assert hits[0].so_dieu == 35 and hits[0].so_khoan is None and hits[0].cung_van_ban is True


def test_bat_khoan_va_dieu():
    hits = find_xrefs("theo quy định tại khoản 2 Điều 35 của Bộ luật này")
    assert hits[0].so_khoan == 2 and hits[0].so_dieu == 35


def test_dan_chieu_van_ban_khac_thi_cung_van_ban_False():
    hits = find_xrefs("theo Điều 12 của Luật Bảo hiểm xã hội")
    assert hits[0].cung_van_ban is False


def test_bat_nhieu_dan_chieu_trong_mot_doan():
    hits = find_xrefs("quy định tại Điều 35 và khoản 1 Điều 36 của Bộ luật này")
    assert {(h.so_dieu, h.so_khoan) for h in hits} == {(35, None), (36, 1)}


def test_khong_bat_so_thu_tu_thuong():
    # "Điều" phải có số ngay sau; "35 ngày" không phải dẫn chiếu
    assert find_xrefs("trong thời hạn 35 ngày làm việc") == []


def test_khong_bat_chinh_tieu_de_dieu():
    # tiêu đề "Điều 21. Nội dung hợp đồng lao động" không phải dẫn chiếu tới chính nó
    assert find_xrefs("Điều 21. Nội dung hợp đồng lao động") == []


# ══ Unit tests — the three regressions the task brief warns about ══════════
# Plan 1 already paid for these lessons in prov_parser.py; xref.py reads the
# same raw noi_dung so it must survive the same defects.


def test_dieu_hau_to_chu_khong_bi_cat_cut():
    """"Điều 33a" (article inserted by an amending law) must resolve to 33a,
    never be truncated to plain 33 — a truncated match would point at the
    wrong provision."""
    hits = find_xrefs("theo Điều 33a của Bộ luật này")
    assert len(hits) == 1
    assert hits[0].so_dieu == 33
    assert hits[0].hau_to == "a"


def test_tieu_de_co_hau_to_chu_van_khong_bi_bat():
    # A heading like "Điều 33a. Bổ sung ..." must not become a self-reference
    # either — same period-lookahead rule as the plain-number heading case.
    assert find_xrefs("Điều 33a. Bổ sung một số điều") == []


def test_chuan_hoa_D_gach_ngang_U00D0():
    # "Ð" (LATIN CAPITAL LETTER ETH) is visually identical to "Đ"
    # (U+0110) — measured twice in document 96172. Build the corrupted string
    # explicitly by codepoint so the substitution is unambiguous.
    corrupted = "theo quy định tại Ðiều 35 của Bộ luật này"
    assert corrupted[18] == "Ð"  # guard: the test itself must contain the defect
    hits = find_xrefs(corrupted)
    assert len(hits) == 1 and hits[0].so_dieu == 35 and hits[0].cung_van_ban is True


def test_chuan_hoa_NFD_khong_lam_mat_dan_chieu():
    # Corpus is not pure NFC (96117 has 'ư' U+01B0 + combining U+0323 instead
    # of precomposed 'ự'); an NFD-decomposed run of "Điều 12 ..." must still
    # be recognized as one match, not silently dropped.
    decomposed = unicodedata.normalize("NFD", "theo Điều 12 của Bộ luật này")
    hits = find_xrefs(decomposed)
    assert len(hits) == 1 and hits[0].so_dieu == 12


# ══ Integration tests — resolve_all against the real corpus ════════════════


@pytest.mark.integration
def test_resolve_all_idempotent_goi_hai_lan_cung_so_dong():
    run_migrations()
    engine = get_engine()

    lan_1 = resolve_all(engine)
    with engine.connect() as conn:
        dem_1 = conn.execute(
            text('SELECT count(*) FROM "references" WHERE from_provision_id IS NOT NULL')
        ).scalar_one()

    lan_2 = resolve_all(engine)
    with engine.connect() as conn:
        dem_2 = conn.execute(
            text('SELECT count(*) FROM "references" WHERE from_provision_id IS NOT NULL')
        ).scalar_one()

    assert lan_1 == dem_1
    assert lan_2 == dem_2
    assert lan_1 == lan_2, f"chạy hai lần ra số cạnh khác nhau: {lan_1} != {lan_2}"
    assert lan_1 > 0, "không bắt được dẫn chiếu nào trên corpus thật — regex sai hoặc noi_dung rỗng"


@pytest.mark.integration
def test_resolve_all_khong_dung_242_dong_cap_van_ban_co_san():
    """242 dòng cấp văn bản (from_provision_id IS NULL) do MOJ cung cấp, từ
    Plan 1 — resolve_all() chỉ được thêm cạnh cấp điều khoản, không được đụng
    tới các dòng này."""
    run_migrations()
    engine = get_engine()
    resolve_all(engine)
    with engine.connect() as conn:
        dem = conn.execute(
            text('SELECT count(*) FROM "references" WHERE from_provision_id IS NULL')
        ).scalar_one()
    assert dem == 242
