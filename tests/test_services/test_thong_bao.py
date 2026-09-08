"""`thong_bao` (spec 2B §5.2): gộp theo khoa_gom, hai hộp thư, đánh dấu đúng người."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, thong_bao
from src.services.db import get_engine

pytestmark = pytest.mark.integration


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "tb@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM thong_bao WHERE khoa_gom LIKE :k"), {"k": f"%{sub}%"})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def _ghi(nguoi_nhan, khoa):
    return thong_bao.ghi(
        nguoi_nhan=nguoi_nhan, loai="yeu_cau_moi", tieu_de="t", noi_dung="n", duong_dan="/x", khoa_gom=khoa
    )


def test_cung_khoa_gom_chi_mot_dong_khi_con_hieu_luc(nguoi):
    k = thong_bao.KHOA_YEU_CAU.format(sub=nguoi)
    assert _ghi(None, k) is not None
    assert _ghi(None, k) is None
    assert thong_bao.vo_hieu(k) == 1
    assert _ghi(None, k) is not None, "sau khi vô hiệu, cùng khoá được ghi lại"


def test_hai_hop_thu_khong_tron_va_dem_chua_doc(nguoi):
    _ghi(None, f"admin:{nguoi}")
    _ghi(nguoi, f"user:{nguoi}")
    assert any(r["khoa_gom"] == f"user:{nguoi}" for r in thong_bao.danh_sach(nguoi))
    assert not any(r["khoa_gom"] == f"user:{nguoi}" for r in thong_bao.danh_sach(None))
    assert thong_bao.dem_chua_doc(nguoi) == 1


def test_danh_dau_chi_dong_cua_dung_nguoi_nhan(nguoi):
    i = _ghi(nguoi, f"user:{nguoi}")
    j = _ghi(None, f"admin:{nguoi}")
    assert thong_bao.danh_dau_da_doc([i, j], nguoi) == 1, "id của hộp thư admin không đổi"
    assert thong_bao.dem_chua_doc(nguoi) == 0
    assert thong_bao.danh_sach(nguoi, chi_chua_doc=True) == []
    assert thong_bao.danh_dau_da_doc([], nguoi) == 0
