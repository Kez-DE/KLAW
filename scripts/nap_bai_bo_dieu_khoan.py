"""Nạp `data/seed/bai_bo_dieu_khoan.yaml` vào bảng `bai_bo_dieu_khoan` (migration 043;
quyết định 2026-09-30 mục 9): điều khoản bị văn bản khác bãi bỏ, kèm điều khoản đi bãi bỏ,
câu trích nguyên văn và nguồn chính thống.

    python -m scripts.nap_bai_bo_dieu_khoan          # dry-run: kiểm, ghi thử, ROLLBACK
    python -m scripts.nap_bai_bo_dieu_khoan --ghi

Seed do `scripts.trich_bai_bo` viết ra, khoá bằng (id văn bản, `duong_dan` điều khoản) và
văn bản đi bãi bỏ — không bằng `provisions.id`, vì `ingest` có thể đổi id (CASCADE xoá dòng
của bảng này): chạy lại script sau mỗi lượt `ingest`. Bảng được ĐỒNG BỘ với seed. Kiểm HẾT
rồi mới ghi, một giao dịch; một điều khoản không phân giải được đúng một dòng là LỖI.
"""

import re
import sys
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from sqlalchemy import Connection, Engine, text

from scripts.lam_moi_hieu_luc import NGUON_CHINH_THONG as _NGUON
from src.models.domain import khoa_so_ky_hieu
from src.services.db import MIGRATIONS_DIR, get_engine

SEED = Path("data/seed/bai_bo_dieu_khoan.yaml")
_KHOA = {
    "van_ban",
    "van_ban_id",
    "boi",
    "boi_id",
    "boi_dieu_khoan",
    "dieu_khoan",
    "trich",
    "url",
    "tu_ngay",
    "kiem_boi",
    "kiem_luc",
}
# Đúng hình dạng phần sau số hiệu của `provisions.duong_dan`.
_RE_DUONG_DAN = re.compile(r"^Điều \d+[a-zđ]?(?: > Khoản \d+[a-zđ]?)?(?: > Điểm [a-zđ]\d?)?$")


def kiem_hang(i: int, h: dict, bay_gio: datetime) -> dict:
    """Một dòng seed → chính nó, sau khi kiểm (cùng mức chặt `nap_canh_doi_chieu.kiem_hang`)."""
    noi = f"{SEED}[{i}]"
    if set(h) != _KHOA:
        raise ValueError(f"{noi}: khoá phải đúng {sorted(_KHOA)}, được {sorted(h)}")
    for k in ("van_ban", "van_ban_id", "boi", "boi_id", "boi_dieu_khoan", "kiem_boi"):
        if not str(h[k] or "").strip():
            raise ValueError(f"{noi}: thiếu {k}")
    dk = h["dieu_khoan"]
    if (
        not isinstance(dk, list)
        or not dk
        or len(set(dk)) != len(dk)
        or not all(_RE_DUONG_DAN.match(str(x)) for x in dk)
    ):
        raise ValueError(f"{noi}: dieu_khoan phải là danh sách không trùng dạng 'Điều 9 > Khoản 5', được {dk!r}")
    if not str(h["trich"] or "").strip() or len(h["trich"]) > 2000:
        raise ValueError(f"{noi}: trich phải có và ≤ 2000 ký tự (được {len(str(h['trich'] or ''))})")
    u = urlsplit(str(h["url"] or ""))
    if u.scheme != "https" or u.hostname not in _NGUON:
        raise ValueError(f"{noi}: url {h['url']!r} phải là https trên nguồn nhà nước {sorted(_NGUON)}")
    if not isinstance(h["tu_ngay"], date) or isinstance(h["tu_ngay"], datetime):
        raise ValueError(f"{noi}: tu_ngay phải là một ngày, được {h['tu_ngay']!r}")
    if not isinstance(h["kiem_luc"], datetime) or h["kiem_luc"].tzinfo is None or h["kiem_luc"] > bay_gio:
        raise ValueError(f"{noi}: kiem_luc phải là thời điểm có múi giờ, không ở tương lai")
    return h


def doc_seed(p: Path = SEED) -> list[dict]:
    tho = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(tho, list):
        raise ValueError(f"{p}: phải là danh sách")
    bay_gio = datetime.now(UTC)
    hang = [kiem_hang(i, h or {}, bay_gio) for i, h in enumerate(tho)]
    khoa = [(h["van_ban_id"], x, h["boi_id"]) for h in hang for x in h["dieu_khoan"]]
    if trung := sorted({k for k in khoa if khoa.count(k) > 1}):
        raise ValueError(f"{p}: điều khoản trùng {trung}")
    return hang


