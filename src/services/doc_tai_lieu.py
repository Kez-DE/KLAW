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
_DUOI_HO_TRO = (".pdf", ".docx")


class LoaiHong(StrEnum):
    """Mỗi nguyên nhân có ĐÚNG MỘT mã của riêng nó (FR-003)."""

    dinh_dang_khong_ho_tro = "dinh_dang_khong_ho_tro"
    tep_hong = "tep_hong"
    can_mat_khau = "can_mat_khau"
    khong_co_lop_chu = "khong_co_lop_chu"


class KhongDocDuoc(Exception):
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


@dataclass(frozen=True)
class TaiLieuDaDoc:
    don_vi: list[DonViVanBan]
    so_trang: int
    so_ky_tu: int


def doc(ten_tep: str, du_lieu: bytes) -> TaiLieuDaDoc:
    """Đọc `du_lieu` thành các đơn vị văn bản, hoặc ném `KhongDocDuoc`.

    Không ghi tệp ra đĩa ở bất kỳ nhánh nào (FR-022): dữ liệu vào bằng bytes,
    ra bằng dataclass, và người gọi chịu trách nhiệm buông tham chiếu.
    """
    ten = (ten_tep or "").lower()
    if ten.endswith(".pdf"):
        thoi = _doc_pdf(du_lieu)
    elif ten.endswith(".docx"):
        thoi = _doc_docx(du_lieu)
    else:
        raise KhongDocDuoc(
            LoaiHong.dinh_dang_khong_ho_tro,
            f"chỉ hỗ trợ {', '.join(_DUOI_HO_TRO)}",
        )

    if not thoi:
        raise KhongDocDuoc(LoaiHong.khong_co_lop_chu, "không rút được ký tự nào")
    return _dat_vi_tri(thoi)


# ------------------------------------------------------------------------ DOCX


def _doc_docx(du_lieu: bytes) -> list[tuple[int | None, str]]:
    """Mọi `w:p` theo đúng thứ tự tài liệu, kể cả `w:p` nằm trong ô bảng.

    Duyệt thẳng toàn bộ `w:p` là đủ để ô bảng tự tách thành đơn vị riêng, vì
    mỗi ô luôn chứa ít nhất một `w:p`. Không cần xử lý `w:tbl` riêng.
    """
    try:
        with zipfile.ZipFile(BytesIO(du_lieu)) as z:
            xml = z.read("word/document.xml")
    except KeyError as e:
        raise KhongDocDuoc(LoaiHong.tep_hong, "thiếu word/document.xml") from e
    except zipfile.BadZipFile as e:
        # DOCX có mật khẩu là tệp OLE chứ không phải zip, nên rơi vào đây. Không
        # phân biệt được hai ca này nếu không đọc header OLE; báo `tep_hong` là
        # nói đúng những gì biết chắc.
        raise KhongDocDuoc(LoaiHong.tep_hong, "không mở được tệp docx") from e

    try:
        goc = ET.fromstring(xml)
    except ET.ParseError as e:
        raise KhongDocDuoc(LoaiHong.tep_hong, "word/document.xml hỏng") from e

    ra: list[tuple[int | None, str]] = []
    for p in goc.iter(f"{{{_NS['w']}}}p"):
        chu = "".join(t.text or "" for t in p.iter(f"{{{_NS['w']}}}t")).strip()
        if chu:
            ra.append((None, chu))  # trang tính sau, theo KY_TU_MOI_TRANG
    return ra


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


def _dat_vi_tri(thoi: list[tuple[int | None, str]]) -> TaiLieuDaDoc:
    """Gán `trang` và `offset_dau` cho từng đơn vị.

    PDF đã biết trang thật. DOCX chưa, nên trang được suy ra từ số ký tự đã đi
    qua — xem ghi chú ở `KY_TU_MOI_TRANG`.
    """
    don_vi: list[DonViVanBan] = []
    da_di = 0          # ký tự đã đi qua trong toàn tài liệu (nhánh DOCX)
    trang_hien = None
    offset = 0

    for i, (trang, noi_dung) in enumerate(thoi):
        if trang is None:
            trang = 1 + da_di // KY_TU_MOI_TRANG
        if trang != trang_hien:
            trang_hien, offset = trang, 0
        don_vi.append(DonViVanBan(chi_so=i, trang=trang, offset_dau=offset, noi_dung=noi_dung))
        offset += len(noi_dung) + 1   # +1 cho dấu xuống dòng giữa hai đơn vị
        da_di += len(noi_dung) + 1

    so_ky_tu = sum(len(d.noi_dung) for d in don_vi)
    so_trang = max((d.trang for d in don_vi), default=1)
    if thoi and thoi[0][0] is None:   # DOCX: trang là xấp xỉ theo ký tự
        so_trang = max(1, ceil(so_ky_tu / KY_TU_MOI_TRANG))
    return TaiLieuDaDoc(don_vi=don_vi, so_trang=so_trang, so_ky_tu=so_ky_tu)
