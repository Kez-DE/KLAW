"""Vòng đời việc đọc tài liệu và tập dữ kiện (spec 2026-09-15 §FR-005, §FR-013..
FR-015, §FR-019/020, §FR-029/030).

Phần thuần (không DB) khoá bốn điều:

1. Trần 100 trang / 20 MB là hai con số nêu tên được, và thông báo từ chối nói
   ĐÚNG trần nào bị vượt (FR-005).
2. Ngưỡng chuyển nền là một hằng số, không phải số rải trong code (FR-029/030).
3. Sửa một dữ kiện rút từ tài liệu GIỮ trích gốc và ĐỔI nguồn — giá trị đã sửa
   không bao giờ được trình bày như thể đến từ tài liệu (FR-015).
4. Chuyển sang biểu mẫu soạn thảo chỉ mang những trường CÓ dữ kiện; trường
   không có thì để trống chứ không suy đoán (FR-020).

Phần chạm DB nằm ở `test_tai_lieu_db.py`, đánh dấu `integration`.
"""

import pytest

from src.services.tai_lieu import (
    NGUONG_NEN_TRANG,
    TRAN_BYTE,
    TRAN_TRANG,
    VuotTran,
    chay_nen,
    hop_nhat_sua,
    kiem_kich_thuoc,
    kiem_so_trang,
    thanh_facts,
)


def test_hai_tran_la_hai_hang_so_dung_con_so_da_chot():
    assert TRAN_TRANG == 100
    assert TRAN_BYTE == 20 * 1024 * 1024


def test_duoi_tran_byte_thi_di_tiep():
    kiem_kich_thuoc(TRAN_BYTE)


def test_vuot_tran_byte_neu_dung_tran_BYTE():
    with pytest.raises(VuotTran) as e:
        kiem_kich_thuoc(TRAN_BYTE + 1)
    assert e.value.tran == "so_byte" and e.value.gioi_han == TRAN_BYTE


def test_vuot_tran_trang_neu_dung_tran_TRANG():
    kiem_so_trang(TRAN_TRANG)
    with pytest.raises(VuotTran) as e:
        kiem_so_trang(TRAN_TRANG + 1)
    assert e.value.tran == "so_trang" and e.value.gioi_han == TRAN_TRANG


def test_nguong_chuyen_nen():
    assert NGUONG_NEN_TRANG == 10
    assert chay_nen(9) is False
    assert chay_nen(10) is True
    assert chay_nen(None) is False


# ------------------------------------------------------------------ sửa dữ kiện

_GOC = {
    "khoa": "luong_thang",
    "nhan": "Lương tháng",
    "gia_tri": "20000000",
    "nguon": "tai_lieu",
    "trich": "Mức lương: 20.000.000 đồng/tháng",
    "chi_so_don_vi": 0,
    "trang": 1,
    "offset_dau": 0,
}


def test_sua_doi_nguon_va_GIU_trich_goc():
    moi = hop_nhat_sua(_GOC, "25000000")
    assert moi["gia_tri"] == "25000000"
    assert moi["nguon"] == "nguoi_dung_sua"
    assert moi["trich_goc"] == _GOC["trich"]


def test_sua_KHONG_giu_trich_cho_gia_tri_moi():
    """Đoạn trích chứng minh giá trị CŨ; để nguyên nó cho giá trị mới là nói dối."""
    assert hop_nhat_sua(_GOC, "25000000")["trich"] is None


def test_sua_HAI_LAN_van_giu_trich_goc_dau_tien():
    moi = hop_nhat_sua(hop_nhat_sua(_GOC, "25000000"), "30000000")
    assert moi["trich_goc"] == _GOC["trich"] and moi["gia_tri"] == "30000000"


def test_sua_khong_dong_cham_ban_ghi_cu():
    hop_nhat_sua(_GOC, "25000000")
    assert _GOC["gia_tri"] == "20000000" and _GOC["nguon"] == "tai_lieu"


def test_du_kien_nguoi_dung_nhap_khong_can_trich():
    nhap = {"khoa": "chuc_danh", "gia_tri": "Nhân viên", "nguon": "nguoi_dung_nhap", "trich": None}
    moi = hop_nhat_sua(nhap, "Trưởng phòng")
    assert moi["nguon"] == "nguoi_dung_nhap" and moi["trich_goc"] is None


# ---------------------------------------------------------- sang biểu mẫu soạn


def test_thanh_facts_chi_mang_truong_CO_du_kien():
    du_kien = [
        {"khoa": "luong_thang", "gia_tri": "20000000"},
        {"khoa": "nhom_chuc_danh", "gia_tri": "cong_viec_khac"},
    ]
    assert thanh_facts(du_kien) == {"luong_thang": "20000000", "nhom_chuc_danh": "cong_viec_khac"}


def test_thanh_facts_bo_gia_tri_rong_thay_vi_dien_chuoi_rong():
    assert thanh_facts([{"khoa": "a", "gia_tri": ""}, {"khoa": "b", "gia_tri": "  "}]) == {}


def test_thanh_facts_bo_du_kien_da_xoa():
    du_kien = [
        {"khoa": "a", "gia_tri": "1"},
        {"khoa": "b", "gia_tri": "2", "xoa_luc": "2026-09-15T00:00:00Z"},
    ]
    assert thanh_facts(du_kien) == {"a": "1"}


def test_thanh_facts_rong_khong_no():
    assert thanh_facts([]) == {}
