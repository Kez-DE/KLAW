r"""Parser văn bản hợp nhất (VBHN) — giải footnote ra bản đồ sửa đổi.

Mọi test ở đây OFFLINE: dựng `.docx` tổng hợp bằng `zipfile` ngay trong test,
theo ĐÚNG hình dạng OOXML đo được trên `18/VBHN-VPQH` thật (xem
`.superpowers/sdd/congbao-ban-do-sua-doi-report.md`). Không mạng, không fixture
nhị phân trong git.

Ba cạm bẫy khảo sát đã sập, mỗi cái một test — cả ba đều sai ÂM THẦM:
  1. `<w:t[^>]*>` khớp cả `<w:tab>` → "0 Điều" trên file 220 Điều.
  2. Số footnote dính liền số khoản: `"1." + <sup>4</sup>` → đọc thành "1.4".
  3. ZIP của congbao có thể dùng `\` làm phân cách → `KeyError`.
"""

import zipfile
from datetime import date
from io import BytesIO

from src.services.vbhn_parser import doc_sua_doi

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _r(*, text: str = "", sup: bool = False, fn: str | None = None) -> str:
    """Một `<w:r>`. `sup` = superscript, `fn` = mang `<w:footnoteReference>`."""
    rpr = "<w:rPr><w:vertAlign w:val='superscript'/></w:rPr>" if sup else ""
    body = f"<w:t xml:space='preserve'>{text}</w:t>" if text else ""
    if fn is not None:
        body += f'<w:footnoteReference w:id="{fn}"/>'
    return f"<w:r>{rpr}{body}</w:r>"


def _p(*runs: str) -> str:
    return f"<w:p>{''.join(runs)}</w:p>"


def _txt(s: str) -> str:
    return _p(_r(text=s))


def _neo(prefix: str, fn: str, noi_dung: str) -> str:
    """Đoạn BỊ SỬA, đúng hình dạng thật: `"1."` + superscript `"4"` + fnRef."""
    return _p(_r(text=prefix), _r(text=fn, sup=True), _r(sup=True, fn=fn),
              _r(text=" " + noi_dung))


def _docx(paras: list[str], footnotes: dict[str, str], *, backslash: bool = False) -> bytes:
    fn_xml = "".join(
        f'<w:footnote w:id="{i}"><w:p><w:r><w:t xml:space="preserve">{t}</w:t>'
        f"</w:r></w:p></w:footnote>"
        for i, t in footnotes.items()
    )
    buf = BytesIO()
    sep = "\\" if backslash else "/"
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"word{sep}document.xml",
                   f"<w:document {W}><w:body>{''.join(paras)}</w:body></w:document>")
        z.writestr(f"word{sep}footnotes.xml", f"<w:footnotes {W}>{fn_xml}</w:footnotes>")
    return buf.getvalue()


# Nguyên văn footnote đo được trên VBHN thật (khuôn do NĐ 78/2025/NĐ-CP quy định).
FN_TT = ("3 Khoản này được sửa đổi, bổ sung theo quy định tại điểm a khoản 1 Điều 3 "
         "của Thông tư số 21/2026/TT-BKHCN, có hiệu lực kể từ ngày 20 tháng 5 năm 2026.")
FN_DS = ("4 Khoản này được sửa đổi, bổ sung theo quy định tại khoản 1 Điều 29 "
         "của Luật Dân số số 113/2025/QH15, có hiệu lực kể từ ngày 01 tháng 7 năm 2026.")


# ── Ca khảo sát đã chứng minh: fn3 → Khoản 3 Điều 7 ──────────────────────────

