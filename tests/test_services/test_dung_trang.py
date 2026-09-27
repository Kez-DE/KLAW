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
import subprocess
import threading
import zipfile
import zlib
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path

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


def pdf_hop(*hop: list) -> bytes:
    """PDF trắng, mỗi phần tử là `/MediaBox` NGUYÊN VĂN của một trang — kể cả
    hộp ngược hay hộp sai số phần tử, thứ một tệp người lạ khai được."""
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, FloatObject, NameObject

    w = PdfWriter()
    for h in hop:
        w.add_blank_page(100, 100)[NameObject("/MediaBox")] = ArrayObject(FloatObject(v) for v in h)
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


def test_hop_media_NGUOC_ra_kho_DUONG_dung_nhu_poppler_ve():
    """`/MediaBox [3000 3000 0 0]`: pypdf trả rộng/cao ÂM, poppler lật hộp và vẽ
    đủ 3000 pt. Khổ âm làm trần điểm ảnh không bao giờ hạ dpi, và nó bị ghi
    thẳng vào `khuon_goc.kho`."""
    assert dung_trang.kho_trang(pdf_hop([3000, 3000, 0, 0])) == [[3000.0, 3000.0]]


@pytest.mark.parametrize(
    "hop",
    [[0, 0, 0, 842], [0, 0, 14401, 842], [0, 0, 595, 1e9], [0, 842]],
    ids=["rong_0", "qua_14400", "khong_lo", "thieu_so"],
)
def test_kho_NGOAI_gioi_han_PDF_la_tep_hong(hop):
    """14400 pt (200 inch) là trần khổ trang của chuẩn PDF (ISO 32000-1, phụ
    lục C). Hộp rỗng, vượt trần hay sai số phần tử là tệp hỏng — không phải
    500 và không phải một khổ lạ nằm trong `khuon_goc`."""
    with pytest.raises(KhongDocDuoc) as e:
        dung_trang.kho_trang(pdf_hop(hop))
    assert e.value.ly_do is LoaiHong.tep_hong


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


@pytest.mark.skipif(not _CO_PDFTOPPM, reason="cần pdftoppm (poppler)")
def test_hop_media_NGUOC_van_bi_tran_canh_chan():
    """Đầu cuối của lỗ hổng: trước bản vá, hộp ngược 3000 pt ra PNG 4584×4584."""
    (png,) = dung_trang.anh_trang(pdf_hop([3000, 3000, 0, 0]))
    assert max(co_png(png)) <= dung_trang._CANH_TOI_DA_PX


@pytest.mark.skipif(not _CO_PDFTOPPM, reason="cần pdftoppm (poppler)")
def test_tran_canh_do_CHINH_pdftoppm_giu_khi_kho_doc_sai(monkeypatch):
    """Phép tính dpi tin khổ pypdf đọc. Nếu pypdf và poppler hiểu một hộp khác
    nhau, trần vẫn phải đứng: poppler tự cắt ảnh ở cạnh tối đa, nên bộ nhớ của
    MỘT trang không bao giờ theo khổ tệp tự khai."""
    monkeypatch.setattr(dung_trang, "kho_trang", lambda pdf: [[100.0, 100.0]])
    (png,) = dung_trang.anh_trang(pdf_trang((4000.0, 4000.0)))
    assert max(co_png(png)) <= dung_trang._CANH_TOI_DA_PX


@pytest.mark.skipif(not _CO_PDFTOPPM, reason="cần pdftoppm (poppler)")
def test_TONG_diem_anh_ca_tai_lieu_bi_chan_nen_phan_hoi_co_tran():
    """`/trang` trả MỌI trang trong một JSON. Mười trang 2000 pt đều dưới trần
    cạnh vẫn ra ~57 Mpx (~170 MB PNG khó nén); trần tổng hạ dpi đều."""
    anh = dung_trang.anh_trang(pdf_trang(*[(2000.0, 2000.0)] * 10))
    assert sum(w * h for w, h in map(co_png, anh)) <= dung_trang._PX_TAI_LIEU_TOI_DA


@pytest.mark.skipif(not _CO_PDFTOPPM, reason="cần pdftoppm (poppler)")
def test_MUOI_trang_A4_van_giu_110_dpi_duoi_tran_tong():
    for png in dung_trang.anh_trang(pdf_trang(*[_A4] * 10)):
        w, h = co_png(png)
        assert abs(w - _A4[0] * 110 / 72) <= 2 and abs(h - _A4[1] * 110 / 72) <= 2


