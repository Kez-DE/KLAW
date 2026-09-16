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

import pytest

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


# ──────────────────────── một tài liệu: KHÔNG được khẳng định một so sánh
# Đo trên tập mẫu 2026-09-16, ba lần liên tiếp: với MỘT bản nội quy, mô hình
# vẫn viết "bản này khác bản trước đó về thời giờ làm việc, chế độ nghỉ phép…".
# Không có tài liệu thứ hai nào tồn tại, nên câu ấy không có nguồn — đúng chế
# độ hỏng cả tính năng này tồn tại để chặn. `can_du_kien` nói đúng nhưng nói
# SAU khi văn xuôi đã khẳng định xong.


def test_mot_tai_lieu_thi_cau_tra_loi_KHONG_khang_dinh_khac_biet():
    llm = _LLM(_ra(
        muc_dich="so_sanh",
        tra_loi_ngan="Bản này khác bản trước đó về thời giờ làm việc và chế độ nghỉ phép.",
    ))
    ra = h.hieu_tai_lieu(ST, MOT, llm, "m")
    k = ra["tai_lieu_ket"]
    assert k["tra_loi_ngan"] == h.SO_SANH_THIEU_TAI_LIEU
    assert h.CAN_TAI_LIEU_THU_HAI in k["can_du_kien"]
    assert k["khac_biet"] == []


def test_hai_tai_lieu_thi_cau_tra_loi_cua_mo_hinh_duoc_giu():
    llm = _LLM(_ra(muc_dich="so_sanh", tra_loi_ngan="Hai bản khác nhau ở thời giờ làm việc."))
    ra = h.hieu_tai_lieu(ST, TL, llm, "m")
    assert ra["tai_lieu_ket"]["tra_loi_ngan"] == "Hai bản khác nhau ở thời giờ làm việc."


def test_mot_tai_lieu_muc_dich_KHAC_thi_khong_doi_gi():
    """Chỉ lượt SO SÁNH mới bị thay câu trả lời: một lượt tóm tắt trên một tài
    liệu là chuyện bình thường."""
    llm = _LLM(_ra(muc_dich="tom_tat", tra_loi_ngan="Phiếu đánh giá bốn tiêu chí."))
    ra = h.hieu_tai_lieu(ST, MOT, llm, "m")
    assert ra["tai_lieu_ket"]["tra_loi_ngan"] == "Phiếu đánh giá bốn tiêu chí."


# ───────── lời NGƯỜI HỎI quyết định, không phải nhãn mô hình vừa chọn
# Đo năm lần 2026-09-16: cùng một câu hỏi, mô hình lúc gán `so_sanh` lúc gán
# `hoi`, và ở nhánh `hoi` thì câu khẳng định "khác bản trước đó" đi thẳng ra
# người dùng. Gác trên nhãn của mô hình nghĩa là một phép kiểm an toàn bật tắt
# theo tâm trạng nó — cùng lý do `route.chac_chan_meta` và `kho.xin_dang_bang`
# gác bằng chính chữ người dùng gõ.


@pytest.mark.parametrize(
    "cau_hoi",
    [
        "So sánh bản nội quy này với bản trước đó khác nhau chỗ nào?",
        "Hai tài liệu này khác nhau ở đâu?",
        "Đối chiếu với bản cũ giúp tôi",
        "so sánh giúp tôi hai bản",
        "bản này có gì khác so với bản trước",
    ],
)
def test_cau_hoi_XIN_SO_SANH_ma_chi_co_mot_tai_lieu(cau_hoi):
    llm = _LLM(_ra(muc_dich="hoi", tra_loi_ngan="Bản này khác bản trước đó về thời giờ làm việc."))
    ra = h.hieu_tai_lieu({"query": cau_hoi}, MOT, llm, "m")
    k = ra["tai_lieu_ket"]
    assert k["tra_loi_ngan"] == h.SO_SANH_THIEU_TAI_LIEU
    assert h.CAN_TAI_LIEU_THU_HAI in k["can_du_kien"]


@pytest.mark.parametrize(
    "cau_hoi",
    ["Phiếu này chấm theo tiêu chí nào?", "Tóm tắt giúp tôi", "Điều 3 khác Điều 2 chỗ nào?"],
)
def test_cau_hoi_KHONG_xin_so_sanh_thi_khong_doi_gi(cau_hoi):
    """"Điều 3 khác Điều 2" là so sánh TRONG một tài liệu — không cần tài liệu
    thứ hai, và chặn nó là chặn một câu hỏi hợp lệ."""
    llm = _LLM(_ra(muc_dich="hoi", tra_loi_ngan="Câu trả lời bình thường."))
    ra = h.hieu_tai_lieu({"query": cau_hoi}, MOT, llm, "m")
    assert ra["tai_lieu_ket"]["tra_loi_ngan"] == "Câu trả lời bình thường."


def test_hai_tai_lieu_thi_cau_hoi_so_sanh_khong_bi_chan():
    llm = _LLM(_ra(muc_dich="so_sanh", tra_loi_ngan="Hai bản khác nhau ở thời giờ làm việc."))
    ra = h.hieu_tai_lieu({"query": "So sánh hai bản này"}, TL, llm, "m")
    assert ra["tai_lieu_ket"]["tra_loi_ngan"] == "Hai bản khác nhau ở thời giờ làm việc."
