"""Định dạng chữ mức run (`w:rPr`) — quyết định 2026-09-18.

`test_doc_tai_lieu_cau_truc.py` khoá "đọc ra CHỖ"; file này khoá "đọc ra HÌNH
DẠNG của chữ": đậm, nghiêng, gạch chân, cỡ, phông — và, quan trọng ngang bằng,
KHOẢNG chữ nào mang hình dạng ấy.

Bốn điều không suy ra được từ hai file kia:

1. **`w:val="0"`/`"false"` TẮT một thuộc tính.** Một session trước đã báo "mọi
   đoạn đều bị in đậm" vì coi sự có mặt của `<w:b>` là bật. Word ghi "BỎ đậm"
   cho một run nằm trong kiểu in đậm bằng đúng `<w:b w:val="0"/>`, nên đây
   không phải ca hiếm mà là cách nói "không đậm" thông dụng nhất.
2. **Đậm đến TỪ KIỂU vẫn là đậm.** Một biểu mẫu in đậm bằng `w:rStyle`/
   `w:pStyle` không khai `w:b` ở đâu trong `document.xml`; đọc thẳng `w:rPr`
   sẽ dựng lại nó thành chữ thường.
3. **`noi_dung` KHÔNG ĐỔI MỘT KÝ TỰ.** Định dạng là những khoảng nằm CẠNH
   chuỗi, không phải thẻ nhét vào chuỗi — nếu không, `neo_du_kien.xac_minh`,
   `normalize` và `lam_sach_van_ban` cùng hỏng một lúc, và phép neo trích dẫn
   là bằng chứng của cả sản phẩm.
4. **Khoảng trỏ đúng chữ.** Một offset lệch in đậm nửa từ — trông như một lỗi
   của tài liệu gốc chứ không như một lỗi của KLAW.
"""

import zipfile
from io import BytesIO

from src.agents.nodes.hieu_tai_lieu import lam_sach_van_ban
from src.services.doc_tai_lieu import doc
from src.services.neo_du_kien import LyDoNeo, normalize, xac_minh

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


def _p(rpr: str, chu: str, ppr: str = "") -> str:
    """Một `w:p` MỘT run, `rpr` là phần bên trong `w:rPr` (rỗng = không có `w:rPr`)."""
    r = f"<w:r><w:rPr>{rpr}</w:rPr><w:t>{chu}</w:t></w:r>" if rpr else f"<w:r><w:t>{chu}</w:t></w:r>"
    return f"<w:p>{ppr}{r}</w:p>"


def _mot(than: str, kieu: str = ""):
    """Đơn vị ĐẦU TIÊN của một tài liệu chỉ có một đoạn."""
    return doc("x.docx", _docx(than, kieu)).don_vi[0]


# --------------------------------------------------------- khai TRỰC TIẾP


def test_DAM_truc_tiep_va_khoang_trung_khop_nguyen_van_doan():
    d = _mot(_p("<w:b/>", "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM"))
    assert d.noi_dung == "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM"
    (r,) = d.dinh_dang
    assert (r.dam, r.nghieng, r.gach) == (True, False, False)
    assert d.noi_dung[r.dau : r.cuoi] == d.noi_dung


def test_NGHIENG_va_GACH_CHAN_doc_duoc_rieng_nhau():
    d = _mot(_p('<w:i/><w:u w:val="single"/>', "Ký, ghi rõ họ tên"))
    (r,) = d.dinh_dang
    assert (r.dam, r.nghieng, r.gach) == (False, True, True)


def test_GACH_CHAN_val_none_la_KHONG_gach():
    """`w:u` mang KIỂU gạch, không phải cờ bật/tắt — `none` nghĩa là không có."""
    d = _mot(_p('<w:u w:val="none"/>', "Không gạch"))
    assert d.dinh_dang[0].gach is False


def test_CO_CHU_doc_ra_NUA_DIEM_dung_don_vi_cua_w_sz():
    d = _mot(_p('<w:sz w:val="28"/>', "Tiêu đề"))
    assert d.dinh_dang[0].co == 28


def test_PHONG_doc_tu_w_rFonts_ascii_GIU_NGUYEN_ten_nguon():
    d = _mot(_p('<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/>', "Điều 1"))
    assert d.dinh_dang[0].phong == "Times New Roman"


