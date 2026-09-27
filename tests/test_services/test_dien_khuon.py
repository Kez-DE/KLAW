"""Bộ áp phép sửa DOCX (P3a) — kế hoạch `docs/plans/active/khuon-goc-dien-tai-cho.md`,
hợp đồng "Edit operations".

`ap_dung_docx(docx, don_vi, phep_sua)` là hàm thuần: `don_vi` là ĐÚNG mảng dict
`tai_lieu` đọc lại từ `viec_doc_tai_lieu.don_vi` (ở đây dựng bằng chính bộ đọc +
`_hang_don_vi` + một vòng JSON), mỗi phiên bản áp lên khuôn gốc NGUYÊN với cả
danh sách phép của phiên bản đó. Phép không hợp lệ bị bỏ và báo, không đoán.
"""

import json
import re
import shutil
import time
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from lxml import etree

from src.services.dien_khuon import O_URI, _dong_goi, _xml, ap_dung_docx, danh_dau_docx
from src.services.doc_tai_lieu import KhongDocDuoc, doc
from src.services.tai_lieu import _hang_don_vi

_NSW = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NSMC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_W = f"{{{_NSW}}}"
_KHAI_NS = (
    f'xmlns:w="{_NSW}" xmlns:mc="{_NSMC}" xmlns:wps="urn:wps" xmlns:v="urn:v" xmlns:w14="urn:w14" mc:Ignorable="w14"'
)
_KHAI_XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
_DOC = _KHAI_XML + f"<w:document {_KHAI_NS}><w:body>{{than}}<w:sectPr/></w:body></w:document>"
_PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4


