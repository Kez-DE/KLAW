"""Phanh chi phí cho một lần đọc tài liệu (spec 2026-09-15 §FR-036, §FR-037, §FR-038).

Chủ dự án đã bỏ trần thời gian: ra được kết quả quan trọng hơn ra nhanh. Nên một
lần đọc được phép chạy lâu — nhưng không được phép tốn vô hạn. File này khoá cái
phanh thay thế.

Vì sao trần ngày sẵn có KHÔNG đủ: `tran_chi_phi_ngay_usd` dùng CHUNG cho mọi
người dùng. Chỉ dựa vào nó thì một tài liệu dị dạng của MỘT người làm cạn hạn
mức của TẤT CẢ, và người bị chặn không hiểu vì sao.
"""

import pytest

from src.services.tai_lieu import (
    TAI_LIEU_NGAY,
    TRAN_CHI_PHI_TAI_LIEU_USD,
    VuotTran,
    han_muc_ngay,
    kiem_tran_chi_phi_tai_lieu,
    uoc_chi_phi,
    vuot_chi_phi_thuc,
)


def test_moi_tran_la_DU_LIEU_khong_phai_so_trong_code():
    """Đổi số phải là đổi `config/han_muc.yaml`, cùng lệ với mọi hạn mức khác."""
    import yaml

    from src.services.bao_ve import HAN_MUC_PATH

    d = yaml.safe_load(HAN_MUC_PATH.read_text(encoding="utf-8"))["tai_lieu"]
    assert TRAN_CHI_PHI_TAI_LIEU_USD == d["chi_phi_usd"]
    assert TAI_LIEU_NGAY == {g: v["tai_lieu_ngay"] for g, v in d["theo_goi"].items()}


def test_KHONG_con_tran_so_lan_thu_lai():
    """Không giữ tệp gốc thì không thử lại được: thử lại = tải lên lại, và
    `tai_lieu_ngay` đã đếm việc đó. Một hằng số không có nơi cưỡng chế là một
    lời hứa, không phải một quy tắc."""
    import src.services.tai_lieu as m

    assert not hasattr(m, "TRAN_THU_LAI") and not hasattr(m, "con_thu_lai")


def test_han_muc_pro_cao_hon_free():
    assert han_muc_ngay("pro") > han_muc_ngay("free") > 0


def test_goi_LA_roi_ve_free_chu_khong_mo_rong_quyen():
    assert han_muc_ngay("goi-chua-ton-tai") == han_muc_ngay("free")


def test_uoc_chi_phi_tang_theo_do_dai():
    assert uoc_chi_phi(1000) < uoc_chi_phi(10_000)
    assert uoc_chi_phi(0) == 0.0


def test_tai_lieu_thuong_DI_QUA():
    """Hợp đồng lao động thật cỡ 6 trang ~ 12.000 ký tự."""
    kiem_tran_chi_phi_tai_lieu(12_000)


def test_tai_lieu_KHONG_LO_bi_chan_TRUOC_khi_goi_mo_hinh():
    with pytest.raises(VuotTran) as e:
        kiem_tran_chi_phi_tai_lieu(50_000_000)
    assert e.value.tran == "chi_phi"
    assert e.value.gioi_han == TRAN_CHI_PHI_TAI_LIEU_USD


def test_chi_phi_THUC_vuot_tran_van_bi_bat_sau_khi_goi():
    """Ước sai vẫn phải bị bắt: ước là phòng ngừa, đối chiếu thật là cưỡng chế."""
    assert vuot_chi_phi_thuc(TRAN_CHI_PHI_TAI_LIEU_USD + 0.001) is True
    assert vuot_chi_phi_thuc(TRAN_CHI_PHI_TAI_LIEU_USD) is False
    assert vuot_chi_phi_thuc(0.0) is False


def test_tat_bang_cach_dat_0_giong_tran_chi_phi_ngay(monkeypatch):
    """0 = TẮT, cùng quy ước `kiem_tran_chi_phi`."""
    import src.services.tai_lieu as m

    monkeypatch.setattr(m, "TRAN_CHI_PHI_TAI_LIEU_USD", 0)
    m.kiem_tran_chi_phi_tai_lieu(50_000_000)
    assert m.vuot_chi_phi_thuc(999.0) is False