# ------------------------------------------------------------ `w:val` TẮT


def test_W_VAL_FALSE_TAT_dam_chu_KHONG_phai_bat():
    """Bẫy đã cắn một lần: có thẻ `<w:b>` KHÔNG có nghĩa là đậm."""
    for v in ("0", "false", "off"):
        d = _mot(_p(f'<w:b w:val="{v}"/>', "Chữ thường"))
        assert d.dinh_dang[0].dam is False, v
        # Vẫn KHAI — `eval.run_trung_thuc` chấm chính con chữ nguồn ghi, và
        # quy nó về một cờ bool rồi dựng lại thành "1" là nói sai điều tệp nói.
        assert d.dinh_dang[0].khai == (("b", v),)


def test_RUN_TAT_DAM_de_de_len_kieu_DANG_in_dam():
    """Đúng ca Word sinh ra `w:val="0"`: một run bỏ đậm trong một kiểu đậm."""
    than = '<w:p><w:pPr><w:pStyle w:val="DamHet"/></w:pPr>'
    than += '<w:r><w:t>Đậm theo kiểu</w:t></w:r>'
    than += '<w:r><w:rPr><w:b w:val="0"/></w:rPr><w:t> thường lại</w:t></w:r></w:p>'
    kieu = '<w:style w:type="paragraph" w:styleId="DamHet"><w:rPr><w:b/></w:rPr></w:style>'
    d = _mot(than, kieu)
    assert [(r.dam, d.noi_dung[r.dau : r.cuoi]) for r in d.dinh_dang] == [
        (True, "Đậm theo kiểu"),
        (False, " thường lại"),
    ]


# ------------------------------------------------------------- theo KIỂU


def test_DAM_den_tu_w_rStyle_qua_chuoi_basedOn():
    than = '<w:p><w:r><w:rPr><w:rStyle w:val="NhanManh"/></w:rPr><w:t>Đậm từ kiểu</w:t></w:r></w:p>'
    kieu = (
        '<w:style w:type="character" w:styleId="ChuGoc">'
        '<w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
        '<w:style w:type="character" w:styleId="NhanManh">'
        '<w:basedOn w:val="ChuGoc"/><w:rPr><w:i/></w:rPr></w:style>'
    )
    d = _mot(than, kieu)
    (r,) = d.dinh_dang
    # Trộn theo TỪNG thuộc tính: `i` của kiểu con, `b`/`sz` thừa kế kiểu cha.
    assert (r.dam, r.nghieng, r.co) == (True, True, 24)
    # Không khai gì TRỰC TIẾP — hai sự thật khác nhau, giữ riêng.
    assert r.khai == ()


def test_DINH_DANG_CHU_cua_DOAN_w_pPr_rPr_ap_cho_moi_run_cua_doan():
    than = _p("", "Cả đoạn in đậm", ppr="<w:pPr><w:rPr><w:b/></w:rPr></w:pPr>")
    assert _mot(than).dinh_dang[0].dam is True


def test_KIEU_KHONG_khai_gi_thi_run_thuong_KHONG_vao_bieu_dien():
    """Run không nói gì cả (không khai, không thừa kế) bị bỏ — phần lớn run
    của một tài liệu là loại này, giữ lại chỉ làm biểu diễn phình ra."""
    assert _mot(_p("", "Một dòng thường")).dinh_dang == ()


# ------------------------------------------------------- nhiều run một đoạn


def test_BA_RUN_KHAC_DINH_DANG_moi_khoang_tro_dung_chu_cua_no():
    than = (
        "<w:p>"
        '<w:r><w:rPr><w:b/></w:rPr><w:t>Họ và tên: </w:t></w:r>'
        '<w:r><w:rPr><w:i/><w:sz w:val="26"/></w:rPr><w:t>Nguyễn Văn A</w:t></w:r>'
        '<w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t> (đã ký)</w:t></w:r>'
        "</w:p>"
    )
    d = _mot(than)
    assert d.noi_dung == "Họ và tên: Nguyễn Văn A (đã ký)"
    assert [(d.noi_dung[r.dau : r.cuoi], r.dam, r.nghieng, r.gach, r.co) for r in d.dinh_dang] == [
        ("Họ và tên: ", True, False, False, 0),
        ("Nguyễn Văn A", False, True, False, 26),
        (" (đã ký)", False, False, True, 0),
    ]
    assert [r.so for r in d.dinh_dang] == [0, 1, 2]


