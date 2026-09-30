import pytest

from src.services.retrieval import chuan_linh_vuc, loc_theo_linh_vuc, nganh_cua_linh_vuc


def test_chuan_linh_vuc_ma_snake_va_nhan_co_dau_ve_cung_mot_ma():
    """`rewrite_query.v2` đoán mã snake ("lao_dong"); `documents.linh_vuc` lưu nhãn
    có dấu ("Lao động"). `loc_theo_linh_vuc` chỉ đúng khi cả hai chuẩn hoá về CÙNG
    một chuỗi — xem brief task-13 §"Kiểm chuan_linh_vuc"."""
    assert chuan_linh_vuc("lao_dong") == chuan_linh_vuc("Lao động")


def test_loc_giu_dung_nganh_giu_van_ban_chua_xep_nganh_va_mo_rong_khi_it():
    ids = [1, 2, 3, 4, 5]
    cua = {1: "lao_dong", 2: "hinh_su", 3: "lao_dong", 4: None, 5: "lao_dong"}
    assert loc_theo_linh_vuc(ids, cua, "lao_dong") == ([1, 3, 4, 5], False)
    assert loc_theo_linh_vuc(ids, cua, "hinh_su") == (ids, True)  # giữ [2, 4]: 2 < 3 → mở lại toàn kho
    assert loc_theo_linh_vuc(ids, cua, None) == (ids, False)
    assert loc_theo_linh_vuc(ids, cua, "khac") == (ids, False)  # không xếp được ngành: không khoanh


def test_cau_tranh_chap_nha_dat_giu_luat_dat_dai_khi_hien_102_2024():
    """Quyết định 2026-09-30 mục 9: nhãn `linh_vuc` nguồn lệch nhau (102/2024 "Đất đai",
    31/2024/QH15 và BLDS trống) làm bộ lọc giữ riêng 102/2024. `nganh_luat` của cả bốn văn
    bản đất đai là `dat_dai`; BLDS là `dan_su`."""
    ids = [235, 236, 1021, 1022, 1023, 91]
    cua = {235: "dat_dai", 236: "dat_dai", 1021: "dat_dai", 1022: "dat_dai", 1023: "dat_dai", 91: "dan_su"}
    giu, mo_rong = loc_theo_linh_vuc(ids, cua, "dat_dai")
    assert {235, 236} <= set(giu) and not mo_rong


@pytest.mark.parametrize(
    ("ma", "nganh"),
    [
        ("lao_dong", "lao_dong"),
        ("dan_su", "dan_su"),
        ("hinh_su", "hinh_su"),
        ("to_tung_dan_su", "to_tung_dan_su"),
        ("to_tung_hinh_su", "to_tung_hinh_su"),
        ("hon_nhan_gia_dinh", "hon_nhan_gia_dinh"),
        ("dat_dai", "dat_dai"),
        ("hanh_chinh", "hanh_chinh"),
        ("doanh_nghiep", "kinh_te"),
        ("so_huu_tri_tue", "kinh_te"),
        ("thue", "tai_chinh"),
        ("hang_hai", "hanh_chinh"),
        ("khac", None),
        (None, None),
    ],
)
def test_ma_linh_vuc_cua_rewrite_xep_vao_nganh_bang_cung_tu_khoa(ma, nganh):
    """Mọi mã của `prompts/rewrite_query.v3.md` bước 1."""
    assert nganh_cua_linh_vuc(ma) == nganh
