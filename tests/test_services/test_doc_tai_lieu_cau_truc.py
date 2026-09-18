"""Cấu trúc DOCX: bảng, đầu trang, chân trang — và cái phanh chống zip bom.

`test_doc_tai_lieu.py` đã khoá phần "đọc ra chữ". File này khoá phần "đọc ra
CHỖ", thứ quyết định một neo tài liệu chỉ được vào ô nào của bảng nào.

Ba điều ở đây không suy ra được từ file kia:

1. Duyệt phẳng mọi `w:p` cho ra ĐÚNG chữ nhưng MẤT toạ độ: ô "2,0" nằm ở hàng
   nào, cột nào, thuộc bảng thứ mấy. Với phiếu chấm điểm — bảng là toàn bộ nội
   dung — mất toạ độ nghĩa là người dùng bấm vào một neo và không biết nó chỉ
   vào đâu.
2. Đầu trang và chân trang là NGUỒN KHÁC: số hiệu biểu mẫu, tên đơn vị ban
   hành, số trang. Trộn chúng vào thân là nói dối về chỗ một câu được viết.
3. Duyệt theo cấu trúc BỎ SÓT những thứ duyệt phẳng thấy (`w:sdt`, hộp chữ).
   Nên nó không được phép thay thế duyệt phẳng một cách mù quáng: ít chữ hơn
   thì lùi về, chấp nhận mất toạ độ chứ không mất nội dung.
"""

import zipfile
from io import BytesIO

import pytest

from src.services.doc_tai_lieu import (
    TRAN_GIAI_NEN_BYTE,
    TRAN_SO_MUC_ZIP,
    KhongDocDuoc,
    LoaiHong,
    NguonChu,
    _dat_vi_tri,
    doc,
)

_NSW = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_DOC = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    f'<w:document xmlns:w="{_NSW}"><w:body>{{than}}</w:body></w:document>'
)
_HDR = f'<?xml version="1.0" encoding="UTF-8"?><w:hdr xmlns:w="{_NSW}">{{than}}</w:hdr>'
_FTR = f'<?xml version="1.0" encoding="UTF-8"?><w:ftr xmlns:w="{_NSW}">{{than}}</w:ftr>'


def _p(chu: str) -> str:
    return f"<w:p><w:r><w:t>{chu}</w:t></w:r></w:p>"


def _tc(*noi: str) -> str:
    return f"<w:tc>{''.join(noi)}</w:tc>"


def _tr(*o: str) -> str:
    return f"<w:tr>{''.join(o)}</w:tr>"


def _tbl(*hang: str) -> str:
    return f"<w:tbl>{''.join(hang)}</w:tbl>"


def _docx(than: str, phan: dict[str, str] | None = None) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", _DOC.format(than=than))
        for ten, xml in (phan or {}).items():
            z.writestr(ten, xml)
    return buf.getvalue()


# ------------------------------------------------------------------ bảng


def test_moi_o_bang_mang_TOA_DO_bang_hang_cot():
    than = _p("PHIẾU ĐÁNH GIÁ") + _tbl(
        _tr(_tc(_p("Tiêu chí")), _tc(_p("Điểm"))),
        _tr(_tc(_p("Chuyên cần")), _tc(_p("2,0"))),
    )
    t = doc("phieu.docx", _docx(than))

    assert [d.noi_dung for d in t.don_vi] == ["PHIẾU ĐÁNH GIÁ", "Tiêu chí", "Điểm", "Chuyên cần", "2,0"]
    assert [d.bang for d in t.don_vi] == [None, (0, 0, 0), (0, 0, 1), (0, 1, 0), (0, 1, 1)]
    assert {d.vung for d in t.don_vi} == {"than"}
    # `chi_so` tuần tự qua MỌI đơn vị — `neo_du_kien.xac_minh` không biết gì về bảng.
    assert [d.chi_so for d in t.don_vi] == [0, 1, 2, 3, 4]


def test_hai_bang_duoc_danh_so_RIENG():
    than = _tbl(_tr(_tc(_p("Bảng đầu")))) + _p("Giữa") + _tbl(_tr(_tc(_p("Bảng sau"))))
    t = doc("x.docx", _docx(than))
    assert [d.bang for d in t.don_vi] == [(0, 0, 0), None, (1, 0, 0)]