def test_KHOANG_TRANG_hai_dau_doan_bi_STRIP_thi_offset_DICH_THEO():
    """`_chu` cắt khoảng trắng hai đầu; khoảng phải đo trên chuỗi ĐÃ cắt."""
    than = (
        "<w:p>"
        "<w:r><w:t>   </w:t></w:r>"
        '<w:r><w:rPr><w:b/></w:rPr><w:t>QUYẾT ĐỊNH</w:t></w:r>'
        "<w:r><w:t>  </w:t></w:r>"
        "</w:p>"
    )
    d = _mot(than)
    assert d.noi_dung == "QUYẾT ĐỊNH"
    dam = [r for r in d.dinh_dang if r.dam]
    assert [d.noi_dung[r.dau : r.cuoi] for r in dam] == ["QUYẾT ĐỊNH"]


def test_O_BANG_NHIEU_DOAN_offset_dich_theo_dau_cach_noi_hai_doan():
    than = (
        "<w:tbl><w:tr><w:tc>"
        + _p("<w:b/>", "TRƯỜNG ĐẠI HỌC PHENIKAA")
        + _p("<w:i/>", "Khoa Luật")
        + "</w:tc></w:tr></w:tbl>"
    )
    d = _mot(than)
    assert d.noi_dung == "TRƯỜNG ĐẠI HỌC PHENIKAA Khoa Luật"
    assert [(d.noi_dung[r.dau : r.cuoi], r.doan) for r in d.dinh_dang] == [
        ("TRƯỜNG ĐẠI HỌC PHENIKAA", 0),
        ("Khoa Luật", 1),
    ]


# ------------------------------- `noi_dung` và mọi thứ tra trên nó KHÔNG ĐỔI

_THAN_DINH_DANG = (
    "<w:p>"
    '<w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr><w:t>Mức lương: </w:t></w:r>'
    '<w:r><w:rPr><w:i/></w:rPr><w:t>20.000.000 đồng/tháng</w:t></w:r>'
    "</w:p>"
)
_THAN_TRAN = (
    "<w:p>"
    "<w:r><w:t>Mức lương: </w:t></w:r>"
    "<w:r><w:t>20.000.000 đồng/tháng</w:t></w:r>"
    "</w:p>"
)


def test_NOI_DUNG_va_NEO_va_LAM_SACH_y_HET_khi_bo_het_dinh_dang():
    """Cột mốc của cả bản vá: thêm `w:rPr` vào tệp KHÔNG được đổi một ký tự
    nào của `noi_dung`, cũng không đổi kết quả của bất cứ phép tra nào đang
    chạy trên nó — phép neo trích dẫn là bằng chứng của cả sản phẩm."""
    co = doc("x.docx", _docx(_THAN_DINH_DANG)).don_vi
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

    # `lam_sach_van_ban` chạy trên CHÍNH chuỗi đó: cùng vào, cùng ra, cùng số
    # đếm — kể cả phần thay giá trị bịa bằng `[…]`.
    van_ban = {
        "muc": [
            {
                "ten": "Lương",
                "khoi": [{"noi_dung": "Mức lương: 20.000.000 đồng/tháng và thưởng 5.000.000 đồng"}],
            }
        ]
    }
    goi_co = [{"nhan": "A", "don_vi": co}]
    goi_khong = [{"nhan": "A", "don_vi": khong}]
    nguon = " ".join(d.noi_dung for d in co)
    ra_co, dem_co = lam_sach_van_ban(van_ban, nguon, goi_co)
    ra_khong, dem_khong = lam_sach_van_ban(van_ban, nguon, goi_khong)
    assert dem_co == dem_khong
    assert [
        [k["noi_dung"] for k in m["khoi"]] for m in ra_co["muc"]
    ] == [[k["noi_dung"] for k in m["khoi"]] for m in ra_khong["muc"]]


