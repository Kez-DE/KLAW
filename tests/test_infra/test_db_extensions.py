import os

import psycopg
import pytest

DSN = os.getenv("DATABASE_URL", "postgresql://klaw:klaw@localhost:5432/klaw")


@pytest.mark.integration
def test_pgvector_va_unaccent_da_bat():
    with psycopg.connect(DSN) as conn:
        rows = conn.execute("SELECT extname FROM pg_extension").fetchall()
    names = {r[0] for r in rows}
    assert "vector" in names, f"thiếu pgvector; có: {names}"
    assert "unaccent" in names, f"thiếu unaccent; có: {names}"
