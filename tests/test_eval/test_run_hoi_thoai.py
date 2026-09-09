from eval.run_hoi_thoai import dung_du_kien


def test_dung_du_kien_theo_khoa_va_cum_chu():
    kv = {"ho_so": {"chu_the": "người lao động"}, "answer_co": ["45 ngày"]}
    da_dung = [{"khoa": "chu_the", "gia_tri": "Người lao động", "gia_dinh": False}]
    assert dung_du_kien(kv, da_dung, "bạn được báo trước 45 ngày") is True
    assert dung_du_kien(kv, da_dung, "bạn được báo trước") is False
    assert dung_du_kien(kv, [], "45 ngày") is False
