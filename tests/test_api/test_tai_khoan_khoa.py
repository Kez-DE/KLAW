"""Tài khoản bị khoá (spec 2B §5.2, §5.4): 403 ở đường tốn LLM và endpoint tài khoản,
`/han-muc` vẫn trả lời kèm `bi_khoa`, endpoint đọc thuần vẫn mở."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, tai_khoan_qt
from src.services.db import get_engine
from tests.test_api.test_tra_cuu_phien import SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration


@pytest.fixture
def nguoi_khoa(cai_dat, khoa_ky):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "khoa@test.local")
    tai_khoan_qt.khoa(sub, "Thử nghiệm.", "qa@klaw.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM thong_bao WHERE nguoi_nhan = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi = 'qa@klaw.local'"))
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


@pytest.mark.asyncio
async def test_khoa_thi_tra_cuu_va_ho_so_403_han_muc_200_pham_vi_200(client, khoa_ky, nguoi_khoa, graph_gia_lap):
    h = _bearer(khoa_ky, nguoi_khoa)
    r = await client.post("/api/v1/tra-cuu", json={"query": "thử việc bao lâu"}, headers=h)
    assert r.status_code == 403 and r.json()["detail"] == bao_ve.LOI_TAI_KHOAN_KHOA
    assert (await client.get("/api/v1/ho-so", headers=h)).status_code == 403
    hm = await client.get("/api/v1/han-muc", headers=h)
    assert hm.status_code == 200 and hm.json()["bi_khoa"] is True
    assert (await client.get("/api/v1/pham-vi")).status_code == 200
    tai_khoan_qt.mo_khoa(nguoi_khoa, "qa@klaw.local")
    assert (await client.get("/api/v1/ho-so", headers=h)).status_code == 200
    assert (await client.get("/api/v1/han-muc", headers=h)).json()["bi_khoa"] is False
