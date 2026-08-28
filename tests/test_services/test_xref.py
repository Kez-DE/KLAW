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


# ══ Unit tests — enumerated same-document lists ("Điều X và Điều Y ...") ═══
# The coordinator measured 88 same-document edges missed because only the
# LAST article in an enumerated list carries the trailing "của Bộ luật này"
# that marks it same-document — real examples: "Điều 3 và Điều 10 của Bộ luật
# này" (95942), "khoản 4 Điều 84, ... của Bộ luật này" (70811).


def test_liet_ke_va_ra_hai_canh():
    hits = find_xrefs("theo Điều 3 và Điều 10 của Bộ luật này")
    assert {h.so_dieu for h in hits} == {3, 10}
    assert all(h.cung_van_ban for h in hits)


def test_liet_ke_phay_ra_hai_canh():
    hits = find_xrefs("theo Điều 49, Điều 50 của Bộ luật này")
    assert {h.so_dieu for h in hits} == {49, 50}


def test_liet_ke_den_mo_rong_thanh_khoang():
    hits = find_xrefs("theo Điều 49 đến Điều 53 của Bộ luật này")
    assert {h.so_dieu for h in hits} == {49, 50, 51, 52, 53}
    assert all(h.cung_van_ban for h in hits)


def test_liet_ke_den_vuot_nguong_bi_bo_qua():
    # 500 - 1 = 499 > 30 — almost certainly a mis-parse, not a real range.
    assert find_xrefs("theo Điều 1 đến Điều 500 của Bộ luật này") == []


def test_dieu_don_le_van_dung_so_khong_bi_anh_huong_boi_liet_ke():
    # Regression guard: extending the pattern for lists must not reopen the
    # \d+ backtrack bug — "21" must stay "21", not fold to "2".
    hits = find_xrefs("theo Điều 21 của Bộ luật này")
    assert len(hits) == 1 and hits[0].so_dieu == 21


# ══ Unit tests — "các điều N, M và K" (bare numbers, "điều" said once) ═════
# A THIRD syntax, distinct from "Điều X và Điều Y": "điều" appears once, then
# bare numbers. Measured in the real corpus (95942): "các điều 22, 23 và 24
# của Bộ luật này", "các điều 228, 229, 230, 231, 232, 233 và 236 của Bộ luật
# này". A separate pattern (RE_LIET_KE_TRAN), not merged into RE_XREF — the
# two trigger conditions ("Điều" repeated vs. said once) don't overlap.


def test_lietke_tran_phay_va_ra_ba_canh():
    hits = find_xrefs("các điều 22, 23 và 24 của Bộ luật này")
    # RE_XREF also independently matches the bare "điều 22" (as it would
    # anywhere), tagged cung_van_ban=False since it has no trailing marker on
    # its own — harmless noise resolve_all discards before writing anything;
    # what matters is the cạnh (edge) resolve_all actually writes, i.e. the
    # cung_van_ban=True hits.
    cung_vb = {h.so_dieu for h in hits if h.cung_van_ban}
    assert cung_vb == {22, 23, 24}


def test_lietke_tran_bo_qua_khong_lien_tuc_khong_tu_dien_91():
    # 88,89,90,92,93 — 91 is skipped in the source text and must NOT be
    # invented; there's no "đến" here, just discrete comma/và items.
    hits = find_xrefs("các điều 88, 89, 90, 92 và 93 của Bộ luật này")
    assert {h.so_dieu for h in hits} == {88, 89, 90, 92, 93}


def test_lietke_tran_den_mo_rong_thanh_khoang():
    hits = find_xrefs("các điều 22 đến 26 của Bộ luật này")
    assert {h.so_dieu for h in hits} == {22, 23, 24, 25, 26}


def test_ca_hai_cu_phap_trong_mot_doan_khong_trung_khong_thieu():
    text_ = (
        "Theo Điều 3 và Điều 10 của Bộ luật này. "
        "Ngoài ra các điều 22, 23 và 24 của Bộ luật này cũng áp dụng."
    )
    hits = find_xrefs(text_)
    cung_vb = [h.so_dieu for h in hits if h.cung_van_ban]
    assert set(cung_vb) == {3, 10, 22, 23, 24}
    assert len(cung_vb) == 5  # không trùng, không thiếu, trong số cạnh sẽ ghi


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


@pytest.mark.integration
def test_resolve_all_khu_trung_cung_mot_cap_trong_mot_provision():
    """Cùng một provision trích 'Điều 5' hai lần, ở hai câu khác nhau — cùng
    một cặp (from_provision_id, to_provision_id) chỉ được ghi MỘT cạnh."""
    run_migrations()
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO documents (id, so_ky_hieu, loai_van_ban, ten, tinh_trang, checksum)"
            " VALUES ('xref-dedup-test', 'x/2024/QH15', 'Luật', 't', 'CHL', 'c')"
            " ON CONFLICT (id) DO NOTHING"))
        conn.execute(text(
            "INSERT INTO provisions (document_id, cap, so_hieu_cap, noi_dung, duong_dan, thu_tu)"
            " VALUES ('xref-dedup-test', 'dieu', '5', 'Điều 5. Nội dung X',"
            " 'x/2024/QH15 > Điều 5', 0)"))
        conn.execute(text(
            "INSERT INTO provisions (document_id, cap, so_hieu_cap, noi_dung, duong_dan, thu_tu)"
            " VALUES ('xref-dedup-test', 'dieu', '9',"
            " 'Điều 9. Theo Điều 5 của Bộ luật này và theo Điều 5 của Bộ luật này một lần nữa.',"
            " 'x/2024/QH15 > Điều 9', 1)"))
    try:
        resolve_all(engine)
        with engine.connect() as conn:
            dem = conn.execute(text(
                'SELECT count(*) FROM "references" r'
                " JOIN provisions fp ON fp.id = r.from_provision_id"
                " WHERE fp.document_id = 'xref-dedup-test' AND fp.so_hieu_cap = '9'"
            )).scalar_one()
        assert dem == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM documents WHERE id = 'xref-dedup-test'"))
