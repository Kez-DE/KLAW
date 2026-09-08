"""Khoá/mở khoá, đặt gói tay, thu hồi (spec 2B §5.2). Task 6 thêm test đọc vào file này."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from src.services import bao_ve, nang_goi, tai_khoan_qt, thong_bao
from src.services.db import get_engine

pytestmark = pytest.mark.integration
BOI = "admin-qt@klaw.local"


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "qt@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM thong_bao WHERE nguoi_nhan = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi = :b"), {"b": BOI})
        c.execute(text("DELETE FROM yeu_cau_nang_goi WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def _dong(sub):
    with get_engine().connect() as c:
        return (
            c.execute(
                text("SELECT plan, plan_het_han, khoa_luc, khoa_ly_do FROM users WHERE sub = CAST(:s AS uuid)"),
                {"s": sub},
            )
            .mappings()
            .one()
        )


def test_khoa_roi_mo_khoa_va_trang_thai_khong_doi(nguoi):
    r = tai_khoan_qt.khoa(nguoi, "Gửi câu hỏi tự động hàng loạt.", BOI, "10.0.0.9")
    assert r["khoa_luc"] is not None and bao_ve.bi_khoa(nguoi) is True
    with pytest.raises(tai_khoan_qt.TrangThaiKhongDoi):
        tai_khoan_qt.khoa(nguoi, "lại", BOI)
    assert thong_bao.dem_chua_doc(nguoi) == 1
    r2 = tai_khoan_qt.mo_khoa(nguoi, BOI)
    assert r2["khoa_luc"] is None and bao_ve.bi_khoa(nguoi) is False
    with pytest.raises(tai_khoan_qt.TrangThaiKhongDoi):
        tai_khoan_qt.mo_khoa(nguoi, BOI)
    with pytest.raises(LookupError):
        tai_khoan_qt.khoa(str(uuid.uuid4()), "x", BOI)
    with get_engine().connect() as c:
        hd = {r[0] for r in c.execute(text("SELECT hanh_dong FROM nhat_ky_quan_tri WHERE boi = :b"), {"b": BOI})}
    assert {"khoa_tai_khoan", "mo_khoa_tai_khoan"} <= hd


def test_dat_goi_so_ngay_None_la_vo_thoi_han_va_goi_la(nguoi):
    r = nang_goi.dat_goi(nguoi, "pro", None, BOI)
    assert r["plan"] == "pro" and r["plan_het_han"] is None and _dong(nguoi)["plan_het_han"] is None
    r = nang_goi.dat_goi(nguoi, "pro", 10, BOI)
    assert 9 < (r["plan_het_han"] - datetime.now(UTC)).total_seconds() / 86400 <= 10
    r = nang_goi.dat_goi(nguoi, "free", None, BOI)
    assert r["plan"] == "free" and r["plan_het_han"] is None
    with pytest.raises(nang_goi.GoiKhongHopLe):
        nang_goi.dat_goi(nguoi, "vip", None, BOI)
    with pytest.raises(nang_goi.ChuaCoHoSo):
        nang_goi.dat_goi(str(uuid.uuid4()), "pro", None, BOI)
    assert thong_bao.dem_chua_doc(nguoi) >= 1


def test_thu_hoi_dat_het_han_now_khong_doi_plan_va_tu_choi_khi_dang_free(nguoi):
    with pytest.raises(nang_goi.KhongCoGiDeThuHoi):
        nang_goi.thu_hoi(nguoi, "x", BOI)
    nang_goi.dat_goi(nguoi, "pro", 30, BOI)
    r = nang_goi.thu_hoi(nguoi, "Chia sẻ tài khoản.", BOI)
    d = _dong(nguoi)
    assert d["plan"] == "pro" and d["plan_het_han"] <= datetime.now(UTC)
    assert r["plan"] == "free", "gói HIỆU LỰC trả về là mặc định"
    assert bao_ve.plan_hieu_luc(nguoi) == "free"
