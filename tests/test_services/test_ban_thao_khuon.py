"""Bản thảo trên khuôn gốc (P4a) — kế hoạch `docs/plans/active/khuon-goc-dien-tai-cho.md`,
hợp đồng Storage và "Edit operations"; quyết định 2026-09-26.

Phần đầu là hàm THUẦN (không DB): gộp phép sửa, chỗ trống của một phiên bản,
chuẩn hoá giá trị điền, "đã đổi" và bản tóm tắt Markdown. Phần sau chạm DB thật
(`integration`): vòng phiên bản, cascade, và lưu ô điền (`sua_o_dien`).
"""

import pytest

from src.services import ban_thao
from src.services.ban_thao import chuan_hoa_dien, cho_trong_khuon, doi_so_voi, gop_phep_sua, tom_tat_khuon


def _d(don_vi: int, cho: int, gia_tri: str) -> dict:
    return {"loai": "dien", "don_vi": don_vi, "cho_trong": cho, "gia_tri": gia_tri}


def _thay(don_vi: int, noi_dung: str) -> dict:
    return {"loai": "thay", "don_vi": don_vi, "noi_dung": noi_dung}


def _xoa(don_vi: int) -> dict:
    return {"loai": "xoa", "don_vi": don_vi}


def _chen(don_vi: int, noi_dung: str) -> dict:
    return {"loai": "chen_sau", "don_vi": don_vi, "noi_dung": noi_dung}


# ───────────────────────────────────────────────────────── gop_phep_sua


def test_gop_dien_MOI_thang_GIU_cho_cu_va_khong_dung_vao_dau_vao():
    cu = [_d(1, 0, "A"), _d(2, 0, "B")]
    moi = [_d(1, 0, "C")]
    assert gop_phep_sua(cu, moi) == [_d(1, 0, "C"), _d(2, 0, "B")]
    assert cu == [_d(1, 0, "A"), _d(2, 0, "B")] and moi == [_d(1, 0, "C")]


def test_gop_dien_RONG_go_o_da_dien_de_dau_cham_tro_lai():
    cu = [_d(1, 0, "A"), _d(2, 0, "B")]
    assert gop_phep_sua(cu, [_d(2, 0, "")]) == [_d(1, 0, "A")]
    assert gop_phep_sua(cu, [_d(2, 0, "   ")]) == [_d(1, 0, "A")]
    assert gop_phep_sua(cu, [_d(9, 0, "")]) == cu, "gỡ một ô chưa điền là không làm gì"


def test_gop_dien_trung_trong_CUNG_lan_gui_thi_lan_sau_thang():
    assert gop_phep_sua([], [_d(1, 0, "A"), _d(1, 0, "B"), _d(1, 1, "C")]) == [_d(1, 0, "B"), _d(1, 1, "C")]


def test_gop_thay_va_xoa_chung_MOT_khoa_theo_don_vi():
    assert gop_phep_sua([_thay(5, "x")], [_xoa(5)]) == [_xoa(5)]
    assert gop_phep_sua([_xoa(5)], [_thay(5, "y")]) == [_thay(5, "y")]
    assert gop_phep_sua([_thay(5, "x"), _thay(6, "z")], [_thay(5, "y")]) == [_thay(5, "y"), _thay(6, "z")]


def test_gop_chen_sau_bo_trung_giu_thu_tu():
    cu = [_chen(3, "a")]
    assert gop_phep_sua(cu, [_chen(3, "b"), _chen(3, "a"), _chen(4, "a")]) == [
        _chen(3, "a"),
        _chen(3, "b"),
        _chen(4, "a"),
    ]


def test_gop_bo_phep_khong_thuoc_bon_loai():
    assert gop_phep_sua([None, {"loai": "la"}], [_d(1, 0, "A"), "rac"]) == [_d(1, 0, "A")]
    assert gop_phep_sua(None, []) == []


# ───────────────────────────────────────────────────────── cho_trong_khuon

_DOCX = [
    {
        "chi_so": 0,
        "noi_dung": "Họ và tên: ......",
        "dia_chi": {"phan": "word/document.xml", "chi_muc": [0]},
        "cho_trong": [{"so": 0, "kieu": "cham", "doan": 0, "dau": 11, "cuoi": 17, "nhan": "Họ và tên:"}],
    },
    {
        "chi_so": 1,
        "noi_dung": "Điện thoại: ...... Email: ......",
        "dia_chi": {"phan": "word/document.xml", "chi_muc": [1]},
        "cho_trong": [
            {"so": 0, "kieu": "cham", "doan": 0, "dau": 12, "cuoi": 18, "nhan": "Điện thoại:"},
            {"so": 1, "kieu": "tab", "doan": 0, "dau": 26, "cuoi": 26, "nhan": "Email:"},
            {"so": 2, "kieu": "la", "doan": 0, "dau": 0, "cuoi": 1, "nhan": "hỏng"},
        ],
    },
    # Không có địa chỉ: bộ áp không tới được, bảng điền không được mời điền nó.
    {"chi_so": 2, "noi_dung": "Ngày: ......", "cho_trong": [{"so": 0, "kieu": "cham", "doan": 0, "dau": 6, "cuoi": 12, "nhan": "Ngày:"}]},
    {"chi_so": 3, "noi_dung": "Ghi chú", "dia_chi": {"phan": "word/document.xml", "chi_muc": [3]}},
]

