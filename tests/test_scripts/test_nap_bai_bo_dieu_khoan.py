"""`scripts.nap_bai_bo_dieu_khoan` — seed điều khoản bị bãi bỏ (quyết định 2026-09-30 mục 9,
migration 043). Thuần: không chạm DB hay mạng."""

from datetime import UTC, date, datetime

import pytest

from scripts.nap_bai_bo_dieu_khoan import SEED, doc_seed, kiem_hang, phan_giai

BAY_GIO = datetime(2026, 9, 30, 12, tzinfo=UTC)
HANG = {
    "van_ban": "101/2024/NĐ-CP",
    "van_ban_id": "169188",
    "boi": "151/2025/NĐ-CP",
    "boi_id": "178259",
    "boi_dieu_khoan": "Điều 21 khoản 4 điểm b",
    "dieu_khoan": ["Điều 9 > Khoản 5", "Điều 21"],
    "trich": "4. Các quy định sau đây hết hiệu lực … b) Khoản 5 và khoản 11 Điều 9; … Nghị định số 101/2024/NĐ-CP;",
    "url": "https://vbpl.vn/van-ban/chi-tiet/178259",
    "tu_ngay": date(2025, 7, 1),
    "kiem_boi": "trich-bai-bo",
    "kiem_luc": datetime(2026, 9, 30, 8, tzinfo=UTC),
}


def test_kiem_hang_nhan_dong_du():
    assert kiem_hang(1, HANG, BAY_GIO) == HANG


@pytest.mark.parametrize(
    ("sua", "loi"),
    [
        ({"trich": "x" * 2001}, "trich"),
        ({"trich": " "}, "trich"),
        ({"url": "https://thuvienphapluat.vn/x"}, "url"),  # trang thương mại
        ({"dieu_khoan": []}, "dieu_khoan"),
        ({"dieu_khoan": ["khoản 5 Điều 9"]}, "dieu_khoan"),  # phải là dạng `duong_dan`
        ({"dieu_khoan": ["Điều 9 > Khoản 5", "Điều 9 > Khoản 5"]}, "dieu_khoan"),
        ({"tu_ngay": "2025-07-01"}, "tu_ngay"),
        ({"boi_dieu_khoan": ""}, "boi_dieu_khoan"),
        ({"kiem_luc": datetime(2026, 10, 1, tzinfo=UTC)}, "kiem_luc"),
        ({"ghi_chu": "x"}, "khoá"),
    ],
)
def test_kiem_hang_tu_choi(sua, loi):
    with pytest.raises(ValueError, match=loi):
        kiem_hang(1, {**HANG, **sua}, BAY_GIO)


def test_seed_da_commit_hop_le_va_co_101_102_2024():
    hang = doc_seed(SEED)
    theo = {(h["van_ban_id"], h["boi_id"]): h for h in hang}
    assert {"Điều 9 > Khoản 5", "Điều 30", "Điều 60"} <= set(theo["169188", "178259"]["dieu_khoan"])
    assert {"Điều 106", "Điều 107", "Điều 94 > Khoản 2 > Điểm c"} <= set(theo["169363", "178259"]["dieu_khoan"])
    assert all(h["boi_dieu_khoan"].startswith("Điều 21 khoản 4") for k, h in theo.items() if k[1] == "178259")


def test_phan_giai_theo_van_ban_va_duong_dan():
    dieu_khoan = {("169188", "Điều 9 > Khoản 5"): [11], ("169188", "Điều 21"): [22]}
    ra = phan_giai([HANG], dieu_khoan, {"169188": "101/2024/NĐ-CP", "178259": "151/2025/NĐ-CP"})
    assert [(r["provision_id"], r["boi_document_id"], r["tu_ngay"]) for r in ra] == [
        (11, "178259", date(2025, 7, 1)),
        (22, "178259", date(2025, 7, 1)),
    ]


@pytest.mark.parametrize(
    ("dieu_khoan", "van_ban", "loi"),
    [
        ({("169188", "Điều 9 > Khoản 5"): [11]}, {"169188": "101/2024/NĐ-CP", "178259": "x"}, "Điều 21"),
        (
            {("169188", "Điều 9 > Khoản 5"): [11], ("169188", "Điều 21"): [22]},
            {"169188": "102/2024/NĐ-CP", "178259": "x"},
            "số hiệu",
        ),
        ({("169188", "Điều 9 > Khoản 5"): [11], ("169188", "Điều 21"): [22]}, {"169188": "101/2024/NĐ-CP"}, "178259"),
    ],
    ids=["dieu-khoan-khong-co", "id-khac-so-hieu", "van-ban-di-bai-bo-khong-co"],
)
def test_phan_giai_khong_doan(dieu_khoan, van_ban, loi):
    with pytest.raises(ValueError, match=loi):
        phan_giai([HANG], dieu_khoan, van_ban)
