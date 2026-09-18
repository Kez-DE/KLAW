"""Chốt cái thước `eval/run_trung_thuc.py` — điểm không được tụt trong im lặng.

Tệp mẫu dựng NGAY TRONG test chứ không lấy từ `eval/datasets/`: tệp .docx ở đó
là ĐẦU RA (bị .gitignore), nên một máy vừa clone về không có tệp nào và test sẽ
xanh vì không đo gì. Quan trọng hơn: cả tập mẫu hiện có chỉ khai `w:p`/`w:tbl`,
không tệp nào khai đường viền, chiều cao hàng, `w:rPr`, lề trang hay ảnh — đo
trên chúng thì mọi mục "CHƯA CÀI" ăn 0 mà không ai chứng minh được là tại bộ
đọc chứ không phải tại nguồn im lặng. Tệp dưới đây khai ĐỦ CẢ MƯỜI MỤC, nên mỗi
số 0 là một lời khẳng định có bằng chứng.

Bốn thứ test này gác:
* điểm của mục đã cài không tụt (cấu trúc, căn lề, có-nét-hay-không của bảng,
  chiều cao hàng, định dạng chữ và giãn cách/thụt lề đang 100%);
* danh sách mục CHƯA CÀI không đổi lặng lẽ — cài xong một mục thì test này ĐỎ,
  và người cài phải sửa con số ở đây. Đó chính là điều muốn: một cái thước đổi
  giá trị mà không ai ký tên thì không gác được gì;
* `vien_bang_co_net` phân biệt đúng HAI ca render làm được — bảng bố cục khai
  `nil` với bảng lấy viền từ `w:tblStyle` — vì đó là chỗ duy nhất chân lý phải
  tự đi chuỗi `w:basedOn`, và đi sai thì thước trừ điểm một câu bộ đọc trả lời
  đúng;
* `dinh_dang_run` khớp CẢ trong ô bảng, nơi khoá chân lý có thêm một chặng
  `p{j}` cho từng `w:p` của ô. Tệp mẫu trên không có run nào khai `w:rPr`
  trong bảng, nên một lỗi đánh khoá ở đó sẽ đi qua nó mà không ai thấy.
"""

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from eval.run_trung_thuc import chay, dac_ta_nguon

_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

# Một trang giấy tí hon nhưng khai đủ mười mục: đoạn căn giữa in đậm có giãn
# cách và thụt lề, một bảng hai cột có lưới + viền + chiều cao hàng + ô căn
# phải + ô gộp hai cột, lề trang, và một tấm ảnh nhúng.
_THAN = (
    '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="120" w:after="240"/>'
    '<w:ind w:firstLine="720"/></w:pPr>'
    '<w:r><w:rPr><w:b/><w:sz w:val="28"/></w:rPr><w:t>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</w:t></w:r>'
    '<w:r><w:drawing/></w:r></w:p>'
    '<w:tbl><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4"/>'
    '<w:bottom w:val="single" w:sz="4"/></w:tblBorders></w:tblPr>'
    '<w:tblGrid><w:gridCol w:w="4000"/><w:gridCol w:w="6000"/></w:tblGrid>'
    '<w:tr><w:trPr><w:trHeight w:val="567" w:hRule="atLeast"/></w:trPr>'
    '<w:tc><w:tcPr><w:tcBorders><w:right w:val="single" w:sz="4"/></w:tcBorders></w:tcPr>'
    '<w:p><w:pPr><w:jc w:val="right"/></w:pPr><w:r><w:t>Số: 01/QĐ</w:t></w:r></w:p></w:tc>'
    '<w:tc><w:p><w:r><w:t>Hà Nội, ngày 18 tháng 9</w:t></w:r></w:p></w:tc></w:tr>'
    '<w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr>'
    '<w:p><w:r><w:t>Người lập biểu</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
    '<w:sectPr><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1701"/></w:sectPr>'
)

