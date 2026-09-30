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


def test_tao_chen_muc_bat_buoc_con_thieu_khong_bao_gio_trong():
    kq = _kiem(_ra(dieu=[_dieu("Làm việc tại văn phòng.", ten="Công việc", key="cong_viec")]), NG_HDLD)
    chen = [d for d in kq["dieu"] if d.get("chen")]
    assert {d["key"] for d in chen} >= {"thoi_han", "luong"}
    # Không mục nào của NG_HDLD mang `mau`: câu trung tính gọi tên mục, chừa chỗ điền.
    assert all(
        d["doan"] == [f"Các bên thỏa thuận về {d['ten'][:1].lower()}{d['ten'][1:]} như sau: {km.CHO}"] for d in chen
    )


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
    assert kq["khong_dat"] == ["X", "Y"]


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


# ─── khung mô hình viết (tên loại, trích yếu, vai) qua CÙNG hai lưới ─────────


def test_trich_yeu_dan_so_hieu_bi_bo_va_neu_ten():
    ng = {"loai": "cong_van", "sua": False, "co_trich_yeu": True, "tieu_de": "CÔNG VĂN", "bo_cuc": "hanh_chinh"}
    ty = "V/v thi hành Điều 5 Nghị định 99/2099/NĐ-CP, thanh toán 750 triệu đồng cho ông Trần Văn Bình"
    kq = _kiem(_ra(tieu_de=None, trich_yeu=ty, bo_cuc=None, ben=None, dieu=[_dieu("Đề nghị xem xét.")]), ng)
    assert kq["khung"]["trich_yeu"] is None and any("trích yếu" in g for g in kq["ghi_chu"])


def test_tieu_de_va_vai_dan_so_hay_dinh_danh_bi_bo_ve_mac_dinh():
    kq = _kiem(
        _ra(
            tieu_de="Hợp đồng số 12/2025/HĐ theo Điều 473 Bộ luật Dân sự",
            ben=[{"khoa": "ben_a", "vai": "Ông Trần Văn Bình, CCCD 001099012345", "loai": "ca_nhan"}],
            dieu=[_dieu("Giá thuê do hai bên thỏa thuận.")],
        )
    )
    assert kq["khung"]["tieu_de"] == "Văn bản" and kq["khung"]["ben"][0]["vai"] is None
    assert any("tên văn bản" in g for g in kq["ghi_chu"]) and any("một bên" in g for g in kq["ghi_chu"])
    spec = km.spec_tu(
        {**km.khung_tong_quat("hop_dong", kq["khung"]["ben"]), "loai": None},
        tieu_de=kq["khung"]["tieu_de"],
        trich_yeu=None,
        can_cu=[],
        dieu=kq["dieu"],
    )
    assert spec["ben"][0]["tieu_de"] == "I. BÊN A (sau đây gọi là Bên A):", "vai trống thì khối bên gọi mặc định"


def test_tieu_de_trich_yeu_khong_dan_so_giu_nguyen():
    kq = _kiem(_ra(trich_yeu="Về việc thuê nhà", dieu=[_dieu("Giá thuê do hai bên thỏa thuận.")]))
    assert kq["khung"]["tieu_de"] == "Hợp đồng thuê tài sản" and kq["khung"]["trich_yeu"] == "Về việc thuê nhà"
    assert kq["khung"]["ben"][0]["vai"] == "Bên cho thuê" and kq["ghi_chu"] == []


