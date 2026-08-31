r"""Giải bản đồ sửa đổi cấp điều khoản từ văn bản hợp nhất (VBHN) của Công báo.

Nguồn: `congbao.chinhphu.vn` (Công báo điện tử) — điều khoản công bố chỉ yêu cầu
ghi rõ nguồn khi phát hành lại. VBHN phát hành `.docx` gốc, text thật, 0 ảnh
nhúng, nên không cần OCR và không cần LLM ở bất kỳ bước nào.

**VBHN KHÔNG thay thế corpus.** `PRODUCT.md` tuyên bố corpus là văn bản GỐC và hệ
thống bảo đảm nguồn gốc + đúng nguyên văn, KHÔNG bảo đảm là bản hiện hành. VBHN
là tài liệu tham khảo, không phải văn bản có hiệu lực pháp lý — thay
`provisions.noi_dung` bằng text hợp nhất là phá chính lời hứa đó. File này chỉ
rút ra QUAN HỆ SỬA ĐỔI; văn bản gốc vẫn là nguồn trích dẫn duy nhất.

── Ranh giới: cái nào là cấu trúc, cái nào là văn xuôi ──────────────────────

    Điều khoản BỊ sửa   ← vị trí neo `<w:footnoteReference>` trong OOXML
                          ✅ CẤU TRÚC. Máy đọc được, không suy diễn ngữ nghĩa.
    Văn bản ĐI sửa      ← chuỗi trong text footnote
    Ngày hiệu lực       ← chuỗi "có hiệu lực kể từ ngày …"
                          ⚠️ VĂN XUÔI theo khuôn mẫu (thể thức do NĐ 78/2025/NĐ-CP
                          quy định). Regex bắt được và ĐỐI CHIẾU CHÉO được với
                          `documents.so_ky_hieu`. Không khớp khuôn thì khai
                          `can_doi_chieu_tay` — không đoán.

Chữ "Khoản này" trong footnote là đại từ hồi chỉ: tự nó KHÔNG nói khoản nào.
Vị trí đến từ chỗ cái neo nằm, không đến từ câu chữ.

── Ba cạm bẫy đã sập trong khảo sát, cả ba sai ÂM THẦM ──────────────────────

1. `<w:t[^>]*>` khớp cả `<w:tab>`, cho ra "0 Điều" trên file có 220 Điều.
   → Không regex XML. Đi qua `xml.etree.ElementTree` (stdlib), hết bẫy.
2. Marker footnote dính liền số khoản: đoạn khoản 1 Điều 139 trích ra là
   `"1.4 Lao động nữ…"` — số 4 là marker. Đo được trên file thật: marker nằm ở
   một `<w:r>` RIÊNG, `vertAlign=superscript`, ngay TRƯỚC run mang
   `<w:footnoteReference>` (run đó không có `<w:t>` nào).
   → `_doan_sach` bỏ cả hai run.
3. ZIP của congbao có thể dùng `\` làm phân cách (`word\document.xml`).
   → `_doc_part` chuẩn hoá `\` → `/`.
"""

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import date
from io import BytesIO

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# ── Nhận diện cấp trong thân văn bản ─────────────────────────────────────────
# `\d+[a-zđ]?` chứ không `\d+`: luật sửa chèn khoản MỚI mang số hiệu có chữ
# ("8a" ở Điều 154). Ép về "8" là trỏ trích dẫn sang một khoản khác đã có sẵn.
_RE_DIEU = re.compile(r"^Điều\s+(\d+)\s*[.:]")
_RE_KHOAN = re.compile(r"^(\d+[a-zđ]?)\s*\.")
_RE_DIEM = re.compile(r"^([a-zđ]\d*)\s*\)")

