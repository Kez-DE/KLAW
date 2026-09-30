"""`scripts/trich_bai_bo` — đọc câu bãi bỏ điều khoản từ nguyên văn văn bản đi bãi bỏ.

Chủ dự án chốt 2026-09-30 (quyết định 2026-09-30 mục 9): mỗi điều khoản bị văn bản
khác bãi bỏ được ghi kèm bằng chứng nguyên văn. Parser THUẦN, 0 DB, 0 model; câu thử
chép từ toàn văn gateway Bộ Tư pháp. Chặt hơn là đủ: câu nào không đọc trọn được thành
danh sách điều khoản thì bỏ, không đoán.
"""

import json
from datetime import UTC, date, datetime

import pytest

from scripts.trich_bai_bo import DOI_CHIEU_TAY, cap_ung_vien, hang_seed, muc_tieu, trich_tay, trich_van_ban

# 151/2025/NĐ-CP Điều 21 (gateway 178259), nguyên văn.
_151 = [
    "Điều 21. Hiệu lực thi hành",
    "1. Nghị định này có hiệu lực thi hành từ ngày 01 tháng 7 năm 2025.",
    "4. Các quy định sau đây hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành",
    "a) Khoản 1 và khoản 2 Điều 22 Nghị định số 71/2024/NĐ-CP;",
    "b) Khoản 5 và khoản 11 Điều 9; khoản 1 Điều 19; khoản 3 Điều 20; các Điều 21, 22, 28, 29, 30, 31, 32, 33,"
    " 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 60; các Mẫu số 01/ĐK, 02/ĐK, 03/ĐK, 04/ĐK,"
    " 05/ĐK, 06/ĐK, 07/ĐK, 08/ĐK, 09/ĐK, 10/ĐK, 11/ĐK, 12/ĐK, 14/ĐK Nghị định số 101/2024/NĐ-CP;",
    "c) Khoản 1 Điều 14; khoản 1 và khoản 5 Điều 54; điểm c khoản 2 và điểm a khoản 3 Điều 94; khoản 4 và khoản 6"
    " Điều 99; khoản 3 Điều 100; điểm b khoản 6 Điều 101; các Điều 20, 21, 23, 44, 45, 48, 49, 51, 52, 53, 60, 64,"
    " 66, 68, 73, 106, 107 Nghị định số 102/2024/NĐ-CP;",
    "d) Các Điều 11, 12 và 13 Nghị định số 112/2024/NĐ-CP ngày 11 tháng 9 năm 2024 của Chính phủ quy định chi tiết"
    " về đất trồng lúa.",
    "Điều 22. Điều khoản chuyển tiếp",
]


def test_151_2025_dieu_21_khoan_4_diem_b_va_c():
    (b,) = trich_van_ban(_151, "101/2024/NĐ-CP")
    assert b.vi_tri == "Điều 21 khoản 4 điểm b"
    assert b.dieu_khoan[:4] == ["Điều 9 > Khoản 5", "Điều 9 > Khoản 11", "Điều 19 > Khoản 1", "Điều 20 > Khoản 3"]
    assert b.dieu_khoan[4:] == [f"Điều {n}" for n in (21, 22, *range(28, 50), 60)]
    # Bằng chứng: câu dẫn + mục, nguyên văn, nối " … ".
    assert b.trich.startswith("4. Các quy định sau đây hết hiệu lực") and " … b) Khoản 5 và khoản 11 Điều 9;" in b.trich
    (c,) = trich_van_ban(_151, "102/2024/NĐ-CP")
    assert c.vi_tri == "Điều 21 khoản 4 điểm c"
    assert c.dieu_khoan[:9] == [
        "Điều 14 > Khoản 1",
        "Điều 54 > Khoản 1",
        "Điều 54 > Khoản 5",
        "Điều 94 > Khoản 2 > Điểm c",
        "Điều 94 > Khoản 3 > Điểm a",
        "Điều 99 > Khoản 4",
        "Điều 99 > Khoản 6",
        "Điều 100 > Khoản 3",
        "Điều 101 > Khoản 6 > Điểm b",
    ]
    assert "Điều 106" in c.dieu_khoan and "Điều 107" in c.dieu_khoan and len(c.dieu_khoan) == 9 + 17
    (d,) = trich_van_ban(_151, "112/2024/NĐ-CP")
    assert d.dieu_khoan == ["Điều 11", "Điều 12", "Điều 13"]
    assert trich_van_ban(_151, "31/2024/QH15") == []