def test_fn3_giai_ra_khoan_3_dieu_7():
    """Ca `09/2026/VBHN-TT-BKHCN` khảo sát đã chứng minh bằng tay.

    Neo là CẤU TRÚC: `<w:footnoteReference>` nằm trong `<w:p>` nào thì `<w:p>`
    đó CHÍNH LÀ khoản bị sửa. Chữ "Khoản này" trong footnote là đại từ hồi chỉ,
    tự nó không nói khoản nào — không được đọc nó để suy ra vị trí.
    """
    b = _docx(
        [_txt("Điều 6. Điều khoản chuyển tiếp"),
         _txt("1. Nội dung điều 6 khoản 1."),
         _txt("Điều 7. Trách nhiệm thi hành"),
         _txt("1. Nội dung khoản 1."),
         _txt("2. Nội dung khoản 2."),
         _neo("3.", "3", "Nội dung khoản 3 đã được sửa.")],
        {"3": FN_TT})
    (s,) = doc_sua_doi(b)
    assert s.vi_tri == "Điều 7 > Khoản 3"
    assert s.sua_boi_so_ky_hieu == "21/2026/TT-BKHCN"
    assert s.sua_boi_duong_dan == "điểm a khoản 1 Điều 3"
    assert s.tu_ngay == date(2026, 5, 20)
    assert s.do_tin_cay == "trung_binh"


def test_neo_diem_lay_khoan_va_dieu_dang_mo():
    """Neo ở cấp Điểm phải mang theo Khoản và Điều đang mở — ca fn2 thật
    (`a)` dưới `2.` dưới `Điều 59`)."""
    b = _docx(
        [_txt("Điều 59. Đào tạo nghề nghiệp"),
         _txt("1. Người lao động được tự do lựa chọn."),
         _txt("2. Nhà nước có chính sách khuyến khích:"),
         _neo("a)", "2", "Thành lập cơ sở giáo dục nghề nghiệp;")],
        {"2": FN_TT.replace("3 Khoản", "2 Điểm")})
    (s,) = doc_sua_doi(b)
    assert s.vi_tri == "Điều 59 > Khoản 2 > Điểm a"


def test_khoan_bo_sung_moi_giu_nguyen_so_hieu_chu_la():
    """`8a` là khoản MỚI do luật sửa chèn vào — số hiệu có chữ, không được ép
    về `8`. Ca fn5 thật (Điều 154)."""
    b = _docx(
        [_txt("Điều 154. Người lao động nước ngoài"),
         _txt("8. Người nước ngoài kết hôn với người Việt Nam."),
         _neo("8a.", "5", "Nhân lực công nghiệp công nghệ số chất lượng cao.")],
        {"5": ("5 Khoản này được bổ sung theo quy định tại khoản 4 Điều 49 của Luật "
               "Công nghiệp công nghệ số số 71/2025/QH15, có hiệu lực kể từ ngày "
               "01 tháng 01 năm 2026.")})
    (s,) = doc_sua_doi(b)
    assert s.vi_tri == "Điều 154 > Khoản 8a"
    # "Luật Công nghiệp công nghệ SỐ SỐ 71/2025/QH15" — hai chữ "số" liền nhau.
    assert s.sua_boi_so_ky_hieu == "71/2025/QH15"
    assert s.tu_ngay == date(2026, 1, 1)


def test_dieu_hien_phap_khong_tieu_de_va_hieu_luc_thi_hanh_tu_ngay():
    """Khuôn `52/VBHN-VPQH` (Hiến pháp) đo 2026-09-29: điều không có tiêu đề nên
    dòng chỉ là "Điều 110", không dấu chấm; footnote viết "có hiệu lực thi hành
    từ ngày", không có "kể". Trước bản sửa: 0/5 điểm sửa đọc được."""
    fn = (
        "Điều này được sửa đổi, bổ sung theo quy định tại khoản {k} Điều 1 của Nghị "
        "quyết số 203/2025/QH15 sửa đổi, bổ sung một số điều của Hiến pháp nước Cộng "
        "hòa xã hội chủ nghĩa Việt Nam, có hiệu lực thi hành từ ngày 16 tháng 6 năm 2025."
    )
    b = _docx(
        [
            _txt("Điều 84"),
            # Câu văn mở đầu bằng "Điều 12 …" KHÔNG phải dòng tiêu đề điều.
            _txt("Điều 12 của Luật này không mở một điều mới."),
            _neo("1.", "4", "Chủ tịch nước, Ủy ban thường vụ Quốc hội có quyền trình dự án luật."),
            _p(_r(text="Điều 110"), _r(text="5", sup=True), _r(sup=True, fn="5")),
        ],
        {"4": fn.format(k=3).replace("Điều này", "Khoản này"), "5": fn.format(k=4)},
    )
    k1, d110 = doc_sua_doi(b)
    assert (k1.vi_tri, k1.sua_boi_duong_dan) == ("Điều 84 > Khoản 1", "khoản 3 Điều 1")
    assert (d110.vi_tri, d110.sua_boi_duong_dan) == ("Điều 110", "khoản 4 Điều 1")
    assert {s.sua_boi_so_ky_hieu for s in (k1, d110)} == {"203/2025/QH15"}
    assert {s.tu_ngay for s in (k1, d110)} == {date(2025, 6, 16)}
    assert {s.do_tin_cay for s in (k1, d110)} == {"trung_binh"}


