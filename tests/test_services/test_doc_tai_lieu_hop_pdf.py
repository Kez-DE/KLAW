"""Hộp dòng và chỗ trống của PDF có lớp chữ và PDF scan — kế hoạch
`docs/plans/completed/khuon-goc-dien-tai-cho.md`, hợp đồng "Đơn vị văn bản
additions" (P2b).

Bộ đè chữ (P3b) cần biết chữ nằm Ở ĐÂU trên trang: `hop` của mỗi dòng và `hop`
của từng dãy chấm, bằng điểm PDF, gốc trên-trái. Bốn điều file này khoá:

1. `noi_dung` của PDF có lớp chữ vẫn là đúng dòng `pypdf` như trước; hộp chỉ
   được gắn khi chữ đã chuẩn hoá khớp DUY NHẤT một dòng của poppler trên trang.
2. Thiếu công cụ hay công cụ hỏng thì không có hộp nào — không đoán.
3. Bản scan: mỗi dòng OCR mang hộp từ TSV của tesseract; dãy chấm dài mà
   tesseract không đọc ra chữ được tìm bằng điểm ảnh, cạnh nhãn hoặc ở dòng
   chấm ngay dưới nhãn.
4. Bộ dò dãy chấm trên ảnh tách được chấm khỏi chữ, gạch chân và dấu lẻ.
"""

import shutil
import subprocess
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

from src.services import doc_tai_lieu as dtl
from src.services.doc_tai_lieu import NguonChu, co_ocr, doc

_CO_PDFTOTEXT = shutil.which("pdftotext") is not None
_CO_SCAN = co_ocr() and shutil.which("pdftoppm") is not None
_H = 842.0

# (x, y đường chân chữ theo reportlab — gốc DƯỚI-trái, chữ)
_DONG = [
    (72, 800, "Ho ten: .............................."),
    (72, 776, "Dien thoai: ............ Fax: ............"),
    (72, 752, "Ngay … thang … nam ……"),
    (72, 728, "Ghi chu chung"),
    (72, 704, "Ghi chu chung"),
    (72, 680, "Dia chi:"),
    (72, 656, "......................................................"),
    (72, 620, "Het."),
]


def _pdf(dong=_DONG, trang: int = 1) -> bytes:
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(595.0, _H))
    for _ in range(trang):
        c.setFont("Helvetica", 12)
        for x, y, chu in dong:
            c.drawString(x, y, chu)
        c.showPage()
    c.save()
    return buf.getvalue()