def _so(s: str | None) -> str:
    return khoa_so_ky_hieu(s).replace(" ", "")


def phan_giai(hang: list[dict], dieu_khoan: dict[tuple[str, str], list[int]], van_ban: dict[str, str]) -> list[dict]:
    """Dòng seed → dòng bảng. `dieu_khoan`: (id văn bản, `duong_dan` sau số hiệu) → id điều
    khoản; `van_ban`: id → số hiệu. Điều khoản khớp 0 hay >1 dòng, id văn bản mang số hiệu
    khác seed, hoặc văn bản đi bãi bỏ không có → ValueError nêu hết."""
    ra, loi = [], []
    for h in hang:
        ten = f"{h['van_ban']} ← {h['boi']} {h['boi_dieu_khoan']}"
        if _so(van_ban.get(h["van_ban_id"])) != _so(h["van_ban"]):
            loi.append(f"{ten}: id {h['van_ban_id']} mang số hiệu {van_ban.get(h['van_ban_id'])!r}")
            continue
        if h["boi_id"] not in van_ban:
            loi.append(f"{ten}: văn bản đi bãi bỏ {h['boi_id']} không có trong documents")
            continue
        for x in h["dieu_khoan"]:
            ids = dieu_khoan.get((h["van_ban_id"], x), [])
            if len(ids) != 1:
                loi.append(f"{ten}: {x} khớp {len(ids)} điều khoản")
                continue
            ra.append(
                {
                    "provision_id": ids[0],
                    "boi_document_id": h["boi_id"],
                    **{k: h[k] for k in ("boi_dieu_khoan", "trich", "url", "tu_ngay", "kiem_boi", "kiem_luc")},
                }
            )
    if loi:
        raise ValueError(f"{SEED}: {len(loi)} dòng không phân giải được: {loi}")
    return ra


def nap_vao(conn: Connection, hang: list[dict]) -> dict[str, int]:
    """Đồng bộ bảng với `hang` trên `conn` (giao dịch của người gọi)."""
    ids = sorted({h["van_ban_id"] for h in hang})
    dieu_khoan: dict[tuple[str, str], list[int]] = defaultdict(list)
    for pid, doc_id, dd in conn.execute(
        text("SELECT id, document_id, duong_dan FROM provisions WHERE document_id = ANY(:ids)"), {"ids": ids}
    ):
        if " > " in dd:
            dieu_khoan[(doc_id, dd.split(" > ", 1)[1])].append(pid)
    van_ban = dict(
        conn.execute(
            text("SELECT id, so_ky_hieu FROM documents WHERE id = ANY(:ids)"),
            {"ids": ids + sorted({h["boi_id"] for h in hang})},
        ).all()
    )
    dong = phan_giai(hang, dieu_khoan, van_ban)
    truoc = conn.execute(text("SELECT count(*) FROM bai_bo_dieu_khoan")).scalar_one()
    conn.execute(text("DELETE FROM bai_bo_dieu_khoan"))
    for r in dong:
        conn.execute(
            text(
                "INSERT INTO bai_bo_dieu_khoan (provision_id, boi_document_id, boi_dieu_khoan, trich, url, tu_ngay,"
                " kiem_boi, kiem_luc) VALUES (:provision_id, :boi_document_id, :boi_dieu_khoan, :trich, :url,"
                " :tu_ngay, :kiem_boi, :kiem_luc)"
            ),
            r,
        )
    return {"dong_seed": len(hang), "dieu_khoan": len(dong), "truoc": truoc}


def nap(engine: Engine, seed: Path = SEED, ghi: bool = False) -> dict[str, int]:
    """DDL 043 chạy TRONG cùng giao dịch: dry-run trên DB chưa có bảng cũng không ghi gì."""
    hang = doc_seed(seed)
    with engine.connect() as c, c.begin() as tx:
        c.execute(text((MIGRATIONS_DIR / "043_bai_bo_dieu_khoan.sql").read_text(encoding="utf-8")))
        bao = nap_vao(c, hang)
        if not ghi:
            tx.rollback()
    return bao


if __name__ == "__main__":
    ghi = "--ghi" in sys.argv
    print(nap(get_engine(), ghi=ghi), "" if ghi else "DRY-RUN — ROLLBACK")
