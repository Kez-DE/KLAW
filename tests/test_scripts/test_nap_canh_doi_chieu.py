"""`scripts.nap_canh_doi_chieu` — seed cạnh đã đối chiếu nguyên văn (quyết định
2026-09-28 mục 12, migration 039). Thuần: không chạm DB hay mạng."""

from datetime import UTC, datetime

import pytest

from scripts.nap_canh_doi_chieu import SEED, doc_seed, kiem_hang, phan_giai

BAY_GIO = datetime(2026, 9, 29, 12, tzinfo=UTC)
HANG = {
    "from_so_ky_hieu": "283/2026/NĐ-CP",
    "to_so_ky_hieu": "12/2022/NĐ-CP",
    "loai": 21,
    "dieu_khoan": "283/2026/NĐ-CP Điều 66 khoản 4",
    "trich": "Nghị định số 12/2022/NĐ-CP … hết hiệu lực thi hành kể từ ngày Nghị định này có hiệu lực thi hành",
    "url": "https://vbpl.vn/van-ban/chi-tiet/787d3780-866f-11f1-8511-612429c9d15e",
    "kiem_boi": "doi-chieu-nguyen-van-k8",
    "kiem_luc": datetime(2026, 9, 29, 3, tzinfo=UTC),
}


def test_kiem_hang_nhan_dong_du():
    assert kiem_hang(1, HANG, BAY_GIO) == HANG


@pytest.mark.parametrize(
    ("sua", "loi"),
    [
        ({"trich": "x" * 401}, "trich"),
        ({"trich": " "}, "trich"),
        ({"url": "http://vbpl.vn/x"}, "url"),
        ({"url": "https://thuvienphapluat.vn/van-ban/x"}, "url"),  # trang thương mại
        ({"loai": 12}, "loai"),
        ({"dieu_khoan": ""}, "dieu_khoan"),
        ({"kiem_boi": None}, "kiem_boi"),
        ({"kiem_luc": datetime(2026, 9, 30, tzinfo=UTC)}, "kiem_luc"),
        ({"kiem_luc": datetime(2026, 9, 28)}, "kiem_luc"),  # không múi giờ
        ({"ghi_chu": "x"}, "khoá"),
    ],
)
def test_kiem_hang_tu_choi(sua, loi):
    with pytest.raises(ValueError, match=loi):
        kiem_hang(1, {**HANG, **sua}, BAY_GIO)


def test_seed_da_commit_hop_le_va_khong_trung_khoa():
    hang = doc_seed(SEED)
    assert len(hang) >= 40
    assert len({(h["from_so_ky_hieu"], h["to_so_ky_hieu"], h["loai"]) for h in hang}) == len(hang)


def test_seed_trung_khoa_la_loi(tmp_path):
    import yaml

    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump([HANG, HANG], allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="trùng"):
        doc_seed(p)


def test_phan_giai_theo_so_hieu_va_loai():
    id_theo_so = {"283/2026/NĐ-CP": ["u283"], "12/2022/NĐ-CP": ["153913"]}
    canh = {("u283", "153913", 21): [5699708]}
    assert phan_giai([HANG], id_theo_so, canh) == {5699708: HANG}


@pytest.mark.parametrize(
    ("id_theo_so", "canh", "loi"),
    [
        ({"283/2026/NĐ-CP": ["u283"], "12/2022/NĐ-CP": ["a", "b"]}, {}, "khớp"),  # số hiệu mơ hồ
        ({"283/2026/NĐ-CP": ["u283"], "12/2022/NĐ-CP": ["153913"]}, {}, "0 cạnh"),  # cạnh không còn
    ],
)
def test_phan_giai_khong_doan(id_theo_so, canh, loi):
    with pytest.raises(ValueError, match=loi):
        phan_giai([HANG], id_theo_so, canh)
