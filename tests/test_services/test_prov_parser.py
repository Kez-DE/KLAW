import json
import unicodedata
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.models.domain import Cap
from src.services.prov_parser import (
    CITABLE,
    _chuan_hoa,
    parse_anomalies,
    parse_provisions,
    parse_tables,
)

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


def test_tieu_de_chuong_mo_bang_TU_CHUONG_TRINH_la_tiep_noi_khong_phai_nhan():
    """27/2023/QH15 (gateway 169032) Chương III tách tiêu đề ba thẻ cùng id; dòng
    thứ ba "CHƯƠNG TRÌNH, KẾ HOẠCH…" mở bằng chữ "chương" của từ ghép "chương
    trình", không phải nhãn: sau nhãn thật chỉ có số hiệu hoặc hết chữ."""
    html = """<div class="WordSection1">
    <p id="c3" class="prov-chapter"><strong>Chương III</strong></p>
    <p id="c3" class="prov-chapter"><strong>CHIẾN LƯỢC PHÁT TRIỂN NHÀ Ở QUỐC GIA,</strong></p>
    <p id="c3" class="prov-chapter"><strong>CHƯƠNG TRÌNH, KẾ HOẠCH PHÁT TRIỂN NHÀ Ở CẤP TỈNH</strong></p>
    <p id="a1" class="prov-article"><strong>Điều 26. Chiến lược phát triển nhà ở quốc gia</strong></p>
    <p id="c4" class="prov-chapter"><strong>Chương IV</strong></p>
    <p id="a2" class="prov-article"><strong>Điều 30. Yêu cầu</strong></p></div>"""
    rows = parse_provisions(html, "27/2023/QH15")
    chuong = [r for r in rows if r.cap is Cap.chuong]
    assert [r.so_hieu_cap for r in chuong] == ["III", "IV"]
    assert "CHƯƠNG TRÌNH, KẾ HOẠCH PHÁT TRIỂN NHÀ Ở CẤP TỈNH" in chuong[0].tieu_de
    d26 = next(r for r in rows if r.duong_dan == "27/2023/QH15 > Điều 26")
    assert d26.parent_local_id == chuong[0].local_id


def test_AM_TINH_nhan_Chuong_tro_van_mo_node_moi():
    """BLHS (96122) viết "Chương " trơ rồi "VIII QUYẾT ĐỊNH HÌNH PHẠT" ở thẻ sau:
    nhãn không kèm số vẫn là node THẬT, không gộp vào Chương VII."""
    html = """<div class="WordSection1">
    <p id="c7" class="prov-chapter"><strong>Chương VII </strong></p>
    <p id="c7" class="prov-chapter"><strong>CÁC BIỆN PHÁP TƯ PHÁP</strong></p>
    <p id="c8" class="prov-chapter"><strong>Chương </strong></p>
    <p id="c8" class="prov-chapter"><strong>VIII QUYẾT ĐỊNH HÌNH PHẠT</strong></p>
    <p id="a1" class="prov-article"><strong>Điều 50. Căn cứ quyết định hình phạt</strong></p></div>"""
    chuong = [r for r in parse_provisions(html, "100/2015/QH13") if r.cap is Cap.chuong]
    assert [r.so_hieu_cap for r in chuong] == ["VII", "VIII"]


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


def test_khoan_KHONG_CO_SO_duoc_gop_vao_KHOAN_lien_truoc():
    """Ruling H3 đảo ruling trước. 4 mảnh trong corpus (BLDS Điều 33, BLTTHS
    Điều 33 và 123, BLHS Điều 3 Khoản 1) là đoạn TIẾP NỐI thật: đã đối chiếu HTML
    thô, cả 4 đứng ngay sau một thẻ CÙNG CẤP có số và mở đầu bằng chữ thường
    ("Trường hợp", "Nếu", "Khoan hồng"), không có dấu hiệu số hiệu nào.

    Không gộp thì Khoản cha bị CẮT CỤT: một trích dẫn ĐÚNG vào khoản 3 Điều 33
    BLDS sẽ THẤT BẠI ở tầng 1 vì đoạn hai của nó không còn trong `noi_dung` — hệ
    thống ABSTAIN một câu trả lời đúng, false-negative trên đúng phép kiểm số 3.

    Cùng một luật, không phải ca riêng thứ sáu: với Khoản/Điểm SỐ HỌC LÀ NHÃN,
    nên "không parse được số" chính là dấu hiệu "không mở đầu bằng nhãn" mà cấp
    có nhãn đang dùng."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 33. Thử nghiệm y học</b></p>
    <p id="k1" class="MsoNormal prov-clause">3. Việc thử nghiệm y học phải được người đó đồng ý.</p>
    <p id="k2" class="MsoNormal prov-clause">Trường hợp người được thử nghiệm là người chưa thành niên thì phải được cha, mẹ đồng ý.</p>
    <p id="i1" class="MsoNormal prov-item">d) Khoan hồng đối với người tự thú;</p>
    <p id="i2" class="MsoNormal prov-item">Nếu phát hiện hành vi trái pháp luật thì phải kiến nghị.</p></div>"""
    with pytest.warns(UserWarning, match="gộp"):
        rows = parse_provisions(html, SKH)

    khoan = [r for r in rows if r.cap is Cap.khoan]
    assert len(khoan) == 1, [r.duong_dan for r in khoan]
    assert khoan[0].duong_dan == f"{SKH} > Điều 33 > Khoản 3"
    assert "chưa thành niên" in khoan[0].noi_dung, "Khoản cha vẫn bị cắt cụt"

    diem = [r for r in rows if r.cap is Cap.diem]
    assert len(diem) == 1, [r.duong_dan for r in diem]
    assert "trái pháp luật" in diem[0].noi_dung, "Điểm cha vẫn bị cắt cụt"

    assert not [r.duong_dan for r in rows
                if r.duong_dan.endswith("> Khoản") or r.duong_dan.endswith("> Điểm")], \
        "còn neo trích dẫn thiếu thành phần số hiệu"


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


def test_HAI_KHOAN_KHONG_SO_duoi_cung_mot_DIEU_thi_RAISE():
    """Thay cho test cũ `test_KHOAN_KHONG_BAO_GIO_bi_gop_du_so_hieu_rong`, vốn
    khẳng định 3 node được tạo — nhưng hai Khoản không số dưới cùng một Điều ra
    CÙNG duong_dan "… > Điều 7 > Khoản", tức hai neo trích dẫn trùng.

    Đây là cơ chế trùng #1 mà review đã xác định là TIỀM ẨN trong corpus. Hai bất
    biến xung đột nhau ở đây và bất biến neo trích dẫn thắng: dữ liệu như vậy
    phải làm build ĐỎ chứ không được ship ra hai neo giống nhau.

    Sau ruling H3, một Khoản không số đứng NGAY SAU một Khoản khác được gộp nên
    không còn ra neo thiếu số. Đường còn lại: thẻ ngay trước nó là cấp KHÁC (một
    Điểm) — gộp không áp dụng, node vẫn sinh ra với `so_hieu` rỗng, và hai node
    như vậy dưới cùng một Điều ra CÙNG `duong_dan` "… > Khoản"."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 7. T</b></p>
    <p id="k1" class="MsoNormal prov-clause">1. Khoản một.</p>
    <p id="i1" class="MsoNormal prov-item">a) Điểm a.</p>
    <p id="k2" class="MsoNormal prov-clause">Không có số gì cả.</p>
    <p id="i2" class="MsoNormal prov-item">b) Điểm b.</p>
    <p id="k3" class="MsoNormal prov-clause">Cũng không có số hiệu.</p></div>"""
    with pytest.raises(ValueError, match="duong_dan TRÙNG"):
        parse_provisions(html, SKH)


def test_khoan_thieu_dau_phan_cach_van_bat_duoc_so():
    """BLTTDS (96115) có Khoản viết '1 Trường hợp...' không có dấu . hoặc )."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 4. T</b></p>
    <p id="k1" class="MsoNormal prov-clause">1 Trường hợp không có quy định.</p>
    <p id="k2" class="MsoNormal prov-clause">2. Có dấu chấm bình thường.</p></div>"""
    khoan = [r for r in parse_provisions(html, SKH) if r.cap is Cap.khoan]
    assert [r.so_hieu_cap for r in khoan] == ["1", "2"], [r.so_hieu_cap for r in khoan]


def test_parse_anomalies_CHAN_neo_trich_dan_trong_bang():
    """Cấp trích dẫn được trong <table> = mất một neo → lỗi CHẶN build."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 90. Lương</b></p>
    <table><tr><td><p id="k1" class="MsoNormal prov-clause">1. Vùng I.</p></td></tr></table></div>"""
    loi, canh_bao = parse_anomalies(html)
    assert any("khoan" in x and "table" in x for x in loi), f"không bắt được: {loi}"
    assert not canh_bao


def test_parse_anomalies_chi_CANH_BAO_container_trong_bang():
    """BLHS (96122) có 9 thẻ prov-part/prov-section trong <table>: "Phần thứ
    hai"/"Mục 3" lặp lại ở đầu trang Công báo tiếp theo. Không mất neo trích
    dẫn nào nên WARN, không chặn build — nếu chặn thì build đỏ vĩnh viễn."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 90. Lương</b></p>
    <table><tr><td><p class="MsoNormal prov-part">Phần thứ hai</p></td></tr></table></div>"""
    loi, canh_bao = parse_anomalies(html)
    assert not loi, loi
    assert any("phan" in x for x in canh_bao), canh_bao


