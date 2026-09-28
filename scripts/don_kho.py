"""Dọn kho K2 (2026-09-28, `docs/plans/active/kho-luat-trich-dan-day-du.md`).

    python -m scripts.don_kho --cache DIR [--dry-run]

`DIR` là thư mục cache của `scripts.lam_moi_hieu_luc` (response gateway trong
`DIR/moj/<id>.json`); script này không gửi request nào. Ba việc, MỘT transaction,
chạy lại được:

1. Ghi đè `linh_vuc_chuan`/`nganh_luat` cho các dòng `ghi_de` của
   `config/linh_vuc.yaml` (bằng chứng từng dòng nằm ở đó).
2. Gộp hai cặp bản ghi trùng (`BAN_TRUNG`): mọi cạnh `references` của dòng thừa
   được trỏ sang dòng giữ (cạnh trùng hệt sau khi trỏ thì bỏ), provision `mo_dau`
   của dòng thừa — bản sao tiêu đề, dòng giữ đã có `mo_dau` riêng — bị xoá (chunk
   của nó đi theo), rồi mới xoá dòng thừa. Dòng thừa còn provision nào khác, hay
   provision của nó còn bị trỏ tới, là LỖI: dừng, không xoá.
3. Đối chiếu toàn văn mọi văn bản tầng sâu nạp từ gateway với response mới tải
   → `verified_documents` cho văn bản khớp 100%.
"""

import argparse
import json
import re
import unicodedata
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path

from sqlalchemy import text

from scripts.load_incoming_edges import BAN_TRUNG
from scripts.nap_link_cong_luat import ID_GATEWAY
from src.services.db import get_engine
from src.services.phan_linh_vuc import GHI_DE

# Cấp không đối chiếu: lời mở đầu và phụ lục nằm ngoài cây quy phạm, hàng bảng
# được dàn lại thành "cột | cột" nên không còn là chuỗi con của HTML nguồn.
_BO_QUA = {"mo_dau", "phu_luc", "hang_bang"}
# Chuẩn hoá chỉ đụng TRÌNH BÀY: Ð→Đ, NBSP, dấu tách ô bảng "|" mà chính kho chèn
# khi dàn bảng trong một khoản, khoảng trắng (kể cả trước dấu câu). Chữ không đổi.
_MAP = str.maketrans({"Ð": "Đ", "ð": "đ", "\xa0": " ", "|": " "})
PHUONG_PHAP = (
    "mọi provision cấp điều/khoản/điểm (trừ mo_dau, phu_luc, hang_bang) là chuỗi con nguyên văn của "
    "documentContent.content gateway, sau chuẩn hoá NFC, Ð→Đ, NBSP, bỏ dấu tách ô bảng '|' của kho, "
    "gộp khoảng trắng và bỏ khoảng trắng trước dấu câu"
)

class _Chu(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.manh: list[str] = []

    def handle_data(self, data: str) -> None:
        self.manh.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"p", "br", "div", "tr", "td", "li"}:
            self.manh.append(" ")


def _chuan(s: str) -> str:
    s = re.sub(r"\s+", " ", unicodedata.normalize("NFC", s.translate(_MAP)))
    return re.sub(r" ([.,;:)])", r"\1", s).strip()


def doi_chieu_toan_van(provisions: list[dict], html_goc: str) -> tuple[int, int, list[int]]:
    """(số provision đối chiếu, số khớp, id không khớp) — khớp = chuỗi con nguyên văn."""
    p = _Chu()
    p.feed(html_goc)
    goc = _chuan("".join(p.manh))
    xet = [x for x in provisions if x["cap"] not in _BO_QUA]
    truot = [x["id"] for x in xet if _chuan(x["noi_dung"]) not in goc]
    return len(xet), len(xet) - len(truot), truot


