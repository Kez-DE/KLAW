"""`muc_chac` — mức chắc TÍNH BẰNG MÃ (cai_thien.md §6 GĐ3, quyết định owner
2026-09-16: không có `result_type` mới, không hỏi điểm tự tin của mô hình).

Hai đầu vào, cả hai tra bảng được: dữ kiện quyết định người hỏi chưa nói, và vai
trò của các căn cứ đã qua kiểm chứng. Không có mức thứ ba ở đây — "chưa đủ" là
`abstain`, và pha này không đổi KHI NÀO abstain.
"""

import json
from pathlib import Path

import pytest

from src.agents.nodes.assemble import (
    MUC_CHAC_LOI,
    ResultType,
    assemble,
    tinh_muc_chac,
)
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.hoi_lai import HOI_LAI_SCHEMA
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import Tier2Verdict
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V
from src.services.llm import Usage

V6 = Path("prompts/assemble.v6.md")
DB = {11: {"id": 11, "document_id": "139264", "duong_dan": "45/2019/QH14 > Điều 26",
           "so_ky_hieu": "45/2019/QH14", "ten": "Bộ Luật lao động", "loai_van_ban": "Bộ luật",
           "link_vbpl": None, "link_chinhphu": None, "link_tvpl": None, "noi_dung": "…85%…"}}
EFF = Effectivity(V.con_hieu_luc, "trung_binh", "x")


def _r(vai_tro=None, text="Ít nhất 85%."):
    return Tier1Result(Claim(text, 11, "85%", None, vai_tro, True), True, R.ok, EFF)


def _thieu(ma="ly_do_cham_dut", lam_doi=True):
    return {"muc_tieu": "m", "cau_hoi_phap_ly": "c",
            "du_kien_quyet_dinh_con_thieu": [
                {"ma": ma, "cau": "Công ty nêu lý do gì khi chấm dứt?", "lam_doi_ket_luan": lam_doi}]}


@pytest.mark.parametrize("prose, khung, ho_so, mong_doi", [
    # Không khung, không vai trò (đường MẶC ĐỊNH hôm nay) → chắc: hành vi cũ.
    ([_r()], None, {}, "chac"),
    ([_r("ket_luan"), _r("dieu_kien", "b")], None, {}, "chac"),
    # Biết vai trò mà KHÔNG có kết luận trực tiếp → không được ghép điều kiện
    # thành một kết luận (§6 GĐ3, đoạn cuối).
    ([_r("dieu_kien"), _r("ngoai_le", "b")], None, {}, "co_dieu_kien"),
    # Còn dữ kiện làm đổi kết luận → hạ giọng dù đã có claim kết luận.
    ([_r("ket_luan")], _thieu(), {}, "co_dieu_kien"),
    # Dữ kiện KHÔNG làm đổi kết luận thì không hạ giọng.
    ([_r("ket_luan")], _thieu(lam_doi=False), {}, "chac"),
    # Người hỏi ĐÃ nói dữ kiện đó → dữ kiện người nói thắng suy đoán của model.
    ([_r("ket_luan")], _thieu(),
     {"ly_do_cham_dut": {"gia_tri": "thu hẹp sản xuất", "nguon": "nguoi_noi"}}, "chac"),
])
def test_bang_tinh_muc_chac(prose, khung, ho_so, mong_doi):
    assert tinh_muc_chac(prose, khung, ho_so) == mong_doi


class FakeLlm:
    """Giữ lại lời nhắc hành văn để soi — mức chắc chỉ có giá trị nếu nó THẬT SỰ
    tới được prompt, không phải chỉ nằm trong traces."""

    def __init__(self):
        self.prompt = ""
        self.schema_da_goi: list = []

    def chat(self, model, messages, json_schema=None):
        self.schema_da_goi.append(json_schema)
        if json_schema is HOI_LAI_SCHEMA:
            return json.dumps({"chieu": [{"ma": "chu_the", "cau": "Bạn ở phía nào?"}]}), Usage(1, 1, 0.0)
        self.prompt = messages[-1]["content"]
        return json.dumps({"answer": "Ít nhất 85% mức lương."}), Usage(1, 1, 0.0)


def _state(**kw):
    return {"intent": "tra_cuu", "query": "lương thử việc bao nhiêu", "expanded": [DB[11]],
            "tier1": [_r("ket_luan")], "tier2": [Tier2Verdict(0, True, "ok")],
            "abstain_threshold": 0.5, **kw}


def test_prompt_v6_mang_CO_DIEU_KIEN_khi_thieu_du_kien_quyet_dinh():
    llm = FakeLlm()
    st = assemble(_state(khung_yeu_cau=_thieu()), DB, llm, "m", prompt_path=V6)
    assert st["result_type"] is ResultType.answer
    assert MUC_CHAC_LOI["co_dieu_kien"] in llm.prompt
    assert "CÓ ĐIỀU KIỆN" in llm.prompt
    assert "Công ty nêu lý do gì khi chấm dứt?" in llm.prompt, "du_kien_thieu phải vào prompt"
    assert st["traces"]["assemble_muc_chac"] == "co_dieu_kien"


def test_prompt_v6_mang_CHAC_khi_du_du_kien():
    llm = FakeLlm()
    st = assemble(_state(), DB, llm, "m", prompt_path=V6)
    assert MUC_CHAC_LOI["chac"] in llm.prompt
    assert "(không)" in llm.prompt, "không thiếu dữ kiện nào thì nói rõ là không"
    assert st["traces"]["assemble_muc_chac"] == "chac"


def test_prompt_v6_mang_cau_goc_va_cau_day_du():
    llm = FakeLlm()
    assemble(_state(cau_hoi_goc="còn nghỉ không báo trước thì sao",
                    cau_hoi_day_du="thời hạn báo trước khi nghỉ việc là bao lâu"),
             DB, llm, "m", prompt_path=V6)
    assert "còn nghỉ không báo trước thì sao" in llm.prompt
    assert "thời hạn báo trước khi nghỉ việc là bao lâu" in llm.prompt


def test_du_kien_thieu_vao_prompt_van_qua_bo_loc_moc_phap_ly():
    """Một "dữ kiện còn thiếu" tự phát biểu mốc pháp lý không được vào ngữ cảnh
    của người viết — nhưng nó VẪN hạ giọng, vì dữ kiện đó thật sự còn thiếu."""
    llm = FakeLlm()
    khung = {"muc_tieu": "m", "cau_hoi_phap_ly": "c", "du_kien_quyet_dinh_con_thieu": [
        {"ma": "bao_truoc", "cau": "Bạn đã báo trước 45 ngày chưa?", "lam_doi_ket_luan": True}]}
    st = assemble(_state(khung_yeu_cau=khung), DB, llm, "m", prompt_path=V6)
    assert "45 ngày" not in llm.prompt
    assert "(không)" in llm.prompt
    assert st["traces"]["assemble_muc_chac"] == "co_dieu_kien"
    assert st["coverage_note"] is None, "câu hỏi cuối cũng phải bị bộ lọc chặn"
