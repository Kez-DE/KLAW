"""Bộ áp phép sửa lên khuôn gốc PDF (P3b) — kế hoạch
`docs/plans/completed/khuon-goc-dien-tai-cho.md`, hợp đồng "Edit operations".

`ap_dung_pdf(pdf, don_vi, phep_sua)` đè một trang phủ (reportlab) lên trang
gốc bằng `pypdf` — KHÔNG dựng lại trang gốc. Mọi đơn vị ở đây đến từ CHÍNH bộ
đọc P2b (`doc`) rồi qua đúng ranh giới lưu (`_hang_don_vi` + một vòng JSON),
nên toạ độ là toạ độ thật của poppler chứ không phải số tự đặt. Kiểm bằng công
cụ độc lập với bộ áp: `pdftotext -tsv` (chữ đã điền nằm đâu) và `pdftoppm`
(điểm ảnh nào đổi).
"""

import json
import shutil
import subprocess
from io import BytesIO
from math import ceil, floor
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.services import dien_khuon_pdf as dkp
from src.services import doc_tai_lieu as dtl
from src.services.dien_khuon_pdf import ap_dung_pdf
from src.services.doc_tai_lieu import KhongDocDuoc, LoaiHong, co_ocr, doc
from src.services.tai_lieu import _hang_don_vi

_CO_POPPLER = shutil.which("pdftotext") is not None and shutil.which("pdftoppm") is not None
_CO_SOFFICE = shutil.which("soffice") is not None
_CO_SCAN = _CO_POPPLER and co_ocr()
_BM_M05 = Path.home() / "giấy tờ thực tập" / "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx"
pytestmark = pytest.mark.skipif(not _CO_POPPLER, reason="cần pdftotext + pdftoppm (poppler)")

_TEN = "Nguyễn Văn Ánh"
_SO = "0912 345 678"
_W, _H = 595.0, 842.0

_DONG = [
    (72, 800, "Ho ten: .............................."),
    (72, 776, "Dien thoai: ............ Fax: ............"),
    (72, 752, "Ghi chu chung"),
    (72, 728, "Ghi chu chung"),
    (72, 700, "Het."),
]

# Khung vẽ "chữ đứng thẳng khi HIỂN THỊ" cho từng /Rotate, media box ở gốc.
_KHUNG = {0: (1, 0, 0, 1, 0, 0), 90: (0, 1, -1, 0, _W, 0), 180: (-1, 0, 0, -1, _W, _H), 270: (0, -1, 1, 0, 0, _H)}


def _nen_xam(c, rong: float = _W, cao: float = _H) -> None:
    """Nền xám phủ trang: trên giấy trắng, ô tô trắng tràn khỏi hộp không đổi
    điểm ảnh nào; trên nền xám thì đổi — nên đo được luật "≤ 1 pt ngoài hộp"."""
    c.setFillGray(0.8)
    c.rect(0, 0, rong, cao, stroke=0, fill=1)
    c.setFillGray(0)


def _pdf(dong=_DONG, trang: int = 1, nen: bool = False) -> bytes:
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(_W, _H))
    for _ in range(trang):
        if nen:
            _nen_xam(c)
        c.setFont("Helvetica", 12)
        for x, y, chu in dong:
            c.drawString(x, y, chu)
        c.showPage()
    c.save()
    return buf.getvalue()


def _pdf_xoay(xoay: int) -> bytes:
    """Chữ đứng thẳng trên trang `/Rotate xoay`, media box LỆCH gốc xa
    [-300 400 295 1242] và CropBox khác media box — ba nguồn lệch toạ độ cùng
    lúc. Lệch đủ xa để một lớp phủ bị cắt theo khung [0 0 595 842] của chính nó
    mất sạch chữ."""
    from pypdf import PdfReader, PdfWriter, Transformation
    from pypdf.generic import RectangleObject
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(_W, _H))
    c.setPageRotation(xoay)
    _nen_xam(c)
    c.transform(*_KHUNG[xoay])
    c.setFont("Helvetica", 12)
    cao = _H if xoay in (0, 180) else _W
    c.drawString(100, cao - 150, "Ho ten: ..............................")
    c.drawString(100, cao - 200, "Dien thoai: ............ Fax: ............")
    c.showPage()
    c.save()
    w = PdfWriter(clone_from=PdfReader(BytesIO(buf.getvalue())))
    p = w.pages[0]
    p.add_transformation(Transformation().translate(-300, 400))
    p.mediabox = RectangleObject([-300, 400, _W - 300, _H + 400])
    p.cropbox = RectangleObject([-270, 440, _W - 340, _H + 390])
    ra = BytesIO()
    w.write(ra)
    return ra.getvalue()