@pytest.mark.parametrize(
    ("doan", "ra"),
    [
        ("Khoản 3 Điều 4 và Khoản 3 Điều 18", ["Điều 4 > Khoản 3", "Điều 18 > Khoản 3"]),
        ("Điều 4, Điều 24 và khoản 3 Điều 45", ["Điều 4", "Điều 24", "Điều 45 > Khoản 3"]),
        ("điểm d khoản 1 Điều 44 và Điều 58", ["Điều 44 > Khoản 1 > Điểm d", "Điều 58"]),
        ("các khoản 1, 3 Điều 7 và khoản 2 Điều 8", ["Điều 7 > Khoản 1", "Điều 7 > Khoản 3", "Điều 8 > Khoản 2"]),
        ("Điều 1, 2, 3, 4, 5 và 6", [f"Điều {n}" for n in range(1, 7)]),
        ("điểm a Điều 5", ["Điều 5 > Điểm a"]),
        ("Điều 33a", ["Điều 33a"]),
        ("từ Điều 21 đến Điều 24", ["Điều 21", "Điều 22", "Điều 23", "Điều 24"]),
        # "đoạn" là phần của một khoản — không ẩn được một phần khoản, bỏ đúng cụm đó.
        (
            "điểm a khoản 2 Điều 5, đoạn 2 khoản 1 Điều 27 và điểm a khoản 1 Điều 38",
            ["Điều 5 > Khoản 2 > Điểm a", "Điều 38 > Khoản 1 > Điểm a"],
        ),
    ],
)
def test_muc_tieu_doc_du_danh_sach(doan, ra):
    assert muc_tieu(doan) == ra


@pytest.mark.parametrize(
    "doan",
    [
        "các quy định về trưng dụng đất",  # chữ ngoài văn phạm điều khoản
        "các Mẫu số 01/ĐK, 02/ĐK",
        "Phụ lục III ban hành kèm theo",
        'cụm từ "trong giai đoạn chuyển tiếp" tại khoản 1 Điều 2',
        "khoản 5",  # thiếu Điều
        "khoản 1 Điều 19, 20",  # khoản của Điều nào — mơ hồ
        "",
    ],
)
def test_muc_tieu_khong_doan(doan):
    assert muc_tieu(doan) == []


def test_bai_bo_trong_cau_va_ranh_gioi_van_ban_khac():
    dong = [
        "Điều 3. Hiệu lực thi hành",
        "2. Bãi bỏ các quy định tại Khoản 3 Điều 4 và Khoản 3 Điều 18 Nghị định số 69/2008/NĐ-CP ngày 30 tháng 5"
        " năm 2008 của Chính phủ.",
        "3. Bãi bỏ quy định tại Điều 2 Nghị định số 10/2017/NĐ-CP ngày 09 tháng 02 năm 2017 của Chính phủ và sửa"
        " đổi, bổ sung khoản 4 Điều 4 Nghị định số 209/2013/NĐ-CP ngày 18 tháng 12 năm 2013 của Chính phủ.",
        "4. Bãi bỏ Điều 57 của Luật hàng không dân dụng Việt Nam số 66/2006/QH11; các quy định về trưng dụng đất"
        " trong Luật trưng mua, trưng dụng tài sản số 15/2008/QH12.",
    ]
    (a,) = trich_van_ban(dong, "69/2008/NĐ-CP")
    assert (a.vi_tri, a.dieu_khoan) == ("Điều 3 khoản 2", ["Điều 4 > Khoản 3", "Điều 18 > Khoản 3"])
    assert [t.dieu_khoan for t in trich_van_ban(dong, "10/2017/NĐ-CP")] == [["Điều 2"]]
    assert trich_van_ban(dong, "209/2013/NĐ-CP") == []  # sửa đổi, không bãi bỏ
    assert [t.dieu_khoan for t in trich_van_ban(dong, "66/2006/QH11")] == [["Điều 57"]]
    assert trich_van_ban(dong, "15/2008/QH12") == []


def test_so_hieu_co_khoang_trang_van_khop():
    dong = ["4. Bãi bỏ Điều 11, Điều 12, Điều 13, Điều 15 Thông tư số 10/2025/TT- BNNMT ngày 19 tháng 6 năm 2025;"]
    (t,) = trich_van_ban(dong, "10/2025/TT-BNNMT")
    assert t.dieu_khoan == ["Điều 11", "Điều 12", "Điều 13", "Điều 15"]


