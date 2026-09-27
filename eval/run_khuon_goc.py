"""Thước đo khuôn gốc — P6 của `docs/plans/active/khuon-goc-dien-tai-cho.md`
(quyết định `2026-09-26-luu-khuon-goc-va-dien-tai-cho`).

    python -m eval.run_khuon_goc [--bo PATH ...] [--out PATH] [--word]

KHÔNG gọi mô hình, KHÔNG ra mạng. Mọi phép đo đi qua ĐÚNG đường của sản phẩm:
`doc_tai_lieu.doc` đọc, `dung_trang.khuon_goc` đếm trang như `POST /tai-lieu`,
`ban_thao.cho_trong_khuon` liệt kê ô điền như bảng ô điền, `chuan_hoa_dien` chuẩn
hoá giá trị, `dien_khuon.ap_dung_docx` / `dien_khuon_pdf.ap_dung_pdf` áp. Với mỗi
`.docx` trong `--bo` (mặc định: kho mẫu của chủ dự án, không bao giờ commit):

1. Số trang THẬT (LibreOffice, như lúc tải lên); `--word`: số trang Word.
2. Khứ hồi: danh sách phép rỗng trả đúng bytes vào, và bản dựng trùng từng điểm
   ảnh với bản dựng của tệp gốc. `ap_dung_docx([])` trả CHÍNH bytes vào, nên
   phép này không thể trượt (`rong_la_dong_nhat`) và không chạm bộ ghi.
3. Điền MỌI ô điền được bằng bốn giá trị mẫu xoay vòng: áp/bỏ theo lý do, số
   trang trước/sau, trang không mang giá trị nào phải trùng từng điểm ảnh, mục
   zip ngoài part đã sửa giữ nguyên nội dung (`muc_zip_doi`, qua `_dong_goi`),
   mọi giá trị phải có trong `pdftotext`; `--word`: Word mở được và xuất PDF.
4. `--word`: LibreOffice so với Word trên tệp GỐC, từng trang ở 72 dpi xám.
5. Đường PDF: bản LibreOffice dựng đọc lại như một PDF số, và bản scan chỉ-ảnh
   (200 dpi) đọc bằng OCR — số ô tìm được, điểm ảnh đổi ngoài hộp tô trắng, giá
   trị trong `pdftotext`.
6. Chỗ `o` (ô rỗng của bảng có viền, G5) đo RIÊNG (`do_o`), nên mục 3 và 5 vẫn là
   đúng phép đo của kiểu chấm/tab: số ô mỗi tệp, áp/bỏ, số trang sau khi điền mọi
   ô, và đọc lại tệp ra đúng giá trị ở đúng đơn vị.

Cộng một ca tổng hợp: tệp 11 trang bị phép đếm lúc tải lên TỪ CHỐI, không cắt.

Mấy số dễ đọc nhầm, ghi rõ ở đây:

* `ti_le_so_voi_docx` của đường PDF là TỈ LỆ SỐ Ô (PDF / docx), không phải một
  phép khớp một-một: hai bộ đọc không chung khoá nào (nhãn PDF rỗng khi nhãn
  nằm ở ô khác), và nó có thể vượt 1. Tổng của nó để ô tìm thừa ở một tệp che
  ô thiếu ở tệp khác; `cho_toi_da_khop` (mỗi tệp tính tối đa số ô docx) là trần
  của độ phủ, `cho_thua` là phần thừa.
* Tệp không điền/vẽ được ô nào trả đúng bytes vào: mọi phép "không đổi" đạt
  hiển nhiên. Tổng hợp liệt kê chúng ở `khong_dien_gi` và bỏ khỏi mẫu số.
* Mẫu số Word là mọi tệp Word đã chạy: một lỗi là trượt, chỉ `blocked` ra ngoài.
* `giong_diem_anh` LibreOffice–Word bị nền trắng chi phối: hai trang lệch hết
  chữ vẫn ra trên 90 %. `iou_muc` (giao/hợp của điểm ảnh có mực, xám < 160) là
  số nói thật về chữ; báo cả hai.

Word chạy qua `scripts/kiem_mo_bang_word.py` (osascript, trần 90 s mỗi tệp). Một
lượt treo (hết giờ AppleScript -1712 hay trần subprocess) hay thiếu quyền
Automation (-1743) thì phần Word của mọi tệp sau ghi
`blocked` — không chờ thêm, không giết tiến trình nào của người dùng.
"""

import argparse
import json
import logging
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path

import numpy as np

from eval.run_trung_thuc import _commit_hash, _tim_tep
from scripts.kiem_mo_bang_word import _THU_MUC_WORD, anh_xam, chu_trang, mo_bang_word, so_trang
from src.services import dung_trang
from src.services import tai_lieu as tl
from src.services.ban_thao import cho_trong_khuon, chuan_hoa_dien
from src.services.dien_khuon import ap_dung_docx
from src.services.dien_khuon_pdf import ap_dung_pdf
from src.services.doc_tai_lieu import TaiLieuDaDoc, co_ocr, doc