def _gop(c, bo: str, giu: str) -> dict:
    if c.execute(text("SELECT 1 FROM documents WHERE id = :i"), {"i": bo}).first() is None:
        return {"bo": bo, "da_gop_tu_truoc": True}
    sk = dict(c.execute(text("SELECT id, so_ky_hieu FROM documents WHERE id IN (:b, :g)"), {"b": bo, "g": giu}).all())
    if len(sk) != 2 or sk[bo] != sk[giu]:
        raise ValueError(f"cặp trùng {bo}/{giu} không cùng số hiệu: {sk}")
    cap_bo = [r[0] for r in c.execute(text("SELECT cap FROM provisions WHERE document_id = :b"), {"b": bo})]
    cap_giu = [r[0] for r in c.execute(text("SELECT cap FROM provisions WHERE document_id = :g"), {"g": giu})]
    if set(cap_bo) - {"mo_dau"} or "mo_dau" not in cap_giu:
        raise ValueError(f"{bo}: provision {cap_bo} (giữ {giu}: {cap_giu}) — không phải bản sao tiêu đề")
    bi_tro = c.execute(
        text(
            'SELECT count(*) FROM "references" r JOIN provisions p ON p.id IN (r.from_provision_id, r.to_provision_id)'
            " WHERE p.document_id = :b"
        ),
        {"b": bo},
    ).scalar_one()
    if bi_tro:
        raise ValueError(f"{bo}: {bi_tro} cạnh cấp điều khoản trỏ vào provision của dòng thừa")
    # Mọi FK đều ON DELETE CASCADE: xoá mà còn dòng neo vào là mất dữ liệu trong im lặng.
    neo = c.execute(
        text(
            "SELECT (SELECT count(*) FROM sua_doi_dieu_khoan s JOIN provisions p ON p.id = s.provision_id"
            "        WHERE p.document_id = :b)"
            " + (SELECT count(*) FROM verified_provisions v JOIN provisions p ON p.id = v.provision_id"
            "    WHERE p.document_id = :b)"
            " + (SELECT count(*) FROM verified_documents WHERE document_id = :b)"
        ),
        {"b": bo},
    ).scalar_one()
    if neo:
        raise ValueError(f"{bo}: {neo} dòng sửa đổi/đã kiểm neo vào dòng thừa")
    tro = sum(
        c.execute(text(f'UPDATE "references" SET {cot} = :g WHERE {cot} = :b'), {"b": bo, "g": giu}).rowcount
        for cot in ("from_document_id", "to_document_id")
    )
    bo_trung = c.execute(
        text(
            'DELETE FROM "references" a USING "references" b WHERE a.id > b.id'
            " AND :g IN (a.from_document_id, a.to_document_id)"
            " AND a.from_document_id = b.from_document_id AND a.to_document_id IS NOT DISTINCT FROM b.to_document_id"
            " AND a.loai = b.loai AND a.from_provision_id IS NOT DISTINCT FROM b.from_provision_id"
            " AND a.to_provision_id IS NOT DISTINCT FROM b.to_provision_id"
        ),
        {"g": giu},
    ).rowcount
    bo_trung += c.execute(
        text('DELETE FROM "references" WHERE from_document_id = :g AND to_document_id = :g'), {"g": giu}
    ).rowcount
    xoa_prov = c.execute(text("DELETE FROM provisions WHERE document_id = :b"), {"b": bo}).rowcount
    c.execute(text("DELETE FROM documents WHERE id = :b"), {"b": bo})
    return {
        "so_ky_hieu": sk[giu],
        "giu": giu,
        "bo": bo,
        "canh_tro_lai": tro,
        "canh_trung_bo": bo_trung,
        "provision_mo_dau_xoa": xoa_prov,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cache", type=Path, required=True, help="thư mục cache của scripts.lam_moi_hieu_luc")
    p.add_argument("--dry-run", action="store_true", help="làm hết trong transaction rồi ROLLBACK")
    a = p.parse_args()

    with get_engine().connect() as c, c.begin() as tx:
        ghi_de = sum(
            c.execute(
                text(
                    "UPDATE documents SET linh_vuc_chuan = COALESCE(:lv, linh_vuc_chuan),"
                    " nganh_luat = COALESCE(:nl, nganh_luat) WHERE id = :i"
                ),
                {"i": i, "lv": g.get("linh_vuc"), "nl": g.get("nganh_luat")},
            ).rowcount
            for i, g in GHI_DE.items()
        )
        gop = [_gop(c, bo, giu) for bo, giu in BAN_TRUNG.items()]

        da_kiem, lech = [], []
        docs = c.execute(text("SELECT id, so_ky_hieu FROM documents WHERE depth = 'deep' ORDER BY id")).all()
        for doc_id, sk in docs:
            if doc_id in ID_GATEWAY:  # toàn văn không lấy từ gateway (xem ID_GATEWAY)
                continue
            f = a.cache / "moj" / f"{doc_id}.json"
            d = json.loads(f.read_text(encoding="utf-8"))
            provs = [
                dict(r)
                for r in c.execute(
                    text("SELECT id, cap, noi_dung FROM provisions WHERE document_id = :d"), {"d": doc_id}
                ).mappings()
            ]
            n, khop, truot = doi_chieu_toan_van(provs, (d.get("documentContent") or {}).get("content") or "")
            if khop < n or n == 0:
                lech.append(f"{sk} ({doc_id}): {khop}/{n}, lệch {truot[:5]}")
                continue
            luc = datetime.fromtimestamp(f.stat().st_mtime, UTC)
            c.execute(
                text(
                    "INSERT INTO verified_documents (document_id, verified_at, verified_by, nguon_doi_chieu,"
                    " ket_luan_hieu_luc, ghi_chu_lech_voi_moj) VALUES (:d, :at, :by, :nguon, :kl, :gc)"
                    " ON CONFLICT (document_id) DO UPDATE SET verified_at = EXCLUDED.verified_at,"
                    " verified_by = EXCLUDED.verified_by, nguon_doi_chieu = EXCLUDED.nguon_doi_chieu,"
                    " ket_luan_hieu_luc = EXCLUDED.ket_luan_hieu_luc, ghi_chu_lech_voi_moj = EXCLUDED.ghi_chu_lech_voi_moj"
                ),
                {
                    "d": doc_id,
                    "at": date.today(),
                    "by": "may-doi-chieu-toan-van",
                    "nguon": f"https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/{doc_id} "
                    f"(documentContent.content, tải {luc:%Y-%m-%d %H:%M} UTC)",
                    "kl": f"effStatus gateway = {(d.get('effStatus') or {}).get('code')} lúc tải; phán quyết hiệu lực "
                    "vẫn do src/services/effectivity.py",
                    "gc": f"{khop}/{n} khớp — {PHUONG_PHAP}",
                },
            )
            da_kiem.append(doc_id)

        print(
            json.dumps(
                {
                    "ghi_de_linh_vuc": ghi_de,
                    "gop_ban_trung": gop,
                    "verified_documents": len(da_kiem),
                    "khong_ghi_vi_lech": lech,
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        if a.dry_run:
            tx.rollback()
            print("DRY-RUN — đã ROLLBACK.")


if __name__ == "__main__":
    main()
