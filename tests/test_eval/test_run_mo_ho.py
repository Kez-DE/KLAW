"""Đo `run_mo_ho.dung`/`tom_tat` — hàm THUẦN, không cần graph/mạng (spec 2026-09-09
§7.7: câu mơ hồ có chủ đích phải được TRẢ LỜI kèm giả định, không abstain oan).

Cùng cam kết `eval/run_trap.py::chay` và `eval/run_hoi_thoai.py::tom_tat_diem`: một
câu lỗi hạ tầng không có khoá `dung`/`result_type` và không được tính vào CẢ tử số
lẫn mẫu số của tỉ lệ đúng — loại riêng ra `so_loi`, không phải một câu trả lời sai.
"""

from eval.run_mo_ho import dung, tom_tat


def test_dung_can_answer_va_gia_dinh_dung():
    it = {"ky_vong": {"chu_the": "người lao động", "khong_abstain": True}}
    ok = {
        "result_type": "answer",
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

    it = {"ky_vong": {"chu_the": "người lao động", "khong_abstain": True}}
    payload = {
        "result_type": ResultType.partial_coverage,
        "ho_so_da_dung": [{"khoa": "chu_the", "gia_tri": "người lao động", "gia_dinh": True}],
    }
    assert dung(it, payload) is True


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
