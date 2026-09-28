"""Nạp cơ quan ban hành + người ký + chức danh cho tầng NÔNG và `metadata` từ
`data/raw/metadata.parquet` — 0 request phát sinh.

    python -m scripts.nap_co_quan_tang_nong

Cùng khuôn `scripts/nap_nguoi_ky.py` (tầng sâu, đọc response MOJ): UPDATE thẳng,
cố ý KHÔNG qua `scripts.ingest` — ingest bỏ qua document có checksum không đổi,
và ép nó chạy lại thì `DELETE FROM documents` CASCADE xoá sạch `provisions`.

Hàng nông/metadata do `scripts.load_incoming_edges` chèn từ chính parquet này
nhưng bỏ lại ba cột trên (kiểm kho 2026-09-28: 0/1.580 dòng có, parquet có
1.580/1.580 cơ quan). Tầng sâu không đụng: nguồn của nó là response gateway.

`COALESCE`: parquet trống ở một cột thì GIỮ giá trị đang có (vd cơ quan do
`scripts.lam_moi_hieu_luc` điền từ `agencyName`), không xoá nó thành NULL.
Idempotent: chạy bao nhiêu lần cũng cho cùng trạng thái.
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from src.services.db import get_engine, run_migrations

_SQL = text(
    "UPDATE documents SET co_quan_ban_hanh = COALESCE(:co_quan, co_quan_ban_hanh),"
    " nguoi_ky = COALESCE(:nguoi_ky, nguoi_ky),"
    " chuc_danh_nguoi_ky = COALESCE(:chuc_danh, chuc_danh_nguoi_ky)"
    " WHERE id = :doc_id AND depth <> 'deep'"
)


def _chuoi(v: object) -> str | None:
    return v.strip() or None if isinstance(v, str) else None


def bo_ba_tu_hang(hang: dict) -> tuple[str | None, str | None, str | None]:
    """Một hàng parquet → (cơ quan, người ký, chức danh); rỗng/NaN → None, khớp
    CHECK của migration 015. Giữ nguyên văn (không đổi hoa/thường), như
    `nap_nguoi_ky.nguoi_ky_tu_response`."""
    return tuple(_chuoi(hang.get(c)) for c in ("co_quan_ban_hanh", "nguoi_ky", "chuc_danh"))


def nap(raw: Path, engine: Engine) -> dict[str, int]:
    p = raw / "metadata.parquet"
    if not p.exists():
        raise FileNotFoundError(f"chưa có {p}; chạy `python -m scripts.download_data` trước")
    meta = pd.read_parquet(p, columns=["id", "co_quan_ban_hanh", "nguoi_ky", "chuc_danh"])
    meta["id"] = meta["id"].astype(str)
    theo_id = {r["id"]: r for r in meta.to_dict("records")}

    run_migrations("015")
    dem = {"tong": 0, "khong_co_trong_parquet": 0, "co_quan": 0, "nguoi_ky": 0, "chuc_danh": 0, "cap_nhat": 0}
    with engine.begin() as conn:
        for (doc_id,) in conn.execute(text("SELECT id FROM documents WHERE depth <> 'deep' ORDER BY id")).all():
            dem["tong"] += 1
            hang = theo_id.get(doc_id)
            if hang is None:
                dem["khong_co_trong_parquet"] += 1
                continue
            co_quan, nguoi_ky, chuc_danh = bo_ba_tu_hang(hang)
            dem["co_quan"] += co_quan is not None
            dem["nguoi_ky"] += nguoi_ky is not None
            dem["chuc_danh"] += chuc_danh is not None
            dem["cap_nhat"] += conn.execute(
                _SQL, {"doc_id": doc_id, "co_quan": co_quan, "nguoi_ky": nguoi_ky, "chuc_danh": chuc_danh}
            ).rowcount
    return dem


if __name__ == "__main__":
    from src.config import get_settings

    print(nap(Path(get_settings().data_raw_dir), get_engine()))