def _scan(pdf: bytes, tmp_path: Path) -> bytes:
    """PDF CHỈ có ảnh (200 dpi) — đúng cách `test_doc_tai_lieu_hop_pdf._scan` dựng."""
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    vao = tmp_path / "so.pdf"
    vao.write_bytes(pdf)
    subprocess.run(["pdftoppm", "-r", "200", "-png", str(vao), str(tmp_path / "p")], check=True, timeout=120)
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


def _don_vi(pdf: bytes, ten: str = "x.pdf") -> list[dict]:
    """Đơn vị đúng như `viec_doc_tai_lieu.don_vi` trả về: qua `_hang_don_vi`
    rồi một vòng JSON (jsonb không có tuple)."""
    return json.loads(json.dumps([_hang_don_vi(d) for d in doc(ten, pdf).don_vi], ensure_ascii=False))


def _mot(don_vi: list[dict], dau: str) -> dict:
    (d,) = [d for d in don_vi if d["noi_dung"].startswith(dau)]
    return d


def _tu(pdf: bytes) -> dict[int, list[tuple[str, tuple[float, float, float, float]]]]:
    return {t: [(chu, hop) for _, chu, hop in tu] for t, tu in dtl._tu_pdf(pdf).items()}


def _trong_hop(hop, khung, du: float = 1.0) -> bool:
    return (
        hop[0] >= khung[0] - du and hop[2] <= khung[2] + du and khung[1] - du <= (hop[1] + hop[3]) / 2 <= khung[3] + du
    )


def _chu_trong(pdf: bytes, trang: int, khung) -> str:
    """Các từ poppler có tâm nằm trong `khung`, nối theo x — trừ từ toàn chấm:
    lớp phủ CHE dãy chấm gốc chứ không xoá nó khỏi lớp chữ của trang gốc."""
    tu = sorted((h[0], c) for c, h in _tu(pdf).get(trang, []) if _trong_hop(h, khung, 0.5) and not dtl._la_cham(c))
    return " ".join(c for _, c in tu)


def _anh(pdf: bytes, tmp_path: Path, ten: str) -> list[np.ndarray]:
    tep = tmp_path / f"{ten}.pdf"
    tep.write_bytes(pdf)
    ra = subprocess.run(["pdftoppm", "-r", "72", "-gray", str(tep)], capture_output=True, check=True, timeout=120)
    return dtl._cac_trang_pgm(ra.stdout)


def _mat_na(shape, hops, gian: float = 1.0) -> np.ndarray:
    """Điểm ảnh được phép đổi ở 72 dpi (1 px = 1 pt): MỌI điểm ảnh chạm hộp giãn
    `gian` pt — hợp đồng cho ô tô trắng tràn khỏi hộp tối đa 1 pt; điểm ảnh
    chạm mép được khử răng cưa nên tính là "chạm", không giãn thêm."""
    m = np.zeros(shape, dtype=bool)
    for x0, y0, x1, y1 in hops:
        m[max(0, floor(y0 - gian)) : ceil(y1 + gian), max(0, floor(x0 - gian)) : ceil(x1 + gian)] = True
    return m


def _kho(trang) -> list[float]:
    """Media box tới 1e-4 pt: pypdf ghi lại số thực của trang ĐÃ SỬA với 8 chữ số
    có nghĩa (595.303937007874 → 595.303937) — lệch dưới một phần triệu điểm."""
    return [round(float(v), 4) for v in trang.mediabox]


def _cho(d: dict, so: int = 0) -> dict:
    (c,) = [c for c in d["cho_trong"] if c["so"] == so]
    return c


@pytest.fixture
def phong_moi():
    """Trình dò phông nhớ kết quả suốt tiến trình; test đổi nguồn phông thì xoá nhớ."""
    dkp._phong.cache_clear()
    yield
    dkp._phong.cache_clear()


# ────────────────────────────────────────────────────── hình dạng hợp đồng


def test_khong_phep_sua_tra_NGUYEN_bytes():
    pdf = _pdf()
    ra, bao_cao = ap_dung_pdf(pdf, _don_vi(pdf), [])
    assert ra == pdf
    assert bao_cao == {"da_ap": [], "bo_qua": []}


def test_moi_phep_bi_bo_thi_bytes_y_nguyen_va_bao_cao_du():
    pdf = _pdf()
    ra, bao_cao = ap_dung_pdf(pdf, _don_vi(pdf), [{"loai": "xoa", "don_vi": 0}])
    assert ra == pdf
    assert bao_cao == {"da_ap": [], "bo_qua": [{"phep": 0, "ly_do": "loai_khong_ho_tro"}]}