@pytest.mark.parametrize(
    "dong",
    [
        # Câu dẫn giới hạn NỘI DUNG (chỉ phần về thuế TNDN) — không phải bãi bỏ cả khoản.
        [
            "4. Bãi bỏ các nội dung quy định về thuế thu nhập doanh nghiệp tại các điều, khoản của các luật sau đây:",
            "b) Khoản 2 Điều 4 của Luật Bảo hiểm y tế số 25/2008/QH12;",
        ],
        ['2. Bãi bỏ cụm từ "trong giai đoạn chuyển tiếp" tại khoản 1 Điều 2 Nghị định số 25/2008/QH12.'],
        # Đi sửa, không đi bãi bỏ.
        ["Điều 1. Sửa đổi, bổ sung một số điều của Luật số 25/2008/QH12", "2. Sửa đổi khoản 3 Điều 4 như sau:"],
        # Lời văn mới trong ngoặc kép là luật ĐƯỢC SỬA, không phải câu bãi bỏ của văn bản này.
        [
            "1. Sửa đổi Điều 5 như sau:",
            "“Điều 5. Bãi bỏ Điều 3 Luật số 25/2008/QH12",
            "Nội dung khác.”",
        ],
        # Số điều khoản của bản ĐÃ SỬA (97/2015/QH13 Điều 23); kho giữ bản gốc, số có thể lệch.
        [
            "d) Bãi bỏ khoản 4 Điều 18 của Luật bảo hiểm y tế số 25/2008/QH12 đã được sửa đổi, bổ sung một số điều"
            " theo Luật số 46/2014/QH13;"
        ],
        # "trừ …" thu hẹp phạm vi bãi bỏ (27/2008/QH12 Điều 10 khoản 2).
        [
            "2. Bãi bỏ các quy định tại Điều 1 của Luật số 25/2008/QH12, trừ các quy định đối với mặt hàng rượu"
            " và bia tiếp tục có hiệu lực thi hành đến hết ngày 31 tháng 12 năm 2009."
        ],
    ],
)
def test_khong_ghi_khi_khong_phai_bai_bo_ca_dieu_khoan(dong):
    assert trich_van_ban(dong, "25/2008/QH12") == []


def test_muc_bai_bo_trong_dieu_sua_doi_van_ban_do():
    """Điều đi sửa MỘT văn bản nêu số hiệu ở tiêu đề; khoản bãi bỏ bên trong không nhắc lại số hiệu."""
    dong = [
        "Điều 4. Sửa đổi, bổ sung một số điều của Nghị định số 23/2020/NĐ-CP ngày 24 tháng 02 năm 2020 của Chính phủ",
        "1. Sửa đổi khoản 2 Điều 5 như sau:",
        "“2. Nội dung mới. Bãi bỏ khoản 9 Điều 1.”",
        "12. Bãi bỏ khoản 5 Điều 6; khoản 4 Điều 8; khoản 3 Điều 15.",
        "Điều 5. Sửa đổi, bổ sung một số điều của Nghị định số 24/2013/NĐ-CP",
        "1. Bãi bỏ Điều 7.",
    ]
    (t,) = trich_van_ban(dong, "23/2020/NĐ-CP")
    assert (t.vi_tri, t.dieu_khoan) == (
        "Điều 4 khoản 12",
        ["Điều 6 > Khoản 5", "Điều 8 > Khoản 4", "Điều 15 > Khoản 3"],
    )
    assert t.trich.startswith(
        "Điều 4. Sửa đổi, bổ sung một số điều của Nghị định số 23/2020/NĐ-CP"
    ) and t.trich.endswith("12. Bãi bỏ khoản 5 Điều 6; khoản 4 Điều 8; khoản 3 Điều 15.")
    assert [x.dieu_khoan for x in trich_van_ban(dong, "24/2013/NĐ-CP")] == [["Điều 7"]]


