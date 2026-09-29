"""Dọn kho K2 (2026-09-28, `docs/plans/active/kho-luat-trich-dan-day-du.md`).

    python -m scripts.don_kho --cache DIR [--dry-run] [--chi-chua-kiem]
    python -m scripts.don_kho --chi-gop [--dry-run] [--sao-luu DIR]

`DIR` là thư mục cache của `scripts.lam_moi_hieu_luc` (response gateway trong
`DIR/moj/<id>.json`); script này không gửi request nào. Ba việc, MỘT transaction,
chạy lại được:

1. Ghi đè `linh_vuc_chuan`/`nganh_luat` cho các dòng `ghi_de` của
   `config/linh_vuc.yaml` (bằng chứng từng dòng nằm ở đó).
2. Gộp các cặp bản ghi trùng (`BAN_TRUNG`): mọi cạnh `references` của dòng thừa
   được trỏ sang dòng giữ (cạnh trùng hệt một cạnh đã có thì bỏ), provision `mo_dau`
   của dòng thừa — bản sao tiêu đề, dòng giữ đã có `mo_dau` riêng — bị xoá (chunk
   của nó đi theo), rồi mới xoá dòng thừa. Dòng thừa còn provision nào khác, hay
   provision của nó còn bị trỏ tới, là LỖI: dừng, không xoá. Hai dòng phải cùng
   `build_seed.khoa_so_hieu` (chữ Kirin đồng hình, khoảng trắng). Khi ghi, mọi dòng
   sắp xoá hoặc sắp trỏ lại được chép ra `--sao-luu/gop-<id>-<bảng>-<UTC>.csv`
   (không bao giờ ghi đè) TRƯỚC khi đụng tới. `--chi-gop` chỉ chạy việc này.
3. Đối chiếu toàn văn mọi văn bản tầng sâu nạp từ gateway với response mới tải
   → `verified_documents` cho văn bản khớp 100%.
"""

import argparse
import csv
import json
import re
import unicodedata
from datetime import UTC, date, datetime
from html.parser import HTMLParser
from pathlib import Path

from sqlalchemy import text

from scripts.build_seed import khoa_so_hieu
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


def _luu_csv(sao_luu: Path | None, ten: str, dong: list[dict]) -> str | None:
    """Chép `dong` ra `sao_luu/<ten>-<UTC>.csv` — mở bằng "x": không bao giờ ghi đè."""
    if sao_luu is None or not dong:
        return None
    sao_luu.mkdir(parents=True, exist_ok=True)
    tep = sao_luu / f"{ten}-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.csv"
    with tep.open("x", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, list(dong[0]))
        w.writeheader()
        w.writerows(dong)
    return str(tep)