def test_dien_dat_gia_tri_dung_hop_cho_trong_giu_so_trang_kho_va_xoay():
    from pypdf import PdfReader

    pdf = _pdf(trang=2)
    don_vi = _don_vi(pdf)
    ho_ten = [d for d in don_vi if d["noi_dung"].startswith("Ho ten") and d["trang"] == 1][0]
    dien = [d for d in don_vi if d["noi_dung"].startswith("Dien thoai") and d["trang"] == 1][0]
    phep = [
        {"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": 0, "gia_tri": _TEN},
        {"loai": "dien", "don_vi": dien["chi_so"], "cho_trong": 0, "gia_tri": "024 3"},
    ]
    ra, bao_cao = ap_dung_pdf(pdf, don_vi, phep)
    assert bao_cao == {"da_ap": [0, 1], "bo_qua": []}
    assert _chu_trong(ra, 1, _cho(ho_ten)["hop"]).startswith(_TEN)
    assert _chu_trong(ra, 1, _cho(dien)["hop"]).startswith("024 3")
    assert ra.startswith(pdf), "cập nhật tăng dần: bytes khuôn gốc giữ nguyên, phần sửa nối thêm"
    goc, moi = PdfReader(BytesIO(pdf)), PdfReader(BytesIO(ra))
    assert len(moi.pages) == len(goc.pages) == 2
    for a, b in zip(goc.pages, moi.pages, strict=True):
        assert _kho(a) == _kho(b) and a.rotation == b.rotation


@pytest.mark.parametrize("xoay", [0, 90, 180, 270])
def test_toa_do_poppler_ve_dung_cho_moi_Rotate_media_box_lech_va_CropBox(xoay, tmp_path):
    """Bộ đọc đo ở hệ hiển thị của poppler (gốc trên-trái của MEDIA box, sau
    /Rotate). Chữ điền phải hiện lại ĐÚNG hộp ấy, nằm ngang, khi poppler đọc
    lại — lệch gốc media box, bỏ quên /Rotate hay lấy nhầm CropBox đều làm nó
    rơi ra ngoài hộp. pdftotext đọc cả chữ bị cắt khuất, nên điểm ảnh (dựng
    theo media box, như bộ đọc) phải đổi TRONG hộp và chỉ trong hộp."""
    pdf = _pdf_xoay(xoay)
    don_vi = _don_vi(pdf)
    ho_ten, dien = _mot(don_vi, "Ho ten"), _mot(don_vi, "Dien thoai")
    phep = [
        {"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": 0, "gia_tri": _TEN},
        {"loai": "dien", "don_vi": dien["chi_so"], "cho_trong": 1, "gia_tri": "024"},
    ]
    ra, bao_cao = ap_dung_pdf(pdf, don_vi, phep)
    assert bao_cao["da_ap"] == [0, 1], bao_cao
    tu = _tu(ra)[1]
    for c, gia_tri in ((_cho(ho_ten), _TEN), (_cho(dien, 1), "024")):
        khop = [(chu, h) for chu, h in tu if chu in gia_tri.split() and _trong_hop(h, c["hop"])]
        assert [chu for chu, _ in khop] == gia_tri.split(), (xoay, c["hop"], tu)
        assert all(h[2] - h[0] > h[3] - h[1] for chu, h in khop if len(chu) > 2), "chữ phải nằm ngang khi hiển thị"
    (a,), (b,) = _anh(pdf, tmp_path, "goc"), _anh(ra, tmp_path, "moi")
    doi = a != b
    for c in (_cho(ho_ten), _cho(dien, 1)):
        x0, y0, x1, y1 = c["hop"]
        assert (doi & _mat_na(a.shape, [c["hop"]], 0)).sum() > 0.5 * (x1 - x0) * (y1 - y0), "ô tô trắng phải hiện"
    assert not (doi & ~_mat_na(a.shape, [_cho(ho_ten)["hop"], _cho(dien, 1)["hop"]])).any()


# ───────────────────────────────────────────────────── mã bỏ qua, không đoán


