"""`phien_luu` trong `config/han_muc.yaml` + `nguoi_dung_bat_buoc` (spec 2026-09-07 §4.2, §5.3)."""

import pytest
from fastapi import HTTPException

from src.services import bao_ve


def test_phien_luu_toi_da_theo_goi_that():
    bao_ve._doc_han_muc.cache_clear()
    assert bao_ve.phien_luu_toi_da("free") == 10
    assert bao_ve.phien_luu_toi_da("pro") >= 10_000
    # Gói lạ rơi về gói mặc định (hỏng theo hướng CHẶT), như `han_muc_thang`.
    assert bao_ve.phien_luu_toi_da("goi-la") == bao_ve.phien_luu_toi_da("free")


def test_yaml_thieu_phien_luu_thi_fail_loud(tmp_path, monkeypatch):
    f = tmp_path / "han_muc.yaml"
    f.write_text("goi_mac_dinh: free\ngoi:\n  free: 50\n  pro: 500\n", encoding="utf-8")
    monkeypatch.setattr(bao_ve, "HAN_MUC_PATH", f)
    bao_ve._doc_han_muc.cache_clear()
    with pytest.raises(ValueError, match="phien_luu"):
        bao_ve._doc_han_muc()
    bao_ve._doc_han_muc.cache_clear()


def test_yaml_phien_luu_thieu_mot_goi_thi_fail_loud(tmp_path, monkeypatch):
    f = tmp_path / "han_muc.yaml"
    f.write_text(
        "goi_mac_dinh: free\ngoi:\n  free: 50\n  pro: 500\nphien_luu:\n  free: 10\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bao_ve, "HAN_MUC_PATH", f)
    bao_ve._doc_han_muc.cache_clear()
    with pytest.raises(ValueError, match="phien_luu"):
        bao_ve._doc_han_muc()
    bao_ve._doc_han_muc.cache_clear()


@pytest.mark.asyncio
async def test_nguoi_dung_bat_buoc_401_khi_khong_co_danh_tinh(cai_dat, monkeypatch):
    """Kể cả khi Supabase CHƯA cấu hình: không có ai để gán phiên → 401, không phải None."""
    cai_dat(supabase_url="")
    monkeypatch.setattr(bao_ve, "kiem_api_key", lambda request: None)
    monkeypatch.setattr(bao_ve, "kiem_rate_limit", lambda ip, so_luot=None: None)

    class Req:
        headers: dict = {}
        client = type("C", (), {"host": "127.0.0.1"})()

    with pytest.raises(HTTPException) as e:
        await bao_ve.nguoi_dung_bat_buoc(Req())
    assert e.value.status_code == 401
