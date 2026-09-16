"""Đọc tài liệu người dùng thành các đơn vị văn bản có vị trí (spec 2026-09-15
§FR-001..FR-005). Thuần Python, 0 token, không I/O ngoài bộ nhớ.

Hai quyết định định hình toàn bộ file:

**Đơn vị không bao giờ bị gộp.** Mỗi đoạn, mỗi ô bảng đứng riêng. Đây là điều
kiện để FR-010 có nghĩa: một đoạn trích phải nằm gọn trong một đơn vị. Nối các
đơn vị lại tạo ra những vết ghép không tồn tại trong tài liệu gốc, và một đoạn
trích vắt qua hai ô bảng sẽ khớp dù nó không nguyên văn ở bất kỳ đâu — đúng chế
độ hỏng mà `verify_tier1._tim_quote` đã chặn cho trích dẫn điều luật bằng cách
so với TỪNG DÒNG `provisions` thay vì nối cả cây.

**Bốn nguyên nhân hỏng là bốn mã riêng.** "Không hỗ trợ", "tệp hỏng", "cần mật
khẩu" và "không có lớp chữ" đòi bốn câu trả lời khác nhau cho người dùng: đổi
định dạng, gửi lại tệp, bỏ mật khẩu, hoặc gửi bản gốc thay vì bản chụp. Gộp
chúng thành một nhãn "không đọc được" là vứt đi thứ duy nhất giúp họ tự sửa.
"""

import logging
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from enum import StrEnum
from io import BytesIO
from math import ceil

logger = logging.getLogger(__name__)

# ponytail: DOCX không có khái niệm trang cố định — số trang phụ thuộc máy in,
# lề và font lúc mở. Quy đổi theo ký tự là xấp xỉ có chủ đích, chỉ dùng để chọn
# đường xử lý tại chỗ hay chạy nền (FR-029/030), không bao giờ hiện cho người
# dùng như số trang thật. Đổi một chỗ này nếu đo lại thấy lệch.
KY_TU_MOI_TRANG = 3000

_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_DUOI_ANH = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".heic")
_DUOI_HO_TRO = (".pdf", ".docx", *_DUOI_ANH)

# Dưới ngưỡng này thì chữ OCR đọc ra là nhiễu chứ không phải nội dung. Đo trên
# một trang sạch: tesseract `vie` cho 92–96%. Để 0.60 vì trang chụp nghiêng, mờ
# hay thiếu sáng tụt xuống khoảng 70–80% mà vẫn đọc đúng.
# ponytail: một ngưỡng cho cả trang; tách theo vùng nếu đo thấy cần.
NGUONG_TIN_OCR = 0.60

# DPI rasterize PDF-ảnh. 200 đủ cho chữ 10–12pt; cao hơn chỉ tốn thời gian.
_DPI_OCR = 200

# Chặn tiến trình TREO, không phải chặn chạy lâu. FR-032 cấm huỷ vì chạy lâu;
# một `tesseract` treo thì không phải đang chạy lâu, nó đang không chạy nữa.
_HAN_TREO_GIAY = 300

# Phanh zip bom. `tai_lieu.kiem_kich_thuoc` đo tệp ĐÃ NÉN, nên 64 MB số 0 nén
# lại còn vài chục KB đi lọt qua nó và nở ra trong RAM lúc đọc. Hai con số dưới
# đây đo cái zip KHAI BÁO, trước khi giải nén một byte nào. Một DOCX thật có
# vài chục mục và vài MB giải nén, nên trần này chỉ chạm tệp dựng ra để phá.
TRAN_SO_MUC_ZIP = 512
TRAN_GIAI_NEN_BYTE = 64 * 1024 * 1024


class NguonChu(StrEnum):
    """Chữ này đến từ đâu — và vì thế đáng tin tới đâu.

    `lop_chu` là chữ THẬT của tài liệu, đọc thẳng từ tệp. `ocr` là PHỎNG ĐOÁN
    của máy nhìn vào ảnh. Hai hạng bằng chứng khác nhau, không bao giờ gộp:
    nếu OCR đọc "20.000.000" thành "2O.OOO.OOO" thì đoạn trích vẫn khớp với đầu
    ra OCR, phép tra chuỗi vẫn chạy đúng, nhưng nó không còn chứng minh được
    điều người dùng tưởng. Bằng chứng yếu đi trong khi giao diện trông y hệt —
    đúng chế độ hỏng nguy hiểm nhất của một sản phẩm pháp lý.
    """

    lop_chu = "lop_chu"
    ocr = "ocr"


