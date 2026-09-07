"""/ho-so, /nang-goi/yeu-cau, /hoi-thoai/nhap (spec 2A §6.2–6.4, §8.4)."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, hoi_thoai
from src.services.db import get_engine
from tests.test_api.test_tra_cuu_phien import SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration
# Payload đúng hình `TraCuuResponse` — lấy từ một response thật của `graph_gia_lap` nếu thiếu trường.
P = {
    "result_type": "answer",
    "answer": "a",
    "citations": [],
    "nguon": [],
    "warnings": [],
    "coverage_note": None,
    "bang": [],
    "documents": [],
    "soan_thao": None,
    "trace_id": "t",
    "cau_hoi_day_du": None,
    "config_name": "full",
}


@pytest.fixture
def nguoi(cai_dat, khoa_ky):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "a@test.local")
    yield sub
    with get_engine().begin() as c:
        for bang in ("yeu_cau_nang_goi", "hoi_thoai", "traces"):
            c.execute(text(f"DELETE FROM {bang} WHERE user_sub = :s"), {"s": sub})  # noqa: S608 — tên bảng là hằng
        c.execute(text("DELETE FROM users WHERE sub = :s"), {"s": sub})


@pytest.mark.asyncio
async def test_ho_so_tong_hop(client, khoa_ky, nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "x")
    hoi_thoai.ghi_luot(pid, "x", P, "t")
    with get_engine().begin() as c:
        c.execute(
            text(
                "INSERT INTO traces (id, endpoint, config_name, result_type, user_sub) VALUES"
                " (:i, '/api/v1/tra-cuu', 'full', 'answer', :s), (:j, '/api/v1/soan-thao', 'full', NULL, :s)"
            ),
            {"i": str(uuid.uuid4()), "j": str(uuid.uuid4()), "s": nguoi},
        )
    d = (await client.get("/api/v1/ho-so", headers=_bearer(khoa_ky, nguoi))).json()
    assert d["email"] == "a@test.local" and d["plan"] == "free" and d["ten_goi"] == "Miễn phí"
    assert d["so_phien"] == 1 and d["tong_hoi_dap"] == 1 and d["tong_ban_thao"] == 1
    assert d["hoat_dong"][-1]["so_luot"] == 2 and {p["khoa"] for p in d["phan_loai"]} >= {"answer", "soan_thao"}


@pytest.mark.asyncio
async def test_yeu_cau_nang_goi_201_409_422(client, khoa_ky, nguoi):
    h = _bearer(khoa_ky, nguoi)
    r = await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)
    assert r.status_code == 201 and r.json()["loai"] == "nang_goi" and r.json()["trang_thai"] == "cho_duyet"
    assert (await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)).status_code == 409
    assert (await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "vip"}, headers=h)).status_code == 422
    assert (await client.get("/api/v1/nang-goi/yeu-cau", headers=h)).json()["trang_thai"] == "cho_duyet"


@pytest.mark.asyncio
async def test_gia_han_chi_khi_con_7_ngay(client, khoa_ky, nguoi):
    h = _bearer(khoa_ky, nguoi)
    with get_engine().begin() as c:
        c.execute(
            text("UPDATE users SET plan='pro', plan_het_han = now() + interval '20 days' WHERE sub = :s"), {"s": nguoi}
        )
    assert (await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)).status_code == 422
    with get_engine().begin() as c:
        c.execute(text("UPDATE users SET plan_het_han = now() + interval '3 days' WHERE sub = :s"), {"s": nguoi})
    r = await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)
    assert r.status_code == 201 and r.json()["loai"] == "gia_han"
    d = (await client.get("/api/v1/han-muc", headers=h)).json()
    assert d["plan"] == "pro" and d["het_han_luc"] is not None and d["phien"]["luot_toi_da"] == 50


@pytest.mark.asyncio
async def test_pro_het_han_ve_free(client, khoa_ky, nguoi):
    with get_engine().begin() as c:
        c.execute(
            text("UPDATE users SET plan='pro', plan_het_han = now() - interval '1 day' WHERE sub = :s"), {"s": nguoi}
        )
    d = (await client.get("/api/v1/han-muc", headers=_bearer(khoa_ky, nguoi))).json()
    assert d["plan"] == "free" and d["het_han_luc"] is not None and d["phien"]["luot_toi_da"] == 20


@pytest.mark.asyncio
async def test_nhap_phien_201_va_422(client, khoa_ky, nguoi):
    h = _bearer(khoa_ky, nguoi)
    r = await client.post(
        "/api/v1/hoi-thoai/nhap", json={"luot": [{"cau_hoi": "Câu?", "tra_loi": P, "trace_id": "t"}]}, headers=h
    )
    assert r.status_code == 201
    assert hoi_thoai.chi_tiet(nguoi, r.json()["id"])["luot"][0]["cau_hoi"] == "Câu?"
    assert (
        await client.post("/api/v1/hoi-thoai/nhap", json={"luot": [{"cau_hoi": "x", "tra_loi": {"rac": 1}}]}, headers=h)
    ).status_code == 422
    assert (await client.post("/api/v1/hoi-thoai/nhap", json={"luot": []}, headers=h)).status_code == 422
