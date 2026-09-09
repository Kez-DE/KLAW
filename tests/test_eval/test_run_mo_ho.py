"""Đo `run_mo_ho.dung`/`tra_loi_dat_chuan`/`tom_tat` — hàm THUẦN, không cần
graph/mạng (spec 2026-09-09 §7.7: câu mơ hồ có chủ đích phải được TRẢ LỜI kèm
giả định, không abstain oan).

Cùng cam kết `eval/run_trap.py::chay` và `eval/run_hoi_thoai.py::tom_tat_diem`: một
câu lỗi hạ tầng không có khoá `dung`/`result_type` và không được tính vào CẢ tử số
lẫn mẫu số của tỉ lệ đúng — loại riêng ra `so_loi`, không phải một câu trả lời sai.

Review round 1 (Important): `suy_dien` (zero-token, chạy TRƯỚC hành văn) đã quyết
định `chu_the` trong `ho_so_da_dung` trên cả 20 câu của `mo_ho.yaml`, nên riêng
"không abstain + đúng vai trong hồ sơ" đúng ngay cả khi mô hình bỏ qua
`assemble.v3` hoàn toàn — lặp lại câu hỏi, không bao giờ nêu dòng giả định. Từ đây
`dung()` có thêm nửa thứ hai (`tra_loi_dat_chuan`) đọc thẳng `answer`; các test
`test_dung_lap_lai_cau_hoi_thi_sai_du_vai_va_result_type_dung` và
`test_dung_khong_neu_gia_dinh_thi_sai_du_vai_va_result_type_dung` khoá lại đúng
phát hiện đó ở mức `dung()`, còn các test `test_tra_loi_dat_chuan_*` khoá trực
tiếp hàm thuần mới.
"""

from eval.run_mo_ho import dung, tom_tat, tra_loi_dat_chuan

_CAU_HOI = "tôi sắp nghỉ việc, hãy đưa cho tôi luật để đảm bảo quyền lợi cho tôi"


def test_dung_can_answer_va_gia_dinh_dung():
    it = {"ky_vong": {"chu_the": "người lao động", "khong_abstain": True}, "cau_hoi": _CAU_HOI}
    ok = {
        "result_type": "answer",
        "answer": "Tôi hiểu bạn là người lao động. Công ty phải báo trước 45 ngày.",
        "ho_so_da_dung": [{"khoa": "chu_the", "gia_tri": "người lao động", "gia_dinh": True}],
    }
    assert dung(it, ok) is True
    assert dung(it, {**ok, "result_type": "abstain"}) is False
    assert dung(it, {**ok, "ho_so_da_dung": []}) is False


def test_dung_suy_sai_phia_thi_sai():
    """Suy ra CÓ vai nhưng đảo phía (NSDLD thay vì NLD) không được tính là đúng —
    "người lao động" không phải substring của "người sử dụng lao động" hay ngược lại."""
    it = {"ky_vong": {"chu_the": "người lao động", "khong_abstain": True}}
    payload = {
        "result_type": "answer",
        "ho_so_da_dung": [{"khoa": "chu_the", "gia_tri": "người sử dụng lao động", "gia_dinh": True}],
    }
    assert dung(it, payload) is False


def test_dung_doc_duoc_result_type_dang_enum():
    """`result_type` từ payload thật là `ResultType` (StrEnum), không phải chuỗi trần."""
    from src.agents.nodes.assemble import ResultType

    it = {"ky_vong": {"chu_the": "người lao động", "khong_abstain": True}, "cau_hoi": _CAU_HOI}
    payload = {
        "result_type": ResultType.partial_coverage,
        "answer": "Tôi hiểu bạn là người lao động. Công ty phải báo trước 45 ngày.",
        "ho_so_da_dung": [{"khoa": "chu_the", "gia_tri": "người lao động", "gia_dinh": True}],
    }
    assert dung(it, payload) is True


def test_dung_lap_lai_cau_hoi_thi_sai_du_vai_va_result_type_dung():
    """Đúng phát hiện review round 1: vai đã đúng và không abstain KHÔNG đủ — mô
    hình lặp lại câu hỏi (bỏ qua assemble.v3) phải bị tính sai."""
    it = {"ky_vong": {"chu_the": "người lao động", "khong_abstain": True}, "cau_hoi": _CAU_HOI}
    payload = {
        "result_type": "answer",
        "answer": f"Về việc {_CAU_HOI}, đây là một số quy định liên quan.",
        "ho_so_da_dung": [{"khoa": "chu_the", "gia_tri": "người lao động", "gia_dinh": True}],
    }
    assert dung(it, payload) is False


def test_dung_khong_neu_gia_dinh_thi_sai_du_vai_va_result_type_dung():
    """Vai tới từ suy diễn (`gia_dinh: true`) mà answer không nêu dòng giả định
    thì vẫn sai — cùng phát hiện review round 1."""
    it = {"ky_vong": {"chu_the": "người lao động", "khong_abstain": True}, "cau_hoi": _CAU_HOI}
    payload = {
        "result_type": "answer",
        "answer": "Công ty phải báo trước 45 ngày trước khi chấm dứt hợp đồng.",
        "ho_so_da_dung": [{"khoa": "chu_the", "gia_tri": "người lao động", "gia_dinh": True}],
    }
    assert dung(it, payload) is False


def test_tra_loi_dat_chuan_lap_lai_cau_hoi_thi_sai():
    answer = f"Bạn hỏi là {_CAU_HOI}. Đây là quy định liên quan."
    assert tra_loi_dat_chuan(answer, _CAU_HOI, True) is False


def test_tra_loi_dat_chuan_neu_dung_gia_dinh_thi_dat():
    answer = "Tôi hiểu bạn là người lao động. Công ty phải báo trước 45 ngày trước khi chấm dứt hợp đồng."
    assert tra_loi_dat_chuan(answer, _CAU_HOI, True) is True


def test_tra_loi_dat_chuan_khong_lap_nhung_cung_khong_neu_gia_dinh_thi_sai():
    answer = "Công ty phải báo trước 45 ngày trước khi chấm dứt hợp đồng."
    assert tra_loi_dat_chuan(answer, _CAU_HOI, True) is False


def test_tra_loi_dat_chuan_vai_khong_phai_suy_dien_thi_khong_doi_dong_gia_dinh():
    """`can_neu_gia_dinh=False` (người nói tự khai vai, không phải máy đoán) thì
    không đòi dòng "Tôi hiểu bạn là" — chỉ đòi không lặp lại câu hỏi."""
    answer = "Công ty phải báo trước 45 ngày trước khi chấm dứt hợp đồng."
    assert tra_loi_dat_chuan(answer, _CAU_HOI, False) is True


def test_tom_tat_loai_cau_loi_khoi_ca_tu_va_mau_so():
    ket = [
        {"id": "mh-001", "dung": True, "result_type": "answer"},
        {"id": "mh-002", "dung": False, "result_type": "abstain"},
        {"id": "mh-003", "error_type": "RuntimeError", "error": "mạng"},
    ]
    tt = tom_tat(ket)
    assert tt == {"so_cham": 2, "dung": 1, "so_loi": 1, "abstain_oan": 1, "ty_le_dung": 0.5}


def test_tom_tat_rong_khong_chia_cho_0():
    assert tom_tat([]) == {"so_cham": 0, "dung": 0, "so_loi": 0, "abstain_oan": 0, "ty_le_dung": 0.0}