_REPO_ROOT = Path(__file__).resolve().parents[1]
_KHO_MAC_DINH = Path.home() / "giấy tờ thực tập"

GIA_TRI = ("Nguyễn Văn Ánh", "0912 345 678", "01/10/2026", "Công ty TNHH Luật Việt")
CHAN = "blocked"
# 72 dpi: một điểm ảnh là một điểm PDF, nên hộp `hop` (điểm) là toạ độ điểm ảnh.
_DPI = 72
_DPI_SCAN = 200
_NGUONG_MUC = 160
_GIAN_HOP = 1.0

_CT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/></Relationships>'
)


def docx_mau(than: str) -> bytes:
    """`.docx` A4 tối thiểu mà LibreOffice mở được; `than` là XML các `w:p`."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body>{than}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>',
        )
    return buf.getvalue()


# ─────────────────────────────────────────────────────────── chấm (thuần)


def phep_dien(o_dien: list[dict]) -> list[dict]:
    """Một `dien` cho MỖI ô điền được, giá trị xoay vòng `GIA_TRI`, chuẩn hoá như
    bảng ô điền lưu (`chuan_hoa_dien`: ô `tab` nhận một dấu cách đầu)."""
    return [
        {
            "loai": "dien",
            "don_vi": o["don_vi"],
            "cho_trong": o["so"],
            "gia_tri": chuan_hoa_dien(GIA_TRI[i % len(GIA_TRI)], o),
        }
        for i, o in enumerate(o_dien)
    ]


def dem_ly_do(bao_cao: dict) -> dict[str, int]:
    return dict(Counter(b["ly_do"] for b in bao_cao["bo_qua"]))


_CHAM = str.maketrans("", "", "._…")


def _gon(s: str, bo_cham: bool = False) -> str:
    s = "".join(s.split())
    return s.translate(_CHAM) if bo_cham else s


def dem_gia_tri(chu_truoc: list[str], chu_sau: list[str], gia_tri: list[str], bo_cham: bool = False) -> tuple[int, int]:
    """`(tìm thấy, cần)`: mỗi giá trị đã áp phải xuất hiện thêm trong chữ bản sau.

    So sau khi bỏ khoảng trắng — một ô hẹp ngắt "01/10/2026" thành "01/ 10/ 202
    6". Lần xuất hiện đã có trong bản gốc không tính; tìm thừa một giá trị không
    bù chỗ thiếu của giá trị khác.

    `bo_cham`: bỏ thêm ký tự dẫn (`.`, `_`, `…`). Lớp phủ PDF CHE dãy chấm mà
    không xoá nó khỏi lớp chữ (`dien_khuon_pdf`), nên `pdftotext` có thể xen
    chấm bị che vào giữa giá trị ("Công ty TNHH ……… Luật Việt"): số đếm thường
    đo "tìm/chép được nguyên giá trị", số `bo_cham` đo "giá trị có vẽ ra"."""
    can = Counter(_gon(v, bo_cham) for v in gia_tri)
    truoc, sau = _gon("\f".join(chu_truoc), bo_cham), _gon("\f".join(chu_sau), bo_cham)
    return sum(min(max(sau.count(v) - truoc.count(v), 0), n) for v, n in can.items()), sum(can.values())


def trang_giong(a: list[np.ndarray], b: list[np.ndarray]) -> bool:
    return len(a) == len(b) and all(x.shape == y.shape and np.array_equal(x, y) for x, y in zip(a, b, strict=False))


def trang_khong_dien(a: list[np.ndarray], b: list[np.ndarray], chu_sau: list[str], gia_tri: list[str]) -> dict | None:
    """Trang của bản đã điền KHÔNG mang giá trị nào phải trùng từng điểm ảnh.

    Trang một chỗ trống rơi vào đọc từ CHÍNH bản dựng (`pdftotext`), không từ
    `trang` của bộ đọc: với docx, `trang` chỉ đếm ngắt khai báo (Evaluation Form
    4 trang thật đọc ra 1). `None` khi số trang đổi — so từng trang hết nghĩa."""
    if not len(a) == len(b) == len(chu_sau):
        return None
    v = [_gon(x) for x in gia_tri]
    khong = [i for i, t in enumerate(chu_sau, start=1) if not any(x in _gon(t) for x in v)]
    doi = [i for i in khong if not trang_giong([a[i - 1]], [b[i - 1]])]
    return {"trang": len(khong), "giong": len(khong) - len(doi), "doi_khong_gia_tri": doi}


def _can_kho(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Hai trang về cùng khổ: đệm nền trắng ở phải/dưới tới khổ lớn hơn."""
    h, w = max(a.shape[0], b.shape[0]), max(a.shape[1], b.shape[1])

    def _dem(x: np.ndarray) -> np.ndarray:
        return np.pad(x, ((0, h - x.shape[0]), (0, w - x.shape[1])), constant_values=255)

    return _dem(a), _dem(b)


