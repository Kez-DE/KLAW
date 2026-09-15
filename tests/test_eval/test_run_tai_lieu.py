"""Chấm điểm rút dữ kiện từ tài liệu (spec 2026-09-15 §SC-001, §SC-002).

Hai phép đo, hai tính chất khác nhau:

* SC-001 phải là **1.0 theo kiến trúc**, không phải theo may mắn: dữ kiện không
  khớp trích đã bị `loc_co_neo` loại từ trong node. Nếu số này từng xuống dưới 1
  thì nghĩa là có đường vòng qua phép kiểm, và đó là lỗi nghiêm trọng nhất tính
  năng này có thể mắc.
* SC-002 là số ĐO ĐƯỢC, sẽ đi vào báo cáo, nên cách so khớp giá trị phải nêu rõ
  và kiểm được — "20.000.000" và "20000000" là cùng một mức lương, còn
  "20.000.000" và "25.000.000" thì không.
"""

import pytest

from eval.run_tai_lieu import bang_nhau, diem_trich, diem_truong


@pytest.mark.parametrize(
    "a, b",
    [
        ("20.000.000", "20000000"),
        ("20 000 000", "20000000"),
        (" 60 ", "60"),
        ("Nhân viên kinh doanh", "nhân viên  kinh doanh"),
    ],
)
def test_bang_nhau_bo_qua_cach_viet_KHONG_bo_qua_gia_tri(a, b):
    assert bang_nhau(a, b)


@pytest.mark.parametrize("a, b", [("20000000", "25000000"), ("60", "90"), ("Giám đốc", "Nhân viên")])
def test_bang_nhau_KHONG_gop_hai_gia_tri_khac_nhau(a, b):
    assert not bang_nhau(a, b)


def test_bang_nhau_GIU_DAU_tieng_Viet():
    """Cùng lý do `verify_tier1.normalize` không bỏ dấu: dấu là chữ."""
    assert not bang_nhau("Phạt tiền", "Phat tien")


def test_diem_trich_la_1_khi_moi_du_kien_deu_co_neo():
    class _Neo:
        ly_do = "ok"

    assert diem_trich([{"neo": _Neo()}, {"neo": _Neo()}]) == 1.0


def test_diem_trich_khong_du_kien_thi_la_1_chu_khong_chia_cho_0():
    assert diem_trich([]) == 1.0


def test_diem_truong_dem_dung_ty_le():
    nhan = {"luong_thang": "20000000", "vung": "I", "nhom_chuc_danh": "cong_viec_khac"}
    du_doan = {"luong_thang": "20.000.000", "vung": "II"}
    # đúng 1/3: luong_thang khớp, vung sai, nhom_chuc_danh thiếu
    assert diem_truong(du_doan, nhan) == pytest.approx(1 / 3)


def test_diem_truong_TRUONG_THIEU_tinh_la_SAI_chu_khong_bo_qua():
    """Bỏ trường thiếu ra khỏi mẫu số sẽ thưởng cho việc rút được ít."""
    assert diem_truong({}, {"a": "1", "b": "2"}) == 0.0


def test_diem_truong_THUA_khong_lam_diem_cao_len():
    nhan = {"a": "1"}
    assert diem_truong({"a": "1", "b": "bịa"}, nhan) == 1.0


def test_diem_truong_nhan_rong_thi_la_1():
    assert diem_truong({}, {}) == 1.0
