"""Giãn cách, thụt lề và mốc tab (`w:spacing`/`w:ind`/`w:tabs`) — quyết định
2026-09-18.

`test_doc_tai_lieu_dinh_dang.py` khoá "chữ trông thế nào"; file này khoá "chữ
đứng ở đâu trên trang": khoảng trống trên/dưới đoạn, giãn dòng, thụt lề, và
chỗ một ký tự tab nhảy tới.

Năm điều không suy ra được từ hai file kia:

1. **`noi_dung` KHÔNG ĐỔI MỘT KÝ TỰ.** `<w:tab/>` chưa bao giờ nằm trong
   `w:t`, nên nó chưa bao giờ vào `noi_dung`, và bản vá này KHÔNG được thêm nó
   vào: `neo_du_kien.xac_minh`, `normalize` và `lam_sach_van_ban` đang tra
   chính chuỗi ấy. Mốc tab là một VỊ TRÍ nằm cạnh chuỗi, không phải một ký tự
   trong chuỗi.
2. **Giãn cách đến TỪ KIỂU vẫn là giãn cách.** Một biểu mẫu đặt giãn dòng bằng
   `w:pStyle` không khai `w:spacing` ở đâu trong `document.xml`; đọc thẳng
   `w:pPr` sẽ dựng lại nó thành đoạn không giãn dòng.
3. **`w:line` một mình không nói được gì.** 360 với `lineRule="auto"` là một
   dòng rưỡi; 360 với `"exact"` là 18pt cố định. Hai câu trả lời khác nhau cho
   cùng một con số, nên `luat_dong` phải đi kèm.
4. **Fail closed theo từng phần tử.** Một `w:spacing` có giá trị đọc không ra
   số làm CẢ `w:spacing` của đoạn về "không khai" — không vẽ nửa bố cục —
   nhưng `w:ind` và `w:tabs` của chính đoạn đó thì không câm theo.
5. **Đường dẫn `dot` là thứ dễ thấy nhất của cả phase.** Nó vẽ ra dòng "……"
   mà một biểu mẫu tiếng Việt chừa cho người điền tay; mất nó thì chỗ để điền
   biến mất khỏi bản dựng lại, dù mọi chữ đều đúng.
"""

import zipfile
from io import BytesIO

from src.agents.nodes.hieu_tai_lieu import lam_sach_van_ban
from src.services.doc_tai_lieu import doc
from src.services.neo_du_kien import LyDoNeo, normalize, xac_minh
from src.services.tai_lieu import _gian_cach_tu_hang, _hang_gian_cach

_NSW = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_DOC = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    f'<w:document xmlns:w="{_NSW}"><w:body>{{than}}</w:body></w:document>'
)
_STYLES = f'<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="{_NSW}">{{kieu}}</w:styles>'


def _docx(than: str, kieu: str = "") -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", _DOC.format(than=than))
        if kieu:
            z.writestr("word/styles.xml", _STYLES.format(kieu=kieu))
    return buf.getvalue()


def _p(ppr: str, chu: str = "Nội dung mẫu", giua: str = "") -> str:
    """Một `w:p` một run, `ppr` là phần bên trong `w:pPr`; `giua` chèn thêm
    XML vào giữa run (chỗ đặt `<w:tab/>`)."""
    return f"<w:p><w:pPr>{ppr}</w:pPr><w:r>{giua}<w:t>{chu}</w:t></w:r></w:p>"


def _mot(than: str, kieu: str = ""):
    return doc("x.docx", _docx(than, kieu)).don_vi[0]


def _gc(than: str, kieu: str = ""):
    (g,) = _mot(than, kieu).gian_cach
    return g


# ------------------------------------------------ `w:spacing` khai TRỰC TIẾP


def test_SPACING_truc_tiep_doc_du_truoc_sau_va_giu_nguyen_van_trong_khai():
    g = _gc(_p('<w:spacing w:before="120" w:after="240"/>'))
    assert (g.truoc, g.sau) == (120, 240)
    # `khai` là thứ `eval.run_trung_thuc` chấm: NGUYÊN VĂN, không quy đổi.
    assert g.khai == (("spacing/after", "240"), ("spacing/before", "120"))


