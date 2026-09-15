"""Neo dữ kiện về đoạn trích trong tài liệu (spec 2026-09-15 §FR-007..FR-010).

Đây là phép kiểm mang toàn bộ giá trị của tính năng: một dữ kiện chỉ tồn tại
nếu đoạn trích của nó tra ngược được về tài liệu. File này khoá năm điều:

1. Phép kiểm là TRA CHUỖI, hàm thuần, không LLM, không I/O (FR-008).
2. Chuẩn hoá DÙNG LẠI `verify_tier1.normalize` — không viết bản thứ hai. Hai
   hàm chuẩn hoá khác nhau trong cùng một hệ là một lỗ hổng chờ ngày nở: một
   bên nới hơn bên kia sẽ đóng dấu "đã kiểm chứng" cho thứ bên kia loại.
3. KHÔNG bỏ dấu, KHÔNG bỏ hoa thường. "Phạt tiền" và "phát tiền" phải trượt.
4. Đoạn trích phải nằm gọn trong MỘT đơn vị; ghép hai đơn vị là trượt (FR-010).
5. Ba lý do trượt là ba mã riêng, cùng khuôn `Tier1Reason`.
"""

import pytest

from src.agents.nodes.verify_tier1 import QUOTE_TOI_THIEU, normalize
from src.services.doc_tai_lieu import DonViVanBan
from src.services.neo_du_kien import LyDoNeo, Neo, xac_minh

DV = [
    DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="Mức lương: 20.000.000 đồng/tháng"),
    DonViVanBan(chi_so=1, trang=1, offset_dau=32, noi_dung="Thời hạn hợp đồng: 12 tháng"),
    DonViVanBan(chi_so=2, trang=2, offset_dau=0, noi_dung="Chức danh: Nhân viên kinh doanh"),
]


def test_khop_nguyen_van_tra_ve_dung_don_vi():
    n = xac_minh("Mức lương: 20.000.000 đồng/tháng", DV)
    assert n.ly_do is LyDoNeo.ok
    assert n.chi_so_don_vi == 0
    assert n.trang == 1


def test_khop_mot_phan_van_hop_le():
    n = xac_minh("Chức danh: Nhân viên kinh doanh", DV)
    assert n.ly_do is LyDoNeo.ok and n.chi_so_don_vi == 2 and n.trang == 2


def test_DUNG_LAI_normalize_cua_verify_tier1():
    """Không có bản chuẩn hoá thứ hai trong hệ."""
    import src.services.neo_du_kien as m

    assert m.normalize is normalize


def test_chuan_hoa_khoang_trang_va_NFD_van_khop():
    import unicodedata

    trich = unicodedata.normalize("NFD", "Mức   lương:  20.000.000 đồng/tháng")
    assert xac_minh(trich, DV).ly_do is LyDoNeo.ok


def test_BO_DAU_thi_TRUOT():
    """Trong tiếng Việt dấu là chữ, không phải trang trí."""
    assert xac_minh("Muc luong: 20.000.000 dong/thang", DV).ly_do is LyDoNeo.trich_khong_khop


def test_DOI_HOA_THUONG_thi_TRUOT():
    assert xac_minh("mức lương: 20.000.000 đồng/tháng", DV).ly_do is LyDoNeo.trich_khong_khop


def test_GHEP_HAI_DON_VI_thi_TRUOT():
    """Vết ghép không tồn tại trong tài liệu gốc."""
    ghep = "Mức lương: 20.000.000 đồng/tháng Thời hạn hợp đồng: 12 tháng"
    assert xac_minh(ghep, DV).ly_do is LyDoNeo.trich_khong_khop


def test_trich_rong():
    assert xac_minh("", DV).ly_do is LyDoNeo.trich_rong
    assert xac_minh("   ", DV).ly_do is LyDoNeo.trich_rong


def test_trich_qua_ngan():
    assert len("12 tháng") < QUOTE_TOI_THIEU
    assert xac_minh("12 tháng", DV).ly_do is LyDoNeo.trich_qua_ngan


def test_BA_ly_do_truot_la_BA_ma_rieng():
    assert len({LyDoNeo.trich_rong, LyDoNeo.trich_qua_ngan, LyDoNeo.trich_khong_khop}) == 3


def test_khong_khop_thi_khong_co_vi_tri():
    n = xac_minh("Điều khoản không có trong tài liệu này", DV)
    assert n.ly_do is LyDoNeo.trich_khong_khop
    assert n.chi_so_don_vi is None and n.trang is None


def test_tai_lieu_rong_thi_truot_chu_khong_no():
    assert xac_minh("Mức lương: 20.000.000 đồng/tháng", []).ly_do is LyDoNeo.trich_khong_khop


def test_Neo_bat_bien():
    n = xac_minh("Thời hạn hợp đồng: 12 tháng", DV)
    with pytest.raises(Exception):
        n.trang = 9  # type: ignore[misc]


def test_loc_giu_lai_CHI_du_kien_co_neo_hop_le():
    from src.services.neo_du_kien import loc_co_neo

    facts = [
        {"key": "muc_luong", "gia_tri": "20.000.000", "trich": "Mức lương: 20.000.000 đồng/tháng"},
        {"key": "chuc_danh", "gia_tri": "Giám đốc", "trich": "Chức danh: Giám đốc"},
        {"key": "thoi_han", "gia_tri": "12", "trich": "Thời hạn hợp đồng: 12 tháng"},
    ]
    giu, bo = loc_co_neo(facts, DV)
    assert [f["key"] for f in giu] == ["muc_luong", "thoi_han"]
    assert [f["key"] for f in bo] == ["chuc_danh"]
    assert giu[0]["neo"].chi_so_don_vi == 0
    assert bo[0]["neo"].ly_do is LyDoNeo.trich_khong_khop


def test_loc_bo_du_kien_THIEU_truong_trich():
    from src.services.neo_du_kien import loc_co_neo

    giu, bo = loc_co_neo([{"key": "x", "gia_tri": "1"}], DV)
    assert giu == [] and bo[0]["neo"].ly_do is LyDoNeo.trich_rong
