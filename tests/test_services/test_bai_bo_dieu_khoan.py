"""Điều khoản bị bãi bỏ (quyết định 2026-09-30 mục 9) — phần THUẦN, 0 DB, 0 LLM.

`effectivity.bai_bo_tai` là nơi phán điều khoản đã bị bãi bỏ tại `as_of` chưa (và
hậu duệ của nó theo cùng); `hien_thi.an_bai_bo_tren_trang` là thân trang văn bản:
điều khoản bị bãi bỏ còn số hiệu, tiêu đề và câu "Đã bị bãi bỏ bởi … từ …" kèm văn bản
đi bãi bỏ, không còn nội dung; hậu duệ của nó không hiện.
"""

from datetime import date

from src.services.effectivity import BaiBo, VanBanNeu, bai_bo_tai
from src.services.hien_thi import an_bai_bo_tren_trang, bai_bo_ra

_151 = VanBanNeu("178259", "151/2025/NĐ-CP")


def _dong(pid: int, goc: int, tu_ngay: date, boi: str = "178259", so: str = "151/2025/NĐ-CP") -> dict:
    return {
        "provision_id": pid,
        "goc": goc,
        "boi_document_id": boi,
        "boi_so_ky_hieu": so,
        "boi_dieu_khoan": "Điều 21 khoản 4 điểm c",
        "tu_ngay": tu_ngay,
    }


def test_chi_bai_bo_khi_da_toi_ngay_va_hau_due_theo_cung():
    rows = [_dong(107, 107, date(2025, 7, 1)), _dong(1071, 107, date(2025, 7, 1))]
    assert bai_bo_tai(rows, date(2025, 6, 30)) == {}
    ra = bai_bo_tai(rows, date(2026, 9, 30))
    assert ra == {
        107: BaiBo(_151, "Điều 21 khoản 4 điểm c", date(2025, 7, 1), 107),
        1071: BaiBo(_151, "Điều 21 khoản 4 điểm c", date(2025, 7, 1), 107),
    }


def test_nhieu_van_ban_cung_bai_bo_lay_lan_dau_va_dong_cua_chinh_no():
    rows = [
        _dong(5, 9, date(2025, 7, 1)),  # qua tổ tiên 9
        _dong(5, 5, date(2025, 7, 1), "x", "số: 12/2026/NĐ-CP"),  # nêu đích danh, cùng ngày
        _dong(5, 5, date(2020, 1, 1), "y", "1/2020/NĐ-CP"),  # sớm hơn
    ]
    assert bai_bo_tai(rows, date(2026, 9, 30))[5].boi == VanBanNeu("y", "1/2020/NĐ-CP")
    assert bai_bo_tai(rows[:2], date(2026, 9, 30))[5] == BaiBo(
        VanBanNeu("x", "12/2026/NĐ-CP"), "Điều 21 khoản 4 điểm c", date(2025, 7, 1), 5
    )


_VB = {
    "id": "178259",
    "so_ky_hieu": "151/2025/NĐ-CP",
    "loai_van_ban": "Nghị định",
    "ten": "Nghị định số 151/2025/NĐ-CP Quy định về phân định thẩm quyền",
    "link_vbpl": "https://vbpl.vn/van-ban/chi-tiet/178259",
    "link_chinhphu": None,
}  # noqa: E501


def test_bai_bo_ra_cho_nguoi_doc():
    b = BaiBo(_151, "Điều 21 khoản 4 điểm c", date(2025, 7, 1), 107)
    ra = bai_bo_ra(b, _VB, frozenset({"178259"}))
    assert ra["boi_dieu_khoan"] == "Điều 21 khoản 4 điểm c"
    assert ra["ten_goi"] == "Nghị định số 151/2025/NĐ-CP"
    assert ra["tu_ngay"] == date(2025, 7, 1)
    assert ra["van_ban"]["doc_id"] == "178259" and ra["van_ban"]["lien_ket"] == _VB["link_vbpl"]
    # Văn bản đi bãi bỏ đang ẩn: không mời mở trang 404; không có trong kho: vẫn nêu số hiệu.
    assert bai_bo_ra(b, _VB, frozenset())["van_ban"]["doc_id"] is None
    assert bai_bo_ra(b, None, frozenset())["ten_goi"] == "151/2025/NĐ-CP"


def test_than_trang_an_noi_dung_va_hau_due_giu_phan_con_lai():
    rows = [
        {"id": 9, "cap": "dieu", "so_hieu_cap": "9", "tieu_de": "Điều 9. Đăng ký", "noi_dung": "Điều 9. Đăng ký"},
        {"id": 95, "cap": "khoan", "so_hieu_cap": "5", "tieu_de": "Khoản 5", "noi_dung": "5. Nội dung đã bãi bỏ"},
        {"id": 951, "cap": "diem", "so_hieu_cap": "a", "tieu_de": "Điểm a", "noi_dung": "a) Cũng đã bãi bỏ"},
        {"id": 96, "cap": "khoan", "so_hieu_cap": "6", "tieu_de": "Khoản 6", "noi_dung": "6. Còn hiệu lực"},
        {"id": 21, "cap": "dieu", "so_hieu_cap": "21", "tieu_de": "Điều 21. Cấp", "noi_dung": "Điều 21. Cấp …"},
        {"id": 211, "cap": "khoan", "so_hieu_cap": "1", "tieu_de": "Khoản 1", "noi_dung": "1. Đã bãi bỏ cùng Điều"},
    ]
    b = {
        95: BaiBo(_151, "Điều 21 khoản 4 điểm b", date(2025, 7, 1), 95),
        951: BaiBo(_151, "Điều 21 khoản 4 điểm b", date(2025, 7, 1), 95),
        21: BaiBo(_151, "Điều 21 khoản 4 điểm b", date(2025, 7, 1), 21),
        211: BaiBo(_151, "Điều 21 khoản 4 điểm b", date(2025, 7, 1), 21),
    }
    ra = an_bai_bo_tren_trang(rows, b, lambda x: {"goc": x.goc})
    assert [r["id"] for r in ra] == [9, 95, 96, 21]
    assert [r.get("bai_bo") for r in ra] == [None, {"goc": 95}, None, {"goc": 21}]
    assert ra[1]["noi_dung"] == "" and ra[3]["noi_dung"] == "" and ra[3]["tieu_de"] == "Điều 21. Cấp"
    assert ra[2]["noi_dung"] == "6. Còn hiệu lực"
    # Hậu duệ đứng một mình (tổ tiên không có trên trang): vẫn không lộ nội dung.
    (mot,) = an_bai_bo_tren_trang(rows[2:3], b, lambda x: {"goc": x.goc})
    assert mot["noi_dung"] == "" and mot["bai_bo"] == {"goc": 95}