def test_parse_anomalies_lo_hong_cu_da_thanh_KHONG_THE_XAY_RA():
    """Hai đường cũ (lời mở đầu trước mọi node; <p> không class prov) trước đây
    được PHÁT HIỆN; sau khi bỏ whitelist chúng KHÔNG THỂ XẢY RA. parse_anomalies
    chuyển sang assert lại bằng phép bảo toàn token, nên fixture này phải SẠCH."""
    html = """<div class="WordSection1">
    <p class="MsoNormal prov-content">Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;</p>
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi</b></p>
    <p class="MsoNormal">Đoạn này không có class prov nào và dài hơn bốn mươi ký tự.</p>
    </div>"""
    loi, canh_bao = parse_anomalies(html)
    assert not loi and not canh_bao, (loi, canh_bao)
    rows = parse_provisions(html, SKH)
    assert any("Căn cứ Hiến pháp" in r.noi_dung for r in rows)
    assert any("không có class prov" in r.noi_dung for r in rows)


def test_parse_anomalies_BAT_khi_whitelist_quay_lai(monkeypatch):
    """Phép bảo toàn phải thực sự bắt được mất chữ, không phải hằng đúng. Mô
    phỏng đúng bản cũ (bỏ mọi text không có class prov-*) và bắt hàm báo đỏ.
    Nếu nó im thì cổng cấu trúc chỉ là trang trí."""
    import src.services.prov_parser as pp

    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi</b></p>
    <p class="MsoNormal">Phụ lục I. DANH MỤC nghề được làm ban đêm.</p>
    </div>"""
    assert not pp.parse_anomalies(html)[0]

    that = pp._don_vi

    def whitelist_cu(node):
        for cap, text, tag in that(node):
            if cap is not None:  # đúng hành vi cũ: `continue` với thẻ không prov-*
                yield cap, text, tag

    monkeypatch.setattr(pp, "_don_vi", whitelist_cu)
    loi, _ = pp.parse_anomalies(html)
    assert any("KHÔNG BẢO TOÀN" in x for x in loi), f"không bắt mất chữ: {loi}"


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


# ══ Mục A — noi_dung là TOÀN VĂN, không phải chuỗi rỗng ══

def test_noi_dung_khoan_la_toan_van_khong_phai_rong():
    """Đã đo trên DB: noi_dung rỗng ở 17.813/19.077 provision (93,4%). MOJ nhét
    toàn bộ text quy phạm vào chính thẻ nhãn Khoản/Điểm → nếu noi_dung chỉ nhận
    prov-content thì verifier tầng 1 đối chiếu vào chuỗi rỗng."""
    rows = parse_provisions(HTML_DIEU_21, SKH)
    k1 = next(r for r in rows if r.cap is Cap.khoan)
    assert "Hợp đồng lao động phải có những nội dung chủ yếu" in k1.noi_dung
    diem_a = next(r for r in rows if r.cap is Cap.diem)
    assert "Tên, địa chỉ của người sử dụng lao động" in diem_a.noi_dung


def test_noi_dung_dieu_gom_ca_dong_tieu_de_va_moi_prov_content():
    rows = parse_provisions(HTML_DIEU_21, SKH)
    d26 = next(r for r in rows if r.duong_dan == "45/2019/QH14 > Điều 26")
    assert "Điều 26" in d26.noi_dung, "noi_dung của Điều phải gồm cả dòng tiêu đề"
    assert "85%" in d26.noi_dung


def test_noi_dung_KHONG_RONG_o_moi_cap_trich_dan_duoc():
    """Bất biến RAISE. Cấp trích dẫn được = dieu/khoan/diem — đây là trường
    tầng 1 đối chiếu câu trích vào; rỗng = verifier không kiểm được gì."""
    for html in (HTML_DIEU_21, HTML_BANG):
        for r in parse_provisions(html, SKH):
            if r.cap in CITABLE:
                assert r.noi_dung.strip(), f"{r.duong_dan} có noi_dung rỗng"


def test_tieu_de_khoan_la_NHAN_NGAN_khong_phai_toan_van():
    rows = parse_provisions(HTML_DIEU_21, SKH)
    k1 = next(r for r in rows if r.cap is Cap.khoan)
    assert k1.tieu_de == "Khoản 1", k1.tieu_de
    diem_a = next(r for r in rows if r.cap is Cap.diem)
    assert diem_a.tieu_de == "Điểm a", diem_a.tieu_de


# ══ Mục B — bỏ whitelist: text ngoài prov-* KHÔNG BAO GIỜ bị bỏ ══

def test_text_ngoai_moi_the_prov_duoc_gan_vao_provision_dang_mo():
    """Whitelist làm mất 113.121 ký tự / 21 văn bản (TT 09/2020: 64,4% tài liệu).
    Phần lớn là Phụ lục và DANH MỤC — nội dung có hiệu lực pháp lý."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi</b></p>
    <p class="MsoNormal">Thông tư này quy định danh mục nghề được làm ban đêm.</p>
    <p id="a2" class="MsoNormal prov-article"><b>Điều 2. Hiệu lực</b></p>
    <p>Phụ lục I</p>
    <em>(Ban hành kèm theo Thông tư số 09/2020/TT-BLĐTBXH)</em>
    </div>"""
    rows = parse_provisions(html, SKH)
    d1 = next(r for r in rows if r.so_hieu_cap == "1")
    assert "danh mục nghề được làm ban đêm" in d1.noi_dung, "mất phần xen giữa"
    pl = next(r for r in rows if r.cap is Cap.phu_luc)
    assert "Phụ lục I" in pl.noi_dung
    assert "Ban hành kèm theo" in pl.noi_dung, "text ngoài <p> cũng không được bỏ"


def test_khong_con_ky_tu_mo_coi_nao_sau_khi_parse():
    """Phép BẢO TOÀN: mọi token của HTML đã strip tag (trừ <table>) phải xuất
    hiện trong provisions. Đây là điều biến case #1 của parse_anomalies từ
    'phát hiện được' thành 'không thể xảy ra'."""
    html = """<div class="WordSection1">
    <p class="MsoNormal">Căn cứ Bộ luật Lao động ngày 20 tháng 11 năm 2019;</p>
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi</b></p>
    <p class="MsoNormal prov-clause">1. Nội dung khoản một.</p>
    <p class="MsoNormal">Đoạn mồ côi giữa hai khoản.</p>
    <p class="MsoNormal prov-clause">2. Nội dung khoản hai.</p>
    <div>Đoạn mồ côi ngoài thẻ p.</div></div>"""
    rows = parse_provisions(html, SKH)
    goc = set(_chuan_hoa(BeautifulSoup(html, "html.parser").get_text(" ")).split())
    db = set(_chuan_hoa(" ".join(f"{r.tieu_de} {r.noi_dung}" for r in rows)).split())
    assert not (goc - db), f"mất token: {sorted(goc - db)}"

    # M9: `set(goc) - set(db)` chỉ chứng minh KHÔNG MẤT — theo định nghĩa nó
    # không thể phát hiện GÁN SAI. Bất biến còn thiếu: `noi_dung` của một
    # provision cấp trích dẫn được chỉ chứa chữ nằm giữa nhãn của nó và nhãn kế
    # tiếp, nên nó phải MỞ ĐẦU bằng nhãn của chính nó.
    k1, k2 = [r for r in rows if r.cap is Cap.khoan]
    assert k1.noi_dung.startswith("1.") and k2.noi_dung.startswith("2."), \
        (k1.noi_dung[:40], k2.noi_dung[:40])
    assert "mồ côi giữa hai khoản" in k1.noi_dung, "đoạn xen giữa phải vào Khoản 1"
    assert "mồ côi giữa hai khoản" not in k2.noi_dung
    assert not [r.duong_dan for r in rows
                if r.cap in CITABLE and "Căn cứ Bộ luật" in r.noi_dung], \
        "lời mở đầu bị gán vào một neo trích dẫn"


def test_loi_mo_dau_vao_ban_ghi_MO_DAU_khong_vao_DIEU_1():
    """M9: bản cũ chỉ assert `any(... in r.noi_dung for r in rows)` — nó chứng
    minh "không mất", chưa bao giờ chứng minh "không gán sai"; và fixture của nó
    mở đầu bằng `prov-chapter`, tức chỉ chạy đúng nhánh vô hại.

    C1: 8/21 văn bản mở đầu TRỰC TIẾP bằng "Điều 1", và ở đó toàn bộ tiêu ngữ +
    tên văn bản + chuỗi "Căn cứ …" trở thành văn bản của Điều 1. Tầng 1 sẽ tra
    `<so_ky_hieu> > Điều 1`, tìm thấy nguyên văn tên văn bản trong `noi_dung` và
    trả về "đã kiểm chứng" cho một câu trích KHÔNG thuộc điều luật nào.

    Fixture này dùng đúng hình dạng đó — đối xứng với chữ ở ĐUÔI (`phu_luc`)."""
    html = """<div class="WordSection1">
    <p class="MsoNormal">CHÍNH PHỦ CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc</p>
    <p class="MsoNormal prov-content">Căn cứ Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam;</p>
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi điều chỉnh</b></p>
    <p class="MsoNormal prov-content">Nghị định này quy định mức lương tối thiểu.</p></div>"""
    rows = parse_provisions(html, SKH)

    md = next(r for r in rows if r.cap is Cap.mo_dau)
    assert md.duong_dan == f"{SKH} > Mở đầu"
    assert md.parent_local_id is None and md.so_hieu_cap == ""
    assert Cap.mo_dau not in CITABLE
    assert "Căn cứ Hiến pháp" in md.noi_dung and "CHÍNH PHỦ" in md.noi_dung

    d1 = next(r for r in rows if r.cap is Cap.dieu)
    assert d1.noi_dung.startswith("Điều 1."), d1.noi_dung[:80]
    assert "Căn cứ" not in d1.noi_dung and "CHÍNH PHỦ" not in d1.noi_dung
    assert "mức lương tối thiểu" in d1.noi_dung, "thân của Điều 1 phải còn nguyên"

    assert not parse_anomalies(html, SKH)[0], "phép bảo toàn ký tự phải còn khít"


def test_mo_dau_MOT_ban_ghi_moi_van_ban_va_KHONG_danh_so():
    """Một bản ghi mỗi văn bản nên `duong_dan` tự duy nhất — không đánh số thứ
    tự, đó là bịa ký hiệu không có trong nguồn. Và văn bản mở đầu ngay bằng thẻ
    `prov-*` thì KHÔNG sinh bản ghi rỗng."""
    html = """<div class="WordSection1">
    <p class="MsoNormal">THÔNG TƯ Quy định về thời giờ làm việc.</p>
    <p class="MsoNormal">Căn cứ Bộ luật Lao động ngày 20 tháng 11 năm 2019;</p>
    <p class="MsoNormal">Theo đề nghị của Cục trưởng;</p>
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi</b></p></div>"""
    md = [r for r in parse_provisions(html, SKH) if r.cap is Cap.mo_dau]
    assert len(md) == 1, [r.duong_dan for r in md]
    assert all(x in md[0].noi_dung for x in ("THÔNG TƯ", "Căn cứ", "Theo đề nghị"))

    assert not [r for r in parse_provisions(HTML_DIEU_21, SKH) if r.cap is Cap.mo_dau], \
        "không có chữ trước thẻ prov-* đầu tiên thì không được tạo bản ghi"


def test_mo_dau_co_thu_tu_NHO_NHAT_du_local_id_lon_nhat():
    """`local_id` của `mo_dau` phải ở CUỐI (để `parent_local_id` của mọi node quy
    phạm giữ nguyên) nhưng chữ mở đầu nằm ở ĐẦU văn bản. Trước khi sửa,
    `126319` có `mo_dau` thu_tu=35 và `phu_luc` thu_tu=36 — lời mở đầu xếp SAU
    Phụ lục. `thu_tu = -1` giải quyết mà không phải đánh số lại gì cả (không có
    CHECK nào bắt `thu_tu >= 0`)."""
    html = """<div class="WordSection1">
    <p class="MsoNormal">THÔNG TƯ Quy định thử.</p>
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi</b></p>
    <p class="MsoNormal">Phụ lục I DUOI danh mục.</p></div>"""
    rows = parse_provisions(html, SKH)
    md = next(r for r in rows if r.cap is Cap.mo_dau)
    assert md.thu_tu == -1, md.thu_tu
    assert md.thu_tu < min(r.thu_tu for r in rows if r.cap is not Cap.mo_dau)
    assert md.local_id > 0, "local_id vẫn ở cuối để parent_local_id không phải dịch"


# ══ Mục F — NFC hoá lúc parse, KHÔNG casefold ══

def test_text_luu_duoc_NFC_hoa():
    """96117 tại offset 33.642 ghi 'ư'+U+0323 thay vì 'ự'(U+1EF1). NFD một phía
    làm độ phủ sụp về 0,28–0,37 — lệch một phần trông y hệt mất dữ liệu."""
    nfd = unicodedata.normalize("NFD", "sự")
    html = f"""<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Danh {nfd} kiện</b></p></div>"""
    r = next(x for x in parse_provisions(html, SKH) if x.cap is Cap.dieu)
    assert r.tieu_de == unicodedata.normalize("NFC", r.tieu_de)
    assert "ự" in r.tieu_de, "chưa NFC hoá: 'ự' vẫn ở dạng tổ hợp dấu"
    assert "Danh sự kiện" in r.noi_dung


# ══ Mục E — neo trích dẫn trùng là bất biến RAISE ══

def test_duong_dan_trung_o_cap_trich_dan_duoc_thi_RAISE():
    """Không được bịa số thứ tự vào duong_dan để né trùng — neo trích dẫn phải
    là thứ có trong văn bản nguồn, nên trùng = raise."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 5. Bản gốc</b></p>
    <p id="a2" class="MsoNormal prov-article"><b>Điều 5. Bản trùng</b></p></div>"""
    with pytest.raises(ValueError, match="duong_dan"):
        parse_provisions(html, SKH)


def test_D_hoa_U00D0_khong_lam_hai_Dieu_that_bi_gop():
    """96172 có đúng 2 lần ký tự Ð U+00D0 (khác Đ U+0110). Nếu rơi vào đầu thẻ
    prov-article thì regex ^Điều không khớp → node số rỗng → gộp mất một Điều."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Ðiều 7. Bản dùng Ð U+00D0</b></p>
    <p id="a2" class="MsoNormal prov-article"><b>Điều 8. Bản thường</b></p></div>"""
    rows = parse_provisions(html, SKH)
    so = [r.so_hieu_cap for r in rows if r.cap is Cap.dieu]
    assert so == ["7", "8"], f"Ð U+00D0 làm mất Điều: {so}"


def test_duong_dan_trung_o_cap_container_chi_WARN():
    """NĐ 145/2020 (152668) thật sự đánh số hai Chương cùng là 'Chương XI' —
    đã chấp nhận có chủ đích, không được bịa 'XII' để né."""
    html = """<div class="WordSection1">
    <p id="c1" class="MsoNormal prov-chapter"><b>Chương XI A</b></p>
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. X</b></p>
    <p id="c2" class="MsoNormal prov-chapter"><b>Chương XI B</b></p>
    <p id="a2" class="MsoNormal prov-article"><b>Điều 2. Y</b></p></div>"""
    with pytest.warns(UserWarning, match="duong_dan"):
        rows = parse_provisions(html, SKH)
    assert len([r for r in rows if r.cap is Cap.chuong]) == 2


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
    assert all(r.noi_dung.strip() for r in dieu), "có Điều noi_dung rỗng"


def test_the_prov_trong_tron_khong_tao_provision_rong():
    """337/2025/NĐ-CP có `<p class="prov-clause"></p>` trống trơn — thẻ không có
    chữ chỉ tạo node noi_dung rỗng và duong_dan mất số hiệu. Không chữ, không mất."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 30. Trách nhiệm</b></p>
    <p class="prov-clause">1. Bộ trưởng Bộ Nội vụ hướng dẫn.</p>
    <p class="prov-clause"></p></div>"""
    khoan = [r for r in parse_provisions(html, SKH) if r.cap is Cap.khoan]
    assert len(khoan) == 1, [r.duong_dan for r in khoan]


# ══ Ruling: tách chữ mồ côi theo VỊ TRÍ, không theo regex tiếng Việt ══

def test_mo_coi_XEN_GIUA_gan_vao_provision_dang_mo_con_DUOI_thanh_phu_luc():
    """Đã đo: 97–98% chữ mồ côi của cụm Lao động nằm SAU thẻ prov-* cuối cùng
    (152668: 42.636 đuôi / 647 xen giữa). Ranh giới là thật.

    - xen giữa hai thẻ prov-* = tiếp nối thật → giữ cách gắn cũ (đây là thứ đã
      cứu BLDS Điều 493)
    - sau thẻ prov-* cuối = nội dung đuôi (Phụ lục, khối chữ ký) → bản ghi riêng
      cấp KHÔNG trích dẫn được, nên nó không thể là neo cho câu trích nào
    """
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi</b></p>
    <p class="MsoNormal">XENGIUA đoạn tiếp nối thật của Điều 1.</p>
    <p id="a2" class="MsoNormal prov-article"><b>Điều 2. Hiệu lực</b></p>
    <p class="MsoNormal">Phụ lục I DUOI danh mục nghề được làm ban đêm.</p>
    <div>DUOIHAI khối chữ ký ngoài cả thẻ p.</div></div>"""
    rows = parse_provisions(html, SKH)

    d1 = next(r for r in rows if r.so_hieu_cap == "1")
    assert "XENGIUA" in d1.noi_dung, "phần xen giữa phải giữ nguyên cách gắn"

    pl = next(r for r in rows if r.cap is Cap.phu_luc)
    assert pl.duong_dan == f"{SKH} > Phụ lục"
    assert pl.parent_local_id is None and pl.so_hieu_cap == ""
    assert "DUOI" in pl.noi_dung and "DUOIHAI" in pl.noi_dung
    assert "XENGIUA" not in pl.noi_dung

    assert not any("DUOI" in r.noi_dung for r in rows if r.cap is not Cap.phu_luc), \
        "chữ đuôi vẫn còn trong một provision khác — neo trích dẫn còn bị loãng"
    assert Cap.phu_luc not in CITABLE


