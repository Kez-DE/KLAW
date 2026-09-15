"""Nhận ra tài liệu người dùng tải lên là loại văn bản gì (spec 2026-09-15c).

Đây là chỗ KLAW thôi hỏi và bắt đầu suy luận. Bắt người dùng chọn "loại văn bản"
từ danh sách 29 mục trước khi đọc được tờ giấy họ đang cầm là hành vi của một
biểu mẫu, không phải của một trợ lý pháp lý.

Bốn điều file này khoá:

1. **Tất định trước.** Tên văn bản nằm ngay dòng đầu của hầu hết giấy tờ pháp lý
   Việt Nam. Tra bảng trên chính chữ đó là 0 token và lặp lại được — cùng nguyên
   tắc `route.R-INT-001` đã đặt cho định tuyến ý định.
2. **Dám nói không biết.** Tài liệu ngoài 29 loại phải trả `None`, không được ép
   vào loại gần nhất. Đoán bừa ở đây nghĩa là rút sai bộ trường, và người dùng
   thấy một bảng dữ kiện sai mà không hiểu vì sao.
3. **Không bỏ dấu khi so.** "Hợp đồng lao động" và "hop dong lao dong" cùng trỏ
   một loại, nhưng đó là chuẩn hoá ĐẦU VÀO của người dùng — không phải nới lỏng
   phép kiểm trích dẫn, vốn vẫn giữ dấu tuyệt đối.
4. **Nói ra vì sao đoán vậy.** Một suy luận không giải thích được thì người dùng
   không sửa được.
"""

import pytest

from src.services.doc_tai_lieu import DonViVanBan
from src.services.phan_loai_tai_lieu import KetQuaPhanLoai, phan_loai


def _dv(*dong: str) -> list[DonViVanBan]:
    return [
        DonViVanBan(chi_so=i, trang=1, offset_dau=0, noi_dung=d) for i, d in enumerate(dong)
    ]


@pytest.mark.parametrize(
    "tieu_de, loai",
    [
        ("HỢP ĐỒNG LAO ĐỘNG", "hdld"),
        ("HỢP ĐỒNG THỬ VIỆC", "hop_dong_thu_viec"),
        ("ĐƠN XIN NGHỈ VIỆC", "don_xin_nghi_viec"),
        ("ĐƠN KHỞI KIỆN", "don_khoi_kien"),
        ("GIẤY UỶ QUYỀN", "giay_uy_quyen"),
        ("NỘI QUY LAO ĐỘNG", "noi_quy"),
        ("QUYẾT ĐỊNH BỔ NHIỆM", "quyet_dinh_bo_nhiem"),
        ("HỢP ĐỒNG MUA BÁN HÀNG HOÁ", "hop_dong_mua_ban"),
    ],
)
def test_nhan_ra_tu_TIEU_DE(tieu_de, loai):
    kq = phan_loai(_dv(tieu_de, "Căn cứ Bộ luật Lao động số 45/2019/QH14."))
    assert kq is not None and kq.loai == loai, f"{tieu_de} -> {kq}"


def test_khong_can_VIET_HOA():
    assert phan_loai(_dv("Hợp đồng lao động")).loai == "hdld"


def test_khong_can_DAU():
    """Người dùng gõ máy không dấu, hoặc OCR nuốt dấu — vẫn phải nhận ra."""
    assert phan_loai(_dv("HOP DONG THU VIEC")).loai == "hop_dong_thu_viec"


def test_TAI_LIEU_LA_thi_tra_None_chu_KHONG_doan_bua():
    """Ca thật: giấy tiếp nhận thực tập không nằm trong 29 loại."""
    kq = phan_loai(_dv("GIẤY TIẾP NHẬN THỰC HÀNH, THỰC TẬP", "Kính gửi: Trường Đại học"))
    assert kq is None


def test_tai_lieu_RONG_tra_None():
    assert phan_loai([]) is None


def test_chi_doc_PHAN_DAU_chu_khong_ca_tai_lieu():
    """Tên văn bản nằm ở đầu. Một chữ 'hợp đồng lao động' ở trang 40 của một nội
    quy không được lật ngược kết luận."""
    dong = _dv("NỘI QUY LAO ĐỘNG") + [
        DonViVanBan(chi_so=i, trang=9, offset_dau=0, noi_dung="hợp đồng lao động " * 20)
        for i in range(1, 60)
    ]
    assert phan_loai(dong).loai == "noi_quy"


def test_ket_qua_NOI_RA_cho_no_doc_duoc():
    """Suy luận không giải thích được thì người dùng không sửa được."""
    kq = phan_loai(_dv("HỢP ĐỒNG LAO ĐỘNG"))
    assert isinstance(kq, KetQuaPhanLoai)
    assert kq.can_cu.strip(), "phải nêu chỗ nó đọc được"
    assert "hợp đồng lao động" in kq.can_cu.lower()
    assert 0 < kq.do_tin <= 1


def test_ban_dai_hon_thang_ban_ngan_hon():
    """"Hợp đồng thử việc" không được rơi vào "hợp đồng" chung chung."""
    assert phan_loai(_dv("HỢP ĐỒNG THỬ VIỆC")).loai == "hop_dong_thu_viec"
    assert phan_loai(_dv("THOẢ THUẬN CHẤM DỨT HỢP ĐỒNG LAO ĐỘNG")).loai == "thoa_thuan_cham_dut_hdld"


def test_moi_loai_tra_ve_deu_CO_THAT_trong_checklist():
    from src.agents.graph_soan_thao import load_checklist_cached

    for tieu_de in ("HỢP ĐỒNG LAO ĐỘNG", "ĐƠN KHIẾU NẠI", "CÔNG VĂN", "BIÊN BẢN HỌP HỘI ĐỒNG QUẢN TRỊ"):
        kq = phan_loai(_dv(tieu_de))
        assert kq is not None, tieu_de
        assert load_checklist_cached(kq.loai) is not None
