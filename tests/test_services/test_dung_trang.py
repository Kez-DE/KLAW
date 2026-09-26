"""Dựng trang của khuôn gốc — quyết định 2026-09-26
(`docs/decisions/2026-09-26-luu-khuon-goc-va-dien-tai-cho.md`).

Bốn điều file này khoá, không cần DB:

1. Số trang và khổ giấy đọc THẲNG từ PDF (pypdf), không suy từ ngắt trang khai
   báo — Letter vẫn là Letter, trang xoay vẫn đứng đúng chiều.
2. Ảnh trang: đúng một PNG cho mỗi trang, cỡ điểm ảnh theo khổ ở 110 dpi.
3. `dung_pdf` đi qua ĐÚNG hộp cát LibreOffice của `.doc` (một suất chung, cùng
   hai lỗi hệ thống `khong_co_cong_cu`/`qua_tai`).
4. Khuôn gốc của `.doc` là bản `.docx` đã quy đổi; ảnh không có khuôn gốc.

Ca cần công cụ thật (`soffice`, `pdftoppm`) tự bỏ qua khi máy không có.
"""

import shutil
import struct
import threading
import zipfile
from io import BytesIO

import pytest

from src.services import dung_trang
from src.services.doc_tai_lieu import ChuyenDoiKhongSanSang, KhongDocDuoc, LoaiHong, TaiLieuDaDoc

_CO_SOFFICE = shutil.which("soffice") is not None
_CO_PDFTOPPM = shutil.which("pdftoppm") is not None

_A4 = (595.0, 842.0)
_LETTER = (612.0, 792.0)

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
# `w:pgSz` theo twip (1/20 pt).
_KHO_TWIP = {"a4": (11906, 16838), "letter": (12240, 15840)}


def docx_that(*doan: str, ngat_trang: int = 0, kho: str = "a4") -> bytes:
    """Một `.docx` tối thiểu mà LibreOffice MỞ ĐƯỢC — khác `_docx` của
    `test_tai_lieu_api.py` (thiếu `_rels/.rels` và kiểu nội dung, bộ đọc của
    KLAW nhận nhưng soffice báo "source file could not be loaded").

    `ngat_trang` thêm từng ấy đoạn bắt đầu bằng ngắt trang cứng, nên tệp dàn
    ra `1 + ngat_trang` trang."""
    than = "".join(f"<w:p><w:r><w:t>{d}</w:t></w:r></w:p>" for d in doan)
    than += '<w:p><w:r><w:br w:type="page"/><w:t>Trang sau</w:t></w:r></w:p>' * ngat_trang
    rong, cao = _KHO_TWIP[kho]
    than += f'<w:sectPr><w:pgSz w:w="{rong}" w:h="{cao}"/></w:sectPr>'
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{than}</w:body></w:document>",
        )
    return buf.getvalue()


def pdf_trang(*kho: tuple[float, float], xoay: int = 0) -> bytes:
    """PDF trắng, mỗi phần tử `kho` là một trang `(rộng, cao)` theo điểm."""
    from pypdf import PdfWriter

    w = PdfWriter()
    for rong, cao in kho:
        trang = w.add_blank_page(rong, cao)
        if xoay:
            trang.rotate(xoay)
    buf = BytesIO()
    w.write(buf)
    return buf.getvalue()


def co_png(du_lieu: bytes) -> tuple[int, int]:
    """(rộng, cao) điểm ảnh đọc từ khối IHDR — không cần Pillow."""
    assert du_lieu[:8] == b"\x89PNG\r\n\x1a\n", "phải là PNG"
    return struct.unpack(">II", du_lieu[16:24])


# ═══ Số trang và khổ giấy — thuần pypdf ════════════════════════════════════


def test_so_trang_va_kho_doc_thang_tu_pdf():
    pdf = pdf_trang(_A4, _LETTER, _A4)
    assert dung_trang.so_trang_pdf(pdf) == 3
    assert dung_trang.kho_trang(pdf) == [list(_A4), list(_LETTER), list(_A4)]


def test_trang_XOAY_90_do_dao_rong_cao_dung_nhu_khi_hien():
    """Bản scan ngang thường là trang dọc khai `/Rotate 90`. pdftoppm vẽ nó
    NẰM NGANG, nên khổ phải nói đúng chiều người dùng nhìn thấy."""
    assert dung_trang.kho_trang(pdf_trang(_A4, xoay=90)) == [[842.0, 595.0]]


@pytest.mark.parametrize("du_lieu", [b"khong phai pdf", b"%PDF-1.4\n rac"])
def test_pdf_hong_la_tep_hong_khong_phai_500(du_lieu):
    with pytest.raises(KhongDocDuoc) as e:
        dung_trang.so_trang_pdf(du_lieu)
    assert e.value.ly_do is LoaiHong.tep_hong


# ═══ Ảnh trang — pdftoppm ══════════════════════════════════════════════════


@pytest.mark.skipif(not _CO_PDFTOPPM, reason="cần pdftoppm (poppler)")
def test_anh_trang_MOT_png_moi_trang_co_theo_kho_o_110_dpi():
    anh = dung_trang.anh_trang(pdf_trang(_A4, _LETTER))
    assert len(anh) == 2
    for png, (rong, cao) in zip(anh, (_A4, _LETTER), strict=True):
        w, h = co_png(png)
        assert abs(w - rong * 110 / 72) <= 2 and abs(h - cao * 110 / 72) <= 2