def test_phep_khong_hop_le_bi_bo_qua_voi_dung_ma(phong_moi):
    pdf = _pdf()
    don_vi = _don_vi(pdf)
    ho_ten, dien, het = _mot(don_vi, "Ho ten"), _mot(don_vi, "Dien thoai"), _mot(don_vi, "Het")
    ghi_chu = [d for d in don_vi if d["noi_dung"] == "Ghi chu chung"][0]
    assert "hop" not in ghi_chu, "hai dòng trùng chữ không có hộp (P2b)"
    phep = [
        {"loai": "chen_sau", "don_vi": ho_ten["chi_so"], "noi_dung": "x"},
        {"loai": "xoa", "don_vi": ho_ten["chi_so"]},
        {"loai": "dien", "don_vi": 999, "cho_trong": 0, "gia_tri": "A"},
        {"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": 5, "gia_tri": "A"},
        {"loai": "thay", "don_vi": ghi_chu["chi_so"], "noi_dung": "B"},
        {"loai": "dien", "don_vi": dien["chi_so"], "cho_trong": 0, "gia_tri": "x" * 200},
        {"loai": "dien", "don_vi": dien["chi_so"], "cho_trong": 1, "gia_tri": "  "},
        {"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": 0, "gia_tri": "A"},
        {"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": 0, "gia_tri": "B"},
        {"loai": "thay", "don_vi": het["chi_so"], "noi_dung": "Hết."},
        "khong phai dict",
        {"loai": "dien", "don_vi": True, "cho_trong": 0, "gia_tri": "A"},
        {"loai": "dien", "don_vi": dien["chi_so"], "cho_trong": 1, "gia_tri": "\U0001f600"},
        {"loai": "dien", "don_vi": dien["chi_so"], "cho_trong": 1, "gia_tri": "a\nb"},
        {"loai": "gi_do", "don_vi": ho_ten["chi_so"]},
        {"loai": "dien", "don_vi": 999, "cho_trong": 0, "gia_tri": ""},
        {"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": "0", "gia_tri": "A"},
    ]
    _, bao_cao = ap_dung_pdf(pdf, don_vi, phep)
    # Cùng luật bộ áp DOCX (P3a): hình dạng sai trước mọi tra cứu là
    # `khong_hop_le`; phép TRƯỚC giữ chỗ, phép sau chồng lên nó là `xung_dot`;
    # mã là chuỗi thường để lưu thẳng vào jsonb.
    assert all(type(b["ly_do"]) is str for b in bao_cao["bo_qua"])
    assert bao_cao == {
        "da_ap": [7, 9],
        "bo_qua": [
            {"phep": 0, "ly_do": "loai_khong_ho_tro"},
            {"phep": 1, "ly_do": "loai_khong_ho_tro"},
            {"phep": 2, "ly_do": "khong_co_don_vi"},
            {"phep": 3, "ly_do": "khong_co_cho_trong"},
            {"phep": 4, "ly_do": "khong_co_dia_chi"},
            {"phep": 5, "ly_do": "khong_vua"},
            {"phep": 6, "ly_do": "khong_hop_le"},
            {"phep": 8, "ly_do": "xung_dot"},
            {"phep": 10, "ly_do": "khong_hop_le"},
            {"phep": 11, "ly_do": "khong_hop_le"},
            {"phep": 12, "ly_do": "khong_co_phong"},
            {"phep": 13, "ly_do": "khong_hop_le"},
            {"phep": 14, "ly_do": "loai_khong_ho_tro"},
            {"phep": 15, "ly_do": "khong_hop_le"},
            {"phep": 16, "ly_do": "khong_hop_le"},
        ],
    }


def test_thay_THEO_DOAN_la_loai_khong_ho_tro_tren_PDF():
    """PDF giữ `thay` cả dòng; `doan` (một đoạn của ô DOCX) không có nghĩa ở đây."""
    pdf = _pdf()
    don_vi = _don_vi(pdf)
    ho_ten = _mot(don_vi, "Ho ten")
    ra, bao_cao = ap_dung_pdf(pdf, don_vi, [{"loai": "thay", "don_vi": ho_ten["chi_so"], "doan": 0, "noi_dung": "A"}])
    assert bao_cao == {"da_ap": [], "bo_qua": [{"phep": 0, "ly_do": "loai_khong_ho_tro"}]} and ra == pdf


def test_hop_ngoai_trang_la_khong_co_dia_chi():
    """Toạ độ không thuộc trang này (dòng lưu hỏng, trang không tồn tại) thì
    không vẽ ra ngoài trang — bỏ qua."""
    pdf = _pdf()
    don_vi = _don_vi(pdf)
    ho_ten = _mot(don_vi, "Ho ten")
    lech = json.loads(json.dumps(don_vi))
    _mot(lech, "Ho ten")["cho_trong"][0]["hop"] = [700.0, 100.0, 800.0, 112.0]
    _mot(lech, "Het")["trang"] = 3
    phep = [
        {"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": 0, "gia_tri": "A"},
        {"loai": "thay", "don_vi": _mot(don_vi, "Het")["chi_so"], "noi_dung": "B"},
    ]
    _, bao_cao = ap_dung_pdf(pdf, lech, phep)
    assert bao_cao["bo_qua"] == [{"phep": 0, "ly_do": "khong_co_dia_chi"}, {"phep": 1, "ly_do": "khong_co_dia_chi"}]


