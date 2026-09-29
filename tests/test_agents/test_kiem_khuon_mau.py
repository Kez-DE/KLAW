"""`hieu_tai_lieu.kiem_khuon_mau` và lược đồ v3 — thiết kế `khuon-mau-thiet-ke.md` §6.

Phép kiểm 0 token, thuần: ra khỏi đây chữ điều khoản không mang số điều luật, số
hiệu văn bản, danh tính, giá trị không nguồn, giữ chỗ của mô hình hay dãy chấm lạc —
và một lượt TẠO luôn có đủ điều luật đòi (để trống, không bịa).
"""

import pytest

from src.agents.nodes import hieu_tai_lieu as h
from src.services import khuon_mau as km

NG_TQ = {"loai": None, "sua": False, "khoa": [], "muc": []}
NG_HDLD = {
    "loai": "hdld",
    "sua": False,
    "tieu_de": "HỢP ĐỒNG LAO ĐỘNG",
    "bo_cuc": "hop_dong",
    "ben": [{"khoa": "nsdld", "vai": "BÊN A"}, {"khoa": "nld", "vai": "BÊN B"}],
    "khoa": ["cong_viec", "thoi_han", "luong", "nang_luong", "thoi_gio", "bao_ho", "bao_hiem", "dao_tao"],
    "bat_buoc": ["cong_viec", "thoi_han", "luong", "nang_luong", "thoi_gio", "bao_ho", "bao_hiem", "dao_tao"],
    "can_cu": [],
}
NGUON = "soạn hợp đồng thuê nhà giữa tôi Nguyễn Văn An và Trần Thị Bình, giá thuê 5.000.000 đồng/tháng"


def _ra(**kw) -> dict:
    ra = {
        "muc_tieu": "ban_moi",
        "tieu_de": "Hợp đồng thuê tài sản",
        "trich_yeu": None,
        "bo_cuc": "hop_dong",
        "ben": [{"khoa": "ben_a", "vai": "Bên cho thuê", "loai": "ca_nhan"}],
        "can_cu": ["91/2015/QH13"],
        "gia_tri": [],
        "dieu": [],
        "sua_dieu": None,
        "khong_dat": [],
    }
    ra.update(kw)
    return ra


def _dieu(*doan: str, ten: str = "Giá thuê", key=None) -> dict:
    return {"key": key, "ten": ten, "doan": list(doan)}


def _kiem(ra: dict, ng: dict = NG_TQ, ten_cu=()):
    return h.kiem_khuon_mau(ra, ng, NGUON, [], list(ten_cu))


def test_so_dau_ten_dieu_bi_bo_dieu_giu_lai():
    kq = _kiem(_ra(dieu=[_dieu("Giá thuê là 5.000.000 đồng/tháng.", ten="Điều 3. Giá thuê")]))
    assert kq["dieu"] == [{"key": None, "ten": "Giá thuê", "doan": ["Giá thuê là 5.000.000 đồng/tháng."]}]


def test_doan_dau_lap_lai_ten_bi_bo():
    kq = _kiem(_ra(dieu=[_dieu("Điều 3. Giá thuê", "Giá thuê do hai bên thỏa thuận.", ten="Giá thuê")]))
    assert kq["dieu"][0]["doan"] == ["Giá thuê do hai bên thỏa thuận."]


def test_khoan_n_dieu_nay_duoc_giu_so_khong_bi_xoa():
    kq = _kiem(_ra(dieu=[_dieu("Bên thuê trả tiền theo quy định tại khoản 2 Điều này.")]))
    assert kq["dieu"][0]["doan"] == ["Bên thuê trả tiền theo quy định tại khoản 2 Điều này."]


def test_dan_chieu_dieu_khac_viet_lai_theo_ten():
    kq = _kiem(
        _ra(
            dieu=[
                _dieu("Bên A giao tài sản.", ten="Tài sản thuê"),
                _dieu("Thực hiện nghĩa vụ tại Điều 1 Hợp đồng này.", ten="Nghĩa vụ"),
            ]
        )
    )
    assert kq["dieu"][1]["doan"] == ["Thực hiện nghĩa vụ tại Điều về tài sản thuê."]