# Mục → (số dữ kiện nguồn KHAI, điểm hôm nay). Nguồn khai > 0 ở CẢ MƯỜI mục:
# một số 0 chỉ có nghĩa khi bên kia thật sự có gì để đo.
_HOM_NAY = {
    "cau_truc": (6, 1.0),
    "vien_bang_co_net": (1, 1.0),
    "vien_bang_tung_canh": (3, 0.0),
    "chieu_cao_hang": (1, 1.0),
    "chieu_cao_hang_hrule": (1, 0.0),
    "can_le": (2, 1.0),
    # Cài 2026-09-18 (`DonViVanBan.dinh_dang`): 0% → 100% trên tệp này. Hai dữ
    # kiện ở đây là `w:b` không `w:val` và `w:sz` — hai HÌNH DẠNG khác nhau
    # (thẻ rỗng nghĩa là bật, thẻ mang số), không phải hai lần cùng một ca.
    "dinh_dang_run": (2, 1.0),
    # Cài 2026-09-18 (`DonViVanBan.gian_cach`): 0% → 100% trên tệp này. Ba dữ
    # kiện là `w:spacing/@w:before`, `@w:after` và `w:ind/@w:firstLine` — hai
    # phần tử khác nhau, nên một lỗi chỉ đọc `w:spacing` không đi lọt.
    "gian_cach_thut_le": (3, 1.0),
    "le_trang": (4, 0.0),
    "media": (2, 0.0),
}
_CHUA_CAI = {
    "vien_bang_tung_canh",
    "chieu_cao_hang_hrule",
    "le_trang",
    "media",
}


def _docx(duong: Path) -> Path:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", f"<w:document {_NS}><w:body>{_THAN}</w:body></w:document>")
        z.writestr("word/media/anh1.png", b"\x89PNG\r\n\x1a\n")
    duong.write_bytes(buf.getvalue())
    return duong


def test_diem_tung_muc_KHONG_TUT_va_muc_chua_cai_KHONG_DOI_LANG_LE(tmp_path):
    ket = chay([_docx(tmp_path / "bieu-mau-du-tam-muc.docx")])
    muc = ket["tong_hop"]

    assert {m for m, v in muc.items() if v["chua_cai"]} == _CHUA_CAI
    for ten, (khai, diem) in _HOM_NAY.items():
        assert muc[ten]["khai"] == khai, f"{ten}: nguồn khai khác trước — tệp mẫu đổi thì mọi số dưới đây vô nghĩa"
        assert muc[ten]["diem"] == pytest.approx(diem), ten
    assert ket["tong"] == pytest.approx(6 / 10)


def test_MAT_TOA_DO_BANG_thi_diem_cau_truc_TUT(tmp_path):
    """Cái thước phải BIẾT ĐAU: bỏ hết bảng khỏi tệp thì cấu trúc nguồn khai
    vẫn thế mà bộ đọc không dựng lại được — không tụt nghĩa là thước gãy."""
    goc = chay([_docx(tmp_path / "co-bang.docx")])
    assert goc["tong_hop"]["cau_truc"]["diem"] == pytest.approx(1.0)

    hong = tmp_path / "mat-bang.docx"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        # Bảng bọc trong `w:sdt` — bộ đọc duyệt con TRỰC TIẾP của `w:body` nên
        # mất toạ độ và phải lùi về duyệt phẳng, đúng ca hỏng thật đã đo.
        than = _THAN.replace("<w:tbl>", "<w:sdt><w:sdtContent><w:tbl>").replace(
            "</w:tbl>", "</w:tbl></w:sdtContent></w:sdt>"
        )
        z.writestr("word/document.xml", f"<w:document {_NS}><w:body>{than}</w:body></w:document>")
    hong.write_bytes(buf.getvalue())

    assert chay([hong])["tong_hop"]["cau_truc"]["diem"] < 1.0


