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

from src.services.doc_tai_lieu import doc

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
