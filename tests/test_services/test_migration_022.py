"""Migration 022 (spec 2B §5.1): chạy hai lần xanh, đổi kiểu `xu_ly_boi` sang text."""

import pytest
from sqlalchemy import text

from src.services import db
from src.services.db import get_engine

pytestmark = pytest.mark.integration

_KIEU = text(
    "SELECT data_type FROM information_schema.columns"
    " WHERE table_name = 'yeu_cau_nang_goi' AND column_name = 'xu_ly_boi'"
)
_COT = text("SELECT column_name FROM information_schema.columns WHERE table_name = :bang ORDER BY column_name")


def test_022_chay_hai_lan_van_xanh_va_doi_kieu_xu_ly_boi():
    assert db.run_migrations("022") == ["022_quan_tri.sql"]
    assert db.run_migrations("022") == ["022_quan_tri.sql"]  # IF NOT EXISTS + ALTER TYPE cùng kiểu
    with get_engine().connect() as c:
        assert c.execute(_KIEU).scalar_one() == "text"
        cot_users = {r[0] for r in c.execute(_COT, {"bang": "users"})}
        cot_yc = {r[0] for r in c.execute(_COT, {"bang": "yeu_cau_nang_goi"})}
        cot_tb = {r[0] for r in c.execute(_COT, {"bang": "thong_bao"})}
        cot_nk = {r[0] for r in c.execute(_COT, {"bang": "nhat_ky_quan_tri"})}
    assert {"khoa_luc", "khoa_ly_do"} <= cot_users
    assert {"nguon", "tham_chieu", "ly_do"} <= cot_yc
    assert {"nguoi_nhan", "loai", "khoa_gom", "da_doc", "het_hieu_luc"} <= cot_tb
    assert {"hanh_dong", "doi_tuong", "chi_tiet", "boi", "tac_nhan_loai", "ip"} <= cot_nk


def test_thong_bao_khoa_gom_chan_nhan_ban_khi_con_hieu_luc():
    chen = (
        "INSERT INTO thong_bao (nguoi_nhan, loai, tieu_de, noi_dung, duong_dan, khoa_gom)"
        " VALUES (NULL, 'yeu_cau_moi', 't', 'n', '/x', 'test:022')"
        " ON CONFLICT (khoa_gom) WHERE NOT het_hieu_luc DO NOTHING RETURNING id"
    )
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM thong_bao WHERE khoa_gom = 'test:022'"))
        assert c.execute(text(chen)).scalar_one_or_none() is not None
        assert c.execute(text(chen)).scalar_one_or_none() is None, "dòng thứ hai cùng khoa_gom phải bị nuốt"
        c.execute(text("DELETE FROM thong_bao WHERE khoa_gom = 'test:022'"))
