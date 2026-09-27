"""Chốt cái thước `eval/run_khuon_goc.py` — cách chấm không được đổi trong im lặng.

Tệp mẫu dựng NGAY TRONG test: biểu mẫu của chủ dự án nằm ngoài repo và không
bao giờ commit. Phần chấm điểm là hàm thuần trên mảng điểm ảnh và chuỗi, test
không cần công cụ nào; phần đi qua LibreOffice/poppler/tesseract tự bỏ qua khi
máy không có.
"""

import shutil
import zipfile
from io import BytesIO

import numpy as np
import pytest

from eval import run_khuon_goc as r
from src.services.doc_tai_lieu import co_ocr

_CO_CONG_CU = all(shutil.which(x) for x in ("soffice", "pdftoppm", "pdftotext"))
_CAN_CONG_CU = pytest.mark.skipif(not _CO_CONG_CU, reason="cần LibreOffice + poppler")
_TEN, _SO, _NGAY, _CTY = r.GIA_TRI


def _o(don_vi: int, so: int = 0, kieu: str = "cham") -> dict:
    return {"don_vi": don_vi, "so": so, "kieu": kieu, "nhan": "Họ tên:", "gia_tri": None}


def _trang(n: int = 1, cao: int = 20, rong: int = 20) -> list[np.ndarray]:
    return [np.full((cao, rong), 255, np.uint8) for _ in range(n)]


# ─────────────────────────────────────────────────────────── phép điền


def test_phep_dien_xoay_vong_bon_gia_tri_va_o_tab_them_mot_dau_cach():
    phep = r.phep_dien([_o(1), _o(1, 1), _o(2, 0, "tab"), _o(3), _o(4)])
    assert phep[0] == {"loai": "dien", "don_vi": 1, "cho_trong": 0, "gia_tri": _TEN}
    assert [p["gia_tri"] for p in phep] == [_TEN, _SO, f" {_NGAY}", _CTY, _TEN]
    assert [(p["don_vi"], p["cho_trong"]) for p in phep] == [(1, 0), (1, 1), (2, 0), (3, 0), (4, 0)]


def test_dem_ly_do_gom_theo_ma():
    bao_cao = {
        "da_ap": [0],
        "bo_qua": [{"phep": i, "ly_do": m} for i, m in enumerate(("khong_vua",) * 2 + ("xung_dot",))],
    }
    assert r.dem_ly_do(bao_cao) == {"khong_vua": 2, "xung_dot": 1}
    assert r.dem_ly_do({"da_ap": [], "bo_qua": []}) == {}


# ─────────────────────────────────────────────────────────── giá trị


def test_dem_gia_tri_bo_khoang_trang_tru_so_co_san_va_khong_dem_du():
    """Ô hẹp ngắt "01/10/2026" thành "01/ 10/ 202 6"; một giá trị đã có sẵn
    trong bản gốc không được tính là đã điền; tìm thấy thừa không bù chỗ thiếu."""
    assert r.dem_gia_tri([""], ["01/ 10/ 202 6"], [f" {_NGAY}"]) == (1, 1)
    assert r.dem_gia_tri(["Ngày 01/10/2026"], ["Ngày 01/10/2026"], [_NGAY]) == (0, 1)
    assert r.dem_gia_tri([""], [f"{_TEN} {_TEN} {_TEN}"], [_TEN, _SO]) == (1, 2)
    truoc, sau = ["Ngày 01/10/2026", ""], ["Ngày 01/10/2026 Tên: Nguyễn Văn Ánh", "01/10/2026"]
    assert r.dem_gia_tri(truoc, sau, [_TEN, _TEN, _NGAY]) == (2, 3)
    assert r.dem_gia_tri([], [], []) == (0, 0)


def test_dem_gia_tri_bo_cham_tach_gia_tri_bi_xen_cham_da_che():
    """Lớp phủ PDF che dãy chấm nhưng để nó trong lớp chữ: `pdftotext` xen chấm
    vào giữa giá trị. Số thường không thấy, số `bo_cham` thấy."""
    sau = ["Ngành: Công ty TNHH ……………... Luật Việt Khóa:"]
    assert r.dem_gia_tri([""], sau, [_CTY]) == (0, 1)
    assert r.dem_gia_tri([""], sau, [_CTY], bo_cham=True) == (1, 1)


# ─────────────────────────────────────────────────────────── điểm ảnh


def test_trang_giong_can_cung_so_trang_cung_kho_cung_diem_anh():
    a = _trang(2)
    assert r.trang_giong(a, [x.copy() for x in a])
    assert not r.trang_giong(a, a[:1])
    assert not r.trang_giong(a, [a[0], np.full((21, 20), 255, np.uint8)])
    b = [x.copy() for x in a]
    b[1][3, 3] = 0
    assert not r.trang_giong(a, b)


