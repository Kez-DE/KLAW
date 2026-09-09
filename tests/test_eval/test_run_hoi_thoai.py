from eval.run_hoi_thoai import dung_du_kien


def test_dung_du_kien_theo_khoa_va_cum_chu():
    kv = {"ho_so": {"chu_the": "người lao động"}, "answer_co": ["45 ngày"]}
    da_dung = [{"khoa": "chu_the", "gia_tri": "Người lao động", "gia_dinh": False}]
    assert dung_du_kien(kv, da_dung, "bạn được báo trước 45 ngày") is True
    assert dung_du_kien(kv, da_dung, "bạn được báo trước") is False
    assert dung_du_kien(kv, [], "45 ngày") is False


def test_dung_du_kien_khong_khop_chuoi_con_giua_hai_loai_hop_dong_doi_lap():
    """Review round 1 (Important): `"xác định thời hạn"` là substring của `"không xác
    định thời hạn"` — hai loại hợp đồng ĐỐI LẬP. So sánh phải là NGUYÊN VĂN, không phải
    "nằm trong", nên hồ sơ ghi loại kia không được tính là đúng dữ kiện."""
    kv = {"ho_so": {"loai_hop_dong": "xác định thời hạn"}}
    da_dung = [{"khoa": "loai_hop_dong", "gia_tri": "không xác định thời hạn", "gia_dinh": False}]
    assert dung_du_kien(kv, da_dung, "") is False