def test_phu_luc_khong_vuong_bat_bien_so_hieu_cap():
    """`phu_luc` không thuộc nhóm cấp có nhãn kèm số, nên bất biến `so_hieu_cap`
    không rỗng KHÔNG áp cho nó. Một bản ghi mỗi văn bản nên nó tự duy nhất —
    không đánh số thứ tự, đó là bịa ký hiệu không có trong nguồn."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi</b></p>
    <p class="MsoNormal">Phụ lục I. Danh mục.</p>
    <p class="MsoNormal">Phụ lục II. Danh mục khác.</p></div>"""
    pl = [r for r in parse_provisions(html, SKH) if r.cap is Cap.phu_luc]
    assert len(pl) == 1, f"phải MỘT bản ghi cho mỗi văn bản, có {len(pl)}"
    assert "Phụ lục I" in pl[0].noi_dung and "Phụ lục II" in pl[0].noi_dung


def test_khong_co_chu_duoi_thi_khong_tao_ban_ghi_phu_luc():
    rows = parse_provisions(HTML_DIEU_21, SKH)
    assert not any(r.cap is Cap.phu_luc for r in rows)


def test_bao_toan_ky_tu_van_khit_khi_co_phu_luc():
    """`noi_dung` của `phu_luc` KHÔNG được thêm chuỗi tổng hợp nào (nhãn
    "Phụ lục" nằm ở `tieu_de`), nếu không phép bảo toàn ký tự lệch."""
    html = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi</b></p>
    <p class="MsoNormal">Phụ lục I. Danh mục nghề.</p></div>"""
    loi, _ = parse_anomalies(html, SKH)
    assert not loi, loi
    pl = next(r for r in parse_provisions(html, SKH) if r.cap is Cap.phu_luc)
    assert pl.tieu_de == "Phụ lục"
    assert pl.noi_dung == "Phụ lục I. Danh mục nghề.", "noi_dung có chuỗi tổng hợp"


@pytest.mark.integration
def test_BLDS_dieu_493_van_giu_doan_xen_giua():
    """232 ký tự mồ côi XEN GIỮA mà Cổng A tìm ra. Ruling nói rõ: đừng đổi phần
    xen giữa. Test này là bằng chứng nó không bị đổi."""
    p = Path("data/raw/moj/95942.json")
    if not p.exists():
        pytest.skip("chạy `python -m scripts.fetch_moj` trước")
    doc = json.loads(p.read_text(encoding="utf-8"))
    rows = parse_provisions(doc["documentContent"]["content"], "91/2015/QH13")
    d493 = next(r for r in rows if r.cap is Cap.dieu and r.so_hieu_cap == "493")
    assert "Khi chấm dứt hợp đồng thuê khoán" in d493.noi_dung
    assert len(d493.noi_dung) == 269, len(d493.noi_dung)


def test_prov_content_RONG_sau_chu_duoi_van_tach_ra_PHU_LUC():
    """H2. Dòng 203 bỏ qua thẻ `prov-<cấp>` không có chữ; nhánh `prov-content`
    thiếu guard tương ứng, nên một `<p class="prov-content"></p>` ở cuối trang
    đẩy mốc `cuoi` VƯỢT QUA Phụ lục → `duoi` rỗng → toàn bộ chữ đuôi quay về gắn
    vào provision đang mở. Đúng bug 42.636 ký tự đã chữa ở 1ddf020, quay lại
    nguyên trạng. 337/2025/NĐ-CP đã ship một `<p class="prov-clause"></p>` trống
    trơn, nên thẻ rỗng là thứ CÓ THẬT trong HTML của MOJ.

    Thẻ không có chữ không mang thông tin vị trí."""
    truoc = """<div class="WordSection1">
    <p id="a1" class="MsoNormal prov-article"><b>Điều 1. Phạm vi</b></p>
    <p class="MsoNormal">DUOI Phụ lục I danh mục nghề được làm ban đêm.</p>"""
    for the_rong in ("", '<p class="prov-content"></p>', '<p class="prov-content">   </p>'):
        html = f"{truoc}{the_rong}</div>"
        rows = parse_provisions(html, SKH)
        pl = [r for r in rows if r.cap is Cap.phu_luc]
        assert len(pl) == 1, f"{the_rong!r}: {len(pl)} bản ghi phu_luc"
        assert "DUOI" in pl[0].noi_dung, the_rong
        d1 = next(r for r in rows if r.cap is Cap.dieu)
        assert "DUOI" not in d1.noi_dung, f"{the_rong!r}: chữ đuôi sập lại vào Điều 1"
        assert not parse_anomalies(html, SKH)[0], the_rong


# ══ Bảng đi VÀO noi_dung — Plan 2, mục "bảng bị mất" ════════════════════════
#
# Trước vòng này `parse_tables()` KHÔNG có caller nào ngoài test của chính nó:
# `parse_provisions` gọi `tbl.decompose()`, nên mọi <table> ra khỏi cây và biến
# mất khỏi corpus. Đo được: 5 provision hứa một danh sách ("… như sau:") mà
# không có con nào và không có bảng — trong đó có CẢ HAI bảng lương tối thiểu
# vùng (293/2025 và 74/2024). Người hỏi "lương tối thiểu vùng I bao nhiêu" nhận
# một trích dẫn tới điều luật KHÔNG CHỨA CON SỐ NÀO, còn mô hình thì có thể viết
# ra con số từ trí nhớ huấn luyện và dẫn đúng Điều 3 Khoản 1 — trích dẫn đó qua
# được cả hai tầng kiểm, vì điều luật có thật và câu văn xuôi khớp.
#
# Bảng ghép vào `noi_dung` (KHÔNG cột riêng, KHÔNG bảng riêng) vì đóng góp trung
# tâm của khoá luận là "câu trích khớp nguyên văn điều luật": con số nằm ngoài
# `noi_dung` thì một câu trích chứa nó KHÔNG BAO GIỜ verify được.

HTML_BANG_TRONG_LUONG = """
<div class="WordSection1">
<table><tr><td>CHÍNH PHỦ</td><td>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do</td></tr></table>
<p id="d1" class="MsoNormal prov-article"><b>Điều 3. Mức lương tối thiểu</b></p>
<p id="k1" class="MsoNormal prov-clause">1. Quy định mức lương tối thiểu tháng đối với người lao động theo vùng như sau:</p>
<table><tr><td>Vùng</td><td>Mức lương tối thiểu tháng</td></tr>
<tr><td>Vùng I</td><td>5.310.000</td></tr>
<tr><td>Vùng II</td><td>4.730.000</td></tr></table>
<p id="k2" class="MsoNormal prov-clause">2. Danh mục địa bàn vùng I quy định tại Phụ lục kèm theo.</p>
<p class="MsoNormal">Nơi nhận:</p>
<table><tr><td>TM. CHÍNH PHỦ Hồ Đức Phớc</td></tr></table>
</div>
"""
SKH_LUONG = "293/2025/NĐ-CP"


def _cay_con_cua(rows, duong_dan):
    """`noi_dung` của một provision + mọi hậu duệ, nối lại — đúng phạm vi mà
    `verify_tier1._cay_con` đối chiếu quote vào."""
    goc = next(r for r in rows if r.duong_dan == duong_dan)
    con = {goc.local_id}
    ra = [goc.noi_dung]
    for r in rows:
        if r.parent_local_id in con:
            con.add(r.local_id)
            ra.append(r.noi_dung)
    return "\n".join(ra)


def test_bang_duoc_GHEP_vao_CAY_CON_cua_provision_gioi_thieu_no():
    """Lỗi gốc: `parse_tables` không có caller trong đường sản xuất — bản cũ
    decompose() mọi <table> và con số 5.310.000 không tồn tại ở đâu cả.

    Từ 2026-09-02 nó nằm ở một dòng `hang_bang` CON thay vì trong `noi_dung` của
    chính Khoản (migrations/017). Phạm vi phải kiểm vì thế là CÂY CON — đúng
    phạm vi `verify_tier1._cay_con` đối chiếu quote vào, nên bất biến "con số
    phải tra được từ neo Khoản 1" không hề yếu đi.
    """
    rows = parse_provisions(HTML_BANG_TRONG_LUONG, SKH_LUONG)
    cay = _cay_con_cua(rows, f"{SKH_LUONG} > Điều 3 > Khoản 1")
    assert "5.310.000" in cay, "bảng lương biến mất khỏi cây con của Khoản 1"
    assert "Vùng I" in cay

    # Cùng MỘT hàm thuần sinh ra markdown ở cả hai đường: `parse_tables` không
    # còn là nhánh chết song song với đường sản xuất. So THEO TỪNG HÀNG vì các
    # hàng nay nằm ở những dòng provision khác nhau.
    bang_luong = next(t for t in parse_tables(HTML_BANG_TRONG_LUONG) if "5.310.000" in t)
    for dong in bang_luong.split("\n"):
        assert dong in cay, f"cây con thiếu hàng {dong!r} của parse_tables"


def test_bang_ghep_vao_KHOAN_gioi_thieu_chu_KHONG_phai_DIEU_cha():
    """73,6% số Điều có `noi_dung == tieu_de`; bảng thuộc Khoản thì phải ở Khoản.

    Ghép nhầm lên Điều cha làm neo trích dẫn trỏ sai cấp, và làm `noi_dung` của
    Điều không còn mở đầu-và-chỉ-chứa nhãn của chính nó.
    """
    rows = parse_provisions(HTML_BANG_TRONG_LUONG, SKH_LUONG)
    d3 = next(r for r in rows if r.duong_dan == f"{SKH_LUONG} > Điều 3")
    k2 = next(r for r in rows if r.duong_dan == f"{SKH_LUONG} > Điều 3 > Khoản 2")
    assert "5.310.000" not in d3.noi_dung, "bảng của Khoản 1 leo lên Điều 3"
    assert "5.310.000" not in k2.noi_dung, "bảng của Khoản 1 trôi xuống Khoản 2"


def test_bang_TIEU_NGU_va_bang_CHU_KY_khong_vao_neo_trich_dan():
    """133 <table> toàn corpus KHÔNG phải đều là nội dung quy phạm.

    Bảng đầu văn bản là TIÊU NGỮ dàn trang ("CHÍNH PHỦ / CỘNG HÒA…"), bảng cuối
    là khối chữ ký. Cả hai nằm ngoài mốc `cuoi`/đầu `mo_dau` nên phải rơi vào
    hai bản ghi cấp TÀI LIỆU — vào một neo trích dẫn được thì một câu trích lấy
    từ tiêu ngữ sẽ "kiểm chứng thành công" trên Điều 3, đúng véc-tơ tấn công mà
    ruling C1 đã đóng cho chữ mồ côi.
    """
    rows = parse_provisions(HTML_BANG_TRONG_LUONG, SKH_LUONG)
    for r in rows:
        if r.cap in CITABLE:
            assert "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" not in r.noi_dung, r.duong_dan
            assert "Hồ Đức Phớc" not in r.noi_dung, r.duong_dan
    md = next(r for r in rows if r.cap is Cap.mo_dau)
    pl = next(r for r in rows if r.cap is Cap.phu_luc)
    assert "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" in md.noi_dung
    assert "Hồ Đức Phớc" in pl.noi_dung


def test_bang_vao_noi_dung_van_GIU_phep_bao_toan_ky_tu():
    """Cổng cấu trúc phải vẫn khít sau khi bảng vào `noi_dung`.

    Phép bảo toàn so `_dem` của HTML đã strip tag với tổng `_dem(noi_dung)`.
    Bảng thêm ký tự `|` phân tách — cả hai vế phải loại nó ra, nếu không cổng sẽ
    báo lệch GIẢ và mọi build đỏ (hoặc tệ hơn: ai đó nới nó thành ngưỡng).
    """
    loi, _ = parse_anomalies(HTML_BANG_TRONG_LUONG, SKH_LUONG)
    assert not loi, loi


def test_bang_KHONG_lam_mat_chu_cua_provision_gioi_thieu():
    """Ghép, không thay thế: văn xuôi dẫn vào bảng phải còn nguyên và đứng TRƯỚC.

    Sau khi tách hàng, `noi_dung` của Khoản còn văn xuôi + HÀNG TIÊU ĐỀ — tiêu
    đề ở lại vì bỏ nó đi thì tên cột biến mất và không ai dựng lại được bảng.
    """
    rows = parse_provisions(HTML_BANG_TRONG_LUONG, SKH_LUONG)
    k1 = next(r for r in rows if r.duong_dan == f"{SKH_LUONG} > Điều 3 > Khoản 1")
    assert k1.noi_dung.startswith("1. Quy định mức lương tối thiểu tháng")
    assert "theo vùng như sau:" in k1.noi_dung
    assert k1.noi_dung.index("như sau:") < k1.noi_dung.index("Mức lương tối thiểu tháng |")
    cay = _cay_con_cua(rows, f"{SKH_LUONG} > Điều 3 > Khoản 1")
    assert cay.index("như sau:") < cay.index("5.310.000")


# Rút gọn từ 66/2025/QH15 Điều 5 Khoản 2 (gateway 180017): công thức dàn bằng
# bảng một hàng, văn xuôi xen giữa các bảng.
HTML_CONG_THUC = """
<div class="WordSection1">
<p id="d5" class="MsoNormal prov-article"><b>Điều 5. Căn cứ tính thuế</b></p>
<p id="k2" class="MsoNormal prov-clause">2. Phương pháp tính thuế:</p>
<table><tr><td>Thuế phải nộp</td><td>=</td><td>Giá tính thuế x Thuế suất</td></tr></table>
<p class="MsoNormal prov-content">Trong đó:</p>
<table><tr><td>Giá tính thuế</td><td>=</td><td>Trị giá x Hệ số</td></tr></table>
<p class="MsoNormal prov-content">Hệ số do Bộ Tài chính công bố.</p>
</div>
"""


def test_van_xuoi_SAU_bang_giu_dung_cho_cua_no():
    """Văn xuôi đứng sau một bảng vẫn đứng sau bảng đó trong `noi_dung`.

    Dồn mọi văn xuôi lên trước bảng sinh ra câu "2. Phương pháp tính thuế: Trong
    đó: Hệ số…" — không có trong nguồn, nhưng một câu trích nó vẫn qua tầng 1
    (đo 2026-09-29: 41 điều khoản của 24 văn bản tầng sâu, kể cả 145/2020/NĐ-CP).
    """
    rows = parse_provisions(HTML_CONG_THUC, "66/2025/QH15")
    k2 = next(r for r in rows if r.duong_dan == "66/2025/QH15 > Điều 5 > Khoản 2")
    assert k2.noi_dung.split("\n\n") == [
        "2. Phương pháp tính thuế:",
        "| Thuế phải nộp | = | Giá tính thuế x Thuế suất |",
        "Trong đó:",
        "| Giá tính thuế | = | Trị giá x Hệ số |",
        "Hệ số do Bộ Tài chính công bố.",
    ]


@pytest.mark.integration
def test_ND_293_2025_that_co_bang_luong_trong_dieu_3_khoan_1():
    """Ca thật đã đo trên DB: `293/2025/NĐ-CP > Điều 3 > Khoản 1` kết thúc bằng
    dấu hai chấm, KHÔNG có con nào, và không chứa con số lương nào."""
    p = Path("data/raw/moj/183939.json")
    if not p.exists():
        pytest.skip("chạy `python -m scripts.fetch_moj` trước")
    html = json.loads(p.read_text(encoding="utf-8"))["documentContent"]["content"]
    rows = parse_provisions(html, SKH_LUONG)
    # Mỗi vùng MỘT neo riêng: đó là toàn bộ điểm của cấp `hang_bang`. Bốn mức
    # trong một `noi_dung` chính là ca hỏng cbd9f317 ("hai mức lương tối thiểu").
    hang = {r.so_hieu_cap: r for r in rows if r.cap is Cap.hang_bang}
    assert set(hang) == {"Vùng I", "Vùng II", "Vùng III", "Vùng IV"}
    for vung, so in (("Vùng I", "5.310.000"), ("Vùng II", "4.730.000"),
                     ("Vùng III", "4.140.000"), ("Vùng IV", "3.700.000")):
        assert so in hang[vung].noi_dung, f"thiếu mức lương {so} ở neo {vung}"
        assert hang[vung].duong_dan == f"{SKH_LUONG} > Điều 3 > Khoản 1 > {vung}"


# ══ Class của MOJ sai cấp — tin CHỮ, không tin class ═════════════════════════
# Ca thật: `124/2025/QH15` (doc_id 187742) gắn `prov-part` cho "Chương I NHỮNG
# QUY ĐỊNH CHUNG"; 9 Chương còn lại đều `prov-chapter`. Tin class thì node đó ra
# `cap=phan, so_hieu_cap=''` và `provisions_so_hieu_cap_check` (migration 005)
# ném CheckViolation, rollback CẢ lần ingest — lỗi nổ ở tầng DB, xa văn bản gây ra.
HTML_CLASS_SAI_CAP = """
<div class="WordSection1">
<p id="c1" class="MsoNormal prov-part"><b>Chương I<br>NHỮNG QUY ĐỊNH CHUNG</b></p>
<p id="c2" class="MsoNormal prov-article"><b>Điều 1. Phạm vi điều chỉnh</b></p>
<p id="c3" class="MsoNormal prov-content">Luật này quy định về giáo dục nghề nghiệp.</p>
<p id="c4" class="MsoNormal prov-chapter"><b>Chương II<br>TỔ CHỨC</b></p>
<p id="c5" class="MsoNormal prov-chapter"><b>VÀ QUẢN TRỊ CƠ SỞ GIÁO DỤC NGHỀ NGHIỆP</b></p>
<p id="c6" class="MsoNormal prov-article"><b>Điều 2. Giải thích từ ngữ</b></p>
</div>
"""


def test_prov_part_mang_chu_Chuong_duoc_doc_lai_thanh_chuong():
    rows = parse_provisions(HTML_CLASS_SAI_CAP, "124/2025/QH15")
    c1 = next(r for r in rows if r.source_node_id == "c1")
    assert c1.cap is Cap.chuong, "class prov-part nhưng chữ nói 'Chương' — chữ thắng"
    assert c1.so_hieu_cap == "I", "đọc lại cấp thì phải đọc được cả số hiệu"


def test_manh_tieu_de_tran_dong_KHONG_bi_doc_lai_cap():
    """"VÀ QUẢN TRỊ…" không mang nhãn cấp nào nên phép đọc lại phải im lặng —
    nó vẫn là phần tiếp nối tiêu đề Chương II, không phải một node mới."""
    rows = parse_provisions(HTML_CLASS_SAI_CAP, "124/2025/QH15")
    chuong = [r for r in rows if r.cap is Cap.chuong]
    assert [r.so_hieu_cap for r in chuong] == ["I", "II"]
    assert "QUẢN TRỊ" in next(r for r in chuong if r.so_hieu_cap == "II").tieu_de


def test_phan_khong_co_so_hieu_bi_CHAN_o_parser_chu_khong_o_DB():
    """Cổng parser phải HẸP BẰNG `provisions_so_hieu_cap_check` (migration 005).
    Hẹp hơn một cấp thì lỗi chỉ lộ khi ingest rollback cả lần nạp."""
    html = '<div><p class="prov-part"><b>MỘT KHỐI KHÔNG SỐ</b></p>' \
           '<p class="prov-article"><b>Điều 1. X</b></p></div>'
    with pytest.raises(ValueError, match="so_hieu_cap rỗng"):
        parse_provisions(html, "x/2026/QH15")


# ── NUỐT ANH EM: điều khoản kế tiếp bị gộp vào noi_dung của hàng liền trước ──
# Đây là chế độ hỏng nặng nhất của bảng tra: điều khoản bị nuốt KHÔNG có `id`,
# KHÔNG có `duong_dan`, nhưng nguyên văn của nó nằm trong cây con của neo liền
# trước — nên verifier tầng 1 báo ĐẠT cho một trích dẫn SAI NGUỒN. Ba cơ chế
# tách biệt, mỗi cái một ca dương tính và một ca ÂM TÍNH.

HTML_GOI_NHIEU_DIEM = """
<div class="WordSection1">
<p id="n1" class="prov-article"><b>Điều 175. Tội lạm dụng tín nhiệm</b></p>
<p id="n2" class="prov-clause">2. Phạm tội thuộc một trong các trường hợp sau đây:</p>
<p id="n3" class="prov-item">b) Có tính chất chuyên nghiệp;</p>
<p id="n4" class="prov-item">c) Chiếm đoạt tài sản trị giá từ 50.000.000 đồng đến dưới 200.000.000 đồng; d) Lợi dụng chức vụ, quyền hạn hoặc lợi dụng danh nghĩa cơ quan, tổ chức; đ) Dùng thủ đoạn xảo quyệt;</p>
<p id="n5" class="prov-item">e) Tái phạm nguy hiểm.</p>
</div>
"""


def test_mot_the_goi_BA_DIEM_duoc_tach_thanh_BA_NEO():
    """`100/2015/QH13 > Điều 175 > Khoản 2`: nguồn MOJ nhét c), d), đ) vào MỘT
    thẻ `prov-item`. Trước khi vá, Điểm d và đ không tồn tại và một câu trích
    nguyên văn Điểm d được 'kiểm chứng thành công' trên neo Điểm c."""
    rows = parse_provisions(HTML_GOI_NHIEU_DIEM, "100/2015/QH13")
    diem = [r for r in rows if r.cap is Cap.diem]
    assert [r.so_hieu_cap for r in diem] == ["b", "c", "d", "đ", "e"]
    c = next(r for r in diem if r.so_hieu_cap == "c")
    assert "Lợi dụng chức vụ" not in c.noi_dung, "Điểm d phải RỜI khỏi thân Điểm c"
    assert next(r for r in diem if r.so_hieu_cap == "d").noi_dung.startswith("d) Lợi dụng")
    # Đoạn tách ra không có node nguồn riêng — bịa lại id của thẻ cha sẽ làm hai
    # provision cùng trỏ về một node HTML.
    assert next(r for r in diem if r.so_hieu_cap == "d").source_node_id is None


def test_khoan_viet_KHONG_DAU_CHAM_van_duoc_tach():
    """`93/2015/QH13 > Điều 55 > Khoản 22` viết "…của Tòa án; 23 Đề nghị…" —
    nguồn không có dấu chấm sau 23. Dấu `;` phía trước và chữ hoa phía sau là
    hai bằng chứng đủ; đòi thêm dấu chấm thì mất cả Khoản 23."""
    html = ('<div><p class="prov-article"><b>Điều 55. Quyền của đương sự</b></p>'
            '<p class="prov-clause">22. Kháng cáo, khiếu nại bản án, quyết định '
            'của Tòa án; 23 Đề nghị người có thẩm quyền kháng nghị theo thủ tục '
            'giám đốc thẩm.</p></div>')
    rows = parse_provisions(html, "93/2015/QH13")
    assert [r.so_hieu_cap for r in rows if r.cap is Cap.khoan] == ["22", "23"]


def test_AM_TINH_dan_chieu_noi_van_KHONG_bi_cat_thanh_khoan_moi():
    """Ca ÂM TÍNH của phép tách. "quy định tại khoản 3 Điều 6" và "ngày 01 tháng
    3 năm 2020" đều có số 3 đứng sau Khoản 2 đang mở. Nới regex quá tay sẽ đẻ ra
    một "Khoản 3" giả — dựng neo trích dẫn không có trong luật, đúng loại sai
    ngược lại và nặng ngang."""
    html = ('<div><p class="prov-article"><b>Điều 62. Thẩm quyền</b></p>'
            '<p class="prov-clause">2. Thực hiện theo quy định tại khoản 3 Điều 6 '
            'Nghị định này và Nghị định số 28/2020/NĐ-CP ngày 01 tháng 3 năm 2020 '
            'của Chính phủ; mức phạt tối đa 3 lần giá trị.</p></div>')
    rows = parse_provisions(html, "12/2022/NĐ-CP")
    assert [r.so_hieu_cap for r in rows if r.cap is Cap.khoan] == ["2"]


def test_AM_TINH_luat_sua_doi_chep_nguyen_van_dieu_khoan_luat_khac():
    """Ca ÂM TÍNH thứ hai. `31/2024/QH15 > Điều 248 > Khoản 6 > Điểm b` chép
    nguyên văn khoản 2 Luật Lâm nghiệp trong “ ”, kèm cả a) b) c) của luật ĐÓ.
    Chúng thuộc văn bản khác nên tách ra là dựng neo giả — dấu “ chưa đóng là
    phép phân biệt duy nhất, vì anh em thật không tồn tại để mà lọc bằng."""
    html = ('<div><p class="prov-article"><b>Điều 248. Sửa đổi Luật Lâm nghiệp</b></p>'
            '<p class="prov-clause">6. Sửa đổi, bổ sung Điều 102 như sau:</p>'
            '<p class="prov-item">a) Sửa đổi, bổ sung khoản 1 như sau:</p>'
            '<p class="prov-item">b) Sửa đổi, bổ sung khoản 2 như sau:</p>'
            '<p class="prov-content">“2. Thẩm quyền của Ủy ban nhân dân cấp huyện '
            'được quy định như sau:</p>'
            '<p class="prov-content">a) Giao rừng đối với hộ gia đình, cá nhân;</p>'
            '<p class="prov-content">b) Giao rừng đối với cộng đồng dân cư;</p>'
            '<p class="prov-content">c) Thu hồi rừng theo quy định của Luật Đất đai.”.</p>'
            '</div>')
    rows = parse_provisions(html, "31/2024/QH15")
    assert [r.so_hieu_cap for r in rows if r.cap is Cap.diem] == ["a", "b"]
    assert "c) Thu hồi rừng" in next(
        r for r in rows if r.cap is Cap.diem and r.so_hieu_cap == "b").noi_dung


def test_prov_content_thuc_ra_la_KHOAN_ke_tiep_duoc_nang_len():
    """`108/2025/QH15 > Điều 4`: Khoản 6 mang class `prov-content` nên bị nối vào
    thân Khoản 5 và biến mất khỏi bảng tra."""
    html = ('<div><p class="prov-article"><b>Điều 4. Giải thích từ ngữ</b></p>'
            '<p class="prov-clause">5. Hệ thống thông tin quản lý thuế là hệ thống '
            'xử lý tập trung.</p>'
            '<p class="prov-content">6. Trụ sở của người nộp thuế là địa điểm người '
            'nộp thuế tiến hành hoạt động kinh doanh.</p>'
            '<p class="prov-clause">7. Mã số thuế là dãy số.</p></div>')
    rows = parse_provisions(html, "108/2025/QH15")
    assert [r.so_hieu_cap for r in rows if r.cap is Cap.khoan] == ["5", "6", "7"]


def test_AM_TINH_prov_content_mo_dau_bang_so_KHONG_thanh_khoan_moi():
    """Ca ÂM TÍNH của phép nâng cấp: một khối thân mở đầu bằng số chỉ bị đọc là
    Khoản khi số đó ĐÚNG BẰNG nhãn liền sau Khoản đang mở."""
    html = ('<div><p class="prov-article"><b>Điều 9. Thời hạn</b></p>'
            '<p class="prov-clause">5. Thời hạn giải quyết được quy định như sau.</p>'
            '<p class="prov-content">10 ngày kể từ ngày nhận đủ hồ sơ hợp lệ.</p>'
            '<p class="prov-content">30. Trường hợp phức tạp thì kéo dài.</p></div>')
    rows = parse_provisions(html, "x/2026/QH15")
    assert [r.so_hieu_cap for r in rows if r.cap is Cap.khoan] == ["5"]
    assert "10 ngày kể từ ngày" in rows[1].noi_dung
    assert "30. Trường hợp phức tạp" in rows[1].noi_dung


def test_class_prov_item_mang_nhan_KHOAN_duoc_doc_lai_thanh_khoan():
    """`88/2025/QH15 > Điều 1`: "10. Bổ sung khoản 3…" mang class `prov-item`.
    Không đọc lại cấp thì nó không có số hiệu Điểm nào, bị gộp vào Điểm c liền
    trước, và CẢ Khoản 10 biến mất."""
    html = ('<div><p class="prov-article"><b>Điều 1. Sửa đổi</b></p>'
            '<p class="prov-clause">9. Sửa đổi Điều 58 như sau:</p>'
            '<p class="prov-item">c) Sửa đổi, bổ sung khoản 5 như sau:</p>'
            '<p class="prov-item">10. Bổ sung khoản 3 vào sau khoản 2 Điều 59 '
            'như sau:</p>'
            '<p class="prov-clause">11. Sửa đổi khoản 3 Điều 60 như sau:</p></div>')
    rows = parse_provisions(html, "88/2025/QH15")
    assert [r.so_hieu_cap for r in rows if r.cap is Cap.khoan] == ["9", "10", "11"]
    assert "Bổ sung khoản 3" not in next(
        r for r in rows if r.cap is Cap.diem).noi_dung


def test_class_prov_clause_mang_nhan_DIEM_duoc_doc_lai_thanh_diem():
    """`13/2023/NĐ-CP > Điều 26 > Khoản 2`: "a) Biện pháp quản lý…" mang class
    `prov-clause` → Điểm a mất neo, dãy còn b…đ."""
    html = ('<div><p class="prov-article"><b>Điều 26. Biện pháp bảo vệ</b></p>'
            '<p class="prov-clause">2. Các biện pháp bảo vệ, bao gồm:</p>'
            '<p class="prov-clause">a) Biện pháp quản lý do tổ chức thực hiện;</p>'
            '<p class="prov-item">b) Biện pháp kỹ thuật do tổ chức thực hiện;</p>'
            '</div>')
    rows = parse_provisions(html, "13/2023/NĐ-CP")
    assert [r.so_hieu_cap for r in rows if r.cap is Cap.diem] == ["a", "b"]
    assert [r.so_hieu_cap for r in rows if r.cap is Cap.khoan] == ["2"]


def test_class_prov_clause_mang_nhan_DIEU_duoc_doc_lai_thanh_dieu():
    """27/2023/QH15 (gateway 169032): "Điều 14. Đại diện chủ sở hữu…" mang class
    `prov-clause` → khoản của Điều 14 thành khoản thứ hai cùng neo "Điều 13 >
    Khoản 1"."""
    html = (
        '<div><p class="prov-article"><b>Điều 13. Nhà ở thuộc tài sản công</b></p>'
        '<p class="prov-clause">1. Nhà ở thuộc tài sản công bao gồm:</p>'
        '<p class="prov-clause">2. Việc phát triển nhà ở thuộc tài sản công.</p>'
        '<p class="prov-clause">Điều 14. Đại diện chủ sở hữu nhà ở thuộc tài sản công</p>'
        '<p class="prov-clause">1. Bộ Xây dựng là đại diện chủ sở hữu.</p></div>'
    )
    rows = parse_provisions(html, "27/2023/QH15")
    assert [r.so_hieu_cap for r in rows if r.cap is Cap.dieu] == ["13", "14"]
    assert "27/2023/QH15 > Điều 14 > Khoản 1" in {r.duong_dan for r in rows}


