"""Router `/admin` (spec 2B §5.3) qua HTTP thật, và hai bất biến grep."""

import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from src.services import bao_ve, nang_goi
from src.services.db import get_engine
from tests.test_api.test_tra_cuu_phien import SUPABASE

H = {"X-Admin-Key": "khoa-thu", "X-Admin-Boi": "qa@klaw.local"}
tich_hop = pytest.mark.integration


@pytest.fixture
def nguoi(cai_dat):
    cai_dat(admin_api_key="khoa-thu", supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "route@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(
            text("DELETE FROM thong_bao WHERE nguoi_nhan = CAST(:s AS uuid) OR khoa_gom LIKE :k"),
            {"s": sub, "k": f"%{sub}%"},
        )
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi IN ('qa@klaw.local', '(không rõ)')"))
        c.execute(text("DELETE FROM yeu_cau_nang_goi WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


@tich_hop
async def test_luong_duyet_tu_api(client, nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    ds = (
        await client.get("/api/v1/admin/yeu-cau", params={"trang_thai": "cho_duyet", "q": "route@"}, headers=H)
    ).json()
    assert (
        ds["tong"] == 1 and ds["items"][0]["email"] == "route@test.local" and ds["items"][0]["plan_hieu_luc"] == "free"
    )
    r = await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/duyet", headers=H)
    assert r.status_code == 200 and r.json()["plan"] == "pro"
    assert (await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/duyet", headers=H)).status_code == 200, "idempotent"
    assert (
        await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/tu-choi", json={"ly_do": "x"}, headers=H)
    ).status_code == 409
    assert (await client.post("/api/v1/admin/yeu-cau/999999999/duyet", headers=H)).status_code == 404


@tich_hop
async def test_tu_choi_can_ly_do_va_hien_o_chi_tiet(client, nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    assert (
        await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/tu-choi", json={"ly_do": ""}, headers=H)
    ).status_code == 422
    r = await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/tu-choi", json={"ly_do": "Chưa nhận tiền."}, headers=H)
    assert r.status_code == 200 and r.json()["trang_thai"] == "tu_choi" and r.json()["ly_do"] == "Chưa nhận tiền."
    ct = (await client.get(f"/api/v1/admin/tai-khoan/{nguoi}", headers=H)).json()
    assert ct["sub"] == nguoi and ct["yeu_cau"][0]["ly_do"] == "Chưa nhận tiền." and ct["plan"] == "free"


@tich_hop
async def test_tim_dat_goi_thu_hoi_khoa_mo_khoa(client, nguoi):
    ds = (await client.get("/api/v1/admin/tai-khoan", params={"q": "route@test"}, headers=H)).json()
    assert ds["tong"] == 1 and ds["items"][0]["sub"] == nguoi and ds["items"][0]["plan"] == "free"
    r = await client.patch(
        f"/api/v1/admin/tai-khoan/{nguoi}/goi",
        json={"plan": "pro", "so_ngay": 15, "ly_do": "Hỗ trợ khách hàng."},
        headers=H,
    )
    assert r.status_code == 200 and r.json()["plan"] == "pro"
    assert (
        await client.patch(f"/api/v1/admin/tai-khoan/{nguoi}/goi", json={"plan": "vip", "ly_do": "x"}, headers=H)
    ).status_code == 422
    assert (
        await client.patch(f"/api/v1/admin/tai-khoan/{nguoi}/goi", json={"plan": "pro", "so_ngay": 15}, headers=H)
    ).status_code == 422
    r = await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/thu-hoi", json={"ly_do": "Chia sẻ."}, headers=H)
    assert r.status_code == 200 and r.json()["plan"] == "free"
    assert (
        await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/thu-hoi", json={"ly_do": "Chia sẻ."}, headers=H)
    ).status_code == 409
    assert (
        await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/khoa", json={"ly_do": "Spam."}, headers=H)
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/khoa", json={"ly_do": "Spam."}, headers=H)
    ).status_code == 409
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    assert (await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/duyet", headers=H)).status_code == 423
    assert (
        await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/mo-khoa", json={"ly_do": "Đã xác minh."}, headers=H)
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/mo-khoa", json={"ly_do": "Đã xác minh."}, headers=H)
    ).status_code == 409
    assert (await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/mo-khoa", headers=H)).status_code == 422
    assert (await client.get("/api/v1/admin/tai-khoan/khong-phai-uuid", headers=H)).status_code == 422
    assert (await client.get(f"/api/v1/admin/tai-khoan/{uuid.uuid4()}", headers=H)).status_code == 404


@tich_hop
async def test_nhat_ky_json_va_csv_cung_so_dong(client, nguoi):
    await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/khoa", json={"ly_do": "a"}, headers=H)
    await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/mo-khoa", json={"ly_do": "a"}, headers=H)
    j = (await client.get("/api/v1/admin/nhat-ky", params={"doi_tuong": nguoi, "limit": 100}, headers=H)).json()
    c = await client.get(
        "/api/v1/admin/nhat-ky", params={"doi_tuong": nguoi, "limit": 100, "dinh_dang": "csv"}, headers=H
    )
    assert c.status_code == 200 and c.headers["content-type"].startswith("text/csv")
    assert "attachment" in c.headers["content-disposition"]
    assert len(c.text.strip().splitlines()) - 1 == j["tong"] == 2


@tich_hop
async def test_tong_quan_va_goi(client, nguoi):
    assert (await client.get("/api/v1/admin/tong-quan", headers=H)).json()["tong_tai_khoan"] >= 1
    g = (await client.get("/api/v1/admin/goi", headers=H)).json()
    assert g["goi_mac_dinh"] == "free" and any(x["ma"] == "pro" and x["ten"] == "Cá nhân" for x in g["goi"])


@tich_hop
async def test_vuot_la_chan_ip_429(client, cai_dat):
    cai_dat(admin_api_key="khoa-thu", rate_limit_so_luot=10, rate_limit_ip_so_luot=2)
    ma = [(await client.get("/api/v1/admin/goi", headers=H)).status_code for _ in range(4)]
    assert 429 in ma


def test_chi_nang_goi_py_moi_UPDATE_users_SET_plan():
    """Bất biến §4.1: một đường đổi gói."""
    mau = re.compile(r"UPDATE\s+users\s+SET\s+plan", re.IGNORECASE)
    vi_pham = [
        str(p)
        for p in Path("src").rglob("*.py")
        if p.name != "nang_goi.py" and mau.search(p.read_text(encoding="utf-8"))
    ]
    assert vi_pham == [], vi_pham


def test_khong_endpoint_admin_nao_doc_hoi_thoai():
    """Bất biến §5.3: admin thấy bao nhiêu lượt, không thấy hỏi gì."""
    src = Path("src/api/routes_admin.py").read_text(encoding="utf-8")
    assert "luot_hoi_thoai" not in src and "hoi_thoai.chi_tiet" not in src and "hoi_thoai.luot" not in src
