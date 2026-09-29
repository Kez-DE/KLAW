"""Hạ về tầng nông (chỉ tên) văn bản tầng sâu mà toàn văn đã bị rút khỏi seed — K6
2026-09-29, `docs/plans/active/kho-luat-trich-dan-day-du.md`.

    python -m scripts.ha_ve_nong [--ghi]

Đích = văn bản `deep` trong DB có id trong `KHONG_NAP` (`scripts/fetch_moj.py`, lý do
và bằng chứng từng dòng nằm ở đó). Không `--ghi` thì chạy thử rồi ROLLBACK. MỘT
transaction, chạy lại được (lần sau 0 văn bản):

1. Dừng nếu provision của nó còn bị neo bởi `sua_doi_dieu_khoan`, `verified_provisions`
   hay cạnh cấp điều khoản của văn bản KHÁC — mọi FK đều CASCADE, xoá là mất im lặng.
2. Xoá `verified_documents` của nó (bằng chứng nói về toàn văn vừa rút) rồi mọi
   provision; chunk và cạnh cấp điều khoản trong chính nó (`xref.resolve_all` dựng
   lại) đi theo CASCADE. Hàng `documents` và cạnh cấp văn bản giữ nguyên.
3. Chèn lại hàng `mo_dau` mang tên văn bản như `migrations/016_tang_nong.sql`, đặt
   `depth='shallow'`, `checksum='metadata-only'`, `nguon_url=NULL` — trạng thái trước K6.

Chunk tên văn bản sau đó: `python -m scripts.build_chunks --chi-moi --chi-id=TỆP`.
"""

import sys

from sqlalchemy import text

from scripts.fetch_moj import KHONG_NAP
from src.services.db import get_engine

_NEO_NGOAI = text(
    "SELECT (SELECT count(*) FROM sua_doi_dieu_khoan s JOIN provisions p ON p.id = s.provision_id"
    "        WHERE p.document_id = :d)"
    " + (SELECT count(*) FROM verified_provisions v JOIN provisions p ON p.id = v.provision_id"
    "    WHERE p.document_id = :d)"
    ' + (SELECT count(*) FROM "references" r JOIN provisions p ON p.id IN (r.from_provision_id, r.to_provision_id)'
    "    WHERE p.document_id = :d AND r.from_document_id <> :d)"
)


def ha(ghi: bool = False) -> dict:
    with get_engine().connect() as c, c.begin() as tx:
        dich = [
            dict(r)
            for r in c.execute(
                text("SELECT id, so_ky_hieu, ten FROM documents WHERE depth = 'deep' AND id = ANY(:i) ORDER BY id"),
                {"i": list(KHONG_NAP)},
            ).mappings()
        ]
        ra = []
        for d in dich:
            if neo := c.execute(_NEO_NGOAI, {"d": d["id"]}).scalar_one():
                raise ValueError(f"{d['id']} ({d['so_ky_hieu']}): {neo} dòng ngoài văn bản neo vào provision của nó")
            kiem = c.execute(text("DELETE FROM verified_documents WHERE document_id = :id"), d).rowcount
            chunk = c.execute(
                text(
                    "SELECT count(*) FROM chunks ch JOIN provisions p ON p.id = ch.provision_id WHERE p.document_id = :id"
                ),
                d,
            ).scalar_one()
            prov = c.execute(text("DELETE FROM provisions WHERE document_id = :id"), d).rowcount
            if len(d["ten"]) >= 25:  # cùng ngưỡng 016: tên ngắn hơn không mang tín hiệu truy hồi
                c.execute(
                    text(
                        "INSERT INTO provisions (document_id, parent_id, cap, so_hieu_cap, tieu_de, noi_dung,"
                        " duong_dan, thu_tu) VALUES (:id, NULL, 'mo_dau', '', '', :ten, :so_ky_hieu || ' > Mở đầu', 0)"
                    ),
                    d,
                )
            c.execute(
                text(
                    "UPDATE documents SET depth = CASE WHEN length(ten) >= 25 THEN 'shallow' ELSE 'metadata' END,"
                    " checksum = 'metadata-only', nguon_url = NULL WHERE id = :id"
                ),
                d,
            )
            ra.append(
                {
                    "id": d["id"],
                    "so_ky_hieu": d["so_ky_hieu"],
                    "provision_xoa": prov,
                    "chunk_xoa": chunk,
                    "verified_documents_xoa": kiem,
                }
            )
        if not ghi:
            c.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            tx.rollback()
    return {"ghi": ghi, "van_ban": ra}


if __name__ == "__main__":
    print(ha(ghi="--ghi" in sys.argv))
