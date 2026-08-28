"""Resolve cross-references inside Vietnamese statute text.

Vietnamese statutes are full of "theo quy định tại khoản 2 Điều 35 của Bộ
luật này". An isolated retrieval chunk cannot resolve that on its own, so the
LLM fills the gap itself (pain point #5) — hallucinated citations. Only
same-document references are resolved to a `provision_id` here; a
cross-document reference rarely names a document number and cannot be mapped
with confidence, so it is left unresolved (see `resolve_all`). Retrieval
expands 1 hop from a resolved edge, never deeper.

This module reads raw `noi_dung`, so it inherits the same three defects Plan
1 already paid for in `prov_parser.py` — each has a regression test in
`tests/test_services/test_xref.py`:

  1. "Điều 33a" is a valid label (an article inserted by an amending law).
     `r"Điều\\s+(\\d+)"` truncates it to 33 and produces a wrong-target edge.
  2. "Ð" (U+00D0, LATIN CAPITAL LETTER ETH) is visually identical to "Đ"
     (U+0110) and appears twice in document 96172.
  3. The corpus is not pure NFC (document 96117 has 'ư' + combining U+0323
     instead of precomposed 'ự').
"""

import logging
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)

# Defect #2/#3 above — normalize before matching, not just at storage time,
# because this function receives raw noi_dung as-is.
_MAP_D = str.maketrans({"Ð": "Đ", "ð": "đ"})


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFC", s).translate(_MAP_D)


# "khoản 2 Điều 35 của Bộ luật này"  |  "Điều 12 của Luật BHXH"
#
# Defect #1: the article number uses `\d+[a-zA-ZđĐ]*`, matching
# `prov_parser.RE_SO[Cap.dieu]`'s convention for the same "Điều 33a" label.
#
# Two lookaheads after the number, in this order:
#   (?!\w)      the match must consume the WHOLE token. Without this, a
#               period-terminated heading like "Điều 21." lets `\d+` back off
#               from "21" to "2" (since backtracking only needs the char
#               right after the shorter match to not be ".", and "1" isn't
#               "."), and the OLD lookahead below would then wrongly pass —
#               producing a phantom match "Điều 2" out of "Điều 21.".
#   (?!\s*\.)   reject a heading: "Điều 21. Nội dung ..." is not a reference
#               to itself — a following period means this is a label, not a
#               citation.
RE_XREF = re.compile(
    r"(?:khoản\s+(?P<khoan>\d+)\s+)?"
    r"Điều\s+(?P<dieu>\d+[a-zA-ZđĐ]*)(?!\w)(?!\s*\.)"
    r"(?P<duoi>\s+(?:của\s+)?(?:Bộ luật|Luật|Nghị định|Thông tư)\s+(?P<nay>này)?)?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class XrefHit:
    so_dieu: int
    so_khoan: int | None
    cung_van_ban: bool
    raw: str
    hau_to: str = ""  # letter suffix of so_dieu (e.g. "a" in "Điều 33a"), "" if none


def find_xrefs(noi_dung: str) -> list[XrefHit]:
    out: list[XrefHit] = []
    for m in RE_XREF.finditer(_normalize(noi_dung)):
        dieu_raw = m.group("dieu")
        so_dieu_str, hau_to = re.match(r"(\d+)([a-zA-ZđĐ]*)", dieu_raw).groups()
        so_dieu = int(so_dieu_str)
        out.append(XrefHit(
            so_dieu=so_dieu,
            so_khoan=int(m.group("khoan")) if m.group("khoan") else None,
            cung_van_ban=bool(m.group("nay")),
            raw=m.group(0).strip(),
            hau_to=hau_to,
        ))
    return out


def resolve_all(engine: Engine) -> int:
    """Scan every provision, write clause-level edges into "references".

    Only same-document references are resolved (see module docstring for
    why). Idempotent: deletes previously-written provision-level edges
    before reinserting, inside one transaction, so a failure rolls back
    cleanly instead of leaving a half-written state — and running this twice
    yields the same edge count, not duplicates. The 242 document-level rows
    from Plan 1/MOJ (from_provision_id IS NULL) are untouched by the DELETE.

    Returns the number of edges written. References that don't resolve
    (cross-document, or a same-document "Điều N" whose N doesn't exist in
    this document) are not written and not silently discarded either — they
    are counted and logged, with a short sample, via the `xref` logger.
    """
    ghi = 0
    khong_resolve = 0
    khac_van_ban = 0
    tu_tham_chieu = 0
    mau_khong_resolve: list[str] = []

    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT id, document_id, noi_dung FROM provisions WHERE noi_dung <> ''"
        )).mappings().all()

        # (document_id, so_hieu_cap) → provision_id, for cap = 'dieu' only.
        dieu_idx = {
            (r["document_id"], r["so_hieu_cap"]): r["id"]
            for r in conn.execute(text(
                "SELECT id, document_id, so_hieu_cap FROM provisions WHERE cap = 'dieu'"
            )).mappings().all()
        }

        conn.execute(text('DELETE FROM "references" WHERE from_provision_id IS NOT NULL'))

        for r in rows:
            for hit in find_xrefs(r["noi_dung"]):
                if not hit.cung_van_ban:
                    khac_van_ban += 1
                    continue
                so_hieu_dich = f"{hit.so_dieu}{hit.hau_to}"
                target = dieu_idx.get((r["document_id"], so_hieu_dich))
                if target is None:
                    khong_resolve += 1
                    if len(mau_khong_resolve) < 5:
                        mau_khong_resolve.append(f"{r['document_id']}: {hit.raw!r}")
                    continue
                if target == r["id"]:
                    tu_tham_chieu += 1
                    continue
                conn.execute(text(
                    'INSERT INTO "references"'
                    " (from_document_id, to_document_id, from_provision_id, to_provision_id, loai, raw_text)"
                    " VALUES (:fd, :td, :fp, :tp, 4, :raw)"   # loai 4 = Dẫn chiếu (mã MOJ)
                ), {"fd": r["document_id"], "td": r["document_id"],
                    "fp": r["id"], "tp": target, "raw": hit.raw})
                ghi += 1

    logger.info(
        "resolve_all: %d cạnh ghi | %d cùng văn bản không resolve | "
        "%d tự tham chiếu bỏ qua | %d khác văn bản (không map)",
        ghi, khong_resolve, tu_tham_chieu, khac_van_ban,
    )
    if mau_khong_resolve:
        logger.info("mẫu không resolve: %s", mau_khong_resolve)
    return ghi