def test_nhieu_doan_trong_MOT_o_la_MOT_don_vi():
    """Ô là đơn vị nhỏ nhất của bảng. Tách theo `w:p` sẽ cắt một câu xuống dòng
    trong ô thành hai đơn vị, và đoạn trích của nó không còn nằm gọn ở đâu."""
    t = doc("x.docx", _docx(_tbl(_tr(_tc(_p("Dòng một"), _p("Dòng hai"))))))
    assert [d.noi_dung for d in t.don_vi] == ["Dòng một Dòng hai"]


def test_bang_long_nhau_NAM_TRONG_o_bao_ngoai():
    trong = _tbl(_tr(_tc(_p("Bên trong"))))
    t = doc("x.docx", _docx(_tbl(_tr(_tc(_p("Bên ngoài") + trong)))))
    assert [d.noi_dung for d in t.don_vi] == ["Bên ngoài Bên trong"]
    assert t.don_vi[0].bang == (0, 0, 0), "bảng lồng không được đánh số như bảng cấp thân"


# ------------------------------------------------- đầu trang / chân trang


def test_dau_trang_va_chan_trang_mang_VUNG_rieng():
    t = doc(
        "x.docx",
        _docx(
            _p("Thân bài"),
            {
                "word/header1.xml": _HDR.format(than=_p("BM.ĐT.18.11")),
                "word/footer1.xml": _FTR.format(than=_p("Trang 1/2")),
            },
        ),
    )
    assert [(d.noi_dung, d.vung) for d in t.don_vi] == [
        ("Thân bài", "than"),
        ("BM.ĐT.18.11", "dau_trang"),
        ("Trang 1/2", "chan_trang"),
    ]


def test_khong_co_dau_chan_trang_thi_moi_don_vi_deu_la_than():
    t = doc("x.docx", _docx(_p("Chỉ có thân")))
    assert [d.vung for d in t.don_vi] == ["than"]


# --------------------------------------------------------------- lùi về


def test_LUI_VE_duyet_phang_khi_cau_truc_doc_duoc_IT_CHU_HON():
    """`w:sdt` ở cấp thân không phải `w:p` cũng không phải `w:tbl`.

    Duyệt theo cấu trúc bỏ qua nó; duyệt phẳng thì không. Mất toạ độ bảng là
    một khoản lỗ có thể sống chung; mất nguyên một điều khoản thì không.
    """
    than = _p("Có") + f"<w:sdt><w:sdtContent>{_p('Nội dung trong sdt')}</w:sdtContent></w:sdt>"
    t = doc("x.docx", _docx(than))

    assert [d.noi_dung for d in t.don_vi] == ["Có", "Nội dung trong sdt"]
    assert [d.bang for d in t.don_vi] == [None, None], "đường lùi không có toạ độ bảng"
    assert {d.vung for d in t.don_vi} == {"than"}


def test_lui_ve_VAN_giu_dau_trang():
    """Thân lùi về duyệt phẳng không kéo theo việc mất đầu trang."""
    than = _p("Có") + f"<w:sdt><w:sdtContent>{_p('Trong sdt')}</w:sdtContent></w:sdt>"
    t = doc("x.docx", _docx(than, {"word/header1.xml": _HDR.format(than=_p("Đầu trang"))}))
    assert [d.vung for d in t.don_vi] == ["than", "than", "dau_trang"]


# ------------------------------------------------------------- phanh zip


def test_qua_nhieu_muc_trong_zip_la_TEP_HONG():
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", _DOC.format(than=_p("x")))
        for i in range(TRAN_SO_MUC_ZIP):
            z.writestr(f"word/media/{i}.png", b"")

    with pytest.raises(KhongDocDuoc) as e:
        doc("x.docx", buf.getvalue())
    assert e.value.ly_do is LoaiHong.tep_hong


