"""Biểu diễn văn bản đã đọc, lưu theo hội thoại — quyết định 2026-09-16
(`docs/decisions/2026-09-16-luu-bieu-dien-tai-lieu-theo-hoi-thoai.md`).

Chạm Postgres thật, vì bốn điều ở đây chỉ đúng nếu cột và truy vấn đúng:

1. Đơn vị đi và về NGUYÊN VẸN, kể cả toạ độ bảng và hạng bằng chứng OCR. Một
   `bang` quay về thành list thay vì tuple là hỏng im lặng: so sánh vẫn chạy,
   chỉ không còn bằng nhau.
2. Ranh giới tài khoản: đơn vị của người khác là `None`, không phân biệt được
   với một id không có thật.
3. `lay_viec` nói được SỐ đơn vị mà không kéo cả nội dung tài liệu qua dây —
   `chi_tiet` gọi nó mỗi lần người dùng mở bảng dữ kiện.
4. Xoá theo hội thoại dọn sạch biểu diễn. Đây là điều khoản đánh đổi của chính
   quyết định trên: nội dung tài liệu được phép nằm trong Postgres ĐÚNG BẰNG
   đời cuộc hội thoại, không lâu hơn.
"""

import pytest
from sqlalchemy import text

from src.services import tai_lieu as tl
from src.services.db import get_engine
from src.services.doc_tai_lieu import DonViVanBan, NguonChu

DON_VI = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="PHIẾU ĐÁNH GIÁ"),
    DonViVanBan(chi_so=1, trang=1, offset_dau=15, noi_dung="Chuyên cần", bang=(0, 1, 0)),
    DonViVanBan(
        chi_so=2, trang=1, offset_dau=26, noi_dung="2,0",
        bang=(0, 1, 1), nguon_chu=NguonChu.ocr, do_tin=0.91,
    ),
    DonViVanBan(chi_so=3, trang=1, offset_dau=30, noi_dung="BM.ĐT.18.11", vung="dau_trang"),
]


@pytest.fixture
def phien():
    """Một tài khoản + hội thoại dùng một lần. Xoá tài khoản là xoá theo tất cả."""
    with get_engine().begin() as c:
        sub = str(c.execute(text("INSERT INTO users (sub) VALUES (gen_random_uuid()) RETURNING sub")).scalar_one())
        ht = str(
            c.execute(
                text("INSERT INTO hoi_thoai (user_sub, tieu_de) VALUES (CAST(:u AS uuid), 'thử') RETURNING id"),
                {"u": sub},
            ).scalar_one()
        )
    yield sub, ht
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM users WHERE sub = CAST(:u AS uuid)"), {"u": sub})


def _viec(sub: str, ht: str, *, ten="phieu.docx", trang_thai="xong", loai=None, mo_ta=None) -> str:
    with get_engine().begin() as c:
        return str(
            c.execute(
                text(
                    "INSERT INTO viec_doc_tai_lieu "
                    "(user_sub, hoi_thoai_id, ten_tep, dau_van_ban, so_byte, so_trang, trang_thai, loai, mo_ta) "
                    "VALUES (CAST(:u AS uuid), CAST(:h AS uuid), :t, 'sha256:x len=1', 100, 1, :s, :l, :m) "
                    "RETURNING id"
                ),
                {"u": sub, "h": ht, "t": ten, "s": trang_thai, "l": loai, "m": mo_ta},
            ).scalar_one()
        )


@pytest.mark.integration
def test_don_vi_di_va_ve_NGUYEN_VEN(phien):
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_don_vi(get_engine(), viec, DON_VI)

    assert tl.don_vi_cua(get_engine(), viec, sub) == DON_VI