def test_trang_khong_dien_bat_trang_doi_ma_khong_mang_gia_tri_nao():
    a = _trang(3)
    b = [x.copy() for x in a]
    b[0][1, 1] = 0  # trang 1 đổi và mang giá trị: đúng
    b[2][2, 2] = 0  # trang 3 đổi mà không có giá trị nào: vi phạm
    chu = ["Tên: Nguyễn Văn Ánh", "Ghi chú", "Hết"]
    assert r.trang_khong_dien(a, b, chu, [_TEN]) == {"trang": 2, "giong": 1, "doi_khong_gia_tri": [3]}
    # Đổi số trang thì so từng trang không còn nghĩa: không chấm, không đoán.
    assert r.trang_khong_dien(a, b[:2], chu[:2], [_TEN]) is None


def test_ti_le_giong_can_kho_bang_nen_trang():
    a, b = np.full((10, 10), 255, np.uint8), np.full((12, 10), 255, np.uint8)
    assert r.ti_le_giong(a, b) == 1.0
    b[0, :] = 0
    assert r.ti_le_giong(a, b) == pytest.approx(110 / 120)


def test_iou_muc_chi_tren_diem_anh_co_muc():
    a, b = np.full((10, 10), 255, np.uint8), np.full((10, 10), 255, np.uint8)
    assert r.iou_muc(a, b) is None
    a[0, 0:4] = 0
    b[0, 2:6] = 0
    assert r.iou_muc(a, b) == pytest.approx(2 / 6)
    b[0, 2:6] = 200  # xám nhạt dưới ngưỡng mực không phải mực
    assert r.iou_muc(a, b) == 0.0


def test_doi_ngoai_hop_dem_diem_anh_doi_ngoai_hop_gian_1pt():
    (a,) = _trang(1, 50, 50)
    b = a.copy()
    b[10:15, 10:30] = 0
    hop = [[10.0, 10.0, 30.0, 15.0]]
    assert r.doi_ngoai_hop(a, b, hop) == (100, 0)
    b[15, 30] = 0  # sát mép hộp, trong 1 pt cho phép
    assert r.doi_ngoai_hop(a, b, hop) == (101, 0)
    b[17, 30] = 0  # quá 1 pt
    b[40, 40] = 0
    assert r.doi_ngoai_hop(a, b, hop) == (103, 2)
    assert r.doi_ngoai_hop(a, b, []) == (103, 103)


def test_muc_zip_doi_bat_muc_doi_them_mat_ngoai_part_da_sua():
    """Kiểm bộ đóng gói: ngoài part bộ áp sửa, mọi mục zip phải giữ NGUYÊN nội
    dung giải nén — khứ hồi rỗng không chạm tới `_dong_goi`, phép này thì có."""

    def _zip(muc: dict[str, bytes]) -> bytes:
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for ten, v in muc.items():
                z.writestr(ten, v)
        return buf.getvalue()

    goc = _zip({"a.xml": b"a", "b.xml": b"b", "c.xml": b"c"})
    assert r.muc_zip_doi(goc, _zip({"a.xml": b"A", "b.xml": b"b", "c.xml": b"c"}), {"a.xml"}) == []
    moi = _zip({"a.xml": b"A", "b.xml": b"B", "d.xml": b"d"})
    assert r.muc_zip_doi(goc, moi, {"a.xml"}) == ["b.xml", "c.xml", "d.xml"]


# ─────────────────────────────────────────────────────────── Word


def test_word_het_gio_applescript_chan_moi_luot_sau(tmp_path, monkeypatch):
    """`with timeout of 85 seconds` ném -1712 TRƯỚC trần 90 s của subprocess:
    Word đứng (hộp thoại) phải chặn các lượt sau, không chờ thêm 85 s mỗi lần."""
    goi: list[str] = []

    def _mo(vao, ra):
        goi.append(vao.name)
        return goi_tra.pop(0)

    monkeypatch.setattr(r, "mo_bang_word", _mo)
    goi_tra = ["Word chạy xong nhưng không có PDF", "execution error: AppleEvent timed out. (-1712)"]
    w = r._Word(tmp_path)
    assert w.pdf(b"x") == "lỗi: Word chạy xong nhưng không có PDF" and w.chan is None  # lỗi của riêng tệp
    assert w.pdf(b"x") == r.CHAN and "-1712" in w.chan
    assert w.pdf(b"x") == r.CHAN
    assert len(goi) == 2


# ─────────────────────────────────────────────────────────── tổng hợp


