"""Phép đối chiếu toàn văn của `scripts/don_kho.py` (cùng phương pháp kiểm kho
2026-09-28, 8.609/8.609): mỗi điều/khoản/điểm trong kho phải là chuỗi con NGUYÊN
VĂN của `documentContent.content` gateway sau chuẩn hoá NFC, Ð→Đ, NBSP, khoảng trắng."""

from scripts.don_kho import doi_chieu_toan_van

HTML = (
    '<p class="prov-article">Điều 1. Phạm vi</p><p>1. Người lao&nbsp;động  có quyền</p>'
    "<p>a) làm việc;</p><table><tr><td>Vùng I</td></tr></table>"
)


def test_moi_cap_trich_dan_duoc_la_chuoi_con_thi_khop_het():
    provs = [
        {"id": 1, "cap": "dieu", "noi_dung": "Điều 1. Phạm vi"},
        {"id": 2, "cap": "khoan", "noi_dung": "1. Người lao động có quyền"},
        {"id": 3, "cap": "diem", "noi_dung": "a) làm việc;"},
        # Ba cấp không đối chiếu: lời mở đầu, phụ lục và hàng bảng dàn trang khác nguồn.
        {"id": 4, "cap": "mo_dau", "noi_dung": "không có trong nguồn"},
        {"id": 5, "cap": "hang_bang", "noi_dung": "Vùng I | 4.960.000"},
    ]
    assert doi_chieu_toan_van(provs, HTML) == (3, 3, [])


def test_Eth_trong_kho_va_chu_lech_bi_bat():
    provs = [
        {"id": 1, "cap": "dieu", "noi_dung": "Ðiều 1. Phạm vi"},  # Ð U+00D0 trong kho vẫn khớp
        {"id": 2, "cap": "khoan", "noi_dung": "1. Người lao động có nghĩa vụ"},
    ]
    assert doi_chieu_toan_van(provs, HTML) == (2, 1, [2])


def test_dau_tach_o_bang_cua_kho_va_khoang_trang_truoc_dau_cau_khong_tinh_la_lech():
    """Kho dàn ô bảng thành 'ô | ô' và đôi khi để khoảng trắng trước dấu chấm —
    trình bày, không phải chữ. Một chữ khác vẫn phải bị bắt."""
    html = "<p>Tiền lương làm thêm giờ</p><table><tr><td>=</td><td>Tiền lương giờ</td></tr></table><p>Chính phủ.</p>"
    provs = [
        {"id": 1, "cap": "khoan", "noi_dung": "Tiền lương làm thêm giờ | = | Tiền lương giờ"},
        {"id": 2, "cap": "khoan", "noi_dung": "Chính phủ ."},
        {"id": 3, "cap": "khoan", "noi_dung": "Tiền lương làm thêm ngày"},
    ]
    assert doi_chieu_toan_van(provs, html) == (3, 2, [3])
