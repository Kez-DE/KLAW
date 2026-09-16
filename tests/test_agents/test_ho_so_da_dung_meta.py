"""`ho_so_da_dung` phải rỗng cho ba nhánh meta — chúng không đọc hồ sơ để dựng
câu trả lời, nên hiển thị "Dựa trên" ở đó là provenance sai (ex.md §2.6/§3.5/FR-007)."""

import json
from pathlib import Path

from src.agents.nodes import assemble as assemble_mod
from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.hoi_lai import HOI_LAI_SCHEMA
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import Tier2Verdict
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V

DB = {11: {"id": 11, "duong_dan": "45/2019/QH14 > Điều 26", "so_ky_hieu": "45/2019/QH14",
           "ten": "Bộ Luật lao động", "noi_dung": "…85%…"}}
EFF = Effectivity(V.con_hieu_luc, "trung_binh", "x")

HO_SO = {
    "chu_the": {"gia_tri": "người lao động", "nguon": "nguoi_noi"},
    "vu_viec": {"gia_tri": "sắp nghỉ việc, hỏi quyền lợi", "nguon": "nguoi_noi"},
}


class FakeLlm:
    def chat(self, model, messages, json_schema=None):
        from src.services.llm import Usage
        if json_schema is HOI_LAI_SCHEMA:
            return json.dumps({"chieu": [{"ma": "chu_the", "cau": "Bạn ở phía nào?"}]}), Usage(1, 1, 0.0)
        return json.dumps({"answer": "Ít nhất 85%."}), Usage(1, 1, 0.0)


def _pass(pid=11):
    return Tier1Result(Claim("Ít nhất 85%.", pid, "85%"), True, R.ok, EFF)


def test_gioi_thieu_khong_dung_ho_so(monkeypatch):
    # Cô lập khỏi `gioi_thieu.cau_gioi_thieu`: phép kiểm này canh gating của
    # `_base`, không phải nội dung câu đáp (module đó đang bị agent khác sửa).
    monkeypatch.setattr(assemble_mod, "cau_gioi_thieu", lambda cau_hoi: "x")
    st = assemble({"query": "bạn làm được gì", "intent": "gioi_thieu", "ho_so": HO_SO}, {}, None, "")
    assert st["result_type"] is ResultType.gioi_thieu
    assert st["ho_so_da_dung"] == []


def test_hoi_ve_kho_khong_dung_ho_so():
    st = assemble({"intent": "hoi_ve_kho", "tra_loi_kho": "x", "ho_so": HO_SO}, {}, None, "")
    assert st["result_type"] is ResultType.hoi_ve_kho
    assert st["ho_so_da_dung"] == []


def test_ngoai_pham_vi_khong_dung_ho_so():
    st = assemble({"intent": "ngoai_pham_vi", "ho_so": HO_SO}, {}, None, "")
    assert st["result_type"] is ResultType.out_of_scope
    assert st["ho_so_da_dung"] == []


def test_answer_phap_ly_van_hien_ho_so_da_dung():
    """Nhánh trả lời pháp lý vẫn nạp cả hồ sơ vào prompt (spec ex.md §7.4.5) —
    thay đổi ở `_base` chỉ khoanh vào ba nhánh meta, không đụng đường này."""
    llm = FakeLlm()
    st = assemble(
        {"intent": "tra_cuu", "expanded": [DB[11]], "tier1": [_pass()],
         "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5, "ho_so": HO_SO},
        DB, llm, "m", prompt_path=Path("prompts/assemble.v3.md"),
    )
    assert st["result_type"] is ResultType.answer
    assert [d["khoa"] for d in st["ho_so_da_dung"]] == ["chu_the", "vu_viec"]


def test_abstain_giu_hanh_vi_cu():
    """Ngõ cụt (không có tier1) không nằm trong `_KHONG_DUNG_HO_SO` — ghim để đổi
    ở trên KHÔNG lan sang nhánh này ngoài ý muốn."""
    st = assemble({"intent": "tra_cuu", "ho_so": HO_SO}, {}, FakeLlm(), "m")
    assert st["result_type"] is ResultType.abstain
    assert st["ho_so_da_dung"] != []
