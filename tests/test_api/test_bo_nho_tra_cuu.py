"""Bộ nhớ đi vào đường tra cứu (spec 2026-09-09 §6.3, §6.5)."""

import uuid

import pytest
from sqlalchemy import text

from src.api import routes
from src.models.schemas import TraCuuRequest
from src.services import bao_ve, bo_nho, hoi_thoai
from src.services.db import get_engine
from tests.test_api.test_xac_thuc_han_muc import _URL as SUPABASE


@pytest.fixture
def nguoi(cai_dat):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM ho_so_tai_khoan WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def test_lich_su_khach_toi_da_10():
    TraCuuRequest(query="x", lich_su=[{"cau_hoi": "a", "tra_loi": "", "duong_dan": []}] * 10)
    with pytest.raises(Exception):
        TraCuuRequest(query="x", lich_su=[{"cau_hoi": "a", "tra_loi": "", "duong_dan": []}] * 11)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chuan_bi_phien_nap_ba_lop(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "c1")
    hoi_thoai.ghi_luot(pid, "c1", {"answer": "a", "citations": []}, None)
    hoi_thoai.ghi_bo_nho(pid, "tóm tắt cũ", 0, {"chu_the": {"gia_tri": "người lao động", "nguon": "nguoi_noi"}})
    req, pid2, bn, _ = await routes._chuan_bi_phien(TraCuuRequest(query="c2", hoi_thoai_id=pid), nguoi)
    assert pid2 == pid and [l.cau_hoi for l in req.lich_su] == ["c1"]  # noqa: E741
    assert bn == {"tom_tat": "tóm tắt cũ", "ho_so": {"chu_the": {"gia_tri": "người lao động", "nguon": "nguoi_noi"}}}
    st = routes._state_vao(req, None, "t", bo_nho=bn)
    assert st["tom_tat"] == "tóm tắt cũ" and st["ho_so"]["chu_the"]["gia_tri"] == "người lao động"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_phien_moi_cua_pro_duoc_seed_tu_tai_khoan_free_thi_khong(nguoi):
    bo_nho.sua_khoa_tai_khoan(nguoi, "tham_nien", "3 năm")
    _, pid, bn, _ = await routes._chuan_bi_phien(TraCuuRequest(query="c1"), nguoi)
    assert bn is None  # free
    with get_engine().begin() as c:
        c.execute(
            text(
                "UPDATE users SET plan = 'pro', plan_het_han = now() + interval '30 days' WHERE sub = CAST(:s AS uuid)"
            ),
            {"s": nguoi},
        )
    _, pid, bn, _ = await routes._chuan_bi_phien(TraCuuRequest(query="c1"), nguoi)
    assert bn["ho_so"]["tham_nien"] == {"gia_tri": "3 năm", "nguon": "tai_khoan"}
    assert hoi_thoai.bo_nho_cua_phien(pid)["ho_so"]["tham_nien"]["gia_tri"] == "3 năm"


def test_payload_va_response_mang_ho_so_da_dung():
    st = {
        "result_type": "answer",
        "answer": "x",
        "citations": [],
        "warnings": [],
        "coverage_note": None,
        "ho_so_da_dung": [{"khoa": "chu_the", "nhan": "Vai của bạn", "gia_tri": "người lao động", "gia_dinh": True}],
    }
    p = routes._payload_cache(st, "answer")
    r = routes.tra_cuu_response(p, "t", "hybrid")
    assert r.ho_so_da_dung[0].khoa == "chu_the" and r.ho_so_da_dung[0].gia_dinh is True
    assert (
        routes.tra_cuu_response({k: v for k, v in p.items() if k != "ho_so_da_dung"}, "t", "hybrid").ho_so_da_dung == []
    )
