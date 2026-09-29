"""`bo_ba_tu_hang` — một hàng `metadata.parquet` → (cơ quan, người ký, chức danh).
Thuần, dict thay cho `pandas.Series`: NaN và None đều không phải `str`."""

import math

from scripts.nap_co_quan_tang_nong import bo_ba_tu_hang


def test_giu_nguyen_van_chi_cat_khoang_trang():
    hang = {"co_quan_ban_hanh": " Bộ Tài chính ", "nguoi_ky": "Trần Xuân Nhĩ", "chuc_danh": "Thứ trưởng"}
    assert bo_ba_tu_hang(hang) == ("Bộ Tài chính", "Trần Xuân Nhĩ", "Thứ trưởng")


def test_rong_nan_khoang_trang_thanh_None():
    """Khớp CHECK của migration 015: '' và NULL là hai cách nói 'không biết'."""
    assert bo_ba_tu_hang({"co_quan_ban_hanh": math.nan, "nguoi_ky": "  ", "chuc_danh": None}) == (None, None, None)
    assert bo_ba_tu_hang({}) == (None, None, None)