@pytest.mark.skipif(not _CO_PDFTOPPM, reason="cần pdftoppm (poppler)")
def test_anh_VUOT_tran_byte_la_tep_hong_khong_doc_vao_bo_nho(monkeypatch):
    """Chốt cuối, đo bằng kích thước tệp TRƯỚC khi đọc: trong trần điểm ảnh thì
    PNG không thể vượt ~3 byte/px, nên vượt nghĩa là phép tính khổ đã sai."""
    monkeypatch.setattr(dung_trang, "_BYTE_ANH_TOI_DA", 10)
    with pytest.raises(KhongDocDuoc) as e:
        dung_trang.anh_trang(pdf_trang(_A4))
    assert e.value.ly_do is LoaiHong.tep_hong


def test_anh_trang_DUNG_CHUNG_suat_voi_LibreOffice(monkeypatch):
    """Vẽ ảnh trang lặp được và không trừ hạn mức, nên nó chia đúng ba suất của
    `.doc`/docx thay vì mở pdftoppm song song không giới hạn."""
    monkeypatch.setattr(dung_trang.shutil, "which", lambda ten: "/usr/bin/pdftoppm")
    monkeypatch.setattr("src.services.doc_tai_lieu._HAN_CHO_SUAT_GIAY", 0.2)
    suat = threading.Semaphore(1)
    suat.acquire()
    monkeypatch.setattr("src.services.doc_tai_lieu._suat_chuyen_doi", suat)
    with pytest.raises(ChuyenDoiKhongSanSang) as e:
        dung_trang.anh_trang(pdf_trang(_A4))
    assert e.value.ly_do == "qua_tai"


def test_MOT_tai_khoan_MOT_luot_dung_mot_luc(monkeypatch):
    """Giới hạn nhịp trước `/trang` đếm theo IP, nên một tài khoản gọi từ nhiều
    IP giữ được cả ba suất chung và mọi lượt tải lên của người khác thành 503.
    Một tài khoản chỉ một lượt dựng mỗi lúc; tài khoản khác vẫn dựng song song,
    và một lượt đã xong — kể cả hỏng — nhả chỗ."""
    monkeypatch.setattr(dung_trang, "kho_trang", lambda pdf: [list(_A4)])
    thay: list[str] = []

    def _anh(pdf):
        if pdf == b"hong":
            raise KhongDocDuoc(LoaiHong.tep_hong, "x")
        if pdf == b"ngoai":
            for ai in ("a", "b"):
                try:
                    dung_trang.dung("pdf", b"trong", ai)
                    thay.append(f"{ai}:dung")
                except ChuyenDoiKhongSanSang as e:
                    thay.append(f"{ai}:{e.ly_do}")
        return [b"png"]

    monkeypatch.setattr(dung_trang, "anh_trang", _anh)
    assert dung_trang.dung("pdf", b"ngoai", "a") == ([list(_A4)], [b"png"], {})
    assert thay == ["a:qua_tai", "b:dung"]
    with pytest.raises(KhongDocDuoc):
        dung_trang.dung("pdf", b"hong", "a")
    assert dung_trang.dung("pdf", b"trong", "a")[1] == [b"png"], "lượt hỏng vẫn nhả chỗ"


def test_BO_AP_va_TAI_VE_chay_TRONG_CUNG_mot_luot_voi_dung(monkeypatch):
    """Bộ áp phép sửa là việc CPU trên khuôn gốc tới 20 MB, bản PDF tải về dựng
    bằng LibreOffice (một trong ba suất): cả hai chạy TRONG lượt của tài khoản,
    không trước lượt — nếu không, một tài khoản gọi từ nhiều IP chạy bao nhiêu
    lượt áp song song cũng được. Mọi nhánh tải về giữ lượt, kể cả khuôn PDF (bộ
    áp PDF vẫn chạy); lượt hỏng giữa chừng vẫn nhả chỗ."""
    monkeypatch.setattr(dung_trang, "kho_trang", lambda pdf: [list(_A4)])
    monkeypatch.setattr(dung_trang, "anh_trang", lambda pdf: [pdf])
    monkeypatch.setattr(dung_trang, "dung_pdf", lambda docx: b"%PDF-" + docx)
    thay: list[str] = []

    def _ap(ban: bytes) -> bytes:
        for ai in ("a", "b"):
            try:
                dung_trang.dung("pdf", b"x", ai)
                thay.append(f"{ai}:dung")
            except ChuyenDoiKhongSanSang as e:
                thay.append(f"{ai}:{e.ly_do}")
        return ban + b"!"

    assert dung_trang.dung("docx", b"d", "a", _ap) == ([list(_A4)], [b"%PDF-d!"], {})
    assert dung_trang.tep_tai_ve("docx", b"d", "docx", "a", _ap) == b"d!"
    assert dung_trang.tep_tai_ve("docx", b"d", "pdf", "a", _ap) == b"%PDF-d!"
    assert dung_trang.tep_tai_ve("pdf", b"%PDF", "pdf", "a", _ap) == b"%PDF!"
    assert thay == ["a:qua_tai", "b:dung"] * 4

    def _hong(ban: bytes) -> bytes:
        raise KhongDocDuoc(LoaiHong.tep_hong, "x")

    with pytest.raises(KhongDocDuoc):
        dung_trang.tep_tai_ve("docx", b"d", "docx", "a", _hong)
    assert dung_trang.tep_tai_ve("docx", b"y", "pdf", "a", lambda b: b) == b"%PDF-y", "xong lượt thì nhả chỗ"


