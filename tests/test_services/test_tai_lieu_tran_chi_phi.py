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
    TRAN_CHI_PHI_TAI_LIEU_USD,
    TRAN_THU_LAI,
    VuotTran,
    con_thu_lai,
    kiem_tran_chi_phi_tai_lieu,
    uoc_chi_phi,
    vuot_chi_phi_thuc,
)


def test_hai_tran_la_DU_LIEU_khong_phai_so_trong_code():
    """Đổi số phải là đổi `config/han_muc.yaml`, cùng lệ với mọi hạn mức khác."""
    import yaml

    from src.services.bao_ve import HAN_MUC_PATH

    d = yaml.safe_load(HAN_MUC_PATH.read_text(encoding="utf-8"))["tai_lieu"]
    assert TRAN_CHI_PHI_TAI_LIEU_USD == d["chi_phi_usd"]
    assert TRAN_THU_LAI == d["so_lan_thu"]


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


def test_tran_thu_lai_chan_vong_lap_vo_han():
    assert con_thu_lai(0) is True
    assert con_thu_lai(TRAN_THU_LAI - 1) is True
    assert con_thu_lai(TRAN_THU_LAI) is False
    assert con_thu_lai(TRAN_THU_LAI + 5) is False


def test_tat_bang_cach_dat_0_giong_tran_chi_phi_ngay(monkeypatch):
    """0 = TẮT, cùng quy ước `kiem_tran_chi_phi`."""
    import src.services.tai_lieu as m

    monkeypatch.setattr(m, "TRAN_CHI_PHI_TAI_LIEU_USD", 0)
    m.kiem_tran_chi_phi_tai_lieu(50_000_000)
    assert m.vuot_chi_phi_thuc(999.0) is False