# ── Khuôn ghi chú sửa đổi ────────────────────────────────────────────────────
# Đo trên `18/VBHN-VPQH` thật: "được sửa đổi, bổ sung" và "được bổ sung" đều có.
# Tiền tố `\d*` nuốt marker mà Word lặp lại ở đầu thân footnote ("4 Khoản này…").
_RE_LA_SUA_DOI = re.compile(
    r"^\s*\d*\s*(?:Điểm|Khoản|Điều|Mục|Tiểu mục|Chương|Phần|Phụ lục)\s+này\s+được\s+"
    r"(?:sửa đổi|bổ sung|bãi bỏ|thay thế|hủy bỏ)")

# Số ký hiệu VBQPPL: "113/2025/QH15", "21/2026/TT-BKHCN", "06/2003/PL-UBTVQH11".
# Bắt THẲNG hình dạng số hiệu thay vì `.+? số (\S+)`: tên văn bản có thể KẾT
# THÚC bằng chữ "số" ("Luật Công nghiệp công nghệ số" + " số 71/2025/QH15"),
# và một regex dựa vào chữ "số" làm mốc sẽ cắt sai ở đúng ca đó.
_RE_SO_KY_HIEU = re.compile(r"\b(\d+/\d{4}/[A-ZĐ][A-ZĐ0-9/-]*)")

# "theo quy định tại điểm a khoản 1 Điều 43 của Luật …" — phần trước chữ "của"
# là đường dẫn trong văn bản ĐI SỬA.
_RE_VI_TRI_NGUON = re.compile(r"theo quy định tại\s+(.+?)\s+của\s")
_RE_NGAY = re.compile(
    r"có hiệu lực(?:\s+thi hành)?\s+kể từ ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})")


@dataclass(frozen=True)
class SuaDoi:
    """Một điểm sửa đổi. `vi_tri` TƯƠNG ĐỐI (chưa có tiền tố số ký hiệu) vì
    parser không biết — và không được đoán — VBHN này hợp nhất văn bản nào."""

    vi_tri: str                        # "Điều 139 > Khoản 1"
    sua_boi_so_ky_hieu: str | None
    sua_boi_duong_dan: str | None      # "khoản 1 Điều 29"
    tu_ngay: date | None
    do_tin_cay: str                    # trung_binh | can_doi_chieu_tay
    ghi_chu: str                       # nguyên văn footnote
    fn_id: str


def _doc_part(z: zipfile.ZipFile, ten: str) -> ET.Element | None:
    """Cạm bẫy 3: một số `.docx` của congbao ghi `word\\document.xml`."""
    thuc = {n.replace("\\", "/"): n for n in z.namelist()}
    goc = thuc.get(ten)
    return ET.fromstring(z.read(goc)) if goc else None


def _doan_sach(p: ET.Element) -> str:
    """Text của một `<w:p>`, ĐÃ GỠ marker footnote (cạm bẫy 2).

    Bỏ run mang `<w:footnoteReference>` và run superscript-toàn-số ngay trước
    nó. `<w:tab>`/`<w:br>` thành khoảng trắng chứ không biến mất, để
    `"Điều 7." + <tab> + "Trách nhiệm"` không dính thành `"Điều 7.Trách nhiệm"`.
    """
    runs = list(p.iter(f"{W}r"))
    bo: set[int] = set()
    for i, r in enumerate(runs):
        if r.find(f"{W}footnoteReference") is None:
            continue
        bo.add(i)
        truoc = runs[i - 1] if i else None
        if truoc is not None and truoc.find(f"{W}rPr/{W}vertAlign") is not None:
            if "".join(t.text or "" for t in truoc.iter(f"{W}t")).strip().isdigit():
                bo.add(i - 1)

    ra: list[str] = []
    for i, r in enumerate(runs):
        if i in bo:
            continue
        for n in r.iter():
            if n.tag == f"{W}t":
                ra.append(n.text or "")
            elif n.tag in (f"{W}tab", f"{W}br", f"{W}cr"):
                ra.append(" ")
    return " ".join("".join(ra).split())


def _text_footnotes(root: ET.Element | None) -> dict[str, str]:
    if root is None:
        return {}
    return {
        f.get(f"{W}id") or "": " ".join(
            " ".join(_doan_sach(p) for p in f.iter(f"{W}p")).split())
        for f in root.iter(f"{W}footnote")
    }


