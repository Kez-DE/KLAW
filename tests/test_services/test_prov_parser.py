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
