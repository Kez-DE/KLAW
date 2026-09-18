"""Viền TỪNG CẠNH, lề trang, và luật chiều cao hàng (quyết định 2026-09-18).

`test_doc_tai_lieu_cau_truc.py` đã khoá phần "bảng này CÓ vẽ nét nào không" —
một cờ bool mỗi bảng. File này khoá phần cờ bool không tả được: nét nào ở cạnh
nào, dày bao nhiêu; chữ trong trang bắt đầu từ đâu; và một `w:trHeight` được
đọc theo luật gì.

Ba điều ở đây không suy ra được từ file kia:

1. Một biểu mẫu chỉ kẻ KHUNG NGOÀI (`w:tblBorders` không khai `insideH`/
   `insideV`) và một biểu mẫu kẻ lưới đủ ô cho ra CÙNG một cờ `bang_vien=True`.
   Vẽ cái thứ nhất thành cái thứ hai là KLAW kẻ thêm nét tài liệu không có —
   đúng chế độ hỏng mà cờ viền từng sửa một lần ở mức cả bảng.
2. `w:sectPr/w:pgMar` chưa từng được đọc, nên mọi bản dựng lại đặt chữ theo lề
   của chính KLAW: một biểu mẫu khai lề trái 1701 twip (30mm) ra màn hình ở
   ≈16,8mm. Không có lề thì "đúng vị trí" không đo được bằng gì.
3. `w:trHeight/@w:hRule` phân biệt "cao ít nhất chừng này" với "cao ĐÚNG chừng
   này, tràn thì cắt" và với "bỏ con số đi". Bộ đọc cất nguyên văn cả ba; ba
   nơi vẽ cố ý coi `exact` như tối thiểu (cắt mất chữ người dùng hỏng hơn),
   nên cái thước phải chấm SỰ THẬT ĐỌC RA, không chấm nét đã vẽ.

`noi_dung` không được đổi một byte vì bản vá này — cột mốc cuối file, cùng phép
đo `test_doc_tai_lieu_dinh_dang`/`_gian_cach` đã dùng cho `w:rPr` và `w:spacing`.
"""

import zipfile
from io import BytesIO

from src.agents.nodes.hieu_tai_lieu import _bang_theo_nhan, lam_sach_van_ban
from src.services.doc_tai_lieu import doc
from src.services.neo_du_kien import LyDoNeo, normalize, xac_minh
from src.services.tai_lieu import _hang_don_vi

_NSW = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_DOC = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    f'<w:document xmlns:w="{_NSW}"><w:body>{{than}}</w:body></w:document>'
)
_STYLES = f'<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="{_NSW}">{{kieu}}</w:styles>'


def _p(chu: str) -> str:
    return f"<w:p><w:r><w:t>{chu}</w:t></w:r></w:p>"


def _tc(chu: str, vien: str = "") -> str:
    pr = f"<w:tcPr>{vien}</w:tcPr>" if vien else ""
    return f"<w:tc>{pr}{_p(chu)}</w:tc>"


def _tr(*o: str, pr: str = "") -> str:
    return f"<w:tr>{f'<w:trPr>{pr}</w:trPr>' if pr else ''}{''.join(o)}</w:tr>"


def _tbl(*hang: str, pr: str = "") -> str:
    return f"<w:tbl>{f'<w:tblPr>{pr}</w:tblPr>' if pr else ''}{''.join(hang)}</w:tbl>"


def _docx(than: str, kieu: str = "") -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", _DOC.format(than=than))
        if kieu:
            z.writestr("word/styles.xml", _STYLES.format(kieu=kieu))
    return buf.getvalue()


def _o_bang(than: str, kieu: str = ""):
    return [d for d in doc("x.docx", _docx(than, kieu)).don_vi if d.bang is not None]


# ------------------------------------------------------ viền theo từng cạnh

_BANG_2x2 = (_tr(_tc("A"), _tc("B")), _tr(_tc("C"), _tc("D")))