def _phan_tich_footnote(txt: str) -> tuple[str | None, str | None, date | None, str]:
    """`(so_ky_hieu, duong_dan_nguon, tu_ngay, do_tin_cay)` từ text footnote.

    Đòi ĐỦ CẢ BA (số hiệu + đường dẫn + ngày) mới nhận `trung_binh`. Thiếu một
    phần là khuôn đã lệch, và một bản ghi nửa vời — "bị sửa bởi 113/2025/QH15
    từ ngày ???" — mời người đọc tự điền nốt phần thiếu bằng phỏng đoán.
    """
    sk = _RE_SO_KY_HIEU.search(txt)
    vt = _RE_VI_TRI_NGUON.search(txt)
    ng = _RE_NGAY.search(txt)
    if not (sk and vt and ng):
        return None, None, None, "can_doi_chieu_tay"
    d, m, y = (int(g) for g in ng.groups())
    try:
        ngay = date(y, m, d)
    except ValueError:
        return None, None, None, "can_doi_chieu_tay"
    return sk.group(1), vt.group(1), ngay, "trung_binh"


def doc_sua_doi(docx: bytes) -> list[SuaDoi]:
    """Đọc `.docx` VBHN → danh sách điểm sửa đổi, theo thứ tự xuất hiện.

    Footnote KHÔNG phải ghi chú sửa đổi bị bỏ hẳn, không phải hạ xuống
    `can_doi_chieu_tay`: VBHN thật có 6 footnote mà chỉ 4 là ghi chú sửa đổi
    (một ghi "căn cứ ban hành", một trích nguyên Điều hiệu lực thi hành). Gộp
    "không phải sửa đổi" với "sửa đổi nhưng chưa đọc được" là tự tạo ra một
    hàng đợi đối chiếu tay không có thật.

    Neo không rơi vào cấp điều khoản nào (lời mở đầu, tiêu đề Chương, đoạn nối
    trong lòng khoản) cũng bị bỏ: không có vị trí thì bịa vị trí là bịa trích dẫn.
    """
    z = zipfile.ZipFile(BytesIO(docx))
    body = _doc_part(z, "word/document.xml")
    if body is None:
        raise ValueError("`.docx` không có word/document.xml — không phải OOXML hợp lệ")
    chu_thich = _text_footnotes(_doc_part(z, "word/footnotes.xml"))

    ra: list[SuaDoi] = []
    dieu = khoan = None
    for p in body.iter(f"{W}p"):
        txt = _doan_sach(p)
        # Cập nhật cấp ĐANG MỞ trước khi xét neo: neo ở cấp Điểm cần Khoản và
        # Điều của chính đoạn đứng trên nó.
        if m := _RE_DIEU.match(txt):
            dieu, khoan = m.group(1), None
        elif m := _RE_KHOAN.match(txt):
            khoan = m.group(1)

        for r in p.iter(f"{W}footnoteReference"):
            fid = r.get(f"{W}id") or ""
            txt_fn = chu_thich.get(fid, "")
            if not _RE_LA_SUA_DOI.match(txt_fn):
                continue
            if (vi_tri := _vi_tri(txt, dieu, khoan)) is None:
                continue
            sk, dd, ngay, tc = _phan_tich_footnote(txt_fn)
            ra.append(SuaDoi(vi_tri, sk, dd, ngay, tc, txt_fn, fid))
    return ra


def _vi_tri(txt: str, dieu: str | None, khoan: str | None) -> str | None:
    """Vị trí của đoạn mang neo, suy từ TIỀN TỐ của chính nó cộng cấp đang mở."""
    if dieu is None:
        return None
    if _RE_DIEU.match(txt):
        return f"Điều {dieu}"
    if m := _RE_KHOAN.match(txt):
        return f"Điều {dieu} > Khoản {m.group(1)}"
    if (m := _RE_DIEM.match(txt)) and khoan is not None:
        return f"Điều {dieu} > Khoản {khoan} > Điểm {m.group(1)}"
    return None