def test_bai_bo_cac_noi_dung_quy_dinh_tai_la_cau_dan_thuong():
    dong = [
        "2. Kể từ ngày Nghị định này có hiệu lực thi hành, bãi bỏ các nội dung quy định tại:",
        "b) Khoản 2, khoản 3, khoản 4, khoản 5, khoản 6 Điều 1, Điều 2, Điều 3, Điều 4 Quyết định số 23/2017/QĐ-TTg"
        " ngày 23 tháng 6 năm 2017 của Thủ tướng Chính phủ;",
    ]
    (t,) = trich_van_ban(dong, "23/2017/QĐ-TTg")
    assert t.dieu_khoan == [*(f"Điều 1 > Khoản {k}" for k in range(2, 7)), "Điều 2", "Điều 3", "Điều 4"]


def test_dang_c_qua_dong_thuong_va_bo_nua_sua_doi():
    dong = [
        "Điều 1. Sửa đổi, bổ sung một số điều của Luật bảo hiểm y tế số 25/2008/QH12",
        "13. Sửa đổi khoản 3 Điều 20 như sau:",
        "Đoạn giải thích không đánh số.",
        "14. Bãi bỏ điểm b khoản 1 Điều 21; sửa đổi, bổ sung điểm c khoản 1 và khoản 2 Điều 21 như sau:",
        "15. Bãi bỏ Điều 45 của Luật đất đai.",  # văn bản khác, không số hiệu
    ]
    (t,) = trich_van_ban(dong, "25/2008/QH12")
    assert (t.vi_tri, t.dieu_khoan) == ("Điều 1 khoản 14", ["Điều 21 > Khoản 1 > Điểm b"])


def test_dang_c_tieu_de_dieu_tach_hai_doan():
    dong = [
        "Điều 77. Sửa đổi, bổ sung, bãi bỏ một số điều của Luật giáo dục đại học",
        "Sửa đổi, bổ sung, bãi bỏ một số điều của Luật giáo dục đại học số 08/2012/QH13 như sau:",
        "3. Bãi bỏ điểm a khoản 2 Điều 5, đoạn 2 khoản 1 Điều 27 và điểm a khoản 1 Điều 38.",
    ]
    (t,) = trich_van_ban(dong, "08/2012/QH13")
    assert (t.vi_tri, t.dieu_khoan) == ("Điều 77 khoản 3", ["Điều 5 > Khoản 2 > Điểm a", "Điều 38 > Khoản 1 > Điểm a"])
    assert t.trich.startswith("Điều 77. Sửa đổi, bổ sung, bãi bỏ một số điều của Luật giáo dục đại học Sửa đổi")


def test_luat_sua_mot_van_ban_dieu_khong_nhac_so_hieu():
    dong = [
        "Quốc hội ban hành Luật sửa đổi, bổ sung một số điều của Luật bảo hiểm y tế số 25/2008/QH12.",
        "Điều 1.",
        "Sửa đổi, bổ sung một số điều của Luật bảo hiểm y tế:",
        "16. Bãi bỏ khoản 10 và khoản 12 Điều 23; sửa đổi, bổ sung khoản 7 và khoản 9 Điều 23 như sau:",
    ]
    (t,) = trich_van_ban(dong, "25/2008/QH12")
    assert (t.vi_tri, t.dieu_khoan) == ("Điều 1 khoản 16", ["Điều 23 > Khoản 10", "Điều 23 > Khoản 12"])
    # Lời ban hành nêu HAI văn bản: không suy được Điều 1 sửa văn bản nào.
    hai = [
        "Quốc hội ban hành Luật sửa đổi, bổ sung một số điều của Luật số 25/2008/QH12 và Luật số 46/2014/QH13.",
        *dong[1:],
    ]
    assert trich_van_ban(hai, "25/2008/QH12") == []


def test_doan_neu_van_ban_khac_khong_so_hieu_la_ranh_gioi():
    dong = ["2. Bãi bỏ khoản 2 Điều 5; Điều 7 của Luật đất đai; khoản 3 Điều 9 Nghị định số 25/2008/QH12."]
    assert [t.dieu_khoan for t in trich_van_ban(dong, "25/2008/QH12")] == [["Điều 9 > Khoản 3"]]