def test_AM_TINH_manh_tiep_noi_khong_co_nhan_van_duoc_gop_nhu_cu():
    """Phép đọc lại cấp chỉ được chạm vào thẻ CÓ nhãn, chỉ sai tầng. Một mảnh
    tiếp nối thật (không nhãn nào cả) vẫn phải gộp vào anh em liền trước —
    không gộp thì Khoản cha bị cắt cụt và một trích dẫn ĐÚNG thất bại tầng 1."""
    html = ('<div><p class="prov-article"><b>Điều 5. Thử nghiệm</b></p>'
            '<p class="prov-clause">2. Việc thử nghiệm phải được đồng ý.</p>'
            '<p class="prov-clause">Trường hợp người được thử nghiệm là người chưa '
            'thành niên thì phải được cha, mẹ đồng ý.</p></div>')
    rows = parse_provisions(html, "91/2015/QH13")
    khoan = [r for r in rows if r.cap is Cap.khoan]
    assert len(khoan) == 1
    assert "Trường hợp người được thử nghiệm" in khoan[0].noi_dung


def test_parse_anomalies_NO_khi_dieu_khoan_bi_nuot():
    """Cổng cấu trúc chạy TRƯỚC khi ghi seed, nên đây là chỗ đúng để chặn. Cổng
    nội dung (bảo toàn ký tự) mù với lỗi này: không ký tự nào mất, chúng chỉ bị
    gán sai neo."""
    import src.services.prov_parser as pp
    html = ('<div><p class="prov-article"><b>Điều 175. Tội lạm dụng</b></p>'
            '<p class="prov-clause">2. Phạm tội trong trường hợp:</p>'
            '<p class="prov-item">c) Chiếm đoạt tài sản; d) Lợi dụng chức vụ, '
            'quyền hạn;</p></div>')
    # Tắt phép tách để dựng lại đúng trạng thái hỏng cũ.
    goc = pp._tach_lien
    pp._tach_lien = lambda cap, text: [text]
    try:
        loi, _ = parse_anomalies(html, "100/2015/QH13")
    finally:
        pp._tach_lien = goc
    assert len(loi) == 1, loi
    assert "NUỐT ANH EM" in loi[0] and "Điểm d" in loi[0]


