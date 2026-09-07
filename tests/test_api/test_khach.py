"""Chế độ khách (spec 2A §8): X-Khach-Id, 10 lượt/24h, soạn thảo cần đăng nhập."""

import uuid

import pytest

from src.services import bao_ve
from tests.test_api.test_tra_cuu_phien import SUPABASE


@pytest.fixture
def ghi_lai_rate_limit(monkeypatch):
    goi: list[tuple] = []

    def gia(khoa, so_luot=None, cua_so_giay=None):
        goi.append((khoa, so_luot, cua_so_giay))

    monkeypatch.setattr(bao_ve, "kiem_rate_limit", gia)
    monkeypatch.setattr(bao_ve, "kiem_tran_chi_phi", lambda: None)
    return goi


@pytest.mark.asyncio
async def test_khach_khong_header_401(client, cai_dat, graph_gia_lap):
    cai_dat(supabase_url=SUPABASE)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"})
    assert r.status_code == 401 and r.json()["detail"] == bao_ve.LOI_KHACH_DANG_NHAP


@pytest.mark.asyncio
async def test_khach_co_header_duoc_hoi_va_dem_dung_khoa(client, cai_dat, graph_gia_lap, ghi_lai_rate_limit):
    cai_dat(supabase_url=SUPABASE)
    kid = str(uuid.uuid4())
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"}, headers={"X-Khach-Id": kid})
    assert r.status_code == 200
    assert (f"khach:{kid}", 10, 86400) in ghi_lai_rate_limit
    khoa = [g[0] for g in ghi_lai_rate_limit]
    assert any(k.startswith("khach-ip:") for k in khoa) and any(k.startswith("ip-ngay:") for k in khoa)


@pytest.mark.asyncio
async def test_khach_header_khong_phai_uuid_401(client, cai_dat, graph_gia_lap):
    cai_dat(supabase_url=SUPABASE)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"}, headers={"X-Khach-Id": "abc"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_khach_soan_thao_401(client, cai_dat, ghi_lai_rate_limit):
    cai_dat(supabase_url=SUPABASE)
    # Body lấy từ một test /soan-thao hiện có (tests/test_api/test_soan_thao*.py) — dependency chạy
    # sau khi parse body nên body phải hợp lệ.
    body = {"loai_van_ban": "hdld", "facts": {}}
    r = await client.post("/api/v1/soan-thao", json=body, headers={"X-Khach-Id": str(uuid.uuid4())})
    assert r.status_code == 401 and r.json()["detail"] == bao_ve.LOI_SOAN_THAO_DANG_NHAP


@pytest.mark.asyncio
async def test_chua_cau_hinh_supabase_khong_dem_khach(client, cai_dat, graph_gia_lap, ghi_lai_rate_limit):
    cai_dat(supabase_url="")
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"})
    assert r.status_code == 200
    assert not any(k.startswith("khach") or k.startswith("ip-ngay") for k, *_ in ghi_lai_rate_limit)


@pytest.mark.integration
def test_kiem_rate_limit_hai_cua_so_khong_don_nhau(cai_dat):
    """Giỏ 60 giây KHÔNG được xoá hàng của giỏ 24 giờ (dọn theo khoá)."""
    from fastapi import HTTPException

    # `tests/conftest.py` TẮT tầng nhịp cho cả suite (`rate_limit_so_luot=0`);
    # test này kiểm chính tầng đó nên phải bật lại tại điểm gọi.
    cai_dat(rate_limit_so_luot=10)
    k = f"test:{uuid.uuid4()}"
    for _ in range(3):
        bao_ve.kiem_rate_limit(k, 10, 86400)
    bao_ve.kiem_rate_limit(f"khac:{uuid.uuid4()}", 10, 60)
    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_rate_limit(k, 3, 86400)  # lượt thứ 4 với trần 3
    assert e.value.status_code == 429 and int(e.value.headers["Retry-After"]) <= 86400
