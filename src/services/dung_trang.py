"""Dựng trang của khuôn gốc — quyết định 2026-09-26
(`docs/decisions/2026-09-26-luu-khuon-goc-va-dien-tai-cho.md`).

Khuôn gốc (`CONTEXT.md`) là chính tệp khách tải lên: `.docx`, `.doc` giữ dưới
dạng `.docx` đã quy đổi, hoặc PDF. "Bản tải lên" hiện bằng CHÍNH tệp đó:
LibreOffice dàn trang docx ra PDF, `pdftoppm` vẽ PDF ra PNG từng trang, giữ khổ
giấy gốc (Letter vẫn là Letter). Số trang của tài liệu là số trang PDF đó — dàn
trang thật, không phải số ngắt trang tệp tự khai.

Cả hai công cụ nhận dữ liệu KHÔNG ĐÁNG TIN, nên đi qua đúng hộp cát của `.doc`
(`doc_tai_lieu._quy_doi_soffice`, `_giet_sach_nhom`): thư mục tạm tự xoá, môi
trường tối giản, nhóm tiến trình riêng, trần thời gian. Log chỉ mang mã thoát.

Không lưu PDF hay PNG đã dựng: dựng lại mỗi lần cần (ponytail: thêm bảng đệm
khi một lần dựng đo được là quá chậm).
"""

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.services.doc_tai_lieu import (
    _HAN_CHUYEN_DOI_GIAY,
    ChuyenDoiKhongSanSang,
    KhongDocDuoc,
    LoaiHong,
    TaiLieuDaDoc,
    _giet_sach_nhom,
    _mo_pdf,
    _quy_doi_soffice,
)

logger = logging.getLogger(__name__)

# 110 dpi: A4 ra ~909×1286 điểm ảnh — đủ đọc chữ 10pt trên màn hình, mỗi trang
# vài chục KB PNG, cả tài liệu 10 trang vừa một phản hồi.
DPI_TRANG = 110

# ponytail: một trần cạnh dài cho cả tài liệu. Khổ trang do tệp người lạ khai —
# 200 inch ở 110 dpi là 22000×22000 điểm ảnh (~1,4 GB RAM) cho MỖI trang. A3
# (1191 pt) vẫn ra đúng 110 dpi dưới trần này; trang lớn hơn bị hạ dpi đều.
_CANH_TOI_DA_PX = 2400


@dataclass(frozen=True)
class KhuonGoc:
    dinh_dang: str
    """`docx` | `pdf` — đúng `ck_khuon_goc_dinh_dang` của migration 036."""
    noi_dung: bytes
    kho: list[list[float]]
    """`[rộng_pt, cao_pt]` của TỪNG trang bản dựng."""

    @property
    def so_trang(self) -> int:
        return len(self.kho)


def dung_pdf(docx: bytes) -> bytes:
    """`.docx` → PDF bằng LibreOffice, trong một suất chung với `.doc`."""
    return _quy_doi_soffice(docx, "vao.docx", "pdf:writer_pdf_Export", "vao.pdf")


def so_trang_pdf(pdf: bytes) -> int:
    return len(_mo_pdf(pdf).pages)


def kho_trang(pdf: bytes) -> list[list[float]]:
    """Khổ từng trang theo điểm, ĐÚNG chiều `pdftoppm` vẽ: hộp media (mặc định
    của nó), đảo rộng/cao khi trang khai `/Rotate` 90 hoặc 270."""
    kho = []
    for trang in _mo_pdf(pdf).pages:
        rong, cao = round(float(trang.mediabox.width), 2), round(float(trang.mediabox.height), 2)
        kho.append([cao, rong] if trang.rotation % 180 else [rong, cao])
    return kho


def anh_trang(pdf: bytes, dpi: int = DPI_TRANG) -> list[bytes]:
    """PNG của từng trang, theo thứ tự trang."""
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        logger.error("dung_trang: máy chủ chưa cài pdftoppm (poppler) — không dựng được ảnh trang")
        raise ChuyenDoiKhongSanSang("khong_co_cong_cu", "chưa cài poppler")
    canh = max((max(k) for k in kho_trang(pdf)), default=0)
    if canh * dpi / 72 > _CANH_TOI_DA_PX:
        dpi = max(1, int(_CANH_TOI_DA_PX * 72 / canh))

    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.Popen(
            [pdftoppm, "-r", str(dpi), "-png", "-", str(Path(tmp) / "t")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmp},
            start_new_session=True,
        )
        try:
            proc.communicate(input=pdf, timeout=_HAN_CHUYEN_DOI_GIAY)
        except subprocess.TimeoutExpired as e:
            _giet_sach_nhom(proc)
            raise KhongDocDuoc(LoaiHong.tep_hong, "dựng ảnh trang quá lâu") from e
        if proc.returncode != 0:
            # Chỉ mã thoát: stderr của pdftoppm có thể trích lại nội dung tệp.
            logger.warning("dung_trang: pdftoppm hỏng (mã thoát %s)", proc.returncode)
            raise KhongDocDuoc(LoaiHong.tep_hong, "không dựng được ảnh trang")
        # pdftoppm đệm số theo trang cuối (`t-01`…`t-10`), nên thứ tự chuỗi
        # trùng thứ tự trang.
        return [p.read_bytes() for p in sorted(Path(tmp).glob("t-*.png"))]


def dung(dinh_dang: str, noi_dung: bytes) -> tuple[list[list[float]], list[bytes]]:
    """`(khổ, PNG)` từng trang của một khuôn gốc (hay một bản đã điền cùng định
    dạng). Khổ đọc từ CHÍNH PDF vừa vẽ, nên `kho[i]` luôn là khổ của ảnh `i`."""
    pdf = dung_pdf(noi_dung) if dinh_dang == "docx" else noi_dung
    return kho_trang(pdf), anh_trang(pdf)


def khuon_goc(ten_tep: str, du_lieu: bytes, tai_lieu: TaiLieuDaDoc) -> KhuonGoc | None:
    """Khuôn gốc của một tệp vừa đọc xong, kèm khổ từng trang dàn thật.

    `None` với ảnh: ảnh giữ đường OCR hôm nay, ngoài phạm vi quyết định.
    `.doc` lấy bản `.docx` `doc()` đã quy đổi, không quy đổi lần hai.
    """
    ten = (ten_tep or "").lower()
    if ten.endswith(".pdf"):
        return KhuonGoc("pdf", du_lieu, kho_trang(du_lieu))
    if ten.endswith((".docx", ".doc")):
        docx = tai_lieu.docx_quy_doi or du_lieu
        return KhuonGoc("docx", docx, kho_trang(dung_pdf(docx)))
    return None