@pytest.mark.integration
def test_toa_do_bang_ve_lai_la_TUPLE_chu_khong_phai_list(phien):
    """JSON không có kiểu tuple. Quên chuyển lại thì so sánh thất bại im lặng."""
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_don_vi(get_engine(), viec, DON_VI)

    ve = tl.don_vi_cua(get_engine(), viec, sub)
    assert ve[1].bang == (0, 1, 0) and isinstance(ve[1].bang, tuple)
    assert ve[0].bang is None
    assert ve[2].nguon_chu is NguonChu.ocr and ve[2].do_tin == 0.91
    assert ve[3].vung == "dau_trang"


@pytest.mark.integration
def test_can_le_di_va_ve_dung_gia_tri_khong_ve_trai_mac_dinh(phien):
    """Phase 9 U5 fix round 1 — đo được thật trên một draft: `_hang_don_vi`
    thiếu khoá `can_le` khiến MỌI đơn vị đọc lại ra mặc định `trai` của
    dataclass, dù `doc_tai_lieu.doc()` đã đọc đúng `giua` cho quốc hiệu và
    `phai` cho dòng "Hà Nội, ngày...". Một phép kiểm chỉ xem khoá `can_le` có
    mặt hay không (`assert "can_le" in ...`) sẽ ĐẬU trên chính lỗi này, vì
    trước bản vá `don_vi_cua` vẫn trả về khoá đó — chỉ sai GIÁ TRỊ. Pin đúng
    ba giá trị, không chỉ sự có mặt của trường."""
    sub, ht = phien
    viec = _viec(sub, ht)
    don_vi = [
        DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM", can_le="giua"),
        DonViVanBan(chi_so=1, trang=1, offset_dau=40, noi_dung="Hà Nội, ngày ..... tháng .... năm 20...", can_le="phai"),
        DonViVanBan(chi_so=2, trang=1, offset_dau=90, noi_dung="Họ và tên sinh viên: ………………"),  # mặc định `trai`
    ]
    tl.luu_don_vi(get_engine(), viec, don_vi)

    ve = tl.don_vi_cua(get_engine(), viec, sub)
    assert [d.can_le for d in ve] == ["giua", "phai", "trai"]


@pytest.mark.integration
def test_bang_nhip_va_ti_le_di_va_ve_dung_gia_tri(phien):
    """Phase 11 R1/R6 — cùng lớp lỗi `can_le` fix round 1 đã bắt: thiếu khoá
    ở `_hang_don_vi` khiến `don_vi_cua` đọc lại ra mặc định (nhịp 1, tỉ lệ
    rỗng) của dataclass, dù `doc_tai_lieu.doc()` đã đọc đúng `bang_nhip`/
    `bang_ti_le` từ tệp. Pin đúng giá trị, không chỉ sự có mặt của khoá."""
    sub, ht = phien
    viec = _viec(sub, ht)
    don_vi = [
        DonViVanBan(
            chi_so=0, trang=1, offset_dau=0, noi_dung="Tổng",
            bang=(0, 1, 0), bang_nhip=2, bang_ti_le=(7, 15, 30, 34, 15),
        ),
        DonViVanBan(
            chi_so=1, trang=1, offset_dau=5, noi_dung="10",
            bang=(0, 1, 2), bang_ti_le=(7, 15, 30, 34, 15),  # bang_nhip mặc định 1
        ),
    ]
    tl.luu_don_vi(get_engine(), viec, don_vi)

    ve = tl.don_vi_cua(get_engine(), viec, sub)
    assert [d.bang_nhip for d in ve] == [2, 1]
    assert [d.bang_ti_le for d in ve] == [(7, 15, 30, 34, 15), (7, 15, 30, 34, 15)]
    assert isinstance(ve[0].bang_ti_le, tuple), "JSON không có tuple — quên chuyển lại thì so sánh hỏng im lặng"


@pytest.mark.integration
def test_don_vi_cua_NGUOI_KHAC_la_None(phien):
    import uuid

    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_don_vi(get_engine(), viec, DON_VI)

    assert tl.don_vi_cua(get_engine(), viec, str(uuid.uuid4())) is None
    assert tl.don_vi_cua(get_engine(), str(uuid.uuid4()), sub) is None


