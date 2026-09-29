"""Nạp người ký + chức danh (và cơ quan của văn bản liên tịch) từ response MOJ ĐÃ
TẢI SẴN — 0 request phát sinh.

    python -m scripts.nap_nguoi_ky [--dry-run]

`documentIssues[]` nằm sẵn trong `data/raw/moj/<doc_id>.json` từ lần
`scripts.fetch_moj` đầu tiên; `scripts.build_seed` đọc `agencyName` rồi bỏ qua
`personName`/`jobTitleName`. Script này chỉ đọc lại file trên đĩa.

UPDATE, cố ý KHÔNG qua `scripts.ingest`: ingest bỏ qua mọi document có checksum
không đổi (thêm một cột metadata không làm checksum đổi), và ép nó chạy lại thì
nó `DELETE FROM documents` — CASCADE xoá sạch `provisions` (đổi toàn bộ id) lẫn
4 dòng `sua_doi_dieu_khoan` neo vào chúng. Xem `migrations/015_nguoi_ky.sql`.

Idempotent: UPDATE thuần, chạy bao nhiêu lần cũng cho cùng trạng thái; `cap_nhat`
đếm dòng thật sự đổi, nên lần chạy lại báo 0.
"""

import json
from pathlib import Path

from sqlalchemy import Engine, text

from scripts.fetch_moj import DOC_IDS
from src.services.db import get_engine, run_migrations

_SQL = text(
    "UPDATE documents SET co_quan_ban_hanh = :co_quan, nguoi_ky = :nguoi_ky, chuc_danh_nguoi_ky = :chuc_danh"
    " WHERE id = :doc_id AND (co_quan_ban_hanh, nguoi_ky, chuc_danh_nguoi_ky)"
    " IS DISTINCT FROM (:co_quan, :nguoi_ky, :chuc_danh)"
)


def _theo_thu_tu(d: dict) -> list[dict]:
    """`documentIssues[]` theo `orderIndex` (thiếu thì cuối), giữ thứ tự gốc khi hoà."""
    return sorted(d.get("documentIssues") or [], key=lambda i: (i.get("orderIndex") is None, i.get("orderIndex", 0)))


# Chữ giữ chỗ gateway ghi thay cho "không có" (đo 2026-09-29: 12/2025/TTLT-VKSNDTC-
# TANDTC-BCA-BQP, 07/2026/TTLT-VKSNDTC-TANDTC). Chép nguyên thì bộ lọc và trang văn
# bản hiện "Chưa xác định" — trái quyết định 2026-09-28 mục 8. Không biết là NULL.
_GIU_CHO = frozenset({"chưa xác định"})


def _gia_tri(s: str | None) -> str | None:
    t = (s or "").strip()
    return t if t and t.casefold() not in _GIU_CHO else None


def _khac_nhau(issues: list[dict], truong: str) -> list[str]:
    return list(dict.fromkeys(t for i in issues if (t := _gia_tri(i.get(truong)))))


def co_quan_tu_response(d: dict) -> str | None:
    """`agencyName`, trừ văn bản liên tịch: `documentIssues[]` nêu từ hai cơ quan trở
    lên thì nối chúng theo `orderIndex`. Đo 2026-09-29: 31/2009 và 37/2011/TTLT-
    BNNPTNT-BNV có `agencyName` chỉ là Bộ Nông nghiệp, còn `documentIssues[]` nêu cả
    Bộ Nội vụ — trích dẫn mất một cơ quan ban hành (quyết định 2026-09-28 mục 3)."""
    co_quan = _khac_nhau(_theo_thu_tu(d), "agencyName")
    return ", ".join(co_quan) if len(co_quan) > 1 else _gia_tri(d.get("agencyName"))


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
    issues = _theo_thu_tu(d)
    if not issues:
        return None, None
    if len(_khac_nhau(issues, "agencyName")) > 1:
        # Liên tịch: mỗi cơ quan một người ký (xem `co_quan_tu_response`).
        ten, chuc = _khac_nhau(issues, "personName"), _khac_nhau(issues, "jobTitleName")
        return ", ".join(ten) or None, ", ".join(chuc) or None
    dau = issues[0]
    return _gia_tri(dau.get("personName")), _gia_tri(dau.get("jobTitleName"))


def nap(raw: Path, engine: Engine, dry_run: bool = False) -> dict[str, int]:
    """Cập nhật `co_quan_ban_hanh`/`nguoi_ky`/`chuc_danh_nguoi_ky` cho các văn bản tầng
    sâu — cùng quy tắc `build_seed` ghi vào seed. `dry_run`: ROLLBACK, chỉ đếm.

    Thiếu file raw là LỖI, không phải lý do bỏ qua im lặng: nó nghĩa là
    `data/raw` chưa được tải, và một lần chạy "thành công" cập nhật 0 dòng
    trông y hệt một lần chạy lại lành.
    """
    dem = {"co_nguoi_ky": 0, "khong_co": 0, "cap_nhat": 0}
    run_migrations("015")
    with engine.connect() as conn, conn.begin() as tx:
        for doc_id in DOC_IDS:
            p = raw / "moj" / f"{doc_id}.json"
            if not p.exists():
                raise FileNotFoundError(
                    f"chưa có {p}; chạy `python -m scripts.fetch_moj` trước")
            d = json.loads(p.read_text(encoding="utf-8"))
            ten, chuc = nguoi_ky_tu_response(d)
            dem["co_nguoi_ky" if ten else "khong_co"] += 1
            dem["cap_nhat"] += conn.execute(
                _SQL, {"doc_id": doc_id, "co_quan": co_quan_tu_response(d), "nguoi_ky": ten, "chuc_danh": chuc}
            ).rowcount
        if dry_run:
            tx.rollback()
    return dem


if __name__ == "__main__":
    import sys

    from src.config import get_settings

    print(nap(Path(get_settings().data_raw_dir), get_engine(), dry_run="--dry-run" in sys.argv))