def _docx(than: str, phan: dict[str, str] | None = None) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", _DOC.format(than=than))
        for ten, xml in (phan or {}).items():
            z.writestr(ten, xml)
        z.writestr("word/media/image1.png", _PNG, compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


def _hdr(noi: str) -> str:
    return _KHAI_XML + f"<w:hdr {_KHAI_NS}>{noi}</w:hdr>"


def _r(chu: str, rpr: str = "") -> str:
    return f'<w:r>{rpr}<w:t xml:space="preserve">{chu}</w:t></w:r>'


def _p(*run: str, ppr: str = "") -> str:
    return f"<w:p>{ppr}{''.join(run)}</w:p>"


def _o(*doan: str, tcpr: str = '<w:tcPr><w:tcW w:w="3000"/></w:tcPr>') -> str:
    return f"<w:tbl><w:tblPr/><w:tr><w:tc>{tcpr}{''.join(doan)}</w:tc></w:tr></w:tbl>"


_TAB = "<w:r><w:tab/></w:r>"
_MOC_CHAM = '<w:pPr><w:tabs><w:tab w:val="right" w:pos="9000" w:leader="dot"/></w:tabs></w:pPr>'
_B, _I, _U = "<w:rPr><w:b/></w:rPr>", "<w:rPr><w:i/></w:rPr>", '<w:rPr><w:u w:val="single"/></w:rPr>'
_GIUA = '<w:pPr><w:jc w:val="center"/></w:pPr>'
_TEN, _SDT, _NGAY = "Nguyễn Văn Ánh", "0912 345 678", "01/10/2026"


def _hop_chu(chu: str) -> str:
    return (
        "<w:r><mc:AlternateContent>"
        f'<mc:Choice Requires="wps"><w:drawing><wps:txbx><w:txbxContent>{_p(_r(chu))}'
        "</w:txbxContent></wps:txbx></w:drawing></mc:Choice>"
        f"<mc:Fallback><w:pict><v:textbox><w:txbxContent>{_p(_r(chu))}"
        "</w:txbxContent></v:textbox></w:pict></mc:Fallback>"
        "</mc:AlternateContent></w:r>"
    )


def _hang(du_lieu: bytes) -> list[dict]:
    """Đúng mảng `luu_don_vi` ghi và `don_vi_cua` đọc lại (jsonb → list[dict])."""
    return json.loads(json.dumps([_hang_don_vi(d) for d in doc("x.docx", du_lieu).don_vi], ensure_ascii=False))


def _ap(than: str, phep: list, phan: dict[str, str] | None = None, hang=None) -> tuple[bytes, bytes, dict]:
    vao = _docx(than, phan)
    ra, bao_cao = ap_dung_docx(vao, _hang(vao) if hang is None else hang, phep)
    return vao, ra, bao_cao


def _goc(du_lieu: bytes, ten: str = "word/document.xml"):
    return etree.fromstring(zipfile.ZipFile(BytesIO(du_lieu)).read(ten))


def _than(du_lieu: bytes) -> list:
    return [c for c in _goc(du_lieu).find(f"{_W}body") if c.tag != f"{_W}sectPr"]


def _chu(nut) -> str:
    return "".join(t.text or "" for t in nut.iter(f"{_W}t"))


def _run(p) -> list[tuple[str, str]]:
    """(tên thẻ đầu tiên trong `w:rPr` hoặc "", chữ) của từng `w:r` trong `p`."""
    ra = []
    for r in p.iter(f"{_W}r"):
        rpr = r.find(f"{_W}rPr")
        ten = etree.QName(rpr[0]).localname if rpr is not None and len(rpr) else ""
        ra.append((ten, _chu(r)))
    return ra


def _noi_dung(du_lieu: bytes) -> list[str]:
    return [d.noi_dung for d in doc("x.docx", du_lieu).don_vi]


def _dien(don_vi: int, cho: int, gia_tri: str) -> dict:
    return {"loai": "dien", "don_vi": don_vi, "cho_trong": cho, "gia_tri": gia_tri}


# ───────────────────────────────────────────────────────── không phép nào


def test_danh_sach_rong_hoac_moi_phep_bi_bo_tra_ve_CHINH_bytes_vao():
    vao = _docx(_p(_r("Họ tên: ……")))
    ra, bc = ap_dung_docx(vao, _hang(vao), [])
    assert ra == vao and bc == {"da_ap": [], "bo_qua": []}
    ra, bc = ap_dung_docx(vao, _hang(vao), [{"loai": "doi_mau", "don_vi": 0}])
    assert ra == vao and bc == {"da_ap": [], "bo_qua": [{"phep": 0, "ly_do": "loai_khong_ho_tro"}]}


# ─────────────────────────────────────────────────────────────────── dien


def test_dien_trong_mot_run_giu_rPr_cua_run_do():
    _, ra, bc = _ap(_p(_r("Họ tên: ……", _B)), [_dien(0, 0, _TEN)])
    assert bc == {"da_ap": [0], "bo_qua": []}
    assert _run(_than(ra)[0]) == [("b", f"Họ tên: {_TEN}")]
    assert _noi_dung(ra) == [f"Họ tên: {_TEN}"]


def test_dien_vat_qua_nhieu_run_gia_tri_o_run_DAU_run_rong_bi_bo_run_con_chu_giu_lai():
    than = _p(
        *(f"<w:r>{rpr}<w:t>{chu}</w:t></w:r>" for chu, rpr in (("Địa chỉ: ……", _I), ("…", _B), ("….. còn lại", _U)))
    )
    _, ra, _ = _ap(than, [_dien(0, 0, _TEN)])
    p = _than(ra)[0]
    assert _run(p) == [("i", f"Địa chỉ: {_TEN}"), ("u", " còn lại")]
    assert [t.get("{http://www.w3.org/XML/1998/namespace}space") for t in p.iter(f"{_W}t")] == [None, "preserve"]


def test_hai_cho_trong_CUNG_mot_w_t_dien_tu_phai_sang_trai():
    than = _p(_r("Điện thoại: ………. Fax: …………"))
    _, ra, _ = _ap(than, [_dien(0, 0, _SDT), _dien(0, 1, _NGAY)])
    assert _noi_dung(ra) == [f"Điện thoại: {_SDT} Fax: {_NGAY}"]
    _, ra, _ = _ap(than, [_dien(0, 1, _NGAY)])
    assert _noi_dung(ra) == [f"Điện thoại: ………. Fax: {_NGAY}"]


def test_tab_dan_cham_gia_tri_dung_TRUOC_w_tab_voi_rPr_cua_run_giu_tab():
    than = _p(_r("Company name:"), f"<w:r>{_I}<w:tab/></w:r>", _r(" "), ppr=_MOC_CHAM)
    _, ra, bc = _ap(than, [_dien(0, 0, _TEN)])
    assert bc["da_ap"] == [0]
    p = _than(ra)[0]
    r = p.findall(f"{_W}r")
    assert [etree.QName(c).localname for c in r[1] if c.tag != f"{_W}rPr"] == ["t", "tab"]
    assert _run(p) == [("", "Company name:"), ("i", _TEN), ("", " ")]


def test_tab_va_cham_CUNG_offset_dien_ca_hai_dung_cho():
    _, ra, bc = _ap(_p(_r("Tên:"), _TAB, _r("……"), ppr=_MOC_CHAM), [_dien(0, 1, _NGAY), _dien(0, 0, _TEN)])
    assert bc["da_ap"] == [0, 1]
    p = _than(ra)[0]
    assert [e.text if e.tag == f"{_W}t" else "TAB" for r in p.iter(f"{_W}r") for e in r.iter(f"{_W}t", f"{_W}tab")] == [
        "Tên:",
        _TEN,
        "TAB",
        _NGAY,
    ]


def test_o_bang_dien_doan_thu_hai_doan_dau_giu_nguyen():
    _, ra, _ = _ap(_o(_p(_r("Họ: ……")), _p(_r("Tên: ……"))), [_dien(0, 1, _TEN)])
    tc = next(_goc(ra).iter(f"{_W}tc"))
    assert [_chu(p) for p in tc.iter(f"{_W}p")] == ["Họ: ……", f"Tên: {_TEN}"]


def test_dau_trang_CHI_ghi_lai_part_dau_trang_moi_muc_khac_giu_nguyen_bytes():
    phan = {"word/header1.xml": _hdr(_p(_r("Mẫu số: ……")))}
    vao, ra, bc = _ap(_p(_r("Thân")), [_dien(1, 0, "05")], phan)
    assert bc["da_ap"] == [0]
    a, b = zipfile.ZipFile(BytesIO(vao)), zipfile.ZipFile(BytesIO(ra))
    assert [m.filename for m in a.infolist()] == [m.filename for m in b.infolist()]
    assert [m.compress_type for m in a.infolist()] == [m.compress_type for m in b.infolist()]
    for m in a.infolist():
        if m.filename != "word/header1.xml":
            assert a.read(m.filename) == b.read(m.filename), m.filename
    assert _chu(_goc(ra, "word/header1.xml")) == "Mẫu số: 05"


def test_dien_NHIEU_cho_trong_mot_doan_trong_thoi_gian_tuyen_tinh():
    n = 5_000
    than = _p(*[f"<w:r><w:t>a{i}……</w:t></w:r>" for i in range(n)])
    vao = _docx(than)
    hang = _hang(vao)
    t = time.perf_counter()
    ra, bc = ap_dung_docx(vao, hang, [_dien(0, i, "x") for i in range(n)])
    assert time.perf_counter() - t < 3
    assert len(bc["da_ap"]) == n and "…" not in _chu(_than(ra)[0])


# ───────────────────────────────────────────────────── thay / chen_sau / xoa


def test_thay_doan_giu_pPr_rPr_run_dau_va_moi_dong_la_mot_doan_moi():
    than = _p('<w:bookmarkStart w:id="0" w:name="a"/>', _r("Tiêu đề cũ", _B), _r(" phần hai", _I), ppr=_GIUA)
    _, ra, bc = _ap(than + _p(_r("Sau")), [{"loai": "thay", "don_vi": 0, "noi_dung": "Dòng một\nDòng hai"}])
    assert bc["da_ap"] == [0]
    p0, p1, p2 = _than(ra)
    for p in (p0, p1):
        assert p.find(f"{_W}pPr/{_W}jc").get(f"{_W}val") == "center"
    assert p0.find(f"{_W}bookmarkStart") is not None
    assert _run(p0) == [("b", "Dòng một")] and _run(p1) == [("b", "Dòng hai")]
    assert _noi_dung(ra) == ["Dòng một", "Dòng hai", "Sau"]


def test_thay_o_bang_o_chi_con_cac_doan_moi_va_giu_tcPr():
    than = _o(_p(_r("A", _B), ppr=_GIUA), _p(_r("B")))
    _, ra, _ = _ap(than, [{"loai": "thay", "don_vi": 0, "noi_dung": "X\nY"}])
    tc = next(_goc(ra).iter(f"{_W}tc"))
    assert [etree.QName(c).localname for c in tc] == ["tcPr", "p", "p"]
    assert tc.find(f"{_W}tcPr/{_W}tcW").get(f"{_W}w") == "3000"
    assert [(_run(p), p.find(f"{_W}pPr/{_W}jc") is not None) for p in tc.iter(f"{_W}p")] == [
        ([("b", "X")], True),
        ([("b", "Y")], True),
    ]


def test_thay_doan_mang_ngat_phan_doan_chuyen_sectPr_xuong_doan_CUOI():
    sect = '<w:pPr><w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:pPr>'
    _, ra, _ = _ap(
        _p(_r("Hết phần một"), ppr=sect) + _p(_r("Phần hai")), [{"loai": "thay", "don_vi": 0, "noi_dung": "A\nB"}]
    )
    p0, p1, _p2 = _than(ra)
    assert p0.find(f"{_W}pPr/{_W}sectPr") is None
    assert p1.find(f"{_W}pPr/{_W}sectPr/{_W}pgSz") is not None


def test_chen_sau_doan_than_bai_theo_thu_tu_phep_va_chep_pPr_rPr():
    than = _p(_r("Mở đầu", _I), ppr=_GIUA) + _p(_r("Cuối"))
    phep = [{"loai": "chen_sau", "don_vi": 0, "noi_dung": "Một"}, {"loai": "chen_sau", "don_vi": 0, "noi_dung": "Hai"}]
    _, ra, bc = _ap(than, phep)
    assert bc["da_ap"] == [0, 1]
    assert [_run(p) for p in _than(ra)] == [[("i", "Mở đầu")], [("i", "Một")], [("i", "Hai")], [("", "Cuối")]]
    assert _than(ra)[1].find(f"{_W}pPr/{_W}jc") is not None


def test_chen_sau_o_bang_them_vao_CUOI_o():
    _, ra, _ = _ap(_o(_p(_r("Dòng 1"))), [{"loai": "chen_sau", "don_vi": 0, "noi_dung": "Dòng 2"}])
    tc = next(_goc(ra).iter(f"{_W}tc"))
    assert [_chu(p) for p in tc.iter(f"{_W}p")] == ["Dòng 1", "Dòng 2"]


@pytest.mark.parametrize("loai", ["thay", "chen_sau"])
def test_o_co_doan_DAU_rong_mau_lay_tu_run_mang_chu_dau_tien_cua_o(loai):
    # BM.M05 ô "Ghi chú": đoạn đầu rỗng, chữ đậm TNR ở đoạn hai.
    _, ra, bc = _ap(_o(_p(), _p(_r("Ghi chú", _B), ppr=_GIUA)), [{"loai": loai, "don_vi": 0, "noi_dung": "X\nY"}])
    assert bc["da_ap"] == [0]
    moi = list(next(_goc(ra).iter(f"{_W}tc")).iter(f"{_W}p"))[-2:]
    assert [(_run(p), p.find(f"{_W}pPr/{_W}jc") is not None) for p in moi] == [
        ([("b", "X")], True),
        ([("b", "Y")], True),
    ]


def test_o_KHONG_co_chu_mau_lay_tu_dinh_dang_dau_doan():
    _, ra, bc = _ap(
        _o('<w:p><w:pPr><w:jc w:val="center"/><w:rPr><w:b/></w:rPr></w:pPr></w:p>'),
        [{"loai": "thay", "don_vi": 0, "noi_dung": _TEN}],
    )
    assert bc["da_ap"] == [0]
    assert _run(next(_goc(ra).iter(f"{_W}p"))) == [("b", _TEN)]


def test_xoa_doan_than_bai():
    _, ra, bc = _ap(_p(_r("Bỏ đi")) + _p(_r("Giữ")), [{"loai": "xoa", "don_vi": 0}])
    assert bc["da_ap"] == [0] and _noi_dung(ra) == ["Giữ"]


@pytest.mark.parametrize("noi_dung", [None, 5, "", ["x"]])
def test_xoa_bo_qua_noi_dung_du_mang_hinh_dang_gi(noi_dung):
    # Một phép `xoa` mang `noi_dung: null` (model_dump không exclude_none) không
    # được làm nổ cả phiên bản: phiên bản nào cũng áp lại TRỌN danh sách phép.
    _, ra, bc = _ap(_p(_r("Bỏ đi")) + _p(_r("Giữ")), [{"loai": "xoa", "don_vi": 0, "noi_dung": noi_dung}])
    assert bc == {"da_ap": [0], "bo_qua": []} and _noi_dung(ra) == ["Giữ"]


def test_xoa_o_bang_giu_MOT_w_p_rong_va_tcPr():
    _, ra, _ = _ap(_o(_p(_r("A"), ppr=_GIUA), _p(_r("B"))), [{"loai": "xoa", "don_vi": 0}])
    tc = next(_goc(ra).iter(f"{_W}tc"))
    assert [etree.QName(c).localname for c in tc] == ["tcPr", "p"]
    assert _chu(tc) == "" and tc.find(f"{_W}p/{_W}pPr/{_W}jc") is not None


def test_xoa_doan_DUY_NHAT_cua_o_dau_trang_de_lai_mot_w_p_rong():
    hdr = _hdr(f"<w:tbl><w:tr><w:tc>{_p(_r('Số hiệu: ……'))}</w:tc></w:tr></w:tbl>")
    _, ra, bc = _ap(_p(_r("Thân")), [{"loai": "xoa", "don_vi": 1}], {"word/header1.xml": hdr})
    assert bc["da_ap"] == [0]
    tc = next(_goc(ra, "word/header1.xml").iter(f"{_W}tc"))
    assert [etree.QName(c).localname for c in tc] == ["p"] and _chu(tc) == ""


# ──────────────────────────────────────────────────────────────── xung đột


def test_thay_hoac_xoa_THANG_dien_tren_cung_don_vi():
    than = _p(_r("Họ tên: ……"))
    _, ra, bc = _ap(than, [_dien(0, 0, _TEN), {"loai": "thay", "don_vi": 0, "noi_dung": "Mới"}])
    assert bc == {"da_ap": [1], "bo_qua": [{"phep": 0, "ly_do": "xung_dot"}]}
    assert _noi_dung(ra) == ["Mới"]


def test_hai_phep_cau_truc_cung_don_vi_phep_SAU_xung_dot_dien_trung_cho_cung_vay():
    than = _p(_r("Họ tên: ……")) + _p(_r("Ngày ……"))
    phep = [
        {"loai": "xoa", "don_vi": 0},
        {"loai": "thay", "don_vi": 0, "noi_dung": "X"},
        _dien(1, 0, _NGAY),
        _dien(1, 0, "02/10/2026"),
    ]
    _, ra, bc = _ap(than, phep)
    assert bc == {"da_ap": [0, 2], "bo_qua": [{"phep": 1, "ly_do": "xung_dot"}, {"phep": 3, "ly_do": "xung_dot"}]}
    assert _noi_dung(ra) == [f"Ngày {_NGAY}"]


def test_chen_sau_roi_xoa_cung_doan_doan_moi_dung_dung_cho_doan_cu():
    phep = [{"loai": "chen_sau", "don_vi": 0, "noi_dung": "Thế chỗ"}, {"loai": "xoa", "don_vi": 0}]
    _, ra, bc = _ap(_p(_r("Cũ")) + _p(_r("Sau")), phep)
    assert bc["da_ap"] == [0, 1] and _noi_dung(ra) == ["Thế chỗ", "Sau"]


# ─────────────────────────────────────────────── phép hỏng, địa chỉ hỏng


@pytest.mark.parametrize(
    ("phep", "ly_do"),
    [
        ("x", "khong_hop_le"),
        ({"loai": "doi_mau", "don_vi": 0}, "loai_khong_ho_tro"),
        ({"don_vi": 0}, "loai_khong_ho_tro"),
        (_dien(99, 0, "A"), "khong_co_don_vi"),
        (_dien(True, 0, "A"), "khong_hop_le"),
        (_dien(0, 5, "A"), "khong_co_cho_trong"),
        (_dien(0, -1, "A"), "khong_hop_le"),
        (_dien(0, 0, ""), "khong_hop_le"),
        (_dien(0, 0, "  "), "khong_hop_le"),
        (_dien(0, 0, "a\nb"), "khong_hop_le"),
        (_dien(0, 0, "a\x00b"), "khong_hop_le"),
        ({"loai": "dien", "don_vi": 0, "cho_trong": 0, "gia_tri": 5}, "khong_hop_le"),
        ({"loai": "thay", "don_vi": 0, "noi_dung": " \n "}, "khong_hop_le"),
        ({"loai": "thay", "don_vi": 0, "noi_dung": "a\tb"}, "khong_hop_le"),
        ({"loai": "chen_sau", "don_vi": 0}, "khong_hop_le"),
    ],
)
def test_phep_sai_hinh_dang_bi_bo_va_bao_dung_ly_do(phep, ly_do):
    vao, ra, bc = _ap(_p(_r("Họ tên: ……")), [phep])
    assert bc == {"da_ap": [], "bo_qua": [{"phep": 0, "ly_do": ly_do}]}
    assert ra == vao


def _sua(hang: list[dict], **khoa) -> list[dict]:
    return [{**hang[0], **khoa}, *hang[1:]]


@pytest.mark.parametrize("loai", ["dien", "thay", "chen_sau", "xoa"])
@pytest.mark.parametrize(
    "dia_chi",
    [
        None,
        {"phan": "word/document.xml", "chi_muc": [99]},
        {"phan": "word/header9.xml", "chi_muc": [0]},
        {"phan": "word/media/image1.png", "chi_muc": [0]},
        {"phan": "[Content_Types].xml", "chi_muc": [0]},
        {"phan": "word/document.xml", "chi_muc": [1]},
        {"phan": "word/document.xml", "chi_muc": [1, 1, 0]},
    ],
    ids=["vang", "ngoai_tam", "part_vang", "part_nhi_phan", "part_khac", "tro_vao_bang", "tro_vao_o_ma_don_vi_la_doan"],
)
def test_dia_chi_hong_bi_bo_voi_moi_loai_phep(loai, dia_chi):
    than = _p(_r("Họ tên: ……")) + _o(_p(_r("Ô")))
    vao = _docx(than)
    hang = _hang(vao)
    hang = _sua(hang, dia_chi=dia_chi) if dia_chi else [{k: v for k, v in hang[0].items() if k != "dia_chi"}, *hang[1:]]
    phep = {"dien": _dien(0, 0, "A"), "thay": {"loai": "thay", "don_vi": 0, "noi_dung": "A"}}.get(
        loai, {"loai": loai, "don_vi": 0, "noi_dung": "A"}
    )
    ra, bc = ap_dung_docx(vao, hang, [phep])
    assert bc == {"da_ap": [], "bo_qua": [{"phep": 0, "ly_do": "khong_co_dia_chi"}]} and ra == vao


@pytest.mark.parametrize(
    "cho",
    [
        {"so": 0, "kieu": "cham", "doan": 0, "dau": 0, "cuoi": 3, "nhan": ""},
        {"so": 0, "kieu": "cham", "doan": 0, "dau": 8, "cuoi": 30, "nhan": ""},
        {"so": 0, "kieu": "cham", "doan": 7, "dau": 8, "cuoi": 10, "nhan": ""},
        {"so": 0, "kieu": "tab", "doan": 0, "dau": 3, "cuoi": 3, "nhan": ""},
    ],
    ids=["nhan_chu", "qua_cuoi_doan", "doan_vang", "tab_khong_co_w_tab"],
)
def test_cho_trong_KHONG_con_la_day_cham_thi_bo_qua_cho_trong_da_doi(cho):
    vao = _docx(_p(_r("Họ tên: ……")))
    ra, bc = ap_dung_docx(vao, _sua(_hang(vao), cho_trong=[cho]), [_dien(0, 0, "A")])
    assert bc == {"da_ap": [], "bo_qua": [{"phep": 0, "ly_do": "cho_trong_da_doi"}]} and ra == vao


def test_cho_trong_luu_TRUOC_ban_va_vat_qua_tab_thi_bo_qua():
    """Dòng lưu trước bản vá cắt-tại-ngắt có thể mang một chỗ vắt qua `w:tab`;
    điền nó là xoá chấm hai bên tab — kiểm lại trên cây thô, bỏ qua."""
    vao = _docx(_p(_r("Tên: ……"), _TAB, _r("……")))
    cu = {"so": 0, "kieu": "cham", "doan": 0, "dau": 5, "cuoi": 9, "nhan": "Tên:"}
    ra, bc = ap_dung_docx(vao, _sua(_hang(vao), cho_trong=[cu]), [_dien(0, 0, "A")])
    assert bc["bo_qua"] == [{"phep": 0, "ly_do": "cho_trong_da_doi"}] and ra == vao


def test_cho_trong_dang_PDF_tren_don_vi_docx_la_khong_co_cho_trong():
    vao = _docx(_p(_r("Họ tên: ……")))
    pdf = {"so": 0, "kieu": "cham", "hop": [1, 2, 3, 4], "co_chu": 10, "nhan": ""}
    _, bc = ap_dung_docx(vao, _sua(_hang(vao), cho_trong=[pdf]), [_dien(0, 0, "A")])
    assert bc["bo_qua"] == [{"phep": 0, "ly_do": "khong_co_cho_trong"}]


def test_khong_phai_zip_la_KhongDocDuoc_tep_hong():
    with pytest.raises(KhongDocDuoc) as e:
        ap_dung_docx(b"khong phai zip", [], [{"loai": "xoa", "don_vi": 0}])
    assert e.value.ly_do == "tep_hong"


# ─────────────────────────────────────────────────────────── fail closed


@pytest.mark.parametrize("loai", ["thay", "chen_sau", "xoa"])
def test_don_vi_chua_HOP_CHU_tu_choi_moi_phep_cau_truc(loai):
    vao, ra, bc = _ap(_p(_r("Phụ lục 4"), _hop_chu("Điền: ……")), [{"loai": loai, "don_vi": 0, "noi_dung": "A"}])
    assert bc["bo_qua"] == [{"phep": 0, "ly_do": "khong_an_toan"}] and ra == vao


def test_doan_trong_hop_chu_KHONG_dien_duoc_du_dong_luu_noi_co_cho_trong():
    than = _o(_p(_r("Tiêu đề"), _hop_chu("Hộp: ……")), _p(_r("Số: ………")))
    vao = _docx(than)
    hang = _hang(vao)
    gia = {"so": 1, "kieu": "cham", "doan": 1, "dau": 5, "cuoi": 7, "nhan": "Hộp:"}
    hang = _sua(hang, cho_trong=[*hang[0]["cho_trong"], gia])
    ra, bc = ap_dung_docx(vao, hang, [_dien(0, 1, "A"), _dien(0, 0, "7")])
    assert bc == {"da_ap": [1], "bo_qua": [{"phep": 0, "ly_do": "khong_an_toan"}]}
    assert "Số: 7" in _chu(_goc(ra))


@pytest.mark.parametrize("loai", ["thay", "xoa"])
def test_doan_co_HINH_thay_xoa_bi_tu_choi_nhung_dien_va_chen_sau_thi_duoc(loai):
    than = _p(_r("Ký tên: ……"), "<w:r><w:drawing/></w:r>")
    vao, ra, bc = _ap(than, [{"loai": loai, "don_vi": 0, "noi_dung": "A"}])
    assert bc["bo_qua"] == [{"phep": 0, "ly_do": "khong_an_toan"}] and ra == vao
    _, ra, bc = _ap(than, [_dien(0, 0, _TEN), {"loai": "chen_sau", "don_vi": 0, "noi_dung": "B"}])
    assert bc["da_ap"] == [0, 1] and next(_goc(ra).iter(f"{_W}drawing"), None) is not None


def test_xoa_doan_mang_NGAT_PHAN_DOAN_bi_tu_choi():
    sect = '<w:pPr><w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:pPr>'
    _, _, bc = _ap(_p(_r("Hết phần một"), ppr=sect) + _p(_r("Hai")), [{"loai": "xoa", "don_vi": 0}])
    assert bc["bo_qua"] == [{"phep": 0, "ly_do": "khong_an_toan"}]


# ─────────────────────────────────────────────────────────────── ghi lại


def test_giu_KHAI_BAO_XML_va_the_goc_NGUYEN_VAN_ke_ca_tien_to_mc_Ignorable():
    vao, ra, _ = _ap(_p(_r("Họ tên: ……")), [_dien(0, 0, _TEN)])
    a = zipfile.ZipFile(BytesIO(vao)).read("word/document.xml")
    b = zipfile.ZipFile(BytesIO(ra)).read("word/document.xml")
    assert b.startswith(_KHAI_XML.encode())
    goc = re.compile(rb"<w:document[^>]*>")
    assert goc.search(a)[0] == goc.search(b)[0]
    assert b'xmlns:w14="urn:w14"' in goc.search(b)[0]


def test_the_goc_XEN_KE_thuoc_tinh_va_xmlns_van_giu_nguyen_van():
    """lxml viết `xmlns:` trước thuộc tính; Word thì xen kẽ (đo trên BM.ĐT.18.11:
    `mc:Ignorable` nằm giữa các `xmlns:`). Thẻ gốc phải ra đúng từng byte."""
    the = f'<w:document xmlns:w="{_NSW}" mc:Ignorable="w14" xmlns:mc="{_NSMC}" xmlns:w14="urn:w14">'
    xml = _KHAI_XML + the + f"<w:body>{_p(_r('Họ tên: ……'))}</w:body></w:document>"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    vao = buf.getvalue()
    ra, _ = ap_dung_docx(vao, _hang(vao), [_dien(0, 0, _TEN)])
    assert zipfile.ZipFile(BytesIO(ra)).read("word/document.xml").startswith((_KHAI_XML + the).encode())


def test_phan_tu_moi_dung_tien_to_w_khong_khai_lai_namespace():
    than = _o(_p(_r("A", _B))) + _p(_r("Tên:"), _TAB, ppr=_MOC_CHAM)
    phep = [
        {"loai": "thay", "don_vi": 0, "noi_dung": "X\nY"},
        _dien(1, 0, _TEN),
        {"loai": "chen_sau", "don_vi": 1, "noi_dung": "Z"},
    ]
    _, ra, bc = _ap(than, phep)
    assert bc["da_ap"] == [0, 1, 2]
    xml = zipfile.ZipFile(BytesIO(ra)).read("word/document.xml")
    assert xml.count(b"xmlns:w=") == 1 and b"ns0" not in xml


# ─────────────────────────────────────────── bản dò vị trí ô (`danh_dau_docx`)
# `GET …/trang` cần biết mỗi ô nằm ở đâu trên trang đã dựng. Bản dò bọc đúng ký
# tự của từng chỗ trống trong một `w:hyperlink` trỏ tới `O_URI{don_vi}/{so}`;
# LibreOffice xuất mỗi liên kết thành một chú thích `/Link` có `/Rect`.

_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _lien_ket(du_lieu: bytes, phan: str = "word/document.xml") -> list[tuple[str, str]]:
    """(URI đích, chữ) của từng `w:hyperlink` của part, theo thứ tự tài liệu."""
    thu_muc, ten = phan.rsplit("/", 1)
    rels = etree.fromstring(zipfile.ZipFile(BytesIO(du_lieu)).read(f"{thu_muc}/_rels/{ten}.rels"))
    dich = {r.get("Id"): r.get("Target") for r in rels if r.get("TargetMode") == "External"}
    return [(dich.get(h.get(f"{{{_R_NS}}}id"), ""), _chu(h)) for h in _goc(du_lieu, phan).iter(f"{_W}hyperlink")]


_THAN_DO = (
    _p(_r("Họ tên: ……", _B), _r("…. Hết"))  # dãy chấm chung `w:t` với nhãn, vắt qua hai run
    + _p(_r("Số …./…."))  # hai chỗ trống trong MỘT `w:t`
    + _p(_r("Tên:"), "<w:r><w:tab/><w:t>x</w:t></w:r>", ppr=_MOC_CHAM)  # `w:tab` chung run với chữ
)
_O_DO = [(0, 0), (1, 0), (1, 1), (2, 0)]


def test_ban_do_BOC_dung_ky_tu_cua_tung_cho_trong_chu_va_dinh_dang_giu_nguyen():
    vao = _docx(_THAN_DO)
    ra = danh_dau_docx(vao, _hang(vao), _O_DO)
    assert _noi_dung(ra) == _noi_dung(vao)
    assert _lien_ket(ra) == [
        (f"{O_URI}0/0", "……"),
        (f"{O_URI}0/0", "…."),
        (f"{O_URI}1/0", "…."),
        (f"{O_URI}1/1", "…."),
        (f"{O_URI}2/0", ""),
    ]
    assert _run(_than(ra)[0]) == [("b", "Họ tên: "), ("b", "……"), ("", "…."), ("", " Hết")]
    tab = _than(ra)[2].find(f"{_W}hyperlink/{_W}r")
    assert [etree.QName(c).localname for c in tab] == ["tab"], "chỉ `w:tab`, chữ cùng run ở lại ngoài liên kết"


def test_bo_ap_tren_ban_do_ra_CUNG_chu_voi_ban_sach_va_gia_tri_nam_TRONG_lien_ket():
    """Trang dựng từ `ap(ban_do)`: bộ áp đi lại đúng chỗ trống trên bản dò (tách
    run không đổi chuỗi thô), và giá trị vào `w:t` đầu của chỗ trống — trong
    liên kết của nó."""
    vao = _docx(_THAN_DO)
    hang = _hang(vao)
    phep = [_dien(0, 0, _TEN), _dien(1, 1, "12"), _dien(2, 0, " a@b.vn")]
    sach, bc = ap_dung_docx(vao, hang, phep)
    do, bc_do = ap_dung_docx(danh_dau_docx(vao, hang, _O_DO), hang, phep)
    assert bc_do == bc == {"da_ap": [0, 1, 2], "bo_qua": []}
    assert _noi_dung(do) == _noi_dung(sach)
    assert [x for x in _lien_ket(do) if x[1]] == [
        (f"{O_URI}0/0", _TEN),
        (f"{O_URI}1/0", "…."),
        (f"{O_URI}1/1", "12"),
        (f"{O_URI}2/0", " a@b.vn"),
    ]


def test_cho_trong_dau_trang_co_rels_RIENG_cua_part_do():
    vao = _docx(_p(_r("Thân")), {"word/header1.xml": _hdr(_p(_r("Mã: ……")))})
    hang = _hang(vao)
    d = next(h for h in hang if h.get("dia_chi", {}).get("phan") == "word/header1.xml")
    ra = danh_dau_docx(vao, hang, [(d["chi_so"], 0)])
    assert _lien_ket(ra, "word/header1.xml") == [(f"{O_URI}{d['chi_so']}/0", "……")]
    assert "word/_rels/document.xml.rels" not in zipfile.ZipFile(BytesIO(ra)).namelist()


def test_ban_do_KHONG_moc_cho_bo_ap_khong_toi_va_khong_long_lien_ket():
    """Ô lạ, đơn vị lạ, hay chỗ trống đã nằm trong một liên kết của tài liệu
    (liên kết lồng nhau không hợp lệ): không mốc — ô đó "chưa định vị" — và
    không mốc nào thì trả CHÍNH bytes vào."""
    vao = _docx(_p(_r("Tên: ……")) + _p('<w:hyperlink w:anchor="a">' + _r("Mã: ……") + "</w:hyperlink>"))
    hang = _hang(vao)
    assert danh_dau_docx(vao, hang, []) == vao
    assert danh_dau_docx(vao, hang, [(0, 5), (9, 0), (1, 0)]) == vao
    assert _lien_ket(danh_dau_docx(vao, hang, [(0, 0), (1, 0)])) == [(f"{O_URI}0/0", "……"), ("", "Mã: ……")]


# ───────────────────────────────────────── tám biểu mẫu thật của chủ dự án
# Kho mẫu ngoài repo, không bao giờ commit; không có thì bỏ qua (CI). Dựng bằng
# LibreOffice + poppler, so ảnh xám 60 dpi từng trang.

_KHO_MAU = Path.home() / "giấy tờ thực tập"
_MAU = sorted(_KHO_MAU.glob("*.docx")) if _KHO_MAU.exists() else []
_THAT = pytest.mark.skipif(
    not (_MAU and all(shutil.which(x) for x in ("soffice", "pdftoppm", "pdftotext"))),
    reason="kho mẫu ngoài repo hoặc LibreOffice/poppler không có trên máy này",
)
_DAU_VA_GOC = re.compile(rb"\A[^>]*\?>\s*<[^>]*>")


def _giong(a, b) -> bool:
    return len(a) == len(b) and all(x.shape == y.shape and bool((x == y).all()) for x, y in zip(a, b, strict=True))


@_THAT
@pytest.mark.parametrize("tep", _MAU, ids=lambda p: p.stem[:24])
def test_tep_that_GHI_LAI_khong_sua_gi_dung_ra_trung_tung_diem_anh(tep):
    """(1) Danh sách rỗng trả chính bytes. Mạnh hơn: đi qua ĐÚNG đường ghi lại
    (lxml → `_xml` → `_dong_goi`) cho mọi part có đơn vị mà không sửa gì — khai
    báo XML và thẻ gốc giữ từng byte, bản dựng trùng tới từng điểm ảnh."""
    from scripts.kiem_mo_bang_word import anh_xam, dung_pdf, hang_don_vi

    du_lieu = tep.read_bytes()
    hang = hang_don_vi(tep.name, du_lieu)
    assert ap_dung_docx(du_lieu, hang, [])[0] == du_lieu
    z = zipfile.ZipFile(BytesIO(du_lieu))
    ghi = {
        p: _xml(etree.fromstring(z.read(p)), z.read(p)) for p in {h["dia_chi"]["phan"] for h in hang if "dia_chi" in h}
    }
    for ten, xml in ghi.items():
        assert _DAU_VA_GOC.match(xml)[0] == _DAU_VA_GOC.match(z.read(ten))[0], ten
    assert _giong(anh_xam(dung_pdf(du_lieu)), anh_xam(dung_pdf(_dong_goi(z, ghi))))


@_THAT
@pytest.mark.parametrize("tep", _MAU, ids=lambda p: p.stem[:24])
def test_tep_that_DIEN_MOI_cho_trong_co_du_gia_tri_va_trang_khong_dien_giu_nguyen(tep):
    """(2) Điền MỌI chỗ trống có địa chỉ: mọi phép áp được, dựng được, cùng số
    trang, `pdftotext` có đủ từng giá trị (so sau khi bỏ khoảng trắng — một ô
    hẹp ngắt "01/10/2026" thành "01/ 10/ 202 6"), trang nào đổi điểm ảnh thì
    trang ấy mang một giá trị, và đọc lại không còn chỗ trống chấm nào."""
    from scripts.kiem_mo_bang_word import GIA_TRI_MAU, anh_xam, chu_trang, dung_pdf, hang_don_vi, phep_dien_het

    du_lieu = tep.read_bytes()
    hang = hang_don_vi(tep.name, du_lieu)
    phep = phep_dien_het(hang)
    ra, bao_cao = ap_dung_docx(du_lieu, hang, phep)
    assert bao_cao == {"da_ap": list(range(len(phep))), "bo_qua": []}

    truoc, sau = dung_pdf(du_lieu), dung_pdf(ra)
    a, b = anh_xam(truoc), anh_xam(sau)
    assert len(a) == len(b)
    chu = ["".join(t.split()) for t in chu_trang(sau)]
    for v in GIA_TRI_MAU:
        assert sum(t.count("".join(v.split())) for t in chu) == sum(p["gia_tri"] == v for p in phep), v
    for i, (x, y) in enumerate(zip(a, b, strict=True)):
        if not _giong([x], [y]):
            assert any("".join(v.split()) in chu[i] for v in GIA_TRI_MAU), f"trang {i + 1} đổi mà không có giá trị nào"
    assert not any(c.kieu == "cham" for d in doc(tep.name, ra).don_vi for c in d.cho_trong)


def test_bo_ap_PDF_dung_CHUNG_tap_ma_ly_do_voi_DOCX():
    """Một tập mã đóng cho cả hai bộ áp: người gọi (P4) đọc `bo_qua` của bộ áp nào
    cũng bằng cùng một enum; chuỗi phát ra không đổi."""
    from src.services import dien_khuon, dien_khuon_pdf

    assert dien_khuon_pdf.LyDoBoQua is dien_khuon.LyDoBoQua
    assert {m.value for m in dien_khuon.LyDoBoQua} == {
        "khong_hop_le",
        "loai_khong_ho_tro",
        "khong_co_don_vi",
        "khong_co_dia_chi",
        "khong_co_cho_trong",
        "cho_trong_da_doi",
        "khong_an_toan",
        "xung_dot",
        "khong_vua",
        "khong_co_phong",
    }
