"""Xếp văn bản vào 12 ngành luật của hệ thống pháp luật Việt Nam (spec 2026-09-15d).

Vì sao cần: `documents.linh_vuc` lấy nguyên văn từ nguồn cho 56 giá trị tự do và
chỉ 88/1634 văn bản có giá trị, trong khi `retrieval.loc_theo_linh_vuc` BẬT mặc
định — bộ lọc đang lọc trên một cột rỗng 95%.

Ba điều file này khoá:

1. **Chồng lấn giải bằng độ cụ thể, không bằng thứ tự bảng chữ cái.** "Bộ luật
   Tố tụng dân sự" khớp cả `dan_su` lẫn `to_tung`; tố tụng cụ thể hơn nên thắng.
   Sai chiều này thì mọi luật tố tụng rơi vào dân sự và bộ lọc thành vô nghĩa.
2. **Dám trả None.** Một văn bản không khớp ngành nào phải để trống, không ép
   vào `hanh_chinh` cho đủ. `hanh_chinh` đã là nhóm gộp lớn nhất của bộ 12 ngành
   (môi trường, giao thông, y tế, giáo dục, quốc phòng đều vào đó); biến nó
   thành thùng rác nữa thì bộ lọc mất nốt phần giá trị còn lại.
3. **Từ khoá là DỮ LIỆU.** Thêm ngành là sửa `config/linh_vuc.yaml`.
"""

import pytest

from src.services.phan_linh_vuc import LINH_VUC, NGANH_LUAT, phan_linh_vuc, phan_nganh_luat


@pytest.mark.parametrize(
    "ten, linh_vuc",
    [
        ("Hiến pháp năm 2013", "hien_phap"),
        ("Bộ luật Lao động", "lao_dong"),
        ("Luật Bảo hiểm xã hội", "lao_dong"),
        ("Bộ luật Hình sự", "hinh_su"),
        ("Bộ luật Dân sự", "dan_su"),
        ("Luật Đất đai", "dat_dai"),
        ("Luật Nhà ở", "dat_dai"),
        ("Luật Doanh nghiệp", "kinh_te"),
        ("Luật Sở hữu trí tuệ", "kinh_te"),
        ("Luật Quản lý thuế", "tai_chinh"),
        ("Luật Các tổ chức tín dụng", "ngan_hang"),
        ("Luật Hôn nhân và gia đình", "hon_nhan_gia_dinh"),
        ("Luật Cán bộ, công chức", "hanh_chinh"),
        # Bộ 12 ngành GỘP: năm nhóm dưới đây đều là Luật Hành chính, không có
        # ngành riêng. Test khoá lại điều đó để không ai tưởng là phân loại sai.
        ("Luật Bảo vệ môi trường", "hanh_chinh"),
        ("Luật Giao thông đường bộ", "hanh_chinh"),
        ("Luật Khám bệnh, chữa bệnh", "hanh_chinh"),
        ("Luật Giáo dục đại học", "hanh_chinh"),
        ("Luật An ninh quốc gia", "hanh_chinh"),
    ],
)
def test_xep_dung_linh_vuc(ten, linh_vuc):
    kq = phan_nganh_luat(ten=ten)
    assert kq is not None and kq.linh_vuc == linh_vuc, f"{ten} -> {kq}"


@pytest.mark.parametrize(
    "ten, linh_vuc",
    [
        ("Bộ luật Tố tụng dân sự", "to_tung_dan_su"),
        ("Bộ luật Tố tụng hình sự", "to_tung_hinh_su"),
        ("Luật Thi hành án dân sự", "to_tung_dan_su"),
        ("Luật Thi hành án hình sự", "to_tung_hinh_su"),
        ("Luật Tố tụng hành chính", "to_tung_dan_su"),
    ],
)
def test_CHONG_LAN_giai_bang_do_CU_THE(ten, linh_vuc):
    """Tố tụng dân sự không được rơi vào dân sự — sai chiều này thì bộ lọc vô nghĩa."""
    assert phan_nganh_luat(ten=ten).linh_vuc == linh_vuc


def test_dung_duoc_ca_linh_vuc_NGUON_lon_xon():
    """56 giá trị tự do của nguồn vẫn là tín hiệu, chỉ là chưa chuẩn hoá."""
    kq = phan_nganh_luat(ten="Thông tư 10/2020/TT-BLĐTBXH", linh_vuc_nguon="Lao động - Thương binh và Xã hội")
    assert kq is not None and kq.linh_vuc == "lao_dong"


def test_dung_duoc_co_quan_ban_hanh():
    kq = phan_nganh_luat(ten="Thông tư 01/2024", co_quan="Ngân hàng Nhà nước Việt Nam")
    assert kq is not None and kq.linh_vuc == "ngan_hang"