def test_parse_anomalies_chi_CANH_BAO_khi_nguon_thieu_han_mot_nhan():
    """`100/2015/QH13 > Điều 278 > Khoản 2`: HTML nguồn nhảy từ d) sang e), không
    thẻ nào chứa Điểm đ. Parser không dựng lại được thứ nguồn không có, nên đây
    phải là CẢNH BÁO — raise sẽ chặn vĩnh viễn cả Bộ luật Hình sự."""
    html = ('<div><p class="prov-article"><b>Điều 278. Tội cản trở</b></p>'
            '<p class="prov-clause">2. Phạm tội trong trường hợp:</p>'
            '<p class="prov-item">c) Gây thương tích;</p>'
            '<p class="prov-item">d) Gây thiệt hại về tài sản;</p>'
            '<p class="prov-item">e) Là người có trách nhiệm.</p></div>')
    loi, canh_bao = parse_anomalies(html, "100/2015/QH13")
    assert loi == []
    assert any("ĐỨT DÃY" in x and "'đ'" in x for x in canh_bao), canh_bao


def test_bang_luong_KHONG_con_bao_BANG_KET_vi_da_duoc_tach():
    """Nghịch đảo của cảnh báo: bảng lương từng là ca `BẢNG KẸT` nặng nhất
    (4 hàng trong MỘT neo → "hai mức lương tối thiểu"). Nay nó được tách nên
    cảnh báo phải TẮT — cảnh báo còn kêu ở đây nghĩa là phép tách đã hỏng."""
    html = ('<div><p class="prov-article"><b>Điều 3. Mức lương tối thiểu</b></p>'
            '<p class="prov-clause">1. Quy định mức lương tối thiểu tháng theo '
            'vùng như sau:</p>'
            '<table><tr><td>Vùng</td><td>Mức lương tối thiểu tháng</td></tr>'
            '<tr><td>Vùng I</td><td>5.310.000</td></tr>'
            '<tr><td>Vùng II</td><td>4.730.000</td></tr></table>'
            '<p class="prov-clause">2. Danh mục địa bàn vùng do Chính phủ quy '
            'định.</p></div>')
    loi, canh_bao = parse_anomalies(html, "293/2025/NĐ-CP")
    assert loi == []
    assert not any("BẢNG KẸT" in x for x in canh_bao), canh_bao
    assert [r.so_hieu_cap for r in parse_provisions(html, "293/2025/NĐ-CP")
            if r.cap is Cap.hang_bang] == ["Vùng I", "Vùng II"]


