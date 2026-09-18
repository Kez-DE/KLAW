"""Ảnh đã tách, lưu theo hội thoại — quyết định 2026-09-18
(`docs/decisions/2026-09-18-trung-thuc-bieu-mau-va-media.md`), migration 035.

Chạm Postgres thật, vì mọi khẳng định ở đây là khẳng định về CỘT và TRUY VẤN,
không về Python:

1. Mô tả ảnh đi và về nguyên vẹn qua cột JSONB `don_vi`, và bytes đi về qua
   bảng `anh_tai_lieu` — hai kênh riêng, đúng hình dạng quyết định đặt ra.
2. RANH GIỚI TÀI KHOẢN. Một con dấu, một chữ ký quét là dữ liệu cá nhân của
   BÊN THỨ BA chưa từng dùng KLAW. Tài khoản B hỏi ảnh của A phải ra `None` —
   không phân biệt được với một id không có thật.
3. CASCADE XOÁ theo hội thoại, cả đường xoá CỨNG (`DELETE FROM hoi_thoai`, khoá
   ngoại 026) lẫn đường xoá MỀM (`tai_lieu.xoa_theo_hoi_thoai`). Đây là điều
   khoản đánh đổi của chính quyết định: ảnh được phép nằm trong Postgres ĐÚNG
   BẰNG đời cuộc hội thoại, không lâu hơn một dòng.
4. Ràng buộc DB tự chặn kiểu lạ và ảnh quá trần, không tin vào kỷ luật người
   gọi — cùng hạng `ck_du_kien_tai_lieu_co_neo` của 026.

Ảnh ở đây là PNG 1×1 sinh tại chỗ. Không một ảnh thật nào vào kho mã.
"""

import pytest
from sqlalchemy import text

from src.services import tai_lieu as tl
from src.services.db import get_engine
from src.services.doc_tai_lieu import AnhTaiLieu, DonViVanBan

_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IENDaE\x82"
)
_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 16

_ANH = (
    AnhTaiLieu(
        phan="word/media/logo.png", kieu="image/png",
        rong=1733550, cao=537039, vung="dau_trang", thu_tu=0,
    ),
    AnhTaiLieu(
        phan="word/media/dau.jpeg", kieu="image/jpeg",
        rong=914400, cao=914400, vung="chan_trang", thu_tu=0,
    ),
)
_BYTE = {
    "word/media/logo.png": ("image/png", _PNG),
    "word/media/dau.jpeg": ("image/jpeg", _JPEG),
}
_DON_VI = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="PHIẾU ĐÁNH GIÁ", anh=_ANH),
    DonViVanBan(chi_so=1, trang=1, offset_dau=15, noi_dung="Chuyên cần", anh=_ANH),
]


@pytest.fixture
def phien():
    with get_engine().begin() as c:
        sub = str(
            c.execute(
                text("INSERT INTO users (sub) VALUES (gen_random_uuid()) RETURNING sub")
            ).scalar_one()
        )
        ht = str(
            c.execute(
                text(
                    "INSERT INTO hoi_thoai (user_sub, tieu_de) "
                    "VALUES (CAST(:u AS uuid), 'thử') RETURNING id"
                ),
                {"u": sub},
            ).scalar_one()
        )
    yield sub, ht
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM users WHERE sub = CAST(:u AS uuid)"), {"u": sub})


def _viec(sub: str, ht: str) -> str:
    with get_engine().begin() as c:
        return str(
            c.execute(
                text(
                    "INSERT INTO viec_doc_tai_lieu "
                    "(user_sub, hoi_thoai_id, ten_tep, dau_van_ban, so_byte, so_trang, trang_thai) "
                    "VALUES (CAST(:u AS uuid), CAST(:h AS uuid), 'phieu.docx', "
                    "'sha256:x len=1', 100, 1, 'xong') RETURNING id"
                ),
                {"u": sub, "h": ht},
            ).scalar_one()
        )