# ═══ Vị trí ô trên trang — bản dò (`dien_khuon.danh_dau_docx`) ════════════


def _tu(*dong: tuple[float, list[tuple[str, float, float]]]) -> dict:
    """`_tu_pdf` giả của MỘT trang: mỗi dòng `(y0, [(chữ, x0, x1)])`, cao 14 pt."""
    return {1: [(("1", "1", str(i), "1"), c, (a, y, b, y + 14)) for i, (y, tu) in enumerate(dong) for c, a, b in tu]}


def test_vi_tri_o_theo_KY_TU_khi_ban_do_NGAT_DONG_KHAC():
    """BM.M05: liên kết của bản dò cho LibreOffice ngắt trước ".……" thay vì
    trước "Khoa" — cùng chuỗi chữ, khác dòng. Hộp liên kết đo trên bản dò được
    tìm lại theo ký tự trên bản SẠCH: ô nằm sau "Khoa" ở dòng 2, không ở dòng
    liên kết của bản dò."""
    sach = _tu((10, [("thuộc", 0, 30)]), (30, [("Khoa", 0, 30), (".……", 35, 100)]))
    do = _tu((10, [("thuộc", 0, 30), ("Khoa", 35, 65)]), (30, [(".……", 0, 65)]))
    assert dung_trang._chuyen_vi_tri({(9, 0): [(0, (0, 30, 65, 44))]}, sach, do) == {(9, 0): (0, [35, 30, 100, 44])}


def test_vi_tri_o_trong_MOT_tu_doi_nguyen_van_phan_hop_lien_ket():
    """ "Số …./….": hai ô trong một từ của poppler. Từ giữ nguyên ranh giới ở
    bản sạch thì phần hộp liên kết trong từ dời nguyên văn, không chia đều."""
    sach = _tu((50, [("Số", 0, 20), ("…./….", 125, 175)]))
    do = _tu((40, [("Số", 0, 20), ("…./….", 100, 150)]))
    lien_ket = {(3, 0): [(0, (100, 40, 118, 54))], (3, 1): [(0, (131, 40, 150, 54))]}
    assert dung_trang._chuyen_vi_tri(lien_ket, sach, do) == {
        (3, 0): (0, [125, 50, 143, 64]),
        (3, 1): (0, [156, 50, 175, 64]),
    }


def test_vi_tri_o_O_VAT_DONG_lay_dong_DAU_tren_ban_sach_va_chu_khac_thi_khong_doan():
    sach = _tu((10, [("A:", 0, 20), ("……", 25, 100)]), (30, [("……", 0, 40)]))
    do = _tu((10, [("A:", 0, 20)]), (30, [("……", 0, 75), ("……", 80, 120)]))
    lien_ket = {(0, 0): [(0, (0, 30, 120, 44))]}
    assert dung_trang._chuyen_vi_tri(lien_ket, sach, do) == {(0, 0): (0, [25, 10, 100, 24])}
    khac = _tu((10, [("B:", 0, 20)]), (30, [("……", 0, 75), ("……", 80, 120)]))
    assert dung_trang._chuyen_vi_tri(lien_ket, sach, khac) == {}