class LoaiHong(StrEnum):
    """Mỗi nguyên nhân có ĐÚNG MỘT mã của riêng nó (FR-003)."""

    dinh_dang_khong_ho_tro = "dinh_dang_khong_ho_tro"
    tep_hong = "tep_hong"
    can_mat_khau = "can_mat_khau"
    khong_co_lop_chu = "khong_co_lop_chu"


class KhongDocDuoc(Exception):  # noqa: N818
    """Tài liệu không đọc được, kèm nguyên nhân phân biệt được."""

    def __init__(self, ly_do: LoaiHong, chi_tiet: str = "") -> None:
        super().__init__(f"{ly_do}: {chi_tiet}" if chi_tiet else str(ly_do))
        self.ly_do = ly_do
        self.chi_tiet = chi_tiet


@dataclass(frozen=True)
class DonViVanBan:
    """Một mẩu văn bản liền mạch trong tài liệu, kèm chỗ nó nằm.

    `offset_dau` tính theo ký tự TRONG TRANG, không tính toàn tài liệu: người
    dùng định vị bằng cặp (trang, vị trí trong trang), và trang là thứ họ thấy.
    """

    chi_so: int
    trang: int
    offset_dau: int
    noi_dung: str
    nguon_chu: NguonChu = NguonChu.lop_chu
    """Mặc định là chữ thật: không khai báo thì KHÔNG bị hạ cấp im lặng."""
    do_tin: float | None = None
    """0–1, chỉ có với `ocr`. `None` với chữ đọc thẳng — ở đó không có gì để đoán."""
    vung: str = "than"
    """`than` | `dau_trang` | `chan_trang`.

    Đầu trang và chân trang là NGUỒN KHÁC với thân bài: số hiệu biểu mẫu, tên
    đơn vị ban hành, số trang. Trộn chúng vào thân là nói sai chỗ một câu được
    viết, và một neo tài liệu chỉ vào "trang 1" của một chân trang lặp lại ở
    mọi trang thì không chỉ vào đâu cả.
    """
    bang: tuple[int, int, int] | None = None
    """(chỉ số bảng, hàng, cột) — ĐẾM TỪ 0, `None` khi đơn vị không ở trong bảng.

    Với phiếu chấm, biểu mẫu, bảng lương thì bảng LÀ nội dung: "2,0" một mình
    không nói gì, "2,0 ở hàng Chuyên cần" mới nói. Giao diện cộng 1 khi hiển
    thị cho người đọc; ở đây giữ chỉ số để cùng gốc với `chi_so`.
    """


@dataclass(frozen=True)
class TaiLieuDaDoc:
    don_vi: list[DonViVanBan]
    so_trang: int
    so_ky_tu: int

    @property
    def co_ocr(self) -> bool:
        """Tài liệu này có phần nào đọc bằng OCR không — người dùng phải biết."""
        return any(d.nguon_chu is NguonChu.ocr for d in self.don_vi)


def co_ocr() -> bool:
    """Máy này chạy được OCR không. Thiếu tesseract thì nhánh ảnh phải nói thật
    là không đọc được, chứ không im lặng trả về tài liệu rỗng."""
    return shutil.which("tesseract") is not None


def doc(ten_tep: str, du_lieu: bytes) -> TaiLieuDaDoc:
    """Đọc `du_lieu` thành các đơn vị văn bản, hoặc ném `KhongDocDuoc`.

    Không ghi tệp ra đĩa ở bất kỳ nhánh nào (FR-022): dữ liệu vào bằng bytes,
    ra bằng dataclass, và người gọi chịu trách nhiệm buông tham chiếu.
    """
    ten = (ten_tep or "").lower()
    if ten.endswith(".pdf"):
        thoi = _doc_pdf(du_lieu)
        if not thoi:
            # PDF bọc ảnh — bản scan trông đúng như vậy. Trước đây bị từ chối
            # thẳng; giờ thử OCR, nhưng kết quả mang nhãn `ocr` chứ không được
            # đánh đồng với PDF có lớp chữ.
            thoi = _ocr_pdf(du_lieu)
    elif ten.endswith(".docx"):
        thoi = _doc_docx(du_lieu)
    elif ten.endswith(_DUOI_ANH):
        thoi = _ocr_anh(du_lieu)
    else:
        raise KhongDocDuoc(
            LoaiHong.dinh_dang_khong_ho_tro,
            f"chỉ hỗ trợ {', '.join(_DUOI_HO_TRO)}",
        )

    if not thoi:
        raise KhongDocDuoc(LoaiHong.khong_co_lop_chu, "không rút được ký tự nào")
    return _dat_vi_tri(thoi)