@pytest.mark.integration
def test_dong_chua_tung_luu_don_vi_tra_ve_danh_sach_RONG(phien):
    """Dòng cũ có trước migration 031 vẫn đọc được, chỉ là không có gì để neo."""
    sub, ht = phien
    assert tl.don_vi_cua(get_engine(), _viec(sub, ht), sub) == []


@pytest.mark.integration
def test_lay_viec_noi_duoc_SO_don_vi_ma_khong_keo_noi_dung(phien):
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_don_vi(get_engine(), viec, DON_VI)

    v = tl.lay_viec(get_engine(), viec, sub)
    assert v["so_don_vi"] == 4
    assert "don_vi" not in v, "nội dung tài liệu không được đi kèm mỗi lần xem chi tiết"


@pytest.mark.integration
def test_lay_viec_chua_co_don_vi_thi_so_don_vi_la_0(phien):
    sub, ht = phien
    assert tl.lay_viec(get_engine(), _viec(sub, ht), sub)["so_don_vi"] == 0


@pytest.mark.integration
def test_tai_lieu_cua_hoi_thoai_chi_lay_dong_XONG_va_CO_don_vi(phien):
    sub, ht = phien
    xong = _viec(sub, ht, ten="co-don-vi.docx", loai="hdld", mo_ta="Phiếu đánh giá thực tập")
    tl.luu_don_vi(get_engine(), xong, DON_VI)
    _viec(sub, ht, ten="khong-don-vi.docx")                       # xong nhưng chưa có don_vi
    dang_doc = _viec(sub, ht, ten="dang-doc.docx", trang_thai="dang_doc")
    tl.luu_don_vi(get_engine(), dang_doc, DON_VI)

    ds = tl.tai_lieu_cua_hoi_thoai(get_engine(), ht, sub)
    assert [d["ten_tep"] for d in ds] == ["co-don-vi.docx"]
    assert ds[0] == {
        "id": xong, "ten_tep": "co-don-vi.docx", "so_trang": 1, "so_don_vi": 4,
        "loai": "hdld", "mo_ta": "Phiếu đánh giá thực tập", "co_ocr": True,
    }


@pytest.mark.integration
def test_tai_lieu_cua_hoi_thoai_MOI_NHAT_TRUOC_va_khong_qua_ranh_gioi_tai_khoan(phien):
    import uuid

    sub, ht = phien
    cu = _viec(sub, ht, ten="cu.docx")
    tl.luu_don_vi(get_engine(), cu, DON_VI)
    moi = _viec(sub, ht, ten="moi.docx")
    tl.luu_don_vi(get_engine(), moi, DON_VI)

    assert [d["ten_tep"] for d in tl.tai_lieu_cua_hoi_thoai(get_engine(), ht, sub)] == ["moi.docx", "cu.docx"]
    assert tl.tai_lieu_cua_hoi_thoai(get_engine(), ht, str(uuid.uuid4())) == []


@pytest.mark.integration
def test_co_ocr_FALSE_khi_moi_don_vi_deu_la_chu_that(phien):
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_don_vi(get_engine(), viec, [d for d in DON_VI if d.nguon_chu is NguonChu.lop_chu])

    assert tl.tai_lieu_cua_hoi_thoai(get_engine(), ht, sub)[0]["co_ocr"] is False


@pytest.mark.integration
def test_xoa_theo_hoi_thoai_DON_SACH_bieu_dien(phien):
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_don_vi(get_engine(), viec, DON_VI)

    tl.xoa_theo_hoi_thoai(get_engine(), ht, sub)

    assert tl.don_vi_cua(get_engine(), viec, sub) is None
    assert tl.tai_lieu_cua_hoi_thoai(get_engine(), ht, sub) == []