def test_CHI_MOT_SO_CANH_khai_thi_chi_nhung_canh_do_duoc_doc():
    """Khung ngoài, KHÔNG kẻ trong — hình dạng của một bảng bố cục biểu mẫu.
    Cạnh không khai phải VẮNG MẶT, không được lấp bằng một giá trị đoán."""
    than = _tbl(
        *_BANG_2x2,
        pr=(
            "<w:tblBorders>"
            '<w:top w:val="single" w:sz="6"/><w:left w:val="single" w:sz="6"/>'
            '<w:bottom w:val="single" w:sz="6"/><w:right w:val="single" w:sz="6"/>'
            "</w:tblBorders>"
        ),
    )
    o = _o_bang(than)
    assert o[0].bang_vien_canh == (
        ("top", "single", "6"),
        ("left", "single", "6"),
        ("bottom", "single", "6"),
        ("right", "single", "6"),
    )
    # `insideH`/`insideV` KHÔNG có mặt: tệp không nói, bộ đọc không thêm.
    assert [c for c, _, _ in o[0].bang_vien_canh] == ["top", "left", "bottom", "right"]
    # Sự thật cấp bảng chép trên MỌI ô, cùng khuôn `bang_ti_le`.
    assert all(d.bang_vien_canh == o[0].bang_vien_canh for d in o)


def test_MOT_O_DE_LEN_dung_MOT_canh_cua_bang():
    than = _tbl(
        _tr(
            _tc("A", '<w:tcBorders><w:bottom w:val="double" w:sz="12"/></w:tcBorders>'),
            _tc("B"),
        ),
        pr='<w:tblBorders><w:bottom w:val="single" w:sz="6"/></w:tblBorders>',
    )
    o = _o_bang(than)
    assert o[0].o_vien_canh == (("bottom", "double", "12"),)
    # Ô thứ hai KHÔNG khai gì — không được thừa hưởng phần khai của ô bên cạnh.
    assert o[1].o_vien_canh == ()
    # Viền cấp bảng vẫn nguyên văn ở cả hai ô: hai sự thật khác nhau, hai chỗ.
    assert o[0].bang_vien_canh == o[1].bang_vien_canh == (("bottom", "single", "6"),)


def test_VAL_NONE_va_NIL_duoc_giu_NGUYEN_VAN_chu_khong_bi_loc_bo():
    """`none` là tệp nói RÕ "không vẽ cạnh này" — khác hẳn cạnh vắng mặt
    (nghĩa là "thừa kế"). Lọc nó ra ở bộ đọc là xoá đúng chỗ phân biệt ấy, và
    một ô tắt cạnh sẽ thừa kế lại cạnh bảng."""
    than = _tbl(
        _tr(_tc("A", '<w:tcBorders><w:right w:val="nil"/></w:tcBorders>')),
        pr='<w:tblBorders><w:right w:val="none"/></w:tblBorders>',
    )
    o = _o_bang(than)
    assert o[0].bang_vien_canh == (("right", "none", ""),)
    assert o[0].o_vien_canh == (("right", "nil", ""),)


def test_VIEN_THUA_KE_QUA_TBLSTYLE_VA_BASEDON_tron_theo_TUNG_CANH():
    """`TableGrid` khai cả sáu cạnh trong `styles.xml` và KHÔNG khai gì trong
    `document.xml` — cách phổ biến nhất để một biểu mẫu Việt Nam có viền. Kiểu
    CON khai lại một cạnh chỉ đè ĐÚNG cạnh đó, không chặn cả cụm của cha."""
    kieu = (
        '<w:style w:type="table" w:styleId="Cha"><w:tblPr><w:tblBorders>'
        '<w:top w:val="single" w:sz="4"/><w:insideH w:val="single" w:sz="4"/>'
        "</w:tblBorders></w:tblPr></w:style>"
        '<w:style w:type="table" w:styleId="Con"><w:basedOn w:val="Cha"/>'
        '<w:tblPr><w:tblBorders><w:insideH w:val="nil"/></w:tblBorders></w:tblPr></w:style>'
    )
    o = _o_bang(_tbl(*_BANG_2x2, pr='<w:tblStyle w:val="Con"/>'), kieu)
    assert o[0].bang_vien_canh == (("top", "single", "4"), ("insideH", "nil", ""))


def test_KHAI_TRUC_TIEP_DE_LEN_KIEU_theo_dung_thu_tu_Word_ap_dung():
    kieu = (
        '<w:style w:type="table" w:styleId="G"><w:tblPr><w:tblBorders>'
        '<w:top w:val="single" w:sz="4"/><w:left w:val="single" w:sz="4"/>'
        "</w:tblBorders></w:tblPr></w:style>"
    )
    than = _tbl(
        *_BANG_2x2,
        pr=(
            '<w:tblStyle w:val="G"/>'
            '<w:tblBorders><w:top w:val="double" w:sz="18"/></w:tblBorders>'
        ),
    )
    o = _o_bang(than, kieu)
    # `top` theo khai trực tiếp, `left` vẫn thừa kế từ kiểu — trộn theo CẠNH.
    assert o[0].bang_vien_canh == (("top", "double", "18"), ("left", "single", "4"))