def _pdf(so_cho: int, so_cho_docx: int, da_ap: int, ngoai_hop: int = 0) -> dict:
    return {
        "so_cho": so_cho,
        "so_cho_docx": so_cho_docx,
        "da_ap": da_ap,
        "bo_qua": {},
        "diem_anh_ngoai_hop": ngoai_hop,
        "diem_anh_ngoai_dai_chu": 0,
        "gia_tri": [da_ap, da_ap],
        "gia_tri_bo_cham": [da_ap, da_ap],
    }


def _ket(tep: str, da_ap: int, word: int | str = 1, word_sau: int | str = 1, lo_sau: int = 1, pdf=None) -> dict:
    """Một dòng `chi_tiet` như `do_tep` ghi: tệp 1 trang, Word như đã cho."""
    d = {
        "so_cho": da_ap,
        "da_ap": da_ap,
        "bo_qua": {},
        "so_trang_truoc": 1,
        "so_trang_sau": lo_sau,
        "trang_khong_dien": {"trang": 1, "giong": 1, "doi_khong_gia_tri": []} if lo_sau == 1 else None,
        "gia_tri": [da_ap, da_ap],
        "muc_zip_doi": [],
        "word_mo": True if isinstance(word_sau, int) else word_sau,
        "so_trang_word_sau": word_sau,
    }
    c = {
        "tep": tep,
        "so_trang": {"lo": 1, "word": word},
        "khu_hoi": {"bytes_giong": True, "trang_giong": True},
        "dien": d,
        "pdf": {"so": pdf or _pdf(da_ap, da_ap, da_ap), "scan": "không có tesseract"},
        "o_bang": {"so_cho": 0},
    }
    if isinstance(word, int):
        c["lo_word"] = {"trung_so_trang": word == 1, "giong_diem_anh": [1.0], "iou_muc": [1.0]}
        if isinstance(word_sau, int):
            d["gia_tri_word"] = [da_ap, da_ap]
    return c


def test_tong_hop_khong_tinh_tep_khong_dien_gi_la_dat():
    """Tệp không điền được ô nào trả CHÍNH bytes vào: mọi phép "không đổi" đạt
    hiển nhiên. Nó được liệt kê, không được cộng vào mẫu số."""
    th = r.tong_hop(
        [
            _ket("rong.docx", 0, pdf=_pdf(0, 0, 0)),
            _ket("a.docx", 2, lo_sau=2, pdf=_pdf(3, 2, 2, ngoai_hop=5)),
            _ket("b.docx", 3, pdf=_pdf(1, 3, 1)),
        ]
    )
    assert th["khong_dien_gi"] == ["rong.docx"]
    dn = th["dien"]
    assert dn["so_trang_giu_lo"] == [1, 2]
    assert dn["so_trang_giu_word"] == [2, 2]
    assert dn["word_mo"] == [2, 2]
    assert dn["trang_khong_dien_giong"] == [1, 1]
    assert dn["zip_giu_muc_khac"] == [2, 2]
    p = th["pdf_so"]
    assert p["khong_dien_gi"] == ["rong.docx"]
    assert p["tep_khong_doi_ngoai_hop"] == [1, 2]
    assert p["tep_khong_doi_ngoai_dai_chu"] == [2, 2]
    # Tỉ lệ số ô 4/5 để tìm thừa ở a.docx che chỗ thiếu ở b.docx; trần khớp thì không.
    assert p["ti_le_so_voi_docx"] == 0.8
    assert p["cho_toi_da_khop"] == [3, 5]
    assert p["cho_thua"] == 1
    assert th["pdf_scan"] is None
    assert th["khu_hoi"]["kieu"] == "rong_la_dong_nhat"


def test_tong_hop_loi_word_la_truot_khong_roi_khoi_mau_so():
    """Word lỗi trên tệp GỐC là một lần trượt; chỉ `blocked` (không chạy) mới ra
    khỏi mẫu số. Hai chuỗi lỗi giống nhau không phải "cùng số trang"."""
    loi = "lỗi: Word chạy xong nhưng không có PDF"
    th = r.tong_hop([_ket("a.docx", 2), _ket("loi.docx", 2, loi, loi), _ket("chan.docx", 2, r.CHAN, r.CHAN)])
    assert th["so_trang_lo_bang_word"] == [1, 2]
    assert th["lo_word"]["trung_so_trang"] == [1, 2]
    assert th["word_loi"] == 1
    dn = th["dien"]
    assert dn["so_trang_giu_word"] == [1, 2]
    assert dn["gia_tri_word"] == [2, 4]
    assert dn["word_mo"] == [1, 2]


