import json
from pathlib import Path

import pytest

from src.models.domain import Cap
from src.services.prov_parser import parse_anomalies, parse_provisions, parse_tables

SKH = "45/2019/QH14"

# HTML thật từ documentContent.content của doc_id 139264 (rút gọn)
HTML_DIEU_21 = """
<div class="WordSection1">
<p id="a1" class="MsoNormal prov-chapter"><strong><b>Chương III<br>HỢP ĐỒNG LAO ĐỘNG</b></strong></p>
<p id="a2" class="MsoNormal prov-article"><strong><b>Điều 21. Nội dung hợp đồng lao động</b></strong></p>
<p id="a3" class="MsoNormal prov-clause">1. Hợp đồng lao động phải có những nội dung chủ yếu sau đây:</p>
<p id="a4" class="MsoNormal prov-item">a) Tên, địa chỉ của người sử dụng lao động;</p>
<p id="a5" class="MsoNormal prov-item">b) Họ tên, ngày tháng năm sinh, giới tính;</p>
<p id="a6" class="MsoNormal prov-article"><strong><b>Điều 26. Tiền lương thử việc</b></strong></p>
<p class="MsoNormal prov-content">Tiền lương của người lao động trong thời gian thử việc do hai bên thỏa thuận nhưng ít nhất phải bằng 85% mức lương của công việc đó.</p>
</div>
"""

HTML_BANG = """
<div class="WordSection1">
<p id="b1" class="MsoNormal prov-article"><strong><b>Điều 3. Mức lương tối thiểu</b></strong></p>
<table><tr><td>Vùng</td><td>Mức tháng</td></tr>
<tr><td>Vùng I</td><td>5.310.000</td></tr>
<tr><td>Vùng II</td><td>4.730.000</td></tr></table>
</div>
"""


def test_bay_1_html_phang_van_dung_duoc_cay_theo_class():
    rows = parse_provisions(HTML_DIEU_21, SKH)
    by_path = {r.duong_dan: r for r in rows}
    diem_a = by_path["45/2019/QH14 > Điều 21 > Khoản 1 > Điểm a"]
    khoan_1 = by_path["45/2019/QH14 > Điều 21 > Khoản 1"]
    assert diem_a.parent_local_id == khoan_1.local_id
    assert by_path["45/2019/QH14 > Điều 21"].cap is Cap.dieu


def test_bay_2_prov_content_KHONG_CO_ID_van_giu_duoc_noi_dung_dieu_26():
    """Bẫy nặng nhất: parser đòi id sẽ mất trắng nội dung Điều 26."""
    rows = parse_provisions(HTML_DIEU_21, SKH)
    d26 = next(r for r in rows if r.duong_dan == "45/2019/QH14 > Điều 26")
    assert "85%" in d26.noi_dung, "mất nội dung Điều 26 — prov-content không có id"
    assert d26.source_node_id == "a6"


def test_bay_3_br_khong_lam_dinh_chu():
    rows = parse_provisions(HTML_DIEU_21, SKH)
    chuong = next(r for r in rows if r.cap is Cap.chuong)
    assert "IIIHỢP" not in chuong.tieu_de + chuong.noi_dung
    assert "Chương III" in chuong.tieu_de


def test_bay_4_bang_parse_rieng_giu_hang_cot():
    tables = parse_tables(HTML_BANG)
    assert len(tables) == 1
    assert "Vùng I" in tables[0] and "5.310.000" in tables[0]
    assert tables[0].count("\n") >= 2, "phải giữ nhiều hàng, không bẹp thành 1 dòng"
    # và bảng KHÔNG lọt vào provisions dưới dạng prov-content rời
    rows = parse_provisions(HTML_BANG, "293/2025/NĐ-CP")
    assert not any(r.noi_dung.strip() == "Vùng I" for r in rows)


def test_so_hieu_cap_tach_dung_tu_text():
    rows = parse_provisions(HTML_DIEU_21, SKH)
    assert next(r for r in rows if r.cap is Cap.dieu and r.so_hieu_cap == "21")
    assert next(r for r in rows if r.cap is Cap.khoan and r.so_hieu_cap == "1")
    assert next(r for r in rows if r.cap is Cap.diem and r.so_hieu_cap == "a")