def test_KHONG_KHAI_VIEN_NAO_thi_ca_hai_truong_canh_deu_RONG():
    o = _o_bang(_tbl(*_BANG_2x2))
    assert o[0].bang_vien_canh == () and o[0].o_vien_canh == ()


def test_CO_NET_van_dung_khi_bang_chi_khai_canh_ngoai():
    """Cờ bool cũ KHÔNG được đổi nghĩa vì có thêm trường cạnh: mục
    `vien_bang_co_net` của thước đo phải giữ nguyên 100%."""
    o = _o_bang(_tbl(*_BANG_2x2, pr='<w:tblBorders><w:top w:val="single" w:sz="6"/></w:tblBorders>'))
    assert o[0].bang_vien is True
    o2 = _o_bang(_tbl(*_BANG_2x2, pr='<w:tblBorders><w:top w:val="nil"/></w:tblBorders>'))
    assert o2[0].bang_vien is False


# -------------------------------------------------------------- lề trang

_PG = '<w:sectPr><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1701" w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>'


def test_PGMAR_doc_ra_du_bay_thuoc_tinh_theo_twip():
    t = doc("x.docx", _docx(_p("Xin chào") + _PG))
    assert t.don_vi[0].le_trang == (
        ("top", 1134),
        ("right", 1134),
        ("bottom", 1134),
        ("left", 1701),
        ("header", 709),
        ("footer", 709),
        ("gutter", 0),
    )


def test_PGMAR_chep_len_MOI_don_vi_ke_ca_o_bang():
    t = doc("x.docx", _docx(_p("Đầu") + _tbl(*_BANG_2x2) + _PG))
    assert len({d.le_trang for d in t.don_vi}) == 1
    assert all(d.le_trang[3] == ("left", 1701) for d in t.don_vi)


def test_KHONG_CO_SECTPR_thi_le_trang_RONG_khong_doan_le_mac_dinh():
    """Không khai thì để phía vẽ giữ lề của chính nó — cùng nguyên tắc
    `bang_ti_le` từ chối đoán tỉ lệ cột."""
    t = doc("x.docx", _docx(_p("Xin chào")))
    assert t.don_vi[0].le_trang == ()


def test_PGMAR_AM_giu_nguyen_dau_am():
    than = _p("x") + '<w:sectPr><w:pgMar w:top="-720" w:left="0"/></w:sectPr>'
    assert doc("x.docx", _docx(than)).don_vi[0].le_trang == (("top", -720), ("left", 0))


def test_MOT_THUOC_TINH_HONG_chi_bo_RIENG_no():
    than = _p("x") + '<w:sectPr><w:pgMar w:top="1134" w:left="abc"/></w:sectPr>'
    assert doc("x.docx", _docx(than)).don_vi[0].le_trang == (("top", 1134),)


# --------------------------------------------------- luật chiều cao hàng


def test_HRULE_EXACT_VA_ATLEAST_doc_ra_NGUYEN_VAN_khong_gop_lam_mot():
    than = _tbl(
        _tr(_tc("A"), pr='<w:trHeight w:val="1499" w:hRule="exact"/>'),
        _tr(_tc("B"), pr='<w:trHeight w:val="800" w:hRule="atLeast"/>'),
    )
    o = _o_bang(than)
    assert [(d.bang_cao, d.bang_cao_luat) for d in o] == [(1499, "exact"), (800, "atLeast")]


def test_HRULE_VANG_MAT_thi_luat_RONG_khong_phai_atLeast():
    """Rỗng nghĩa là "tệp không khai", khác hẳn tệp khai `atLeast` — cái thước
    chỉ đếm những gì tệp KHAI, nên lấp sẵn `atLeast` là thổi điểm."""
    o = _o_bang(_tbl(_tr(_tc("A"), pr='<w:trHeight w:val="600"/>')))
    assert (o[0].bang_cao, o[0].bang_cao_luat) == (600, "")


def test_HRULE_AUTO_van_doc_CA_SO_LAN_LUAT_quyet_dinh_ve_o_phia_render():
    """`auto` bảo Word bỏ con số. Bộ đọc vẫn cất CẢ HAI: sự thật là sự thật,
    còn bỏ hay không là quyết định của ba nơi vẽ (chúng bỏ — xem
    `XemTruocA4.caoTrenTrang`)."""
    o = _o_bang(_tbl(_tr(_tc("A"), pr='<w:trHeight w:val="600" w:hRule="auto"/>')))
    assert (o[0].bang_cao, o[0].bang_cao_luat) == (600, "auto")