# ------------------------------------------------------------------------ DOCX


_P = f"{{{_NS['w']}}}p"
_TBL = f"{{{_NS['w']}}}tbl"
_TR = f"{{{_NS['w']}}}tr"
_TC = f"{{{_NS['w']}}}tc"
_BODY = f"{{{_NS['w']}}}body"


def _kiem_zip(z: zipfile.ZipFile) -> None:
    """Phanh zip bom, chạy TRƯỚC khi đọc bất kỳ mục nào — xem `TRAN_SO_MUC_ZIP`."""
    muc = z.infolist()
    if len(muc) > TRAN_SO_MUC_ZIP:
        raise KhongDocDuoc(LoaiHong.tep_hong, f"tệp docx có quá {TRAN_SO_MUC_ZIP} mục")
    if sum(m.file_size for m in muc) > TRAN_GIAI_NEN_BYTE:
        raise KhongDocDuoc(LoaiHong.tep_hong, "tệp docx giải nén ra quá lớn")


def _goc_xml(xml: bytes, ten: str) -> ET.Element:
    try:
        return ET.fromstring(xml)
    except ET.ParseError as e:
        raise KhongDocDuoc(LoaiHong.tep_hong, f"{ten} hỏng") from e


def _chu(nut: ET.Element) -> str:
    return "".join(t.text or "" for t in nut.iter(f"{{{_NS['w']}}}t")).strip()


def _duyet_phang(goc: ET.Element, vung: str) -> list[tuple]:
    """Mọi `w:p` theo thứ tự tài liệu, KHÔNG toạ độ bảng.

    Vừa là đường lùi của thân bài, vừa là đường duy nhất cho đầu/chân trang —
    ở đó một `w:p` là một dòng và không có gì để định vị thêm.
    """
    return [(None, c, None, vung, None) for p in goc.iter(_P) if (c := _chu(p))]


def _duyet_than(goc: ET.Element) -> list[tuple]:
    """Con trực tiếp của `w:body` theo thứ tự: `w:p` là một đơn vị, `w:tbl` cho
    một đơn vị mỗi ô kèm toạ độ (bảng, hàng, cột).

    Chữ của một ô là các `w:p` TRONG ô nối bằng một dấu cách — kể cả `w:p` của
    bảng lồng bên trong. Bảng lồng không được đánh số riêng: nó là chi tiết
    trình bày của ô bao ngoài, và tách ra thì "hàng 2 cột 1" của người đọc trỏ
    vào một bảng họ không nhìn thấy.
    """
    than = goc.find(_BODY)
    if than is None:
        return []
    ra: list[tuple] = []
    so_bang = 0
    for con in than:
        if con.tag == _P:
            if chu := _chu(con):
                ra.append((None, chu, None, "than", None))
        elif con.tag == _TBL:
            for h, tr in enumerate(con.findall(_TR)):
                for c, tc in enumerate(tr.findall(_TC)):
                    if chu := " ".join(x for p in tc.iter(_P) if (x := _chu(p))):
                        ra.append((None, chu, None, "than", (so_bang, h, c)))
            so_bang += 1
    return ra