def test_sua_doan_dau_diem_van_la_ghi_chu_sua_doi():
    """`54/VBHN-VPQH` fn23, đo 2026-09-29: "Đoạn đầu điểm này được sửa đổi…" —
    36/37 dấu sửa của cổng MOJ khớp VBHN, dấu còn lại là chính điểm này."""
    b = _docx(
        [
            _txt("Điều 46. Xây dựng, ban hành nghị quyết"),
            _txt("1. Xây dựng, ban hành nghị quyết của Hội đồng Thẩm phán:"),
            _neo("b)", "23", "Dự thảo nghị quyết được đăng tải trên Cổng thông tin điện tử"),
        ],
        {
            "23": (
                "Đoạn đầu điểm này được sửa đổi, bổ sung theo quy định tại điểm a khoản 14 "
                "Điều 1 của Luật số 87/2025/QH15 sửa đổi, bổ sung một số điều của Luật Ban hành "
                "văn bản quy phạm pháp luật, có hiệu lực kể từ ngày 01 tháng 7 năm 2025."
            )
        },
    )
    (s,) = doc_sua_doi(b)
    assert s.vi_tri == "Điều 46 > Khoản 1 > Điểm b"
    assert (s.sua_boi_so_ky_hieu, s.sua_boi_duong_dan) == ("87/2025/QH15", "điểm a khoản 14 Điều 1")
    assert s.tu_ngay == date(2025, 7, 1)


# ── Cạm bẫy 1: `<w:tab>` ─────────────────────────────────────────────────────

def test_tab_khong_nuot_mat_dieu():
    """`<w:t[^>]*>` khớp cả `<w:tab>`; khảo sát đo được "0 Điều" trên file có
    220 Điều — sai âm thầm, không lỗi. Parser phải đi qua cây XML, không regex."""
    b = _docx(
        [_p(_r(text="Điều 7."), "<w:tab/>", _r(text=" Trách nhiệm thi hành")),
         _neo("3.", "3", "Nội dung khoản 3.")],
        {"3": FN_TT})
    (s,) = doc_sua_doi(b)
    assert s.vi_tri == "Điều 7 > Khoản 3", "tab làm hỏng việc nhận diện Điều"


# ── Cạm bẫy 2: số footnote dính liền số khoản ────────────────────────────────

def test_marker_footnote_khong_bi_doc_thanh_so_khoan():
    """`"1." + <sup>4</sup>` trích ra text phẳng là `"1.4 Lao động nữ…"`. Số 4
    là MARKER footnote, không phải phần của số khoản. Đọc tham thành "Khoản 1.4"
    hoặc "Khoản 4" — cả hai đều sai, và cả hai đều im lặng."""
    b = _docx(
        [_txt("Điều 139. Nghỉ thai sản"),
         _neo("1.", "4", "Lao động nữ được nghỉ thai sản là 06 tháng.")],
        {"4": FN_DS})
    (s,) = doc_sua_doi(b)
    assert s.vi_tri == "Điều 139 > Khoản 1"
    assert "4" not in s.vi_tri.split("Khoản")[1]


# ── Cạm bẫy 3: ZIP dùng `\` làm phân cách ────────────────────────────────────