def test_hanh_chinh_tu_soan_hai_ben_co_dinh_cua_khung_gia_tri_la_vao_khong_dat():
    kq = h.kiem_khuon_mau(
        _ra(
            tieu_de="Thông báo",
            trich_yeu="Về việc nghỉ lễ",
            bo_cuc="hanh_chinh",
            ben=[{"khoa": "cong_ty", "vai": "Công ty", "loai": "to_chuc"}],
            can_cu=[],
            gia_tri=[
                {"ben": "nguoi_ky", "truong": "ho_ten", "gia_tri": "Trần Văn Bình"},
                {"ben": "cong_ty", "truong": "ten_to_chuc", "gia_tri": "Công ty TNHH Minh An"},
            ],
            dieu=[_dieu("Công ty thông báo lịch nghỉ lễ.", ten="")],
        ),
        NG_TQ,
        "thông báo nghỉ lễ, người ký Trần Văn Bình, Công ty TNHH Minh An",
        [],
        [],
    )
    assert [b["khoa"] for b in kq["khung"]["ben"]] == ["co_quan", "nguoi_ky"]
    assert kq["gia_tri"] == [{"ben": "nguoi_ky", "truong": "ho_ten", "gia_tri": "Trần Văn Bình"}]
    assert kq["khong_dat"] == ["Công ty TNHH Minh An"], "giá trị không đặt được thì báo, không bỏ im"
    _, ban_do = km.dung_docx(
        km.spec_tu(
            {**km.khung_tong_quat("hanh_chinh", kq["khung"]["ben"]), "loai": None},
            tieu_de="Thông báo",
            trich_yeu=None,
            can_cu=[],
            dieu=kq["dieu"],
        )
    )
    assert {k for v in ban_do.values() for k in v if k} >= {("nguoi_ky", "ho_ten"), ("co_quan", "ten_to_chuc")}


NG_THUE = {
    "loai": "hop_dong_thue_tai_san",
    "sua": False,
    "tieu_de": "HỢP ĐỒNG THUÊ TÀI SẢN",
    "bo_cuc": "hop_dong",
    "ben": [
        {"khoa": "ben_cho_thue", "vai": "Bên cho thuê", "loai": "tuy", "mac_dinh": "ca_nhan"},
        {"khoa": "ben_thue", "vai": "Bên thuê", "loai": "tuy", "mac_dinh": "ca_nhan"},
    ],
    "khoa": [],
    "bat_buoc": [],
    "can_cu": [],
}


def _loai_ben(kq: dict) -> dict:
    return {b["khoa"]: b.get("loai") for b in kq["khung"]["ben"]}


def test_ben_tuy_loai_theo_loi_mo_hinh_roi_theo_truong_roi_mac_dinh():
    # Mô hình nói thẳng: bên thuê là tổ chức.
    kq = _kiem(_ra(ben=[{"khoa": "ben_thue", "vai": "Bên thuê", "loai": "to_chuc"}]), NG_THUE)
    assert _loai_ben(kq) == {"ben_cho_thue": "ca_nhan", "ben_thue": "to_chuc"}
    # Không nói `ben`, nhưng gán tên tổ chức cho bên thuê: suy từ trường.
    g = [{"ben": "ben_thue", "truong": "ten_to_chuc", "gia_tri": "Công ty TNHH An Phát"}]
    assert _loai_ben(_kiem(_ra(ben=None, gia_tri=g), NG_THUE))["ben_thue"] == "to_chuc"
    # Trường chung của hai loại (điện thoại) không nói gì: mặc định.
    g = [{"ben": "ben_thue", "truong": "dien_thoai", "gia_tri": "0901"}]
    assert _loai_ben(_kiem(_ra(ben=None, gia_tri=g), NG_THUE)) == {"ben_cho_thue": "ca_nhan", "ben_thue": "ca_nhan"}


def test_sua_giu_loai_da_luu_tru_khi_mo_hinh_noi_doi():
    ng = {
        **NG_THUE,
        "sua": True,
        "khung_cu": {
            "loai": "hop_dong_thue_tai_san",
            "ben": [
                {"khoa": "ben_cho_thue", "vai": "Bên cho thuê", "loai": "ca_nhan"},
                {"khoa": "ben_thue", "vai": "Bên thuê", "loai": "to_chuc"},
            ],
        },
    }
    # Một giá trị "họ tên" lẻ không lật bên thuê (đã là tổ chức) sang cá nhân.
    g = [{"ben": "ben_thue", "truong": "ho_ten", "gia_tri": "An"}]
    kq = _kiem(_ra(muc_tieu="sua_ban_dang_co", ben=None, gia_tri=g, dieu=None, sua_dieu=[]), ng)
    assert _loai_ben(kq) == {"ben_cho_thue": "ca_nhan", "ben_thue": "to_chuc"}
    ra = _ra(
        muc_tieu="sua_ban_dang_co",
        ben=[{"khoa": "ben_cho_thue", "vai": "x", "loai": "to_chuc"}],
        dieu=None,
        sua_dieu=[],
    )
    assert _loai_ben(_kiem(ra, ng))["ben_cho_thue"] == "to_chuc"