def test_dung_DOCX_co_ban_do_dung_ANH_ban_sach_va_ban_do_hong_van_ra_trang(monkeypatch):
    """Bản dò đi qua CÙNG bộ áp và cùng lượt LibreOffice với bản sạch; ảnh là
    của bản sạch. Lượt đôi hỏng thì dựng riêng bản sạch — trang về, không vị trí."""
    monkeypatch.setattr(dung_trang, "kho_trang", lambda pdf: [list(_A4)])
    monkeypatch.setattr(dung_trang, "anh_trang", lambda pdf: [pdf])
    kem: list[tuple[bytes, bytes]] = []
    monkeypatch.setattr(dung_trang, "dung_pdf_kem", lambda a, b: kem.append((a, b)) or (b"%PDF-" + a, b"%DO-" + b))
    monkeypatch.setattr(dung_trang, "vi_tri_o", lambda sach, do: {"sach": sach, "do": do})
    ra = dung_trang.dung("docx", b"d", "a", lambda b: b + b"!", lambda b: b + b"?")
    assert kem == [(b"d!", b"d?!")]
    assert ra == ([list(_A4)], [b"%PDF-d!"], {"sach": b"%PDF-d!", "do": b"%DO-d?!"})

    def _vo(sach, do):
        raise ValueError("pypdf ném trên chú thích lạ")

    monkeypatch.setattr(dung_trang, "vi_tri_o", _vo)
    assert dung_trang.dung("docx", b"d", "a", None, lambda b: b)[2] == {}, "vị trí hỏng không làm mất trang"

    def _hong(a, b):
        raise KhongDocDuoc(LoaiHong.tep_hong, "x")

    monkeypatch.setattr(dung_trang, "dung_pdf_kem", _hong)
    monkeypatch.setattr(dung_trang, "dung_pdf", lambda docx: b"%PDF-" + docx)
    assert dung_trang.dung("docx", b"d", "a", None, lambda b: b + b"?") == ([list(_A4)], [b"%PDF-d"], {})


_CO_BA = _CO_SOFFICE and _CO_PDFTOPPM and shutil.which("pdftotext") is not None


@pytest.mark.skipif(not _CO_BA, reason="cần LibreOffice + poppler")
def test_vi_tri_o_that_nam_tren_DAY_CHAM_cua_trang_sach():
    """Đường thật: LibreOffice xuất liên kết của bản dò thành `/Link`, và hộp
    của mỗi ô phủ điểm ảnh tối (dãy chấm) trên ảnh 72 dpi của bản SẠCH."""
    from src.services.dien_khuon import danh_dau_docx
    from tests.test_services.test_dien_khuon import _hang

    vao = docx_that("Họ và tên: ………………………………", "Điện thoại: ………… Fax: …………")
    hang = _hang(vao)
    o = [(0, 0), (1, 0), (1, 1)]
    kho, png, vi_tri = dung_trang.dung("docx", vao, "a", do=lambda b: danh_dau_docx(b, hang, o))
    assert set(vi_tri) == set(o) and len(png) == 1
    anh = _anh_xam_72(dung_trang.dung_pdf(vao))[0]
    for trang, (x0, y0, x1, y1) in vi_tri.values():
        assert trang == 0 and 0 <= x0 < x1 <= kho[0][0] and 0 <= y0 < y1 <= kho[0][1]
        assert anh[int(y0) : int(y1) + 1, int(x0) : int(x1) + 1].min() < 128
    assert vi_tri[1, 0][1][2] < vi_tri[1, 1][1][0], "ô Fax nằm bên phải ô Điện thoại"


def _anh_xam_72(pdf: bytes) -> list:
    from src.services.doc_tai_lieu import _cac_trang_pgm, _chay_cong_cu

    return _cac_trang_pgm(_chay_cong_cu(["pdftoppm", "-r", "72", "-gray", "-"], pdf) or b"")


# Kho mẫu ngoài repo, không bao giờ commit; không có thì bỏ qua (CI).
_KHO_MAU = Path.home() / "giấy tờ thực tập"
_MAU = sorted(_KHO_MAU.glob("*.docx")) if _KHO_MAU.exists() else []
# Đo 2026-09-27 (LibreOffice 26.2.4): LibreOffice không xuất liên kết của MỘT ô
# chỉ là "…" ở cuối đoạn căn phải ("… năm 20…" của BM.ĐT.18.03) khi ô còn trống
# — ô đó "chưa định vị"; điền rồi thì có.
_CHUA_DINH_VI = {"BM.ĐT.18.03. Đơn đăng ký đi thực tập tốt nghiệp Ver 02.docx": {(2, 2)}}