def test_LAM_SACH_VAN_BAN_mang_dinh_dang_sang_khoi_khop_NGUYEN_VAN():
    """Đường từ `DonViVanBan.dinh_dang` ra khối bản thảo: khối nào tái hiện
    NGUYÊN VĂN một dòng nguồn thì mang theo định dạng của dòng đó."""
    don_vi = doc("x.docx", _docx(_THAN_DINH_DANG)).don_vi
    goi = [{"nhan": "A", "don_vi": don_vi}]
    chu_nguon = don_vi[0].noi_dung
    ra, _ = lam_sach_van_ban(
        {"muc": [{"ten": "Lương", "khoi": [{"noi_dung": chu_nguon}]}]},
        chu_nguon,
        goi,
    )
    khoi = ra["muc"][0]["khoi"][0]
    assert khoi["noi_dung"] == chu_nguon
    assert [(chu_nguon[k["dau"] : k["cuoi"]], k["dam"], k["nghieng"], k["co"]) for k in khoi["chu"]] == [
        ("Mức lương: ", True, False, 28),
        ("20.000.000 đồng/tháng", False, True, 0),
    ]


def test_KHOI_KHONG_KHOP_dong_nguon_nao_thi_KHONG_co_khoa_chu():
    """Mô hình gõ lại lệch một chữ → không tra được, và khoảng đo trên chữ CŨ
    không được áp lên chữ MỚI: thà không đậm còn hơn đậm nửa từ."""
    don_vi = doc("x.docx", _docx(_THAN_DINH_DANG)).don_vi
    ra, _ = lam_sach_van_ban(
        {"muc": [{"ten": "Lương", "khoi": [{"noi_dung": "Mức lương: theo thoả thuận"}]}]},
        " ".join(d.noi_dung for d in don_vi) + " theo thoả thuận",
        [{"nhan": "A", "don_vi": don_vi}],
    )
    assert "chu" not in ra["muc"][0]["khoi"][0]


# ------------------------------------------------- Ô BẢNG: cùng đường, cùng luật

# Ô trái của letterhead BM.ĐT.18.05: một ô, nhiều run khác định dạng. Trước bản
# vá này ba nơi vẽ đều tô CẢ ô một kiểu, nên đúng dòng chữ đậm của biểu mẫu chủ
# sở hữu ra màn hình thành chữ thường — trong khi CÙNG chữ ấy nằm ngoài bảng
# thì đậm đúng.
_O_TRAI_BA_RUN = (
    "<w:tc><w:p>"
    '<w:r><w:rPr><w:b/><w:sz w:val="26"/></w:rPr><w:t>TRƯỜNG ĐẠI HỌC PHENIKAA </w:t></w:r>'
    '<w:r><w:rPr><w:i/></w:rPr><w:t>TRƯỜNG CÔNG NGHỆ THÔNG TIN</w:t></w:r>'
    '<w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t> (đơn vị)</w:t></w:r>'
    "</w:p></w:tc>"
)
_O_TRAI_TRAN = (
    "<w:tc><w:p>"
    "<w:r><w:t>TRƯỜNG ĐẠI HỌC PHENIKAA </w:t></w:r>"
    "<w:r><w:t>TRƯỜNG CÔNG NGHỆ THÔNG TIN</w:t></w:r>"
    "<w:r><w:t> (đơn vị)</w:t></w:r>"
    "</w:p></w:tc>"
)
# Ô phải KHÔNG khai `w:rPr` nào — chỗ chứng minh "không khai thì không vẽ".
# Chữ của nó cố ý không mang số hiệu văn bản: `bo_nho._vuong_luoi_chan` bỏ CẢ
# mục khi thấy một số hiệu, và mục bị bỏ thì không còn khối nào để kiểm.
_O_PHAI = "<w:tc>" + _p("", "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM") + "</w:tc>"
_CHU_O_TRAI = "TRƯỜNG ĐẠI HỌC PHENIKAA TRƯỜNG CÔNG NGHỆ THÔNG TIN (đơn vị)"
_CHU_O_PHAI = "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM"


def _bang(o_trai: str) -> str:
    return f"<w:tbl><w:tr>{o_trai}{_O_PHAI}</w:tr></w:tbl>"


def _van_ban_bang() -> dict:
    """Một mục: một khối văn xuôi có giá trị BỊA (để phép làm sạch có việc
    thật) và một khối bảng tái hiện đúng hai ô nguồn (để `_khop_bang` thay
    bảng THẬT vào). Dựng lại mỗi lần gọi — không chia sẻ dict giữa hai lượt."""
    return {
        "muc": [
            {
                "ten": "Đầu trang",
                "khoi": [
                    {"noi_dung": "Đơn vị ban hành thu 9.999.999 đồng"},
                    {"noi_dung": "", "bang": [[_CHU_O_TRAI, _CHU_O_PHAI]]},
                ],
            }
        ]
    }


