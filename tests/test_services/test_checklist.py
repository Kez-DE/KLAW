"""Checklist nội dung bắt buộc HĐLĐ — config/checklist_hdld.yaml là nguồn dữ liệu
duy nhất; file này khoá lại ba điều Task 3 phải đúng:

1. Completeness tính đúng ty_le/thieu/duoc_phep_giam cho trường hợp đủ, thiếu,
   và BA NGOẠI LỆ luật định (test_NGOAI_LE_*, cùng ca biên của chúng).
2. Một giá trị `nganh` lạ (không nằm trong nganh_duoc_giam.danh_sach) không
   được ném exception — bài học từ Task 2, nơi `bang_thang[vung]` ném KeyError
   khi `vung` lạ (test_NGANH_LA_KHONG_NO).
3. Mọi can_cu trong checklist đều là một `provisions.duong_dan` có thật
   (test_can_cu_*, test_MOI_can_cu_TON_TAI_trong_DB) — cùng khuôn hai test
   tích hợp của test_rules.py.
"""

from pathlib import Path

import pytest
from sqlalchemy import text

from src.services.checklist import (
    Checklist,
    cac_can_cu,
    check_completeness,
    kiem_tra_can_cu_ton_tai,
    load_checklist,
)
from src.services.db import get_engine

CL = load_checklist(Path("config/checklist_hdld.yaml"))
DU_10 = [
    {"key": k}
    for k in (
        "nsdld",
        "nld",
        "cong_viec",
        "thoi_han",
        "luong",
        "nang_luong",
        "thoi_gio",
        "bao_ho",
        "bao_hiem",
        "dao_tao",
    )
]


# ══ Đủ / thiếu mục, không có ngoại lệ nào áp dụng ═══════════════════════════


def test_du_10_muc_thi_completeness_1_0():
    r = check_completeness(CL, DU_10, nganh="thuong_mai")
    assert r.ty_le == 1.0 and r.thieu == []


def test_thieu_2_muc_thi_completeness_0_8():
    r = check_completeness(CL, DU_10[:8], nganh="thuong_mai")
    assert r.ty_le == 0.8
    assert set(r.thieu) == {"bao_hiem", "dao_tao"}


def test_clauses_rong_thi_thieu_tat_ca_muc():
    r = check_completeness(CL, [], nganh="thuong_mai")
    assert r.ty_le == 0.0
    assert set(r.thieu) == {m["key"] for m in CL.muc}


# ══ Ngoại lệ 1 (Đ21.3): nông/lâm/ngư/diêm nghiệp được giảm mục, denominator
# đổi theo ngành, và phải THÊM điều khoản thiên tai ═════════════════════════


def test_NGOAI_LE_D21_3_nganh_nong_nghiep_thieu_bao_ho_la_DUOC_PHEP_GIAM():
    thieu_bao_ho = [c for c in DU_10 if c["key"] != "bao_ho"]
    thieu_bao_ho.append({"key": "thien_tai"})
    r = check_completeness(CL, thieu_bao_ho, nganh="nong_nghiep")
    assert "bao_ho" in r.duoc_phep_giam
    assert "bao_ho" not in r.thieu, "ngành được giảm thì không tính là thiếu"
    assert r.ty_le == 1.0


def test_NGOAI_LE_D21_3_nganh_nong_nghiep_THIEU_dieu_khoan_thien_tai_la_VI_PHAM():
    r = check_completeness(CL, DU_10, nganh="nong_nghiep")
    assert "thien_tai" in r.thieu, "ngành nông nghiệp phải có điều khoản thiên tai"


def test_denominator_doi_theo_nganh_khong_co_dinh_10():
    r = check_completeness(CL, DU_10, nganh="nong_nghiep")
    assert r.tong_muc != 10, "denominator phải đổi theo ngành (spec 7.2 Đ21.3)"


def test_nganh_duoc_giam_nhung_ghi_du_ca_muc_duoc_giam_thi_DUOC_PHEP_GIAM_RONG():
    """duoc_phep_giam phải phản ánh mục THỰC SỰ bị bỏ, không phải mục CHỈ ĐỦ
    ĐIỀU KIỆN để bỏ — một hợp đồng nông nghiệp ghi đầy đủ (kể cả các mục được
    phép giảm) không được báo là "đã dùng quyền giảm" cho mục nào cả.
    """
    du_ca_thien_tai = DU_10 + [{"key": "thien_tai"}]
    r = check_completeness(CL, du_ca_thien_tai, nganh="nong_nghiep")
    assert r.duoc_phep_giam == []
    assert r.thieu == []
    assert r.ty_le == 1.0


# ══ Ngoại lệ 2 (Đ21.2): bí mật kinh doanh là QUYỀN, không bắt buộc ══════════


def test_NGOAI_LE_D21_2_bi_mat_kinh_doanh_KHONG_bao_thieu():
    r = check_completeness(CL, DU_10, nganh="thuong_mai")
    assert "bi_mat_kinh_doanh" not in r.thieu, "bí mật KD là quyền, không bắt buộc"


def test_NGOAI_LE_D21_2_bi_mat_kinh_doanh_CO_MAT_khong_lam_tang_mau_so():
    voi_bi_mat = DU_10 + [{"key": "bi_mat_kinh_doanh"}]
    r = check_completeness(CL, voi_bi_mat, nganh="thuong_mai")
    assert r.ty_le == 1.0
    assert r.tong_muc == 10, "khoản tự nguyện không được tính vào mẫu số bắt buộc"


