from src.services.chunker import build_chunks, dem_token

DIEU = {"id": 10, "cap": "dieu", "so_hieu_cap": "25", "parent_id": None,
        "tieu_de": "Điều 25. Thời gian thử việc", "noi_dung": "Thời gian thử việc do hai bên thỏa thuận.",
        "duong_dan": "45/2019/QH14 > Điều 25"}
KHOAN_1 = {"id": 11, "cap": "khoan", "so_hieu_cap": "1", "parent_id": 10,
           "tieu_de": "1. Không quá 180 ngày", "noi_dung": "Không quá 180 ngày đối với người quản lý doanh nghiệp.",
           "duong_dan": "45/2019/QH14 > Điều 25 > Khoản 1"}


def test_dieu_ngan_thanh_MOT_chunk_gom_ca_khoan_con():
    chunks = build_chunks([DIEU, KHOAN_1], max_tokens=1500)
    assert len(chunks) == 1
    assert chunks[0].provision_id == 10
    assert "180 ngày" in chunks[0].noi_dung_embed, "Khoản con phải nằm trong chunk của Điều"


def test_chunk_luon_mang_context_header_duong_dan():
    chunks = build_chunks([DIEU, KHOAN_1], max_tokens=1500)
    assert chunks[0].noi_dung_embed.startswith("45/2019/QH14 > Điều 25")


def test_dieu_qua_dai_bi_cat_theo_khoan_va_moi_chunk_neo_vao_khoan():
    dai = dict(DIEU, noi_dung="x " * 2000)
    k2 = dict(KHOAN_1, id=12, so_hieu_cap="2",
              duong_dan="45/2019/QH14 > Điều 25 > Khoản 2", noi_dung="y " * 900)
    k1 = dict(KHOAN_1, noi_dung="z " * 900)
    chunks = build_chunks([dai, k1, k2], max_tokens=100)
    assert len(chunks) >= 2
    assert {c.provision_id for c in chunks} == {11, 12}, (
        "khi cắt theo Khoản, chunk phải neo vào provision_id của KHOẢN, không của Điều"
    )
    assert all("Điều 25" in c.noi_dung_embed for c in chunks), "vẫn phải giữ ngữ cảnh Điều"


def test_khong_sinh_chunk_rong():
    rong = dict(DIEU, noi_dung="", tieu_de="")
    assert build_chunks([rong], max_tokens=1500) == []


def test_dem_token_xap_xi_theo_tu_khong_theo_ky_tu():
    assert 3 <= dem_token("một hai ba") <= 6


# ══ 4 điều bắt buộc ngoài brief (coordinator, xem task-2-brief.md) ═════════


def test_khong_doc_tieu_de_chi_dua_vao_noi_dung():
    """`noi_dung` là toàn văn (nhãn+thân); `tieu_de` chỉ là nhãn ngắn — không đọc tieu_de."""
    p = dict(DIEU, noi_dung="", tieu_de="Điều 99. Có tiêu đề nhưng nội dung rỗng")
    assert build_chunks([p], max_tokens=1500) == []


def test_mo_dau_khong_lot_vao_chunk_du_bi_gan_nham_parent_id():
    """mo_dau/phu_luc không thuộc điều luật nào, không phải neo trích dẫn được —
    kể cả khi dữ liệu lỗi gán nhầm parent_id trỏ vào một Điều thật."""
    mo_dau_nham = {"id": 99, "cap": "mo_dau", "so_hieu_cap": "", "parent_id": 10,
                   "tieu_de": "", "noi_dung": "Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam",
                   "duong_dan": "45/2019/QH14"}
    chunks = build_chunks([DIEU, mo_dau_nham], max_tokens=1500)
    assert len(chunks) == 1
    assert chunks[0].provision_id == 10
    assert "Căn cứ Hiến pháp" not in chunks[0].noi_dung_embed


# ══ C1 (review-final-p2): chunk cấp Khoản mất tiêu đề Điều cha ═══════════════


def _dieu_dai_hai_khoan() -> list[dict]:
    """Điều có tiêu đề + câu dẫn, đủ dài để bị cắt theo Khoản."""
    dieu = dict(
        DIEU,
        noi_dung=(
            "Điều 42. Vi phạm quy định về đưa người lao động Việt Nam đi làm việc ở nước ngoài"
            " Mức phạt đối với doanh nghiệp dịch vụ được quy định như sau:"
        ),
    )
    k1 = dict(KHOAN_1, noi_dung="1. " + "alpha " * 900)
    k2 = dict(
        KHOAN_1, id=12, so_hieu_cap="2",
        duong_dan="45/2019/QH14 > Điều 25 > Khoản 2", noi_dung="2. " + "beta " * 900,
    )
    return [dieu, k1, k2]


def test_chunk_cap_khoan_mang_tieu_de_dieu_cha():
    """C1: header chỉ có `duong_dan` (số hiệu) — chủ đề của Điều biến mất khỏi
    index. 190 chunk thật đang bị vậy, phủ 6/49 gold anchor."""
    chunks = build_chunks(_dieu_dai_hai_khoan(), max_tokens=100)
    assert len(chunks) == 2
    for c in chunks:
        assert "đưa người lao động Việt Nam đi làm việc ở nước ngoài" in c.noi_dung_embed, (
            "chunk cấp Khoản phải mang tiêu đề của Điều cha"
        )


def test_chunk_cap_khoan_giu_ca_cau_dan_truoc_khoan_1():
    """Câu dẫn (chapeau) thường mang điều kiện áp dụng — mất nó là mất ràng buộc."""
    chunks = build_chunks(_dieu_dai_hai_khoan(), max_tokens=100)
    assert all("Mức phạt đối với doanh nghiệp dịch vụ" in c.noi_dung_embed for c in chunks)


def test_chunk_cap_khoan_KHONG_nhoi_toan_van_dieu_cha():
    """Chỉ tiêu đề + câu dẫn. Nhồi cả Khoản anh em vào là phình chunk và trùng
    lặp — đúng thứ việc cắt theo Khoản sinh ra để tránh."""
    chunks = build_chunks(_dieu_dai_hai_khoan(), max_tokens=100)
    theo_id = {c.provision_id: c.noi_dung_embed for c in chunks}
    assert "beta" not in theo_id[11], "chunk Khoản 1 không được chứa text của Khoản 2"
    assert "alpha" not in theo_id[12], "chunk Khoản 2 không được chứa text của Khoản 1"


def test_dieu_khong_co_noi_dung_rieng_van_cat_duoc_theo_khoan():
    """Điều rỗng thân (chỉ có Khoản con) không được sinh dòng trống thừa trong body."""
    dieu = dict(DIEU, noi_dung="")
    k1 = dict(KHOAN_1, noi_dung="1. " + "alpha " * 900)
    k2 = dict(KHOAN_1, id=12, so_hieu_cap="2",
              duong_dan="45/2019/QH14 > Điều 25 > Khoản 2", noi_dung="2. " + "beta " * 900)
    chunks = build_chunks([dieu, k1, k2], max_tokens=100)
    assert len(chunks) == 2
    assert all("\n\n" not in c.noi_dung_embed for c in chunks)
