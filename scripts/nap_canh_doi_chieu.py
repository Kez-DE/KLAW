"""Nạp `data/seed/canh_doi_chieu.yaml` vào bảng `canh_doi_chieu` (migration 039;
quyết định 2026-09-28 mục 12): cạnh hiệu lực đã đối chiếu với nguyên văn chính
thống, kèm điều khoản, câu trích và URL làm bằng chứng.

    python -m scripts.nap_canh_doi_chieu [--dry-run]

Seed khoá bằng (số hiệu đi, số hiệu đến, loai) chứ không bằng id cạnh:
`load_incoming_edges` xoá rồi chèn lại mọi cạnh loai 20..23 ở mỗi lượt nạp (id đổi,
bảng này CASCADE theo), nên hàm đó gọi lại `nap_vao` cuối giao dịch của nó. Bảng được
ĐỒNG BỘ với seed: dòng không còn trong seed bị xoá. Kiểm HẾT rồi mới ghi, một giao
dịch; một dòng không phân giải được đúng một cạnh là LỖI — không đoán, không bỏ qua.
"""

import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from sqlalchemy import Connection, Engine, text

from scripts.lam_moi_hieu_luc import NGUON_CHINH_THONG as _NGUON  # cùng nguồn với bằng chứng ghi đè
from src.models.domain import khoa_so_ky_hieu
from src.services.db import get_engine, run_migrations

SEED = Path("data/seed/canh_doi_chieu.yaml")
_KHOA = {"from_so_ky_hieu", "to_so_ky_hieu", "loai", "dieu_khoan", "trich", "url", "kiem_boi", "kiem_luc"}
_LOAI = (20, 21, 22, 23)  # dải cạnh hiệu lực của `load_incoming_edges`


def kiem_hang(i: int, h: dict, bay_gio: datetime) -> dict:
    """Một dòng seed → chính nó, sau khi kiểm (cùng mức chặt `lam_moi_hieu_luc.kiem_ghi_de`)."""
    noi = f"{SEED}[{i}]"
    if set(h) != _KHOA:
        raise ValueError(f"{noi}: khoá phải đúng {sorted(_KHOA)}, được {sorted(h)}")
    if h["loai"] not in _LOAI:
        raise ValueError(f"{noi}: loai {h['loai']!r} ngoài dải cạnh hiệu lực {_LOAI}")
    for k in ("from_so_ky_hieu", "to_so_ky_hieu", "dieu_khoan", "kiem_boi"):
        if not str(h[k] or "").strip():
            raise ValueError(f"{noi}: thiếu {k}")
    if not str(h["trich"] or "").strip() or len(h["trich"]) > 400:
        raise ValueError(f"{noi}: trich phải có và ≤ 400 ký tự (được {len(str(h['trich'] or ''))})")
    u = urlsplit(str(h["url"] or ""))
    if u.scheme != "https" or u.hostname not in _NGUON:
        raise ValueError(f"{noi}: url {h['url']!r} phải là https trên nguồn nhà nước {sorted(_NGUON)}")
    if not isinstance(h["kiem_luc"], datetime) or h["kiem_luc"].tzinfo is None or h["kiem_luc"] > bay_gio:
        raise ValueError(f"{noi}: kiem_luc phải là thời điểm có múi giờ, không ở tương lai")
    return h


def doc_seed(p: Path = SEED) -> list[dict]:
    tho = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(tho, list):
        raise ValueError(f"{p}: phải là danh sách")
    bay_gio = datetime.now(UTC)
    hang = [kiem_hang(i, h or {}, bay_gio) for i, h in enumerate(tho)]
    khoa = [(h["from_so_ky_hieu"], h["to_so_ky_hieu"], h["loai"]) for h in hang]
    if trung := sorted({k for k in khoa if khoa.count(k) > 1}):
        raise ValueError(f"{p}: khoá trùng {trung}")
    return hang


def phan_giai(hang: list[dict], id_theo_so: dict[str, list[str]], canh: dict[tuple, list[int]]) -> dict[int, dict]:
    """Dòng seed → `references.id`. `id_theo_so` khoá bằng `khoa_so_ky_hieu`. Số hiệu khớp
    0 hay >1 văn bản, hoặc cặp đó không có đúng một cạnh `loai` → ValueError nêu hết."""
    ra, loi = {}, []
    for h in hang:
        ten = f"{h['from_so_ky_hieu']} → {h['to_so_ky_hieu']} loai {h['loai']}"
        f = id_theo_so.get(khoa_so_ky_hieu(h["from_so_ky_hieu"]), [])
        t = id_theo_so.get(khoa_so_ky_hieu(h["to_so_ky_hieu"]), [])
        if len(f) != 1 or len(t) != 1:
            loi.append(f"{ten}: số hiệu khớp {len(f)}/{len(t)} văn bản")
            continue
        ids = canh.get((f[0], t[0], h["loai"]), [])
        if len(ids) != 1:
            loi.append(f"{ten}: {len(ids)} cạnh")
            continue
        ra[ids[0]] = h
    if loi:
        raise ValueError(f"{SEED}: {len(loi)} dòng không phân giải được: {loi}")
    return ra


def nap_vao(conn: Connection, hang: list[dict]) -> dict[str, int]:
    """Đồng bộ bảng với `hang` trên `conn` (giao dịch của người gọi)."""
    id_theo_so: dict[str, list[str]] = defaultdict(list)
    for i, so in conn.execute(text("SELECT id, so_ky_hieu FROM documents")):
        id_theo_so[khoa_so_ky_hieu(so)].append(i)
    canh: dict[tuple, list[int]] = defaultdict(list)
    for rid, f, t, loai in conn.execute(
        text(
            'SELECT id, from_document_id, to_document_id, loai FROM "references"'
            " WHERE loai BETWEEN 20 AND 23 AND from_provision_id IS NULL"
        )
    ):
        canh[(f, t, loai)].append(rid)
    ra = phan_giai(hang, id_theo_so, canh)
    xoa = conn.execute(
        text("DELETE FROM canh_doi_chieu WHERE NOT (reference_id = ANY(:ids))"), {"ids": list(ra)}
    ).rowcount
    for rid, h in ra.items():
        conn.execute(
            text(
                "INSERT INTO canh_doi_chieu (reference_id, dieu_khoan, trich, url, kiem_boi, kiem_luc)"
                " VALUES (:r, :dieu_khoan, :trich, :url, :kiem_boi, :kiem_luc) ON CONFLICT (reference_id) DO UPDATE SET"
                " dieu_khoan = EXCLUDED.dieu_khoan, trich = EXCLUDED.trich, url = EXCLUDED.url,"
                " kiem_boi = EXCLUDED.kiem_boi, kiem_luc = EXCLUDED.kiem_luc"
            ),
            {"r": rid, **{k: h[k] for k in ("dieu_khoan", "trich", "url", "kiem_boi", "kiem_luc")}},
        )
    return {"dong_seed": len(hang), "ghi": len(ra), "xoa_ngoai_seed": xoa}


def nap(engine: Engine, seed: Path = SEED, ghi: bool = True) -> dict[str, int]:
    hang = doc_seed(seed)
    run_migrations("039")
    with engine.connect() as c, c.begin() as tx:
        bao = nap_vao(c, hang)
        if not ghi:
            tx.rollback()
    return bao


if __name__ == "__main__":
    kho = "--dry-run" in sys.argv
    print(nap(get_engine(), ghi=not kho), "DRY-RUN — ROLLBACK" if kho else "")
