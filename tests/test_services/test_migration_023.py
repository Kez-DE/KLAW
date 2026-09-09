"""Migration 023 — bộ nhớ ba lớp của phiên + hồ sơ tài khoản (spec 2026-09-09 §6)."""

import pytest
from sqlalchemy import text

from src.services.db import get_engine, run_migrations

pytestmark = pytest.mark.integration


def _cot(bang: str) -> set[str]:
    with get_engine().connect() as c:
        rows = c.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = :b"), {"b": bang}
        ).all()
    return {r[0] for r in rows}


def test_023_chay_hai_lan_van_xanh_va_co_du_cot():
    run_migrations()
    run_migrations()
    assert {"tom_tat", "tom_tat_den_thu_tu", "ho_so", "khong_ghi_nho"} <= _cot("hoi_thoai")
    assert "ghi_nho" in _cot("users")
    assert {"user_sub", "khoa", "gia_tri", "nguon_hoi_thoai_id", "cap_nhat_luc"} == _cot("ho_so_tai_khoan")
