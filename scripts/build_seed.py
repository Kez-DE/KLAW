"""Parse JSON thô → data/seed/*.jsonl (VÀO GIT)."""

import hashlib
import json
import warnings
from pathlib import Path

from scripts.fetch_moj import DOC_IDS
from src.models.domain import DocumentRow
from src.services.prov_parser import parse_anomalies, parse_provisions

TINH_TRANG_MAP = {
    "CHL": "CHL", "HHL": "HHL", "HHL1P": "HHL1P",
}


def _date(v: str | None) -> str | None:
    return v[:10] if v else None


def bam_tep(p: Path) -> str:
    """sha256 của một file seed. Dùng CHUNG với `scripts.ingest`."""
    return hashlib.sha256(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def build(raw: Path, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    docs: list[dict] = []
    provs: list[dict] = []
    refs: list[dict] = []
    checksums: dict[str, str] = {}
    canh_bao_tong: list[str] = []

    for doc_id, (depth, so_ky_hieu) in DOC_IDS.items():
        p = raw / "moj" / f"{doc_id}.json"
        if not p.exists():
            raise FileNotFoundError(f"chưa fetch {doc_id}; chạy `python -m scripts.fetch_moj`")
        d = json.loads(p.read_text(encoding="utf-8"))
        html = (d.get("documentContent") or {}).get("content") or ""
        if not html:
            raise ValueError(f"doc {doc_id} không có documentContent.content — không được bỏ qua im lặng")

        # Cổng CẤU TRÚC chạy TRƯỚC khi ghi seed. parse_anomalies() đã tồn tại và
        # đã có test từ vòng trước nhưng build không gọi nó, nên nó chưa bao giờ
        # chạy trên dữ liệu thật — đó là lý do bốn nhóm lỗi parser lọt được vào
        # 19.077 dòng seed mà 49 test vẫn xanh.
        loi, canh_bao = parse_anomalies(html, so_ky_hieu)
        if loi:
            raise ValueError(
                f"doc {doc_id} ({so_ky_hieu}): {len(loi)} bất thường cấu trúc — "
                f"KHÔNG ghi seed: {loi[:5]}")
        canh_bao_tong.extend(f"{doc_id} ({so_ky_hieu}): {c}" for c in canh_bao)

        prov_rows = [r.model_dump(mode="json") for r in parse_provisions(html, so_ky_hieu)]

        # Checksum băm HTML *VÀ* các dòng provision sinh ra từ nó. Nếu chỉ băm
        # HTML thì có một kênh dữ liệu cũ ÂM THẦM: sửa parser → rebuild seed →
        # `ingest` thấy checksum không đổi nên bỏ qua cả 21 văn bản → Postgres
        # giữ nguyên các dòng hỏng và mọi phép kiểm vẫn xanh. Vẫn idempotent:
        # cùng HTML + cùng parser ⇒ cùng checksum.
        checksum = hashlib.sha256(
            (html + "\n" + json.dumps(prov_rows, ensure_ascii=False, sort_keys=True))
            .encode("utf-8")).hexdigest()
        checksums[doc_id] = checksum

        docs.append(DocumentRow(
            id=doc_id,
            so_ky_hieu=so_ky_hieu,
            loai_van_ban=(d.get("docType") or {}).get("name") or "Chưa xác định",
            ten=d.get("title") or "",
            co_quan_ban_hanh=d.get("agencyName"),
            ngay_ban_hanh=_date(d.get("issueDate")),
            ngay_hieu_luc=_date(d.get("effFrom")),
            ngay_het_hieu_luc=_date(d.get("effTo")),
            tinh_trang=TINH_TRANG_MAP.get((d.get("effStatus") or {}).get("code", ""), "chua_xac_dinh"),
            depth=depth,
            nguon_url=f"vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/{doc_id}",
            checksum=checksum,
        ).model_dump(mode="json"))

        for row in prov_rows:
            row["document_id"] = doc_id
            provs.append(row)

        for ref in d.get("references") or []:
            tgt = ref.get("targetDocument") or {}
            refs.append({"from_document_id": doc_id,
                         "to_document_id": str(tgt.get("id")) if tgt.get("id") else None,
                         "loai": ref.get("referenceType") or 0,
                         "raw_text": tgt.get("docNum")})

    tep: list[str] = []
    for name, data in (("documents", docs), ("provisions", provs), ("references", refs)):
        (out / f"{name}.jsonl").write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in data) + "\n", encoding="utf-8")
        tep.append(f"{name}.jsonl")

    # `files` là mục để `ingest` KIỂM ĐƯỢC tính toàn vẹn của seed. Checksum theo
    # document băm HTML thô nên ingest không thể tính lại (data/raw gitignored);
    # checksum theo FILE thì tính lại được từ chính seed, và nó bắt luôn kênh
    # hỏng âm thầm: sửa `provisions.jsonl` mà không chạm `documents.jsonl` để lại
    # 21 checksum không đổi → ingest bỏ qua cả 21 → trả 0/0/0, không phân biệt
    # được với một lần re-run lành.
    # Băm TEXT đã đọc qua universal newline (không băm bytes thô) nên checkout
    # CRLF trên Windows không làm checksum lệch giả.
    (out / "checksums.json").write_text(json.dumps(
        {"documents": checksums,
         "files": {n: bam_tep(out / n) for n in tep}},
        indent=2, ensure_ascii=False), encoding="utf-8")

    for c in canh_bao_tong:
        warnings.warn(c, stacklevel=2)

    return {"documents": len(docs), "provisions": len(provs), "references": len(refs)}


if __name__ == "__main__":
    from src.config import get_settings

    s = get_settings()
    print(build(Path(s.data_raw_dir), Path(s.data_seed_dir)))