# ───────────────────────────────────────── rút dữ kiện lần hai không nhân đôi
# `hieu_tai_lieu` rút dữ kiện theo lược đồ ĐỘNG, nên cùng một tài liệu hỏi hai
# lần ra cùng bộ `khoa`. Không có ràng buộc duy nhất nào ở DB (bộ trường là
# động, không khai trước được), nên chống trùng nằm ở đây — và nó phải giữ giá
# trị NGƯỜI DÙNG đã sửa (FR-012), không phải ghi đè bằng bản mô hình đọc lại.

_NEO = DonViVanBan(chi_so=1, trang=1, offset_dau=15, noi_dung="Chuyên cần", bang=(0, 1, 0))


def _hang(khoa: str, gia_tri: str) -> dict:
    from src.services.neo_du_kien import LyDoNeo, Neo

    return {
        "key": khoa, "nhan": "Chuyên cần", "gia_tri": gia_tri, "trich": "Chuyên cần",
        "nguon": "tai_lieu",
        "neo": Neo(LyDoNeo.ok, chi_so_don_vi=_NEO.chi_so, trang=_NEO.trang, offset_dau=_NEO.offset_dau),
    }


@pytest.mark.integration
def test_luu_du_kien_lan_hai_KHONG_tao_dong_trung_khoa(phien):
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_du_kien(get_engine(), viec, ht, [_hang("chuyen_can", "2,0")])
    tl.luu_du_kien(get_engine(), viec, ht, [_hang("chuyen_can", "2,0"), _hang("thai_do", "1,5")])

    khoa = [d["khoa"] for d in tl.du_kien_cua_hoi_thoai(get_engine(), ht, sub)]
    assert sorted(khoa) == ["chuyen_can", "thai_do"], "khoá đã có phải bị bỏ qua, khoá mới vẫn vào"


@pytest.mark.integration
def test_lan_hai_KHONG_de_len_gia_tri_nguoi_dung_da_sua(phien):
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_du_kien(get_engine(), viec, ht, [_hang("chuyen_can", "2,0")])
    cu = tl.du_kien_cua_hoi_thoai(get_engine(), ht, sub)[0]
    tl.sua_du_kien(get_engine(), str(cu["id"]), sub, "1,0")

    tl.luu_du_kien(get_engine(), viec, ht, [_hang("chuyen_can", "2,0")])

    con = tl.du_kien_cua_hoi_thoai(get_engine(), ht, sub)
    assert len(con) == 1
    assert con[0]["gia_tri"] == "1,0" and con[0]["nguon"] == "nguoi_dung_sua"


@pytest.mark.integration
def test_khoa_da_XOA_thi_rut_lai_duoc(phien):
    """Xoá một dòng là cách người dùng nói "đọc lại giúp tôi" — nó phải rút lại được."""
    sub, ht = phien
    viec = _viec(sub, ht)
    tl.luu_du_kien(get_engine(), viec, ht, [_hang("chuyen_can", "2,0")])
    cu = tl.du_kien_cua_hoi_thoai(get_engine(), ht, sub)[0]
    tl.xoa_du_kien(get_engine(), str(cu["id"]), sub)

    tl.luu_du_kien(get_engine(), viec, ht, [_hang("chuyen_can", "2,5")])
    con = tl.du_kien_cua_hoi_thoai(get_engine(), ht, sub)
    assert [d["gia_tri"] for d in con] == ["2,5"]


@pytest.mark.integration
def test_hai_tai_lieu_cung_khoa_van_giu_ca_hai(phien):
    """Chống trùng theo TỪNG tài liệu: "họ tên" của hai phiếu là hai dữ kiện."""
    sub, ht = phien
    a, b = _viec(sub, ht), _viec(sub, ht, ten="phieu-2.docx")
    tl.luu_du_kien(get_engine(), a, ht, [_hang("chuyen_can", "2,0")])
    tl.luu_du_kien(get_engine(), b, ht, [_hang("chuyen_can", "1,0")])

    assert len(tl.du_kien_cua_hoi_thoai(get_engine(), ht, sub)) == 2
