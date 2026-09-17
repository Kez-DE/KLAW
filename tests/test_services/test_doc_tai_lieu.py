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
from pathlib import Path

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


def _p_jc(text: str, val: str) -> str:
    """Đoạn văn CĂN LỀ TRỰC TIẾP (`w:pPr/w:jc`, Phase 9 U5)."""
    return f'<w:p><w:pPr><w:jc w:val="{val}"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'


def _p_kieu(text: str, style_id: str) -> str:
    """Đoạn văn KHÔNG căn lề trực tiếp, chỉ mang `w:pStyle` — căn lề (nếu có)
    phải suy ra từ chính kiểu đó (Phase 9 U5)."""
    return f'<w:p><w:pPr><w:pStyle w:val="{style_id}"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'


def _bang(o: list[str]) -> str:
    tc = "".join(f"<w:tc>{_p(x)}</w:tc>" for x in o)
    return f"<w:tbl><w:tr>{tc}</w:tr></w:tbl>"


def _tc_nhip(text: str, nhip: int | None = None) -> str:
    """Một `<w:tc>`, có gộp `w:gridSpan` khi `nhip` được cho (Phase 11 R6)."""
    pr = f'<w:tcPr><w:gridSpan w:val="{nhip}"/></w:tcPr>' if nhip else ""
    return f"<w:tc>{pr}{_p(text)}</w:tc>"


def _bang_luoi(grid: list[int], hang: list[list[tuple[str, int | None]]]) -> str:
    """`<w:tbl>` có khai `w:tblGrid` (Phase 11 R1) và tuỳ chọn `w:gridSpan`
    theo từng ô `(chữ, nhịp | None)` (Phase 11 R6)."""
    luoi = "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in grid) + "</w:tblGrid>"
    rows = "".join("<w:tr>" + "".join(_tc_nhip(t, n) for t, n in hg) + "</w:tr>" for hg in hang)
    return f"<w:tbl>{luoi}{rows}</w:tbl>"


def _styles_xml(kieu: list[tuple[str, str | None, str | None]]) -> str:
    """`[(styleId, jc|None, basedOn|None), …]` → `word/styles.xml` tối thiểu."""
    than = "".join(
        f'<w:style w:type="paragraph" w:styleId="{sid}">'
        + (f'<w:basedOn w:val="{cha}"/>' if cha else "")
        + (f'<w:pPr><w:jc w:val="{jc}"/></w:pPr>' if jc else "")
        + "</w:style>"
        for sid, jc, cha in kieu
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"{than}</w:styles>"
    )


def _docx(than: str, styles: str | None = None) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        z.writestr("word/document.xml", _DOC_XML.format(than=than))
        if styles is not None:
            z.writestr("word/styles.xml", styles)
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


# ────────────────────────── tỉ lệ cột / nhịp gộp (Phase 11 R1/R6)


def test_DOCX_ti_le_cot_tu_tblGrid():
    """`w:tblGrid` khai lưới → `bang_ti_le` mang đúng % mỗi cột, GIỐNG NHAU
    trên mọi ô của cùng bảng — cùng số đo brief cho letterhead BM.ĐT.18.05
    (4616/5755 twips → 45/55)."""
    than = _bang_luoi([4616, 5755], [[("A", None), ("B", None)]])
    t = doc("hd.docx", _docx(than))
    assert [d.bang_ti_le for d in t.don_vi] == [(45, 55), (45, 55)]


def test_DOCX_khong_tblGrid_ti_le_rong():
    """Bảng không khai `w:tblGrid` → `bang_ti_le` rỗng — không suy đoán tỉ lệ,
    phía render tự quyết định chia đều (R1)."""
    t = doc("hd.docx", _docx(_bang(["A", "B"])))
    assert [d.bang_ti_le for d in t.don_vi] == [(), ()]


