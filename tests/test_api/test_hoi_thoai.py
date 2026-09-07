"""CRUD phiên hội thoại (spec 2026-09-07 §5.3)."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, hoi_thoai
from src.services.db import get_engine
from tests.test_api.test_xac_thuc_han_muc import _URL as SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration
P = {"result_type": "answer", "answer": "a", "citations": []}


@pytest.fixture
def hai_nguoi(cai_dat, khoa_ky):
    cai_dat(supabase_url=SUPABASE)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    for s in (a, b):
        bao_ve.ghi_nhan_nguoi_dung(s, None)
    yield a, b
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = ANY(CAST(:s AS uuid[]))"), {"s": [a, b]})
        c.execute(text("DELETE FROM users WHERE sub = ANY(CAST(:s AS uuid[]))"), {"s": [a, b]})


@pytest.mark.asyncio
async def test_khong_dang_nhap_401(client, cai_dat):
    cai_dat(supabase_url="")
    assert (await client.get("/api/v1/hoi-thoai")).status_code == 401


@pytest.mark.asyncio
async def test_danh_sach_chi_tiet_doi_ten_xoa(client, khoa_ky, hai_nguoi):
    a, _ = hai_nguoi
    pid = hoi_thoai.tao_phien(a, "Câu hỏi đầu tiên của A")
    hoi_thoai.ghi_luot(pid, "Câu hỏi đầu tiên của A", P, "t")
    r = await client.get("/api/v1/hoi-thoai", headers=_bearer(khoa_ky, a))
    assert r.status_code == 200
    d = r.json()
    assert d["plan"] == "free" and d["luot_moi_phien"] == 20 and d["tong"] == 1
    assert d["items"][0]["id"] == pid and d["items"][0]["so_luot"] == 1
    r = await client.get(f"/api/v1/hoi-thoai/{pid}", headers=_bearer(khoa_ky, a))
    assert r.json()["luot"][0]["tra_loi"]["answer"] == "a"
    r = await client.patch(f"/api/v1/hoi-thoai/{pid}", json={"tieu_de": "  Tên mới  "}, headers=_bearer(khoa_ky, a))
    assert r.status_code == 200 and r.json()["tieu_de"] == "Tên mới"
    assert (
        await client.patch(f"/api/v1/hoi-thoai/{pid}", json={"tieu_de": "   "}, headers=_bearer(khoa_ky, a))
    ).status_code == 422
    assert (await client.delete(f"/api/v1/hoi-thoai/{pid}", headers=_bearer(khoa_ky, a))).status_code == 204
    assert (await client.get(f"/api/v1/hoi-thoai/{pid}", headers=_bearer(khoa_ky, a))).status_code == 404


@pytest.mark.asyncio
async def test_nguoi_khac_404_va_id_sai_dinh_dang_404(client, khoa_ky, hai_nguoi):
    a, b = hai_nguoi
    pid = hoi_thoai.tao_phien(a, "của A")
    assert (await client.get(f"/api/v1/hoi-thoai/{pid}", headers=_bearer(khoa_ky, b))).status_code == 404
    assert (await client.delete(f"/api/v1/hoi-thoai/{pid}", headers=_bearer(khoa_ky, b))).status_code == 404
    assert (
        await client.patch(f"/api/v1/hoi-thoai/{pid}", json={"tieu_de": "x"}, headers=_bearer(khoa_ky, b))
    ).status_code == 404
    assert (await client.get("/api/v1/hoi-thoai/khong-phai-uuid", headers=_bearer(khoa_ky, a))).status_code == 404


@pytest.mark.asyncio
async def test_khong_con_an_theo_goi_va_xoa_phien_bat_ky(client, khoa_ky, hai_nguoi):
    a, _ = hai_nguoi
    ids = [hoi_thoai.tao_phien(a, f"c{i}") for i in range(3)]
    d = (await client.get("/api/v1/hoi-thoai", headers=_bearer(khoa_ky, a))).json()
    assert d["tong"] == 3 and len(d["items"]) == 3
    assert (await client.get(f"/api/v1/hoi-thoai/{ids[0]}", headers=_bearer(khoa_ky, a))).status_code == 200
    assert (await client.delete(f"/api/v1/hoi-thoai/{ids[0]}", headers=_bearer(khoa_ky, a))).status_code == 204