def test_zip_dung_backslash_van_doc_duoc():
    b = _docx([_txt("Điều 7. X"), _neo("3.", "3", "Y")], {"3": FN_TT}, backslash=True)
    (s,) = doc_sua_doi(b)
    assert s.vi_tri == "Điều 7 > Khoản 3"


# ── Không khớp khuôn ⇒ khai báo, KHÔNG đoán ──────────────────────────────────

def test_regex_khong_khop_thi_can_doi_chieu_tay_chu_khong_bia():
    """Footnote ĐÚNG là ghi chú sửa đổi nhưng câu trích dẫn lệch khuôn: giữ
    lại vị trí (cấu trúc, vẫn tin được) và khai `can_doi_chieu_tay`. Tuyệt đối
    không đoán số hiệu hay ngày."""
    b = _docx(
        [_txt("Điều 7. X"),
         _neo("3.", "3", "Y")],
        {"3": "3 Khoản này được sửa đổi, bổ sung theo một văn bản chưa rõ số hiệu."})
    (s,) = doc_sua_doi(b)
    assert s.vi_tri == "Điều 7 > Khoản 3"
    assert s.do_tin_cay == "can_doi_chieu_tay"
    assert s.sua_boi_so_ky_hieu is None and s.tu_ngay is None


def test_footnote_khong_phai_ghi_chu_sua_doi_thi_bo_qua_han():
    """VBHN thật có 6 footnote nhưng CHỈ 4 là ghi chú sửa đổi. fn1 là "căn cứ
    ban hành", fn6 trích nguyên Điều hiệu lực thi hành của luật sửa — neo của
    chúng là lời mở đầu và tiêu đề Chương, không phải điều khoản.

    Chúng KHÔNG được thành `can_doi_chieu_tay`: gộp "không phải sửa đổi" với
    "sửa đổi nhưng chưa đọc được" là tự tạo việc đối chiếu tay không có thật,
    rồi người thật đi rà một danh sách rác."""
    b = _docx(
        [_p(_r(text="Quốc hội ban hành Bộ luật Lao động."), _r(text="1", sup=True),
            _r(sup=True, fn="1")),
         _txt("Điều 7. X"),
         _neo("3.", "3", "Y"),
         _p(_r(text="ĐIỀU KHOẢN THI HÀNH"), _r(text="6", sup=True), _r(sup=True, fn="6"))],
        {"1": "1 Luật Công nghiệp công nghệ số số 71/2025/QH15 có căn cứ ban hành như sau: …",
         "3": FN_TT,
         "6": "6 Điều 50 của Luật Công nghiệp công nghệ số số 71/2025/QH15 quy định như sau: …"})
    ra = doc_sua_doi(b)
    assert [s.vi_tri for s in ra] == ["Điều 7 > Khoản 3"]


def test_neo_khong_nam_o_cap_dieu_khoan_nao_thi_bo_qua():
    """Ghi chú sửa đổi neo vào một đoạn không mang số hiệu cấp nào (đoạn nối
    trong lòng khoản). Không có vị trí ⇒ không có bản ghi; im lặng ở đây là
    đúng, vì bịa một vị trí là bịa một trích dẫn."""
    b = _docx(
        [_txt("Điều 7. X"),
         _neo("Trong trường hợp này,", "3", "áp dụng quy định chuyển tiếp.")],
        {"3": FN_TT})
    assert doc_sua_doi(b) == []


def test_ngay_mot_chu_so_va_hai_chu_so_deu_doc_duoc():
    """`"tháng 7"` (VBHN thật) và `"tháng 01"` cùng xuất hiện trong MỘT file."""
    b = _docx([_txt("Điều 1. X"), _neo("1.", "4", "Y")], {"4": FN_DS})
    assert doc_sua_doi(b)[0].tu_ngay == date(2026, 7, 1)


def test_khong_co_footnote_thi_tra_rong_chu_khong_no():
    b = _docx([_txt("Điều 1. X"), _txt("1. Y")], {})
    assert doc_sua_doi(b) == []
