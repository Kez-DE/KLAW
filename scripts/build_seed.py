"""Parse JSON thô → data/seed/*.jsonl (VÀO GIT)."""

import hashlib
import json
import warnings
from pathlib import Path

import pandas as pd

from scripts.fetch_chinhphu import VAN_BAN as VAN_BAN_CHINHPHU
from scripts.fetch_chinhphu import url_chi_tiet
from scripts.fetch_moj import DOC_IDS
from scripts.nap_linh_vuc import linh_vuc_tu_hang
from scripts.nap_nguoi_ky import nguoi_ky_tu_response
from src.models.domain import DocumentRow
from src.services.chinhphu_parser import sang_html_prov
from src.services.prov_parser import parse_anomalies, parse_provisions

TINH_TRANG_MAP = {
    "CHL": "CHL", "HHL": "HHL", "HHL1P": "HHL1P",
}


def _date(v: str | None) -> str | None:
    return v[:10] if v else None


def bam_tep(p: Path) -> str:
    """sha256 của một file seed. Dùng CHUNG với `scripts.ingest`."""
    return hashlib.sha256(p.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _soat_va_bam(html: str, so_ky_hieu: str, doc_id: str,
                 canh_bao_tong: list[str]) -> tuple[list[dict], str]:
    """Cổng cấu trúc + parse + checksum. DÙNG CHUNG cho mọi nguồn.

    Tách ra khỏi vòng lặp MOJ khi thêm nguồn `vanban.chinhphu.vn` (2026-09-02).
    Chép khối này cho nguồn thứ hai sẽ tạo ra hai cổng chất lượng trôi dạt khỏi
    nhau — nguồn mới là nguồn ÍT tin cậy hơn (không có class `prov-*`, cấp bậc
    suy từ nhãn), nên nó là nguồn CẦN cổng chặt hơn cả, không phải nguồn được
    miễn. Hành vi với đầu vào MOJ không đổi một bit: đã đối chiếu
    `data/seed/*.jsonl` trước/sau, md5 giữ nguyên.
    """
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
    return prov_rows, checksum


def _linh_vuc_theo_id(raw: Path) -> dict[str, str | None]:
    """`documents.id` (MOJ) → `linh_vuc`, đọc MỘT LẦN từ `metadata.parquet`.

    Đọc lúc SEED (ở đây), không lúc chạy: `metadata.parquet` không nằm trong
    git (`.gitignore:35`), nên API không thể đọc nó lúc phục vụ request. Thiếu
    file là LỖI cùng kiểu với thiếu `data/raw/moj/<doc_id>.json` — không đoán.
    """
    p = raw / "metadata.parquet"
    if not p.exists():
        raise FileNotFoundError(
            f"chưa có {p}; chạy `python -m scripts.download_data` trước")
    meta = pd.read_parquet(p, columns=["id", "nganh", "linh_vuc"])
    meta["id"] = meta["id"].astype(str)
    return {r.id: linh_vuc_tu_hang({"linh_vuc": r.linh_vuc, "nganh": r.nganh})
            for r in meta.itertuples(index=False)}


def build(raw: Path, out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    docs: list[dict] = []
    provs: list[dict] = []
    refs: list[dict] = []
    checksums: dict[str, str] = {}
    canh_bao_tong: list[str] = []
    linh_vuc_theo_id = _linh_vuc_theo_id(raw)

    for doc_id, (depth, so_ky_hieu) in DOC_IDS.items():
        p = raw / "moj" / f"{doc_id}.json"
        if not p.exists():
            raise FileNotFoundError(f"chưa fetch {doc_id}; chạy `python -m scripts.fetch_moj`")
        d = json.loads(p.read_text(encoding="utf-8"))
        # `so_ky_hieu` của `DOC_IDS` là chữ gõ tay; `docNum` là chữ CSDL quốc gia
        # khai cho CHÍNH id này. Lệch = id sai hoặc gõ sai (đo 2026-09-28: 53/53
        # khớp). Không lấy `docNum` đè lên: số hiệu nằm trong mọi `duong_dan`.
        if d.get("docNum") != so_ky_hieu:
            raise ValueError(
                f"doc {doc_id}: so_ky_hieu khai báo {so_ky_hieu!r} lệch docNum gateway "
                f"{d.get('docNum')!r} — id sai hoặc gõ sai, KHÔNG ghi seed")
        html = (d.get("documentContent") or {}).get("content") or ""
        if not html:
            raise ValueError(f"doc {doc_id} không có documentContent.content — không được bỏ qua im lặng")

        prov_rows, checksum = _soat_va_bam(html, so_ky_hieu, doc_id, canh_bao_tong)
        nguoi_ky, chuc_danh = nguoi_ky_tu_response(d)
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
            # `documentIssues[]` đã nằm trong response, chỉ chưa ai đọc. Xem
            # `scripts/nap_nguoi_ky` — module đó là CHỦ SỞ HỮU quy tắc trích
            # (lấy orderIndex nhỏ nhất, không chuẩn hoá hoa/thường, "" → None),
            # và nó cũng là đường nạp cho DB đã seed sẵn: thêm một cột metadata
            # không làm `checksum` đổi nên `ingest` sẽ bỏ qua mọi document.
            nguoi_ky=nguoi_ky, chuc_danh_nguoi_ky=chuc_danh,
            # Verbatim từ `metadata.parquet` (`linh_vuc`, rỗng thì `nganh`) —
            # xem `_linh_vuc_theo_id`/`scripts.nap_linh_vuc.linh_vuc_tu_hang`.
            # None khi id không có mặt trong metadata.parquet hoặc cả hai cột
            # đều rỗng ở đó — KHÔNG đoán.
            linh_vuc=linh_vuc_theo_id.get(doc_id),
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

    # ── Nguồn THỨ HAI: vanban.chinhphu.vn ──
    # Chỉ cho văn bản mà bản MOJ hỏng (xem `KHONG_NAP` ở scripts/fetch_moj.py và
    # docstring của src/services/chinhphu_parser.py). Đi qua ĐÚNG cổng
    # `_soat_va_bam` như nguồn MOJ — không có đường tắt cho nguồn yếu hơn.
    #
    # Không có `references`: trang Chính phủ không công bố quan hệ giữa các văn
    # bản. Đó là một THIẾU HỤT THẬT, không phải "rỗng" — văn bản nạp bằng đường
    # này sẽ không có cạnh nào trong `/van-ban/{id}/lien-quan`. Chấp nhận được
    # vì lựa chọn thay thế là không có văn bản nào cả.
    for docid, meta in VAN_BAN_CHINHPHU.items():
        p = raw / "chinhphu" / f"{docid}.html"
        if not p.exists():
            raise FileNotFoundError(
                f"chưa fetch chinhphu/{docid}; chạy `python -m scripts.fetch_chinhphu`")
        doc_id = f"cp-{docid}"
        html = sang_html_prov(p.read_text(encoding="utf-8"))
        prov_rows, checksum = _soat_va_bam(html, meta["so_ky_hieu"], doc_id, canh_bao_tong)
        checksums[doc_id] = checksum

        docs.append(DocumentRow(
            id=doc_id,
            so_ky_hieu=meta["so_ky_hieu"],
            loai_van_ban=meta["loai_van_ban"],
            ten=meta["ten"],
            co_quan_ban_hanh=meta["co_quan_ban_hanh"],
            ngay_ban_hanh=meta["ngay_ban_hanh"],
            ngay_hieu_luc=meta["ngay_hieu_luc"],
            ngay_het_hieu_luc=meta["ngay_het_hieu_luc"],
            tinh_trang=meta["tinh_trang"],
            # `documentIssues[]` là trường của API MOJ; trang Chính phủ không có
            # tương đương. None chứ không phải chuỗi rỗng — "không biết người
            # ký" khác "người ký là chuỗi rỗng".
            nguoi_ky=None, chuc_danh_nguoi_ky=None,
            # KHÔNG tra `metadata.parquet` bằng `docid` trần: id đó có thể
            # trùng một văn bản HOÀN TOÀN KHÁC trong dải id số của MOJ (đo
            # được: `162374` trong metadata.parquet là một Nghị quyết HĐND,
            # không phải Luật Khiếu nại của `docid` này) — tra nhầm gán sai
            # linh_vực còn hơn không gán. None ở đây là KHÔNG BIẾT thật.
            linh_vuc=None,
            depth=meta["depth"],
            nguon_url=url_chi_tiet(docid),
            checksum=checksum,
        ).model_dump(mode="json"))

        for row in prov_rows:
            row["document_id"] = doc_id
            provs.append(row)

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