def test_O_BANG_BA_RUN_KHAC_DINH_DANG_ra_khoi_bang_voi_KHOANG_nguyen_ven():
    """Ba run khác định dạng trong MỘT ô đi hết đường tới khối bảng, mỗi
    khoảng vẫn trỏ đúng chữ của chính nó — đây là thứ ba nơi vẽ đọc."""
    don_vi = doc("x.docx", _docx(_bang(_O_TRAI_BA_RUN))).don_vi
    ra, _ = lam_sach_van_ban(
        _van_ban_bang(),
        " ".join(d.noi_dung for d in don_vi),
        [{"nhan": "A", "don_vi": don_vi}],
    )
    khoi = ra["muc"][0]["khoi"][1]
    assert khoi["bang"] == [[_CHU_O_TRAI, _CHU_O_PHAI]]
    assert [
        (_CHU_O_TRAI[k["dau"] : k["cuoi"]], k["dam"], k["nghieng"], k["gach"], k["co"])
        for k in khoi["chu_o"][0][0]
    ] == [
        ("TRƯỜNG ĐẠI HỌC PHENIKAA ", True, False, False, 26),
        ("TRƯỜNG CÔNG NGHỆ THÔNG TIN", False, True, False, 0),
        (" (đơn vị)", False, False, True, 0),
    ]
    # Ô không khai gì KHÔNG nhận một khoảng nào: chỗ tệp không nói gì thì
    # render giữ chữ thường, đúng luật của cả bản vá.
    assert khoi["chu_o"][0][1] == []


def test_O_BANG_NOI_DUNG_VA_NEO_VA_LAM_SACH_y_HET_khi_bo_het_dinh_dang():
    """Cột mốc của nhánh bảng, đúng phép so `test_NOI_DUNG_va_NEO_va_LAM_SACH`
    đã đặt cho văn xuôi: thêm `w:rPr` vào các ô KHÔNG đổi một ký tự nào của
    `noi_dung`, không đổi neo trích dẫn, không đổi kết quả làm sạch."""
    co = doc("x.docx", _docx(_bang(_O_TRAI_BA_RUN))).don_vi
    khong = doc("x.docx", _docx(_bang(_O_TRAI_TRAN))).don_vi

    assert [d.noi_dung for d in co] == [d.noi_dung for d in khong]
    assert [(d.trang, d.offset_dau, d.chi_so, d.bang) for d in co] == [
        (d.trang, d.offset_dau, d.chi_so, d.bang) for d in khong
    ]
    assert [normalize(d.noi_dung) for d in co] == [normalize(d.noi_dung) for d in khong]

    neo_co, neo_khong = xac_minh(_CHU_O_TRAI, co), xac_minh(_CHU_O_TRAI, khong)
    assert neo_co.ly_do is LyDoNeo.ok
    assert (neo_co.chi_so_don_vi, neo_co.trang, neo_co.offset_dau) == (
        neo_khong.chi_so_don_vi,
        neo_khong.trang,
        neo_khong.offset_dau,
    )

    nguon = " ".join(d.noi_dung for d in co)
    ra_co, dem_co = lam_sach_van_ban(_van_ban_bang(), nguon, [{"nhan": "A", "don_vi": co}])
    ra_khong, dem_khong = lam_sach_van_ban(_van_ban_bang(), nguon, [{"nhan": "A", "don_vi": khong}])

    def _tru_dinh_dang(v: dict) -> list:
        return [
            [{k: x for k, x in b.items() if k not in ("chu", "chu_o")} for b in m["khoi"]]
            for m in v["muc"]
        ]

    assert dem_co == dem_khong
    assert dem_co["gia_tri_lam_sach"] == 1  # phép làm sạch có việc thật để làm
    assert _tru_dinh_dang(ra_co) == _tru_dinh_dang(ra_khong)
    # Khác biệt DUY NHẤT là định dạng — và nó chỉ có mặt ở bản tệp có khai.
    assert ra_co["muc"][0]["khoi"][1]["chu_o"][0][0]
    assert "chu_o" not in ra_khong["muc"][0]["khoi"][1]