def test_dieu_van_tro_vao_chuong_cha_trong_cay():
    """Spec 4.4: provisions là CÂY Phần>Chương>Mục>Điều>Khoản>Điểm.
    duong_dan bỏ container, nhưng parent_local_id PHẢI giữ cấu trúc thật."""
    rows = parse_provisions(HTML_DIEU_21, SKH)
    chuong = next(r for r in rows if r.cap is Cap.chuong)
    d21 = next(r for r in rows if r.duong_dan == "45/2019/QH14 > Điều 21")
    assert d21.parent_local_id == chuong.local_id, "Điều mất liên kết với Chương cha"
    assert "Chương" not in d21.duong_dan, "duong_dan không được chứa Chương"


def test_khong_container_nao_bi_bo_ro():
    """Mọi Chương/Mục phải có ít nhất một con — nếu không, cây bị vỡ."""
    rows = parse_provisions(HTML_DIEU_21, SKH)
    co_con = {r.parent_local_id for r in rows if r.parent_local_id is not None}
    ro = [r for r in rows if r.cap in (Cap.phan, Cap.chuong, Cap.muc)
          and r.local_id not in co_con]
    assert not ro, f"container bị bỏ rơ: {[(r.cap.value, r.so_hieu_cap) for r in ro]}"


def test_hai_prov_content_lien_tiep_duoc_merge_CA_HAI():
    """Reference swap (model_copy) dễ sai: chỉ cái cuối được merge, cái đầu mất.
    Brief không có test cho chỗ này."""
    html = """
    <div class="WordSection1">
    <p id="x1" class="MsoNormal prov-article"><strong><b>Điều 9. Thử</b></strong></p>
    <p class="MsoNormal prov-content">Đoạn thứ nhất của điều này.</p>
    <p class="MsoNormal prov-content">Đoạn thứ hai của điều này.</p>
    </div>
    """
    rows = parse_provisions(html, SKH)
    d9 = next(r for r in rows if r.cap is Cap.dieu)
    assert "thứ nhất" in d9.noi_dung, "mất đoạn prov-content ĐẦU (reference swap sai)"
    assert "thứ hai" in d9.noi_dung, "mất đoạn prov-content SAU"


def test_tieu_de_chuong_tach_lam_2_the_khong_bi_bo_ro():
    """Phát hiện qua verify dữ liệu thật (không phải test của brief): Chương I
    của BLLĐ tách tiêu đề thành 2 <p class="prov-chapter"> riêng (cùng id) thay
    vì nối bằng <br> trong 1 thẻ như 16 chương còn lại. Thẻ sau không khớp
    so_hieu phải nối vào node đã có, không tạo node mồ côi mới."""
    html = """
    <div class="WordSection1">
    <p id="c1" class="MsoNormal prov-chapter"><strong><b>Chương I</b></strong></p>
    <p id="c1" class="MsoNormal prov-chapter"><strong><b>NHỮNG QUY ĐỊNH CHUNG</b></strong></p>
    <p id="c2" class="MsoNormal prov-article"><strong><b>Điều 1. Phạm vi điều chỉnh</b></strong></p>
    </div>
    """
    rows = parse_provisions(html, SKH)
    chuong_rows = [r for r in rows if r.cap is Cap.chuong]
    assert len(chuong_rows) == 1, "tiêu đề tách 2 thẻ phải gộp lại thành 1 node Chương"
    assert chuong_rows[0].so_hieu_cap == "I"
    assert "NHỮNG QUY ĐỊNH CHUNG" in chuong_rows[0].tieu_de
    dieu1 = next(r for r in rows if r.cap is Cap.dieu)
    assert dieu1.parent_local_id == chuong_rows[0].local_id


def test_dieu_33a_KHONG_dung_chung_duong_dan_voi_dieu_33():
    """FALSE-POSITIVE VERIFICATION: hai Điều cùng anchor thì verify tầng 1 sẽ
    'kiểm chứng thành công' một trích dẫn sai."""
    html = """
    <div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><strong><b>Điều 33. Nội dung gốc</b></strong></p>
    <p id="a2" class="MsoNormal prov-article"><strong><b>Điều 33a. Nội dung bổ sung</b></strong></p>
    </div>
    """
    rows = parse_provisions(html, SKH)
    dd = [r.duong_dan for r in rows if r.cap is Cap.dieu]
    assert len(dd) == len(set(dd)), f"hai Điều dùng chung duong_dan: {dd}"
    assert "45/2019/QH14 > Điều 33a" in dd