def test_tong_kich_thuoc_GIAI_NEN_vuot_tran_la_TEP_HONG():
    """Zip bom: 64 MB số 0 nén lại còn vài chục KB. Trần đọc theo kích thước
    KHAI BÁO trong zip, trước khi giải nén một byte nào."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", _DOC.format(than=_p("x")))
        z.writestr("word/media/phinh.bin", b"\0" * (TRAN_GIAI_NEN_BYTE + 1))

    assert len(buf.getvalue()) < 1_000_000, "tệp nén vẫn nhỏ — trần kích thước tệp không bắt được"
    with pytest.raises(KhongDocDuoc) as e:
        doc("x.docx", buf.getvalue())
    assert e.value.ly_do is LoaiHong.tep_hong


def test_docx_binh_thuong_di_qua_duoc_phanh():
    t = doc("x.docx", _docx(_p("Bình thường")))
    assert [d.noi_dung for d in t.don_vi] == ["Bình thường"]


# ------------------------------------------------------------ _dat_vi_tri


def test__dat_vi_tri_giu_vung_va_bang_ma_VAN_nhan_hai_hinh_dang_cu():
    t = _dat_vi_tri(
        [
            (1, "Đoạn thân"),                                  # nhánh chữ thật
            (1, "Dòng OCR", 0.9),                              # nhánh OCR
            (1, "Ô bảng", None, "chan_trang", (2, 0, 1)),      # nhánh có cấu trúc
        ]
    )
    assert [d.vung for d in t.don_vi] == ["than", "than", "chan_trang"]
    assert [d.bang for d in t.don_vi] == [None, None, (2, 0, 1)]
    assert t.don_vi[1].nguon_chu is NguonChu.ocr
    assert t.don_vi[0].nguon_chu is NguonChu.lop_chu


# --------------------------------------------------------------- neo vào ô


def test_xac_minh_NEO_DUOC_vao_mot_o_bang():
    """Cấu trúc mới không được làm hỏng phép tra chuỗi đang chạy."""
    from src.services.neo_du_kien import LyDoNeo, xac_minh

    t = doc("phieu.docx", _docx(_tbl(_tr(_tc(_p("Ý thức chuyên cần")), _tc(_p("Đạt 2,0 điểm"))))))
    neo = xac_minh("Đạt 2,0 điểm", t.don_vi)

    assert neo.ly_do is LyDoNeo.ok
    assert neo.chi_so_don_vi == 1 and neo.trang == 1


# ------------------------------------------------- hộp chữ và mc:AlternateContent

_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def _hop_chu(chu: str) -> str:
    """Một `w:r` mang hộp chữ theo đúng khuôn Word: cùng nội dung ở `mc:Choice`
    và `mc:Fallback`."""
    txbx = f"<w:txbxContent>{_p(chu)}</w:txbxContent>"
    return (
        f'<w:r><mc:AlternateContent xmlns:mc="{_MC}">'
        f'<mc:Choice Requires="wps"><w:drawing>{txbx}</w:drawing></mc:Choice>'
        f"<mc:Fallback><w:pict>{txbx}</w:pict></mc:Fallback>"
        "</mc:AlternateContent></w:r>"
    )


def test_hop_chu_KHONG_lam_cau_truc_thua_oan_va_KHONG_doc_hai_lan():
    """Đo trên tệp thật 2026-09-16: một đoạn mang hộp chữ làm duyệt phẳng đếm
    "Phụ lục 4" hai lần (Choice + Fallback, lại lồng `w:p` trong `w:p`), cấu
    trúc bị coi là "ít chữ hơn" và ba bảng mất toạ độ. Thước đo lùi về phải là
    tổng chữ thật, và `mc:Fallback` phải bị bỏ trước khi đếm."""
    than = (
        f"<w:p><w:r><w:t>Phụ lục 4</w:t></w:r>{_hop_chu('Hộp chữ')}</w:p>"
        + _tbl(_tr(_tc(_p("Tuần 1")), _tc(_p("Nội dung tuần một của kế hoạch"))))
    )
    t = doc("x.docx", _docx(than))

    chu = " ".join(d.noi_dung for d in t.don_vi)
    assert chu.count("Hộp chữ") == 1, "Fallback bị đọc lần hai"
    assert [d.bang for d in t.don_vi if d.bang] == [(0, 0, 0), (0, 0, 1)], "bảng phải giữ toạ độ"


def test_sdt_o_cap_than_VAN_lui_ve_duyet_phang():
    """Thước đo mới không được làm mất đường lùi: chữ trong `w:sdt` cấp thân vẫn
    chỉ duyệt phẳng thấy."""
    than = _p("Có") + f"<w:sdt><w:sdtContent>{_p('Nội dung trong sdt dài hơn hẳn')}</w:sdtContent></w:sdt>"
    t = doc("x.docx", _docx(than))
    assert [d.noi_dung for d in t.don_vi] == ["Có", "Nội dung trong sdt dài hơn hẳn"]


# ------------------------------------------------------------------ viền bảng
#
# Biểu mẫu tiếng Việt dùng bảng KHÔNG viền để xếp cột — cặp ô ký tên cuối
# trang, khối "tên đơn vị trái / quốc hiệu phải" đầu trang. Trước bản vá này,
# reader không đọc `w:tblBorders`/`w:tcBorders` nên mọi bảng ra màn hình đều có
# kẻ ô: một khối ký thành cái lưới, không còn chỗ ký. Điều phải khoá ở đây là
# NGUỒN quyết định, không phải một phép đoán theo chữ trong ô.


def _tbl_pr(*noi: str) -> str:
    return f"<w:tblPr>{''.join(noi)}</w:tblPr>"


def _canh(*ten: str) -> str:
    return "".join(f'<w:{t} w:val="single" w:sz="4" w:space="0" w:color="auto"/>' for t in ten)


def _vien_cua(t, bang: int) -> set[bool]:
    return {d.bang_vien for d in t.don_vi if d.bang and d.bang[0] == bang}


def test_bang_KHONG_khai_vien_nao_doc_ra_KHONG_VIEN():
    """Ô ký của BM.ĐT.18.05 (đo 2026-09-18): `w:tbl` không `w:tblBorders`,
    không `w:tblStyle`, không `w:tcBorders` — Word vẽ nó không viền, và reader
    phải nói đúng như vậy thay vì để render tự kẻ khung."""
    than = _tbl(_tr(_tc(_p("Giảng viên hướng dẫn")), _tc(_p("Sinh viên thực tập"))))
    t = doc("ke-hoach.docx", _docx(than))

    assert _vien_cua(t, 0) == {False}


def test_bang_khai_tblBorders_doc_ra_CO_VIEN():
    """Bảng kế hoạch của cùng biểu mẫu đó KHAI `w:tblBorders` single đủ sáu
    cạnh — bỏ viền của nó là làm hỏng một bảng đang đúng."""
    than = _tbl(
        _tbl_pr(
            f"<w:tblBorders>{_canh('top', 'left', 'bottom', 'right', 'insideH', 'insideV')}</w:tblBorders>"
        ),
        _tr(_tc(_p("TT")), _tc(_p("Thời gian"))),
    )
    t = doc("ke-hoach.docx", _docx(than))

    assert _vien_cua(t, 0) == {True}


def test_tblBorders_toan_nil_doc_ra_KHONG_VIEN():
    """`w:val="nil"` là cách Word ghi "đã tắt viền" — khai báo CÓ mặt nhưng
    không vẽ nét nào. Đọc "có `w:tblBorders` nghĩa là có viền" sẽ sai đúng ở
    những bảng người soạn cố ý tắt viền."""
    canh = "".join(f'<w:{c} w:val="nil"/>' for c in ("top", "left", "bottom", "right"))
    than = _tbl(_tbl_pr(f"<w:tblBorders>{canh}</w:tblBorders>"), _tr(_tc(_p("Bên A")), _tc(_p("Bên B"))))
    t = doc("hop-dong.docx", _docx(than))

    assert _vien_cua(t, 0) == {False}


def test_MOT_o_khai_tcBorders_du_lam_ca_bang_CO_VIEN():
    """Bảng im lặng ở cấp bảng nhưng kẻ khung cho một ô vẫn là bảng có nét —
    một cờ cho cả bảng phải nghiêng về "giữ nét tệp có vẽ", không bỏ mất nó."""
    o_co_vien = f"<w:tc><w:tcPr><w:tcBorders>{_canh('top')}</w:tcBorders></w:tcPr>{_p('1')}</w:tc>"
    than = _tbl(_tr(o_co_vien, _tc(_p("Tuần 1"))))
    t = doc("x.docx", _docx(than))

    assert _vien_cua(t, 0) == {True}


def test_vien_thua_ke_tu_KIEU_bang_TableGrid():
    """`TableGrid` là cách phổ biến nhất để một biểu mẫu có viền: bảng chỉ khai
    `w:tblStyle`, còn nét nằm trong `styles.xml`. Bỏ qua phần đó là đọc mọi
    bảng TableGrid thành không viền — mất nét tệp CÓ vẽ."""
    canh = _canh("top", "left", "bottom", "right", "insideH", "insideV")
    styles = (
        f'<?xml version="1.0"?><w:styles xmlns:w="{_NSW}">'
        '<w:style w:type="table" w:styleId="TableGrid">'
        f"<w:tblPr><w:tblBorders>{canh}</w:tblBorders></w:tblPr></w:style></w:styles>"
    )
    than = _tbl(_tbl_pr('<w:tblStyle w:val="TableGrid"/>'), _tr(_tc(_p("TT")), _tc(_p("Nội dung"))))
    t = doc("x.docx", _docx(than, {"word/styles.xml": styles}))

    assert _vien_cua(t, 0) == {True}


def test_kieu_con_TAT_vien_cua_kieu_cha():
    """Thừa kế `w:basedOn` phải đi đúng chiều: kiểu con khai viền `nil` thì
    bảng dùng kiểu con KHÔNG có viền, dù kiểu cha có."""
    canh = _canh("top", "left", "bottom", "right")
    nil = "".join(f'<w:{c} w:val="nil"/>' for c in ("top", "left", "bottom", "right"))
    styles = (
        f'<?xml version="1.0"?><w:styles xmlns:w="{_NSW}">'
        '<w:style w:type="table" w:styleId="Luoi">'
        f"<w:tblPr><w:tblBorders>{canh}</w:tblBorders></w:tblPr></w:style>"
        '<w:style w:type="table" w:styleId="LuoiTrang"><w:basedOn w:val="Luoi"/>'
        f"<w:tblPr><w:tblBorders>{nil}</w:tblBorders></w:tblPr></w:style></w:styles>"
    )
    than = _tbl(_tbl_pr('<w:tblStyle w:val="LuoiTrang"/>'), _tr(_tc(_p("Bên A")), _tc(_p("Bên B"))))
    t = doc("x.docx", _docx(than, {"word/styles.xml": styles}))

    assert _vien_cua(t, 0) == {False}


def test_hai_bang_trong_MOT_tai_lieu_giu_vien_RIENG():
    """Cờ viền phải theo từng BẢNG, không phải một giá trị cho cả tài liệu —
    BM.ĐT.18.05 có đúng hình dạng này: đầu trang không viền, bảng kế hoạch có
    viền, ô ký không viền."""
    co_vien = _tbl(
        _tbl_pr(f"<w:tblBorders>{_canh('top', 'left', 'bottom', 'right')}</w:tblBorders>"),
        _tr(_tc(_p("TT")), _tc(_p("Thời gian"))),
    )
    khong_vien = _tbl(_tr(_tc(_p("Giảng viên hướng dẫn")), _tc(_p("Sinh viên thực tập"))))
    t = doc("ke-hoach.docx", _docx(co_vien + khong_vien))

    assert _vien_cua(t, 0) == {True}
    assert _vien_cua(t, 1) == {False}


def test_trHeight_doc_ra_chieu_cao_hang_theo_twip():
    """Chiều cao khai báo là thứ cho hàng ký chỗ ký tay: hàng ký của
    BM.ĐT.18.05 khai 1499 twip trong khi chữ của nó chỉ chiếm hai dòng. Hàng
    không khai thì `0`, không đoán một con số nào."""
    than = _tbl(
        f'<w:tr><w:trPr><w:trHeight w:val="1499"/></w:trPr>{_tc(_p("Giảng viên hướng dẫn"))}</w:tr>',
        _tr(_tc(_p("Ghi chú"))),
    )
    t = doc("x.docx", _docx(than))

    assert [(d.bang, d.bang_cao) for d in t.don_vi if d.bang] == [((0, 0, 0), 1499), ((0, 1, 0), 0)]


def test_tep_docx_THAT_cua_tap_mau_doc_ra_bang_KHONG_VIEN():
    """Cùng phép đọc trên một tệp `.docx` THẬT, không phải chuỗi XML dựng trong
    test: `phieu-cham-trang.docx` của tập mẫu đường tổng quát có `w:tbl` không
    khai viền nào, và reader phải nói đúng như vậy — kể cả khi tên tệp gợi ý
    một phiếu chấm (thứ người ta hay kẻ khung). NGUỒN quyết định, không phải
    loại giấy tờ.

    Tệp là ĐẦU RA của `eval/datasets/tai_lieu_tong_quat/dung_mau.py`, không
    commit (xem docstring script đó) — chưa dựng thì bỏ qua, không dựng hộ:
    một phép kiểm tự sinh đầu vào của chính nó không còn kiểm được gì.
    """
    from pathlib import Path

    tep = Path("eval/datasets/tai_lieu_tong_quat/phieu-cham-trang.docx")
    if not tep.exists():
        pytest.skip("chưa dựng tập mẫu: python eval/datasets/tai_lieu_tong_quat/dung_mau.py")

    t = doc(tep.name, tep.read_bytes())
    o_bang = [d for d in t.don_vi if d.bang is not None]

    assert o_bang, "tệp mẫu này phải có bảng thật"
    assert {d.bang_vien for d in o_bang} == {False}
