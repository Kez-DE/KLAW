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


def test_tim_theo_email_va_dem_luot_30_ngay(nguoi):
    with get_engine().begin() as c:
        c.execute(
            text(
                "INSERT INTO traces (id, endpoint, config_name, result_type, user_sub, cache_hit) VALUES"
                " (:a, '/api/v1/tra-cuu', 'full', 'answer', :s, false),"
                " (:b, '/api/v1/tra-cuu', 'full', 'answer', :s, true),"
                " (:c, '/api/v1/tra-cuu', 'full', 'loi', :s, false)"
            ),
            {"a": str(uuid.uuid4()), "b": str(uuid.uuid4()), "c": str(uuid.uuid4()), "s": nguoi},
        )
    tong, rows = tai_khoan_qt.tim("qt@test", 20, 0)
    assert tong >= 1
    r = next(x for x in rows if x["sub"] == nguoi)
    assert r["email"] == "qt@test.local" and r["luot_30_ngay"] == 1 and r["so_phien"] == 0
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM traces WHERE user_sub = :s"), {"s": nguoi})


def test_chi_tiet_gom_ho_so_khoa_va_lich_su_yeu_cau(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    nang_goi.tu_choi(yc["id"], "Thử.", BOI)
    tai_khoan_qt.khoa(nguoi, "Kiểm.", BOI)
    d = tai_khoan_qt.chi_tiet(nguoi)
    assert d is not None and d["sub"] == nguoi and d["khoa_ly_do"] == "Kiểm." and d["email"] == "qt@test.local"
    assert d["yeu_cau"][0]["trang_thai"] == "tu_choi" and d["yeu_cau"][0]["ly_do"] == "Thử."
    assert tai_khoan_qt.chi_tiet(str(uuid.uuid4())) is None
    assert tai_khoan_qt.yeu_cau_theo_id(yc["id"])["ly_do"] == "Thử."
    assert tai_khoan_qt.yeu_cau_theo_id(10**9) is None


def test_danh_sach_yeu_cau_loc_trang_thai_va_email(nguoi):
    nang_goi.tao_yeu_cau(nguoi, "pro")
    tong, rows = tai_khoan_qt.danh_sach_yeu_cau("cho_duyet", "qt@test", 20, 0)
    assert tong == 1 and rows[0]["user_sub"] == nguoi and rows[0]["email"] == "qt@test.local"
    assert rows[0]["plan"] == "free" and rows[0]["khoa_luc"] is None
    tong0, _ = tai_khoan_qt.danh_sach_yeu_cau("da_duyet", "qt@test", 20, 0)
    assert tong0 == 0


def test_tong_quan_dem_du_bay_so(nguoi):
    truoc = tai_khoan_qt.tong_quan()
    nang_goi.dat_goi(nguoi, "pro", 3, BOI)  # Cá nhân hiệu lực, hết hạn trong 7 ngày
    nang_goi.tao_yeu_cau(nguoi, "pro")  # gia_han, cho_duyet
    sau = tai_khoan_qt.tong_quan()
    assert set(sau) == {
        "tong_tai_khoan",
        "dang_ca_nhan",
        "cho_duyet",
        "het_han_7_ngay",
        "moi_7_ngay",
        "dang_khoa",
        "hoi_dap_hom_nay",
    }
    assert sau["dang_ca_nhan"] == truoc["dang_ca_nhan"] + 1
    assert sau["het_han_7_ngay"] == truoc["het_han_7_ngay"] + 1
    assert sau["cho_duyet"] == truoc["cho_duyet"] + 1
    tai_khoan_qt.khoa(nguoi, "x", BOI)
    assert tai_khoan_qt.tong_quan()["dang_khoa"] == truoc["dang_khoa"] + 1


def test_danh_sach_goi_doc_tu_yaml():
    d = tai_khoan_qt.danh_sach_goi()
    ma = {g["ma"]: g for g in d["goi"]}
    assert d["goi_mac_dinh"] == "free" and d["chu_ky_pro_ngay"] == 30
    assert ma["pro"]["ten"] == "Cá nhân" and ma["free"]["han_muc"]["hoi_dap_ngay"] == 200
