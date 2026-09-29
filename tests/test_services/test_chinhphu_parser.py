"""Adapter `vanban.chinhphu.vn` → class `prov-*`.

Bốn hỏng hóc test này chặn, cả bốn đều IM LẶNG khi xảy ra — đó là tiêu chí để
một ca được vào đây, không phải "phủ cho đủ dòng":

1. Thẻ inline cắt ngang từ. Nguồn là bản xuất từ Word và nó có thật
   `<i>Khiếu nạ</i>i` ở Điều 2 Khoản 1. Lấy text bằng `get_text(" ")` cho ra
   "Khiếu nạ i" — sai chính tả ngay trong định nghĩa trung tâm của đạo luật,
   chuỗi vẫn không rỗng nên bất biến CITABLE không thấy gì.
2. Câu văn mở đầu bằng số bị nhận nhầm thành Khoản. Regex Khoản ở đây chặt hơn
   `RE_SO` của prov_parser vì không có class làm bằng chứng độc lập; nới ra thì
   "15 ngày kể từ…" thành một Khoản giả treo lơ lửng giữa cây.
3. Trang đổi cấu trúc. Không tìm thấy `div#block_detail` mà vẫn parse cả trang
   thì menu và breadcrumb chui vào `noi_dung` của Điều cuối — vẫn "thành công".
4. Phần mở đầu rơi mất. Quốc hiệu, "Căn cứ Hiến pháp…", "Quốc hội ban hành
   Luật khiếu nại." không mang nhãn cấp nào; gắn `prov-content` để nguyên tắc
   KHÔNG-WHITELIST của prov_parser nối chúng vào node đang mở.
"""

import pytest

from src.services.chinhphu_parser import sang_html_prov
from src.services.prov_parser import parse_anomalies, parse_provisions


def _trang(than: str) -> str:
    return f'<html><body><div id="block_detail">{than}</div></body></html>'


def test_the_inline_khong_duoc_cat_ngang_tu():
    # Arrange — đúng hình dạng đã đo được ở Điều 2 Khoản 1 của 02/2011/QH13.
    html = _trang("<p>1. <i>Khiếu nạ</i>i là việc công dân đề nghị xem xét lại.</p>")

    # Act
    out = sang_html_prov(html)

    # Assert
    assert "Khiếu nại" in out
    assert "Khiếu nạ i" not in out


def test_cau_mo_dau_bang_so_khong_thanh_khoan_gia():
    html = _trang(
        "<p>Điều 9. Thời hiệu khiếu nại</p>"
        "<p>90 ngày kể từ ngày nhận được quyết định hành chính.</p>"
    )
    out = sang_html_prov(html)
    # "90 ngày…" không có dấu . hoặc ) sau số ⇒ là thân của Điều 9, không phải Khoản.
    assert 'class="prov-clause"' not in out
    assert out.count('class="prov-content"') == 1


def test_so_co_dau_cham_van_la_khoan():
    out = sang_html_prov(_trang("<p>Điều 8. Hình thức</p><p>1. Việc khiếu nại.</p>"))
    assert 'class="prov-clause"' in out


def test_thieu_khoi_noi_dung_thi_dung_han():
    with pytest.raises(ValueError, match="block_detail"):
        sang_html_prov("<html><body><div id='doi_ten'><p>Điều 1. X</p></div></body></html>")


def test_phan_mo_dau_thanh_prov_content_chu_khong_roi_mat():
    out = sang_html_prov(_trang(
        "<p>QUỐC HỘI</p><p>Căn cứ Hiến pháp;</p><p>Điều 1. Phạm vi điều chỉnh</p>"))
    assert out.count('class="prov-content"') == 2
    assert 'class="prov-article"' in out


def test_cay_hoan_chinh_di_qua_dung_cong_cua_prov_parser():
    """Ca tổng: adapter → parse_anomalies → parse_provisions, đúng đường thật."""
    html = _trang(
        "<p>CHƯƠNG I</p><p>NHỮNG QUY ĐỊNH CHUNG</p>"
        "<p>Điều 8. Hình thức khiếu nại</p>"
        "<p>1. Việc khiếu nại được thực hiện bằng đơn.</p>"
        "<p>2. Trường hợp nhiều người cùng khiếu nại thì:</p>"
        "<p>a) Cử người đại diện;</p>"
        "<p>b) Ghi rõ nội dung.</p>"
    )
    prov_html = sang_html_prov(html)

    loi, _ = parse_anomalies(prov_html, "02/2011/QH13")
    assert loi == []

    duong_dan = [r.duong_dan for r in parse_provisions(prov_html, "02/2011/QH13")]
    assert "02/2011/QH13 > Điều 8 > Khoản 2 > Điểm b" in duong_dan
    # "CHƯƠNG I" + "NHỮNG QUY ĐỊNH CHUNG" tách hai thẻ vẫn về MỘT node Chương —
    # nguyên tắc "gộp trước, đọc số hiệu sau" của prov_parser, không phải việc
    # adapter phải tự lo.
    assert sum(d.startswith("02/2011/QH13 > Chương") for d in duong_dan) == 1