def test_AM_TINH_bang_MOT_hang_khong_bi_bao_la_danh_sach():
    """Ca ÂM TÍNH: công thức tính lương làm thêm giờ (`145/2020 > Điều 55 >
    Khoản 1`) cũng được dàn trang bằng <table>, nhưng nó là MỘT hàng — không
    phải liệt kê. Báo nó là "bảng kẹt" sẽ dẫn tới tách một công thức thành năm
    'điểm con', tức dựng năm neo không có trong luật."""
    html = ('<div><p class="prov-article"><b>Điều 55. Tiền lương làm thêm giờ</b></p>'
            '<p class="prov-clause">1. Đối với người lao động hưởng lương theo '
            'thời gian, tiền lương làm thêm giờ được tính như sau:</p>'
            '<table><tr><td>Tiền lương làm thêm giờ</td><td>=</td>'
            '<td>Tiền lương giờ thực trả</td><td>x</td><td>Mức ít nhất 150%</td>'
            '</tr></table>'
            '<p class="prov-clause">2. Đối với người lao động hưởng lương theo '
            'sản phẩm thì áp dụng tương tự.</p></div>')
    _, canh_bao = parse_anomalies(html, "145/2020/NĐ-CP")
    assert not any("BẢNG KẸT" in x for x in canh_bao), canh_bao