def test_muc_tuy_chon_ghi_ro_trong_prompt():
    ng = {
        "muc": [
            {"key": "cuoc_phi", "ten": "Cước phí", "trich": ""},
            {"key": "giay_van_tai", "ten": "Giấy vận tải khi vận tải hàng hoá bằng xe ô tô", "trich": ""},
        ],
        "bat_buoc": ["cuoc_phi"],
    }
    khoi = h._khoi_muc_khuon_mau(ng)
    assert "`cuoc_phi` — Cước phí\n" in khoi
    assert "`giay_van_tai` — Giấy vận tải khi vận tải hàng hoá bằng xe ô tô — TUỲ CHỌN" in khoi


# ═══ Số tiền bằng số và bằng chữ là MỘT giá trị (app thật 2026-09-30, bản thảo 91c288d5) ═══
#
# Lượt 1 nói "giá thuê 10 triệu đồng một tháng"; Điều 3 in "Giá thuê là …… đồng (Mười
# triệu đồng) mỗi tháng": lưới giá trị đọc "10 triệu" là 10 nên xoá "10.000.000", còn
# phần chữ (không chữ số) lọt qua. Một giá trị của người hỏi phải điền cả hai dạng, và
# một số không nguồn không được sống sót ở dạng chữ.
NGUON_THUE = (
    "Soạn hợp đồng thuê nhà ở giữa bên cho thuê là ông Nguyễn Văn An và bên thuê là bà Trần Thị Bình,"
    " giá thuê 10 triệu đồng một tháng, thời hạn 12 tháng"
)


def _doan_thue(chu: str) -> list[str]:
    return h.kiem_khuon_mau(_ra(dieu=[_dieu(chu)]), NG_TQ, NGUON_THUE, [], [])["dieu"][0]["doan"]


@pytest.mark.parametrize(
    ("mo_hinh", "ra"),
    [
        # Số và chữ cùng là giá trị người hỏi nói: giữ cả hai.
        (
            "Giá thuê là 10.000.000 đồng (Mười triệu đồng) mỗi tháng.",
            "Giá thuê là 10.000.000 đồng (Mười triệu đồng) mỗi tháng.",
        ),
        # Mô hình để trống phần số mà viết phần chữ: phần số điền từ cùng giá trị ấy.
        (
            f"Giá thuê là {km.CHO} đồng (Mười triệu đồng) mỗi tháng.",
            "Giá thuê là 10.000.000 đồng (Mười triệu đồng) mỗi tháng.",
        ),
        (
            f"Giá thuê là {km.CHO} đồng (bằng chữ: mười triệu đồng).",
            "Giá thuê là 10.000.000 đồng (bằng chữ: mười triệu đồng).",
        ),
        # Số không nguồn: phần số thành chỗ trống, phần chữ cũng vậy — không lọt ở dạng chữ.
        ("Tiền đặt cọc là 20.000.000 đồng (Hai mươi triệu đồng).", f"Tiền đặt cọc là {km.CHO} đồng ({km.CHO})."),
        # Phần chữ nói một số khác phần số: phần chữ thành chỗ trống.
        ("Giá thuê là 10.000.000 đồng (Một trăm triệu đồng).", f"Giá thuê là 10.000.000 đồng ({km.CHO})."),
        # Ngoặc không phải số bằng chữ: không đụng.
        (
            "Giá thuê là 10.000.000 đồng (đã gồm thuế) mỗi tháng.",
            "Giá thuê là 10.000.000 đồng (đã gồm thuế) mỗi tháng.",
        ),
    ],
    ids=["khop", "so_trong_chu_co_nguon", "bang_chu_nhan", "khong_nguon", "chu_lech_so", "ngoac_khac"],
)
def test_so_tien_bang_so_va_bang_chu_mot_gia_tri(mo_hinh, ra):
    assert _doan_thue(mo_hinh) == [ra]