def _scan(pdf: bytes, tmp_path) -> bytes:
    """PDF CHỈ có ảnh: dựng trang ở 200 dpi rồi bọc ảnh lại thành PDF — đúng
    hình dạng một bản scan, từ chất liệu an toàn để giữ trong kho mã."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    vao = tmp_path / "so.pdf"
    vao.write_bytes(pdf)
    subprocess.run(["pdftoppm", "-r", "200", "-png", str(vao), str(tmp_path / "p")], check=True, timeout=60)
    buf = BytesIO()
    c = canvas.Canvas(buf)
    for anh in sorted(tmp_path.glob("p-*.png")):
        im = ImageReader(str(anh))
        w, h = im.getSize()
        c.setPageSize((w * 72 / 200, h * 72 / 200))
        c.drawImage(im, 0, 0, w * 72 / 200, h * 72 / 200)
        c.showPage()
    c.save()
    return buf.getvalue()


def _theo_chu(don_vi, dau):
    return [d for d in don_vi if d.noi_dung.startswith(dau)]


def _chong(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# ────────────────────────────────────────────────────── PDF có lớp chữ


@pytest.mark.skipif(not _CO_PDFTOTEXT, reason="cần pdftotext (poppler)")
def test_dong_co_hop_bang_diem_goc_tren_trai():
    (d,) = _theo_chu(doc("x.pdf", _pdf()).don_vi, "Ho ten")
    x0, y0, x1, y1 = d.hop
    assert abs(x0 - 72) < 0.5
    assert y0 < _H - 800 < y1, "đường chân chữ phải nằm trong hộp, đo từ mép TRÊN"
    assert x1 > x0 + 100


@pytest.mark.skipif(not _CO_PDFTOTEXT, reason="cần pdftotext (poppler)")
def test_cho_trong_la_tu_TOAN_CHAM_kem_nhan_va_co_chu():
    don_vi = doc("x.pdf", _pdf()).don_vi
    (d,) = _theo_chu(don_vi, "Dien thoai")
    assert [(c.so, c.kieu, c.nhan) for c in d.cho_trong] == [(0, "cham", "Dien thoai"), (1, "cham", "Fax")]
    for c in d.cho_trong:
        assert c.hop[0] >= d.hop[0] and c.hop[2] <= d.hop[2] + 0.01
        assert 8 < c.co_chu < 16
    assert d.cho_trong[0].hop[2] < d.cho_trong[1].hop[0]
    (ngay,) = _theo_chu(don_vi, "Ngay")
    assert [c.nhan for c in ngay.cho_trong] == ["Ngay", "thang", "nam"]


@pytest.mark.skipif(not _CO_PDFTOTEXT, reason="cần pdftotext (poppler)")
def test_dong_CHI_co_cham_lay_nhan_la_duoi_dong_ngay_tren():
    """Dãy chấm dài xuống hàng dưới nhãn ("Dia chi:" rồi một dòng toàn chấm):
    trên dòng của nó không có chữ nào, nên nhãn là phần chữ cuối dòng ngay trên
    cùng trang — cùng luật nhánh scan. Trước đây nhãn rỗng, và bảng ô điền hiện
    "Ô 9.0" (BM.M05 xuất ra PDF, đo 2026-09-27)."""
    (d,) = _theo_chu(doc("x.pdf", _pdf()).don_vi, "......")
    assert [c.nhan for c in d.cho_trong] == ["Dia chi"]


@pytest.mark.skipif(not _CO_PDFTOTEXT, reason="cần pdftotext (poppler)")
def test_nhan_dong_tren_KHONG_vuot_trang_hay_dong_khong_khop():
    """Dòng chấm đầu trang không mượn nhãn của trang trước; dòng pypdf không
    khớp poppler (không biết giữa hai dòng có gì) cũng không cho mượn."""
    don_vi = doc(
        "x.pdf", _pdf([(72, 800, "......................................"), (72, 776, "Dia chi:")], trang=2)
    ).don_vi
    assert [c.nhan for d in don_vi for c in d.cho_trong] == ["", ""]
    trung = [(72, 800, "Ghi chu"), (72, 776, "Ghi chu"), (72, 752, "......................................")]
    assert [c.nhan for d in doc("x.pdf", _pdf(trung)).don_vi for c in d.cho_trong] == [""]


_BM_M05 = Path.home() / "giấy tờ thực tập" / "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx"


@pytest.mark.skipif(
    not (_BM_M05.exists() and shutil.which("soffice") and _CO_PDFTOTEXT), reason="kho mẫu ngoài repo + LibreOffice"
)
def test_BM_M05_xuat_PDF_dong_chi_co_cham_mang_nhan_dong_tren():
    """BM.M05 xuất ra PDF là nơi bảng ô điền hiện "Ô 9.0", "Ô 11.0" (bản `.doc`
    quy đổi thì không — nhãn ở đó y như `.docx`). Mọi dòng chấm dài xuống hàng
    dưới nhãn giờ mang nhãn dòng trên; chỉ dòng chấm nối tiếp MỘT chỗ trống
    ("Khoa ……" rồi "……") còn rỗng."""
    from src.services.dung_trang import dung_pdf

    nhan = [c.nhan for d in doc("bm.pdf", dung_pdf(_BM_M05.read_bytes())).don_vi for c in d.cho_trong]
    for n in ("Cơ quan/Đơn vị tiếp nhận", "Địa chỉ", "Fax", "Ngành", "Thực hành/thực tập tại bộ phận"):
        assert n in nhan, (n, nhan)
    assert nhan.count("") == 1, nhan


@pytest.mark.skipif(not _CO_PDFTOTEXT, reason="cần pdftotext (poppler)")
def test_dong_TRUNG_chu_tren_cung_trang_KHONG_co_hop():
    """Hai dòng "Ghi chu chung": không biết dòng nào là dòng nào, nên không
    gắn hộp nào — bộ đè chữ đặt nhầm dòng tệ hơn không đặt."""
    trung = _theo_chu(doc("x.pdf", _pdf()).don_vi, "Ghi chu")
    assert len(trung) == 2
    assert all(d.hop is None and d.cho_trong == () for d in trung)


@pytest.mark.skipif(not _CO_PDFTOTEXT, reason="cần pdftotext (poppler)")
def test_dong_chu_bi_gian_rong_van_khop_theo_dong_thi_giac():
    """Căn đều hai lề tách một dòng thành nhiều "dòng" poppler (mỗi từ một dòng
    khi khoảng cách lớn); dòng thị giác gom lại theo độ cao vẫn khớp."""
    dong = [(72, 800, "Co"), (300, 800, "quan"), (500, 800, "nhan:"), (72, 780, "Het.")]
    don_vi = doc("x.pdf", _pdf(dong)).don_vi
    co_hop = [d for d in don_vi if d.hop]
    assert co_hop, [d.noi_dung for d in don_vi]
    for d in co_hop:
        assert d.hop[0] < d.hop[2]


@pytest.mark.skipif(not _CO_PDFTOTEXT, reason="cần pdftotext (poppler)")
def test_hop_do_tu_goc_tren_trai_cua_MEDIA_BOX_ke_ca_khi_co_CropBox():
    """poppler (`pdftotext -tsv`, và `pdftoppm` mặc định của nhánh scan) đo trên
    MEDIA box, không phải CropBox: chữ vẽ ở x = 100 của một trang cắt
    [50 50 545 792] vẫn có x0 = 100 (hệ CropBox sẽ cho 50). P3b đặt chữ bằng
    đúng hệ này — lệch nó là lệch mọi chữ điền theo độ cắt."""
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(595.0, _H))
    c.setCropBox((50, 50, 545, 792))
    c.setFont("Helvetica", 12)
    c.drawString(100, 700, "Ho ten: ..............")
    c.showPage()
    c.save()
    (d,) = _theo_chu(doc("x.pdf", buf.getvalue()).don_vi, "Ho ten")
    assert abs(d.hop[0] - 100) < 0.5, d.hop
    assert d.hop[1] < _H - 700 < d.hop[3], "y đo từ mép TRÊN của media box"


def test_THIEU_pdftotext_thi_khong_co_hop_va_noi_dung_y_het(monkeypatch):
    goc = doc("x.pdf", _pdf()).don_vi
    that = shutil.which
    monkeypatch.setattr(dtl.shutil, "which", lambda ten, *a, **k: None if ten == "pdftotext" else that(ten, *a, **k))
    thieu = doc("x.pdf", _pdf()).don_vi
    assert all(d.hop is None and d.cho_trong == () for d in thieu)
    assert [(d.chi_so, d.trang, d.offset_dau, d.noi_dung, d.nguon_chu) for d in thieu] == [
        (d.chi_so, d.trang, d.offset_dau, d.noi_dung, d.nguon_chu) for d in goc
    ]


def test_cong_cu_tra_RAC_thi_khong_co_hop(monkeypatch):
    monkeypatch.setattr(dtl, "_chay_cong_cu", lambda *a, **k: b"level\tpage_num\nrac\tx\n")
    assert all(d.hop is None for d in doc("x.pdf", _pdf()).don_vi)


def test_cong_cu_TREO_bi_cat_va_khong_co_hop(monkeypatch):
    """Công cụ ngoài nhận dữ liệu KHÔNG ĐÁNG TIN: treo thì bị giết cả nhóm tiến
    trình trong hạn định, và bộ đọc đi tiếp không hộp."""
    monkeypatch.setattr(dtl, "_HAN_CONG_CU_GIAY", 1)
    ra = dtl._chay_cong_cu(["sleep", "30"], b"")
    assert ra is None


# ─────────────────────────────────────────────────────────── PDF scan


@pytest.mark.skipif(not (_CO_SCAN and _CO_PDFTOTEXT), reason="cần tesseract + vie + pdftoppm + pdftotext")
def test_scan_moi_dong_OCR_co_hop_va_cho_trong_trung_dau_cham_that(tmp_path):
    so = _pdf()
    don_vi = doc("scan.pdf", _scan(so, tmp_path)).don_vi
    assert don_vi and all(d.nguon_chu is NguonChu.ocr for d in don_vi)
    assert all(d.hop and 0 <= d.hop[0] < d.hop[2] <= 596 and 0 <= d.hop[1] < d.hop[3] <= _H for d in don_vi)

    # Sự thật nền: hộp của các "từ" toàn chấm trên CHÍNH bản có lớp chữ.
    that = [c.hop for d in doc("x.pdf", so).don_vi for c in d.cho_trong]
    thay = [c.hop for d in don_vi for c in d.cho_trong]
    assert len(that) >= 7
    trung = sum(any(_chong(a, b) for b in thay) for a in that)
    assert trung >= len(that) - 1, (that, thay)
    assert all(any(_chong(b, a) for a in that) for b in thay), "không bịa chỗ trống ở chỗ không có chấm"

    (ho_ten,) = [d for d in don_vi if "Ho ten" in d.noi_dung]
    assert ho_ten.cho_trong and ho_ten.cho_trong[0].nhan.startswith("Ho ten")


@pytest.mark.skipif(not (_CO_SCAN and _CO_PDFTOTEXT), reason="cần tesseract + vie + pdftoppm + pdftotext")
def test_scan_dong_CHI_co_cham_gan_vao_nhan_ngay_tren(tmp_path):
    """Dòng chấm dài đứng riêng dưới "Dia chi:" không sinh ra chữ OCR nào, nên
    nó không có đơn vị của riêng nó — chỗ trống gắn vào nhãn ngay phía trên."""
    so = _pdf()
    (goc,) = [c.hop for d in doc("x.pdf", so).don_vi if d.noi_dung.startswith("......") for c in d.cho_trong]
    don_vi = doc("scan.pdf", _scan(so, tmp_path)).don_vi
    chu = [d for d in don_vi if any(_chong(c.hop, goc) for c in d.cho_trong)]
    assert len(chu) == 1
    # Tesseract `vie` đọc "Dia chi" thành "Dia chỉ": so tiền tố, không so dấu.
    assert chu[0].noi_dung.startswith(("Dia", "..."))


@pytest.mark.skipif(not _CO_SCAN, reason="cần tesseract + vie + pdftoppm")
def test_scan_THIEU_anh_xam_thi_noi_dung_y_het_va_khong_cho_trong(tmp_path, monkeypatch):
    anh = _scan(_pdf(), tmp_path)
    goc = doc("scan.pdf", anh).don_vi
    monkeypatch.setattr(dtl, "_chay_cong_cu", lambda *a, **k: None)
    thieu = doc("scan.pdf", anh).don_vi
    assert [(d.noi_dung, d.do_tin, d.hop) for d in thieu] == [(d.noi_dung, d.do_tin, d.hop) for d in goc]
    assert all(d.cho_trong == () for d in thieu)


def _ghi_lenh(monkeypatch) -> list[list[str]]:
    """Ghi lại mọi lệnh `_chay_cong_cu` nhận, vẫn chạy thật."""
    lenh: list[list[str]] = []
    that = dtl._chay_cong_cu

    def ghi(mot, vao):
        lenh.append(mot)
        return that(mot, vao)

    monkeypatch.setattr(dtl, "_chay_cong_cu", ghi)
    return lenh


@pytest.mark.skipif(not _CO_SCAN, reason="cần tesseract + vie + pdftoppm")
def test_scan_anh_xam_dung_TUNG_TRANG_mot(tmp_path, monkeypatch):
    """`communicate()` nhận TRỌN stdout vào tiến trình API: ảnh xám của mọi trang
    trong một lượt là cả tệp điểm ảnh nằm trong worker (đo 2026-09-26: 60 trang
    A4 trắng = 464 MB). Mỗi lượt chỉ dựng đúng một trang."""
    anh = _scan(_pdf(trang=2), tmp_path)
    lenh = _ghi_lenh(monkeypatch)
    don_vi = doc("scan.pdf", anh).don_vi
    xam = [mot[-5:] for mot in lenh if "-gray" in mot]
    assert xam == [["-f", "1", "-l", "1", "-"], ["-f", "2", "-l", "2", "-"]]
    assert {d.trang for d in don_vi if d.cho_trong} == {1, 2}


@pytest.mark.skipif(not _CO_SCAN, reason="cần tesseract + vie + pdftoppm")
def test_scan_trang_QUA_TRAN_diem_anh_khong_dung_anh_xam(tmp_path, monkeypatch):
    """Một PDF 1,3 KB khai trang 6000×6000 pt là ~280 Mpx ở 200 dpi. Cỡ trang
    đọc từ PNG đã dựng cho tesseract, TRƯỚC khi xin ảnh xám; quá trần thì trang
    ấy không có chỗ trống (fail closed), chữ OCR và hộp y nguyên."""
    anh = _scan(_pdf(), tmp_path)
    goc = doc("scan.pdf", anh).don_vi
    monkeypatch.setattr(dtl, "_PX_XAM_TOI_DA", 1000, raising=False)
    lenh = _ghi_lenh(monkeypatch)
    qua = doc("scan.pdf", anh).don_vi
    assert [mot for mot in lenh if "-gray" in mot] == []
    assert [(d.noi_dung, d.do_tin, d.hop) for d in qua] == [(d.noi_dung, d.do_tin, d.hop) for d in goc]
    assert all(d.cho_trong == () for d in qua)


# ────────────────────────────────────────────── bộ dò dãy chấm trên ảnh


def _dai(cao=30, rong=400):
    return np.zeros((cao, rong), dtype=bool)


def _cham(den, x0, x1, buoc=12, day=22, co=4):
    for x in range(x0, x1, buoc):
        den[day : day + co, x : x + co] = True


def test_do_day_cham_tach_cham_khoi_chu():
    den = _dai()
    den[5:26, 0:8] = True  # chữ: nét cao
    den[5:26, 12:20] = True
    _cham(den, 40, 300)
    (ra,) = dtl._day_cham_anh(den, 0, 30, 0, 400, 200)
    assert ra[0] == 40 and 290 <= ra[1] <= 300


def test_do_day_cham_bo_qua_hai_cham_le_gach_chan_va_dau_tren_cao():
    den = _dai()
    _cham(den, 40, 64)  # hai chấm
    den[24:26, 100:300] = True  # gạch chân liền
    assert dtl._day_cham_anh(den, 0, 30, 0, 400, 200) == []
    tren = _dai()
    _cham(tren, 40, 300, day=2)  # dấu nhỏ ở PHẦN TRÊN dải chữ
    assert dtl._day_cham_anh(tren, 0, 30, 0, 400, 200) == []


def test_do_day_cham_tren_dai_mong_chi_co_cham():
    den = _dai(cao=4)
    _cham(den, 10, 200, day=0)
    (ra,) = dtl._day_cham_anh(den, 0, 4, 0, 400, 200)
    assert ra[0] == 10


def test_doc_cac_trang_pgm_noi_lien_tu_stdout_pdftoppm():
    """`pdftoppm -gray` không có tên gốc thì ghi MỌI trang liền nhau ra stdout."""
    mot = b"P5\n3 2\n255\n" + bytes([0, 255, 10, 200, 0, 0])
    hai = b"P5\n2 1\n255\n" + bytes([7, 8])
    (a, b) = dtl._cac_trang_pgm(mot + hai)
    assert a.shape == (2, 3) and a[0, 2] == 10
    assert b.shape == (1, 2) and b[0, 1] == 8
    assert dtl._cac_trang_pgm(b"P6\n3 2\n255\n" + bytes(18)) == []
    assert dtl._cac_trang_pgm(b"P5\n3 2\n255\n" + bytes(2)) == []
