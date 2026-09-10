from eval.run_hoi_thoai import dung_du_kien, tom_tat_diem


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


def test_tom_tat_diem_loai_hoi_thoai_loi_khoi_ca_tu_va_mau_so():
    """Review round 2 (Important): một hội thoại lỗi hạ tầng không được tính là câu
    trả lời sai — loại nó khỏi CẢ tử số lẫn mẫu số của tỉ lệ, đếm riêng ở `so_loi`."""
    ket = [
        {"id": "a", "dung": True},
        {"id": "b", "dung": False},
        {"id": "c", "error_type": "RuntimeError", "error": "mạng"},
    ]
    tt = tom_tat_diem(ket)
    assert tt == {"so_cham": 2, "dung": 1, "so_loi": 1, "ty_le_giu_du_kien": 0.5}


def test_dung_du_kien_bo_qua_tien_to_hop_dong_thua():
    """`bo_nho.v1.md` liệt kê giá trị `loai_hop_dong` bằng cụm trần ("thử việc"),
    nhưng mô hình thường trích cả tiền tố ("hợp đồng thử việc") — cùng một dữ kiện,
    chấm trượt vì một chữ. Bỏ tiền tố "hợp đồng " ở CẢ HAI vế rồi vẫn so NGUYÊN
    VĂN, nên hai loại hợp đồng đối lập vẫn không lẫn vào nhau."""
    kv = {"ho_so": {"loai_hop_dong": "thử việc 2 tháng"}}
    assert dung_du_kien(kv, [{"khoa": "loai_hop_dong", "gia_tri": "Hợp đồng thử việc 2 tháng"}], "") is True
    assert dung_du_kien({"ho_so": {"loai_hop_dong": "hợp đồng thử việc"}},
                        [{"khoa": "loai_hop_dong", "gia_tri": "thử việc"}], "") is True
    assert dung_du_kien({"ho_so": {"loai_hop_dong": "xác định thời hạn"}},
                        [{"khoa": "loai_hop_dong", "gia_tri": "hợp đồng không xác định thời hạn"}], "") is False
