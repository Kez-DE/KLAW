"""Endpoint `/ban-thao` — danh sách, chi tiết, lùi, xoá (spec 2026-09-09 §8.3)."""

import uuid

import pytest
from sqlalchemy import text

from src.services import ban_thao, bao_ve, hoi_thoai
from src.services.db import get_engine
from tests.test_api.test_xac_thuc_han_muc import _URL as SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration

KET = {
    "document": "# ĐƠN\nMục 1",
    "clauses": [{"stt": 1, "key": "nguoi_lam_don", "noi_dung": "Tôi là A"}],
    "audit_report": {"findings": [], "completeness": 1.0},
}


@pytest.fixture
def hai_nguoi(cai_dat, khoa_ky):
    cai_dat(supabase_url=SUPABASE)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    for s in (a, b):
        bao_ve.ghi_nhan_nguoi_dung(s, None)
    yield a, b
    with get_engine().begin() as c:
        for s in (a, b):
            c.execute(text("DELETE FROM ban_thao WHERE user_sub = CAST(:s AS uuid)"), {"s": s})
            c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": s})
            c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": s})


@pytest.mark.asyncio
async def test_danh_sach_chi_tiet_lui_xoa_va_chu_so_huu(client, khoa_ky, hai_nguoi):
    a, b = hai_nguoi
    ha, hb = _bearer(khoa_ky, a), _bearer(khoa_ky, b)
    pid = hoi_thoai.tao_phien(a, "đơn nghỉ việc")
    bt = ban_thao.tao(a, pid, "don_xin_nghi_viec", {"ho_ten": "A"}, KET)
    ban_thao.sua(a, bt["id"], {"ho_ten": "A", "ngay_nghi": "15/10/2026"}, {**KET, "document": "# ĐƠN v2"})

    d = (await client.get("/api/v1/ban-thao", headers=ha)).json()
    assert d["tong"] == 1
    item = d["items"][0]
    assert item["id"] == bt["id"] and item["loai"] == "don_xin_nghi_viec" and item["hoi_thoai_id"] == pid
    assert item["phien_ban"] == 2 and "ten" in item and "cap_nhat_luc" in item

    r = await client.get(f"/api/v1/ban-thao/{bt['id']}", headers=ha)
    assert r.status_code == 200
    ct = r.json()
    assert ct["id"] == bt["id"] and ct["phien_ban"] == 2 and ct["document"] == "# ĐƠN v2"

    # Người khác không thấy gì — cùng câu trả lời với một id không tồn tại.
    assert (await client.get(f"/api/v1/ban-thao/{bt['id']}", headers=hb)).status_code == 404
    assert (await client.post(f"/api/v1/ban-thao/{bt['id']}/lui", headers=hb)).status_code == 404
    assert (await client.delete(f"/api/v1/ban-thao/{bt['id']}", headers=hb)).status_code == 404
    khong_ton_tai = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/api/v1/ban-thao/{khong_ton_tai}", headers=ha)).status_code == 404

    r = await client.post(f"/api/v1/ban-thao/{bt['id']}/lui", headers=ha)
    assert r.status_code == 200
    assert r.json()["phien_ban"] == 1

    assert (await client.delete(f"/api/v1/ban-thao/{bt['id']}", headers=ha)).status_code == 204
    assert (await client.get(f"/api/v1/ban-thao/{bt['id']}", headers=ha)).status_code == 404


@pytest.mark.asyncio
async def test_id_sai_dinh_dang_uuid_la_404(client, khoa_ky, hai_nguoi):
    a, _ = hai_nguoi
    h = _bearer(khoa_ky, a)
    assert (await client.get("/api/v1/ban-thao/khong-phai-uuid", headers=h)).status_code == 404
    assert (await client.post("/api/v1/ban-thao/khong-phai-uuid/lui", headers=h)).status_code == 404
    assert (await client.delete("/api/v1/ban-thao/khong-phai-uuid", headers=h)).status_code == 404


@pytest.mark.asyncio
async def test_khong_dang_nhap_401(client):
    assert (await client.get("/api/v1/ban-thao")).status_code == 401