def test_dan_so_dieu_luat_chi_bo_dung_doan_do_va_neu_ten():
    kq = _kiem(_ra(dieu=[_dieu("Hai bên thỏa thuận giá thuê.", "Theo Điều 473 Bộ luật Dân sự, bên thuê trả tiền.")]))
    assert kq["dieu"][0]["doan"] == ["Hai bên thỏa thuận giá thuê."]
    assert any("Điều 1" in g for g in kq["ghi_chu"])


@pytest.mark.parametrize("cho", ["[Tên Bên A]", "[Thông tin về Bên A…]", "[số tiền]", "<họ tên>", "[…]", "{gia}"])
def test_giu_cho_cua_mo_hinh_thanh_dau_cho(cho):
    kq = _kiem(_ra(dieu=[_dieu(f"Bên cho thuê là {cho} cam kết.")]))
    assert kq["dieu"][0]["doan"] == [f"Bên cho thuê là {km.CHO} cam kết."]
    assert kq["dem"]["cho_mo_hinh"] == 1


def test_dau_ba_cham_le_va_day_cham():
    kq = _kiem(_ra(dieu=[_dieu("Chi phí điện, nước, internet…", "Tiền cọc ……… đồng.")]))
    assert kq["dieu"][0]["doan"] == ["Chi phí điện, nước, internet.", f"Tiền cọc {km.CHO} đồng."]


def test_so_khong_nguon_thanh_dau_cho():
    kq = _kiem(_ra(dieu=[_dieu("Giá thuê 9.000.000 đồng, cọc 5.000.000 đồng.")]))
    assert kq["dieu"][0]["doan"] == [f"Giá thuê {km.CHO} đồng, cọc 5.000.000 đồng."]


def test_key_la_bi_doc_thanh_null():
    kq = _kiem(_ra(dieu=[_dieu("Công việc: lập trình viên.", key="cong_viec"), _dieu("x y z.", key="bia")]), NG_HDLD)
    khoa = [d["key"] for d in kq["dieu"]]
    assert "bia" not in khoa and khoa[0] == "cong_viec"


def test_tao_chen_muc_bat_buoc_con_thieu_voi_dau_cho():
    kq = _kiem(_ra(dieu=[_dieu("Làm việc tại văn phòng.", ten="Công việc", key="cong_viec")]), NG_HDLD)
    chen = [d for d in kq["dieu"] if d.get("chen")]
    assert {d["key"] for d in chen} >= {"thoi_han", "luong"}
    assert all(d["doan"] == [km.CHO] for d in chen)


def test_sua_khong_chen_muc_thieu_chi_la_phat_hien():
    ng = {**NG_HDLD, "sua": True, "khung_cu": {"loai": "hdld", "tieu_de": "HỢP ĐỒNG LAO ĐỘNG", "ben": []}}
    kq = _kiem(_ra(muc_tieu="sua_ban_dang_co", dieu=[_dieu("Làm việc tại văn phòng.", key="cong_viec")]), ng)
    assert not any(d.get("chen") for d in kq["dieu"]) and "luong" in kq["hoan_thanh"]["thieu"]


def test_vuot_ngan_sach_bo_dieu_khong_bat_buoc_tu_cuoi_va_neu_ten(monkeypatch):
    monkeypatch.setattr(km, "NGAN_SACH_KY_TU", 60)
    dieu = [
        _dieu("Công việc là lập trình viên phần mềm.", ten="Công việc", key="cong_viec"),
        _dieu("Hai bên giữ bí mật mọi thông tin của nhau.", ten="Bảo mật"),
        _dieu("Tranh chấp giải quyết bằng thương lượng.", ten="Tranh chấp"),
    ]
    kq = _kiem(_ra(dieu=dieu), {**NG_HDLD, "bat_buoc": ["cong_viec"]})
    ten = [d["ten"] for d in kq["dieu"] if not d.get("chen")]
    assert ten == ["Công việc"], ten
    assert any("Tranh chấp" in g for g in kq["ghi_chu"]) and any("Bảo mật" in g for g in kq["ghi_chu"])