def _doc_docx(du_lieu: bytes) -> list[tuple]:
    """Thân bài theo cấu trúc, rồi đầu trang, rồi chân trang.

    Duyệt theo cấu trúc BỎ SÓT thứ duyệt phẳng thấy: `w:sdt` (content control),
    hộp chữ, và mọi phần tử cấp thân chưa được kể tên ở đây. Nên nó không thay
    thế duyệt phẳng một cách mù quáng — ít chữ hơn thì lùi về. Mất toạ độ bảng
    là khoản lỗ sống chung được; mất nguyên một điều khoản thì không.
    """
    try:
        with zipfile.ZipFile(BytesIO(du_lieu)) as z:
            _kiem_zip(z)
            goc = _goc_xml(z.read("word/document.xml"), "word/document.xml")
            than = _duyet_than(goc)
            phang = _duyet_phang(goc, "than")
            if sum(len(t[1]) for t in than) < sum(len(t[1]) for t in phang):
                than = phang

            ra = list(than)
            for tien_to, vung in (("word/header", "dau_trang"), ("word/footer", "chan_trang")):
                for ten in sorted(n for n in z.namelist() if n.startswith(tien_to) and n.endswith(".xml")):
                    ra.extend(_duyet_phang(_goc_xml(z.read(ten), ten), vung))
            return ra
    except KeyError as e:
        raise KhongDocDuoc(LoaiHong.tep_hong, "thiếu word/document.xml") from e
    except zipfile.BadZipFile as e:
        # DOCX có mật khẩu là tệp OLE chứ không phải zip, nên rơi vào đây. Không
        # phân biệt được hai ca này nếu không đọc header OLE; báo `tep_hong` là
        # nói đúng những gì biết chắc.
        raise KhongDocDuoc(LoaiHong.tep_hong, "không mở được tệp docx") from e


# ------------------------------------------------------------------------- PDF


def _doc_pdf(du_lieu: bytes) -> list[tuple[int | None, str]]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(du_lieu))
    except Exception as e:
        # pypdf ném `PyPdfError` cho tệp sai cấu trúc nhưng cũng ném
        # ValueError/OSError cho tệp rác; bắt rộng ở đây là đúng vì mọi nhánh
        # đều dẫn tới cùng một câu trả lời cho người dùng: gửi lại tệp.
        raise KhongDocDuoc(LoaiHong.tep_hong, "không mở được tệp pdf") from e

    if reader.is_encrypted:
        raise KhongDocDuoc(LoaiHong.can_mat_khau, "pdf được bảo vệ bằng mật khẩu")

    ra: list[tuple[int | None, str]] = []
    for so, trang in enumerate(reader.pages, start=1):
        try:
            chu = trang.extract_text() or ""
        except Exception:
            # Một trang hỏng không được làm hỏng cả tài liệu; nếu MỌI trang đều
            # câm thì `doc()` sẽ báo `khong_co_lop_chu` ở tầng trên.
            logger.warning("doc_tai_lieu: không rút được chữ ở trang %d", so)
            chu = ""
        for dong in chu.splitlines():
            if dong.strip():
                ra.append((so, dong.strip()))
    return ra


# ---------------------------------------------------------------- gán vị trí


def _dat_vi_tri(thoi: list[tuple]) -> TaiLieuDaDoc:
    """Gán `trang`, `offset_dau` và nguồn chữ cho từng đơn vị.

    Nhận cả ba hình dạng: `(trang, noi_dung)` từ nhánh đọc chữ thật,
    `(trang, noi_dung, do_tin)` từ nhánh OCR, và
    `(trang, noi_dung, do_tin, vung, bang)` từ nhánh DOCX có cấu trúc. Có
    `do_tin` nghĩa là máy đang đoán, nên đơn vị đó mang nhãn `ocr`.

    PDF đã biết trang thật. DOCX chưa, nên trang được suy ra từ số ký tự đã đi
    qua — xem ghi chú ở `KY_TU_MOI_TRANG`.
    """
    don_vi: list[DonViVanBan] = []
    da_di = 0          # ký tự đã đi qua trong toàn tài liệu (nhánh DOCX)
    trang_hien = None
    offset = 0
    theo_ky_tu = bool(thoi) and thoi[0][0] is None

    for i, muc in enumerate(thoi):
        trang, noi_dung = muc[0], muc[1]
        do_tin = muc[2] if len(muc) > 2 else None
        vung = muc[3] if len(muc) > 3 else "than"
        bang = muc[4] if len(muc) > 4 else None
        if trang is None:
            trang = 1 + da_di // KY_TU_MOI_TRANG
        if trang != trang_hien:
            trang_hien, offset = trang, 0
        don_vi.append(
            DonViVanBan(
                chi_so=i,
                trang=trang,
                offset_dau=offset,
                noi_dung=noi_dung,
                nguon_chu=NguonChu.ocr if do_tin is not None else NguonChu.lop_chu,
                do_tin=do_tin,
                vung=vung,
                bang=bang,
            )
        )
        offset += len(noi_dung) + 1   # +1 cho dấu xuống dòng giữa hai đơn vị
        da_di += len(noi_dung) + 1

    so_ky_tu = sum(len(d.noi_dung) for d in don_vi)
    so_trang = max((d.trang for d in don_vi), default=1)
    if theo_ky_tu:   # DOCX: trang là xấp xỉ theo ký tự
        so_trang = max(1, ceil(so_ky_tu / KY_TU_MOI_TRANG))
    return TaiLieuDaDoc(don_vi=don_vi, so_trang=so_trang, so_ky_tu=so_ky_tu)