def test_SPACING_giu_CA_thuoc_tinh_khong_ve_duoc_vi_thuoc_do_hoi_tep_khai_gi():
    """`w:beforeLines` không có chỗ nào vẽ, nhưng vẫn là một điều tệp khai."""
    g = _gc(_p('<w:spacing w:before="48" w:beforeLines="20"/>'))
    assert ("spacing/beforeLines", "20") in g.khai


def test_SPACING_BEFORE_so_thuc_cua_bo_ghi_that_van_doc_ra_twip():
    """`Report_instruction.docx` của chủ dự án khai `48.00000000000001` trên 50
    đoạn. Từ chối nó thì 50 đoạn thật mất luôn cả giãn dòng của chúng."""
    g = _gc(_p('<w:spacing w:before="48.00000000000001" w:line="312" w:lineRule="auto"/>'))
    assert (g.truoc, g.dong) == (48, 312)
    assert ("spacing/before", "48.00000000000001") in g.khai


# --------------------------------------------------------- `w:line` × `w:lineRule`


def test_LINE_RULE_AUTO_giu_nguyen_boi_so_240_va_giu_nhan_auto():
    g = _gc(_p('<w:spacing w:line="360" w:lineRule="auto"/>'))
    assert (g.dong, g.luat_dong) == (360, "auto")


def test_LINE_RULE_EXACT_va_ATLEAST_doc_ra_hai_nhan_khac_nhau():
    assert _gc(_p('<w:spacing w:line="360" w:lineRule="exact"/>')).luat_dong == "exact"
    assert _gc(_p('<w:spacing w:line="360" w:lineRule="atLeast"/>')).luat_dong == "atLeast"


def test_LINE_khong_kem_LINE_RULE_ve_auto_dung_mac_dinh_OOXML():
    g = _gc(_p('<w:spacing w:line="480"/>'))
    assert (g.dong, g.luat_dong) == (480, "auto")


def test_KHONG_KHAI_LINE_thi_luat_dong_RONG_khong_phai_auto():
    """"Không khai" phải phân biệt được với "khai auto": phía vẽ giữ giãn dòng
    mặc định của chính nó ở ca đầu, và làm theo tệp ở ca sau."""
    assert _gc(_p('<w:spacing w:after="120"/>')).luat_dong == ""


# ------------------------------------------------------------------ `w:ind`


def test_IND_THUT_DONG_DAU_doc_rieng_khoi_thut_le_trai():
    g = _gc(_p('<w:ind w:left="720" w:firstLine="360"/>'))
    assert (g.trai, g.dau_dong, g.treo) == (720, 360, 0)


def test_IND_TREO_doc_rieng_va_KHONG_lan_sang_dau_dong():
    """`w:hanging` đẩy dòng ĐẦU ngược ra, `w:firstLine` đẩy nó vào — hai dấu
    ngược nhau, gộp một trường thì không nói được đang đẩy chiều nào."""
    g = _gc(_p('<w:ind w:left="720" w:hanging="426"/>'))
    assert (g.trai, g.dau_dong, g.treo) == (720, 0, 426)


def test_IND_START_END_ten_OOXML_strict_doc_nhu_LEFT_RIGHT():
    g = _gc(_p('<w:ind w:start="567" w:end="113"/>'))
    assert (g.trai, g.phai) == (567, 113)


def test_IND_AM_giu_nguyen_dau_am_vi_bieu_mau_that_tran_ra_ngoai_le():
    g = _gc(_p('<w:ind w:right="-567"/>'))
    assert g.phai == -567


# ------------------------------------------------------------------ `w:tabs`

