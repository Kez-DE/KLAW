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
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from src.services.dien_khuon import O_MAU_DO, O_URI
from src.services.dien_khuon_pdf import _khung
from src.services.doc_tai_lieu import (
    _HAN_CHUYEN_DOI_GIAY,
    ChuyenDoiKhongSanSang,
    KhongDocDuoc,
    LoaiHong,
    TaiLieuDaDoc,
    _cung_dong,
    _giet_sach_nhom,
    _giu_suat_chuyen_doi,
    _mo_pdf,
    _quy_doi_soffice,
    _quy_doi_soffice_kem,
    _tu_pdf,
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


def dung_pdf_kem(docx: bytes, do: bytes) -> tuple[bytes, bytes | None]:
    """`dung_pdf` của bản sạch VÀ bản dò (`dien_khuon.danh_dau_docx`) trong MỘT
    lượt LibreOffice — một suất, một lần khởi động: hai tệp một lượt đo 1,4–1,7 s,
    bằng một tệp (tám biểu mẫu, 2026-09-27). Bản dò không ra được thì `None`."""
    sach, ban_do = _quy_doi_soffice_kem(
        "pdf:writer_pdf_Export", (docx, "vao.docx", "vao.pdf"), (do, "do.docx", "do.pdf")
    )
    return sach, ban_do


ViTri = dict[tuple[int, int], tuple[int, list[float]]]
"""`(don_vi, so)` → `(trang, hop)`: chỉ số trang từ 0, hộp `[x0, y0, x1, y1]` bằng
điểm, gốc trên-trái của trang — cùng hệ `kho` và hộp của bộ đọc PDF."""


def vi_tri_o(pdf: bytes, pdf_do: bytes) -> ViTri:
    """Vị trí mỗi ô trên bản SẠCH `pdf`, đo bằng bản DÒ `pdf_do` của cùng phiên
    bản.

    Liên kết của bản dò đổi cách LibreOffice ngắt dòng ở ranh giới của nó
    (BM.M05: "Khoa .……" xuống một dòng khác, mọi dòng dưới lệch theo), nên hộp
    `/Link` không dùng thẳng được cho trang sạch. Chữ hai bản thì là MỘT chuỗi
    (đo trên tám biểu mẫu, trước và sau khi điền): ký tự trong hộp liên kết của
    bản dò được tìm lại theo thứ tự trên bản sạch (`pdftotext -tsv`), và hộp là
    phần của chúng trên dòng ĐẦU. Hai chuỗi khác nhau thì không định vị ô nào —
    không đoán. Chỗ `o` (ô rỗng) không có ký tự: hộp NỀN mốc của ô trên bản dò
    (`_nen_o`) dùng thẳng khi chữ phía trên ô không lệch (`_chuyen_vi_tri`)."""
    lien_ket, nen = _lien_ket_o(pdf_do), _nen_o(pdf_do)
    return _chuyen_vi_tri(lien_ket, _tu_pdf(pdf), _tu_pdf(pdf_do), nen) if lien_ket or nen else {}


def _hien_thi(khung: tuple, x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, float, float]:
    """Hộp hệ người dùng → hệ hiển thị gốc trên-trái (`/MediaBox`, `/Rotate` —
    nghịch đảo `dien_khuon_pdf._khung`)."""
    (a, b, c, d, e, f), _, cao = khung
    diem = [(a * (u - e) + b * (v - f), cao - (c * (u - e) + d * (v - f))) for u, v in ((x0, y0), (x1, y1))]
    (xa, xb), (ya, yb) = sorted(p[0] for p in diem), sorted(p[1] for p in diem)
    return xa, ya, xb, yb


# Toán tử tô của PDF (ISO 32000-1 §8.5.3.3): kết thúc đường đi bằng một lần tô.
_TO = {b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}


def _nen_o(pdf: bytes) -> dict[tuple[int, int], tuple[int, tuple[float, ...]]]:
    """Hình chữ nhật tô màu mốc `dien_khuon.mau_o` của bản dò → `{(don_vi, 0):
    (trang, hộp)}`, hộp hệ hiển thị; LibreOffice vẽ nền ô thành `r g b rg`, `x y w
    h re`, `f*` (đo 26.2.4). Màu theo `q`/`Q`; `re` qua ma trận hiện hành.

    ponytail: chỉ `rg` (DeviceRGB) và `re`; nền vẽ bằng đường `m`/`l` hay không
    gian màu khác thì ô "chưa định vị" (fail closed) — đọc thêm khi một bản
    LibreOffice khác đo ra thế."""
    ra: dict[tuple[int, int], tuple[int, tuple[float, ...]]] = {}
    for i, trang in enumerate(_mo_pdf(pdf).pages):
        khung = _khung(trang)
        if khung is None:
            continue
        mau: list[tuple[int, ...] | None] = [None]
        cho: list[tuple[float, ...]] = []

        def _xem(op, so, cm, _tm, khung=khung, i=i, mau=mau, cho=cho) -> None:
            if op == b"q":
                mau.append(mau[-1])
            elif op == b"Q" and len(mau) > 1:
                mau.pop()
            elif op == b"rg" and len(so) == 3:
                mau[-1] = tuple(round(float(v) * 255) for v in so)
            elif op == b"re" and len(so) == 4:
                x, y, w, h = (float(v) for v in so)
                a, b, c, d, e, f = (float(v) for v in cm)
                goc = [(a * u + c * v + e, b * u + d * v + f) for u, v in ((x, y), (x + w, y + h))]
                cho.append((*goc[0], *goc[1]))
            elif op in _TO:
                if (m := mau[-1]) and m[0] == O_MAU_DO:
                    for x0, y0, x1, y1 in cho:
                        ra.setdefault(((m[1] << 8) | m[2], 0), (i, _hien_thi(khung, x0, y0, x1, y1)))
                cho.clear()
            elif op in (b"n", b"S", b"s"):
                cho.clear()

        try:
            trang.extract_text(visitor_operand_before=_xem)
        except Exception:
            # Bắt rộng cùng lý do `_mo_pdf`: nền ô không đọc được không được làm
            # mất vị trí các ô chấm/tab của cùng bản dò.
            logger.warning("dung_trang: không đọc được nền ô trang %d của bản dò", i + 1)
    return ra


def _lien_ket_o(pdf: bytes) -> dict[tuple[int, int], list[tuple[int, tuple[float, ...]]]]:
    """`/Link` trỏ tới `O_URI{don_vi}/{so}` → `[(trang, hộp)]` theo thứ tự trang,
    hộp đổi từ hệ người dùng về hệ hiển thị gốc trên-trái (`_hien_thi`). Một ô vắt
    qua dòng có nhiều hộp."""
    ra: dict[tuple[int, int], list[tuple[int, tuple[float, ...]]]] = {}
    for i, trang in enumerate(_mo_pdf(pdf).pages):
        khung = _khung(trang)
        if khung is None:
            continue
        for chu_thich in trang.get("/Annots") or []:
            chu_thich = chu_thich.get_object()
            hanh_dong = chu_thich.get("/A")
            uri = hanh_dong.get_object().get("/URI") if hanh_dong is not None else None
            if chu_thich.get("/Subtype") != "/Link" or not isinstance(uri, str) or not uri.startswith(O_URI):
                continue
            try:
                khoa = tuple(int(x) for x in uri[len(O_URI) :].split("/"))
                x0, y0, x1, y1 = (float(v) for v in chu_thich["/Rect"])
            except (KeyError, TypeError, ValueError):
                continue
            if len(khoa) != 2:
                continue
            ra.setdefault(khoa, []).append((i, _hien_thi(khung, x0, y0, x1, y1)))
    return ra


def _chu_theo_ky_tu(tu: dict) -> tuple[str, list[tuple[int, int, int, tuple[float, ...]]]]:
    """Chuỗi ký tự không trắng của cả PDF theo thứ tự `pdftotext`, và cho mỗi
    ký tự `(trang, ký tự đầu của từ, số ký tự của từ, hộp từ)`."""
    chu, ra = [], []
    for trang in sorted(tu):
        for _, tu_, hop in tu[trang]:
            s = "".join(tu_.split())
            dau = len(ra)
            chu.append(s)
            ra += [(trang - 1, dau, len(s), hop)] * len(s)
    return "".join(chu), ra


# Hai bản dựng của CÙNG một dàn trang lệch nhau dưới một điểm (G1: ≤ 1 px ở
# 110 dpi); một dòng ngắt khác lệch cả một dòng (≥ 10 pt).
_LECH_TOI_DA_PT = 1.0


def _chuyen_vi_tri(lien_ket: dict, tu_sach: dict, tu_do: dict, nen: dict | None = None) -> ViTri:
    """Hộp liên kết của bản dò → hộp trên bản sạch, theo chỉ số ký tự (xem
    `vi_tri_o`). Ký tự của một từ lấy phần bề rộng chia đều (poppler chỉ cho hộp
    TỪ); từ giữ nguyên ranh giới ở bản sạch thì phần hộp liên kết trong từ được
    dời nguyên văn — chính xác, không chia đều.

    `nen` (`_nen_o`): hộp nền của chỗ `o` trên bản dò, dùng NGUYÊN khi mọi từ của
    trang đó mà đỉnh nằm trên đáy ô đứng đúng chỗ ở bản sạch (≤ `_LECH_TOI_DA_PT`,
    cùng trang): nền không đổi dàn trang, nên chỉ một liên kết phía trên ngắt dòng
    khác mới dời được ô — khi đó ô "chưa định vị", không đoán."""
    chu_sach, sach = _chu_theo_ky_tu(tu_sach)
    chu_do, do = _chu_theo_ky_tu(tu_do)
    if chu_sach != chu_do:
        logger.warning(
            "dung_trang: chữ bản dò khác bản sạch (%d/%d ký tự) — không định vị ô", len(chu_do), len(chu_sach)
        )
        return {}
    theo_trang: dict[int, list[int]] = {}
    for k, (trang, dau, _, _) in enumerate(do):
        if k == dau:
            theo_trang.setdefault(trang, []).append(k)
    ra: ViTri = {}
    for khoa, cac_hop in lien_ket.items():
        manh: list[tuple[int, tuple[float, ...]]] = []
        for trang, lk in cac_hop:
            for dau in theo_trang.get(trang, []):
                _, _, n, h = do[dau]
                if not (h[0] < lk[2] and lk[0] < h[2] and lk[1] <= (h[1] + h[3]) / 2 <= lk[3]):
                    continue
                for m in range(n):
                    if not lk[0] <= h[0] + (h[2] - h[0]) * (m + 0.5) / n <= lk[2]:
                        continue
                    trang_s, dau_s, n_s, hs = sach[dau + m]
                    if (dau_s, n_s) == (dau, n):  # cùng từ: dời phần hộp liên kết nguyên văn
                        x0, x1 = max(lk[0], h[0]) - h[0] + hs[0], min(lk[2], h[2]) - h[0] + hs[0]
                    else:
                        x0 = hs[0] + (hs[2] - hs[0]) * (dau + m - dau_s) / n_s
                        x1 = hs[0] + (hs[2] - hs[0]) * (dau + m - dau_s + 1) / n_s
                    manh.append((dau + m, (trang_s, x0, hs[1], min(x1, hs[2]), hs[3])))
        if not manh:
            continue
        trang_s, *dong = min(manh)[1]
        x0, y0, x1, y1 = zip(*(p[1:] for _, p in manh if p[0] == trang_s and _cung_dong(p[1:], dong)), strict=True)
        ra[khoa] = (trang_s, [round(v, 2) for v in (min(x0), min(y0), max(x1), max(y1))])
    for khoa, (trang, hop) in (nen or {}).items():
        tren = [k for k in theo_trang.get(trang, []) if do[k][3][1] < hop[3]]
        if all(
            sach[k][0] == trang
            and max(abs(u - v) for u, v in zip(sach[k][3], do[k][3], strict=True)) <= _LECH_TOI_DA_PT
            for k in tren
        ):
            ra[khoa] = (trang, [round(v, 2) for v in hop])
    return ra


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


@contextmanager
def _mot_luot(user_sub: str):
    """Một lượt LibreOffice/`pdftoppm` mỗi tài khoản mỗi lúc: lượt thứ hai trong
    khi lượt đầu còn chạy là `ChuyenDoiKhongSanSang("qua_tai")`, cùng 503 của ba
    suất chung. Nhả chỗ cả khi lượt hỏng."""
    with _khoa_dang_dung:
        if user_sub in _dang_dung:
            raise ChuyenDoiKhongSanSang("qua_tai", "tài khoản đang có một lượt dựng trang")
        _dang_dung.add(user_sub)
    try:
        yield
    finally:
        with _khoa_dang_dung:
            _dang_dung.discard(user_sub)


def dung(
    dinh_dang: str,
    noi_dung: bytes,
    user_sub: str,
    ap: Callable[[bytes], bytes] | None = None,
    do: Callable[[bytes], bytes] | None = None,
) -> tuple[list[list[float]], list[bytes], ViTri]:
    """`(khổ, PNG, vị trí ô)` từng trang của một khuôn gốc. Khổ đọc từ CHÍNH PDF
    vừa vẽ, nên `kho[i]` luôn là khổ của ảnh `i`. Một lượt mỗi tài khoản mỗi lúc
    (`_mot_luot`).

    `ap`: bước biến `noi_dung` thành bản đã điền cùng định dạng (bộ áp phép sửa
    của một bản thảo), chạy TRONG cùng lượt: bộ áp là việc CPU trên tệp tới
    20 MB, nên áp và dựng là một lượt, không phải việc nặng đứng ngoài hàng rào.

    `do` (chỉ docx): dựng bản DÒ từ khuôn gốc (`dien_khuon.danh_dau_docx`); `ap`
    áp lên nó như lên bản sạch, hai bản ra PDF trong cùng lượt LibreOffice, và
    `vi_tri_o` đo ô trên bản sạch. Ảnh luôn từ bản SẠCH — bản dò có thể ngắt
    dòng khác. Bản dò hỏng thì trang vẫn về, không có vị trí nào."""
    ap = ap or (lambda b: b)
    with _mot_luot(user_sub):
        ban = ap(noi_dung)
        vi_tri: ViTri = {}
        if dinh_dang != "docx":
            pdf = ban
        elif do is None:
            pdf = dung_pdf(ban)
        else:
            try:
                pdf, pdf_do = dung_pdf_kem(ban, ap(do(noi_dung)))
            except KhongDocDuoc:
                # ponytail: lượt đôi hỏng thì dựng lại riêng bản sạch — bản dò
                # không bao giờ làm mất trang; tệp tự hỏng thì hỏng hai lần.
                logger.warning("dung_trang: lượt kèm bản dò hỏng, dựng riêng bản sạch")
                pdf, pdf_do = dung_pdf(ban), None
            try:
                vi_tri = vi_tri_o(pdf, pdf_do) if pdf_do else {}
            except Exception:
                # Bắt rộng cùng lý do `_mo_pdf`: pypdf ném đủ loại lỗi trên một
                # PDF lạ, và vị trí ô không bao giờ được làm mất trang.
                logger.warning("dung_trang: không đọc được vị trí ô từ bản dò")
        return kho_trang(pdf), anh_trang(pdf), vi_tri


def tep_tai_ve(dinh_dang: str, noi_dung: bytes, dang: str, user_sub: str, ap: Callable[[bytes], bytes]) -> bytes:
    """Tệp tải về của một bản đã điền: `ap(noi_dung)`, và với `dang="pdf"` trên
    khuôn DOCX là bản LibreOffice dựng từ nó. Mọi nhánh trong MỘT lượt như
    `dung` — kể cả khuôn PDF và `dang="docx"`, nơi chỉ bộ áp chạy."""
    with _mot_luot(user_sub):
        ban = ap(noi_dung)
        return dung_pdf(ban) if dinh_dang == "docx" and dang == "pdf" else ban


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
