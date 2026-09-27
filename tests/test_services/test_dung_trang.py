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
    assert dung_trang.dung("pdf", b"ngoai", "a") == ([list(_A4)], [b"png"])
    assert thay == ["a:qua_tai", "b:dung"]
    with pytest.raises(KhongDocDuoc):
        dung_trang.dung("pdf", b"hong", "a")
    assert dung_trang.dung("pdf", b"trong", "a")[1] == [b"png"], "lượt hỏng vẫn nhả chỗ"


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
@pytest.mark.xfail(
    reason="rủi ro còn lại đã đo (quyết định 2026-09-26, Tradeoffs): bộ nhập .doc "
    "tải ảnh liên kết bất kể BlockUntrustedRefererLinks — chặn cần cách ly mạng",
)
def test_quy_doi_doc_KHONG_goi_ra_mang_voi_lien_ket_ngoai(tmp_path):
    """PHÉP ĐO, không phải rào: `.doc` là nhị phân, không có rào nào ở tầng tệp.
    Đo 2026-09-27 (LibreOffice 26.2.4): một GET mù lúc nhập; bản docx quy đổi
    giữ liên kết chứ không giữ bytes đã tải, và bước dựng PDF sau đó bị rào
    chặn. XFAIL trong image triển khai = rủi ro có thật ở đó."""
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
