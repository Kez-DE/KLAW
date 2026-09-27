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
import math
import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from src.services.doc_tai_lieu import (
    _HAN_CHUYEN_DOI_GIAY,
    ChuyenDoiKhongSanSang,
    KhongDocDuoc,
    LoaiHong,
    TaiLieuDaDoc,
    _giet_sach_nhom,
    _giu_suat_chuyen_doi,
    _mo_pdf,
    _quy_doi_soffice,
)

logger = logging.getLogger(__name__)

# 110 dpi: A4 ra ~909×1286 điểm ảnh — đủ đọc chữ 10pt trên màn hình, mỗi trang
# vài chục KB PNG, cả tài liệu 10 trang vừa một phản hồi.
DPI_TRANG = 110

# Trần khổ trang của chuẩn PDF (ISO 32000-1, phụ lục C): 14400 đơn vị = 200
# inch. Khổ ngoài (0, trần] là tệp hỏng, không phải một khổ để vẽ hay để lưu.
_KHO_TOI_DA_PT = 14400

# ponytail: một trần cạnh dài cho cả tài liệu. Khổ trang do tệp người lạ khai —
# 200 inch ở 110 dpi là 22000×22000 điểm ảnh (~1,4 GB RAM) cho MỖI trang. A3
# (1191 pt) vẫn ra đúng 110 dpi dưới trần này; trang lớn hơn bị hạ dpi đều.
# `pdftoppm` còn tự cắt ở đúng cạnh này (`-W`/`-H`), nên bộ nhớ một trang
# không phụ thuộc phép tính dpi đúng hay sai.
_CANH_TOI_DA_PX = 2400

# ponytail: trần điểm ảnh TỔNG của một lần dựng — `/trang` trả mọi trang trong
# một JSON base64. Mười trang A4/Letter ở 110 dpi (~11,7 Mpx) lọt trần; khổ lớn
# hơn hạ dpi đều cho cả tài liệu. Nâng khi có số đo biểu mẫu khổ lớn thật.
_PX_TAI_LIEU_TOI_DA = 12_000_000

# PNG 8-bit RGB không nén vượt quá ~3 byte/px một chút (một byte lọc mỗi
# dòng, khung zlib). Trong trần điểm ảnh thì không bản dựng nào chạm con số
# này; chạm nghĩa là khổ đã đọc sai, và việc dựng hỏng đóng (fail closed).
_BYTE_ANH_TOI_DA = _PX_TAI_LIEU_TOI_DA * 3 + (1 << 20)

# ponytail: tập trong bộ nhớ, cùng phạm vi tiến trình với `_suat_chuyen_doi`;
# nhiều worker thì mỗi worker một tập — chuyển sang khoá DB khi chạy nhiều tiến
# trình. Giới hạn nhịp trước `/trang` đếm theo IP, nên không có tập này thì một
# tài khoản gọi từ nhiều IP giữ được cả ba suất chung.
_dang_dung: set[str] = set()
_khoa_dang_dung = threading.Lock()


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
    của nó), đảo rộng/cao khi trang khai `/Rotate` 90 hoặc 270.

    Trị tuyệt đối vì poppler lật một hộp khai ngược (`[3000 3000 0 0]`) còn
    pypdf trả rộng/cao âm. Khổ này vừa chặn dpi vừa được lưu vào
    `khuon_goc.kho`, nên nó bị kiểm ở đây — nơi duy nhất sinh ra nó."""
    kho = []
    for trang in _mo_pdf(pdf).pages:
        try:
            rong, cao = abs(float(trang.mediabox.width)), abs(float(trang.mediabox.height))
        except Exception as e:
            # pypdf ném ValueError cho hộp thiếu hay sai số phần tử; bắt rộng
            # cùng lý do `_mo_pdf`: mọi nhánh dẫn tới cùng câu "gửi lại tệp".
            raise KhongDocDuoc(LoaiHong.tep_hong, "khổ trang không đọc được") from e
        # `not 0 < x <= trần` cũng loại NaN/vô cực: mọi phép so với NaN là sai.
        if not (0 < rong <= _KHO_TOI_DA_PT and 0 < cao <= _KHO_TOI_DA_PT):
            raise KhongDocDuoc(LoaiHong.tep_hong, "khổ trang ngoài giới hạn PDF")
        rong, cao = round(rong, 2), round(cao, 2)
        kho.append([cao, rong] if trang.rotation % 180 else [rong, cao])
    return kho


def _dpi_trong_tran(kho: list[list[float]], dpi: int) -> int:
    """dpi lớn nhất ≤ `dpi` giữ cả hai trần: cạnh dài nhất và tổng điểm ảnh."""
    if not kho:
        return dpi
    canh = max(max(k) for k in kho)
    dien_tich = sum(r * c for r, c in kho)
    return max(1, min(dpi, int(_CANH_TOI_DA_PX * 72 / canh), int(72 * math.sqrt(_PX_TAI_LIEU_TOI_DA / dien_tich))))


def anh_trang(pdf: bytes, dpi: int = DPI_TRANG) -> list[bytes]:
    """PNG của từng trang, theo thứ tự trang."""
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        logger.error("dung_trang: máy chủ chưa cài pdftoppm (poppler) — không dựng được ảnh trang")
        raise ChuyenDoiKhongSanSang("khong_co_cong_cu", "chưa cài poppler")
    dpi = _dpi_trong_tran(kho_trang(pdf), dpi)
    canh = str(_CANH_TOI_DA_PX)

    with _giu_suat_chuyen_doi(), tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.Popen(
            [pdftoppm, "-r", str(dpi), "-W", canh, "-H", canh, "-png", "-", str(Path(tmp) / "t")],
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
        tep = sorted(Path(tmp).glob("t-*.png"))
        tong = sum(p.stat().st_size for p in tep)
        if tong > _BYTE_ANH_TOI_DA:
            logger.warning("dung_trang: ảnh trang vượt trần byte (%d trang, %d byte)", len(tep), tong)
            raise KhongDocDuoc(LoaiHong.tep_hong, "ảnh trang vượt trần")
        return [p.read_bytes() for p in tep]


def dung(dinh_dang: str, noi_dung: bytes, user_sub: str) -> tuple[list[list[float]], list[bytes]]:
    """`(khổ, PNG)` từng trang của một khuôn gốc (hay một bản đã điền cùng định
    dạng). Khổ đọc từ CHÍNH PDF vừa vẽ, nên `kho[i]` luôn là khổ của ảnh `i`.

    Một lượt mỗi tài khoản mỗi lúc: lượt thứ hai trong khi lượt đầu còn vẽ là
    `ChuyenDoiKhongSanSang("qua_tai")`, cùng 503 của ba suất chung."""
    with _khoa_dang_dung:
        if user_sub in _dang_dung:
            raise ChuyenDoiKhongSanSang("qua_tai", "tài khoản đang có một lượt dựng trang")
        _dang_dung.add(user_sub)
    try:
        pdf = dung_pdf(noi_dung) if dinh_dang == "docx" else noi_dung
        return kho_trang(pdf), anh_trang(pdf)
    finally:
        with _khoa_dang_dung:
            _dang_dung.discard(user_sub)


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