def _gop(c, bo: str, giu: str, sao_luu: Path | None = None) -> dict:
    if c.execute(text("SELECT 1 FROM documents WHERE id = :i"), {"i": bo}).first() is None:
        return {"bo": bo, "da_gop_tu_truoc": True}
    sk = dict(c.execute(text("SELECT id, so_ky_hieu FROM documents WHERE id IN (:b, :g)"), {"b": bo, "g": giu}).all())
    # Số hiệu LƯU là `docNum` nguyên văn của gateway, nên bản trùng có thể khác byte
    # (07/2025/NĐ-СР Kirin, 18/2011/TT- BNNPTNT): so bằng khoá của `build_seed`.
    if len(sk) != 2 or khoa_so_hieu(sk[bo]) != khoa_so_hieu(sk[giu]):
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
            " + (SELECT count(*) FROM anh_van_ban WHERE doc_id = :b)"
        ),
        {"b": bo},
    ).scalar_one()
    if neo:
        raise ValueError(f"{bo}: {neo} dòng sửa đổi/đã kiểm/ảnh bản gốc neo vào dòng thừa")

    canh = [
        dict(r)
        for r in c.execute(
            text('SELECT * FROM "references" WHERE :b IN (from_document_id, to_document_id) ORDER BY id'), {"b": bo}
        ).mappings()
    ]
    ids = [r["id"] for r in canh]
    sao = {
        bang: _luu_csv(sao_luu, f"gop-{bo}-{bang}", dong)
        for bang, dong in (
            (
                "documents",
                [dict(r) for r in c.execute(text("SELECT * FROM documents WHERE id = :b"), {"b": bo}).mappings()],
            ),
            (
                "provisions",
                [
                    dict(r)
                    for r in c.execute(text("SELECT * FROM provisions WHERE document_id = :b"), {"b": bo}).mappings()
                ],
            ),
            (
                "chunks",
                [
                    dict(r)
                    for r in c.execute(
                        text(
                            "SELECT c.* FROM chunks c JOIN provisions p ON p.id = c.provision_id WHERE p.document_id = :b"
                        ),
                        {"b": bo},
                    ).mappings()
                ],
            ),
            ("references", canh),
        )
    }
    bang_chung = c.execute(text("SELECT count(*) FROM canh_doi_chieu")).scalar_one()

    tro = sum(
        c.execute(text(f'UPDATE "references" SET {cot} = :g WHERE {cot} = :b'), {"b": bo, "g": giu}).rowcount
        for cot in ("from_document_id", "to_document_id")
    )
    # Chỉ bỏ cạnh VỪA trỏ lại (`ids`) khi trùng hệt một cạnh khác: cạnh của dòng giữ
    # (có thể mang bằng chứng `canh_doi_chieu`) ở lại; hai cạnh vừa trỏ trùng nhau thì
    # giữ id nhỏ. Không đụng cạnh trùng sẵn có của dòng giữ (việc của B-E8).
    bo_trung = c.execute(
        text(
            'DELETE FROM "references" a USING "references" b WHERE a.id = ANY(:ids) AND b.id <> a.id'
            " AND (b.id <> ALL(:ids) OR b.id < a.id)"
            " AND a.from_document_id = b.from_document_id AND a.to_document_id IS NOT DISTINCT FROM b.to_document_id"
            " AND a.loai = b.loai AND a.from_provision_id IS NOT DISTINCT FROM b.from_provision_id"
            " AND a.to_provision_id IS NOT DISTINCT FROM b.to_provision_id"
        ),
        {"ids": ids},
    ).rowcount
    # Cạnh cấp văn bản giữa hai bản sao thành cạnh tự trỏ sau khi trỏ lại. Dẫn chiếu nội
    # bộ cấp điều khoản của dòng giữ (from = to = giữ, có provision) KHÔNG phải loại này.
    bo_trung += c.execute(
        text(
            'DELETE FROM "references" WHERE id = ANY(:ids) AND from_document_id = :g AND to_document_id = :g'
            " AND from_provision_id IS NULL AND to_provision_id IS NULL"
        ),
        {"ids": ids, "g": giu},
    ).rowcount
    if (con := c.execute(text("SELECT count(*) FROM canh_doi_chieu")).scalar_one()) != bang_chung:
        raise ValueError(f"gộp {bo} → {giu} làm mất {bang_chung - con} dòng canh_doi_chieu — dừng")
    xoa_prov = c.execute(text("DELETE FROM provisions WHERE document_id = :b"), {"b": bo}).rowcount
    c.execute(text("DELETE FROM documents WHERE id = :b"), {"b": bo})
    return {
        "so_ky_hieu": sk[giu],
        "so_ky_hieu_bo": sk[bo],
        "giu": giu,
        "bo": bo,
        "canh_tro_lai": tro,
        "canh_trung_bo": bo_trung,
        "provision_mo_dau_xoa": xoa_prov,
        "sao_luu": sao,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cache", type=Path, help="thư mục cache của scripts.lam_moi_hieu_luc (bắt buộc, trừ --chi-gop)")
    p.add_argument("--dry-run", action="store_true", help="làm hết trong transaction rồi ROLLBACK")
    p.add_argument(
        "--chi-chua-kiem",
        action="store_true",
        help="bước 3 chỉ đối chiếu văn bản tầng sâu CHƯA có dòng verified_documents (dòng cũ giữ nguyên bằng chứng)",
    )
    p.add_argument("--chi-gop", action="store_true", help="chỉ bước 2 (gộp BAN_TRUNG)")
    p.add_argument(
        "--sao-luu", type=Path, default=Path("data/sao-luu"), help="thư mục CSV dòng xoá/trỏ lại (chỉ khi ghi)"
    )
    a = p.parse_args()
    if not a.chi_gop and a.cache is None:
        p.error("--cache là bắt buộc, trừ khi --chi-gop")

    if a.chi_gop:
        with get_engine().connect() as c, c.begin() as tx:
            gop = [_gop(c, bo, giu, None if a.dry_run else a.sao_luu) for bo, giu in BAN_TRUNG.items()]
            print(json.dumps({"gop_ban_trung": gop}, ensure_ascii=False, indent=1))
            if a.dry_run:
                tx.rollback()
                print("DRY-RUN — đã ROLLBACK.")
        return

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
        gop = [_gop(c, bo, giu, None if a.dry_run else a.sao_luu) for bo, giu in BAN_TRUNG.items()]

        da_kiem, lech = [], []
        chua_kiem = " AND id NOT IN (SELECT document_id FROM verified_documents)" if a.chi_chua_kiem else ""
        docs = c.execute(
            text(f"SELECT id, so_ky_hieu FROM documents WHERE depth = 'deep'{chua_kiem} ORDER BY id")
        ).all()
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