@pytest.mark.skipif(not (_MAU and _CO_BA), reason="kho mẫu ngoài repo hoặc LibreOffice/poppler không có")
@pytest.mark.parametrize("tep", _MAU, ids=lambda p: p.stem[:24])
@pytest.mark.parametrize("dien", [False, True], ids=["trong", "da_dien"])
def test_tep_that_MOI_o_co_trang_va_hop_tren_day_cham_hay_gia_tri(tep, dien):
    """Tám biểu mẫu thật, trước và sau khi điền MỌI ô: mỗi ô bộ áp tới được có
    `trang` + `hop` (trừ `_CHUA_DINH_VI`), hộp nằm trong trang và phủ điểm ảnh
    tối trên ảnh 72 dpi của bản sạch; ô đã điền thì một từ `pdftotext` của giá
    trị cắt hộp. BM.M05 là ca bản dò ngắt dòng khác ("Khoa .……")."""
    import unicodedata

    from scripts.kiem_mo_bang_word import hang_don_vi, phep_dien_het
    from src.services.ban_thao import ap_phep_sua, cho_trong_khuon
    from src.services.dien_khuon import danh_dau_docx
    from src.services.doc_tai_lieu import _tu_pdf

    du_lieu = tep.read_bytes()
    hang = hang_don_vi(tep.name, du_lieu)
    o = [(x["don_vi"], x["so"]) for x in cho_trong_khuon("docx", hang, [])]
    phep = phep_dien_het(hang) if dien else []
    gia_tri = {(p["don_vi"], p["cho_trong"]): p["gia_tri"] for p in phep}

    def ap(b: bytes) -> bytes:
        return ap_phep_sua("docx", b, hang, phep)[0]

    pdf, pdf_do = dung_trang.dung_pdf_kem(ap(du_lieu), ap(danh_dau_docx(du_lieu, hang, o)))
    vi_tri = dung_trang.vi_tri_o(pdf, pdf_do)
    assert set(o) - set(vi_tri) <= (set() if dien else _CHUA_DINH_VI.get(unicodedata.normalize("NFC", tep.name), set()))
    kho, anh, tu = dung_trang.kho_trang(pdf), _anh_xam_72(pdf), _tu_pdf(pdf)
    for k, (trang, (x0, y0, x1, y1)) in vi_tri.items():
        rong, cao = kho[trang]
        assert 0 <= x0 < x1 <= rong + 0.5 and 0 <= y0 < y1 <= cao + 0.5, k
        assert anh[trang][int(y0) : int(y1) + 1, int(x0) : int(x1) + 1].min() < 128, k
        if k in gia_tri:
            v = "".join(unicodedata.normalize("NFC", gia_tri[k]).split())
            cat = [c for _, c, h in tu[trang + 1] if h[0] < x1 and x0 < h[2] and h[1] < y1 and y0 < h[3]]
            assert any(c in v or any(t in c for t in gia_tri[k].split()) for c in cat), (k, cat)


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


_NS_ANH = (
    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"'
)


def _docx_lien_ket_ngoai(goc: str, dich_anh: str | None = None) -> bytes:
    """Một docx với hai đường liên kết ngoài phổ biến: ảnh DrawingML liên kết
    (`r:link`, `TargetMode="External"`, đích `dich_anh` hay `{goc}/anh.png`) và
    trường `INCLUDEPICTURE`."""
    anh = (
        '<w:p><w:r><w:drawing><wp:inline><wp:extent cx="914400" cy="914400"/><wp:docPr id="1" name="p"/>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
        '<pic:nvPicPr><pic:cNvPr id="1" name="p"/><pic:cNvPicPr/></pic:nvPicPr>'
        '<pic:blipFill><a:blip r:link="rIdNgoai"/></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/>'
        '<a:ext cx="914400" cy="914400"/></a:xfrm><a:prstGeom prst="rect"/></pic:spPr>'
        "</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"
    )
    truong = (
        '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        f'<w:r><w:instrText> INCLUDEPICTURE "{goc}/truong.png" \\d </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>x</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    )
    rels = (
        '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rIdNgoai" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        f'Target="{dich_anh or goc + "/anh.png"}" TargetMode="External"/></Relationships>'
    )
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/_rels/document.xml.rels", rels)
        z.writestr(
            "word/document.xml",
            f'<?xml version="1.0"?><w:document {_NS_ANH}><w:body>{anh}{truong}</w:body></w:document>',
        )
    return buf.getvalue()