def test_prov_content_thuc_ra_la_KHOAN_1_cua_dieu_duoc_nang_len():
    """`84/2015/QH13 > Điều 33` và `91/2015/QH13 > Điều 490` gắn `prov-content`
    cho Khoản 1 ngay dưới dòng tiêu đề Điều. Không nâng thì Khoản 1 mất neo VÀ
    mọi Điểm của nó treo thẳng vào Điều — `duong_dan` của chúng nhảy mất một
    tầng ("Điều 33 > Điểm a" thay vì "Điều 33 > Khoản 1 > Điểm a")."""
    html = ('<div><p class="prov-article"><b>Điều 33. Trách nhiệm của các bộ</b></p>'
            '<p class="prov-content">1. Các bộ có trách nhiệm quản lý nhà nước '
            'như sau:</p>'
            '<p class="prov-item">a) Bộ Y tế chịu trách nhiệm;</p>'
            '<p class="prov-clause">2. Bộ Lao động chủ trì.</p></div>')
    rows = parse_provisions(html, "84/2015/QH13")
    assert [r.so_hieu_cap for r in rows if r.cap is Cap.khoan] == ["1", "2"]
    assert next(r for r in rows if r.cap is Cap.diem).duong_dan == \
        "84/2015/QH13 > Điều 33 > Khoản 1 > Điểm a"


def test_AM_TINH_prov_content_mo_dau_bang_so_o_DIEU_da_co_khoan():
    """Ca ÂM TÍNH: điều kiện là "Điều CHƯA có Khoản nào", không phải "mở đầu
    bằng 1.". Một Điều đã có Khoản thì khối thân mở đầu bằng số là văn xuôi —
    tách nó ra là dựng một Khoản 1 thứ hai, tức một neo trùng."""
    html = ('<div><p class="prov-article"><b>Điều 7. Mức phạt</b></p>'
            '<p class="prov-clause">1. Phạt tiền theo khung sau đây.</p>'
            '<p class="prov-content">1. đến 5. của khung này áp dụng cho cá nhân.</p>'
            '</div>')
    rows = parse_provisions(html, "x/2026/QH15")
    khoan = [r for r in rows if r.cap is Cap.khoan]
    assert [r.so_hieu_cap for r in khoan] == ["1"]
    assert "áp dụng cho cá nhân" in khoan[0].noi_dung


# ── hang_bang: mỗi HÀNG DỮ LIỆU của bảng là một neo trích dẫn riêng ─────────
# Quyết định 2026-09-02 của chủ dự án. `so_hieu_cap` đọc từ CỘT 1 của chính
# bảng, không mượn nhãn Điểm — xem migrations/017.