def test_DIEU_viet_hoa_toan_bo_van_bat_duoc_so_hieu():
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>ĐIỀU 5. Viết hoa</b></p></div>"""
    r = next(x for x in parse_provisions(html, SKH) if x.cap is Cap.dieu)
    assert r.so_hieu_cap == "5", f"so_hieu={r.so_hieu_cap!r}"


def test_phan_thu_nhat_va_thu_hai_khac_nhau():
    """Bộ luật Dân sự trong corpus dùng quy ước 'Phần thứ nhất'."""
    html = """<div class="WordSection1">
    <p id="p1" class="MsoNormal prov-part"><b>Phần thứ nhất NHỮNG QUY ĐỊNH CHUNG</b></p>
    <p id="p2" class="MsoNormal prov-part"><b>Phần thứ hai QUYỀN SỞ HỮU</b></p></div>"""
    phan = [r.so_hieu_cap for r in parse_provisions(html, SKH) if r.cap is Cap.phan]
    assert len(set(phan)) == 2, f"hai Phần cùng so_hieu: {phan}"


def test_khoan_khong_khop_regex_KHONG_bi_gop_vao_khoan_truoc():
    """Fix bẫy #5 phải hẹp: gộp tiêu đề chỉ áp cho container, không cho Khoản."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 7. Thử</b></p>
    <p id="k1" class="MsoNormal prov-clause">1. Khoản một.</p>
    <p id="k2" class="MsoNormal prov-clause">I/ Khoản định dạng lạ.</p></div>"""
    rows = parse_provisions(html, SKH)
    khoan = [r for r in rows if r.cap is Cap.khoan]
    assert len(khoan) == 2, f"chỉ còn {len(khoan)} Khoản — bị gộp mất một"
    assert "định dạng lạ" not in khoan[0].tieu_de


def test_tieu_de_DIEU_tach_2_the_KHAC_id_duoc_gop():
    """BLDS/BLHS/BLTTDS/BLTTHS có 75 thẻ prov-article tách tiêu đề, id KHÁC nhau."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 33.</b></p>
    <p id="a2" class="MsoNormal prov-article"><b>Bảo vệ quyền nhân thân</b></p></div>"""
    rows = parse_provisions(html, SKH)
    dieu = [r for r in rows if r.cap is Cap.dieu]
    assert len(dieu) == 1, f"tạo {len(dieu)} node thay vì gộp"
    assert dieu[0].so_hieu_cap == "33"
    assert "nhân thân" in dieu[0].tieu_de


def test_DIEU_that_so_hieu_la_KHONG_bi_gop():
    """'Điều 33a' và 'ĐIỀU 5' đều mở đầu bằng nhãn -> là node THẬT, không gộp."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 33. Gốc</b></p>
    <p id="a2" class="MsoNormal prov-article"><b>Điều 33a. Bổ sung</b></p>
    <p id="a3" class="MsoNormal prov-article"><b>ĐIỀU 34. Hoa</b></p></div>"""
    so = [r.so_hieu_cap for r in parse_provisions(html, SKH) if r.cap is Cap.dieu]
    assert so == ["33", "33a", "34"], so


def test_KHOAN_KHONG_BAO_GIO_bi_gop_du_so_hieu_rong():
    """Khoản không có nhãn trong text -> LABEL_LEVELS loại nó ra -> bất biến."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 7. T</b></p>
    <p id="k1" class="MsoNormal prov-clause">1. Khoản một.</p>
    <p id="k2" class="MsoNormal prov-clause">I/ Định dạng lạ.</p>
    <p id="k3" class="MsoNormal prov-clause">Không có số gì cả.</p></div>"""
    khoan = [r for r in parse_provisions(html, SKH) if r.cap is Cap.khoan]
    assert len(khoan) == 3, f"chỉ còn {len(khoan)} Khoản — bị gộp mất"


def test_parse_anomalies_bat_provision_trong_bang():
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 90. Lương</b></p>
    <table><tr><td><p id="k1" class="MsoNormal prov-clause">1. Vùng I.</p></td></tr></table></div>"""
    a = parse_anomalies(html)
    assert any("table" in x for x in a), f"không bắt được: {a}"


