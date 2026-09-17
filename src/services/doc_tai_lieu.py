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
import os
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
_DUOI_HO_TRO = (".pdf", ".docx", ".doc", *_DUOI_ANH)

# .doc là OLE2/CFB (Compound File Binary), không phải zip+XML — không đọc trực
# tiếp được bằng `zipfile`. Chuyển sang .docx bằng LibreOffice headless rồi TÁI
# DÙNG `_doc_docx` KHÔNG ĐỔI GÌ: đo trên BM.M05 thật (`.sdd/phase-13-brief.md`),
# vòng .doc -> .docx giữ nguyên số đoạn, số bảng và tỉ lệ cột — viết một bộ đọc
# .doc riêng (kiểu antiword) sẽ vứt bỏ đúng những gì Phase 8/9/11 dựng lên.
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

# LibreOffice là một tiến trình con nhận dữ liệu KHÔNG ĐÁNG TIN (CVE history có
# thật). 60 giây: soffice khởi động nguội mất vài giây, một .doc hợp lệ dưới
# trần TRAN_BYTE (20 MB, `tai_lieu.kiem_kich_thuoc`) chuyển xong trong vài giây
# nữa — một tệp CỐ Ý làm treo bộ phân tích OLE2 phải lộ ra trong một phút, không
# phải đợi hết `_HAN_TREO_GIAY` (300s) vốn đo cho OCR cả trang ảnh, việc nặng
# hơn nhiều lần.
_HAN_CHUYEN_DOI_GIAY = 60

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
    can_le: str = "trai"
    """`trai` | `giua` | `phai` (Phase 9 U5) — căn lề THẬT của đoạn/ô này, đọc
    từ `w:pPr/w:jc` hoặc, khi vắng (nghĩa là "thừa kế"), từ kiểu đoạn văn của
    nó (`w:pStyle`, theo hết chuỗi `w:basedOn`). Mặc định `trai`: DOCX không
    khai báo `jc` là căn trái, không phải "chưa biết" — cùng lý lẽ `vung`
    không được suy diễn thêm gì ngoài những gì tệp nói.
    """
    bang_nhip: int = 1
    """Số cột LƯỚI ô này CHIẾM (Phase 11 R6) — đọc `w:tcPr/w:gridSpan/@w:val`,
    mặc định 1 (không gộp ngang). `bang[2]` (cột) đã là cột lưới THẬT, cộng
    dồn nhịp các ô đứng trước trong CÙNG hàng — không còn là số thứ tự ô đến
    thứ mấy. Cần trường riêng vì một ô gộp 2 cột vẫn CHỈ là một đơn vị (một
    `w:tc`), và số cột nó chiếm là sự thật thứ hai, khác với vị trí nó bắt đầu.
    """
    bang_ti_le: tuple[int, ...] = ()
    """% mỗi cột lưới trên tổng bề rộng BẢNG mà ô này thuộc về (Phase 11 R1),
    đọc từ `w:tblGrid/w:gridCol` — GIỐNG NHAU trên mọi ô của cùng một bảng,
    cùng cách `bang`/`vung` tự mô tả theo từng đơn vị thay vì một bảng tra
    riêng. Rỗng khi bảng không khai `w:tblGrid`: không suy đoán tỉ lệ, để
    phía render tự quyết định (chia đều) — cùng nguyên tắc không suy diễn
    thêm gì ngoài những gì tệp nói.
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
    elif ten.endswith(".doc"):
        # Chuyển trước, đọc sau — bằng ĐÚNG một hàm `_doc_docx`, không nhánh
        # riêng nào biết tệp .docx này từng là .doc.
        thoi = _doc_docx(_chuyen_doc_sang_docx(du_lieu))
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
_PPR = f"{{{_NS['w']}}}pPr"
_JC = f"{{{_NS['w']}}}jc"
_PSTYLE = f"{{{_NS['w']}}}pStyle"
_BASEDON = f"{{{_NS['w']}}}basedOn"
_TCPR = f"{{{_NS['w']}}}tcPr"
_GRIDSPAN = f"{{{_NS['w']}}}gridSpan"
_TBLGRID = f"{{{_NS['w']}}}tblGrid"
_GRIDCOL = f"{{{_NS['w']}}}gridCol"
_STYLE = f"{{{_NS['w']}}}style"

# OOXML `w:jc` → `DonViVanBan.can_le` (Phase 9 U5). Chỉ "center"/"right"/"end"
# đổi khỏi trái: "left"/"start"/"both" (căn đều) và mọi giá trị lạ đọc như
# người xem thường thấy — căn đều trông giống căn trái, không giống căn giữa.
_JC_RA_CAN_LE = {"center": "giua", "right": "phai", "end": "phai"}


def _can_le_gia_tri(v: str | None) -> str:
    return _JC_RA_CAN_LE.get(v or "", "trai")


def _kieu_can_le(goc_styles: ET.Element | None) -> dict[str, str]:
    """id kiểu đoạn văn → giá trị `w:jc` THẬT của kiểu đó, đã theo hết chuỗi
    `w:basedOn` — `styles.xml` có thể vắng mặt (DOCX không bắt buộc phần này),
    và một kiểu có thể không tự khai `jc` mà thừa kế từ kiểu nó dựa vào."""
    if goc_styles is None:
        return {}
    truc_tiep: dict[str, str] = {}
    cha: dict[str, str] = {}
    for st in goc_styles.findall(_STYLE):
        sid = st.get(f"{{{_NS['w']}}}styleId")
        if not sid:
            continue
        b = st.find(_BASEDON)
        if b is not None and (v := b.get(f"{{{_NS['w']}}}val")):
            cha[sid] = v
        jc = st.find(f"{_PPR}/{_JC}")
        if jc is not None and (v := jc.get(f"{{{_NS['w']}}}val")):
            truc_tiep[sid] = v

    def _giai(sid: str | None, di_qua: frozenset[str]) -> str | None:
        if sid is None or sid in di_qua:
            return None
        if sid in truc_tiep:
            return truc_tiep[sid]
        return _giai(cha.get(sid), di_qua | {sid})

    return {sid: v for sid in {*truc_tiep, *cha} if (v := _giai(sid, frozenset()))}


def _can_le_doan(p: ET.Element | None, theo_kieu: dict[str, str]) -> str:
    """Căn lề THẬT của một `w:p` — trực tiếp (`w:pPr/w:jc`) nếu có; vắng mặt
    thì theo kiểu đoạn văn của nó (`w:pStyle`, đã giải qua `_kieu_can_le`),
    KHÔNG mặc định trái ngay: `jc` vắng mặt trên `w:p` nghĩa là "thừa kế kiểu",
    và một tài liệu căn giữa bằng KIỂU (không phải định dạng trực tiếp) đọc
    thẳng `jc` trên từng đoạn sẽ luôn ra trái, sai với chính tài liệu đó."""
    if p is None:
        return "trai"
    jc = p.find(f"{_PPR}/{_JC}")
    if jc is not None:
        return _can_le_gia_tri(jc.get(f"{{{_NS['w']}}}val"))
    kieu = p.find(f"{_PPR}/{_PSTYLE}")
    sid = kieu.get(f"{{{_NS['w']}}}val") if kieu is not None else None
    return _can_le_gia_tri(theo_kieu.get(sid) if sid else None)


def _nhip_o(tc: ET.Element) -> int:
    """Số cột lưới một Ô CHIẾM (Phase 11 R6) — `w:tcPr/w:gridSpan/@w:val`, mặc
    định 1. Đọc trực tiếp thay vì suy từ số ô trong hàng: một hàng ngắn hơn
    hàng tiêu đề có thể là do MỘT ô gộp (nhịp > 1) hoặc do các ô cuối THẬT SỰ
    không tồn tại (đã đọc hết, không còn `w:tc` nào) — hai ca khác nhau, và chỉ
    tệp mới nói được ca nào đang xảy ra, không phải phép đếm chênh lệch."""
    gs = tc.find(f"{_TCPR}/{_GRIDSPAN}")
    if gs is None:
        return 1
    try:
        n = int(gs.get(f"{{{_NS['w']}}}val") or "1")
    except ValueError:
        return 1
    return n if n > 0 else 1


def _ti_le_luoi(tbl: ET.Element) -> tuple[int, ...]:
    """% mỗi cột lưới trên tổng bề rộng BẢNG — `w:tblGrid/w:gridCol` (Phase 11
    R1). Rỗng khi bảng không khai lưới; phía render tự quyết định chia đều,
    không suy đoán tỉ lệ ở đây.

    Làm tròn TỪNG cột ĐỘC LẬP theo tổng của chính bảng đó — `sum(gridCol)`
    không nhất thiết bằng bề rộng thân trang (đo trên form thật: 10371/9062/
    8950 twips cho một thân 9072 twips, đây là ca THƯỜNG chứ không phải ca
    hiếm), nên phép quy đổi luôn tính theo TỔNG của chính bảng. Không dồn phần
    dư làm tròn vào cột nào: tổng các % có thể lệch 100 một chút (vd 101, đo
    được trên BM.ĐT.18.05 — 7/15/30/34/15), và một cột lệch 1% không đáng để
    đổi số đo trực tiếp của MỘT cột thành số đã bị nắn cho tổng tròn.
    """
    grid = tbl.find(_TBLGRID)
    if grid is None:
        return ()
    rong = [v for g in grid.findall(_GRIDCOL) if (w := g.get(f"{{{_NS['w']}}}w")) and (v := int(w)) > 0]
    tong = sum(rong)
    if not rong or tong <= 0:
        return ()
    return tuple(round(w * 100 / tong) for w in rong)


def _kiem_zip(z: zipfile.ZipFile) -> None:
    """Phanh zip bom, chạy TRƯỚC khi đọc bất kỳ mục nào — xem `TRAN_SO_MUC_ZIP`."""
    muc = z.infolist()
    if len(muc) > TRAN_SO_MUC_ZIP:
        raise KhongDocDuoc(LoaiHong.tep_hong, f"tệp docx có quá {TRAN_SO_MUC_ZIP} mục")
    if sum(m.file_size for m in muc) > TRAN_GIAI_NEN_BYTE:
        raise KhongDocDuoc(LoaiHong.tep_hong, "tệp docx giải nén ra quá lớn")


_MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"


def _bo_fallback(goc: ET.Element) -> ET.Element:
    """Bỏ `mc:Fallback`. `mc:AlternateContent` mang CÙNG một nội dung hai lần —
    `Choice` cho Word mới, `Fallback` cho Word cũ — nên đọc cả hai là đọc
    "Phụ lục 4" thành "Phụ lục 4Phụ lục 4" (đo trên tệp thật 2026-09-16), và
    mọi phép so độ dài phía sau đều lệch theo."""
    for cha in list(goc.iter()):
        for con in [c for c in cha if c.tag == _MC_FALLBACK]:
            cha.remove(con)
    return goc


def _tong_chu(nut: ET.Element) -> int:
    """Tổng ký tự `w:t` dưới `nut`, mỗi `w:t` đếm đúng một lần."""
    return sum(len((t.text or "").strip()) for t in nut.iter(f"{{{_NS['w']}}}t"))


def _goc_xml(xml: bytes, ten: str) -> ET.Element:
    try:
        return ET.fromstring(xml)
    except ET.ParseError as e:
        raise KhongDocDuoc(LoaiHong.tep_hong, f"{ten} hỏng") from e


def _chu(nut: ET.Element) -> str:
    return "".join(t.text or "" for t in nut.iter(f"{{{_NS['w']}}}t")).strip()


def _duyet_phang(goc: ET.Element, vung: str, theo_kieu: dict[str, str] | None = None) -> list[tuple]:
    """Mọi `w:p` theo thứ tự tài liệu, KHÔNG toạ độ bảng.

    Vừa là đường lùi của thân bài, vừa là đường duy nhất cho đầu/chân trang —
    ở đó một `w:p` là một dòng và không có gì để định vị thêm.
    """
    tk = theo_kieu or {}
    return [(None, c, None, vung, None, _can_le_doan(p, tk)) for p in goc.iter(_P) if (c := _chu(p))]


def _duyet_than(goc: ET.Element, theo_kieu: dict[str, str] | None = None) -> list[tuple]:
    """Con trực tiếp của `w:body` theo thứ tự: `w:p` là một đơn vị, `w:tbl` cho
    một đơn vị mỗi ô kèm toạ độ (bảng, hàng, cột).

    Chữ của một ô là các `w:p` TRONG ô nối bằng một dấu cách — kể cả `w:p` của
    bảng lồng bên trong. Bảng lồng không được đánh số riêng: nó là chi tiết
    trình bày của ô bao ngoài, và tách ra thì "hàng 2 cột 1" của người đọc trỏ
    vào một bảng họ không nhìn thấy.

    Cột (Phase 11 R6) là cột LƯỚI THẬT — cộng dồn nhịp (`w:gridSpan`) của các
    ô đứng TRƯỚC nó trong cùng hàng, không phải số thứ tự ô thứ mấy. Con trỏ
    cột đi qua CẢ ô rỗng chữ (để nhịp của nó vẫn được cộng dồn cho ô sau) — chỉ
    đơn vị (dòng `ra.append`) mới bỏ qua ô rỗng, đúng hành vi trước Phase 11.
    """
    than = goc.find(_BODY)
    if than is None:
        return []
    tk = theo_kieu or {}
    ra: list[tuple] = []
    so_bang = 0
    for con in than:
        if con.tag == _P:
            if chu := _chu(con):
                ra.append((None, chu, None, "than", None, _can_le_doan(con, tk)))
        elif con.tag == _TBL:
            ti_le = _ti_le_luoi(con)
            for h, tr in enumerate(con.findall(_TR)):
                cot = 0
                for tc in tr.findall(_TC):
                    nhip = _nhip_o(tc)
                    c = cot
                    cot += nhip
                    # Phase 11 fix round 2 — GIỮ ô rỗng chữ, không bỏ qua như
                    # một đoạn văn rỗng. Một phiếu TRẮNG (biểu mẫu để trống
                    # cho người điền tay) có những HÀNG toàn ô rỗng — bỏ qua
                    # chúng thì `don_vi` không còn dấu vết những hàng đó tồn
                    # tại, và `hieu_tai_lieu._bang_theo_nhan` dựng lại bảng chỉ
                    # thấy đúng hàng tiêu đề (đo được thật: 5 hàng nguồn, 1
                    # hàng dựng lại). Ô rỗng CŨNG là ý nghĩa của biểu mẫu —
                    # cùng nguyên tắc dấu chấm điền của một dòng trường tự do,
                    # chỉ khác hình dạng (một Ô thay vì một cụm ký tự).
                    chu = " ".join(x for p in tc.iter(_P) if (x := _chu(p)))
                    # Căn lề của Ô lấy từ ĐOẠN VĂN ĐẦU của chính ô đó — một
                    # ô có thể có nhiều `w:p` lồng, nhưng căn lề hiển thị
                    # là của dòng đầu tiên người đọc thấy.
                    can_le = _can_le_doan(tc.find(_P), tk)
                    ra.append((None, chu, None, "than", (so_bang, h, c), can_le, nhip, ti_le))
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
            goc = _bo_fallback(_goc_xml(z.read("word/document.xml"), "word/document.xml"))
            # Căn lề theo KIỂU (Phase 9 U5) — `styles.xml` không bắt buộc có
            # trong một DOCX hợp lệ, và hỏng ở đó không được làm hỏng cả tài
            # liệu: mất căn lề theo kiểu là khoản lỗ sống chung được (`jc` trực
            # tiếp trên từng đoạn vẫn đọc đúng), mất nguyên một điều khoản thì
            # không.
            theo_kieu: dict[str, str] = {}
            if "word/styles.xml" in z.namelist():
                try:
                    theo_kieu = _kieu_can_le(_goc_xml(z.read("word/styles.xml"), "word/styles.xml"))
                except KhongDocDuoc:
                    theo_kieu = {}
            than = _duyet_than(goc, theo_kieu)
            # Thước đo để lùi về là TỔNG chữ `w:t` của thân, KHÔNG phải duyệt
            # phẳng: duyệt phẳng đếm hai lần chữ trong hộp chữ (một `w:p` lồng
            # trong `w:p`), và với thước đó cấu trúc luôn "thua". Đo 2026-09-16
            # trên một kế hoạch thực tập: ba bảng mất toạ độ vì hai chữ "Phụ lục 4".
            nut_than = goc.find(_BODY)
            tong = _tong_chu(nut_than) if nut_than is not None else 0
            if sum(len(t[1]) for t in than) < 0.9 * tong:
                than = _duyet_phang(goc, "than", theo_kieu)

            ra = list(than)
            for tien_to, vung in (("word/header", "dau_trang"), ("word/footer", "chan_trang")):
                for ten in sorted(n for n in z.namelist() if n.startswith(tien_to) and n.endswith(".xml")):
                    ra.extend(_duyet_phang(_goc_xml(z.read(ten), ten), vung, theo_kieu))
            return ra
    except KeyError as e:
        raise KhongDocDuoc(LoaiHong.tep_hong, "thiếu word/document.xml") from e
    except zipfile.BadZipFile as e:
        # DOCX có mật khẩu là tệp OLE chứ không phải zip, nên rơi vào đây. Không
        # phân biệt được hai ca này nếu không đọc header OLE; báo `tep_hong` là
        # nói đúng những gì biết chắc.
        raise KhongDocDuoc(LoaiHong.tep_hong, "không mở được tệp docx") from e


# ------------------------------------------------------------------------- DOC


def _duong_soffice() -> str | None:
    """Đường dẫn `soffice`. `KLAW_SOFFICE_PATH` (Settings) THẮNG dò theo PATH —
    máy dev, CI và container triển khai không chắc cài LibreOffice ở cùng một
    chỗ, cùng cách mọi công cụ ngoài khác của dự án đọc qua Settings thay vì
    một hằng số cứng. `None` khi cả hai đều không ra gì — người gọi phải báo
    lỗi rõ ràng, không được thử gọi một chuỗi rỗng làm lệnh."""
    from src.config import get_settings

    return get_settings().soffice_path or shutil.which("soffice")


def _la_ole2(du_lieu: bytes) -> bool:
    """8 byte đầu của container OLE2/CFB — .doc, .xls, .ppt (bản cũ) đều dùng
    chung. Không đọc sâu hơn (thư mục CFB) để biết đây có đúng là Word hay
    không: một .xls/.ppt đổi đuôi thành .doc qua được cửa này, nhưng KHÔNG qua
    được bộ chuyển đổi phía dưới — soffice mở nó bằng Calc/Impress rồi không
    xuất được sang khuôn Writer (.docx), và việc đó tự rơi vào nhánh `tep_hong`.
    Viết thêm một bộ phân tích CFB chỉ để bắt sớm hơn một chế độ hỏng vốn đã bị
    chặn là dư."""
    return du_lieu[:8] == _OLE2_MAGIC


def _chuyen_doc_sang_docx(du_lieu: bytes) -> bytes:
    """.doc (OLE2) -> bytes .docx, bằng LibreOffice headless.

    Ba điều làm tiến trình con này an toàn với dữ liệu người dùng:

    - Hồ sơ (`-env:UserInstallation`) RIÊNG cho MỖI lần gọi, trong chính thư
      mục tạm sắp bị xoá — hồ sơ mặc định DÙNG CHUNG là nguồn lỗi đã biết "lần
      chuyển đổi thứ hai lặng lẽ không làm gì" khi hai tiến trình soffice đụng
      khoá cùng một hồ sơ.
    - TRẦN THỜI GIAN cứng (`_HAN_CHUYEN_DOI_GIAY`) — một .doc cố ý làm treo bộ
      phân tích OLE2 phải hỏng việc đọc, không được treo cả request.
    - MÔI TRƯỜNG tối giản — tiến trình con KHÔNG thừa hưởng biến môi trường của
      ứng dụng (API key, secrets khác). Không có cách tắt macro bằng cờ dòng
      lệnh, nhưng một hồ sơ MỚI TOANH giữ mức an toàn macro mặc định "Trung
      bình" (hỏi trước khi chạy) — ở chế độ headless không có hộp thoại nào để
      lỡ tay bấm "Đồng ý", nên macro không tự chạy được; môi trường tối giản
      thêm một lớp nữa: dù có gì chạy được, không có mạng và không có gì đáng
      lấy trộm trong biến môi trường.

    Tệp .doc và .docx tạm đều nằm trong MỘT thư mục do
    `tempfile.TemporaryDirectory` dựng và tự xoá khi hàm kết thúc — kể cả khi
    kết thúc bằng lỗi. Không nhánh nào để lại tệp trên đĩa (FR-022 áp dụng cho
    cả bản chuyển đổi: nó vẫn là bytes gốc của người dùng, chỉ khác lớp vỏ).
    """
    if not _la_ole2(du_lieu):
        raise KhongDocDuoc(LoaiHong.tep_hong, "tệp .doc không đúng định dạng OLE2")

    soffice = _duong_soffice()
    if not soffice:
        raise KhongDocDuoc(
            LoaiHong.khong_co_lop_chu,
            "máy chủ chưa cài LibreOffice, chưa chuyển đổi được tệp .doc",
        )

    from pathlib import Path as _P  # noqa: N814 — cùng cách `_ocr_pdf` làm

    with tempfile.TemporaryDirectory() as tmp:
        thu_muc = _P(tmp)
        vao = thu_muc / "vao.doc"
        vao.write_bytes(du_lieu)
        moi_truong = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmp}
        try:
            kq = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--invisible",
                    "--nocrashreport",
                    "--nodefault",
                    "--nofirststartwizard",
                    "--nolockcheck",
                    "--nologo",
                    "--norestore",
                    f"-env:UserInstallation=file://{thu_muc / 'ho_so'}",
                    "--convert-to",
                    "docx:MS Word 2007 XML",
                    "--outdir",
                    tmp,
                    str(vao),
                ],
                capture_output=True,
                timeout=_HAN_CHUYEN_DOI_GIAY,
                env=moi_truong,
            )
        except subprocess.TimeoutExpired as e:
            raise KhongDocDuoc(LoaiHong.tep_hong, "chuyển đổi tệp .doc quá lâu") from e

        ra = thu_muc / "vao.docx"
        if kq.returncode != 0 or not ra.exists():
            logger.warning(
                "doc_tai_lieu: soffice không chuyển được .doc (mã %s): %s",
                kq.returncode,
                kq.stderr.decode("utf-8", errors="replace")[:500],
            )
            raise KhongDocDuoc(LoaiHong.tep_hong, "không chuyển đổi được tệp .doc")

        return ra.read_bytes()


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

    Nhận cả năm hình dạng: `(trang, noi_dung)` từ nhánh đọc chữ thật,
    `(trang, noi_dung, do_tin)` từ nhánh OCR,
    `(trang, noi_dung, do_tin, vung, bang)` từ DOCX trước Phase 9,
    `(trang, noi_dung, do_tin, vung, bang, can_le)` từ DOCX có căn lề (Phase 9
    U5), và `(…, can_le, bang_nhip, bang_ti_le)` từ một Ô BẢNG có lưới (Phase
    11 R1/R6). Có `do_tin` nghĩa là máy đang đoán, nên đơn vị đó mang nhãn
    `ocr`.

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
        can_le = muc[5] if len(muc) > 5 else "trai"
        bang_nhip = muc[6] if len(muc) > 6 else 1
        bang_ti_le = muc[7] if len(muc) > 7 else ()
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
                can_le=can_le,
                bang_nhip=bang_nhip,
                bang_ti_le=bang_ti_le,
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