HTML_BANG_LUONG = """
<div class="WordSection1">
<p class="prov-article"><b>Điều 3. Mức lương tối thiểu</b></p>
<p class="prov-clause">1. Quy định mức lương tối thiểu tháng và mức lương tối thiểu giờ theo vùng như sau:</p>
<table>
<tr><td>Vùng</td><td>Mức lương tối thiểu tháng</td><td>Mức lương tối thiểu giờ</td></tr>
<tr><td>Vùng I</td><td>5.310.000</td><td>25.500</td></tr>
<tr><td>Vùng II</td><td>4.730.000</td><td>22.700</td></tr>
<tr><td>Vùng III</td><td>4.140.000</td><td>20.000</td></tr>
<tr><td>Vùng IV</td><td>3.700.000</td><td>17.800</td></tr>
</table>
<p class="prov-clause">2. Danh mục địa bàn vùng do Chính phủ quy định.</p>
</div>
"""


def test_bang_luong_thanh_BON_neo_trich_dan_rieng():
    """Ca hỏng gốc: bốn vùng là MỘT neo nên mô hình trích hai hàng rồi kết luận
    "hai mức lương tối thiểu", và bảy phép kiểm vẫn xanh."""
    rows = parse_provisions(HTML_BANG_LUONG, "293/2025/NĐ-CP")
    hang = [r for r in rows if r.cap is Cap.hang_bang]
    assert [r.so_hieu_cap for r in hang] == ["Vùng I", "Vùng II", "Vùng III", "Vùng IV"]
    assert hang[2].duong_dan == "293/2025/NĐ-CP > Điều 3 > Khoản 1 > Vùng III"
    # `noi_dung` LÀ hàng markdown: đúng chuỗi mô hình trích và verify_tier1 đối
    # chiếu vào. Đo được từ trace 13f3a5ec.
    assert hang[2].noi_dung == "| Vùng III | 4.140.000 | 20.000 |"


def test_hang_bang_treo_vao_KHOAN_gioi_thieu_bang():
    rows = parse_provisions(HTML_BANG_LUONG, "293/2025/NĐ-CP")
    khoan1 = next(r for r in rows if r.duong_dan.endswith("Khoản 1"))
    hang = [r for r in rows if r.cap is Cap.hang_bang]
    assert {r.parent_local_id for r in hang} == {khoan1.local_id}
    # Khoản 2 đứng SAU bảng vẫn là con của Điều, không của hàng bảng cuối —
    # hàng bảng cố ý không vào stack.
    khoan2 = next(r for r in rows if r.duong_dan.endswith("Khoản 2"))
    assert khoan2.parent_local_id == next(
        r for r in rows if r.cap is Cap.dieu).local_id


def test_hang_TIEU_DE_o_lai_Khoan_cha_va_KHONG_thanh_neo():
    """Hàng tiêu đề là nhãn cột, không phải văn bản quy phạm — nó không được
    thành neo. Nhưng bỏ hẳn thì tên cột biến mất và không ai dựng lại được bảng,
    nên nó ở lại `noi_dung` của Khoản cha."""
    rows = parse_provisions(HTML_BANG_LUONG, "293/2025/NĐ-CP")
    assert "Vùng" not in [r.so_hieu_cap for r in rows if r.cap is Cap.hang_bang]
    khoan1 = next(r for r in rows if r.duong_dan.endswith("Khoản 1"))
    assert "| Vùng | Mức lương tối thiểu tháng | Mức lương tối thiểu giờ |" in khoan1.noi_dung
    # Hàng DỮ LIỆU thì KHÔNG còn ở cha: nếu còn, một quote hàng khớp ở CẢ HAI
    # dòng, `_tim_quote` trả về cha, và hai citation lại chung một khop_tai_id —
    # đúng lỗi đang chữa, chỉ là quay lại qua cửa khác.
    assert "4.140.000" not in khoan1.noi_dung


def test_o_cot_1_khong_tu_mo_ta_thi_ghep_TIEU_DE_COT():
    """Bảng thuế ghi cột 1 là `1`. Neo `… > Khoản 2 > 1` không phân biệt được
    với Khoản 1 hay Điểm 1; ghép tiêu đề cột thành `Bậc thuế 1` — cũng đúng cách
    người Việt dẫn biểu thuế luỹ tiến."""
    html = ('<div><p class="prov-article"><b>Điều 9. Biểu thuế</b></p>'
            '<p class="prov-clause">2. Biểu thuế luỹ tiến từng phần như sau:</p>'
            '<table><tr><td>Bậc thuế</td><td>Thu nhập</td><td>Thuế suất</td></tr>'
            '<tr><td>1</td><td>Đến 120</td><td>5</td></tr>'
            '<tr><td>2</td><td>Trên 120 đến 360</td><td>10</td></tr></table>'
            '<p class="prov-clause">3. Chính phủ quy định chi tiết.</p></div>')
    rows = parse_provisions(html, "109/2025/QH15")
    hang = [r for r in rows if r.cap is Cap.hang_bang]
    assert [r.so_hieu_cap for r in hang] == ["Bậc thuế 1", "Bậc thuế 2"]
    assert hang[0].duong_dan == "109/2025/QH15 > Điều 9 > Khoản 2 > Bậc thuế 1"


def test_AM_TINH_bang_tieu_de_HAI_TANG_khong_bi_ep_tach():
    """`135/2020/NĐ-CP > Điều 4 > Khoản 2` (lộ trình hưu nam/nữ): hàng đầu 2 ô,
    16 hàng sau 4 ô, và 7 hàng cuối có cột 1 RỖNG vì ô gộp bẹp khi sang markdown.
    Ép tách sẽ đẻ ra 7 neo `so_hieu_cap` rỗng — thứ
    `provisions_so_hieu_cap_check` chặn. Thà để nguyên và ghi ra."""
    html = ('<div><p class="prov-article"><b>Điều 4. Lộ trình</b></p>'
            '<p class="prov-clause">2. Lộ trình theo bảng dưới đây:</p>'
            '<table>'
            '<tr><td>Lao động nam</td><td>Lao động nữ</td></tr>'
            '<tr><td>Năm nghỉ hưu</td><td>Tuổi</td><td>Năm nghỉ hưu</td><td>Tuổi</td></tr>'
            '<tr><td>2021</td><td>60 tuổi 3 tháng</td><td>2021</td><td>55 tuổi 4 tháng</td></tr>'
            '<tr><td></td><td></td><td>2029</td><td>58 tuổi</td></tr>'
            '</table>'
            '<p class="prov-clause">3. Bộ trưởng hướng dẫn.</p></div>')
    rows = parse_provisions(html, "135/2020/NĐ-CP")
    assert [r for r in rows if r.cap is Cap.hang_bang] == []
    khoan2 = next(r for r in rows if r.duong_dan.endswith("Khoản 2"))
    assert "60 tuổi 3 tháng" in khoan2.noi_dung, "để nguyên nghĩa là KHÔNG mất chữ"
    _, canh_bao = parse_anomalies(html, "135/2020/NĐ-CP")
    assert any("BẢNG KẸT" in c and "số ô không đều" in c for c in canh_bao), canh_bao


def test_AM_TINH_bang_MOT_hang_du_lieu_khong_bi_tach():
    """`31/2024/QH15 > Điều 243 > Khoản 4`: tiêu đề + đúng 1 hàng. Không có anh
    em nào để phép so tập con đối chiếu, nên tách chỉ thêm một tầng cây."""
    html = ('<div><p class="prov-article"><b>Điều 243. Sửa Phụ lục II</b></p>'
            '<p class="prov-clause">4. Bổ sung quy hoạch số thứ tự 1a như sau:</p>'
            '<table><tr><td>STT</td><td>TÊN QUY HOẠCH</td></tr>'
            '<tr><td>1a.</td><td>Quy hoạch sử dụng đất cấp tỉnh</td></tr></table>'
            '<p class="prov-clause">5. Điều khoản thi hành.</p></div>')
    rows = parse_provisions(html, "31/2024/QH15")
    assert [r for r in rows if r.cap is Cap.hang_bang] == []
    _, canh_bao = parse_anomalies(html, "31/2024/QH15")
    assert any("chỉ 1 hàng dữ liệu" in c for c in canh_bao), canh_bao


def test_AM_TINH_cong_thuc_trong_bang_khong_bi_tach():
    """`145/2020 > Điều 55 > Khoản 1` xếp một CÔNG THỨC vào ô bảng. Một hàng, và
    tách nó thành 'điểm con' là dựng năm neo không có trong Nghị định."""
    html = ('<div><p class="prov-article"><b>Điều 55. Tiền lương làm thêm giờ</b></p>'
            '<p class="prov-clause">1. Tiền lương làm thêm giờ tính như sau:</p>'
            '<table><tr><td>Tiền lương làm thêm giờ</td><td>=</td>'
            '<td>Tiền lương giờ thực trả</td><td>x</td><td>150%</td></tr></table>'
            '<p class="prov-clause">2. Áp dụng tương tự cho lương sản phẩm.</p></div>')
    rows = parse_provisions(html, "145/2020/NĐ-CP")
    assert [r for r in rows if r.cap is Cap.hang_bang] == []


def test_tach_bang_KHONG_lam_lech_phep_bao_toan_ky_tu():
    """Hàng dữ liệu chuyển từ cha sang con, tiêu đề ở lại — tổng ký tự không đổi,
    nên cổng bảo toàn vẫn khít tuyệt đối."""
    loi, _ = parse_anomalies(HTML_BANG_LUONG, "293/2025/NĐ-CP")
    assert loi == []


def test_hang_bang_la_cap_TRICH_DAN_DUOC():
    """Cả mục đích của cấp này là để mỗi hàng thành một neo kiểm chứng được, nên
    nó phải chịu ĐÚNG hai bất biến của cấp trích dẫn được (migrations/017)."""
    from src.services.prov_parser import CITABLE
    assert Cap.hang_bang in CITABLE
