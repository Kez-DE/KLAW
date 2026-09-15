"""Hạng bằng chứng của một dữ kiện neo vào chữ OCR (mở rộng 2026-09-15b).

Phép tra chuỗi vẫn chạy y hệt. Điều đổi là NÓ CHỨNG MINH ĐƯỢC GÌ: neo vào lớp
chữ thật nghĩa là "tài liệu viết đúng câu này"; neo vào chữ OCR nghĩa là "máy
đọc ảnh ra câu này". Câu thứ hai yếu hơn, và người dùng phải thấy sự khác nhau
đó, nếu không giao diện đang hứa nhiều hơn thứ nó giữ được.
"""

from src.services.doc_tai_lieu import DonViVanBan, NguonChu
from src.services.neo_du_kien import LyDoNeo, loc_co_neo, xac_minh

DONG = "Mức lương: 20.000.000 đồng/tháng"
THAT = [DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung=DONG)]
QUET = [
    DonViVanBan(
        chi_so=0, trang=1, offset_dau=0, noi_dung=DONG,
        nguon_chu=NguonChu.ocr, do_tin=0.93,
    )
]


def test_neo_vao_lop_chu_that_mang_nhan_lop_chu():
    n = xac_minh(DONG, THAT)
    assert n.ly_do is LyDoNeo.ok
    assert n.nguon_chu is NguonChu.lop_chu and n.do_tin is None


def test_neo_vao_chu_OCR_mang_nhan_OCR_va_do_tin():
    n = xac_minh(DONG, QUET)
    assert n.ly_do is LyDoNeo.ok
    assert n.nguon_chu is NguonChu.ocr and n.do_tin == 0.93


def test_du_kien_neo_vao_OCR_co_NGUON_rieng():
    """`tai_lieu` và `tai_lieu_ocr` là hai giá trị, không phải một."""
    f = [{"key": "luong_thang", "gia_tri": "20000000", "trich": DONG}]
    giu_that, _ = loc_co_neo(f, THAT)
    giu_quet, _ = loc_co_neo(f, QUET)
    assert giu_that[0]["nguon"] == "tai_lieu"
    assert giu_quet[0]["nguon"] == "tai_lieu_ocr"


def test_bo_dau_van_TRUOT_ca_tren_chu_OCR():
    assert xac_minh("Muc luong: 20.000.000 dong/thang", QUET).ly_do is LyDoNeo.trich_khong_khop


def test_khong_khop_thi_khong_co_hang_bang_chung():
    n = xac_minh("câu này không có trong tài liệu", QUET)
    assert n.ly_do is LyDoNeo.trich_khong_khop
    assert n.nguon_chu is None and n.do_tin is None
