import json
from pathlib import Path

import pytest

from src.models.domain import Cap
from src.services.prov_parser import parse_provisions, parse_tables

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