# ------------------------------------------- ghép về từng ô (hieu_tai_lieu)


def test_GHEP_O_lay_canh_NGOAI_cho_hang_dau_va_insideH_cho_hang_giua():
    than = _tbl(
        _tr(_tc("A"), _tc("B")),
        _tr(_tc("C"), _tc("D")),
        pr=(
            "<w:tblBorders>"
            '<w:top w:val="single" w:sz="6"/><w:bottom w:val="single" w:sz="6"/>'
            '<w:left w:val="single" w:sz="6"/><w:right w:val="single" w:sz="6"/>'
            '<w:insideH w:val="nil"/><w:insideV w:val="single" w:sz="4"/>'
            "</w:tblBorders>"
        ),
    )
    ra = _bang_theo_nhan([{"nhan": "A", "don_vi": _o_bang(than)}])["A0"]
    # Ô (0,0): trên = `top` (hàng đầu), dưới = `insideH` (nil), trái = `left`,
    # phải = `insideV`. Ô (1,1): dưới = `bottom`, phải = `right`.
    assert ra["vien_o"][0][0] == "single/6|single/4|nil/|single/6"
    assert ra["vien_o"][1][1] == "nil/|single/6|single/6|single/4"


def test_GHEP_O_canh_cua_CHINH_O_de_len_canh_bang():
    than = _tbl(
        _tr(_tc("A", '<w:tcBorders><w:top w:val="double" w:sz="18"/></w:tcBorders>')),
        pr='<w:tblBorders><w:top w:val="single" w:sz="6"/></w:tblBorders>',
    )
    ra = _bang_theo_nhan([{"nhan": "A", "don_vi": _o_bang(than)}])["A0"]
    assert ra["vien_o"][0][0].split("|")[0] == "double/18"


def test_GHEP_O_SZ_HONG_lam_CA_BANG_lui_ve_net_deu():
    """Fail closed theo BẢNG: nửa bảng theo nguồn, nửa kia theo một bề dày
    đoán bừa là tệ hơn hẳn cả bảng kẻ một nét đều như trước bản vá."""
    than = _tbl(
        *_BANG_2x2,
        pr='<w:tblBorders><w:top w:val="single" w:sz="6pt"/></w:tblBorders>',
    )
    ra = _bang_theo_nhan([{"nhan": "A", "don_vi": _o_bang(than)}])["A0"]
    assert ra["vien_o"] == []
    assert ra["vien"] is True  # cờ cũ vẫn nói "bảng này có vẽ nét"


def test_GHEP_O_bang_KHONG_khai_canh_nao_thi_vien_o_RONG():
    ra = _bang_theo_nhan([{"nhan": "A", "don_vi": _o_bang(_tbl(*_BANG_2x2))}])["A0"]
    assert ra["vien_o"] == [] and ra["cao_luat"] == ["", ""]


def test_LAM_SACH_VAN_BAN_mang_LE_TRANG_sang_TUNG_MUC():
    don_vi = doc("x.docx", _docx(_p("Xin chào") + _PG)).don_vi
    ra, _ = lam_sach_van_ban(
        {"muc": [{"ten": "A", "khoi": [{"noi_dung": "Xin chào"}]}]},
        "Xin chào",
        [{"nhan": "A", "don_vi": don_vi}],
    )
    assert ra["muc"][0]["le_trang"][3] == ("left", 1701)


def test_LAM_SACH_VAN_BAN_KHONG_them_khoa_le_trang_khi_nguon_khong_khai():
    don_vi = doc("x.docx", _docx(_p("Xin chào"))).don_vi
    ra, _ = lam_sach_van_ban(
        {"muc": [{"ten": "A", "khoi": [{"noi_dung": "Xin chào"}]}]},
        "Xin chào",
        [{"nhan": "A", "don_vi": don_vi}],
    )
    assert "le_trang" not in ra["muc"][0]


# ------------------------------------------------------- lưu rồi đọc lại


