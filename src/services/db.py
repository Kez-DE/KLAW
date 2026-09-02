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
        # Pool TƯỜNG MINH. Mặc định của SQLAlchemy (5 + 10 overflow,
        # `pool_timeout=30`) là mặc định của thư viện, không phải một quyết định
        # của dự án — và nó đã đo được là sai với hình dạng tải ở đây: 20 + 20
        # phục vụ được lượng request đồng thời mà một trang tìm kiếm tạo ra,
        # còn `pool_timeout=5` biến "cạn pool" từ 30 GIÂY TREO thành một lỗi
        # nhanh mà người dùng và log đều đọc được ngay.
        #
        # `pool_pre_ping`: kết nối nằm không qua đêm bị Postgres (hoặc một
        # NAT/proxy ở giữa) đóng phía server, và lần dùng lại đầu tiên nổ
        # `OperationalError` — một lỗi 503 cho người dùng đầu tiên mỗi sáng.
        _engine = create_engine(
            db_url, future=True,
            pool_size=20, max_overflow=20, pool_timeout=5, pool_pre_ping=True,
        )
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
