"""Nạp người ký + chức danh từ response MOJ ĐÃ TẢI SẴN — 0 request phát sinh.

    python -m scripts.nap_nguoi_ky

`documentIssues[]` nằm sẵn trong `data/raw/moj/<doc_id>.json` từ lần
`scripts.fetch_moj` đầu tiên; `scripts.build_seed` đọc `agencyName` rồi bỏ qua
`personName`/`jobTitleName`. Script này chỉ đọc lại file trên đĩa.

UPDATE, cố ý KHÔNG qua `scripts.ingest`: ingest bỏ qua mọi document có checksum
không đổi (thêm một cột metadata không làm checksum đổi), và ép nó chạy lại thì
nó `DELETE FROM documents` — CASCADE xoá sạch `provisions` (đổi toàn bộ id) lẫn
4 dòng `sua_doi_dieu_khoan` neo vào chúng. Xem `migrations/015_nguoi_ky.sql`.

Idempotent: UPDATE thuần, chạy bao nhiêu lần cũng cho cùng trạng thái.
"""

import json
from pathlib import Path

from sqlalchemy import Engine, text

from scripts.fetch_moj import DOC_IDS
from src.services.db import get_engine, run_migrations

_SQL = text(
    "UPDATE documents SET nguoi_ky = :nguoi_ky, chuc_danh_nguoi_ky = :chuc_danh"
    " WHERE id = :doc_id"
)


def nguoi_ky_tu_response(d: dict) -> tuple[str | None, str | None]:
    """`documentIssues[]` → (người ký, chức danh). `(None, None)` khi không có.

    Lấy mục có `orderIndex` NHỎ NHẤT, giữ thứ tự gốc khi hoà — đó là thứ tự MOJ
    công bố. 46/47 văn bản có đúng một mục; 13/2023/NĐ-CP có hai mục TRÙNG người
    ("TRẦN LƯU QUANG" / "Trần Lưu Quang"), và mục đầu viết hoa toàn bộ.

    KHÔNG chuẩn hoá hoa/thường: một cái tên viết hoa là thứ CSDL quốc gia công
    bố, còn `.title()` sẽ phá đúng những tên mà quy tắc viết hoa tiếng Việt
    không áp được. Trình bày là việc của giao diện.

    Chuỗi rỗng/khoảng trắng → None, khớp CHECK của migration 015: "" và NULL
    đọc giống nhau trên màn hình nhưng khác nhau ở `IS NULL`, và có hai cách
    biểu đạt "không biết" là có một cách sẽ bị quên.
    """
    issues = d.get("documentIssues") or []
    if not issues:
        return None, None
    dau = min(issues, key=lambda i: (i.get("orderIndex") is None, i.get("orderIndex", 0)))
    ten = (dau.get("personName") or "").strip() or None
    chuc = (dau.get("jobTitleName") or "").strip() or None
    return ten, chuc


def nap(raw: Path, engine: Engine) -> dict[str, int]:
    """Cập nhật `documents.nguoi_ky`/`chuc_danh_nguoi_ky` cho các văn bản tầng sâu.

    Thiếu file raw là LỖI, không phải lý do bỏ qua im lặng: nó nghĩa là
    `data/raw` chưa được tải, và một lần chạy "thành công" cập nhật 0 dòng
    trông y hệt một lần chạy lại lành.
    """
    dem = {"co_nguoi_ky": 0, "khong_co": 0, "cap_nhat": 0}
    run_migrations("015")
    with engine.begin() as conn:
        for doc_id in DOC_IDS:
            p = raw / "moj" / f"{doc_id}.json"
            if not p.exists():
                raise FileNotFoundError(
                    f"chưa có {p}; chạy `python -m scripts.fetch_moj` trước")
            ten, chuc = nguoi_ky_tu_response(json.loads(p.read_text(encoding="utf-8")))
            dem["co_nguoi_ky" if ten else "khong_co"] += 1
            dem["cap_nhat"] += conn.execute(
                _SQL, {"doc_id": doc_id, "nguoi_ky": ten, "chuc_danh": chuc}
            ).rowcount
    return dem


if __name__ == "__main__":
    from src.config import get_settings

    print(nap(Path(get_settings().data_raw_dir), get_engine()))