def test_cau_dan_co_dau_hai_cham_va_ngay_rieng():
    dong = [
        "Điều 44. Hiệu lực thi hành",
        "2. Kể từ ngày 01 tháng 7 năm 2025, các Nghị định của Chính phủ và các điều khoản sau đây hết hiệu lực thi hành:",
        "a) Nghị định số 115/2015/NĐ-CP ngày 11 tháng 11 năm 2015 của Chính phủ;",
        "c) Khoản 2 Điều 3; các khoản 1, 3 Điều 7 và khoản 2 Điều 8 của Nghị định số 135/2020/NĐ-CP ngày 18 tháng 11"
        " năm 2020 của Chính phủ quy định về tuổi nghỉ hưu.",
    ]
    (t,) = trich_van_ban(dong, "135/2020/NĐ-CP")
    assert t.dieu_khoan == ["Điều 3 > Khoản 2", "Điều 7 > Khoản 1", "Điều 7 > Khoản 3", "Điều 8 > Khoản 2"]
    assert t.tu_ngay == date(2025, 7, 1)
    assert trich_van_ban(_151, "101/2024/NĐ-CP")[0].tu_ngay is None  # "kể từ ngày Nghị định này có hiệu lực"


# ── Ứng viên: văn bản đi SỬA cũng bãi bỏ điều khoản (loai 20) ────────────────


def test_ung_vien_doc_ca_loai_20_nguoc_chieu_va_loai_23_xuoi_chieu():
    """49/2026/NĐ-CP và 226/2025/NĐ-CP bãi bỏ điều khoản của 101/102/2024 qua cạnh loai 20 (from SỬA
    to); loai 23 thì from bị to khai tử một phần. Cặp luôn là (bị bãi bỏ, đi bãi bỏ), bị bãi bỏ phải hiện."""
    canh = [
        (23, "169188", "178259"),
        (20, "187157", "169188"),
        (20, "187157", "168381"),  # 71/2024/NĐ-CP không được hiện
        (23, "168381", "178259"),
    ]
    cap = cap_ung_vien(canh, frozenset({"169188", "169363"}))
    assert ("169188", "178259") in cap and ("169188", "187157") in cap
    assert not any(d == "168381" for d, _ in cap)
    assert {(d, r) for d, r, *_ in DOI_CHIEU_TAY} <= set(cap)


# ── Đối chiếu tay: câu parser cố ý không đọc, kiểm lại nguyên văn mỗi lần sinh seed ──

# 49/2026/NĐ-CP Điều 16 (gateway 187157) và 226/2025/NĐ-CP Điều 7 (gateway 181906), nguyên văn.
_49_226 = [
    "Điều 16. Hiệu lực thi hành",
    "3. Các quy định sau đây hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành:",
    "c) Khoản 2 Điều 30; Điều 32; Điều 33; Điều 34; Điều 50; khoản 5 Điều 54 và Điều 65 của Nghị định số"
    " 102/2024/NĐ-CP;",
    "d) Khoản 4 Điều 77 của Nghị định số 102/2024/NĐ-CP (đã được sửa đổi, bổ sung tại khoản 12 Điều 4 của Nghị"
    " định số 226/2025/NĐ-CP);",
    "3. Thay thế, bổ sung, bãi bỏ các điều, từ, cụm từ tại Nghị định số 101/2024/NĐ-CP",
    "c) Bãi bỏ điều, các từ, cụm từ như sau:",
    "- Điều 7;",
    "- Cụm từ “cơ quan có chức năng quản lý đất đai cấp huyện” tại điểm b khoản 1 Điều 8;",
    "4. Thay thế, bổ sung, bãi bỏ các điểm, từ, cụm từ, mẫu tại Nghị định số 102/2024/NĐ-CP",
    "c) Bãi bỏ một số điểm, khoản, cụm từ, mẫu như sau:",
    "- Điểm b khoản 1 Điều 69;",
]


def test_doi_chieu_tay_49_2026_diem_d_va_226_2025_gach_dau_dong():
    # Parser bỏ đúng ba câu này: "(đã được sửa đổi …)" và mục gạch đầu dòng không nêu số hiệu.
    assert [t.dieu_khoan for t in trich_van_ban(_49_226, "102/2024/NĐ-CP")] == [
        ["Điều 30 > Khoản 2", "Điều 32", "Điều 33", "Điều 34", "Điều 50", "Điều 54 > Khoản 5", "Điều 65"]
    ]
    assert trich_van_ban(_49_226, "101/2024/NĐ-CP") == []
    (d,) = trich_tay(_49_226, "169363", "187157")
    assert (d.vi_tri, d.dieu_khoan, d.kiem_boi) == ("Điều 16 khoản 3 điểm d", ["Điều 77 > Khoản 4"], "doi-chieu-tay")
    assert d.trich.startswith("3. Các quy định sau đây hết hiệu lực") and d.trich.endswith("226/2025/NĐ-CP);")
    (a,) = trich_tay(_49_226, "169188", "181906")
    assert (a.vi_tri, a.dieu_khoan) == ("Điều 7 khoản 3 điểm c", ["Điều 7"])
    assert a.trich.endswith("c) Bãi bỏ điều, các từ, cụm từ như sau: … - Điều 7;")
    (b,) = trich_tay(_49_226, "169363", "181906")
    assert b.dieu_khoan == ["Điều 69 > Khoản 1 > Điểm b"]
    assert trich_tay(_49_226, "169188", "187157") == []


