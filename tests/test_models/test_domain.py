import pytest
from pydantic import ValidationError

from src.models.domain import Cap, DocumentRow, ProvisionRow


def test_cap_co_dung_cac_bac():
    """`prov-subsection` tồn tại 43 lần trong corpus (23 Tiểu mục BLDS sau khi
    gộp tiêu đề tách thẻ). Thiếu cấp này thì chúng mất trắng."""
    assert [c.value for c in Cap] == [
        "phan", "chuong", "muc", "tieu_muc", "dieu", "khoan", "diem",
        # `hang_bang` (một HÀNG dữ liệu của bảng) đứng NGAY SAU `diem`: nó là
        # cấp sâu nhất của cây quy phạm, và `bac` quyết định parser pop stack ở
        # đâu. Đặt nó sau `phu_luc` sẽ làm một hàng bảng "nông hơn" Điểm.
        "hang_bang",
        # Hai cấp TÀI LIỆU, đứng cuối enum: chữ ở ĐUÔI văn bản và chữ ở ĐẦU văn
        # bản, cả hai không trích dẫn được. `bac` của chúng dịch khi thêm cấp
        # cây mới và điều đó vô hại — chúng không bao giờ vào stack.
        "phu_luc", "mo_dau"]


def test_cap_bac_tang_dan_de_stack_pop_dung():
    assert Cap.chuong.bac < Cap.muc.bac < Cap.tieu_muc.bac < Cap.dieu.bac
    assert Cap.dieu.bac < Cap.khoan.bac < Cap.diem.bac


def test_provision_row_cho_phep_noi_dung_rong_nhung_khong_cho_duong_dan_rong():
    ProvisionRow(local_id=0, parent_local_id=None, cap=Cap.dieu, so_hieu_cap="25",
                 tieu_de="Thời gian thử việc", noi_dung="", duong_dan="45/2019/QH14 > Điều 25",
                 source_node_id=None, thu_tu=0)
    with pytest.raises(ValidationError):
        ProvisionRow(local_id=0, parent_local_id=None, cap=Cap.dieu, so_hieu_cap="25",
                     tieu_de="x", noi_dung="", duong_dan="", source_node_id=None, thu_tu=0)


def test_document_row_bat_buoc_so_ky_hieu_khong_dung_ten():
    # doc_id 96117 có title = "Hàng hải" — định danh phải là so_ky_hieu
    d = DocumentRow(id="96117", so_ky_hieu="95/2015/QH13", loai_van_ban="Bộ luật",
                    ten="Hàng hải", tinh_trang="HHL1P", checksum="abc", depth="deep")
    assert d.so_ky_hieu == "95/2015/QH13"
    with pytest.raises(ValidationError):
        DocumentRow(id="96117", so_ky_hieu="", loai_van_ban="Bộ luật", ten="Hàng hải",
                    tinh_trang="HHL1P", checksum="abc", depth="deep")