def test_DOCX_gridSpan_dat_dung_cot_luoi_that():
    """Một ô gộp `w:gridSpan="2"` (Phase 11 R6, đo thật trên BM.ĐT.18.11: nhãn
    "Tổng" gộp 2 cột) phải đẩy CỘT LƯỚI của ô kế tiếp trong cùng hàng — ô sau
    đứng ở cột 2, không phải cột 1 (số thứ tự ô thứ mấy, cách đọc CŨ trước
    Phase 11)."""
    than = _bang_luoi(
        [1000, 1000, 1000, 1000],
        [
            [("TT", None), ("Tiêu chí", None), ("Điểm tối đa", None), ("Điểm đánh giá", None)],
            [("Tổng", 2), ("10", None)],
        ],
    )
    t = doc("hd.docx", _docx(than))
    theo_chu = {d.noi_dung: (d.bang, d.bang_nhip) for d in t.don_vi}
    assert theo_chu["Tổng"] == ((0, 1, 0), 2), "Tổng bắt đầu ở cột 0, chiếm 2 cột"
    assert theo_chu["10"] == ((0, 1, 2), 1), "10 đứng ở cột lưới THẬT (2), không phải cột 1"


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


# ------------------------------------------------------ căn lề (Phase 9 U5)


def test_DOCX_can_le_truc_tiep():
    """`w:pPr/w:jc` khai TRỰC TIẾP trên đoạn — đường ngắn nhất, phải đọc đúng
    cả ba giá trị quan sát được trên form thật (BM.ĐT.18.11): `center` (quốc
    hiệu/tiêu ngữ/tiêu đề), vắng mặt (dòng trường tự do, mặc định `trai`), và
    `right` (dòng "Hà Nội, ngày … tháng … năm …" phía trên khối ký)."""
    than = _p_jc("CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM", "center") + _p(
        "Họ và tên sinh viên: …………………"
    ) + _p_jc("Hà Nội, ngày ..... tháng .... năm 20...", "right")
    t = doc("hd.docx", _docx(than))
    assert [d.can_le for d in t.don_vi] == ["giua", "trai", "phai"]


def test_DOCX_can_le_theo_kieu_khi_khong_co_truc_tiep():
    """Đoạn KHÔNG khai `jc` trực tiếp, chỉ mang `w:pStyle` trỏ tới một kiểu tự
    khai `center` — phải đọc ra `giua`, không phải mặc định `trai`: đây chính
    là ca coordinator cảnh báo ("một tài liệu căn giữa bằng KIỂU mà đọc thẳng
    `jc` trên `w:p` sẽ luôn ra trái, sai với chính tài liệu đó")."""
    styles = _styles_xml([("TieuDe", "center", None)])
    than = _p_kieu("PHIẾU ĐÁNH GIÁ", "TieuDe")
    t = doc("hd.docx", _docx(than, styles))
    assert t.don_vi[0].can_le == "giua"


def test_DOCX_can_le_theo_kieu_qua_chuoi_basedOn():
    """Kiểu của đoạn (`Con`) không tự khai `jc`, nhưng KẾ THỪA (`w:basedOn`)
    một kiểu cha (`Goc`) có khai — phải giải hết chuỗi mới ra `giua`, không
    dừng ở kiểu gần nhất."""
    styles = _styles_xml([("Goc", "center", None), ("Con", None, "Goc")])
    than = _p_kieu("ĐỘC LẬP - TỰ DO - HẠNH PHÚC", "Con")
    t = doc("hd.docx", _docx(than, styles))
    assert t.don_vi[0].can_le == "giua"


def test_DOCX_khong_ro_can_le_thi_ve_trai():
    """Không `jc` trực tiếp, không `pStyle`, hoặc `pStyle` trỏ tới một kiểu
    không tồn tại — mọi ca không xác định được đều về `trai`, không suy đoán
    thêm gì ngoài những gì tệp thật sự khai."""
    than = _p("Trường tự do") + _p_kieu("Đoạn kiểu lạ", "KhongTonTai")
    t = doc("hd.docx", _docx(than, _styles_xml([("Khac", "center", None)])))
    assert [d.can_le for d in t.don_vi] == ["trai", "trai"]


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