def test_gia_tri_loc_ben_va_truong_la():
    kq = _kiem(
        _ra(
            gia_tri=[
                {"ben": "ben_a", "truong": "ho_ten", "gia_tri": "Nguyễn Văn An"},
                {"ben": "ben_z", "truong": "ho_ten", "gia_tri": "X"},
                {"ben": "ben_a", "truong": "bia", "gia_tri": "Y"},
            ]
        )
    )
    assert kq["gia_tri"] == [{"ben": "ben_a", "truong": "ho_ten", "gia_tri": "Nguyễn Văn An"}]


def test_sua_dieu_ngoai_pham_vi_hoi_lai_dieu_nao():
    ng = {**NG_TQ, "sua": True, "khung_cu": {"tieu_de": "HỢP ĐỒNG", "ben": []}}
    ra = _ra(
        muc_tieu="sua_ban_dang_co",
        dieu=None,
        sua_dieu=[{"thao_tac": "thay", "dieu": 9, "key": None, "ten": "X", "doan": ["y."]}],
    )
    kq = _kiem(ra, ng, ten_cu=["Tài sản", "Giá thuê"])
    assert kq["sua_dieu"] == [] and h.CHUA_RO_DIEU in kq["ghi_chu"]


def test_sua_dieu_giu_thao_tac_hop_le():
    ng = {**NG_TQ, "sua": True, "khung_cu": {"tieu_de": "HỢP ĐỒNG", "ben": []}}
    ra = _ra(
        muc_tieu="sua_ban_dang_co",
        dieu=None,
        sua_dieu=[
            {"thao_tac": "xoa", "dieu": 2, "key": None, "ten": None, "doan": None},
            {"thao_tac": "them_sau", "dieu": 0, "key": None, "ten": "Phạt vi phạm", "doan": ["Bên vi phạm chịu phạt."]},
        ],
    )
    kq = _kiem(ra, ng, ten_cu=["Tài sản", "Giá thuê"])
    assert kq["sua_dieu"] == [
        {"thao_tac": "xoa", "dieu": 2},
        {"thao_tac": "them_sau", "dieu": 0, "key": None, "ten": "Phạt vi phạm", "doan": ["Bên vi phạm chịu phạt."]},
    ]


def test_luoc_do_khong_sua_chi_ban_moi_va_sua_dieu_null():
    s = h.schema_khuon_mau(False)
    assert s["properties"]["muc_tieu"]["enum"] == ["ban_moi"]
    assert s["properties"]["sua_dieu"] == {"type": "null"}
    s2 = h.schema_khuon_mau(True, ["luong"])
    assert s2["properties"]["muc_tieu"]["enum"] == ["ban_moi", "sua_ban_dang_co"]
    assert set(s2["required"]) == set(s2["properties"])


def test_tu_soan_khung_tu_loi_mo_hinh_sua_khoa_ben():
    kq = _kiem(
        _ra(
            ben=[
                {"khoa": "Bên A!", "vai": "Bên cho thuê", "loai": "ca_nhan"},
                {"khoa": "van_ban", "vai": "x", "loai": "ca_nhan"},
            ]
        )
    )
    assert kq["khung"]["ben"] == [{"khoa": "ben_a", "vai": "Bên cho thuê", "loai": "ca_nhan"}]
    assert kq["khung"]["can_cu_so"] == ["91/2015/QH13"] and kq["khung"]["bo_cuc"] == "hop_dong"


def test_don_chi_nhan_muc_cua_mau():
    ng = {
        "loai": "don_khoi_kien",
        "sua": False,
        "khoa": ["yeu_cau", "tai_lieu", "thong_tin_khac"],
        "khoa_than": ["yeu_cau", "tai_lieu", "thong_tin_khac"],
        "co_dieu": False,
        "ben": [],
        "bat_buoc": [],
    }
    kq = _kiem(_ra(dieu=[_dieu("Buộc trả tiền.", ten="Yêu cầu", key="yeu_cau"), _dieu("Lan man.", ten="Khác")]), ng)
    assert [d["key"] for d in kq["dieu"] if not d.get("chen")] == ["yeu_cau"]
    assert any("Khác" in g for g in kq["ghi_chu"])