def test_gia_tri_dai_hon_hop_duoc_thu_nho_toi_70_phan_tram(phong_moi):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    pdf = _pdf()
    don_vi = _don_vi(pdf)
    dien = _mot(don_vi, "Dien thoai")
    c = _cho(dien, 1)
    rong = c["hop"][2] - c["hop"][0]
    co = c["co_chu"] / dkp._TY_LE_CO_CHU
    ten = dkp._phong().fontName
    so = ["0" * n for n in range(1, 40)]
    vua = next(s for s in so if 1.05 < stringWidth(s, ten, co) / rong < 1.35)
    qua = next(s for s in so if stringWidth(s, ten, co) / rong > 1 / 0.7)
    ra, bao_cao = ap_dung_pdf(pdf, don_vi, [{"loai": "dien", "don_vi": dien["chi_so"], "cho_trong": 1, "gia_tri": vua}])
    assert bao_cao["da_ap"] == [0]
    ((_, h),) = [(chu, h) for chu, h in _tu(ra)[1] if chu == vua]
    assert h[0] >= c["hop"][0] - 0.5 and h[2] <= c["hop"][2] + 0.5
    _, bao_cao = ap_dung_pdf(pdf, don_vi, [{"loai": "dien", "don_vi": dien["chi_so"], "cho_trong": 1, "gia_tri": qua}])
    assert bao_cao["bo_qua"] == [{"phep": 0, "ly_do": "khong_vua"}]


def test_thay_to_trang_hop_dong_va_viet_mot_dong_moi():
    """`thay` phải vừa hộp của CHÍNH dòng ấy (≥70 % cỡ chữ) — PDF không dàn lại."""
    pdf = _pdf()
    don_vi = _don_vi(pdf)
    ho_ten, het = _mot(don_vi, "Ho ten"), _mot(don_vi, "Het")
    moi = "Họ tên: Nguyễn Văn Ánh"
    ra, bao_cao = ap_dung_pdf(
        pdf,
        don_vi,
        [
            {"loai": "thay", "don_vi": ho_ten["chi_so"], "noi_dung": moi},
            {"loai": "thay", "don_vi": het["chi_so"], "noi_dung": "Hết hạn hợp đồng lao động."},
        ],
    )
    assert bao_cao == {"da_ap": [0], "bo_qua": [{"phep": 1, "ly_do": "khong_vua"}]}
    # Lớp phủ CHE chữ cũ chứ không xoá nó khỏi lớp chữ gốc: poppler vẫn đọc ra
    # "Ho ten: ..." xen giữa — chữ mới phải có đủ, đúng thứ tự, đúng dấu.
    cu = set(ho_ten["noi_dung"].split())
    assert [w for w in _chu_trong(ra, 1, ho_ten["hop"]).split() if w not in cu] == moi.split()


def test_PDF_hong_hay_co_mat_khau_nem_loi_co_ma():
    with pytest.raises(KhongDocDuoc) as e:
        ap_dung_pdf(b"khong phai pdf", [], [{"loai": "dien", "don_vi": 0, "cho_trong": 0, "gia_tri": "A"}])
    assert e.value.ly_do is LoaiHong.tep_hong
    from pypdf import PdfReader, PdfWriter

    w = PdfWriter(clone_from=PdfReader(BytesIO(_pdf())))
    w.encrypt("mat-khau")
    buf = BytesIO()
    w.write(buf)
    with pytest.raises(KhongDocDuoc) as e:
        ap_dung_pdf(buf.getvalue(), [], [{"loai": "dien", "don_vi": 0, "cho_trong": 0, "gia_tri": "A"}])
    assert e.value.ly_do is LoaiHong.can_mat_khau


# ──────────────────────────── luồng của khuôn gốc: không bao giờ giải mã


