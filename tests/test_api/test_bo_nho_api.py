"""Endpoint bộ nhớ tài khoản (Pro) và phiên (spec 2026-09-09 §6.4, §6.6)."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, bo_nho, hoi_thoai
from src.services.db import get_engine
from tests.test_api.test_xac_thuc_han_muc import _URL as SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration


@pytest.fixture
def hai_nguoi(cai_dat, khoa_ky):
    cai_dat(supabase_url=SUPABASE)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    for s in (a, b):
        bao_ve.ghi_nhan_nguoi_dung(s, None)
    with get_engine().begin() as c:
        c.execute(
            text(
                "UPDATE users SET plan = 'pro', plan_het_han = now() + interval '30 days' WHERE sub = CAST(:s AS uuid)"
            ),
            {"s": a},
        )
    yield a, b
    with get_engine().begin() as c:
        for s in (a, b):
            c.execute(text("DELETE FROM ho_so_tai_khoan WHERE user_sub = CAST(:s AS uuid)"), {"s": s})
            c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": s})
            c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": s})


@pytest.mark.asyncio
async def test_free_403_moi_endpoint_bo_nho(client, khoa_ky, hai_nguoi):
    _, b = hai_nguoi
    h = _bearer(khoa_ky, b)
    assert (await client.get("/api/v1/tai-khoan/bo-nho", headers=h)).status_code == 403
    assert (
        await client.patch("/api/v1/tai-khoan/bo-nho/tham_nien", json={"gia_tri": "3 năm"}, headers=h)
    ).status_code == 403
    assert bo_nho.ho_so_tai_khoan(b) == []


@pytest.mark.asyncio
async def test_pro_doc_sua_xoa(client, khoa_ky, hai_nguoi):
    a, _ = hai_nguoi
    h = _bearer(khoa_ky, a)
    r = await client.patch("/api/v1/tai-khoan/bo-nho/tham_nien", json={"gia_tri": "3 năm"}, headers=h)
    assert r.status_code == 200
    assert (
        await client.patch("/api/v1/tai-khoan/bo-nho/tham_nien", json={"gia_tri": "theo Điều 35"}, headers=h)
    ).status_code == 422
    assert (await client.patch("/api/v1/tai-khoan/bo-nho/khoa_la", json={"gia_tri": "x"}, headers=h)).status_code == 422
    d = (await client.get("/api/v1/tai-khoan/bo-nho", headers=h)).json()
    assert d["ghi_nho"] is True and d["muc"][0]["khoa"] == "tham_nien" and d["muc"][0]["nhan"] == "Thâm niên"
    r = await client.patch("/api/v1/tai-khoan/bo-nho/cai-dat", json={"ghi_nho": False}, headers=h)
    assert r.status_code == 200 and r.json()["ghi_nho"] is False
    assert (await client.delete("/api/v1/tai-khoan/bo-nho/tham_nien", headers=h)).status_code == 204
    bo_nho.sua_khoa_tai_khoan(a, "chu_the", "người lao động")
    assert (await client.delete("/api/v1/tai-khoan/bo-nho", headers=h)).status_code == 204
    assert bo_nho.ho_so_tai_khoan(a) == []


@pytest.mark.asyncio
async def test_phien_khong_ghi_nho_va_sua_ho_so(client, khoa_ky, hai_nguoi):
    a, b = hai_nguoi
    h = _bearer(khoa_ky, a)
    pid = hoi_thoai.tao_phien(a, "c1")
    r = await client.patch(f"/api/v1/hoi-thoai/{pid}/ghi-nho", json={"khong_ghi_nho": True}, headers=h)
    assert r.status_code == 200 and r.json()["khong_ghi_nho"] is True
    assert (
        await client.patch(
            f"/api/v1/hoi-thoai/{pid}/ghi-nho", json={"khong_ghi_nho": True}, headers=_bearer(khoa_ky, b)
        )
    ).status_code == 404
    # Regression: đổi tên một phiên đã tắt ghi nhớ KHÔNG được âm thầm báo lại `false`
    # (PhienTomTatOut.khong_ghi_nho mặc định False che mất cột thật nếu `_SQL_LAY` quên chọn nó).
    r = await client.patch(f"/api/v1/hoi-thoai/{pid}", json={"tieu_de": "Tên mới"}, headers=h)
    assert r.status_code == 200 and r.json()["khong_ghi_nho"] is True
    r = await client.patch(
        f"/api/v1/hoi-thoai/{pid}/ho-so", json={"khoa": "chu_the", "gia_tri": "người lao động"}, headers=h
    )
    assert r.status_code == 200 and r.json()["ho_so_da_dung"] == [
        {"khoa": "chu_the", "nhan": "Vai của bạn", "gia_tri": "người lao động", "gia_dinh": False}
    ]
    r = await client.patch(f"/api/v1/hoi-thoai/{pid}/ho-so", json={"khoa": "chu_the", "gia_tri": None}, headers=h)
    assert r.json()["ho_so_da_dung"] == []
    assert (
        await client.patch(f"/api/v1/hoi-thoai/{pid}/ho-so", json={"khoa": "chu_the", "gia_tri": "Điều 35"}, headers=h)
    ).status_code == 422
    d = (await client.get("/api/v1/hoi-thoai", headers=h)).json()
    assert d["items"][0]["khong_ghi_nho"] is True