# `TableGrid` KHÔNG khai viền nào trong `document.xml` — chỉ `w:tblStyle`, và ở
# đây còn qua một chặng `w:basedOn` nữa. Chân lý phải tự đi chuỗi đó, vì bỏ nó
# thì bảng có viền đọc thành không viền và bộ đọc bị trừ điểm oan.
_STYLES = (
    f"<w:styles {_NS}>"
    '<w:style w:type="table" w:styleId="TableGrid"><w:tblPr><w:tblBorders>'
    '<w:top w:val="single" w:sz="4"/><w:insideH w:val="single" w:sz="4"/>'
    "</w:tblBorders></w:tblPr></w:style>"
    '<w:style w:type="table" w:styleId="BangCon"><w:basedOn w:val="TableGrid"/></w:style>'
    "</w:styles>"
)

# Hai ca DUY NHẤT mà ba nơi vẽ bảng phân biệt được: bảng bố cục khai `nil`
# (khối quốc hiệu, ô ký) và bảng lấy viền từ kiểu.
_HAI_BANG = (
    '<w:tbl><w:tblPr><w:tblBorders><w:top w:val="nil"/><w:left w:val="nil"/>'
    '<w:bottom w:val="nil"/><w:right w:val="nil"/></w:tblBorders></w:tblPr>'
    "<w:tr><w:tc><w:p><w:r><w:t>BỘ GIÁO DỤC VÀ ĐÀO TẠO</w:t></w:r></w:p></w:tc>"
    "<w:tc><w:p><w:r><w:t>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    '<w:tbl><w:tblPr><w:tblStyle w:val="BangCon"/></w:tblPr>'
    "<w:tr><w:tc><w:p><w:r><w:t>STT</w:t></w:r></w:p></w:tc>"
    "<w:tc><w:p><w:r><w:t>Nội dung</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
)


def test_VIEN_CO_NET_phan_biet_bang_BO_CUC_voi_bang_lay_vien_TU_KIEU(tmp_path):
    """Mục đo được của viền chỉ đáng tin khi nó trả lời KHÁC NHAU cho hai ca —
    `nil` và `w:tblStyle` — mà cả ba nơi vẽ bảng thật sự phân biệt được."""
    duong = tmp_path / "hai-kieu-vien.docx"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", f"<w:document {_NS}><w:body>{_HAI_BANG}</w:body></w:document>")
        z.writestr("word/styles.xml", _STYLES)
    duong.write_bytes(buf.getvalue())

    # Chốt CHÂN LÝ trước: "khớp 2/2" của hai bảng cùng một giá trị chỉ là đoán
    # trúng một hằng số hai lần.
    assert dac_ta_nguon(duong.read_bytes())["vien_bang_co_net"] == {"bang0": "khong", "bang1": "co"}

    muc = chay([duong])["tong_hop"]["vien_bang_co_net"]
    assert (muc["khai"], muc["khop"]) == (2, 2)


# Ô bảng: khoá chân lý là `bang{b}/o{h},{c}/p{j}/run{k}/{ten}` — thêm một chặng
# `p{j}` mà đoạn thân bài không có. Đoạn thứ hai của ô để `j` khác 0 ở ít nhất
# một dữ kiện, vì `p0` khớp cả khi bộ đọc quên hẳn chỉ số đoạn.
_BANG_CO_DINH_DANG = (
    "<w:tbl><w:tr><w:tc>"
    '<w:p><w:r><w:rPr><w:b/><w:sz w:val="26"/></w:rPr><w:t>TRƯỜNG ĐẠI HỌC</w:t></w:r></w:p>'
    '<w:p><w:r><w:rPr><w:i/><w:rFonts w:ascii="Times New Roman"/></w:rPr><w:t>Khoa Luật</w:t></w:r></w:p>'
    "</w:tc><w:tc>"
    '<w:p><w:r><w:rPr><w:b w:val="0"/></w:rPr><w:t>Số: 01/QĐ</w:t></w:r>'
    '<w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t> gạch chân</w:t></w:r></w:p>'
    "</w:tc></w:tr></w:tbl>"
)


