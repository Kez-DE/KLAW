"""Hạn mức ngày/tháng/lá chắn trên `traces` theo giờ VN (spec 2A §4.2)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from src.services import bao_ve
from src.services.db import get_engine

pytestmark = pytest.mark.integration
TRA_CUU, SOAN_THAO = "/api/v1/tra-cuu", "/api/v1/soan-thao"


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM traces WHERE user_sub = :s"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = :s"), {"s": sub})


def _ghi(sub, endpoint, ts, result_type="answer", cache_hit=False):
    with get_engine().begin() as c:
        c.execute(
            text(
                "INSERT INTO traces (id, ts, endpoint, config_name, result_type, cache_hit, user_sub)"
                " VALUES (:id, :ts, :ep, 'full', :rt, :ch, :sub)"
            ),
            {"id": str(uuid.uuid4()), "ts": ts, "ep": endpoint, "rt": result_type, "ch": cache_hit, "sub": sub},
        )


def test_dem_luot_loai_cache_loi_ngoai_pham_vi_va_NULL_van_dem(nguoi):
    now = datetime.now(UTC)
    _ghi(nguoi, TRA_CUU, now)
    _ghi(nguoi, TRA_CUU, now, cache_hit=True)
    _ghi(nguoi, TRA_CUU, now, result_type="loi")
    _ghi(nguoi, TRA_CUU, now, result_type="out_of_scope")
    _ghi(nguoi, SOAN_THAO, now, result_type=None)
    assert bao_ve.dem_luot(nguoi, TRA_CUU, bao_ve.moc_ngay(now)) == 1
    assert bao_ve.dem_luot(nguoi, SOAN_THAO, bao_ve.moc_ngay(now)) == 1


def test_moc_ngay_theo_VN_khong_theo_UTC(nguoi):
    moc = bao_ve.moc_ngay()
    _ghi(nguoi, TRA_CUU, (moc + timedelta(hours=3)).astimezone(UTC))  # 03:00 hôm nay giờ VN
    _ghi(nguoi, TRA_CUU, (moc - timedelta(minutes=1)).astimezone(UTC))  # hôm qua giờ VN
    assert bao_ve.dem_luot(nguoi, TRA_CUU, moc) == 1


def test_kiem_han_muc_ngay_truoc_la_chan_thang(nguoi, monkeypatch):
    monkeypatch.setattr(bao_ve, "han_muc", lambda plan, khoa: 2 if khoa == "hoi_dap_ngay" else 100_000)
    monkeypatch.setattr(bao_ve, "la_chan", lambda khoa: 3 if khoa == "free_hoi_dap_thang" else 100_000)
    now = datetime.now(UTC)
    _ghi(nguoi, TRA_CUU, now)
    _ghi(nguoi, TRA_CUU, now)
    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_han_muc(nguoi, "free", TRA_CUU)
    assert e.value.status_code == 429 and "2/2 lượt hỏi đáp" in e.value.detail and "Hôm nay" in e.value.detail
    assert int(e.value.headers["Retry-After"]) > 0


def test_la_chan_thang_free_chan_khi_ngay_con(nguoi, monkeypatch):
    monkeypatch.setattr(bao_ve, "han_muc", lambda plan, khoa: 100_000)
    monkeypatch.setattr(bao_ve, "la_chan", lambda khoa: 1 if khoa == "free_hoi_dap_thang" else 100_000)
    _ghi(nguoi, TRA_CUU, datetime.now(UTC))
    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_han_muc(nguoi, "free", TRA_CUU)
    assert e.value.status_code == 429 and "Tháng này" in e.value.detail


def test_soan_thao_kiem_ngay_roi_thang(nguoi, monkeypatch):
    monkeypatch.setattr(
        bao_ve, "han_muc", lambda plan, khoa: {"soan_thao_ngay": 5, "soan_thao_thang": 1}.get(khoa, 100_000)
    )
    _ghi(nguoi, SOAN_THAO, datetime.now(UTC), result_type=None)
    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_han_muc(nguoi, "free", SOAN_THAO)
    assert e.value.status_code == 429 and "bản thảo" in e.value.detail


def test_pro_khong_gioi_han_ngay_nhung_co_la_chan(nguoi, monkeypatch):
    monkeypatch.setattr(bao_ve, "la_chan", lambda khoa: 1 if khoa == "pro_hoi_dap_ngay" else 100_000)
    _ghi(nguoi, TRA_CUU, datetime.now(UTC))
    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_han_muc(nguoi, "pro", TRA_CUU)
    assert e.value.status_code == 429 and "Cá nhân" in e.value.detail


def test_mo_ta_muc_ba_dong_khong_gom_la_chan(nguoi):
    muc = bao_ve.mo_ta_muc(nguoi, "free")
    assert [m["khoa"] for m in muc] == ["hoi_dap_ngay", "soan_thao_ngay", "soan_thao_thang"]
    assert all(m["dat_lai_luc"] is not None for m in muc) and muc[0]["han_muc"] == 200