def test_khoi_chu_ky_khong_chui_vao_dieu_cuoi():
    """Nguồn MOJ tách khối đuôi bằng CẤU TRÚC; trang Chính phủ không, nên adapter
    phải nhận nó bằng công thức ban hành. Sai chỗ này thì lời chứng thông qua và
    tên người ký nằm trong `noi_dung` của Điều cuối — một câu trích lấy từ khối
    chữ ký sẽ 'kiểm chứng thành công' trên một neo Điều, đúng véc-tơ mà ruling
    chữ-đuôi đã đóng. Đo được trên 02/2011/QH13 Điều 70 trước khi sửa.
    """
    out = sang_html_prov(_trang(
        "<p>Điều 70. Quy định chi tiết</p>"
        "<p>Chính phủ quy định chi tiết các điều, khoản được giao.</p>"
        "<p>Luật này đã được Quốc hội khóa XIII thông qua ngày 11 tháng 11 năm 2011.</p>"
        "<p>CHỦ TỊCH QUỐC HỘI</p><p>Nguyễn Sinh Hùng</p>"))
    rows = {r.cap.value: r.noi_dung for r in parse_provisions(out, "02/2011/QH13")}

    assert "Nguyễn Sinh Hùng" in rows["phu_luc"]
    assert "thông qua ngày" in rows["phu_luc"]
    assert "Nguyễn Sinh Hùng" not in rows["dieu"]
    # Thân thật của Điều cuối vẫn phải ở lại trong Điều, không bị đẩy sang đuôi.
    assert "quy định chi tiết các điều, khoản được giao" in rows["dieu"]


def test_cong_thuc_ban_hanh_o_giua_than_khong_cat_nham():
    """`_RE_KHOI_DUOI` chỉ khớp công thức ban hành CHUẨN ("… này đã được"). Một
    Điều dẫn chiếu văn bản khác không được kích hoạt nó, nếu không nửa cuối đạo
    luật rơi hết vào `phu_luc` và biến mất khỏi mọi neo trích dẫn."""
    out = sang_html_prov(_trang(
        "<p>Điều 1. Phạm vi</p>"
        "<p>Áp dụng Luật khiếu nại, tố cáo số 09/1998/QH10 đã được sửa đổi, bổ sung.</p>"
        "<p>Điều 2. Giải thích</p>"))
    assert out.count('class="prov-article"') == 2
    assert "<p>Áp dụng" not in out  # không bị đẩy thành khối đuôi


def test_cong_thuc_moi_luat_nay_duoc_quoc_hoi_thong_qua_la_khoi_duoi():
    """Luật từ 2025 viết "Luật này được Quốc hội … thông qua" (không "đã"; 148/2025/QH15,
    Công báo số 43). Không nhận ra thì lời chứng và tên người ký chui vào Điều cuối. Một
    câu thân văn bản "Luật này được áp dụng …" thì KHÔNG phải khối đuôi."""
    out = sang_html_prov(
        _trang(
            "<p>Điều 2. Đối tượng áp dụng</p>"
            "<p>Luật này được áp dụng đối với cơ quan, tổ chức, cá nhân.</p>"
            "<p>Điều 48. Điều khoản chuyển tiếp</p>"
            "<p>1. Chiến lược đã được phê duyệt được tiếp tục thực hiện.</p>"
            "<p>Luật này được Quốc hội nước Cộng hòa xã hội chủ nghĩa Việt Nam khóa XV thông qua ngày 11 tháng 12 năm 2025.</p>"
            "<p>CHỦ TỊCH QUỐC HỘI</p><p>Trần Thanh Mẫn</p>"
        )
    )
    rows = [(r.cap.value, r.noi_dung) for r in parse_provisions(out, "148/2025/QH15")]
    dieu = [n for c, n in rows if c == "dieu"]
    assert "Luật này được áp dụng" in dieu[0]
    assert not any("Trần Thanh Mẫn" in n or "thông qua ngày" in n for c, n in rows if c != "phu_luc")


def test_docx_cong_bao_moi_doan_than_van_ban_ke_ca_trong_bang():
    """Bản `.docx` Công báo → cùng adapter: mỗi `<w:p>` thân văn bản (cả ô bảng: tiêu đề,
    khối chữ ký) thành một đoạn, theo đúng thứ tự tài liệu."""
    import io
    import zipfile

    from src.services.chinhphu_parser import docx_sang_html_prov

    def p(t):
        return f'<w:p><w:r><w:t xml:space="preserve">{t}</w:t></w:r></w:p>'

    than = (
        "<w:tbl><w:tr><w:tc>"
        + p("QUỐC HỘI")
        + p("Luật số: 9/2025/QH15")
        + "</w:tc></w:tr></w:tbl>"
        + p("Điều 1. Phạm vi")
        + p("1. Nội dung khoản một.")
        + p("Luật này được Quốc hội khóa XV thông qua ngày 11 tháng 12 năm 2025.")
        + "<w:tbl><w:tr><w:tc>"
        + p("CHỦ TỊCH QUỐC HỘI")
        + "</w:tc></w:tr></w:tbl>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w='
            f'"http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{than}</w:body></w:document>',
        )
    rows = {r.cap.value: r.noi_dung for r in parse_provisions(docx_sang_html_prov(buf.getvalue()), "9/2025/QH15")}
    assert rows["khoan"] == "1. Nội dung khoản một."
    assert "CHỦ TỊCH QUỐC HỘI" in rows["phu_luc"] and "QUỐC HỘI" in rows["mo_dau"]