def test_doi_chieu_tay_dung_khi_nguyen_van_khong_con_khop():
    lech = [x.replace("- Điều 7;", "- Điều 8;") for x in _49_226]
    with pytest.raises(ValueError, match="nguyên văn"):
        trich_tay(lech, "169188", "181906")


# ── `hang_seed` trên một kết nối giả: ngày, đối chiếu tay, kiem_boi ─────────


class _KetQua(list):
    def mappings(self):
        return self

    def scalars(self):
        return self


class _Conn:
    """Đủ hai truy vấn của `hang_seed`; toàn văn đi bãi bỏ đọc từ tệp JSON gateway."""

    def __init__(self, van_ban, duong_dan):
        self.van_ban, self.duong_dan = van_ban, duong_dan

    def execute(self, sql, p):
        if "FROM documents" in str(sql):
            return _KetQua(self.van_ban[i] for i in p["ids"])
        return _KetQua(self.duong_dan[p["i"]])


def _gateway(thu_muc, doc_id, dong):
    html = "".join(f"<p>{x}</p>" for x in dong)
    (thu_muc / f"{doc_id}.json").write_text(json.dumps({"documentContent": {"content": html}}), encoding="utf-8")


def _vb(i, so, ngay):
    return {"id": i, "so_ky_hieu": so, "ngay_hieu_luc": ngay, "link_vbpl": f"https://vbpl.vn/van-ban/chi-tiet/{i}"}


def test_hang_seed_nhan_bai_bo_cung_ngay_hieu_luc_va_dong_doi_chieu_tay(tmp_path):
    """12/2017/QH14 bãi bỏ BLHS 100/2015/QH13 Điều 292 từ 01/01/2018 — đúng ngày BLHS có hiệu lực:
    cùng ngày là hợp lệ; chỉ ngày TRƯỚC văn bản mới là dấu hiệu đọc nhầm."""
    _gateway(
        tmp_path,
        "122826",
        [
            "Điều 1. Sửa đổi, bổ sung, bãi bỏ một số điều của Bộ luật Hình sự số 100/2015/QH13",
            "141. Bãi bỏ Điều 292 .",
        ],
    )
    _gateway(tmp_path, "181906", _49_226)
    conn = _Conn(
        {
            "96122": _vb("96122", "100/2015/QH13", date(2018, 1, 1)),
            "122826": _vb("122826", "12/2017/QH14", date(2018, 1, 1)),
            "169188": _vb("169188", "101/2024/NĐ-CP", date(2024, 8, 1)),
            "181906": _vb("181906", "226/2025/NĐ-CP", date(2025, 8, 15)),
        },
        {"96122": ["100/2015/QH13 > Điều 292"], "169188": ["101/2024/NĐ-CP > Điều 7"]},
    )
    hang, bo = hang_seed(
        conn, [("96122", "122826"), ("169188", "181906")], (tmp_path,), datetime(2026, 9, 30, tzinfo=UTC)
    )
    assert bo == []
    assert [(h["van_ban"], h["dieu_khoan"], h["tu_ngay"], h["kiem_boi"]) for h in hang] == [
        ("100/2015/QH13", ["Điều 292"], date(2018, 1, 1), "trich-bai-bo"),
        ("101/2024/NĐ-CP", ["Điều 7"], date(2025, 8, 15), "doi-chieu-tay"),
    ]
    conn.van_ban["122826"]["ngay_hieu_luc"] = date(2017, 12, 31)
    hang, bo = hang_seed(conn, [("96122", "122826")], (tmp_path,), datetime(2026, 9, 30, tzinfo=UTC))
    assert hang == [] and "không sau văn bản" in bo[0][2]