# ═══ OCR ════════════════════════════════════════════════════════════════════
# Gọi `tesseract` qua subprocess thay vì thêm `pytesseract`: một tiến trình con
# và một lần đọc TSV là đủ, còn thư viện bọc thì thêm một dependency để làm
# đúng việc đó. Bản thân `tesseract` với gói `vie` vẫn là điều kiện bắt buộc.


def _tesseract(duong_anh: str) -> list[tuple[str, float]]:
    """(dòng, độ tin) cho một ảnh. TSV vì nó cho độ tin TỪNG TỪ.

    Độ tin của một dòng là trung bình độ tin các từ trong dòng đó — thấp nghĩa
    là máy đang đoán, và một dòng máy đang đoán không nên thành bằng chứng.
    """
    ra = subprocess.run(
        ["tesseract", duong_anh, "-", "-l", "vie", "tsv"],
        capture_output=True,
        timeout=_HAN_TREO_GIAY,
    )
    if ra.returncode != 0:
        raise KhongDocDuoc(LoaiHong.tep_hong, "tesseract không đọc được ảnh")

    dong: dict[tuple, list[tuple[str, float]]] = {}
    for hang in ra.stdout.decode("utf-8", errors="replace").splitlines()[1:]:
        c = hang.split("\t")
        if len(c) < 12 or not c[11].strip():
            continue
        try:
            tin = float(c[10])
        except ValueError:
            continue
        if tin < 0:
            continue
        dong.setdefault(tuple(c[2:5]), []).append((c[11], tin / 100.0))

    ket: list[tuple[str, float]] = []
    for tu in dong.values():
        chu = " ".join(t for t, _ in tu).strip()
        tin = sum(d for _, d in tu) / len(tu)
        if chu and tin >= NGUONG_TIN_OCR:
            ket.append((chu, tin))
    return ket


def _ocr_anh(du_lieu: bytes) -> list[tuple[int | None, str, float]]:
    if not co_ocr():
        raise KhongDocDuoc(
            LoaiHong.khong_co_lop_chu,
            "máy chủ chưa cài công cụ nhận dạng chữ, chưa đọc được ảnh",
        )
    with tempfile.NamedTemporaryFile(suffix=".img", delete=True) as f:
        f.write(du_lieu)
        f.flush()
        return [(1, chu, tin) for chu, tin in _tesseract(f.name)]


def _ocr_pdf(du_lieu: bytes) -> list[tuple[int | None, str, float]]:
    """Rasterize từng trang rồi OCR. Cần `pdftoppm` của poppler."""
    if not co_ocr() or not shutil.which("pdftoppm"):
        raise KhongDocDuoc(
            LoaiHong.khong_co_lop_chu,
            "tệp không có lớp chữ và máy chủ chưa đọc được bản scan",
        )
    ra: list[tuple[int | None, str, float]] = []
    with tempfile.TemporaryDirectory() as thu_muc:
        goc = f"{thu_muc}/t"
        kq = subprocess.run(
            ["pdftoppm", "-r", str(_DPI_OCR), "-png", du_lieu and "-", goc],
            input=du_lieu,
            capture_output=True,
            timeout=_HAN_TREO_GIAY,
        )
        if kq.returncode != 0:
            raise KhongDocDuoc(LoaiHong.tep_hong, "không dựng được ảnh từ pdf")
        from pathlib import Path as _P  # noqa: N814

        for so, anh in enumerate(sorted(_P(thu_muc).glob("t-*.png")), start=1):
            ra.extend((so, chu, tin) for chu, tin in _tesseract(str(anh)))
    return ra