def test_KHONG_KHOP_thi_None_chu_khong_don_vao_hanh_chinh():
    """`hanh_chinh` đã gộp năm nhóm rồi; đừng biến nó thành thùng rác nữa."""
    assert phan_nganh_luat(ten="Nghị quyết về chương trình công tác năm") is None
    assert phan_nganh_luat(ten="") is None


def test_ket_qua_noi_ra_tu_khoa_da_khop():
    kq = phan_nganh_luat(ten="Bộ luật Lao động")
    assert kq.tu_khoa == "lao dong"
    assert kq.linh_vuc_ten.strip()


def test_DUNG_12_nganh_luat_va_uu_tien_khong_trung():
    assert len(NGANH_LUAT) == 12
    uu = sorted(v.uu_tien for v in NGANH_LUAT.values())
    assert uu == list(range(1, 13))


def test_moi_nganh_deu_mo_ta_duoc_bang_ten_tieng_Viet():
    assert {lv.ten for lv in NGANH_LUAT.values()} == {
        "Luật Hiến pháp", "Luật Hành chính", "Luật Hình sự", "Luật Tố tụng hình sự",
        "Luật Dân sự", "Luật Tố tụng dân sự", "Luật Đất đai", "Luật Tài chính",
        "Luật Ngân hàng", "Luật Hôn nhân và gia đình", "Luật Lao động", "Luật Kinh tế",
    }


def test_moi_nganh_deu_co_ten_va_tu_khoa():
    for slug, lv in {**NGANH_LUAT, **LINH_VUC}.items():
        assert lv.ten.strip(), slug
        assert lv.tu_khoa, slug


# ═══ Trục 2 — 27 lĩnh vực ═══════════════════════════════════════════════════


@pytest.mark.parametrize(
    "ten, linh_vuc",
    [
        ("Luật Doanh nghiệp", "doanh_nghiep"),
        ("Luật Đầu tư công", "dau_tu"),
        ("Luật Thương mại", "thuong_mai"),
        ("Luật Hải quan", "xuat_nhap_khau"),
        ("Luật Các tổ chức tín dụng", "tien_te_ngan_hang"),
        ("Luật Quản lý thuế", "thue_phi_le_phi"),
        ("Luật Chứng khoán", "chung_khoan"),
        ("Luật Kinh doanh bảo hiểm", "bao_hiem"),
        ("Luật Kiểm toán độc lập", "ke_toan_kiem_toan"),
        ("Bộ luật Lao động", "lao_dong_tien_luong"),
        ("Luật An ninh mạng", "cong_nghe_thong_tin"),
        ("Luật Kinh doanh bất động sản", "bat_dong_san"),
        ("Luật Luật sư", "dich_vu_phap_ly"),
        ("Luật Sở hữu trí tuệ", "so_huu_tri_tue"),
        ("Luật Cán bộ, công chức", "phap_luat_hanh_chinh"),
        ("Luật Xử lý vi phạm hành chính", "vi_pham_hanh_chinh"),
        ("Bộ luật Hình sự", "trach_nhiem_hinh_su"),
        ("Bộ luật Tố tụng dân sự", "thu_tuc_to_tung"),
        ("Luật Ngân sách nhà nước", "tai_chinh_nha_nuoc"),
        ("Luật Xây dựng", "xay_dung_do_thi"),
        ("Luật Giao thông đường bộ", "giao_thong_van_tai"),
        ("Luật Giáo dục đại học", "giao_duc"),
        ("Luật Bảo vệ môi trường", "tai_nguyen_moi_truong"),
        ("Luật Khám bệnh, chữa bệnh", "the_thao_y_te"),
        ("Bộ luật Dân sự", "quyen_dan_su"),
        ("Luật Di sản văn hóa", "van_hoa_xa_hoi"),
        ("Luật Chăn nuôi", "linh_vuc_khac"),
    ],
)
def test_27_linh_vuc_xep_dung(ten, linh_vuc):
    kq = phan_linh_vuc(ten=ten)
    assert kq is not None and kq.linh_vuc == linh_vuc, f"{ten} -> {kq}"


def test_DUNG_27_linh_vuc_va_uu_tien_khong_trung():
    assert len(LINH_VUC) == 27
    assert sorted(v.uu_tien for v in LINH_VUC.values()) == list(range(1, 28))


def test_HAI_TRUC_doc_lap_nhau():
    """Cùng một văn bản mang một giá trị ở MỖI trục, không phải trục này suy ra trục kia."""
    assert phan_nganh_luat(ten="Luật Sở hữu trí tuệ").linh_vuc == "kinh_te"
    assert phan_linh_vuc(ten="Luật Sở hữu trí tuệ").linh_vuc == "so_huu_tri_tue"