def test_KHONG_BAT_BUOC_loai_tru_khoi_bat_buoc_du_key_co_mat_trong_muc():
    """Phòng vệ chủ động: nếu `muc` một ngày nào đó vô tình liệt kê trùng một
    key đã khai trong `khong_bat_buoc.keys`, key đó vẫn KHÔNG được tính là
    bắt buộc. Hành vi 'đừng báo thiếu' không được phép chỉ là hệ quả tình cờ
    của việc config/checklist_hdld.yaml hiện tại không chứa key trùng.
    """
    cl_gia = Checklist(
        loai="gia", ten="văn bản giả", tieu_de="VĂN BẢN GIẢ",
        can_cu_goc="test",
        can_cu_chi_tiet="test",
        muc=[{"key": "a", "can_cu": "test"}, {"key": "tuy_chon", "can_cu": "test"}],
        nganh_duoc_giam={"can_cu": "test", "danh_sach": [], "duoc_giam_muc": [], "bat_buoc_them": {"key": "x", "ten": "x"}},
        khong_bat_buoc={"can_cu": "test", "keys": ["tuy_chon"]},
        quy_tac_dinh_dang={"can_cu": "test"},
    )
    r = check_completeness(cl_gia, [{"key": "a"}], nganh="khong_lien_quan")
    assert r.thieu == [], "'tuy_chon' nằm trong khong_bat_buoc nên không được coi là thiếu"
    assert r.tong_muc == 1


# ══ Giá trị `nganh` lạ không được ném exception (bài học từ Task 2) ═════════


def test_NGANH_LA_KHONG_CO_TRONG_DANH_SACH_KHONG_NO_MA_TINH_NHU_NGANH_BINH_THUONG():
    """`nganh` lạ (không có trong nganh_duoc_giam.danh_sach) phải cho ra một
    kết quả có nghĩa — giống hệt một ngành hợp lệ nhưng không được giảm mục
    nào — KHÔNG được rò một exception ra ngoài. check_completeness dùng phép
    `in` trên danh sách để xét ngành, không tra từ điển theo khoá như
    `bang_thang[vung]` của Task 2, nên không có nguy cơ KeyError tương tự.
    """
    r = check_completeness(CL, DU_10, nganh="nganh_khong_ton_tai_nao_ca")
    assert r.ty_le == 1.0
    assert r.thieu == []
    assert r.tong_muc == 10


# ══ can_cu: mọi trích dẫn phải là provisions.duong_dan có thật ══════════════
# (yêu cầu bắt buộc ngoài brief — cùng khuôn hai test tích hợp của
# test_rules.py: một test nhanh không cần DB thật để khoá cả hai chiều, và
# hai test tích hợp đọc Postgres thật.)


def test_load_checklist_khong_lam_rot_can_cu_chi_tiet():
    """`can_cu_chi_tiet` phải được nạp vào Checklist, không âm thầm rớt mất —
    nếu không thì không thể kiểm nó với DB.
    """
    assert CL.can_cu_chi_tiet == "10/2020/TT-BLĐTBXH > Điều 3"


def test_can_cu_gia_bi_bat_KHONG_can_DB_that():
    cl_gia = Checklist(
        loai=CL.loai, ten=CL.ten, tieu_de=CL.tieu_de,
        can_cu_goc="00/0000/XX-YY > Điều 0",
        can_cu_chi_tiet=CL.can_cu_chi_tiet,
        muc=CL.muc,
        nganh_duoc_giam=CL.nganh_duoc_giam,
        khong_bat_buoc=CL.khong_bat_buoc,
        quy_tac_dinh_dang=CL.quy_tac_dinh_dang,
    )
    with pytest.raises(ValueError, match="00/0000/XX-YY"):
        kiem_tra_can_cu_ton_tai(cl_gia, duong_dan_hop_le={"45/2019/QH14 > Điều 25"})

    # Chiều ngược lại: không raise khi mọi can_cu đều nằm trong tập hợp lệ.
    kiem_tra_can_cu_ton_tai(CL, duong_dan_hop_le=cac_can_cu(CL))


@pytest.mark.integration
def test_MOI_can_cu_TON_TAI_trong_DB():
    """Checklist trích dẫn điều luật không tồn tại thì audit report vô giá trị."""
    kiem_tra_can_cu_ton_tai(CL)  # đọc DB thật qua get_engine(); raise nếu thiếu can_cu nào


@pytest.mark.integration
def test_can_cu_khop_dung_provisions_duong_dan_that():
    """Đối chiếu trực tiếp, không qua kiem_tra_can_cu_ton_tai hay cac_can_cu,
    để hai đường kiểm tra (hàm sản phẩm + truy vấn độc lập ngay trong test)
    không cùng che giấu một lỗi chung.
    """
    with get_engine().connect() as c:
        co = {r[0] for r in c.execute(text("SELECT duong_dan FROM provisions")).all()}
    can_cu_can_kiem = {
        CL.can_cu_goc,
        CL.can_cu_chi_tiet,
        CL.nganh_duoc_giam["can_cu"],
        CL.khong_bat_buoc["can_cu"],
        CL.quy_tac_dinh_dang["can_cu"],
        *(m["can_cu"] for m in CL.muc),
    }
    thieu = sorted(can_cu_can_kiem - co)
    assert not thieu, f"căn cứ không có trong DB: {thieu}"
