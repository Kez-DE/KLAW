"""Ánh xạ lỗi của `/tai-lieu` sang HTTP (spec 2026-09-15 §FR-002..FR-005).

Bốn nguyên nhân không đọc được và hai trần tuyệt đối phải ra SÁU thông điệp
khác nhau, mỗi thông điệp nói được MỘT việc người dùng làm tiếp được. Đây là
toàn bộ lý do các mã lỗi không bị gộp: một câu "không xử lý được tệp" đúng về
mặt kỹ thuật và vô dụng với người đang cầm tệp đó.

Phần chạm DB của router nằm ở `test_tai_lieu_api.py`, đánh dấu `integration`.
"""

import pytest
from fastapi import HTTPException

from src.api.routes_tai_lieu import (
    _THONG_DIEP,
    _THONG_DIEP_HE_THONG,
    THONG_DIEP_TRAN,
    _loi_http,
    _uuid_hop_le,
)
from src.services.doc_tai_lieu import ChuyenDoiKhongSanSang, KhongDocDuoc, LoaiHong
from src.services.tai_lieu import TRAN_BYTE, TRAN_TRANG, VuotTran


@pytest.mark.parametrize("ly_do", list(LoaiHong))
def test_MOI_nguyen_nhan_co_thong_diep_rieng(ly_do):
    assert _THONG_DIEP[ly_do].strip()


def test_BON_thong_diep_KHAC_NHAU():
    assert len(set(_THONG_DIEP.values())) == 4


@pytest.mark.parametrize("ly_do", list(LoaiHong))
def test_khong_doc_duoc_thanh_422_dung_thong_diep(ly_do):
    e = _loi_http(KhongDocDuoc(ly_do))
    assert e.status_code == 422 and e.detail == _THONG_DIEP[ly_do]


def test_vuot_tran_byte_neu_MB_chu_khong_phai_so_byte_tho():
    e = _loi_http(VuotTran("so_byte", TRAN_BYTE, TRAN_BYTE + 1))
    assert e.status_code == 422 and "20 MB" in e.detail


def test_vuot_tran_trang_neu_SO_TRANG():
    e = _loi_http(VuotTran("so_trang", TRAN_TRANG, TRAN_TRANG + 1))
    assert e.status_code == 422 and "100 trang" in e.detail


def test_vuot_tran_CHI_PHI_co_cau_rieng_khong_noi_ve_tien():
    """Người dùng không cần biết ngân sách nội bộ; họ cần biết phải làm gì."""
    e = _loi_http(VuotTran("chi_phi", 0.05, 9.9))
    assert e.status_code == 422
    assert "tách nhỏ" in e.detail.lower() and "usd" not in e.detail.lower()


def test_BA_tran_la_BA_cau_khac_nhau():
    assert len(set(THONG_DIEP_TRAN.values())) == 3


@pytest.mark.parametrize("ly_do", ["khong_co_cong_cu", "qua_tai"])
def test_he_thong_khong_san_sang_thanh_503_khong_phai_422(ly_do):
    """Fix round 2 — lỗi HỆ THỐNG (thiếu công cụ, quá tải) không phải lỗi
    tài liệu: 503, không phải 422 dùng cho `KhongDocDuoc`/`VuotTran`, và câu
    trả lời không được đổ lỗi cho người dùng."""
    e = _loi_http(ChuyenDoiKhongSanSang(ly_do))
    assert e.status_code == 503
    assert e.detail == _THONG_DIEP_HE_THONG[ly_do]
    assert "tệp của bạn" not in e.detail.lower(), "không được đổ lỗi cho tài liệu của người dùng"


def test_HAI_thong_diep_he_thong_khac_nhau():
    assert len(set(_THONG_DIEP_HE_THONG.values())) == 2


def test_loi_LA_thi_KHONG_nuot():
    """Lỗi hạ tầng phải nổi lên, không bị hạ cấp thành 422 gây hiểu nhầm."""
    with pytest.raises(RuntimeError):
        _loi_http(RuntimeError("openrouter 502"))


def test_id_khong_phai_uuid_thanh_404_chu_khong_de_postgres_no():
    with pytest.raises(HTTPException) as e:
        _uuid_hop_le("khong-phai-uuid")
    assert e.value.status_code == 404


def test_uuid_hop_le_di_qua():
    assert _uuid_hop_le("0f9d2c1a-1111-4222-8333-444455556666")
