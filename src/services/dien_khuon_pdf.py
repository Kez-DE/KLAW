"""Áp phép sửa lên khuôn gốc PDF (P3b) — kế hoạch
`docs/plans/active/khuon-goc-dien-tai-cho.md`, hợp đồng "Edit operations".

PDF không dàn lại được, nên bộ áp KHÔNG đụng vào nội dung trang gốc: mỗi trang
có phép sửa nhận một trang PHỦ dựng bằng reportlab — hình chữ nhật trắng che
hộp cũ, rồi chữ mới — ghép lên trên bằng `pypdf` (`merge_page`). Chỉ `dien` và
`thay`; `chen_sau`/`xoa` cần dàn lại dòng nên bị bỏ qua. PDF scan đi cùng
đường: trang là một ảnh, lớp phủ nằm trên ảnh.

Thuần: bytes vào, bytes ra, không DB, không mạng. Mỗi phiên bản áp TOÀN BỘ danh
sách phép của nó lên khuôn gốc NGUYÊN BẢN (không cộng dồn ở tầng này); phép
hỏng bị bỏ qua và báo bằng một mã của `LyDoBoQua`, không bao giờ đoán.

Lớp phủ CHE chữ gốc chứ không xoá nó: lớp chữ của trang gốc vẫn còn dưới ô
trắng — pdftotext, sao chép hay tìm kiếm vẫn thấy dãy chấm và chữ cũ của một
phép `thay`. Đây không phải công cụ xoá thông tin (redaction).

Toạ độ trong `don_vi` (`hop`, `cho_trong[].hop`) là hệ hiển thị của poppler:
điểm, gốc ở góc trên-trái MEDIA box (không phải CropBox), sau `/Rotate` — đúng
hệ bộ đọc P2b đo. `_khung` đổi hệ ấy về hệ người dùng của từng trang.
"""

import glob
import logging
import statistics
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from io import BytesIO
from typing import TYPE_CHECKING, Any

from src.config import get_settings
from src.services.doc_tai_lieu import KhongDocDuoc, LoaiHong
from src.services.tai_lieu import _cho_trong_tu_hang, _hop_tu_hang, _so_tu_nhien

if TYPE_CHECKING:
    from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)

# Đổi `co_chu` (chiều cao hộp từ của poppler, điểm) ra cỡ phông danh nghĩa.
# poppler cao hộp từ = ascent + descent của phông NGUỒN: Times New Roman (và
# Liberation Serif, cùng số đo) là 0,891 + 0,216 = 1,107 em. Đo 2026-09-26 trên
# BM.M05 dựng bằng LibreOffice: chữ 13 pt → `co_chu` 14,39; 12 pt → 13,28.
# ponytail: một hệ số cho mọi phông nguồn — Arial 1,117, Calibri 1,221 (chữ điền
# to hơn nguồn chừng 10 %); đọc ascent/descent của phông nguồn khi một biểu mẫu
# thật lệch thấy được.
_TY_LE_CO_CHU = 1.107
# Phần dưới đường chân chữ của phông nguồn, theo em (descent Times New Roman).
_DUOI_CHAN = 0.216
# Lề tô trắng quanh hộp, điểm — hợp đồng: không quá 1 pt ngoài hộp.
_DEM = 0.5
# Chữ dài hơn hộp được thu nhỏ tới 70 % cỡ danh nghĩa, quá nữa là `khong_vua`.
_THU_NHO_TOI_DA = 0.7

# Phông điền, theo thứ tự ưu tiên; mẫu glob vì Debian đặt Liberation ở
# `liberation/` (fonts-liberation 2.x) hay `liberation2/` tuỳ bản phát hành.
_UNG_VIEN_PHONG = (
    "/usr/share/fonts/truetype/liberation*/LiberationSerif-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/Library/Fonts/Times New Roman.ttf",
    "/Applications/LibreOffice.app/Contents/Resources/fonts/truetype/LiberationSerif-Regular.ttf",
    "/usr/lib/libreoffice/share/fonts/truetype/LiberationSerif-Regular.ttf",
    "/opt/libreoffice*/share/fonts/truetype/LiberationSerif-Regular.ttf",
)
# Một phông chỉ được nhận khi vẽ được MỌI chữ cái tiếng Việt dựng sẵn.
_CHU_VIET = "ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯư" + "".join(map(chr, range(0x1EA0, 0x1EFA)))

_Hop = tuple[float, float, float, float]


