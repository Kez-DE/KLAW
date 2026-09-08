# tests/test_api/test_thong_bao_api.py
"""Sáu endpoint thông báo (spec 2B §5.3, §5.4) và thông báo admin sinh từ `tao_yeu_cau`."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, nang_goi, thong_bao
from src.services.db import get_engine
from tests.test_api.test_tra_cuu_phien import SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration
H = {"X-Admin-Key": "khoa-thu", "X-Admin-Boi": "qa@klaw.local"}


@pytest.fixture
def nguoi(cai_dat, khoa_ky):
    cai_dat(admin_api_key="khoa-thu", supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "tb-api@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(
            text("DELETE FROM thong_bao WHERE nguoi_nhan = CAST(:s AS uuid) OR khoa_gom LIKE :k"),
            {"s": sub, "k": f"%{sub}%"},
        )
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi = 'qa@klaw.local'"))
        c.execute(text("DELETE FROM yeu_cau_nang_goi WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


async def test_tao_yeu_cau_sinh_mot_thong_bao_admin_va_duyet_vo_hieu_no(client, nguoi, khoa_ky):
    h = _bearer(khoa_ky, nguoi)
    truoc = thong_bao.dem_chua_doc(None)
    assert (await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)).status_code == 201
    assert (await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)).status_code == 409
    assert thong_bao.dem_chua_doc(None) == truoc + 1, "hai lần gửi, một thông báo"
    hop = (await client.get("/api/v1/admin/thong-bao", params={"chi_chua_doc": "true"}, headers=H)).json()
    dong = next(x for x in hop["items"] if "tb-api@test.local" in x["noi_dung"])
    assert dong["loai"] == "yeu_cau_moi" and dong["duong_dan"].startswith("/admin/yeu-cau")
    yc = nang_goi.moi_nhat(nguoi)
    assert (await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/duyet", headers=H)).status_code == 200
    assert thong_bao.dem_chua_doc(None) == truoc, "duyệt xong thì thông báo admin hết hiệu lực"
    tb = (await client.get("/api/v1/thong-bao", headers=h)).json()
    assert tb["so_chua_doc"] == 1 and tb["items"][0]["loai"] == "yeu_cau_duyet"
    r = await client.post("/api/v1/thong-bao/da-doc", json={"ids": [tb["items"][0]["id"]]}, headers=h)
    assert r.status_code == 200 and r.json()["da_danh_dau"] == 1
    assert (await client.get("/api/v1/thong-bao", headers=h)).json()["so_chua_doc"] == 0


async def test_da_doc_khong_dong_toi_hop_thu_nguoi_khac(client, nguoi, khoa_ky):
    i = thong_bao.ghi(nguoi_nhan=None, loai="yeu_cau_moi", tieu_de="t", noi_dung="n", duong_dan="/x", khoa_gom=f"test:{nguoi}")
    r = await client.post("/api/v1/thong-bao/da-doc", json={"ids": [i]}, headers=_bearer(khoa_ky, nguoi))
    assert r.status_code == 200 and r.json()["da_danh_dau"] == 0


async def test_luong_tra_event_stream(client, nguoi, khoa_ky, monkeypatch):
    from src.api import luong_thong_bao

    async def ngan(nn, **kw):
        yield luong_thong_bao.sse("so_chua_doc", {"so": 0})

    monkeypatch.setattr(luong_thong_bao, "phat", ngan)
    r = await client.get("/api/v1/admin/thong-bao/luong", headers=H)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream") and "so_chua_doc" in r.text
    r = await client.get("/api/v1/thong-bao/luong", headers=_bearer(khoa_ky, nguoi))
    assert r.status_code == 200 and "so_chua_doc" in r.text