# Đúng hình dạng `Evaluation Form.docx` của chủ dự án dùng 45 lần: một nhãn,
# một ký tự tab, một mốc canh PHẢI ở mép cột chữ với đường dẫn chấm. Đây là
# dòng "Company name: ………………" để người ta điền tay.
_THAN_DAN_CHAM = _p(
    '<w:tabs><w:tab w:val="right" w:pos="9360" w:leader="dot"/></w:tabs>'
    '<w:spacing w:line="240" w:lineRule="auto"/>',
    "Company name:",
    "",
).replace("</w:r>", "<w:tab/></w:r>")


def test_MOC_TAB_DAN_CHAM_doc_du_ba_su_that_val_pos_leader():
    g = _gc(_THAN_DAN_CHAM)
    (m,) = g.moc
    assert (m.val, m.pos, m.leader) == ("right", 9360, "dot")


def test_KY_TU_TAB_thanh_MOT_VI_TRI_tren_noi_dung_khong_phai_mot_ky_tu():
    d = _mot(_THAN_DAN_CHAM)
    assert d.noi_dung == "Company name:"
    (g,) = d.gian_cach
    # Ngay SAU ký tự cuối: đường dẫn bắt đầu ở chỗ chữ kết thúc.
    assert g.tab == (len(d.noi_dung),)


def test_MOC_TAB_dem_ca_mot_w_tab_VAL_CLEAR_nhung_khong_nhay_toi_no():
    """`w:val="clear"` XOÁ một mốc kiểu đặt sẵn — vẫn là một khai báo (thước
    đo đếm nó), nhưng không phải chỗ để nhảy tới."""
    g = _gc(
        _p(
            '<w:tabs><w:tab w:val="clear" w:pos="1440"/>'
            '<w:tab w:val="left" w:pos="2880" w:leader="hyphen"/></w:tabs>'
        )
    )
    assert [m.pos for m in g.moc] == [2880]
    assert ("tabs", "2") in g.khai


def test_MOC_TAB_sap_theo_POS_tang_dan_du_tep_ghi_lon_xon():
    g = _gc(
        _p(
            '<w:tabs><w:tab w:val="left" w:pos="5000"/>'
            '<w:tab w:val="left" w:pos="1000"/></w:tabs>'
        )
    )
    assert [m.pos for m in g.moc] == [1000, 5000]


def test_MOC_TAB_khong_khai_LEADER_thi_khong_ve_gi_dung_mac_dinh_w_leader():
    g = _gc(_p('<w:tabs><w:tab w:val="center" w:pos="4680"/></w:tabs>'))
    assert g.moc[0].leader == ""


def test_W_TAB_trong_W_TABS_khong_bi_dem_nham_thanh_KY_TU_tab():
    """Hai thẻ trùng tên, khác hẳn nghĩa: `w:tabs/w:tab` là ĐỊNH NGHĨA mốc."""
    g = _gc(_p('<w:tabs><w:tab w:val="left" w:pos="1440"/></w:tabs>'))
    assert g.tab == ()


# ----------------------------------------------- thừa kế qua kiểu đoạn văn

_KIEU_CHUOI = (
    '<w:style w:type="paragraph" w:styleId="Goc">'
    '<w:pPr><w:spacing w:line="360" w:lineRule="auto"/><w:ind w:left="720"/></w:pPr>'
    "</w:style>"
    '<w:style w:type="paragraph" w:styleId="Con">'
    '<w:basedOn w:val="Goc"/><w:pPr><w:spacing w:after="200"/></w:pPr>'
    "</w:style>"
)


def test_GIAN_CACH_thua_ke_qua_PSTYLE_va_BASEDON_tron_theo_tung_thuoc_tinh():
    """Kiểu con chỉ khai `w:after` vẫn phải thừa kế giãn dòng VÀ thụt lề của
    kiểu cha — lấy nguyên khối của kiểu đầu tiên có khai sẽ xoá mất hai thứ."""
    g = _gc(_p('<w:pStyle w:val="Con"/>'), _KIEU_CHUOI)
    assert (g.sau, g.dong, g.luat_dong, g.trai) == (200, 360, "auto", 720)


