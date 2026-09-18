"""Chốt cái thước `eval/run_trung_thuc.py` — điểm không được tụt trong im lặng.

Tệp mẫu dựng NGAY TRONG test chứ không lấy từ `eval/datasets/`: tệp .docx ở đó
là ĐẦU RA (bị .gitignore), nên một máy vừa clone về không có tệp nào và test sẽ
xanh vì không đo gì. Quan trọng hơn: cả tập mẫu hiện có chỉ khai `w:p`/`w:tbl`,
không tệp nào khai đường viền, chiều cao hàng, `w:rPr`, lề trang hay ảnh — đo
trên chúng thì sáu mục "CHƯA CÀI" ăn 0 mà không ai chứng minh được là tại bộ
đọc chứ không phải tại nguồn im lặng. Tệp dưới đây khai ĐỦ CẢ TÁM MỤC, nên mỗi
số 0 là một lời khẳng định có bằng chứng.

Hai thứ test này gác:
* điểm của mục đã cài không tụt (cấu trúc, căn lề đang 100%);
* danh sách mục CHƯA CÀI không đổi lặng lẽ — cài xong một mục thì test này ĐỎ,
  và người cài phải sửa con số ở đây. Đó chính là điều muốn: một cái thước đổi
  giá trị mà không ai ký tên thì không gác được gì.
"""

import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from eval.run_trung_thuc import chay

_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

# Một trang giấy tí hon nhưng khai đủ tám mục: đoạn căn giữa in đậm có giãn
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

# Mục → (số dữ kiện nguồn KHAI, điểm hôm nay). Nguồn khai > 0 ở CẢ TÁM mục:
# một số 0 chỉ có nghĩa khi bên kia thật sự có gì để đo.
_HOM_NAY = {
    "cau_truc": (6, 1.0),
    "vien_bang": (3, 0.0),
    "chieu_cao_hang": (1, 0.0),
    "can_le": (2, 1.0),
    "dinh_dang_run": (2, 0.0),
    "gian_cach_thut_le": (3, 0.0),
    "le_trang": (4, 0.0),
    "media": (2, 0.0),
}
_CHUA_CAI = {"vien_bang", "chieu_cao_hang", "dinh_dang_run", "gian_cach_thut_le", "le_trang", "media"}


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
    assert ket["tong"] == pytest.approx(2 / 8)


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