class LyDoBoQua(StrEnum):
    """Tập ĐÓNG các lý do một phép sửa không được áp (`bao_cao["bo_qua"]`)."""

    khong_hop_le = "khong_hop_le"
    """Phép sai hình dạng: không phải dict, `don_vi`/`cho_trong` không phải số
    tự nhiên, giá trị không phải chuỗi, rỗng hay có ký tự điều khiển."""
    loai_khong_ho_tro = "loai_khong_ho_tro"
    """`chen_sau`, `xoa` hay một `loai` lạ — PDF chỉ nhận `dien`, `thay`."""
    khong_co_don_vi = "khong_co_don_vi"
    """Không đơn vị nào có `chi_so` bằng `don_vi` của phép."""
    khong_co_dia_chi = "khong_co_dia_chi"
    """Đơn vị không có `hop` (`thay`), hoặc hộp/trang không thuộc tệp này."""
    khong_co_cho_trong = "khong_co_cho_trong"
    """Đơn vị không có chỗ trống PDF nào mang `so` bằng `cho_trong` của phép."""
    xung_dot = "xung_dot"
    """Vùng vẽ chồng lên vùng của một phép ĐỨNG TRƯỚC đã nhận trên cùng trang
    (cùng chỗ trống hai lần, `dien` trong dòng đã `thay`…): phép trước giữ chỗ."""
    khong_vua = "khong_vua"
    """Chữ không vừa bề rộng hộp kể cả khi thu nhỏ tới 70 %."""
    khong_co_phong = "khong_co_phong"
    """Không có phông tiếng Việt, hoặc phông không vẽ được một ký tự của giá trị."""


@dataclass(frozen=True)
class _Ve:
    """Một phép đã lập xong, chờ vẽ — mọi toạ độ ở hệ hiển thị (y hướng XUỐNG)."""

    trang: int
    to: _Hop
    chu: str
    x: float
    chan: float
    co: float
    vung: _Hop


