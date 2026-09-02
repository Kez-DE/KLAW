"""Nạp `linh_vuc` từ `data/raw/metadata.parquet` — UPDATE, cố ý KHÔNG qua
`scripts.ingest`.

    python -m scripts.nap_linh_vuc

Cùng lý do với `scripts/nap_nguoi_ky.py` (xem đó): thêm một cột metadata không
làm `checksum` đổi nên `ingest` bỏ qua mọi document đã có; script này đọc lại
`data/raw/metadata.parquet` trên đĩa rồi UPDATE thẳng, tránh `DELETE FROM
documents` — CASCADE xoá sạch `provisions` (đổi toàn bộ id). Xem
`migrations/018_linh_vuc.sql`.

Khác `nap_nguoi_ky`: nguồn không phải response MOJ đã tải riêng từng văn bản
(`data/raw/moj/<doc_id>.json`) mà là một file `metadata.parquet` DUY NHẤT, phủ
TOÀN BỘ `documents` (kể cả 76 hàng `shallow` + 5 hàng `metadata` nạp bởi
`scripts.load_incoming_edges`, những hàng không nằm trong `DOC_IDS`) chứ không
riêng tầng sâu — nên vòng lặp ở đây chạy trên id đọc từ CHÍNH `documents`,
không phải `DOC_IDS`.

Idempotent: UPDATE thuần, chạy bao nhiêu lần cũng cho cùng trạng thái.
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from src.services.db import get_engine, run_migrations

_SQL = text("UPDATE documents SET linh_vuc = :linh_vuc WHERE id = :doc_id")

# "Chưa phân loại" là nhãn MẶC ĐỊNH của nguồn cho văn bản CHƯA được gắn lĩnh
# vực nào — về nghĩa nó là "rỗng", không phải một lĩnh vực pháp luật thật. Giữ
# nguyên văn nó sẽ khiến một bảng lĩnh vực dựng sau này hiện "Chưa phân loại"
# như một hạng mục thật (T1 finding 2, `task-1-findings.md`). Coi như rỗng:
# rơi xuống `nganh`, hoặc None nếu `nganh` cũng rỗng/"Chưa phân loại".
_CHUA_PHAN_LOAI = "Chưa phân loại"


def linh_vuc_tu_hang(hang: dict) -> str | None:
    """Một hàng `metadata.parquet` (`{"linh_vuc": ..., "nganh": ...}`) → `linh_vuc`.

    Ưu tiên `linh_vuc`, rỗng/NaN/"Chưa phân loại" thì lấy `nganh`, cả hai rỗng
    → None. Không đoán và không tự đặt taxonomy nào KHÁC — chỉ mỗi placeholder
    "Chưa phân loại" của nguồn bị coi như rỗng, mọi giá trị khác giữ verbatim.

    Nhận `dict` thuần (không phải `pandas.Series`) để test được mà không cần
    dựng `metadata.parquet`: giá trị NaN của pandas và `None` của Python đều
    KHÔNG phải `str`, nên `isinstance` bắt được cả hai.
    """
    for cot in ("linh_vuc", "nganh"):
        gia_tri = hang.get(cot)
        if isinstance(gia_tri, str) and gia_tri.strip() and gia_tri.strip() != _CHUA_PHAN_LOAI:
            return gia_tri
    return None


def nap(raw: Path, engine: Engine) -> dict[str, object]:
    """Backfill `documents.linh_vuc` cho MỌI hàng đang có trong DB.

    Thiếu `metadata.parquet` là LỖI, không phải lý do bỏ qua im lặng: nó nghĩa
    là `python -m scripts.download_data` chưa chạy, và một lần chạy "thành
    công" cập nhật 0 dòng trông y hệt một lần chạy lại lành.

    Một `doc_id` không khớp hàng nào trong `metadata.parquet` (văn bản nguồn
    `vanban.chinhphu.vn`, tiền tố `cp-` cố ý không tra bằng id trần — xem
    `migrations/018_linh_vuc.sql`) hoặc khớp nhưng cả `linh_vuc`/`nganh` đều
    rỗng thì KHÔNG phải lỗi: ghi NULL và liệt kê doc_id đó vào `khong_co` thay
    vì đoán.
    """
    p = raw / "metadata.parquet"
    if not p.exists():
        raise FileNotFoundError(
            f"chưa có {p}; chạy `python -m scripts.download_data` trước")
    meta = pd.read_parquet(p, columns=["id", "nganh", "linh_vuc"])
    meta["id"] = meta["id"].astype(str)
    theo_id = {r.id: {"linh_vuc": r.linh_vuc, "nganh": r.nganh}
               for r in meta.itertuples(index=False)}

    run_migrations("018")
    cap_nhat = co_linh_vuc = 0
    khong_co: list[str] = []
    with engine.begin() as conn:
        doc_ids = [r[0] for r in conn.execute(text("SELECT id FROM documents")).all()]
        for doc_id in doc_ids:
            lv = linh_vuc_tu_hang(theo_id.get(doc_id, {}))
            if lv is None:
                khong_co.append(doc_id)
            else:
                co_linh_vuc += 1
            cap_nhat += conn.execute(_SQL, {"doc_id": doc_id, "linh_vuc": lv}).rowcount
    return {"cap_nhat": cap_nhat, "co_linh_vuc": co_linh_vuc, "khong_co": khong_co}


if __name__ == "__main__":
    from src.config import get_settings

    ket_qua = nap(Path(get_settings().data_raw_dir), get_engine())
    print({**ket_qua, "khong_co_so_luong": len(ket_qua["khong_co"])})
