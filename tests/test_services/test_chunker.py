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
