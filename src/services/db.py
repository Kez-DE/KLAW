from pathlib import Path

from sqlalchemy import Engine, create_engine, text

from src.config import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        db_url = get_settings().database_url
        # Ensure psycopg3 driver is used
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        _engine = create_engine(db_url, future=True)
    return _engine


def run_migrations() -> list[str]:
    """Chạy mọi file migrations/*.sql theo thứ tự tên. Idempotent nhờ IF NOT EXISTS."""
    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))
    applied: list[str] = []
    with get_engine().begin() as conn:
        for f in files:
            conn.execute(text(f.read_text(encoding="utf-8")))
            applied.append(f.name)
    return applied