@contextmanager
def _may_nghe():
    """Máy nghe HTTP 127.0.0.1: `(gốc URL, các đường đã bị gọi tới)`."""
    import http.server
    import socketserver

    goi: list[str] = []

    class _Nghe(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — tên do http.server đặt
            goi.append(self.path)
            self.send_response(404)
            self.end_headers()

        def log_message(self, *a):
            pass

    with socketserver.TCPServer(("127.0.0.1", 0), _Nghe) as may:
        threading.Thread(target=may.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{may.server_address[1]}", goi
        finally:
            may.shutdown()


def _png_do(canh: int = 20) -> bytes:
    """Một PNG đỏ hợp lệ, dựng bằng stdlib."""

    def khoi(loai: bytes, du_lieu: bytes) -> bytes:
        return struct.pack(">I", len(du_lieu)) + loai + du_lieu + struct.pack(">I", zlib.crc32(loai + du_lieu))

    dong = b"".join(b"\x00" + b"\xff\x00\x00" * canh for _ in range(canh))
    return (
        b"\x89PNG\r\n\x1a\n"
        + khoi(b"IHDR", struct.pack(">IIBBBBB", canh, canh, 8, 2, 0, 0, 0))
        + khoi(b"IDAT", zlib.compress(dong))
        + khoi(b"IEND", b"")
    )


@pytest.mark.skipif(not _CO_SOFFICE, reason="cần LibreOffice")
def test_dung_pdf_KHONG_goi_ra_mang_voi_lien_ket_ngoai():
    """Rào SSRF. Hộp cát LibreOffice không chặn mạng ở tầng hệ điều hành, và từ
    quyết định 2026-09-26 MỌI docx tải lên và mọi `GET /trang` của docx đi qua
    nó. Đo 2026-09-27 (LibreOffice 26.2.4): không có rào, ảnh `r:link` bị tải
    về ba lần. Rào là `BlockUntrustedRefererLinks` trong hồ sơ riêng
    (`doc_tai_lieu._chay_soffice`); đỏ trên một image nào nghĩa là rào không
    giữ ở bản LibreOffice đó."""
    with _may_nghe() as (goc, goi):
        dung_trang.dung_pdf(_docx_lien_ket_ngoai(goc))
    assert goi == []


@pytest.mark.skipif(not _CO_SOFFICE, reason="cần LibreOffice")
def test_dung_pdf_KHONG_nhung_tep_may_chu_qua_lien_ket_file(tmp_path):
    """Cùng rào, đường `file://`. Đo 2026-09-27: không có rào, ảnh liên kết tới
    một tệp CỦA MÁY CHỦ được nhúng vào PDF đã dựng — và `/trang` trả nó, dưới
    dạng ảnh trang, cho người tải tệp lên."""
    from pypdf import PdfReader

    anh = tmp_path / "may_chu.png"
    anh.write_bytes(_png_do())
    with _may_nghe() as (goc, _):
        pdf = dung_trang.dung_pdf(_docx_lien_ket_ngoai(goc, f"file://{anh}"))
    assert sum(len(t.images) for t in PdfReader(BytesIO(pdf)).pages) == 0


@pytest.mark.skipif(not _CO_SOFFICE, reason="cần LibreOffice")
def test_quy_doi_doc_KHONG_goi_ra_mang_voi_lien_ket_ngoai(tmp_path):
    """Rào thứ hai. Bộ nhập `.doc` tải ảnh liên kết bất kể
    `BlockUntrustedRefererLinks` — đo 2026-09-27: một GET mù lúc nhập, ở cả
    LibreOffice 26.2.4 lẫn 25.2.3. Lượt tải đó đi qua proxy của LibreOffice, nên
    hồ sơ riêng trỏ proxy về một cổng loopback chết (`_HO_SO_CHAN_LIEN_KET`).
    Đỏ trên một image nào nghĩa là rào không giữ ở bản LibreOffice đó."""
    from src.services.doc_tai_lieu import _chuyen_doc_sang_docx

    with _may_nghe() as (goc, goi):
        nguon = tmp_path / "lien_ket.docx"
        nguon.write_bytes(_docx_lien_ket_ngoai(goc))
        subprocess.run(
            [
                shutil.which("soffice"),
                "--headless",
                f"-env:UserInstallation=file://{tmp_path / 'ho_so'}",
                "--convert-to",
                "doc",
                "--outdir",
                str(tmp_path),
                str(nguon),
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )
        goi.clear()  # lượt tạo `.doc` ở trên là dựng test, không qua hộp cát
        _chuyen_doc_sang_docx((tmp_path / "lien_ket.doc").read_bytes())
    assert goi == []


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
