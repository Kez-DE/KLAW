import pytest

from src.agents.nodes.suy_dien import suy_dien, suy_vai

NLD = "người lao động"
NSDLD = "người sử dụng lao động"


@pytest.mark.parametrize(
    "cau, vai",
    [
        ("tôi sắp nghỉ việc, hãy đưa cho tôi luật để đảm bảo quyền lợi", NLD),
        ("em bị sa thải không có lý do", NLD),
        ("mình bị trừ lương vì đi muộn", NLD),
        ("tôi đang thử việc thì công ty cho nghỉ", NLD),
        ("công ty nợ lương tôi hai tháng", NLD),
        ("tôi xin nghỉ không lương được không", NLD),
        ("hợp đồng lao động của tôi hết hạn thì sao", NLD),
        ("tôi làm ở công ty 3 năm, muốn nghỉ", NLD),
        ("công ty tôi có được sa thải nhân viên đi muộn không", NSDLD),
        ("nhân viên của tôi tự ý bỏ việc", NSDLD),
        ("tôi là trưởng phòng nhân sự, cần xử lý kỷ luật", NSDLD),
        ("tôi là giám đốc, muốn chấm dứt hợp đồng với một nhân viên", NSDLD),
        ("doanh nghiệp chúng tôi muốn cắt giảm lao động", NSDLD),
        ("bên tôi tuyển người thử việc 3 tháng được không", NSDLD),
        ("thời gian thử việc tối đa là bao lâu", None),
        ("so sánh trợ cấp thôi việc và trợ cấp mất việc", None),
        ("Điều 35 Bộ luật Lao động nói gì", None),
        ("người lao động được nghỉ phép bao nhiêu ngày", None),
        ("bạn là ai", None),
        ("công ty phải báo trước bao nhiêu ngày khi cho nghỉ", None),
    ],
)
def test_suy_vai(cau, vai):
    assert suy_vai(cau) == vai


def test_node_dien_chu_the_khi_trong_va_khong_de_khi_da_co():
    st = suy_dien({"query": "tôi sắp nghỉ việc", "ho_so": {}, "traces": {}})
    assert st["ho_so"]["chu_the"] == {"gia_tri": NLD, "nguon": "suy_dien"}
    assert st["traces"]["suy_dien_chu_the"] == NLD
    da_co = {"chu_the": {"gia_tri": NSDLD, "nguon": "nguoi_noi"}}
    st2 = suy_dien({"query": "tôi sắp nghỉ việc", "ho_so": da_co, "traces": {}})
    assert st2["ho_so"]["chu_the"]["gia_tri"] == NSDLD and st2["traces"]["suy_dien_chu_the"] is None
    st3 = suy_dien({"query": "thử việc tối đa bao lâu", "cau_hoi_day_du": None, "traces": {}})
    assert "chu_the" not in st3["ho_so"] and st3["traces"]["suy_dien_chu_the"] is None
