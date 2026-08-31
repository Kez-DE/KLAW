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


def run_migrations(chi: str | None = None) -> list[str]:
    """Chạy mọi file migrations/*.sql theo thứ tự tên. Idempotent nhờ IF NOT EXISTS.

    `chi` — chỉ chạy file có tên bắt đầu bằng tiền tố này (vd `"014"`). Mặc định
    `None` = chạy hết, đúng hành vi cũ; đây là đường khởi động của ứng dụng.

    Vì sao cần lọc: mọi file chạy trong MỘT transaction, nên một migration-cổng
    đang đỏ (loại `RAISE EXCEPTION` khi corpus vi phạm bất biến) làm rollback cả
    những file DDL chả liên quan. Đúng như thiết kế cho ứng dụng — cổng phải chặn
    khởi động. Nhưng một script nạp dữ liệu chỉ cần đúng BẢNG CỦA NÓ tồn tại,
    và một test đo tính idempotent của migration X không được đỏ vì migration Y.
    """
    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql")
                   if chi is None or p.name.startswith(chi))
    applied: list[str] = []
    with get_engine().begin() as conn:
        for f in files:
            conn.execute(text(f.read_text(encoding="utf-8")))
            applied.append(f.name)
    return applied
