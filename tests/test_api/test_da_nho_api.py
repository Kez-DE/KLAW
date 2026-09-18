"""`/tai-khoan/da-nho` (Phase 12, R2): xem, xoá một, xoá hết — và tài khoản B
không chạm được vào ký ức của A qua HTTP. Giá trị trong file đều là giả."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve
from src.services import bo_nho_tai_khoan as bn
from src.services.db import get_engine, run_migrations
from tests.test_api.test_xac_thuc_han_muc import _URL as SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration

URL = "/api/v1/tai-khoan/da-nho"


@pytest.fixture
def hai_nguoi(cai_dat, khoa_ky):
    cai_dat(supabase_url=SUPABASE)
    # Bảng chỉ được tạo lúc app khởi động (`MIGRATIONS_KHOI_DONG`); test tự áp
    # migration để không lệ thuộc thứ tự file hay một lần restart uvicorn.
    run_migrations("034")
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    for s in (a, b):
        bao_ve.ghi_nhan_nguoi_dung(s, None)
    bn.ghi(a, "ca_nhan", "ho_ten", "Nguyễn Văn Thử", str(uuid.uuid4()))
    bn.ghi(a, "ca_nhan", "ma_sv", "00000000")
    yield a, b
    with get_engine().begin() as c:
        for s in (a, b):
            c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": s})


@pytest.mark.asyncio
async def test_chua_dang_nhap_401(client, hai_nguoi):
    assert (await client.get(URL)).status_code == 401
    assert (await client.delete(URL)).status_code == 401


@pytest.mark.asyncio
async def test_b_khong_thay_khong_xoa_duoc_cua_a(client, khoa_ky, hai_nguoi):
    a, b = hai_nguoi
    hb = _bearer(khoa_ky, b)
    id_a = bn.liet_ke(a)[0]["id"]
    r = await client.get(URL, headers=hb)
    assert r.status_code == 200 and r.json() == {"muc": []}
    # 404, không 403: không xác nhận với B rằng id đó tồn tại.
    assert (await client.delete(f"{URL}/{id_a}", headers=hb)).status_code == 404
    assert (await client.delete(URL, headers=hb)).status_code == 204
    assert len(bn.liet_ke(a)) == 2


@pytest.mark.asyncio
async def test_a_xem_roi_xoa_mot_roi_xoa_het(client, khoa_ky, hai_nguoi):
    a, _ = hai_nguoi
    ha = _bearer(khoa_ky, a)
    d = (await client.get(URL, headers=ha)).json()
    assert [(m["khoa"], m["nhan"], m["gia_tri"]) for m in d["muc"]] == [
        ("ho_ten", "Họ và tên", "Nguyễn Văn Thử"),
        ("ma_sv", "Mã sinh viên", "00000000"),
    ]
    id_ten = d["muc"][0]["id"]
    assert (await client.delete(f"{URL}/{id_ten}", headers=ha)).status_code == 204
    assert (await client.delete(f"{URL}/{id_ten}", headers=ha)).status_code == 404  # đã xoá thật, không còn để xoá
    assert (await client.delete(f"{URL}/khong-phai-uuid", headers=ha)).status_code == 422
    with get_engine().connect() as c:
        assert c.execute(text("SELECT count(*) FROM bo_nho_tai_khoan WHERE id = CAST(:i AS uuid)"), {"i": id_ten}).scalar_one() == 0
    assert (await client.delete(URL, headers=ha)).status_code == 204
    assert (await client.get(URL, headers=ha)).json() == {"muc": []}