def test_DINH_DANG_RUN_khop_ca_trong_O_BANG_ke_ca_khi_w_val_TAT(tmp_path):
    """`w:rPr` trong ô bảng phải khớp đúng toạ độ `p{j}/run{k}` của nó, và
    `w:b w:val="0"` phải đi qua nguyên vẹn: bộ đọc quy nó về một cờ bool rồi
    dựng lại thành `"1"` sẽ ra chữ đậm ở đúng chỗ tệp nói KHÔNG đậm."""
    duong = tmp_path / "bang-co-dinh-dang.docx"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr(
            "word/document.xml",
            f"<w:document {_NS}><w:body>{_BANG_CO_DINH_DANG}</w:body></w:document>",
        )
    duong.write_bytes(buf.getvalue())

    # Chốt CHÂN LÝ trước — "khớp 6/6" không nói gì nếu chân lý đọc sai chỗ.
    assert dac_ta_nguon(duong.read_bytes())["dinh_dang_run"] == {
        "bang0/o0,0/p0/run0/b": "1",
        "bang0/o0,0/p0/run0/sz": "26",
        "bang0/o0,0/p1/run0/i": "1",
        "bang0/o0,0/p1/run0/rFonts": "Times New Roman",
        "bang0/o0,1/p0/run0/b": "0",
        "bang0/o0,1/p0/run1/u": "single",
    }

    muc = chay([duong])["tong_hop"]["dinh_dang_run"]
    assert (muc["khai"], muc["khop"]) == (6, 6)


# Cùng chặng `p{j}` mà `dinh_dang_run` đã gác, nhưng cho một phần tử ở cấp
# ĐOẠN chứ không cấp run: khoá là `bang{b}/o{h},{c}/p{j}/{ten}`. Đoạn thứ hai
# của ô để `j` khác 0, vì `p0` khớp cả khi bộ đọc quên hẳn chỉ số đoạn.
_BANG_CO_GIAN_CACH = (
    "<w:tbl><w:tr><w:tc>"
    '<w:p><w:pPr><w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
    "<w:r><w:t>TRƯỜNG ĐẠI HỌC</w:t></w:r></w:p>"
    '<w:p><w:pPr><w:ind w:hanging="426"/>'
    '<w:tabs><w:tab w:val="right" w:pos="9360" w:leader="dot"/></w:tabs></w:pPr>'
    "<w:r><w:t>Khoa Luật</w:t></w:r></w:p>"
    "</w:tc><w:tc>"
    '<w:p><w:pPr><w:spacing w:after="0"/></w:pPr><w:r><w:t>Số: 01/QĐ</w:t></w:r></w:p>'
    "</w:tc></w:tr></w:tbl>"
)


def test_GIAN_CACH_khop_ca_trong_O_BANG_theo_dung_toa_do_tung_DOAN(tmp_path):
    """`w:spacing`/`w:ind`/`w:tabs` trong ô bảng phải khớp đúng toạ độ `p{j}`
    của nó, và `w:after="0"` phải đi qua NGUYÊN VĂN: bộ đọc quy nó về "không
    khai" rồi bỏ khoá sẽ mất đúng dữ kiện tệp nói "không có khoảng trống"."""
    duong = tmp_path / "bang-co-gian-cach.docx"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr(
            "word/document.xml",
            f"<w:document {_NS}><w:body>{_BANG_CO_GIAN_CACH}</w:body></w:document>",
        )
    duong.write_bytes(buf.getvalue())

    # Chốt CHÂN LÝ trước — "khớp 5/5" không nói gì nếu chân lý đọc sai chỗ.
    assert dac_ta_nguon(duong.read_bytes())["gian_cach_thut_le"] == {
        "bang0/o0,0/p0/spacing/line": "360",
        "bang0/o0,0/p0/spacing/lineRule": "auto",
        "bang0/o0,0/p1/ind/hanging": "426",
        "bang0/o0,0/p1/tabs": "1",
        "bang0/o0,1/p0/spacing/after": "0",
    }

    muc = chay([duong])["tong_hop"]["gian_cach_thut_le"]
    assert (muc["khai"], muc["khop"]) == (5, 5)
