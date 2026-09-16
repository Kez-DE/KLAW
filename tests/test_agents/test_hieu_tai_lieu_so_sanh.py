"""GĐ2 của node `hieu_tai_lieu`: SO SÁNH HAI TÀI LIỆU
(plan `tai-lieu-tong-quat.md` S4, FR-014).

Một khác biệt là hai câu, mỗi câu của một tài liệu. Vì thế nó phải neo được ở
CẢ HAI phía: một khác biệt chỉ neo được một bên là một nửa bằng chứng, và một
nửa bằng chứng trình bày như một khác biệt đã kiểm là đúng thứ dự án này tồn
tại để không làm. Neo một bên hỏng → cả cặp bị bỏ.

Với MỘT tài liệu thì không có gì để so. Node nói thẳng là thiếu tài liệu thứ
hai (`can_du_kien`) thay vì gọi lại mô hình — hỏi lại một mô hình không có dữ
liệu chỉ tốn thêm một lượt để nhận cùng một câu trả lời.
"""

from src.agents.nodes import hieu_tai_lieu as h
from tests.test_agents.test_hieu_tai_lieu import _LLM, A_ID, B_ID, MOT, ST, TL, _ra

TRICH_A = "Tổng điểm tối đa là 10 cho bốn tiêu chí"
TRICH_B = "Hợp đồng lao động số 12/2026 ký ngày 01/10/2026"


def _kb(noi_dung="Hai tài liệu nói về hai việc khác nhau", a=TRICH_A, b=TRICH_B):
    return {"noi_dung": noi_dung, "trich_a": a, "trich_b": b}


def test_khac_biet_neo_ca_hai_phia():
    llm = _LLM(_ra(muc_dich="so_sanh", khac_biet=[_kb()]))
    ra = h.hieu_tai_lieu(ST, TL, llm, "m")
    kb = ra["tai_lieu_ket"]["khac_biet"]
    assert len(kb) == 1
    assert kb[0]["noi_dung"] == "Hai tài liệu nói về hai việc khác nhau"
    assert kb[0]["neo_a"]["tai_lieu_id"] == A_ID and kb[0]["neo_a"]["chi_so_don_vi"] == 1
    assert kb[0]["neo_b"]["tai_lieu_id"] == B_ID and kb[0]["neo_b"]["chi_so_don_vi"] == 0
    assert ra["traces"]["hieu_tai_lieu_so_khac_biet"] == 1


def test_mot_ben_khong_neo_duoc_thi_bo_ca_cap():
    llm = _LLM(_ra(muc_dich="so_sanh", khac_biet=[
        _kb(b="câu này không hề có trong hợp đồng của người ta"),
        _kb(a="câu này cũng không có trong phiếu chấm đâu"),
    ]))
    ra = h.hieu_tai_lieu(ST, TL, llm, "m")
    assert ra["tai_lieu_ket"]["khac_biet"] == []
    assert ra["traces"]["hieu_tai_lieu_so_khac_biet_bo"] == 2


def test_trich_doi_ben_KHONG_neo_cheo():
    """Đoạn của B đặt ở `trich_a` không được neo sang B — mỗi phía tra trong
    đúng tài liệu của nó."""
    llm = _LLM(_ra(muc_dich="so_sanh", khac_biet=[_kb(a=TRICH_B, b=TRICH_A)]))
    assert h.hieu_tai_lieu(ST, TL, llm, "m")["tai_lieu_ket"]["khac_biet"] == []


def test_muc_dich_so_sanh_khong_con_bi_ha_thanh_hoi():
    ra = h.hieu_tai_lieu(ST, TL, _LLM(_ra(muc_dich="so_sanh")), "m")
    assert ra["tai_lieu_ket"]["muc_dich"] == "so_sanh"


def test_mot_tai_lieu_thi_xin_tai_lieu_thu_hai():
    llm = _LLM(_ra(muc_dich="so_sanh", khac_biet=[_kb()]))
    ket = h.hieu_tai_lieu(ST, MOT, llm, "m")["tai_lieu_ket"]
    assert "tài liệu thứ hai" in ket["can_du_kien"]
    assert ket["khac_biet"] == [], "không có tài liệu B thì không có khác biệt nào neo được"


def test_khong_so_sanh_thi_khong_xin_them_tai_lieu():
    ket = h.hieu_tai_lieu(ST, MOT, _LLM(_ra(muc_dich="hoi")), "m")["tai_lieu_ket"]
    assert "tài liệu thứ hai" not in ket["can_du_kien"]


def test_khac_biet_rong_khi_khong_so_sanh():
    llm = _LLM(_ra(muc_dich="hoi", khac_biet=[_kb()]))
    assert h.hieu_tai_lieu(ST, TL, llm, "m")["tai_lieu_ket"]["khac_biet"] == []


def test_schema_co_du_ba_mang_moi_cua_S4():
    s = h.schema_hieu(["A", "B"])["properties"]
    assert set(s["phep_tinh"]["items"]["required"]) == {"bieu_thuc", "ket_qua_tai_lieu", "trich"}
    assert set(s["truong"]["items"]["required"]) == {"khoa", "nhan", "gia_tri", "trich"}
    assert set(s["khac_biet"]["items"]["required"]) == {"noi_dung", "trich_a", "trich_b"}


def test_ket_qua_day_du_van_tuan_tu_hoa_duoc_qua_TaiLieuKetQuaOut():
    """Chế độ hỏng đã xảy ra một lần trong dự án (`gioi_thieu`, 2026-09-01):
    node dựng đúng kết quả rồi cả lượt chết ở khâu tuần tự hoá."""
    from src.models.schemas import TaiLieuKetQuaOut

    llm = _LLM(_ra(
        muc_dich="so_sanh",
        khac_biet=[_kb()],
        phep_tinh=[{"bieu_thuc": "2,0 + 8,0", "ket_qua_tai_lieu": "10", "trich": TRICH_A}],
    ))
    ket = h.hieu_tai_lieu(ST, TL, llm, "m")["tai_lieu_ket"]
    ra = TaiLieuKetQuaOut(**ket)
    assert ra.phep_tinh[0].khop is True and ra.phep_tinh[0].neo.tai_lieu_id == A_ID
    assert ra.khac_biet[0].neo_b.tai_lieu_id == B_ID