def ti_le_giong(a: np.ndarray, b: np.ndarray) -> float:
    x, y = _can_kho(a, b)
    return float((x == y).mean())


def iou_muc(a: np.ndarray, b: np.ndarray) -> float | None:
    """Giao/hợp của điểm ảnh có mực; `None` khi cả hai trang trắng."""
    x, y = _can_kho(a, b)
    x, y = x < _NGUONG_MUC, y < _NGUONG_MUC
    hop = (x | y).sum()
    return float((x & y).sum() / hop) if hop else None


def doi_ngoai_hop(a: np.ndarray, b: np.ndarray, hops: list[list[float]]) -> tuple[int, int]:
    """`(điểm ảnh đổi, điểm ảnh đổi NGOÀI mọi hộp)` của một trang 72 dpi.

    Hộp giãn `_GIAN_HOP` pt — hợp đồng cho ô tô trắng tràn khỏi hộp tối đa 1 pt;
    điểm ảnh chạm mép (khử răng cưa) tính là trong."""
    doi = a != b
    duoc = np.zeros(a.shape, dtype=bool)
    for x0, y0, x1, y1 in hops:
        g = _GIAN_HOP
        duoc[
            max(0, int(np.floor(y0 - g))) : int(np.ceil(y1 + g)), max(0, int(np.floor(x0 - g))) : int(np.ceil(x1 + g))
        ] = True
    return int(doi.sum()), int((doi & ~duoc).sum())


def muc_zip_doi(goc: bytes, moi: bytes, sua: set[str]) -> list[str]:
    """Mục zip ngoài `sua` (part bộ áp sửa) mà nội dung giải nén đổi, thêm hay mất.

    Đây là phép đi qua `_dong_goi`: mục không sửa được viết lại từ luồng giải nén,
    nên chúng phải ra cùng nội dung — `[]` là đạt."""
    with zipfile.ZipFile(BytesIO(goc)) as a, zipfile.ZipFile(BytesIO(moi)) as b:
        ta, tb = set(a.namelist()), set(b.namelist())
        return sorted(t for t in (ta | tb) - sua if t not in ta or t not in tb or a.read(t) != b.read(t))


# ─────────────────────────────────────────────────────────── công cụ


def _hang(tai_lieu: TaiLieuDaDoc) -> list[dict]:
    """Đúng mảng `viec_doc_tai_lieu.don_vi` lưu (jsonb: không tuple)."""
    return json.loads(json.dumps([tl._hang_don_vi(d) for d in tai_lieu.don_vi], ensure_ascii=False))


def _anh(pdf: bytes) -> list[np.ndarray]:
    """Ảnh xám 72 dpi từng trang. Thiếu trang là lỗi: hai danh sách rỗng "trùng
    từng điểm ảnh" là một phép đo giả."""
    anh = anh_xam(pdf, _DPI)
    if len(anh) != so_trang(pdf):
        raise RuntimeError(f"pdftoppm dựng {len(anh)}/{so_trang(pdf)} trang")
    return anh


