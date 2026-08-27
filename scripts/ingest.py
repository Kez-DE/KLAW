"""Load data/seed/*.jsonl vào Postgres. Idempotent qua documents.checksum."""

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

from src.services.db import get_engine, run_migrations

TEP_SEED = ("documents.jsonl", "provisions.jsonl", "references.jsonl")


def _read(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _kiem_toan_ven(seed: Path) -> None:
    """So từng file seed với `checksums.json`. MỘT LẦN, trước vòng lặp document.

    Khác hẳn phép skip-per-document bên dưới, và đây là kênh hỏng mà phép kia
    không thể thấy: sửa tay `provisions.jsonl` mà KHÔNG chạm `documents.jsonl`
    để lại 21 checksum document không đổi → mọi document bị `continue` → hàm
    trả `{0, 0, 0}`, không phân biệt được với một lần re-run idempotent lành.
    Dữ liệu hỏng nằm trong git, không bao giờ vào DB, không ai biết.

    Trước hàm này `checksums.json` không được dòng Python nào đọc — nó là
    artefact CHỈ-GHI. Thiếu mục cho một file seed cũng là lỗi: bỏ qua im lặng
    thì phép kiểm chỉ là trang trí.
    """
    p = seed / "checksums.json"
    if not p.exists():
        raise ValueError(f"{p} không tồn tại — chạy `python -m scripts.build_seed`")
    files = json.loads(p.read_text(encoding="utf-8")).get("files") or {}
    for name in TEP_SEED:
        mong_doi = files.get(name)
        if not mong_doi:
            raise ValueError(
                f"checksums.json KHÔNG có mục cho {name} — không kiểm được toàn vẹn "
                "seed; chạy lại `python -m scripts.build_seed`")
        thuc_te = hashlib.sha256(
            (seed / name).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        if thuc_te != mong_doi:
            raise ValueError(
                f"{name} LỆCH checksum: file={thuc_te} checksums.json={mong_doi} — "
                "seed bị sửa mà không rebuild; chạy `python -m scripts.build_seed`")


def ingest(seed: Path) -> dict[str, int]:
    _kiem_toan_ven(seed)
    run_migrations()
    docs = _read(seed / "documents.jsonl")
    provs = _read(seed / "provisions.jsonl")
    refs = _read(seed / "references.jsonl")
    written = {"documents": 0, "provisions": 0, "references": 0}

    provs_by_doc: dict[str, list[dict]] = defaultdict(list)
    for p in provs:
        provs_by_doc[p["document_id"]].append(p)
    refs_by_doc: dict[str, list[dict]] = defaultdict(list)
    for r in refs:
        refs_by_doc[r["from_document_id"]].append(r)

    eng = get_engine()
    with eng.begin() as conn:
        existing = dict(conn.execute(text("SELECT id, checksum FROM documents")).all())

        for d in docs:
            if existing.get(d["id"]) == d["checksum"]:
                continue  # không đổi → bỏ qua cả document lẫn provisions của nó

            conn.execute(text("DELETE FROM documents WHERE id = :id"), {"id": d["id"]})
            cols = ", ".join(d)
            binds = ", ".join(f":{k}" for k in d)
            conn.execute(text(f"INSERT INTO documents ({cols}) VALUES ({binds})"), d)
            written["documents"] += 1

            # provisions của document này, theo thứ tự để parent luôn có trước con
            mine = sorted(provs_by_doc.get(d["id"], []), key=lambda x: x["thu_tu"])
            local_to_db: dict[int, int] = {}
            for p in mine:
                parent_db = local_to_db.get(p["parent_local_id"]) if p["parent_local_id"] is not None else None
                new_id = conn.execute(text(
                    "INSERT INTO provisions"
                    " (document_id, parent_id, cap, so_hieu_cap, tieu_de, noi_dung,"
                    "  duong_dan, source_node_id, thu_tu)"
                    " VALUES (:document_id, :parent_id, :cap, :so_hieu_cap, :tieu_de, :noi_dung,"
                    "         :duong_dan, :source_node_id, :thu_tu) RETURNING id"
                ), {**{k: p[k] for k in
                       ("document_id", "cap", "so_hieu_cap", "tieu_de", "noi_dung",
                        "duong_dan", "source_node_id", "thu_tu")},
                    "parent_id": parent_db}).scalar_one()
                if p["parent_local_id"] is not None and parent_db is None:
                    raise ValueError(
                        f"document {d['id']}: provision local_id={p['local_id']} có "
                        f"parent_local_id={p['parent_local_id']} nhưng parent chưa ingest "
                        "(thứ tự thu_tu sai hoặc parent thiếu trong seed)"
                    )
                local_to_db[p["local_id"]] = new_id
                written["provisions"] += 1

            conn.execute(text('DELETE FROM "references" WHERE from_document_id = :id'), {"id": d["id"]})
            for r in refs_by_doc.get(d["id"], []):
                conn.execute(text(
                    'INSERT INTO "references" (from_document_id, to_document_id, loai, raw_text)'
                    " VALUES (:from_document_id, :to_document_id, :loai, :raw_text)"), r)
                written["references"] += 1

    return written


if __name__ == "__main__":
    from src.config import get_settings

    print(ingest(Path(get_settings().data_seed_dir)))
