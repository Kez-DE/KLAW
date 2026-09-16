"""Phép tính chạy BẰNG MÃ trên số của tài liệu (plan `tai-lieu-tong-quat.md` S4,
FR-013).

File này khoá hai điều, và điều thứ hai mới là lý do file tồn tại:

1. Số viết kiểu Việt đọc đúng: `2,0` là hai phẩy không, `20.000.000` là hai
   mươi triệu, `1.234,56` là một nghìn hai trăm ba mươi tư phẩy năm sáu.
2. Bộ đánh giá KHÔNG chạy Python. Một biểu thức do mô hình viết đi thẳng vào
   `eval()` là một lỗ thực thi mã; ở đây `__import__('os')`, `2**10` hay một
   cái tên trần đều trả `None` chứ không phải một kết quả.
"""

from decimal import Decimal

import pytest

from src.services.phep_tinh import so_bang_nhau, tinh, viet_so

# ───────────────────────────────────────────────────── dạng số tiếng Việt


@pytest.mark.parametrize(
    ("bieu_thuc", "mong_doi"),
    [
        ("2,0 + 2,0 + 2,0 + 4,0", "10"),
        ("20.000.000", "20000000"),
        ("20.000.000 - 5.000.000", "15000000"),
        ("1.234,56", "1234.56"),
        ("10", "10"),
        ("10 / 4", "2.5"),
        ("(2 + 3) * 4", "20"),
        ("-5 + 10", "5"),
        ("10.0 + 0.5", "10.5"),
    ],
)
def test_doc_dung_dang_so(bieu_thuc, mong_doi):
    assert tinh(bieu_thuc) == Decimal(mong_doi)


def test_cham_khong_thanh_ba_chu_so_la_dau_thap_phan():
    """`10.000` là mười nghìn, `10.0` là mười — nhóm ĐÚNG ba chữ số mới là
    dấu phân nhóm."""
    assert tinh("10.000") == Decimal("10000")
    assert tinh("10.0") == Decimal("10")


# ─────────────────────────────────────────────────────────────── từ chối


@pytest.mark.parametrize(
    "bieu_thuc",
    [
        "__import__('os')",
        "2**10",
        "a + 1",
        "open('x')",
        "[1, 2][0]",
        "(1).real",
        "2 + ",
        "",
        "   ",
        "5 %",
        "50% + 10",
        "1,2,3",
    ],
)
def test_tu_choi_moi_thu_khong_phai_bon_phep(bieu_thuc):
    assert tinh(bieu_thuc) is None


def test_chia_cho_khong_tra_none():
    assert tinh("10 / 0") is None
    assert tinh("10 / (5 - 5)") is None


# ─────────────────────────────────────────────────────────── so sánh số


@pytest.mark.parametrize(("a", "b"), [("10", "10,0"), ("10", "10.0"), ("10,0", "10.0"),
                                      ("20.000.000", "20000000"), ("50%", "50")])
def test_so_bang_nhau(a, b):
    assert so_bang_nhau(a, b) is True


@pytest.mark.parametrize(("a", "b"), [("10", "9,99"), ("10", "diểm mười"), ("", "10"), ("10", "")])
def test_so_khac_nhau(a, b):
    assert so_bang_nhau(a, b) is False


# ─────────────────────────────────────────────────────── viết lại kết quả


@pytest.mark.parametrize(
    ("d", "mong_doi"),
    [("10", "10"), ("10.00", "10"), ("5.5", "5,5"), ("-2.50", "-2,5"), ("0", "0")],
)
def test_viet_so_dau_phay_khong_thua_so_khong(d, mong_doi):
    assert viet_so(Decimal(d)) == mong_doi


def test_viet_so_chia_le_khong_tran_28_chu_so():
    assert viet_so(tinh("10 / 3")) == "3,333333"