def test_THUA_KE_khong_vao_KHAI_vi_document_xml_khong_noi_cau_do():
    """`khai` trả lời "tệp tự khai gì Ở ĐÂY", còn các trường đã giải trả lời
    "phải vẽ thế nào" — hai câu hỏi, hai chỗ, không gộp."""
    assert _gc(_p('<w:pStyle w:val="Con"/>'), _KIEU_CHUOI).khai == ()


def test_DOAN_KHAI_TRUC_TIEP_DE_LEN_kieu_dung_thu_tu_Word_ap_dung():
    g = _gc(_p('<w:pStyle w:val="Con"/><w:spacing w:line="240" w:lineRule="auto"/>'), _KIEU_CHUOI)
    assert g.dong == 240
    assert g.sau == 200, "thuộc tính đoạn KHÔNG khai vẫn phải giữ giá trị thừa kế"


def test_MOC_TAB_thua_ke_tu_KIEU_khi_doan_khong_khai_w_tabs():
    kieu = (
        '<w:style w:type="paragraph" w:styleId="Dien">'
        '<w:pPr><w:tabs><w:tab w:val="right" w:pos="9000" w:leader="dot"/></w:tabs></w:pPr>'
        "</w:style>"
    )
    g = _gc(_p('<w:pStyle w:val="Dien"/>'), kieu)
    assert [(m.pos, m.leader) for m in g.moc] == [(9000, "dot")]


# ------------------------------------------------------------- fail closed


def test_GIA_TRI_HONG_lam_ca_W_SPACING_cua_doan_ve_KHONG_KHAI():
    g = _gc(_p('<w:spacing w:before="rất nhiều" w:line="360" w:lineRule="auto"/>'))
    assert (g.truoc, g.dong, g.luat_dong) == (0, 0, "")
    assert ("spacing/before", "rất nhiều") in g.khai, "thước đo vẫn phải thấy tệp khai gì"


def test_W_SPACING_HONG_KHONG_lam_cam_luon_W_IND_cua_cung_doan():
    """Ba phần tử độc lập: một `w:spacing` hỏng không nói gì về thụt lề."""
    g = _gc(_p('<w:spacing w:after="?"/><w:ind w:left="720"/>'))
    assert (g.sau, g.trai) == (0, 720)


def test_POS_HONG_lam_CA_NHOM_MOC_rong_vi_mot_moc_lech_keo_moc_sau_lech_theo():
    g = _gc(
        _p(
            '<w:tabs><w:tab w:val="left" w:pos="abc"/>'
            '<w:tab w:val="right" w:pos="9360" w:leader="dot"/></w:tabs>'
        )
    )
    assert g.moc == ()
    assert ("tabs", "2") in g.khai


def test_AUTOSPACING_BAT_bo_con_so_before_vi_Word_tu_tinh_khoang_do():
    assert _gc(_p('<w:spacing w:before="240" w:beforeAutospacing="1"/>')).truoc == 0


def test_AUTOSPACING_VAL_0_la_TAT_nen_con_so_before_van_duoc_dung():
    """Cùng bẫy `w:b w:val="0"`: "có thẻ" không phải "bật"."""
    assert _gc(_p('<w:spacing w:before="240" w:beforeAutospacing="0"/>')).truoc == 240
    assert _gc(_p('<w:spacing w:after="240" w:afterAutospacing="false"/>')).sau == 240


def test_DOAN_KHONG_KHAI_GI_khong_sinh_phan_tu_GIAN_CACH_nao():
    assert _mot("<w:p><w:r><w:t>Chữ trần</w:t></w:r></w:p>").gian_cach == ()


# -------------------------------- `noi_dung` và mọi thứ tra trên nó KHÔNG ĐỔI