def _dem(viec: str) -> int:
    with get_engine().connect() as c:
        return c.execute(
            text("SELECT count(*) FROM anh_tai_lieu WHERE viec_id = CAST(:v AS uuid)"),
            {"v": viec},
        ).scalar_one()


# ═══ Đi và về ════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_mo_ta_anh_di_va_ve_NGUYEN_VEN_qua_cot_don_vi(phien):
    """JSON không có tuple. Quên chuyển lại thì `DonViVanBan` hết bằng chính nó
    sau một vòng lưu–đọc, và phép so sánh hỏng im lặng."""
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_don_vi(get_engine(), viec, _DON_VI)

    ve = tl.don_vi_cua(get_engine(), viec, sub)
    assert ve == _DON_VI
    assert isinstance(ve[0].anh, tuple)
    assert (ve[0].anh[0].vung, ve[0].anh[0].thu_tu) == ("dau_trang", 0)
    assert (ve[0].anh[1].rong, ve[0].anh[1].cao) == (914400, 914400)


@pytest.mark.integration
def test_bytes_di_va_ve_NGUYEN_VEN_qua_bang_rieng(phien):
    sub, ht = phien
    viec = _viec(sub, ht)

    assert tl.luu_anh(get_engine(), viec, _BYTE) == 2
    assert tl.anh_cua(get_engine(), viec, sub, "word/media/logo.png") == ("image/png", _PNG)
    assert tl.anh_cua(get_engine(), viec, sub, "word/media/dau.jpeg") == ("image/jpeg", _JPEG)


@pytest.mark.integration
def test_luu_LAI_cung_tai_lieu_KHONG_nhan_doi_con_dau(phien):
    """Một lượt tải lại/thử lại cùng tệp không được sinh dòng thứ hai —
    `UNIQUE (viec_id, phan)` cộng `ON CONFLICT DO NOTHING`."""
    sub, ht = phien
    viec = _viec(sub, ht)

    tl.luu_anh(get_engine(), viec, _BYTE)
    tl.luu_anh(get_engine(), viec, _BYTE)

    assert _dem(viec) == 2


@pytest.mark.integration
def test_tai_lieu_KHONG_co_anh_khong_cham_DB(phien):
    sub, ht = phien
    viec = _viec(sub, ht)

    assert tl.luu_anh(get_engine(), viec, {}) == 0
    assert _dem(viec) == 0


# ═══ Ranh giới tài khoản ═════════════════════════════════════════════════════


@pytest.mark.integration
def test_tai_khoan_B_KHONG_doc_duoc_anh_cua_tai_khoan_A(phien):
    """Con dấu và chữ ký quét là dữ liệu cá nhân của bên thứ ba. `None` ở tầng
    DỮ LIỆU, không phải một phép kiểm thứ hai ở tầng API — một id lọt qua biên
    HTTP bằng cách nào cũng không đọc ra bytes."""
    sub_a, ht_a = phien
    viec_a = _viec(sub_a, ht_a)
    tl.luu_anh(get_engine(), viec_a, _BYTE)

    with get_engine().begin() as c:
        sub_b = str(
            c.execute(
                text("INSERT INTO users (sub) VALUES (gen_random_uuid()) RETURNING sub")
            ).scalar_one()
        )
    try:
        # B biết ĐÚNG viec_id và ĐÚNG tên part của A — và vẫn không đọc được.
        assert tl.anh_cua(get_engine(), viec_a, sub_b, "word/media/logo.png") is None
        # Không phân biệt được với một ảnh không tồn tại: cùng một `None`.
        assert tl.anh_cua(get_engine(), viec_a, sub_b, "word/media/khong-co.png") is None
        # Chính chủ thì vẫn đọc được — nếu không, hai dòng trên đúng một cách
        # tầm thường vì bảng rỗng.
        assert tl.anh_cua(get_engine(), viec_a, sub_a, "word/media/logo.png") is not None
    finally:
        with get_engine().begin() as c:
            c.execute(text("DELETE FROM users WHERE sub = CAST(:u AS uuid)"), {"u": sub_b})