def _scan(pdf: bytes) -> bytes:
    """PDF CHỈ có ảnh: `pdftoppm` 200 dpi, mỗi trang một ảnh, không lớp chữ."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["pdftoppm", "-r", str(_DPI_SCAN), "-png", "-", f"{tmp}/p"],
            input=pdf,
            check=True,
            capture_output=True,
            timeout=120,
        )
        c = canvas.Canvas(buf)
        for tep in sorted(Path(tmp).glob("p-*.png")):
            im = ImageReader(str(tep))
            w, h = (x * 72 / _DPI_SCAN for x in im.getSize())
            c.setPageSize((w, h))
            c.drawImage(im, 0, 0, w, h)
            c.showPage()
        c.save()
    return buf.getvalue()


class _Word:
    """Word qua `osascript`, tệp tạm trong hộp cát của Word (không hộp thoại quyền
    tệp). Lượt treo hay bị từ chối Automation chặn mọi lượt sau."""

    def __init__(self, thu_muc: Path) -> None:
        self.thu_muc, self.chan, self._n = thu_muc, None, 0

    def pdf(self, docx: bytes) -> bytes | str:
        """PDF Word xuất, `CHAN`, hoặc lỗi nguyên văn của đúng tệp này."""
        if self.chan:
            return CHAN
        self._n += 1
        vao, ra = self.thu_muc / f"t{self._n}.docx", self.thu_muc / f"t{self._n}.pdf"
        vao.write_bytes(docx)
        loi = mo_bang_word(vao, ra)
        # `mo_bang_word` báo treo bằng "treo quá"; -1712 là "AppleEvent timed
        # out" — `with timeout of 85 seconds` của kịch bản ném nó TRƯỚC trần 90 s,
        # nên Word đứng vì hộp thoại hiện ra ở đây; -1743 là "Not authorized to
        # send Apple events". Cả ba đúng cho MỌI tệp sau, không phải tệp này.
        if loi and ("treo quá" in loi or "-1712" in loi or "-1743" in loi):
            self.chan = loi
            return CHAN
        return f"lỗi: {loi}" if loi else ra.read_bytes()


def _so_trang_word(x: bytes | str) -> int | str:
    return x if isinstance(x, str) else so_trang(x)


# ─────────────────────────────────────────────────────────── đo


def _do_pdf(ten: str, pdf: bytes, so_cho_docx: int) -> dict:
    """Đường PDF trên một bản PDF của biểu mẫu (số hay scan)."""
    hang = _hang(doc(ten, pdf))
    o = cho_trong_khuon("pdf", hang, [])
    phep = phep_dien(o)
    moi, bao_cao = ap_dung_pdf(pdf, hang, phep)
    vi_tri = {(d["chi_so"], c["so"]): (d["trang"], c) for d in hang for c in d.get("cho_trong", []) if c.get("hop")}
    hop: dict[int, list] = {}
    dai: dict[int, list] = {}
    for i in bao_cao["da_ap"]:
        t, c = vi_tri[(phep[i]["don_vi"], phep[i]["cho_trong"])]
        (x0, y0, x1, y1), co = c["hop"], c["co_chu"]
        hop.setdefault(t, []).append(c["hop"])
        # Dải chữ: trên một dải CHỈ có chấm (scan) bộ áp đặt chữ ngồi TRÊN đường
        # chấm, ngoài hộp tô trắng — đúng thiết kế; cùng biên mà test BM.M05 scan
        # của `test_dien_khuon_pdf` cho phép.
        dai.setdefault(t, []).append([x0, min(y0, y1 - 1.2 * co), x1, max(y1, y1 + 0.3 * co)])
    a, b = _anh(pdf), _anh(moi)
    giu = len(a) == len(b)
    cap = list(enumerate(zip(a, b, strict=False), start=1)) if giu else []
    doi = [doi_ngoai_hop(x, y, hop.get(t, [])) for t, (x, y) in cap]
    ngoai_dai = [doi_ngoai_hop(x, y, dai.get(t, []))[1] for t, (x, y) in cap]
    chu_truoc, chu_sau = chu_trang(pdf), chu_trang(moi)
    gia_tri = [phep[i]["gia_tri"] for i in bao_cao["da_ap"]]
    return {
        "so_cho": len(o),
        "so_cho_docx": so_cho_docx,
        "ti_le_so_voi_docx": round(len(o) / so_cho_docx, 4) if so_cho_docx else None,
        "da_ap": len(bao_cao["da_ap"]),
        "bo_qua": dem_ly_do(bao_cao),
        "so_trang_giu": giu,
        "diem_anh_doi": sum(x for x, _ in doi) if giu else None,
        "diem_anh_ngoai_hop": sum(y for _, y in doi) if giu else None,
        "trang_doi_ngoai_hop": [t for t, (_, y) in enumerate(doi, start=1) if y],
        "diem_anh_ngoai_dai_chu": sum(ngoai_dai) if giu else None,
        "gia_tri": list(dem_gia_tri(chu_truoc, chu_sau, gia_tri)),
        "gia_tri_bo_cham": list(dem_gia_tri(chu_truoc, chu_sau, gia_tri, bo_cham=True)),
    }


def _thu(ham, *args) -> dict:
    """Một nhánh đo hỏng không xoá các nhánh khác của cùng tệp."""
    try:
        return ham(*args)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# Giá trị ngắn có chữ số cho MỌI ô `o`: ô hẹp («STT» 33 pt) ngắt một giá trị dài
# thành nhiều dòng, và cột «Mã …»/«STT» chỉ nhận giá trị có chữ số.
GIA_TRI_O = "12"


def do_o(ten: str, du_lieu: bytes, hang: list[dict], o: list[dict], so_trang: int) -> dict:
    """Điền MỌI chỗ `o` bằng `GIA_TRI_O`: áp/bỏ theo lý do, số trang sau (LibreOffice),
    và đọc lại tệp — đúng giá trị trong đúng đơn vị (không qua `pdftotext`, vốn đọc
    bảng theo dòng và xen chữ các ô)."""
    if not o:
        return {"so_cho": 0}
    phep = [{"loai": "dien", "don_vi": x["don_vi"], "cho_trong": x["so"], "gia_tri": GIA_TRI_O} for x in o]
    moi, bao_cao = ap_dung_docx(du_lieu, hang, phep)
    doc_lai = {d.chi_so: d.noi_dung for d in doc(ten, moi).don_vi}
    return {
        "so_cho": len(o),
        "da_ap": len(bao_cao["da_ap"]),
        "bo_qua": dem_ly_do(bao_cao),
        "so_trang_truoc": so_trang,
        "so_trang_sau": dung_trang.so_trang_pdf(dung_trang.dung_pdf(moi)),
        "doc_lai_dung": _cap(phep, lambda p: doc_lai.get(p["don_vi"]) == GIA_TRI_O),
    }


def do_tep(ten: str, du_lieu: bytes, word: _Word | None) -> dict:
    tai_lieu = doc(ten, du_lieu)
    hang = _hang(tai_lieu)
    so_lo = dung_trang.khuon_goc(ten, du_lieu, tai_lieu).so_trang
    pdf_goc = dung_trang.dung_pdf(du_lieu)
    anh_goc, chu_goc = _anh(pdf_goc), chu_trang(pdf_goc)
    ket: dict = {"tep": ten, "so_trang": {"lo": so_lo}}

    cung, _ = ap_dung_docx(du_lieu, hang, [])
    ket["khu_hoi"] = {
        "bytes_giong": cung == du_lieu,
        "trang_giong": trang_giong(anh_goc, _anh(dung_trang.dung_pdf(cung))),
    }

    word_goc = word.pdf(du_lieu) if word else None
    if word:
        ket["so_trang"]["word"] = _so_trang_word(word_goc)
    if isinstance(word_goc, bytes):
        anh_w = _anh(word_goc)
        ket["lo_word"] = {
            "trung_so_trang": len(anh_w) == len(anh_goc),
            "giong_diem_anh": [round(ti_le_giong(x, y), 4) for x, y in zip(anh_goc, anh_w, strict=False)],
            "iou_muc": [
                None if (v := iou_muc(x, y)) is None else round(v, 4) for x, y in zip(anh_goc, anh_w, strict=False)
            ],
        }

    tat_ca = cho_trong_khuon("docx", hang, [])
    # Chỗ `o` (ô rỗng của bảng, G5) đo RIÊNG (`do_o`): số của các kiểu chấm/tab giữ
    # nguyên phép đo cũ, và đường PDF (chỉ tìm dãy chấm) so với đúng các kiểu đó.
    o = [x for x in tat_ca if x["kieu"] != "o"]
    ket["o_bang"] = do_o(ten, du_lieu, hang, [x for x in tat_ca if x["kieu"] == "o"], so_lo)
    phep = phep_dien(o)
    moi, bao_cao = ap_dung_docx(du_lieu, hang, phep)
    da_ap = [phep[i]["gia_tri"] for i in bao_cao["da_ap"]]
    phan = {h["chi_so"]: h["dia_chi"]["phan"] for h in hang if h.get("dia_chi")}
    pdf_moi = dung_trang.dung_pdf(moi)
    anh_moi, chu_moi = _anh(pdf_moi), chu_trang(pdf_moi)
    d = {
        "so_cho": len(o),
        "da_ap": len(bao_cao["da_ap"]),
        "bo_qua": dem_ly_do(bao_cao),
        "so_trang_truoc": so_lo,
        "so_trang_sau": len(anh_moi),
        "trang_khong_dien": trang_khong_dien(anh_goc, anh_moi, chu_moi, da_ap),
        "gia_tri": list(dem_gia_tri(chu_goc, chu_moi, da_ap)),
        "muc_zip_doi": muc_zip_doi(du_lieu, moi, {phan[phep[i]["don_vi"]] for i in bao_cao["da_ap"]}),
    }
    if word:
        word_moi = word.pdf(moi)
        d["word_mo"] = True if isinstance(word_moi, bytes) else word_moi
        d["so_trang_word_sau"] = _so_trang_word(word_moi)
        if isinstance(word_goc, bytes) and isinstance(word_moi, bytes):
            d["gia_tri_word"] = list(dem_gia_tri(chu_trang(word_goc), chu_trang(word_moi), da_ap))
    ket["dien"] = d

    ket["pdf"] = {
        "so": _thu(_do_pdf, "so.pdf", pdf_goc, len(o)),
        "scan": _thu(lambda: _do_pdf("scan.pdf", _scan(pdf_goc), len(o))) if co_ocr() else "không có tesseract",
    }
    return ket


def tu_choi_11_trang() -> dict:
    """Tệp tổng hợp 10 ngắt trang (11 trang) qua đúng hai bước của `POST
    /tai-lieu`: đếm bằng `dung_trang.khuon_goc`, rồi `tai_lieu.kiem_so_trang`.
    Kèm biên 10 trang phải được nhận. `so_trang_dem` 11 (không phải 10) là bằng
    chứng tài liệu bị từ chối nguyên vẹn chứ không bị cắt về trần."""

    def _dem(ngat: int) -> tuple[int, str | None]:
        du_lieu = docx_mau(
            "<w:p><w:r><w:t>Trang 1</w:t></w:r></w:p>"
            + '<w:p><w:r><w:br w:type="page"/><w:t>Trang sau</w:t></w:r></w:p>' * ngat
        )
        so = dung_trang.khuon_goc("x.docx", du_lieu, doc("x.docx", du_lieu)).so_trang
        try:
            tl.kiem_so_trang(so)
        except tl.VuotTran as e:
            return so, f"vuot_tran_{e.tran}"  # đúng `ly_do_hong` route ghi
        return so, None

    so, ly_do = _dem(10)
    so_bien, ly_do_bien = _dem(9)
    return {
        "so_trang_dem": so,
        "tu_choi": ly_do is not None,
        "ly_do": ly_do,
        "bien_10_trang_nhan": so_bien == 10 and ly_do_bien is None,
    }


# ─────────────────────────────────────────────────────────── tổng hợp


def _cap(ds: list, dk) -> list[int]:
    return [sum(1 for x in ds if dk(x)), len(ds)]


def _cong(ds: list[list[int]]) -> list[int]:
    return [sum(x[0] for x in ds), sum(x[1] for x in ds)]


def _chay_word(v: object) -> bool:
    """Word đã chạy trên tệp này (được bật, không bị chặn) — kết quả lỗi vẫn tính."""
    return v is not None and v != CHAN


def _tong_pdf(ok: list[dict], nhanh: str) -> dict | None:
    p = [
        {**c["pdf"][nhanh], "tep": c["tep"]}
        for c in ok
        if isinstance(c["pdf"][nhanh], dict) and "error" not in c["pdf"][nhanh]
    ]
    if not p:
        return None
    bo_qua: Counter = Counter()
    for x in p:
        bo_qua.update(x["bo_qua"])
    cho, docx = sum(x["so_cho"] for x in p), sum(x["so_cho_docx"] for x in p)
    # Tệp không vẽ gì trả đúng PDF vào: "không đổi ngoài hộp" đạt hiển nhiên.
    co_ap = [x for x in p if x["da_ap"] > 0]
    return {
        "so_cho": cho,
        "so_cho_docx": docx,
        "ti_le_so_voi_docx": round(cho / docx, 4) if docx else None,
        # Trần của độ phủ: mỗi tệp tính tối đa số ô docx của nó, để ô tìm thừa ở
        # tệp này không che ô thiếu ở tệp khác.
        "cho_toi_da_khop": [sum(min(x["so_cho"], x["so_cho_docx"]) for x in p), docx],
        "cho_thua": sum(max(0, x["so_cho"] - x["so_cho_docx"]) for x in p),
        "da_ap": sum(x["da_ap"] for x in p),
        "bo_qua": dict(bo_qua),
        "khong_dien_gi": [x["tep"] for x in p if x["da_ap"] == 0],
        "tep_khong_doi_ngoai_hop": _cap(co_ap, lambda x: x["diem_anh_ngoai_hop"] == 0),
        "tep_khong_doi_ngoai_dai_chu": _cap(co_ap, lambda x: x["diem_anh_ngoai_dai_chu"] == 0),
        "gia_tri": _cong([x["gia_tri"] for x in p]),
        "gia_tri_bo_cham": _cong([x["gia_tri_bo_cham"] for x in p]),
        "loi": sum(1 for c in ok if isinstance(c["pdf"][nhanh], dict) and "error" in c["pdf"][nhanh]),
    }


def tong_hop(chi_tiet: list[dict]) -> dict:
    ok = [c for c in chi_tiet if "error" not in c]
    dien = [c["dien"] for c in ok]
    bo_qua: Counter = Counter()
    for d in dien:
        bo_qua.update(d["bo_qua"])
    # Mẫu số Word: mọi tệp Word ĐÃ chạy — một lỗi là trượt, chỉ `blocked` ra ngoài.
    co_word = [c for c in ok if _chay_word(c["so_trang"].get("word"))]
    # Tệp không điền được ô nào trả CHÍNH bytes vào (`ap_dung_docx([])`): mọi phép
    # "không đổi" đạt hiển nhiên, nên liệt kê riêng, không cộng vào mẫu số.
    co_dien = [c for c in ok if c["dien"]["da_ap"] > 0]
    dien_word = [
        c for c in co_dien if _chay_word(c["so_trang"].get("word")) and _chay_word(c["dien"].get("so_trang_word_sau"))
    ]
    tkd = [c["dien"]["trang_khong_dien"] for c in co_dien if c["dien"]["trang_khong_dien"]]
    lw = [c["lo_word"] for c in ok if "lo_word" in c]
    co_o = [c for c in ok if c["o_bang"]["so_cho"]]
    giong = [v for x in lw for v in x["giong_diem_anh"]]
    iou = [v for x in lw for v in x["iou_muc"] if v is not None]
    return {
        "so_tep": len(chi_tiet),
        "loi": len(chi_tiet) - len(ok),
        "khong_dien_gi": [c["tep"] for c in ok if c["dien"]["da_ap"] == 0],
        "word_loi": sum(
            1
            for c in ok
            if any(isinstance(v, str) and v != CHAN for v in (c["so_trang"].get("word"), c["dien"].get("word_mo")))
        ),
        "so_trang_lo": {c["tep"]: c["so_trang"]["lo"] for c in ok},
        "so_trang_lo_bang_word": _cap(co_word, lambda c: c["so_trang"]["lo"] == c["so_trang"]["word"]),
        # Danh sách phép rỗng trả đúng bytes vào (`ap_dung_docx`) — phép này KHÔNG
        # thể trượt, không phải bằng chứng cho bộ ghi; `dien.zip_giu_muc_khac` và
        # `dien.trang_khong_dien_giong` mới là.
        "khu_hoi": {
            "kieu": "rong_la_dong_nhat",
            "bytes_giong": _cap(ok, lambda c: c["khu_hoi"]["bytes_giong"]),
            "trang_giong": _cap(ok, lambda c: c["khu_hoi"]["trang_giong"]),
        },
        "dien": {
            "so_cho": sum(d["so_cho"] for d in dien),
            "da_ap": sum(d["da_ap"] for d in dien),
            "bo_qua": dict(bo_qua),
            "so_trang_giu_lo": _cap(co_dien, lambda c: c["dien"]["so_trang_sau"] == c["dien"]["so_trang_truoc"]),
            "so_trang_giu_word": _cap(
                dien_word,
                lambda c: (
                    isinstance(c["dien"]["so_trang_word_sau"], int)
                    and c["dien"]["so_trang_word_sau"] == c["so_trang"]["word"]
                ),
            ),
            "trang_khong_dien_giong": [sum(t["giong"] for t in tkd), sum(t["trang"] for t in tkd)],
            "zip_giu_muc_khac": _cap(co_dien, lambda c: c["dien"]["muc_zip_doi"] == []),
            "gia_tri": _cong([d["gia_tri"] for d in dien]),
            "gia_tri_word": _cong([c["dien"].get("gia_tri_word", [0, c["dien"]["da_ap"]]) for c in dien_word]),
            "word_mo": _cap(
                [c for c in co_dien if _chay_word(c["dien"].get("word_mo"))], lambda c: c["dien"]["word_mo"] is True
            ),
        },
        "lo_word": {
            "trung_so_trang": _cap(co_word, lambda c: "lo_word" in c and c["lo_word"]["trung_so_trang"]),
            "giong_diem_anh_tb": round(sum(giong) / len(giong), 4) if giong else None,
            "giong_diem_anh_min": min(giong) if giong else None,
            "iou_muc_tb": round(sum(iou) / len(iou), 4) if iou else None,
            "iou_muc_min": min(iou) if iou else None,
        },
        "pdf_so": _tong_pdf(ok, "so"),
        "pdf_scan": _tong_pdf(ok, "scan"),
        "o_bang": {
            "so_cho_theo_tep": {c["tep"]: c["o_bang"]["so_cho"] for c in ok},
            "da_ap": [sum(c["o_bang"].get("da_ap", 0) for c in co_o), sum(c["o_bang"]["so_cho"] for c in co_o)],
            "bo_qua": dict(sum((Counter(c["o_bang"]["bo_qua"]) for c in co_o), Counter())),
            "so_trang_giu": _cap(co_o, lambda c: c["o_bang"]["so_trang_sau"] == c["o_bang"]["so_trang_truoc"]),
            "doc_lai_dung": _cong([c["o_bang"]["doc_lai_dung"] for c in co_o]),
        },
    }


def chay(tep: list[Path], word: bool) -> dict:
    """Một tệp hỏng KHÔNG làm mất cả lượt — cùng khuôn `eval.run_trung_thuc.chay`."""
    thu_muc = None
    if word:
        goc = _THU_MUC_WORD if _THU_MUC_WORD.exists() else Path(tempfile.gettempdir())
        thu_muc = Path(tempfile.mkdtemp(prefix="klaw-thuoc-khuon-", dir=goc))
    w = _Word(thu_muc) if thu_muc else None
    chi_tiet = []
    try:
        for t in tep:
            ten = unicodedata.normalize("NFC", t.name)  # macOS trả tên tệp dạng NFD
            try:
                chi_tiet.append(do_tep(ten, t.read_bytes(), w))
            except Exception as e:
                chi_tiet.append({"tep": ten, "error": f"{type(e).__name__}: {e}"})
    finally:
        if thu_muc:
            shutil.rmtree(thu_muc, ignore_errors=True)
    return {
        "commit_hash": _commit_hash(),
        "word": word,
        "word_chan": w.chan if w else None,
        "so_tep": len(chi_tiet),
        "chi_tiet": chi_tiet,
        "tu_choi_11_trang": _thu(tu_choi_11_trang),
        "tong_hop": tong_hop(chi_tiet),
    }


# ─────────────────────────────────────────────────────────── in


def _ti(x: list[int]) -> str:
    return f"{x[0]}/{x[1]}"


def _in_bang(ket: dict) -> None:
    print(f"commit_hash={ket['commit_hash']}  word={'bật' if ket['word'] else 'tắt'}")
    print(
        f"  {'tệp':<30}{'LO':>3}{'Word':>8}{'zip khác':>9}{'chỗ':>5}{'áp':>4}{'bỏ':>4}{'LO sau':>7}{'W sau':>8}"
        f"{'giữ':>6}{'giá trị':>9}{'LO~W iou':>10}{'PDF':>7}{'scan':>7}"
    )
    for c in ket["chi_tiet"]:
        if "error" in c:
            print(f"  {c['tep'][:30]:<30}LỖI {c['error']}")
            continue
        d, lw = c["dien"], c.get("lo_word")
        tkd = d["trang_khong_dien"]
        iou = [v for v in (lw or {}).get("iou_muc", []) if v is not None]
        pdf = [
            f"{v['so_cho']}/{v['da_ap']}" if isinstance(v, dict) and "error" not in v else "lỗi"
            for v in c["pdf"].values()
        ]
        print(
            f"  {c['tep'][:30]:<30}{c['so_trang']['lo']:>3}{str(c['so_trang'].get('word', '-')):>8}"
            f"{', '.join(d['muc_zip_doi']) or '=':>9}{d['so_cho']:>5}{d['da_ap']:>4}"
            f"{sum(d['bo_qua'].values()):>4}{d['so_trang_sau']:>7}{str(d.get('so_trang_word_sau', '-')):>8}"
            f"{_ti([tkd['giong'], tkd['trang']]) if tkd else '—':>6}{_ti(d['gia_tri']):>9}"
            f"{f'{min(iou):.2f}' if iou else '-':>10}" + "".join(f"{p:>7}" for p in pdf)
        )
    th, tc = ket["tong_hop"], ket["tu_choi_11_trang"]
    dn, lw = th["dien"], th["lo_word"]
    kh = th["khu_hoi"]
    print(f"TỔNG ({th['so_tep']} tệp, {th['loi']} lỗi; không điền gì: {th['khong_dien_gi'] or 0})")
    print(
        f"  số trang LO = Word: {_ti(th['so_trang_lo_bang_word'])}, Word lỗi {th['word_loi']}"
        + (f"  (Word: {ket['word_chan']})" if ket["word_chan"] else "")
    )
    print(
        f"  khứ hồi ({kh['kieu']}, không thể trượt): bytes {_ti(kh['bytes_giong'])}, điểm ảnh {_ti(kh['trang_giong'])}"
    )
    print(
        f"  điền: {dn['da_ap']}/{dn['so_cho']} áp, bỏ {dn['bo_qua'] or 0}; số trang giữ LO {_ti(dn['so_trang_giu_lo'])}, "
        f"Word {_ti(dn['so_trang_giu_word'])}; trang không điền trùng {_ti(dn['trang_khong_dien_giong'])}; "
        f"zip giữ mục khác {_ti(dn['zip_giu_muc_khac'])}; giá trị {_ti(dn['gia_tri'])} "
        f"(Word {_ti(dn['gia_tri_word'])}); Word mở {_ti(dn['word_mo'])}"
    )
    print(
        f"  LO~Word gốc: số trang {_ti(lw['trung_so_trang'])}, điểm ảnh tb {lw['giong_diem_anh_tb']} "
        f"min {lw['giong_diem_anh_min']}, iou mực tb {lw['iou_muc_tb']} min {lw['iou_muc_min']}"
    )
    for k in ("pdf_so", "pdf_scan"):
        if p := th[k]:
            print(
                f"  {k}: tỉ lệ số ô {p['so_cho']}/{p['so_cho_docx']} docx ({p['ti_le_so_voi_docx']}), "
                f"trần khớp {_ti(p['cho_toi_da_khop'])}, thừa {p['cho_thua']}; áp {p['da_ap']}, "
                f"bỏ {p['bo_qua'] or 0}, không điền gì {p['khong_dien_gi'] or 0}; tệp không đổi ngoài hộp {_ti(p['tep_khong_doi_ngoai_hop'])} "
                f"(ngoài dải chữ {_ti(p['tep_khong_doi_ngoai_dai_chu'])}), giá trị {_ti(p['gia_tri'])} "
                f"(bỏ chấm {_ti(p['gia_tri_bo_cham'])}), lỗi {p['loi']}"
            )
    ob = th["o_bang"]
    print(
        f"  ô bảng (o): {', '.join(f'{t[:24]} {n}' for t, n in ob['so_cho_theo_tep'].items() if n) or 0}; "
        f"áp {_ti(ob['da_ap'])}, bỏ {ob['bo_qua'] or 0}; số trang giữ LO {_ti(ob['so_trang_giu'])}; "
        f"đọc lại đúng {_ti(ob['doc_lai_dung'])}"
    )
    print(f"  11 trang: {tc}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bo", type=Path, nargs="*", default=[_KHO_MAC_DINH], help="thư mục hoặc tệp .docx")
    ap.add_argument("--out", type=Path, default=_REPO_ROOT / "eval" / "results" / "khuon_goc.json")
    ap.add_argument("--word", action="store_true", help="đo thêm bằng Microsoft Word qua osascript")
    args = ap.parse_args()
    # pypdf cảnh báo từng đối tượng lệch offset trong PDF của Word — tiếng ồn.
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    tep = _tim_tep([p for p in args.bo if p.exists()])
    if not tep:
        raise SystemExit(f"không thấy .docx nào trong {', '.join(map(str, args.bo))} — biểu mẫu không commit")
    ket = chay(tep, args.word)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ket, ensure_ascii=False, indent=2), encoding="utf-8")
    _in_bang(ket)


if __name__ == "__main__":
    main()
