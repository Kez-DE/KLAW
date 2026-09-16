"""`result_type="tai_lieu"` — loại kết quả thứ TÁM, cho một lượt nói về tài liệu
của người hỏi chứ không về nội dung pháp luật.

Ba điều bị khoá:

1. `assemble` KHÔNG gọi mô hình trên nhánh này: lượt hành văn đã xảy ra ở node
   `hieu_tai_lieu`, gọi lại ở đây là trả tiền hai lần cho một câu trả lời.
2. `ho_so_da_dung` rỗng: câu trả lời dựng từ TÀI LIỆU, không từ hồ sơ tình
   huống — hiện "Dựa trên: …" ở đây là provenance sai (cùng lý lẽ của ba loại
   meta).
3. Chữ trong tài liệu KHÔNG chảy vào hồ sơ phiên (`bo_nho.ho_so_sau_luot`).
"""

import pytest

from src.agents.nodes.assemble import _KHONG_DUNG_HO_SO, ResultType, assemble
from src.models.schemas import TraCuuResponse
from src.services.bo_nho import KHONG_GOP_HO_SO, ho_so_sau_luot

KET = {
    "muc_dich": "hoi",
    "mo_ta": "Phiếu đánh giá thực tập",
    "tra_loi_ngan": "Phiếu chấm theo bốn tiêu chí, tổng 10 điểm.",
    "quan_sat": [
        {
            "noi_dung": "Tổng điểm tối đa là 10.",
            "trich": "Tổng điểm tối đa là 10",
            "neo": {"tai_lieu_id": "aaaa", "chi_so_don_vi": 1, "trang": 1, "vung": "than",
                    "bang": None, "nguon_chu": "lop_chu", "do_tin": None},
        }
    ],
    "suy_luan": ["Thang điểm nhất quán."],
    "phep_tinh": [],
    "can_du_kien": ["họ tên sinh viên"],
    "du_kien": [],
    "tai_lieu_da_dung": [{"id": "aaaa", "ten_tep": "phieu.docx", "nhan": "A"}],
}

HO_SO = {"vai_tro": {"gia_tri": "người lao động", "nguon": "nguoi_noi"}}


class _No:
    def chat(self, *a, **k):  # pragma: no cover - chỉ để nổ nếu bị gọi
        raise AssertionError("nhánh tài liệu không được gọi mô hình")


def _chay(**ghi_de):
    st = {"query": "phiếu này chấm thế nào", "intent": "tai_lieu", "tai_lieu_ket": KET, "ho_so": HO_SO}
    return assemble({**st, **ghi_de}, {}, _No(), "m")


def test_ket_qua_la_tai_lieu_va_answer_lay_tu_tra_loi_ngan():
    ra = _chay()
    assert ra["result_type"] is ResultType.tai_lieu
    assert ra["answer"] == KET["tra_loi_ngan"]
    assert ra["tai_lieu"] == KET


def test_nhanh_tai_lieu_khong_ton_mot_token_nao():
    t = _chay()["traces"]
    assert t["assemble_token_in"] == 0 and t["assemble_token_out"] == 0 and t["assemble_cost_usd"] == 0.0


def test_ho_so_da_dung_rong_du_phien_co_ho_so():
    assert _chay()["ho_so_da_dung"] == []
    assert ResultType.tai_lieu in _KHONG_DUNG_HO_SO


def test_chay_duoc_ca_khi_intent_khong_phai_tai_lieu():
    """Lượt ĐÍNH KÈM rẽ tất định từ `_vao_graph`, không qua `route`, nên `intent`
    trống — `tai_lieu_ket` một mình phải đủ để chọn nhánh."""
    ra = assemble({"query": "x", "tai_lieu_ket": KET}, {}, _No(), "m")
    assert ra["result_type"] is ResultType.tai_lieu


def test_khong_co_tai_lieu_ket_thi_khong_cuop_nhanh_khac():
    ra = assemble({"query": "x", "intent": "gioi_thieu", "tra_loi_gioi_thieu": "chào"}, {}, _No(), "m")
    assert ra["result_type"] is ResultType.gioi_thieu


def test_payload_tuan_tu_hoa_duoc_qua_TraCuuResponse():
    ra = _chay()
    resp = TraCuuResponse(
        result_type=ra["result_type"].value,
        answer=ra["answer"], citations=[], warnings=[], coverage_note=None,
        tai_lieu=ra["tai_lieu"], tai_lieu_neo=ra.get("tai_lieu_neo") or [],
        trace_id="t", config_name="c",
    )
    assert resp.result_type == "tai_lieu"
    assert resp.tai_lieu.quan_sat[0].neo.chi_so_don_vi == 1
    assert resp.tai_lieu.tai_lieu_da_dung[0].nhan == "A"


# ───────────────────────────────────────────────── bộ nhớ không nuốt tài liệu


def test_ho_so_phien_KHONG_gop_gi_tu_luot_tai_lieu():
    cu = {"vai_tro": {"gia_tri": "người lao động", "nguon": "nguoi_noi"}}
    assert ho_so_sau_luot("tai_lieu", cu, {"vai_tro": "giám đốc"}) == cu


@pytest.mark.parametrize("rt", ["gioi_thieu", "hoi_ve_kho", "out_of_scope", "tai_lieu"])
def test_cac_loai_khong_gop_ho_so_van_du(rt):
    assert rt in KHONG_GOP_HO_SO