# ─────────────────── corpus thật — không form nào ra toàn "giua" (Phase 9 U5)
#
# Review task quality [Medium] — báo cáo Phase 9 chỉ có một bảng đo TAY, không
# phải một phép kiểm CAM KẾT lại được. `doc_tai_lieu.doc()` là hàm THUẦN, 0
# token (không gọi mô hình), nên chạy được thẳng trong `pytest` — bỏ qua an
# toàn (không fail CI) khi thư mục kho mẫu không có trên máy đang chạy.

_KHO_MAU = Path.home() / "giấy tờ thực tập"
_CORPUS_CO_MAT = _KHO_MAU.is_dir()
_TEP_KHO_MAU = [
    "BM.M05. Giay tiep nhan thuc hanh. thuc tap (1).docx",
    "BM.ĐT.18.03. Đơn đăng ký đi thực tập tốt nghiệp Ver 02.docx",
    "BM.ĐT.18.05. Kế hoạch thực tập tại cơ sở Ver 02.docx",
    "BM.ĐT.18.11. Phiếu đánh giá quá trình thực tập tốt nghiệp của sinh viên tại cơ sở thực tập Ver 02 (1).docx",
    "phiếu đánh giá thực tập công nghiệp.docx",
    "Evaluation Form.docx",
]


@pytest.mark.skipif(not _CORPUS_CO_MAT, reason="kho mẫu ngoài repo không có trên máy này")
@pytest.mark.parametrize("ten_tep", _TEP_KHO_MAU)
def test_corpus_khong_form_nao_ra_toan_giua(ten_tep):
    """Thất bại an toàn của một mặc định căn giữa quá tay: nếu `_can_le_doan`/
    `_kieu_can_le` hỏng theo hướng "cứ thấy `w:jc` là căn giữa" hay tương tự,
    dấu hiệu là CẢ tài liệu ra `giua` — không form thật nào của kho mẫu có
    hình dạng đó (mọi form đều có ít nhất một dòng trường tự do/trái)."""
    duong_dan = _KHO_MAU / ten_tep
    if not duong_dan.exists():
        pytest.skip(f"không thấy {ten_tep} trong kho mẫu")
    t = doc(duong_dan.name, duong_dan.read_bytes())
    can_le = [d.can_le for d in t.don_vi if d.noi_dung]
    assert can_le, "tài liệu phải đọc ra ít nhất một đơn vị"
    assert any(c != "giua" for c in can_le), f"{ten_tep}: mọi đơn vị ra 'giua' — mặc định căn giữa quá tay"


# ──────────────────── corpus thật — tỉ lệ cột (Phase 11 R1), ghim đúng số đo
#
# `.sdd/phase-11-brief.md` R1 — số đo TRỰC TIẾP trên `word/document.xml` của
# BM.ĐT.18.05: letterhead `[4616, 5755]` = 45/55, bảng kế hoạch `[618, 1352,
# 2677, 3052, 1363]` = 7/15/30/34/15 (làm tròn ĐỘC LẬP từng cột, không dồn
# phần dư — tổng ra 101, không phải 100, đúng số đo, xem `_ti_le_luoi`), bảng
# ký `[4238, 4712]` = 47/53. Ghim để một bản vá sau này không âm thầm đổi
# công thức quy đổi mà không ai biết.


@pytest.mark.skipif(not _CORPUS_CO_MAT, reason="kho mẫu ngoài repo không có trên máy này")
def test_corpus_ti_le_cot_BM_DT_18_05():
    ten_tep = "BM.ĐT.18.05. Kế hoạch thực tập tại cơ sở Ver 02.docx"
    duong_dan = _KHO_MAU / ten_tep
    if not duong_dan.exists():
        pytest.skip(f"không thấy {ten_tep} trong kho mẫu")
    t = doc(duong_dan.name, duong_dan.read_bytes())
    ti_le_theo_bang: dict[int, tuple[int, ...]] = {}
    for d in t.don_vi:
        if d.bang is not None:
            ti_le_theo_bang.setdefault(d.bang[0], d.bang_ti_le)
    assert ti_le_theo_bang == {
        0: (45, 55),
        1: (7, 15, 30, 34, 15),
        2: (47, 53),
    }