def test_tong_hop_o_bang_dem_RIENG_khong_cong_vao_so_cua_kieu_cu():
    """Chỗ `o` (ô rỗng của bảng, G5) đo riêng: số chấm/tab của thước giữ nguyên."""
    a = _ket("a.docx", 2)
    a["o_bang"] = {"so_cho": 3, "da_ap": 3, "bo_qua": {}, "so_trang_truoc": 1, "so_trang_sau": 1}
    a["o_bang"]["doc_lai_dung"] = [3, 3]
    th = r.tong_hop([a, _ket("b.docx", 2)])
    assert th["o_bang"] == {
        "so_cho_theo_tep": {"a.docx": 3, "b.docx": 0},
        "da_ap": [3, 3],
        "bo_qua": {},
        "so_trang_giu": [1, 1],
        "doc_lai_dung": [3, 3],
    }
    assert th["dien"]["so_cho"] == 4


# ─────────────────────────────────────────────────────────── lượt chạy


def test_tep_hong_khong_lam_mat_ca_luot(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "tu_choi_11_trang", lambda: {"so_trang_dem": 11})
    hong = tmp_path / "hong.docx"
    hong.write_bytes(b"khong phai zip")
    ket = r.chay([hong, hong], word=False)
    assert ket["commit_hash"]
    assert ket["word"] is False
    assert [c["tep"] for c in ket["chi_tiet"]] == ["hong.docx", "hong.docx"]
    assert all("error" in c for c in ket["chi_tiet"])
    assert ket["tong_hop"]["so_tep"] == 2 and ket["tong_hop"]["loi"] == 2
    assert ket["tu_choi_11_trang"] == {"so_trang_dem": 11}


@_CAN_CONG_CU
def test_11_trang_bi_tu_choi_boi_dem_trang_tai_len_khong_bi_cat():
    assert r.tu_choi_11_trang() == {
        "so_trang_dem": 11,
        "tu_choi": True,
        "ly_do": "vuot_tran_so_trang",
        "bien_10_trang_nhan": True,
    }


_CHAM = "." * 60
# Giãn sau đoạn: hai dòng đơn liền nhau có hộp poppler chạm nhau (83,20 / 83,23),
# ô tô trắng giãn 0,5 pt thì chồng lên nhau và bộ áp PDF bỏ dòng sau (`xung_dot`)
# — hành vi của bộ áp, thước báo nó trên biểu mẫu thật; ca này chốt cách chấm.
_GIAN = '<w:pPr><w:spacing w:after="240"/></w:pPr>'
_MAU = (
    f"<w:p>{_GIAN}<w:r><w:t>Họ và tên: {_CHAM}</w:t></w:r></w:p>"
    f"<w:p>{_GIAN}<w:r><w:t>Điện thoại: {_CHAM}</w:t></w:r></w:p>"
    '<w:p><w:r><w:br w:type="page"/><w:t>Ghi chú chung</w:t></w:r></w:p>'
)


@_CAN_CONG_CU
def test_mot_bieu_mau_hai_trang_do_du_cac_duong():
    """Hai chỗ trống ở trang 1, trang 2 không có chỗ nào: khứ hồi trùng từng
    điểm ảnh, điền đủ, trang 2 giữ nguyên, `pdftotext` thấy đủ giá trị, và
    đường PDF chỉ đổi điểm ảnh trong hộp tô trắng."""
    ket = r.do_tep("mau.docx", r.docx_mau(_MAU), word=None)
    assert ket["so_trang"] == {"lo": 2}
    assert ket["khu_hoi"] == {"bytes_giong": True, "trang_giong": True}
    d = ket["dien"]
    assert (d["so_cho"], d["da_ap"], d["bo_qua"]) == (2, 2, {})
    assert (d["so_trang_truoc"], d["so_trang_sau"]) == (2, 2)
    assert d["trang_khong_dien"] == {"trang": 1, "giong": 1, "doi_khong_gia_tri": []}
    assert d["gia_tri"] == [2, 2]
    assert d["muc_zip_doi"] == []
    assert ket["o_bang"] == {"so_cho": 0}
    p = ket["pdf"]["so"]
    assert (p["so_cho"], p["so_cho_docx"], p["da_ap"], p["bo_qua"]) == (2, 2, 2, {})
    assert p["so_trang_giu"] and p["diem_anh_doi"] > 0
    assert p["diem_anh_ngoai_hop"] == p["diem_anh_ngoai_dai_chu"] == 0
    assert p["gia_tri"] == p["gia_tri_bo_cham"] == [2, 2]
    if co_ocr():
        s = ket["pdf"]["scan"]
        assert "error" not in s and s["so_trang_giu"], s
        assert s["gia_tri"][0] == s["gia_tri"][1] == s["da_ap"]