# ═══ Cascade xoá ═════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_XOA_MEM_hoi_thoai_don_sach_anh(phien):
    """`routes_hoi_thoai.xoa` xoá MỀM, nên cascade của khoá ngoại không nổ —
    `tai_lieu.xoa_theo_hoi_thoai` là đường duy nhất dọn, và nó phải dọn CẢ ảnh."""
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_don_vi(get_engine(), viec, _DON_VI)
    tl.luu_anh(get_engine(), viec, _BYTE)
    assert _dem(viec) == 2

    tl.xoa_theo_hoi_thoai(get_engine(), ht, sub)

    assert _dem(viec) == 0
    assert tl.anh_cua(get_engine(), viec, sub, "word/media/logo.png") is None
    with get_engine().connect() as c:
        assert c.execute(text("SELECT count(*) FROM anh_tai_lieu")).scalar_one() >= 0


@pytest.mark.integration
def test_XOA_CUNG_hoi_thoai_cascade_xuong_tan_anh(phien):
    """Khoá ngoại 026 (`hoi_thoai` → `viec_doc_tai_lieu`) cộng khoá ngoại 035
    (`viec_doc_tai_lieu` → `anh_tai_lieu`): một lệnh xoá hội thoại phải mang
    con dấu đi cùng, kể cả khi một đường xoá mới được thêm ở chỗ khác và người
    viết quên dọn."""
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_anh(get_engine(), viec, _BYTE)
    assert _dem(viec) == 2

    with get_engine().begin() as c:
        c.execute(text("DELETE FROM hoi_thoai WHERE id = CAST(:h AS uuid)"), {"h": ht})

    assert _dem(viec) == 0


@pytest.mark.integration
def test_XOA_TAI_KHOAN_cascade_xuong_tan_anh(phien):
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_anh(get_engine(), viec, _BYTE)

    with get_engine().begin() as c:
        c.execute(text("DELETE FROM users WHERE sub = CAST(:u AS uuid)"), {"u": sub})

    assert _dem(viec) == 0


# ═══ Ràng buộc ở tầng DB ═════════════════════════════════════════════════════


@pytest.mark.integration
@pytest.mark.parametrize(
    ("ten", "kieu", "du_lieu"),
    [
        ("svg — XML chạy được script", "image/svg+xml", b"<svg/>"),
        ("kiểu lạ", "application/octet-stream", _PNG),
        ("ảnh rỗng", "image/png", b""),
    ],
)
def test_DB_tu_chan_dong_khong_hop_le(phien, ten, kieu, du_lieu):
    """Ràng buộc ở DB, không chỉ ở Python: một script nạp tay hay một endpoint
    tương lai không mở lại được cửa này."""
    from sqlalchemy.exc import IntegrityError

    sub, ht = phien
    viec = _viec(sub, ht)
    with pytest.raises(IntegrityError):
        with get_engine().begin() as c:
            c.execute(
                text(
                    "INSERT INTO anh_tai_lieu (viec_id, phan, kieu, so_byte, du_lieu) "
                    "VALUES (CAST(:v AS uuid), 'word/media/x', :k, :s, :d)"
                ),
                {"v": viec, "k": kieu, "s": len(du_lieu), "d": du_lieu},
            )


@pytest.mark.integration
def test_DB_tu_chan_so_byte_KHAI_LECH_voi_bytes_that(phien):
    """`so_byte` là cột riêng để đọc kích thước mà không kéo bytes qua dây — nên
    nó phải KHÔNG BAO GIỜ nói khác bytes thật, hoặc nó là một con số vô nghĩa."""
    from sqlalchemy.exc import IntegrityError

    sub, ht = phien
    viec = _viec(sub, ht)
    with pytest.raises(IntegrityError):
        with get_engine().begin() as c:
            c.execute(
                text(
                    "INSERT INTO anh_tai_lieu (viec_id, phan, kieu, so_byte, du_lieu) "
                    "VALUES (CAST(:v AS uuid), 'word/media/x.png', 'image/png', 1, :d)"
                ),
                {"v": viec, "d": _PNG},
            )
