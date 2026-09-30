"""Migration 042 — route flags and meta facets in `traces` (decision 2026-09-30
item 8).

The integration case runs only at the Integrate step, by explicit file path:
applies clean and idempotent, with the right types. DDL and catalog only — no row
written.
"""

import pytest
from sqlalchemy import text

from src.main import MIGRATIONS_KHOI_DONG
from src.services.db import get_engine, run_migrations


def test_042_nam_trong_migration_khoi_dong():
    assert "042" in MIGRATIONS_KHOI_DONG


@pytest.mark.integration
def test_042_ap_sach_idempotent_dung_kieu():
    run_migrations("042")
    run_migrations("042")
    with get_engine().connect() as c:
        cot = dict(
            c.execute(
                text(
                    "SELECT column_name, udt_name FROM information_schema.columns"
                    " WHERE table_name = 'traces'"
                    " AND column_name IN ('route_ep_meta', 'route_ep_luat', 'gioi_thieu_khia_canh')"
                )
            ).all()
        )
    assert cot == {"route_ep_meta": "bool", "route_ep_luat": "bool", "gioi_thieu_khia_canh": "_text"}