@pytest.mark.skipif(not _CO_PDFTOPPM, reason="cần pdftoppm (poppler)")
def test_anh_trang_MUOI_trang_giu_dung_thu_tu():
    """pdftoppm đệm số khi có ≥10 trang (`t-01`…`t-10`); thứ tự phải theo
    trang, không theo chuỗi."""
    kho = [(300.0 + i * 10, 400.0) for i in range(10)]
    anh = dung_trang.anh_trang(pdf_trang(*kho))
    assert [co_png(p)[0] for p in anh] == sorted(co_png(p)[0] for p in anh)
    assert len(anh) == 10


@pytest.mark.skipif(not _CO_PDFTOPPM, reason="cần pdftoppm (poppler)")
def test_trang_KHONG_LO_bi_ha_dpi_khong_nuot_ram():
    """Một PDF người lạ khai trang 200 inch ở 110 dpi là một ảnh 22000×22000
    điểm (~1,4 GB RAM) cho MỖI trang. Cạnh dài bị chặn, tỉ lệ giữ nguyên."""
    (png,) = dung_trang.anh_trang(pdf_trang((14400.0, 7200.0)))
    w, h = co_png(png)
    assert w <= dung_trang._CANH_TOI_DA_PX
    assert abs(w / h - 2.0) < 0.01


def test_thieu_pdftoppm_la_loi_HE_THONG(monkeypatch):
    monkeypatch.setattr(dung_trang.shutil, "which", lambda ten: None)
    with pytest.raises(ChuyenDoiKhongSanSang) as e:
        dung_trang.anh_trang(pdf_trang(_A4))
    assert e.value.ly_do == "khong_co_cong_cu"


# ═══ docx → PDF — LibreOffice, chung hộp cát với `.doc` ════════════════════


@pytest.mark.skipif(not _CO_SOFFICE, reason="cần LibreOffice")
def test_dung_pdf_dem_trang_that_va_giu_kho_letter():
    pdf = dung_trang.dung_pdf(docx_that("Xin chào", ngat_trang=10, kho="letter"))
    assert dung_trang.so_trang_pdf(pdf) == 11
    assert dung_trang.kho_trang(pdf)[0] == list(_LETTER)


def test_dung_pdf_thieu_soffice_la_loi_HE_THONG(monkeypatch):
    monkeypatch.setattr("src.services.doc_tai_lieu._duong_soffice", lambda: None)
    with pytest.raises(ChuyenDoiKhongSanSang) as e:
        dung_trang.dung_pdf(docx_that("x"))
    assert e.value.ly_do == "khong_co_cong_cu"


def test_dung_pdf_DUNG_CHUNG_suat_voi_doc(monkeypatch):
    """Ba suất LibreOffice là ngân sách RAM của cả tiến trình — một docx đang
    dựng trang và một .doc đang quy đổi phải chia nhau đúng ba suất đó."""
    monkeypatch.setattr("src.services.doc_tai_lieu._duong_soffice", lambda: "/usr/bin/soffice")
    monkeypatch.setattr("src.services.doc_tai_lieu._HAN_CHO_SUAT_GIAY", 0.2)
    suat = threading.Semaphore(1)
    suat.acquire()
    monkeypatch.setattr("src.services.doc_tai_lieu._suat_chuyen_doi", suat)
    with pytest.raises(ChuyenDoiKhongSanSang) as e:
        dung_trang.dung_pdf(docx_that("x"))
    assert e.value.ly_do == "qua_tai"


@pytest.mark.skipif(not _CO_SOFFICE, reason="cần LibreOffice")
def test_docx_LibreOffice_khong_mo_duoc_la_tep_hong():
    """Zip hợp lệ với bộ đọc của KLAW nhưng không phải một docx soffice nạp
    được: không dựng được trang thì không có khuôn gốc để hứa, nên từ chối."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document/>")
    with pytest.raises(KhongDocDuoc) as e:
        dung_trang.dung_pdf(buf.getvalue())
    assert e.value.ly_do is LoaiHong.tep_hong


# ═══ Khuôn gốc theo định dạng ══════════════════════════════════════════════


def _da_doc(**k) -> TaiLieuDaDoc:
    return TaiLieuDaDoc(don_vi=[], so_trang=1, so_ky_tu=0, **k)


def test_khuon_goc_PDF_la_chinh_tep_khong_dung_lai():
    pdf = pdf_trang(_A4, _A4)
    k = dung_trang.khuon_goc("scan.PDF", pdf, _da_doc())
    assert (k.dinh_dang, k.noi_dung, k.so_trang) == ("pdf", pdf, 2)


def test_khuon_goc_DOC_la_ban_docx_da_quy_doi(monkeypatch):
    goi: list[bytes] = []
    monkeypatch.setattr(dung_trang, "dung_pdf", lambda docx: goi.append(docx) or pdf_trang(_LETTER))
    k = dung_trang.khuon_goc("cu.doc", b"\xd0\xcf ole2", _da_doc(docx_quy_doi=b"PK docx"))
    assert (k.dinh_dang, k.noi_dung, k.kho) == ("docx", b"PK docx", [list(_LETTER)])
    assert goi == [b"PK docx"], "dựng trang từ bản docx, không từ bytes OLE2"


def test_khuon_goc_DOCX_la_chinh_tep(monkeypatch):
    monkeypatch.setattr(dung_trang, "dung_pdf", lambda docx: pdf_trang(_A4, _A4, _A4))
    k = dung_trang.khuon_goc("hd.docx", b"PK goc", _da_doc())
    assert (k.dinh_dang, k.noi_dung, k.so_trang) == ("docx", b"PK goc", 3)


def test_anh_KHONG_co_khuon_goc():
    assert dung_trang.khuon_goc("chup.jpg", b"\xff\xd8", _da_doc()) is None
