import pytest
from sqlalchemy import text

from src.services.db import get_engine, run_migrations

pytestmark = pytest.mark.integration


def _cot(bang):
    with get_engine().connect() as c:
        return {
            r[0]
            for r in c.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = :b"), {"b": bang}
            ).all()
        }


def test_024_chay_hai_lan_va_du_cot():
    run_migrations()
    run_migrations()
    assert {
        "id",
        "user_sub",
        "hoi_thoai_id",
        "loai",
        "facts",
        "document",
        "clauses",
        "audit",
        "phien_ban",
        "phien_ban_truoc",
        "tao_luc",
        "cap_nhat_luc",
        "xoa_luc",
        # `run_migrations()` chạy cả danh sách: cột của các migration sau 024.
        "so_lan_sua",  # 025
        "phien_ban_ke_tiep",  # 033
        "viec_id",  # 037
        "phep_sua",  # 037
    } == _cot("ban_thao")
    assert "soan_thao" in _cot("hoi_thoai")
