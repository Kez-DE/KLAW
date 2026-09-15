"""Đọc tài liệu người dùng (spec 2026-09-15 §FR-001..FR-005, §FR-029/030).

File này khoá bốn điều Pha 1 phải đúng:

1. DOCX và PDF có lớp chữ đều ra `DonViVanBan`, và ĐƠN VỊ KHÔNG BỊ GỘP — mỗi
   đoạn, mỗi ô bảng là một đơn vị riêng. Đây là tiền đề của FR-010: một đoạn
   trích phải nằm gọn trong một đơn vị, y hệt cách `verify_tier1._tim_quote`
   so với TỪNG DÒNG `provisions` chứ không nối cả cây.
2. Dấu tiếng Việt đi qua nguyên vẹn. Mất dấu ở tầng đọc thì mọi phép tra chuỗi
   phía sau vô nghĩa, và nó hỏng im lặng.
3. Bốn nguyên nhân không đọc được (FR-003) là BỐN mã riêng, không gộp một nhãn
   — cùng lý do `Tier1Reason` giữ riêng ba chế độ hỏng của quote.
4. Quy đổi trang cho DOCX là một hằng số nêu tên được, vì DOCX không có khái
   niệm trang cố định (rủi ro R2 của kế hoạch).
"""

import zipfile
from io import BytesIO

import pytest

from src.services.doc_tai_lieu import (
    KY_TU_MOI_TRANG,
    DonViVanBan,
    KhongDocDuoc,
    LoaiHong,
    doc,
)

# ---------------------------------------------------------------- dựng tệp thử

_DOC_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body>{than}</w:body></w:document>"
)


def _p(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _bang(o: list[str]) -> str:
    tc = "".join(f"<w:tc>{_p(x)}</w:tc>" for x in o)
    return f"<w:tbl><w:tr>{tc}</w:tr></w:tbl>"


def _docx(than: str) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        z.writestr("word/document.xml", _DOC_XML.format(than=than))
    return buf.getvalue()


def _pdf(trang: list[str]) -> bytes:
    """PDF Type1/Helvetica tối thiểu. Chỉ ASCII: WinAnsi không mã được chữ Việt
    có dấu, nên nhánh dấu tiếng Việt được khoá bằng DOCX (test_DOCX_giu_dau)."""
    objs: list[bytes] = []
    noi_dung_ids = []
    for t in trang:
        ct = f"BT /F1 12 Tf 72 720 Td ({t}) Tj ET".encode("latin-1")
        objs.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(ct), ct))
        noi_dung_ids.append(len(objs))

    trang_ids = []
    for i in noi_dung_ids:
        objs.append(
            b"<< /Type /Page /Parent 999 0 R /MediaBox [0 0 612 792] /Contents %d 0 R "
            b"/Resources << /Font << /F1 998 0 R >> >> >>" % i
        )
        trang_ids.append(len(objs))

    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_id = len(objs)
    kids = b" ".join(b"%d 0 R" % i for i in trang_ids)
    objs.append(b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(trang_ids)))
    pages_id = len(objs)
    objs.append(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    catalog_id = len(objs)

    objs = [o.replace(b"999 0 R", b"%d 0 R" % pages_id).replace(b"998 0 R", b"%d 0 R" % font_id) for o in objs]

    ra = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for n, o in enumerate(objs, start=1):
        offsets.append(len(ra))
        ra += b"%d 0 obj\n" % n + o + b"\nendobj\n"
    xref = len(ra)
    ra += b"xref\n0 %d\n" % (len(objs) + 1)
    ra += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        ra += b"%010d 00000 n \n" % off
    ra += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objs) + 1,
        catalog_id,
        xref,
    )
    return bytes(ra)


def _pdf_khong_chu() -> bytes:
    """Một trang hợp lệ nhưng không có toán tử văn bản nào — bản scan trông như vậy."""
    return _pdf([]).replace(b"/Kids []", b"/Kids []")


# ---------------------------------------------------------------------- DOCX


def test_DOCX_moi_doan_la_mot_don_vi():
    t = doc("hd.docx", _docx(_p("Doan mot") + _p("Doan hai")))
    assert [d.noi_dung for d in t.don_vi] == ["Doan mot", "Doan hai"]
    assert [d.chi_so for d in t.don_vi] == [0, 1]