def test_parse_anomalies_bat_loi_mo_dau_va_text_ngoai_prov():
    html = """<div class="WordSection1">
    <p class="MsoNormal prov-content">Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;</p>
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi</b></p>
    <p class="MsoNormal">Đoạn này không có class prov nào và dài hơn bốn mươi ký tự nên phải bị bắt.</p>
    </div>"""
    a = parse_anomalies(html)
    assert any("trước mọi node" in x for x in a), f"không bắt lời mở đầu: {a}"
    assert any("không có class prov" in x for x in a), f"không bắt text ngoài prov: {a}"


def test_muc_cung_so_o_chuong_khac_nhau_co_duong_dan_KHAC_NHAU():
    """BLLĐ có 6 'Mục 1' ở 6 Chương khác nhau. Nếu duong_dan trùng thì mọi phép
    kiểm 'duong_dan trùng' về sau phải khoét ngoại lệ — mà chính phép kiểm đó
    bắt được bug Điều 33/33a."""
    html = """<div class="WordSection1">
    <p id="c1" class="MsoNormal prov-chapter"><b>Chương III HỢP ĐỒNG LAO ĐỘNG</b></p>
    <p id="m1" class="MsoNormal prov-section"><b>Mục 1. GIAO KẾT</b></p>
    <p id="a1" class="MsoNormal prov-article"><b>Điều 13. Hợp đồng</b></p>
    <p id="c2" class="MsoNormal prov-chapter"><b>Chương V ĐỐI THOẠI</b></p>
    <p id="m2" class="MsoNormal prov-section"><b>Mục 1. ĐỐI THOẠI</b></p>
    <p id="a2" class="MsoNormal prov-article"><b>Điều 63. Đối thoại</b></p></div>"""
    rows = parse_provisions(html, SKH)
    muc = [r.duong_dan for r in rows if r.cap is Cap.muc]
    assert len(set(muc)) == 2, f"hai Mục 1 dùng chung duong_dan: {muc}"
    assert "Chương" in muc[0], f"duong_dan của Mục phải giữ Chương: {muc[0]!r}"
    # nhưng Điều thì VẪN bỏ container
    dieu = [r.duong_dan for r in rows if r.cap is Cap.dieu]
    assert all("Chương" not in d and "Mục" not in d for d in dieu), dieu


def test_moi_duong_dan_duy_nhat_tren_toan_bo_provision():
    """Invariant: duong_dan duy nhất trên toàn bộ provision của một văn bản."""
    html = """<div class="WordSection1">
    <p id="c1" class="MsoNormal prov-chapter"><b>Chương I A</b></p>
    <p id="m1" class="MsoNormal prov-section"><b>Mục 1. X</b></p>
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. P</b></p>
    <p id="k1" class="MsoNormal prov-clause">1. K.</p>
    <p id="c2" class="MsoNormal prov-chapter"><b>Chương II B</b></p>
    <p id="m2" class="MsoNormal prov-section"><b>Mục 1. Y</b></p>
    <p id="a2" class="MsoNormal prov-article"><b>Điều 2. Q</b></p>
    <p id="k2" class="MsoNormal prov-clause">1. K.</p></div>"""
    dd = [r.duong_dan for r in parse_provisions(html, SKH)]
    assert len(dd) == len(set(dd)), f"trùng: {[x for x in dd if dd.count(x) > 1]}"


@pytest.mark.integration
def test_bo_luat_lao_dong_that_co_dung_220_dieu():
    p = Path("data/raw/moj/139264.json")
    if not p.exists():
        pytest.skip("chạy `python -m scripts.fetch_moj` trước")
    doc = json.loads(p.read_text(encoding="utf-8"))
    rows = parse_provisions(doc["documentContent"]["content"], "45/2019/QH14")
    dieu = [r for r in rows if r.cap is Cap.dieu]
    assert len(dieu) == 220, f"đếm được {len(dieu)} Điều, phải là 220"
    assert dieu[0].so_hieu_cap == "1"
    assert dieu[-1].so_hieu_cap == "220"
    assert all(r.noi_dung or any(c.parent_local_id == r.local_id for c in rows) for r in dieu), (
        "có Điều vừa rỗng nội dung vừa không có con — dấu hiệu mất dữ liệu"
    )