def test_LUU_ROI_DOC_LAI_ra_DUNG_canh_luat_va_le_ban_dau():
    """Ranh giới lưu/đọc là chỗ căn lề từng mất một lần (xem `_hang_don_vi`):
    một vòng JSON phải trả về một giá trị BẰNG chính nó."""
    import json

    from src.services.tai_lieu import _canh_tu_hang, _le_tu_hang

    than = (
        _tbl(
            _tr(
                _tc("A", '<w:tcBorders><w:top w:val="double" w:sz="18"/></w:tcBorders>'),
                pr='<w:trHeight w:val="1499" w:hRule="exact"/>',
            ),
            pr='<w:tblBorders><w:top w:val="single" w:sz="6"/></w:tblBorders>',
        )
        + _PG
    )
    d = _o_bang(than)[0]
    tho = json.loads(json.dumps(_hang_don_vi(d), ensure_ascii=False))
    assert _canh_tu_hang(tho["bang_vien_canh"]) == d.bang_vien_canh
    assert _canh_tu_hang(tho["o_vien_canh"]) == d.o_vien_canh
    assert _le_tu_hang(tho["le_trang"]) == d.le_trang
    assert tho["bang_cao_luat"] == d.bang_cao_luat == "exact"


# -------------------------------- `noi_dung` và mọi thứ tra trên nó KHÔNG ĐỔI

_THAN_DAY = (
    _p("Mức lương: 20.000.000 đồng/tháng")
    + _tbl(
        _tr(
            _tc("Chức danh", '<w:tcBorders><w:top w:val="double" w:sz="18"/></w:tcBorders>'),
            _tc("Kỹ sư"),
            pr='<w:trHeight w:val="1499" w:hRule="exact"/>',
        ),
        pr=(
            '<w:tblStyle w:val="G"/>'
            '<w:tblBorders><w:top w:val="single" w:sz="6"/><w:insideV w:val="nil"/></w:tblBorders>'
        ),
    )
    + _PG
)
_THAN_TRAN = _p("Mức lương: 20.000.000 đồng/tháng") + _tbl(_tr(_tc("Chức danh"), _tc("Kỹ sư")))
_KIEU_G = (
    '<w:style w:type="table" w:styleId="G"><w:tblPr><w:tblBorders>'
    '<w:left w:val="single" w:sz="4"/>'
    "</w:tblBorders></w:tblPr></w:style>"
)


def test_NOI_DUNG_va_NEO_va_LAM_SACH_y_HET_khi_bo_het_vien_va_le():
    """Cột mốc của cả bản vá, cùng phép đo `test_doc_tai_lieu_gian_cach` đã
    dùng cho `w:spacing`: thêm `w:tblBorders`/`w:tcBorders`/`w:trHeight`/
    `w:sectPr` vào tệp KHÔNG được đổi một ký tự nào của `noi_dung`, cũng không
    đổi kết quả của bất cứ phép tra nào đang chạy trên nó."""
    co = doc("x.docx", _docx(_THAN_DAY, _KIEU_G)).don_vi
    khong = doc("x.docx", _docx(_THAN_TRAN)).don_vi

    assert [d.noi_dung for d in co] == [d.noi_dung for d in khong]
    assert [(d.trang, d.offset_dau, d.chi_so) for d in co] == [
        (d.trang, d.offset_dau, d.chi_so) for d in khong
    ]
    assert [normalize(d.noi_dung) for d in co] == [normalize(d.noi_dung) for d in khong]

    trich = "20.000.000 đồng/tháng"
    neo_co, neo_khong = xac_minh(trich, co), xac_minh(trich, khong)
    assert neo_co.ly_do is LyDoNeo.ok
    assert (neo_co.chi_so_don_vi, neo_co.trang, neo_co.offset_dau) == (
        neo_khong.chi_so_don_vi,
        neo_khong.trang,
        neo_khong.offset_dau,
    )

    van_ban = {
        "muc": [
            {
                "ten": "Lương",
                "khoi": [{"noi_dung": "Mức lương: 20.000.000 đồng/tháng và thưởng 5.000.000 đồng"}],
            }
        ]
    }
    nguon = " ".join(d.noi_dung for d in co)
    ra_co, dem_co = lam_sach_van_ban(van_ban, nguon, [{"nhan": "A", "don_vi": co}])
    ra_khong, dem_khong = lam_sach_van_ban(van_ban, nguon, [{"nhan": "A", "don_vi": khong}])
    assert dem_co == dem_khong
    assert [[k["noi_dung"] for k in m["khoi"]] for m in ra_co["muc"]] == [
        [k["noi_dung"] for k in m["khoi"]] for m in ra_khong["muc"]
    ]