_THAN_GIAN_CACH = (
    '<w:p><w:pPr><w:spacing w:before="120" w:after="240" w:line="360" w:lineRule="auto"/>'
    '<w:ind w:left="720" w:firstLine="360"/>'
    '<w:tabs><w:tab w:val="right" w:pos="9360" w:leader="dot"/></w:tabs></w:pPr>'
    "<w:r><w:t>Mức lương: </w:t></w:r>"
    "<w:r><w:tab/><w:t>20.000.000 đồng/tháng</w:t></w:r>"
    "</w:p>"
)
_THAN_TRAN = (
    "<w:p>"
    "<w:r><w:t>Mức lương: </w:t></w:r>"
    "<w:r><w:t>20.000.000 đồng/tháng</w:t></w:r>"
    "</w:p>"
)


def test_NOI_DUNG_va_NEO_va_LAM_SACH_y_HET_khi_bo_het_gian_cach():
    """Cột mốc của cả bản vá, cùng phép đo `test_doc_tai_lieu_dinh_dang` đã
    dùng cho `w:rPr`: thêm `w:spacing`/`w:ind`/`w:tabs` VÀ một `<w:tab/>` vào
    tệp KHÔNG được đổi một ký tự nào của `noi_dung`, cũng không đổi kết quả
    của bất cứ phép tra nào đang chạy trên nó."""
    co = doc("x.docx", _docx(_THAN_GIAN_CACH)).don_vi
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


# ------------------------------------------- đường ra khối bản thảo


def test_LAM_SACH_VAN_BAN_mang_GIAN_CACH_sang_khoi_khop_NGUYEN_VAN():
    don_vi = doc("x.docx", _docx(_THAN_GIAN_CACH)).don_vi
    chu_nguon = don_vi[0].noi_dung
    ra, _ = lam_sach_van_ban(
        {"muc": [{"ten": "Lương", "khoi": [{"noi_dung": chu_nguon}]}]},
        chu_nguon,
        [{"nhan": "A", "don_vi": don_vi}],
    )
    gc = ra["muc"][0]["khoi"][0]["gian_cach"]
    assert (gc["truoc"], gc["sau"], gc["dong"], gc["luat_dong"]) == (120, 240, 360, "auto")
    assert (gc["trai"], gc["dau_dong"]) == (720, 360)
    # Mốc tab ghép theo thứ tự: tab thứ nhất đi tới mốc thứ nhất, và offset
    # trỏ đúng chỗ `<w:tab/>` đứng — ngay sau dấu cách cuối "Mức lương: ".
    assert gc["tab"] == [{"o": len("Mức lương: "), "val": "right", "pos": 9360, "leader": "dot"}]


def test_KHOI_KHONG_KHOP_dong_nguon_nao_thi_KHONG_co_khoa_GIAN_CACH():
    """Mô hình gõ lại lệch một chữ → offset mốc tab đo trên chữ CŨ không được
    áp lên chữ MỚI: thà không có đường dẫn còn hơn một đường dẫn giữa từ."""
    don_vi = doc("x.docx", _docx(_THAN_GIAN_CACH)).don_vi
    ra, _ = lam_sach_van_ban(
        {"muc": [{"ten": "Lương", "khoi": [{"noi_dung": "Mức lương: theo thoả thuận"}]}]},
        " ".join(d.noi_dung for d in don_vi) + " theo thoả thuận",
        [{"nhan": "A", "don_vi": don_vi}],
    )
    assert "gian_cach" not in ra["muc"][0]["khoi"][0]


# ------------------------------------------------------- lưu rồi đọc lại


def test_LUU_ROI_DOC_LAI_ra_DUNG_GianCach_ban_dau():
    """Ranh giới lưu/đọc là chỗ căn lề từng mất một lần (xem `_hang_don_vi`):
    một vòng JSON phải trả về một giá trị BẰNG chính nó, không phải một giá
    trị "gần giống" mà `==` trả `False`."""
    goc = doc("x.docx", _docx(_THAN_GIAN_CACH)).don_vi[0].gian_cach
    assert _gian_cach_tu_hang([_hang_gian_cach(g) for g in goc]) == goc


def test_DONG_LUU_TRUOC_TRUONG_NAY_doc_ra_RONG_khong_doan_lai():
    assert _gian_cach_tu_hang(None) == ()
    assert _gian_cach_tu_hang("hỏng") == ()