def _them_luong(pdf: bytes, bo_loc: str) -> bytes:
    """Thêm vào tài nguyên trang 1 một ảnh (không vẽ) mang bộ lọc `bo_loc` và
    dữ liệu rác — như ảnh JBIG2 của máy scan văn phòng hay luồng riêng của
    một trình soạn: poppler, và bộ đọc, vẫn đọc được tệp."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, NumberObject, StreamObject

    w = PdfWriter(clone_from=PdfReader(BytesIO(pdf)))
    luong = StreamObject.initialize_from_dictionary(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(8),
            NameObject("/Height"): NumberObject(8),
            NameObject("/BitsPerComponent"): NumberObject(1),
            NameObject("/Filter"): NameObject(bo_loc),
            "__streamdata__": b"\x97JB2\r\n\x1a\nrac",
        }
    )
    w.pages[0]["/Resources"][NameObject("/XObject")] = DictionaryObject({NameObject("/Rac"): w._add_object(luong)})
    ra = BytesIO()
    w.write(ra)
    return ra.getvalue()


@pytest.mark.parametrize("bo_loc", ["/JBIG2Decode", "/BoLocRieng"])
def test_luong_goc_khong_giai_ma_duoc_van_dien_duoc(bo_loc):
    """Ảnh Docker không có `jbig2dec`, và pypdf không có mọi bộ lọc: bộ áp chỉ
    ghi phần nối thêm nên KHÔNG được giải mã luồng nào của khuôn gốc."""
    import pypdf

    pdf = _them_luong(_pdf(), bo_loc)
    don_vi = _don_vi(pdf)
    ho_ten = _mot(don_vi, "Ho ten")
    phep = [{"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": 0, "gia_tri": _TEN}]
    with pypdf.apply_configuration(jbig2dec_binary=None):
        ra, bao_cao = ap_dung_pdf(pdf, don_vi, phep)
    assert bao_cao == {"da_ap": [0], "bo_qua": []}
    assert ra.startswith(pdf)
    assert _chu_trong(ra, 1, _cho(ho_ten)["hop"]).startswith(_TEN)


def test_ban_scan_anh_khong_mat_du_lieu_khong_bi_giai_ma():
    """Scan lưu ảnh không mất dữ liệu: vài KB trên đĩa, hàng chục MB khi giải
    mã. Đỉnh bộ nhớ một lượt điền phải dưới MỘT trang ảnh đã giải mã — tức là
    không ảnh nào của khuôn gốc bị giải mã."""
    import tracemalloc

    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    rong, cao = 1654, 2339  # A4 200 dpi, RGB: 11,6 MB mỗi trang khi giải mã
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(_W, _H))
    for xam in (240, 245):  # hai ảnh KHÁC nhau: reportlab gộp ảnh trùng
        c.drawImage(ImageReader(Image.new("RGB", (rong, cao), (xam,) * 3)), 0, 0, _W, _H)
        c.setFont("Helvetica", 12)
        for x, y, chu in _DONG:
            c.drawString(x, y, chu)
        c.showPage()
    c.save()
    pdf = buf.getvalue()
    ho_ten = next(d for d in _don_vi(pdf) if d["noi_dung"].startswith("Ho ten") and d["trang"] == 1)
    phep = [{"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": 0, "gia_tri": _TEN}]
    ap_dung_pdf(pdf, [ho_ten], phep)  # làm nóng: dò phông, import
    tracemalloc.start()
    try:
        _, bao_cao = ap_dung_pdf(pdf, [ho_ten], phep)
        _, dinh = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert bao_cao["da_ap"] == [0]
    assert dinh < rong * cao * 3, dinh


# ─────────────────────────────────────────────────────────────── phông chữ


def test_khong_tim_thay_phong_thi_moi_phep_la_khong_co_phong(monkeypatch, tmp_path, phong_moi):
    pdf = _pdf()
    don_vi = _don_vi(pdf)
    ho_ten, het = _mot(don_vi, "Ho ten"), _mot(don_vi, "Het")
    phep = [
        {"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": 0, "gia_tri": _TEN},
        {"loai": "thay", "don_vi": het["chi_so"], "noi_dung": "B"},
    ]
    monkeypatch.setattr(dkp, "_UNG_VIEN_PHONG", ())
    monkeypatch.setattr(dkp, "get_settings", lambda: SimpleNamespace(phong_dien_path=""))
    ra, bao_cao = ap_dung_pdf(pdf, don_vi, phep)
    assert ra == pdf
    assert bao_cao["bo_qua"] == [{"phep": 0, "ly_do": "khong_co_phong"}, {"phep": 1, "ly_do": "khong_co_phong"}]

    # Đường dẫn cấu hình CÓ đặt thì chỉ dùng nó — hỏng là hỏng, không lặng lẽ lùi về danh sách.
    dkp._phong.cache_clear()
    monkeypatch.setattr(dkp, "get_settings", lambda: SimpleNamespace(phong_dien_path=str(tmp_path / "khong.ttf")))
    _, bao_cao = ap_dung_pdf(pdf, don_vi, phep)
    assert [b["ly_do"] for b in bao_cao["bo_qua"]] == ["khong_co_phong", "khong_co_phong"]


def test_phong_hong_cau_truc_la_khong_co_phong(monkeypatch, tmp_path, phong_moi):
    """Tệp TTF cụt: reportlab ném `struct.error`, không phải `TTFError`."""
    pdf = _pdf()
    don_vi = _don_vi(pdf)
    ho_ten, het = _mot(don_vi, "Ho ten"), _mot(don_vi, "Het")
    phep = [
        {"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": 0, "gia_tri": _TEN},
        {"loai": "thay", "don_vi": het["chi_so"], "noi_dung": "B"},
    ]
    cut = tmp_path / "cut.ttf"
    cut.write_bytes(Path(dkp._phong().face.filename).read_bytes()[:20_000])
    dkp._phong.cache_clear()
    monkeypatch.setattr(dkp, "get_settings", lambda: SimpleNamespace(phong_dien_path=str(cut)))
    ra, bao_cao = ap_dung_pdf(pdf, don_vi, phep)
    assert ra == pdf
    assert bao_cao["bo_qua"] == [{"phep": 0, "ly_do": "khong_co_phong"}, {"phep": 1, "ly_do": "khong_co_phong"}]


def test_duong_dan_phong_cau_hinh_duoc_dung_va_co_alias_KLAW(monkeypatch, phong_moi):
    from src.config import Settings

    that = dkp._phong()
    assert that is not None, "máy chạy test phải có một phông tiếng Việt trong danh sách ứng viên"
    monkeypatch.setenv("KLAW_PHONG_DIEN_PATH", that.face.filename)
    s = Settings(_env_file=None)
    assert s.phong_dien_path == that.face.filename
    dkp._phong.cache_clear()
    monkeypatch.setattr(dkp, "_UNG_VIEN_PHONG", ())
    monkeypatch.setattr(dkp, "get_settings", lambda: s)
    assert dkp._phong().face.filename == that.face.filename


# ─────────────────────────────────────────── điểm ảnh: chỉ đổi trong hộp


def test_diem_anh_chi_doi_trong_hop_to_trang(tmp_path):
    pdf = _pdf(nen=True)
    don_vi = _don_vi(pdf)
    ho_ten, dien, het = _mot(don_vi, "Ho ten"), _mot(don_vi, "Dien thoai"), _mot(don_vi, "Het")
    phep = [
        {"loai": "dien", "don_vi": ho_ten["chi_so"], "cho_trong": 0, "gia_tri": _TEN},
        {"loai": "dien", "don_vi": dien["chi_so"], "cho_trong": 0, "gia_tri": "024"},
        {"loai": "thay", "don_vi": het["chi_so"], "noi_dung": "Hết."},
    ]
    ra, bao_cao = ap_dung_pdf(pdf, don_vi, phep)
    assert bao_cao["da_ap"] == [0, 1, 2]
    (a,), (b,) = _anh(pdf, tmp_path, "goc"), _anh(ra, tmp_path, "moi")
    doi = a != b
    duoc = _mat_na(a.shape, [_cho(ho_ten)["hop"], _cho(dien)["hop"], het["hop"]])
    assert doi.any()
    assert not (doi & ~duoc).any(), np.argwhere(doi & ~duoc)[:5]


# ─────────────────────────────────────────── biểu mẫu thật của chủ dự án


def _bm_m05_pdf(tmp_path: Path) -> bytes:
    vao = tmp_path / "bm.docx"
    vao.write_bytes(_BM_M05.read_bytes())
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmp_path), str(vao)],
        check=True,
        capture_output=True,
        timeout=180,
    )
    return (tmp_path / "bm.pdf").read_bytes()


def _gia_tri(c: dict) -> str:
    """Tên / số điện thoại cho chỗ đủ rộng; chỗ ngày-tháng hẹp nhận "26"."""
    if c["hop"][2] - c["hop"][0] < 40:
        return "26"
    return _SO if "thoại" in c["nhan"] else _TEN


def _dien_moi_cho(don_vi: list[dict]) -> list[dict]:
    return [
        {"loai": "dien", "don_vi": d["chi_so"], "cho_trong": c["so"], "gia_tri": _gia_tri(c)}
        for d in don_vi
        for c in d.get("cho_trong", [])
    ]


@pytest.mark.skipif(not (_BM_M05.exists() and _CO_SOFFICE), reason="cần kho mẫu ngoài repo + soffice")
def test_BM_M05_dien_moi_cho_trong_chu_dung_dau_va_diem_anh_chi_doi_trong_hop(tmp_path):
    from pypdf import PdfReader

    pdf = _bm_m05_pdf(tmp_path)
    don_vi = _don_vi(pdf)
    phep = _dien_moi_cho(don_vi)
    assert len(phep) >= 25
    ra, bao_cao = ap_dung_pdf(pdf, don_vi, phep)
    assert bao_cao == {"da_ap": list(range(len(phep))), "bo_qua": []}

    theo = {(d["chi_so"], c["so"]): (d["trang"], c) for d in don_vi for c in d.get("cho_trong", [])}
    hop_theo_trang: dict[int, list] = {}
    for i in bao_cao["da_ap"]:
        trang, c = theo[(phep[i]["don_vi"], phep[i]["cho_trong"])]
        assert _chu_trong(ra, trang, c["hop"]) == phep[i]["gia_tri"], (c, _chu_trong(ra, trang, c["hop"]))
        hop_theo_trang.setdefault(trang, []).append(c["hop"])

    goc, moi = PdfReader(BytesIO(pdf)), PdfReader(BytesIO(ra))
    assert len(moi.pages) == len(goc.pages) == 2
    assert [_kho(p) for p in moi.pages] == [_kho(p) for p in goc.pages]
    for a, b, t in zip(_anh(pdf, tmp_path, "goc"), _anh(ra, tmp_path, "moi"), (1, 2), strict=True):
        doi = a != b
        assert not (doi & ~_mat_na(a.shape, hop_theo_trang.get(t, []))).any(), t


@pytest.mark.skipif(not (_BM_M05.exists() and _CO_SOFFICE), reason="cần kho mẫu ngoài repo + soffice")
def test_BM_M05_trang_khong_co_phep_sua_giong_tung_diem_anh(tmp_path):
    pdf = _bm_m05_pdf(tmp_path)
    don_vi = _don_vi(pdf)
    phep = [p for p in _dien_moi_cho(don_vi) if _mot_chi_so(don_vi, p["don_vi"])["trang"] == 1]
    ra, bao_cao = ap_dung_pdf(pdf, don_vi, phep)
    assert bao_cao["da_ap"]
    (a1, a2), (b1, b2) = _anh(pdf, tmp_path, "goc"), _anh(ra, tmp_path, "moi")
    assert (a1 != b1).any()
    assert np.array_equal(a2, b2)


def _mot_chi_so(don_vi: list[dict], chi_so: int) -> dict:
    (d,) = [d for d in don_vi if d["chi_so"] == chi_so]
    return d


@pytest.mark.skipif(not (_BM_M05.exists() and _CO_SOFFICE and _CO_SCAN), reason="cần kho mẫu + soffice + tesseract vie")
def test_BM_M05_ban_scan_dien_cung_duong_de_len_anh(tmp_path):
    """Bản scan: trang là một ảnh, lớp phủ nằm trên ảnh — và mang lớp chữ của
    giá trị, nên pdftotext đọc lại được đúng dấu. Chỗ hẹp mà cỡ chữ ước từ dòng
    OCR không vừa thì `khong_vua`; mọi chỗ rộng đều được điền."""
    from pypdf import PdfReader

    scan = _scan(_bm_m05_pdf(tmp_path), tmp_path)
    don_vi = _don_vi(scan, "scan.pdf")
    assert all(d["nguon_chu"] == "ocr" for d in don_vi)
    phep = _dien_moi_cho(don_vi)
    assert len(phep) >= 15, len(phep)
    ra, bao_cao = ap_dung_pdf(scan, don_vi, phep)
    assert {b["ly_do"] for b in bao_cao["bo_qua"]} <= {"khong_vua"}, bao_cao

    theo = {(d["chi_so"], c["so"]): (d["trang"], c) for d in don_vi for c in d.get("cho_trong", [])}
    hop = {i: theo[(p["don_vi"], p["cho_trong"])][1]["hop"] for i, p in enumerate(phep)}
    rong = [i for i, h in hop.items() if h[2] - h[0] >= 100]
    assert len(rong) >= 5 and set(rong) <= set(bao_cao["da_ap"])
    tu = _tu(ra)
    # MỘT cỡ chữ cho cả trang scan: chiều cao dòng OCR của các nhãn lệch tới
    # ±30 % (10,8–18 pt cho cùng chữ 13 pt), chữ điền thì không được lệch theo.
    cao = {round(h[3] - h[1], 1) for chu, h in tu[1] if chu in _TEN.split()}
    assert len(cao) == 1, cao
    duoc: dict[int, list] = {}
    for i in bao_cao["da_ap"]:
        trang, c = theo[(phep[i]["don_vi"], phep[i]["cho_trong"])]
        x0, y0, x1, y1 = c["hop"]
        # Trên dải chỉ có chấm, chữ đứng TRÊN đường chấm: so theo cột và theo đường chân chữ.
        khop = sorted(
            (h[0], chu)
            for chu, h in tu.get(trang, [])
            if x0 - 1 <= h[0] and h[2] <= x1 + 1 and abs(h[3] - y1) <= c["co_chu"]
        )
        assert " ".join(chu for _, chu in khop) == phep[i]["gia_tri"], (c, khop)
        duoc.setdefault(trang, []).append([x0, min(y0, y1 - 1.2 * c["co_chu"]), x1, max(y1, y1 + 0.3 * c["co_chu"])])
    goc, moi = PdfReader(BytesIO(scan)), PdfReader(BytesIO(ra))
    assert len(moi.pages) == len(goc.pages)
    assert [_kho(p) for p in moi.pages] == [_kho(p) for p in goc.pages]
    for t, (a, b) in enumerate(zip(_anh(scan, tmp_path, "goc"), _anh(ra, tmp_path, "moi"), strict=True), start=1):
        assert not ((a != b) & ~_mat_na(a.shape, duoc.get(t, []))).any(), t
