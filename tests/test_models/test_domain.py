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


def test_khoa_so_ky_hieu_chiu_Eth_va_gach_en_nhung_khong_doi_chu_khac():
    """Kho có `110/2002/QÐ-BTC` (Ð U+00D0) và `43/2010/TT–BNNPTNT` (gạch en):
    tra bằng dạng người gõ phải ra đúng dòng đó, còn dữ liệu lưu giữ nguyên văn."""
    from src.models.domain import khoa_so_ky_hieu

    assert khoa_so_ky_hieu("110/2002/QÐ-BTC") == khoa_so_ky_hieu("110/2002/QĐ-BTC") == "110/2002/QĐ-BTC"
    assert khoa_so_ky_hieu("43/2010/TT–BNNPTNT") == "43/2010/TT-BNNPTNT"
    assert khoa_so_ky_hieu(" 45/2019/QH14 ") == "45/2019/QH14"
    assert khoa_so_ky_hieu("145/2020/NĐ-CP") != khoa_so_ky_hieu("145/2020/ND-CP")
    assert khoa_so_ky_hieu(None) == ""


@pytest.mark.integration
def test_sql_khoa_so_ky_hieu_khop_ban_python():
    from sqlalchemy import text

    from src.models.domain import khoa_so_ky_hieu, sql_khoa_so_ky_hieu
    from src.services.db import get_engine

    mau = ["110/2002/QÐ-BTC", "43/2010/TT–BNNPTNT", "12/2022/NĐ-CP", "18/2002/QÐ—BTS"]
    with get_engine().connect() as c:
        ra = [c.execute(text(f"SELECT {sql_khoa_so_ky_hieu(':s')}"), {"s": s}).scalar_one() for s in mau]
    assert ra == [khoa_so_ky_hieu(s) for s in mau]
