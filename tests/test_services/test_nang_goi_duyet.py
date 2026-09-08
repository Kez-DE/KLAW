"""`nang_goi.duyet`/`tu_choi` (spec 2B §5.2): idempotent theo tham_chieu, FOR UPDATE,
cộng dồn khi gia hạn, khoá thì không duyệt, lưu lý do từ chối."""

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from src.services import bao_ve, nang_goi, thong_bao
from src.services.db import get_engine

BOI = "admin-test@klaw.local"


def test_han_moi_nang_goi_tinh_tu_now_gia_han_cong_don():
    now = datetime(2026, 9, 8, 12, tzinfo=UTC)
    con = now + timedelta(days=10)
    assert nang_goi._han_moi("nang_goi", con, now, 30) == now + timedelta(days=30)
    assert nang_goi._han_moi("gia_han", con, now, 30) == con + timedelta(days=30)
    assert nang_goi._han_moi("gia_han", now - timedelta(days=1), now, 30) == now + timedelta(days=30)
    assert nang_goi._han_moi("gia_han", None, now, 30) == now + timedelta(days=30)


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "duyet@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(
            text("DELETE FROM thong_bao WHERE khoa_gom LIKE :k OR nguoi_nhan = CAST(:s AS uuid)"),
            {"k": f"%{sub}%", "s": sub},
        )
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi = :b"), {"b": BOI})
        c.execute(text("DELETE FROM yeu_cau_nang_goi WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def _goi(sub):
    with get_engine().connect() as c:
        return c.execute(text("SELECT plan, plan_het_han FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub}).one()


def _ngay_con(het):
    return (het - datetime.now(UTC)).total_seconds() / 86400


@pytest.mark.integration
def test_duyet_hai_lan_cung_tham_chieu_chi_cong_mot_chu_ky(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    r1 = nang_goi.duyet(yc["id"], "admin", f"yeu_cau:{yc['id']}", BOI, "10.0.0.1")
    r2 = nang_goi.duyet(yc["id"], "admin", f"yeu_cau:{yc['id']}", BOI, "10.0.0.1")
    assert r1["trang_thai"] == "da_duyet" and r2["plan_het_han"] == r1["plan_het_han"]
    plan, het = _goi(nguoi)
    assert plan == "pro" and 29 < _ngay_con(het) <= 30
    with get_engine().connect() as c:
        so_nk = c.execute(
            text("SELECT count(*) FROM nhat_ky_quan_tri WHERE boi = :b AND hanh_dong = 'duyet_yeu_cau'"), {"b": BOI}
        ).scalar_one()
    assert so_nk == 1, "lần hai không ghi thêm gì"
    assert thong_bao.dem_chua_doc(nguoi) == 1


@pytest.mark.integration
def test_gia_han_cong_don_tu_han_con_hieu_luc(nguoi):
    with get_engine().begin() as c:
        c.execute(
            text("UPDATE users SET plan='pro', plan_het_han = now() + interval '3 days' WHERE sub = CAST(:s AS uuid)"),
            {"s": nguoi},
        )
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    assert yc["loai"] == "gia_han"
    nang_goi.duyet(yc["id"], "admin", f"yeu_cau:{yc['id']}", BOI)
    assert 32.9 < _ngay_con(_goi(nguoi)[1]) <= 33


@pytest.mark.integration
def test_duyet_yeu_cau_da_xu_ly_bang_tham_chieu_khac_nem_DaXuLy(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    nang_goi.duyet(yc["id"], "admin", f"yeu_cau:{yc['id']}", BOI)
    with pytest.raises(nang_goi.DaXuLy):
        nang_goi.duyet(yc["id"], "thanh_toan", "gd:khac", BOI)
    with pytest.raises(nang_goi.KhongTonTai):
        nang_goi.duyet(10**9, "admin", "x", BOI)


@pytest.mark.integration
def test_hai_duyet_song_song_mot_thang_mot_DaXuLy(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    ket_qua: list[str] = []

    def chay(tc: str) -> None:
        try:
            nang_goi.duyet(yc["id"], "admin", tc, BOI)
            ket_qua.append("ok")
        except nang_goi.DaXuLy:
            ket_qua.append("da_xu_ly")

    luong = [threading.Thread(target=chay, args=(tc,)) for tc in ("a", "b")]
    for t in luong:
        t.start()
    for t in luong:
        t.join()
    assert sorted(ket_qua) == ["da_xu_ly", "ok"]
    assert 29 < _ngay_con(_goi(nguoi)[1]) <= 30, "chỉ một chu kỳ"


@pytest.mark.integration
def test_duyet_cho_nguoi_dang_khoa_nem_TaiKhoanKhoa(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    with get_engine().begin() as c:
        c.execute(text("UPDATE users SET khoa_luc = now(), khoa_ly_do = 'x' WHERE sub = CAST(:s AS uuid)"), {"s": nguoi})
    with pytest.raises(nang_goi.TaiKhoanKhoa):
        nang_goi.duyet(yc["id"], "admin", f"yeu_cau:{yc['id']}", BOI)
    assert _goi(nguoi)[0] == "free"


@pytest.mark.integration
def test_tu_choi_luu_ly_do_va_cho_gui_lai(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    r = nang_goi.tu_choi(yc["id"], "Chưa nhận được chuyển khoản.", BOI)
    assert r["trang_thai"] == "tu_choi" and r["ly_do"].startswith("Chưa")
    assert nang_goi.moi_nhat(nguoi)["ly_do"] == "Chưa nhận được chuyển khoản."
    assert _goi(nguoi)[0] == "free"
    assert nang_goi.tao_yeu_cau(nguoi, "pro")["trang_thai"] == "cho_duyet", "từ chối rồi thì gửi lại được"
    with pytest.raises(nang_goi.DaXuLy):
        nang_goi.tu_choi(yc["id"], "lại", BOI)