_PDF = [
    {"chi_so": 0, "trang": 1, "hop": [72, 30, 300, 44], "noi_dung": "Ho ten: ....",
     "cho_trong": [{"so": 0, "kieu": "cham", "hop": [120, 30, 300, 44], "co_chu": 14.0, "nhan": "Ho ten:"}]},
    # Chỗ trống mang hình dạng DOCX trên khuôn PDF: bộ áp PDF không có toạ độ.
    {"chi_so": 1, "trang": 1, "hop": [72, 50, 300, 64], "noi_dung": "Ngay: ....",
     "cho_trong": [{"so": 0, "kieu": "cham", "doan": 0, "dau": 6, "cuoi": 10, "nhan": "Ngay:"}]},
]


def test_cho_trong_DOCX_chi_don_vi_co_dia_chi_va_gia_tri_theo_phien_ban():
    ra = cho_trong_khuon("docx", _DOCX, [_d(1, 1, " a@b.vn")])
    assert ra == [
        {"don_vi": 0, "so": 0, "kieu": "cham", "nhan": "Họ và tên:", "gia_tri": None},
        {"don_vi": 1, "so": 0, "kieu": "cham", "nhan": "Điện thoại:", "gia_tri": None},
        {"don_vi": 1, "so": 1, "kieu": "tab", "nhan": "Email:", "gia_tri": " a@b.vn"},
    ]


def test_cho_trong_PDF_chi_cho_trong_co_hop():
    ra = cho_trong_khuon("pdf", _PDF, [_d(0, 0, "Ánh")])
    assert ra == [{"don_vi": 0, "so": 0, "kieu": "cham", "nhan": "Ho ten:", "gia_tri": "Ánh"}]


def test_cho_trong_cua_doan_da_THAY_hay_XOA_khong_con_dien_duoc():
    """Đoạn đã bị thay/xoá không còn dãy chấm nào: mời điền nó là mời một lần
    lưu chắc chắn bị bộ áp bỏ (`xung_dot`)."""
    ra = cho_trong_khuon("docx", _DOCX, [_thay(0, "Họ và tên: A"), _xoa(1)])
    assert ra == []


def test_cho_trong_don_vi_rong_hay_sai_hinh_dang():
    assert cho_trong_khuon("docx", [], []) == []
    assert cho_trong_khuon("docx", [None, {"chi_so": "x"}], None) == []


# ───────────────────────────────────────────────────────── chuan_hoa_dien

_CHAM = {"don_vi": 0, "so": 0, "kieu": "cham", "nhan": "Họ và tên:"}
_TAB_KHONG_CACH = {"don_vi": 1, "so": 1, "kieu": "tab", "nhan": "Email:"}
_TAB_CO_CACH = {"don_vi": 1, "so": 1, "kieu": "tab", "nhan": "Email: "}


def test_chuan_hoa_cat_khoang_trang_va_dua_ve_NFC():
    assert chuan_hoa_dien("  Nguyễn Văn A  ", _CHAM) == "Nguyễn Văn A"
    assert chuan_hoa_dien("Nguyễn Văn", _CHAM) == "Nguyễn Văn"


def test_chuan_hoa_o_TAB_them_mot_cach_khi_nhan_khong_ket_bang_khoang_trang():
    assert chuan_hoa_dien("a@b.vn", _TAB_KHONG_CACH) == " a@b.vn"
    assert chuan_hoa_dien("a@b.vn", _TAB_CO_CACH) == "a@b.vn"
    assert chuan_hoa_dien("  ", _TAB_KHONG_CACH) == "", "giá trị rỗng là gỡ ô, không thành một dấu cách"


@pytest.mark.parametrize("sai", ["A\nB", "A\r\nB", "A\tB", "A\x00", "A​", "A\x7f"])
def test_chuan_hoa_tu_choi_xuong_dong_va_ky_tu_dieu_khien(sai):
    with pytest.raises(ValueError) as e:
        chuan_hoa_dien(sai, _CHAM)
    assert str(e.value) == ban_thao.LOI_GIA_TRI_DIEN


# ───────────────────────────────────────────────────── đã đổi, tóm tắt


def _khuon(*o: tuple) -> dict:
    return {
        "viec_id": "v",
        "dinh_dang": "docx",
        "so_trang": 1,
        "cho_trong": [{"don_vi": d, "so": s, "kieu": "cham", "nhan": n, "gia_tri": g} for d, s, n, g in o],
    }


def test_doi_so_voi_KHUON_liet_ke_o_doi_cu_sang_moi():
    truoc = {"facts": {}, "khuon": _khuon((0, 0, "Họ và tên:", None), (1, 0, "Email:", " a@b.vn"), (2, 0, "", "x"))}
    sau = {"facts": {}, "khuon": _khuon((0, 0, "Họ và tên:", "Ánh"), (1, 0, "Email:", None), (2, 0, "", "x"))}
    assert doi_so_voi(truoc, sau) == ["Họ và tên: … → Ánh", "Email: a@b.vn → …"]


def test_doi_so_voi_KHONG_khuon_giu_hinh_dang_facts():
    assert doi_so_voi({"facts": {"a": 1}}, {"facts": {"a": 2}, "khuon": None}) == ["a"]


def test_tom_tat_khuon_la_tieu_de_va_mot_dong_moi_o_da_dien():
    k = _khuon((0, 0, "Họ và tên:", "Ánh"), (1, 0, "Email:", None), (1, 1, "", " a@b.vn"))
    assert tom_tat_khuon("Giấy tiếp nhận", k) == "# Giấy tiếp nhận\n\n- Họ và tên: Ánh\n- Ô 1.1: a@b.vn\n"
    assert tom_tat_khuon(None, _khuon()) == "# Văn bản\n"