@pytest.mark.parametrize(
    ("chu", "so"),
    [
        ("Mười triệu đồng", 10_000_000),
        ("hai mươi lăm triệu năm trăm nghìn đồng chẵn", 25_500_000),
        ("một tỷ hai trăm triệu", 1_200_000_000),
        ("một trăm linh năm nghìn", 105_000),
        ("ba mươi mốt", 31),
        ("đã gồm thuế", None),
        ("hai ba triệu", None),
    ],
)
def test_doc_so_bang_chu(chu, so):
    assert h.doc_so_chu(chu) == so


# ═══ Điều luật đòi không bao giờ trống (app thật 2026-09-30, bản thảo 91c288d5) ═══
#
# Điều 5 "Giao tài sản thuê" in "……": đoạn của mô hình dẫn số điều luật nên lưới chặn
# bỏ CẢ đoạn, điều không còn gì, và mục bắt buộc được chèn lại với một "……" trơn.
NG_GIAO = {
    "loai": "hop_dong_thue_tai_san",
    "sua": False,
    "ben": [],
    "khoa": ["tai_san_thue", "giao_tai_san"],
    "bat_buoc": ["tai_san_thue", "giao_tai_san"],
    "can_cu": [],
    "muc": [
        {"key": "tai_san_thue", "ten": "Tài sản thuê và mục đích thuê"},
        {
            "key": "giao_tai_san",
            "ten": "Giao tài sản thuê",
            "mau": "Bên cho thuê phải giao tài sản cho bên thuê đúng số lượng, chất lượng, chủng loại, tình trạng,"
            " thời điểm, địa điểm đã thoả thuận và cung cấp thông tin cần thiết về việc sử dụng tài sản đó.",
        },
    ],
}


def test_dan_so_dieu_luat_chi_bo_cau_do_giu_phan_con_lai_cua_doan():
    kq = _kiem(
        _ra(
            dieu=[
                _dieu(
                    "Bên cho thuê giao nhà cho Bên thuê đúng hiện trạng. Việc giao nhận theo Điều 476 Bộ luật Dân sự.",
                    ten="Giao tài sản thuê",
                )
            ]
        )
    )
    assert kq["dieu"][0]["doan"] == ["Bên cho thuê giao nhà cho Bên thuê đúng hiện trạng."]
    assert any("Điều 1" in g and "Bỏ phần" in g for g in kq["ghi_chu"])


def test_dieu_bat_buoc_bi_loc_het_lay_noi_dung_chuan_theo_can_cu():
    ra = _ra(
        ben=None,
        dieu=[
            _dieu("Bên cho thuê cho thuê căn nhà tại …….", ten="Tài sản thuê", key="tai_san_thue"),
            _dieu(
                "Bên cho thuê giao nhà theo quy định tại Điều 476 Bộ luật Dân sự.", ten="Giao nhà", key="giao_tai_san"
            ),
        ],
    )
    kq = h.kiem_khuon_mau(ra, NG_GIAO, NGUON, [], [])
    giao = next(d for d in kq["dieu"] if d["key"] == "giao_tai_san")
    assert giao["doan"] == [NG_GIAO["muc"][1]["mau"]] and giao.get("chen") is True
    assert "Điều 476" not in " ".join(giao["doan"])


def test_dieu_bat_buoc_khong_co_noi_dung_chuan_van_khong_trong():
    ra = _ra(ben=None, dieu=[_dieu("Bên cho thuê giao nhà đúng hạn.", ten="Giao nhà", key="giao_tai_san")])
    kq = h.kiem_khuon_mau(ra, NG_GIAO, NGUON, [], [])
    ts = next(d for d in kq["dieu"] if d["key"] == "tai_san_thue")
    assert ts["doan"] == [f"Các bên thỏa thuận về tài sản thuê và mục đích thuê như sau: {km.CHO}"]
