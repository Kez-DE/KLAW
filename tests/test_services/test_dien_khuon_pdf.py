"""Bộ áp phép sửa lên khuôn gốc PDF (P3b) — kế hoạch
`docs/plans/active/khuon-goc-dien-tai-cho.md`, hợp đồng "Edit operations".

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


def _pdf(dong=_DONG, trang: int = 1) -> bytes:
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(_W, _H))
    for _ in range(trang):
        c.setFont("Helvetica", 12)
        for x, y, chu in dong:
            c.drawString(x, y, chu)
        c.showPage()
    c.save()
    return buf.getvalue()


def _pdf_xoay(xoay: int) -> bytes:
    """Chữ đứng thẳng trên trang `/Rotate xoay`, media box LỆCH gốc
    [-30 40 565 882] và CropBox khác media box — ba nguồn lệch toạ độ cùng lúc."""
    from pypdf import PdfReader, PdfWriter, Transformation
    from pypdf.generic import RectangleObject
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(_W, _H))
    c.setPageRotation(xoay)
    c.transform(*_KHUNG[xoay])
    c.setFont("Helvetica", 12)
    cao = _H if xoay in (0, 180) else _W
    c.drawString(100, cao - 150, "Ho ten: ..............................")
    c.drawString(100, cao - 200, "Dien thoai: ............ Fax: ............")
    c.showPage()
    c.save()
    w = PdfWriter(clone_from=PdfReader(BytesIO(buf.getvalue())))
    p = w.pages[0]
    p.add_transformation(Transformation().translate(-30, 40))
    p.mediabox = RectangleObject([-30, 40, _W - 30, _H + 40])
    p.cropbox = RectangleObject([0, 80, _W - 70, _H - 10])
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
        hop[0] >= khung[0] - du
        and hop[2] <= khung[2] + du
        and khung[1] - du <= (hop[1] + hop[3]) / 2 <= khung[3] + du
    )


def _chu_trong(pdf: bytes, trang: int, khung) -> str:
    """Các từ poppler có tâm nằm trong `khung`, nối theo x."""
    tu = sorted((h[0], c) for c, h in _tu(pdf).get(trang, []) if _trong_hop(h, khung, 0.5))
    return " ".join(c for _, c in tu)


def _anh(pdf: bytes, tmp_path: Path, ten: str) -> list[np.ndarray]:
    tep = tmp_path / f"{ten}.pdf"
    tep.write_bytes(pdf)
    ra = subprocess.run(["pdftoppm", "-r", "72", "-gray", str(tep)], capture_output=True, check=True, timeout=120)
    return dtl._cac_trang_pgm(ra.stdout)


def _mat_na(shape, hops, gian: float = 1.0) -> np.ndarray:
    """Vùng được phép đổi ở 72 dpi (1 px = 1 pt): hộp + `gian` pt + 1 px giãn."""
    m = np.zeros(shape, dtype=bool)
    for x0, y0, x1, y1 in hops:
        m[max(0, int(y0 - gian) - 1) : int(y1 + gian) + 2, max(0, int(x0 - gian) - 1) : int(x1 + gian) + 2] = True
    return m


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
    goc, moi = PdfReader(BytesIO(pdf)), PdfReader(BytesIO(ra))
    assert len(moi.pages) == len(goc.pages) == 2
    for a, b in zip(goc.pages, moi.pages, strict=True):
        assert list(a.mediabox) == list(b.mediabox) and a.rotation == b.rotation


@pytest.mark.parametrize("xoay", [0, 90, 180, 270])
def test_toa_do_poppler_ve_dung_cho_moi_Rotate_media_box_lech_va_CropBox(xoay):
    """Bộ đọc đo ở hệ hiển thị của poppler (gốc trên-trái của MEDIA box, sau
    /Rotate). Chữ điền phải hiện lại ĐÚNG hộp ấy, nằm ngang, khi poppler đọc
    lại — lệch gốc media box, bỏ quên /Rotate hay lấy nhầm CropBox đều làm nó
    rơi ra ngoài hộp."""
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
    ]
    _, bao_cao = ap_dung_pdf(pdf, don_vi, phep)
    assert bao_cao == {
        "da_ap": [9],
        "bo_qua": [
            {"phep": 0, "ly_do": "loai_khong_ho_tro"},
            {"phep": 1, "ly_do": "loai_khong_ho_tro"},
            {"phep": 2, "ly_do": "khong_co_don_vi"},
            {"phep": 3, "ly_do": "khong_co_cho_trong"},
            {"phep": 4, "ly_do": "khong_co_dia_chi"},
            {"phep": 5, "ly_do": "khong_vua"},
            {"phep": 6, "ly_do": "khong_hop_le"},
            {"phep": 7, "ly_do": "xung_dot"},
            {"phep": 8, "ly_do": "xung_dot"},
            {"phep": 10, "ly_do": "khong_hop_le"},
            {"phep": 11, "ly_do": "khong_co_don_vi"},
            {"phep": 12, "ly_do": "khong_co_phong"},
            {"phep": 13, "ly_do": "khong_hop_le"},
            {"phep": 14, "ly_do": "loai_khong_ho_tro"},
        ],
    }


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
    vua = next(s for s in ("0912", "09123", "091234", "0912345") if 1 < stringWidth(s, ten, co) / rong < 1 / 0.7)
    qua = next(s for s in ("0912345678", "09123456789012") if stringWidth(s, ten, co) / rong > 1 / 0.7)
    ra, bao_cao = ap_dung_pdf(pdf, don_vi, [{"loai": "dien", "don_vi": dien["chi_so"], "cho_trong": 1, "gia_tri": vua}])
    assert bao_cao["da_ap"] == [0]
    ((_, h),) = [(chu, h) for chu, h in _tu(ra)[1] if chu == vua]
    assert h[0] >= c["hop"][0] - 0.5 and h[2] <= c["hop"][2] + 0.5
    _, bao_cao = ap_dung_pdf(pdf, don_vi, [{"loai": "dien", "don_vi": dien["chi_so"], "cho_trong": 1, "gia_tri": qua}])
    assert bao_cao["bo_qua"] == [{"phep": 0, "ly_do": "khong_vua"}]


def test_thay_to_trang_hop_dong_va_viet_mot_dong_moi():
    pdf = _pdf()
    don_vi = _don_vi(pdf)
    het = _mot(don_vi, "Het")
    ra, bao_cao = ap_dung_pdf(pdf, don_vi, [{"loai": "thay", "don_vi": het["chi_so"], "noi_dung": "Hết hạn."}])
    assert bao_cao["da_ap"] == [0]
    assert "Hết hạn." in _chu_trong(ra, 1, [het["hop"][0], het["hop"][1], het["hop"][0] + 200, het["hop"][3]])


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
    pdf = _pdf()
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


def _dien_moi_cho(don_vi: list[dict]) -> list[dict]:
    return [
        {"loai": "dien", "don_vi": d["chi_so"], "cho_trong": c["so"], "gia_tri": _SO if "thoại" in c["nhan"] else _TEN}
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
    assert {b["ly_do"] for b in bao_cao["bo_qua"]} <= {"khong_vua"}, bao_cao
    assert len(bao_cao["da_ap"]) + len(bao_cao["bo_qua"]) == len(phep)

    theo = {(d["chi_so"], c["so"]): (d["trang"], c) for d in don_vi for c in d.get("cho_trong", [])}
    hop_theo_trang: dict[int, list] = {}
    for i in bao_cao["da_ap"]:
        trang, c = theo[(phep[i]["don_vi"], phep[i]["cho_trong"])]
        assert _chu_trong(ra, trang, c["hop"]) == phep[i]["gia_tri"], (c, _chu_trong(ra, trang, c["hop"]))
        hop_theo_trang.setdefault(trang, []).append(c["hop"])
    # Mọi chỗ trống đủ rộng cho giá trị đều được điền — "không vừa" chỉ ở chỗ hẹp.
    for b in bao_cao["bo_qua"]:
        _, c = theo[(phep[b["phep"]]["don_vi"], phep[b["phep"]]["cho_trong"])]
        assert c["hop"][2] - c["hop"][0] < 110, c

    goc, moi = PdfReader(BytesIO(pdf)), PdfReader(BytesIO(ra))
    assert len(moi.pages) == len(goc.pages) == 2
    assert [list(p.mediabox) for p in moi.pages] == [list(p.mediabox) for p in goc.pages]
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


@pytest.mark.skipif(
    not (_BM_M05.exists() and _CO_SOFFICE and _CO_SCAN), reason="cần kho mẫu + soffice + tesseract vie"
)
def test_BM_M05_ban_scan_dien_cung_duong_de_len_anh(tmp_path):
    from pypdf import PdfReader

    scan = _scan(_bm_m05_pdf(tmp_path), tmp_path)
    don_vi = _don_vi(scan, "scan.pdf")
    assert all(d["nguon_chu"] == "ocr" for d in don_vi)
    phep = _dien_moi_cho(don_vi)
    assert len(phep) >= 15, len(phep)
    ra, bao_cao = ap_dung_pdf(scan, don_vi, phep)
    assert {b["ly_do"] for b in bao_cao["bo_qua"]} <= {"khong_vua", "xung_dot"}, bao_cao
    assert len(bao_cao["da_ap"]) >= 10, bao_cao

    theo = {(d["chi_so"], c["so"]): (d["trang"], c) for d in don_vi for c in d.get("cho_trong", [])}
    tu = _tu(ra)
    for i in bao_cao["da_ap"]:
        trang, c = theo[(phep[i]["don_vi"], phep[i]["cho_trong"])]
        x0, _, x1, y1 = c["hop"]
        # Trên dải chỉ có chấm, chữ đứng TRÊN đường chấm: so theo cột và theo đường chân chữ.
        khop = sorted((h[0], chu) for chu, h in tu.get(trang, []) if x0 - 1 <= h[0] and h[2] <= x1 + 1 and abs(h[3] - y1) <= c["co_chu"])
        assert " ".join(chu for _, chu in khop) == phep[i]["gia_tri"], (c, khop)
    goc, moi = PdfReader(BytesIO(scan)), PdfReader(BytesIO(ra))
    assert len(moi.pages) == len(goc.pages)
    assert [list(p.mediabox) for p in moi.pages] == [list(p.mediabox) for p in goc.pages]