def test_DOCX_moi_o_bang_la_mot_don_vi_RIENG():
    """Gộp ô lại sẽ tạo ra vết ghép không có trong tài liệu, và một đoạn trích
    vắt qua hai ô sẽ khớp dù nó không nguyên văn ở đâu cả."""
    t = doc("hd.docx", _docx(_bang(["Muc luong", "20.000.000"])))
    assert [d.noi_dung for d in t.don_vi] == ["Muc luong", "20.000.000"]


def test_DOCX_giu_dau():
    t = doc("hd.docx", _docx(_p("Mức lương: 20.000.000 đồng/tháng")))
    assert t.don_vi[0].noi_dung == "Mức lương: 20.000.000 đồng/tháng"


def test_DOCX_bo_doan_rong():
    t = doc("hd.docx", _docx(_p("Co chu") + _p("") + _p("   ")))
    assert [d.noi_dung for d in t.don_vi] == ["Co chu"]


def test_DOCX_so_trang_quy_doi_theo_KY_TU_MOI_TRANG():
    than = "".join(_p("x" * 1000) for _ in range(7))  # 7000 ký tự
    t = doc("hd.docx", _docx(than))
    assert KY_TU_MOI_TRANG == 3000
    assert t.so_trang == 3  # ceil(7000 / 3000)


def test_DOCX_rong_la_khong_co_lop_chu():
    with pytest.raises(KhongDocDuoc) as e:
        doc("hd.docx", _docx(""))
    assert e.value.ly_do is LoaiHong.khong_co_lop_chu


# ----------------------------------------------------------------------- PDF


def test_PDF_doc_duoc_va_dem_dung_trang():
    t = doc("hd.pdf", _pdf(["Trang mot", "Trang hai"]))
    assert t.so_trang == 2
    assert [d.trang for d in t.don_vi] == [1, 2]
    assert "Trang mot" in t.don_vi[0].noi_dung


def test_PDF_KHONG_TRANG_NAO_la_tep_hong():
    """PDF 0 trang là tệp dị dạng, không phải bản scan.

    Trước khi có OCR, mọi PDF không rút được chữ đều rơi vào `khong_co_lop_chu`.
    Giờ hai ca đã tách: không có lớp chữ thì thử OCR, còn không dựng nổi một
    trang ảnh nào thì tệp hỏng — và hai câu trả lời cho người dùng khác nhau.
    Ca "scan đọc được" nằm ở `test_doc_tai_lieu_ocr.py`.
    """
    with pytest.raises(KhongDocDuoc) as e:
        doc("scan.pdf", _pdf_khong_chu())
    assert e.value.ly_do is LoaiHong.tep_hong


# ------------------------------------------------------------- bốn nguyên nhân


def test_dinh_dang_khong_ho_tro():
    """`.png` KHÔNG còn nằm ở đây — ảnh nay đọc được bằng OCR."""
    with pytest.raises(KhongDocDuoc) as e:
        doc("bang-tinh.xlsx", b"PK\x03\x04")
    assert e.value.ly_do is LoaiHong.dinh_dang_khong_ho_tro


def test_ANH_khong_con_bi_tu_choi_vi_DINH_DANG():
    """Người vừa chụp giấy tờ bằng điện thoại không được nghe "định dạng không
    hỗ trợ" — đó là câu trả lời sai cho việc họ vừa làm."""
    with pytest.raises(KhongDocDuoc) as e:
        doc("anh.png", b"\x89PNG\r\n\x1a\n")
    assert e.value.ly_do is not LoaiHong.dinh_dang_khong_ho_tro


def test_tep_hong_PDF():
    with pytest.raises(KhongDocDuoc) as e:
        doc("hd.pdf", b"khong phai pdf")
    assert e.value.ly_do is LoaiHong.tep_hong


def test_tep_hong_DOCX():
    with pytest.raises(KhongDocDuoc) as e:
        doc("hd.docx", b"khong phai zip")
    assert e.value.ly_do is LoaiHong.tep_hong


def test_BON_nguyen_nhan_la_BON_ma_rieng():
    assert len({LoaiHong.dinh_dang_khong_ho_tro, LoaiHong.tep_hong,
                LoaiHong.can_mat_khau, LoaiHong.khong_co_lop_chu}) == 4


def test_offset_dau_dung_trong_trang():
    t = doc("hd.docx", _docx(_p("Mot") + _p("Hai")))
    assert t.don_vi[0].offset_dau == 0
    assert t.don_vi[1].offset_dau == len("Mot") + 1


def test_DonViVanBan_bat_bien():
    d = DonViVanBan(chi_so=0, trang=1, offset_dau=0, noi_dung="x")
    with pytest.raises(Exception):
        d.noi_dung = "y"  # type: ignore[misc]
