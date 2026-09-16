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
