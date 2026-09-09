from src.services.retrieval import chuan_linh_vuc, loc_theo_linh_vuc


def test_chuan_linh_vuc_ma_snake_va_nhan_co_dau_ve_cung_mot_ma():
    """`rewrite_query.v2` đoán mã snake ("lao_dong"); `documents.linh_vuc` lưu nhãn
    có dấu ("Lao động"). `loc_theo_linh_vuc` chỉ đúng khi cả hai chuẩn hoá về CÙNG
    một chuỗi — xem brief task-13 §"Kiểm chuan_linh_vuc"."""
    assert chuan_linh_vuc("lao_dong") == chuan_linh_vuc("Lao động")


def test_loc_giu_dung_linh_vuc_va_mo_rong_khi_it():
    ids = [1, 2, 3, 4, 5]
    cua = {1: "Lao động", 2: "Hình sự", 3: "Lao động", 4: None, 5: "Lao động"}
    assert loc_theo_linh_vuc(ids, cua, "lao_dong") == ([1, 3, 5], False)
    assert loc_theo_linh_vuc(ids, cua, "hinh_su") == (ids, True)  # 1 kết quả < 3 → mở lại toàn kho
    assert loc_theo_linh_vuc(ids, cua, None) == (ids, False)
    assert loc_theo_linh_vuc(ids, cua, "khac") == (ids, True)