@cache
def _phong() -> "TTFont | None":
    """Phông điền, dò và đăng ký MỘT lần mỗi tiến trình. `None` khi không có."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFError, TTFont

    cau_hinh = get_settings().phong_dien_path
    ung_vien = [cau_hinh] if cau_hinh else [p for mau in _UNG_VIEN_PHONG for p in sorted(glob.glob(mau))]
    for duong in ung_vien:
        try:
            phong = TTFont("KlawDien", duong)
        except (TTFError, OSError):
            continue
        if all(ord(c) in phong.face.charToGlyph for c in _CHU_VIET):
            pdfmetrics.registerFont(phong)
            return phong
    logger.warning("dien_khuon_pdf: không có phông tiếng Việt trong %d ứng viên", len(ung_vien))
    return None


def _khung(trang: Any) -> tuple[tuple[float, ...], float, float] | None:
    """Ma trận `cm` đổi hệ hiển thị-y-LÊN (X = x poppler, Y = cao − y poppler)
    về hệ người dùng của trang, cùng bề rộng/cao hiển thị. `/Rotate` xoay trang
    theo chiều kim đồng hồ khi hiển thị; không là bội của 90 thì `None`."""
    mb = trang.mediabox
    x0, x1 = sorted((float(mb[0]), float(mb[2])))
    y0, y1 = sorted((float(mb[1]), float(mb[3])))
    rong, cao = x1 - x0, y1 - y0
    try:
        xoay = int(trang.rotation) % 360
    except (TypeError, ValueError):
        return None
    return {
        0: ((1, 0, 0, 1, x0, y0), rong, cao),
        90: ((0, 1, -1, 0, x1, y0), cao, rong),
        180: ((-1, 0, 0, -1, x1, y1), rong, cao),
        270: ((0, -1, 1, 0, x0, y1), cao, rong),
    }.get(xoay)


def _chong(a: _Hop, b: _Hop) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _co_scan(don_vi: list[dict]) -> dict[int, float]:
    """Trang → chiều cao dòng TRUNG VỊ của các dòng OCR có hộp.

    ponytail: bản scan dùng MỘT cỡ chữ cho cả trang. Chiều cao dòng OCR là
    chiều cao MỰC (dấu chồng, chân g/p/q), nên lệch ±30 % giữa các dòng cùng
    cỡ chữ — BM.M05 scan: 10,8–18,0 cho chữ 13 pt, chữ điền to nhỏ theo nhãn.
    Trung vị của trang ổn định (13,3–14,4; bản có lớp chữ đo 14,39). Tách theo
    khối khi có biểu mẫu scan hai cỡ chữ thân bài."""
    cao: dict[int, list[float]] = {}
    for d in don_vi:
        hop = _hop_tu_hang(d.get("hop")) if isinstance(d, dict) and d.get("nguon_chu") == "ocr" else None
        if hop and _so_tu_nhien(d.get("trang")):
            cao.setdefault(d["trang"], []).append(hop[3] - hop[1])
    return {t: statistics.median(h) for t, h in cao.items()}


def _lap(
    p: Any, theo_chi_so: dict[int, dict], khung: list, phong: "TTFont | None", co_scan: dict[int, float]
) -> "_Ve | LyDoBoQua":
    """Một phép → thứ cần vẽ, hoặc lý do bỏ qua. Không đoán: thiếu gì là bỏ."""
    if not isinstance(p, dict):
        return LyDoBoQua.khong_hop_le
    loai = p.get("loai")
    if loai not in ("dien", "thay"):
        return LyDoBoQua.loai_khong_ho_tro
    chu = p.get("gia_tri" if loai == "dien" else "noi_dung")
    # `isprintable()` loại cả `\n`: trên PDF mọi giá trị nằm trên MỘT dòng.
    if (
        not _so_tu_nhien(p.get("don_vi"))
        or (loai == "dien" and not _so_tu_nhien(p.get("cho_trong")))
        or not isinstance(chu, str)
        or not chu.strip()
        or not chu.isprintable()
    ):
        return LyDoBoQua.khong_hop_le
    chu = unicodedata.normalize("NFC", chu)
    d = theo_chi_so.get(p["don_vi"])
    if d is None:
        return LyDoBoQua.khong_co_don_vi
    if loai == "dien":
        c = next((c for c in _cho_trong_tu_hang(d.get("cho_trong")) if c.so == p["cho_trong"] and c.hop), None)
        if c is None:
            return LyDoBoQua.khong_co_cho_trong
        hop, co_chu = c.hop, c.co_chu
    else:
        hop = _hop_tu_hang(d.get("hop"))
        if hop is None:
            return LyDoBoQua.khong_co_dia_chi
        co_chu = hop[3] - hop[1]

    so_trang = d.get("trang")
    k = khung[so_trang - 1] if _so_tu_nhien(so_trang) and 1 <= so_trang <= len(khung) else None
    if d.get("nguon_chu") == "ocr":
        co_chu = co_scan.get(so_trang, co_chu)
    x0, y0, x1, y1 = hop
    if k is None or co_chu <= 0 or x0 < -1 or y0 < -1 or x1 > k[1] + 1 or y1 > k[2] + 1:
        return LyDoBoQua.khong_co_dia_chi
    if phong is None or any(ord(ch) not in phong.face.charToGlyph for ch in chu):
        return LyDoBoQua.khong_co_phong

    from reportlab.pdfbase.pdfmetrics import stringWidth

    co = co_chu / _TY_LE_CO_CHU
    rong = stringWidth(chu, phong.fontName, co)
    co_ve = co if rong <= x1 - x0 else co * (x1 - x0) / rong
    if co_ve < _THU_NHO_TOI_DA * co:
        return LyDoBoQua.khong_vua
    # Hộp cao cỡ dòng chữ (từ poppler, dòng OCR) chứa cả phần dưới chân chữ;
    # dải CHỈ có chấm (scan, dòng chấm dưới nhãn) thì chấm ngồi ngay trên chân chữ.
    chan = y1 if y1 - y0 < co_chu / 2 else y1 - _DUOI_CHAN * co
    to = (x0 - _DEM, y0 - _DEM, x1 + _DEM, y1 + _DEM)
    vung = (
        to[0],
        min(to[1], chan - (_TY_LE_CO_CHU - _DUOI_CHAN) * co_ve),
        max(to[2], x0 + min(rong, x1 - x0)),
        max(to[3], chan + _DUOI_CHAN * co_ve),
    )
    return _Ve(trang=so_trang, to=to, chu=chu, x=x0, chan=chan, co=co_ve, vung=vung)


def ap_dung_pdf(pdf: bytes, don_vi: list[dict], phep_sua: list[dict]) -> tuple[bytes, dict]:
    """Áp `phep_sua` lên khuôn gốc `pdf`; trả `(bytes mới, bao_cao)`.

    `don_vi` là các dict đúng như `viec_doc_tai_lieu.don_vi` lưu; phép trỏ đơn
    vị theo `chi_so`, chỗ trống theo `so`. `bao_cao = {"da_ap": [chỉ số phép],
    "bo_qua": [{"phep": chỉ số, "ly_do": mã LyDoBoQua dạng chuỗi}]}` — mỗi
    phép ở đúng một bên. Không phép nào áp được thì trả NGUYÊN bytes vào. PDF không mở được hay
    có mật khẩu: `KhongDocDuoc` (`tep_hong` / `can_mat_khau`), như bộ đọc.
    """
    if not phep_sua:
        return pdf, {"da_ap": [], "bo_qua": []}
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import RectangleObject

    try:
        reader = PdfReader(BytesIO(pdf))
        if reader.is_encrypted:
            raise KhongDocDuoc(LoaiHong.can_mat_khau, "pdf được bảo vệ bằng mật khẩu")
        khung = [_khung(t) for t in reader.pages]
    except KhongDocDuoc:
        raise
    except Exception as e:
        # Cùng lý lẽ `doc_tai_lieu._doc_pdf`: pypdf ném đủ loại lỗi cho tệp rác.
        raise KhongDocDuoc(LoaiHong.tep_hong, "không mở được tệp pdf") from e

    theo_chi_so = {d["chi_so"]: d for d in don_vi if isinstance(d, dict) and _so_tu_nhien(d.get("chi_so"))}
    phong = _phong()
    co_scan = _co_scan(don_vi)
    ve: dict[int, _Ve] = {}
    bo_qua: dict[int, LyDoBoQua] = {}
    for i, p in enumerate(phep_sua):
        ra = _lap(p, theo_chi_so, khung, phong, co_scan)
        # ponytail: so với mọi phép đã nhận, O(n²) — ≤10 trang, vài trăm chỗ trống.
        if isinstance(ra, _Ve) and any(v.trang == ra.trang and _chong(v.vung, ra.vung) for v in ve.values()):
            ra = LyDoBoQua.xung_dot
        if isinstance(ra, _Ve):
            ve[i] = ra
        else:
            bo_qua[i] = ra
    bao_cao = {"da_ap": sorted(ve), "bo_qua": [{"phep": i, "ly_do": str(bo_qua[i])} for i in sorted(bo_qua)]}
    if not ve:
        return pdf, bao_cao

    from reportlab.pdfgen import canvas

    cac_trang = sorted({v.trang for v in ve.values()})
    buf = BytesIO()
    # Phông đầu mặc định của reportlab là Helvetica KHÔNG nhúng; đặt phông điền.
    c = canvas.Canvas(buf, invariant=True, pageCompression=1, initialFontName=phong.fontName)
    for so_trang in cac_trang:
        ma_tran, _, cao = khung[so_trang - 1]
        c.transform(*ma_tran)
        for v in (v for v in ve.values() if v.trang == so_trang):
            x0, y0, x1, y1 = v.to
            c.setFillColorRGB(1, 1, 1)
            c.rect(x0, cao - y1, x1 - x0, y1 - y0, stroke=0, fill=1)
            c.setFillColorRGB(0, 0, 0)
            c.setFont(phong.fontName, v.co)
            c.drawString(v.x, cao - v.chan, v.chu)
        c.showPage()
    c.save()

    phu = PdfReader(BytesIO(buf.getvalue()))
    # Cập nhật TĂNG DẦN: bytes gốc giữ nguyên từng byte, chỉ trang có phép sửa
    # được ghi lại ở phần nối thêm — trang không có phép giống hệt khuôn gốc.
    writer = PdfWriter(reader, incremental=True)
    for lop, so_trang in zip(phu.pages, cac_trang, strict=True):
        trang = writer.pages[so_trang - 1]
        # `merge_page` cắt lớp phủ theo CropBox CỦA LỚP PHỦ (mặc định = media box
        # của nó, gốc 0,0); phải phủ đúng media box trang gốc, kể cả khi lệch gốc.
        lop.mediabox = RectangleObject([float(v) for v in trang.mediabox])
        trang.merge_page(lop)
        trang.compress_content_streams()
    # `merge_page` và `compress_content_streams` mỗi lượt để lại một luồng nội
    # dung KHÔNG nén, không ai trỏ tới; chế độ tăng dần vẫn ghi chúng ra. Đo
    # 2026-09-26: Report_sample 19 trang +422 KB → +105 KB khi bỏ chúng.
    writer.compress_identical_objects(remove_duplicates=False, remove_unreferenced=True)
    ra = BytesIO()
    writer.write(ra)
    logger.info("dien_khuon_pdf: áp %d/%d phép trên %d trang", len(ve), len(phep_sua), len(cac_trang))
    return ra.getvalue(), bao_cao
