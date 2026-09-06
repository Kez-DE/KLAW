"""SOUL đi đúng 5 node và KHÔNG đi vào 3 node (spec 2026-09-06 §5.1).

Hai lớp kiểm: quét mã nguồn (rẻ, không cần LLM/DB, bắt được cả node khó dựng
state như `draft_generate`) và một lượt gọi thật của `assemble` để chắc chuỗi
`messages` tới `llm.chat` có `system` đứng đầu.
"""

import json
from pathlib import Path

import pytest

from src.agents.nodes.assemble import ANSWER_SCHEMA, ResultType, assemble
from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.hoi_lai import HOI_LAI_SCHEMA
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import Tier2Verdict
from src.services.effectivity import Effectivity
from src.services.effectivity import EffectivityVerdict as V
from src.services.llm import Usage
from src.services.prompts import soul

NODES = Path(__file__).resolve().parents[2] / "src/agents/nodes"
CO_SOUL = ("assemble", "hoi_lai", "giai_nghia", "draft_generate", "generate_claims")
KHONG_SOUL = ("route", "rewrite_query", "verify_tier2")


@pytest.mark.parametrize("ten", CO_SOUL)
def test_node_co_soul_goi_messages(ten):
    ma = (NODES / f"{ten}.py").read_text(encoding="utf-8")
    assert "from src.services.prompts import messages" in ma, f"{ten}: chưa import messages"
    assert '[{"role": "user", "content": prompt}]' not in ma, f"{ten}: còn gọi LLM không SOUL"


@pytest.mark.parametrize("ten", KHONG_SOUL)
def test_node_khong_soul_khong_import_prompts(ten):
    ma = (NODES / f"{ten}.py").read_text(encoding="utf-8")
    assert "src.services.prompts" not in ma, f"{ten}: KHÔNG được tiêm SOUL (spec §5.1)"


DB = {11: {"id": 11, "document_id": "139264", "duong_dan": "45/2019/QH14 > Điều 26",
           "so_ky_hieu": "45/2019/QH14", "ten": "Bộ Luật lao động", "loai_van_ban": "Bộ luật",
           "link_vbpl": None, "link_chinhphu": None, "link_tvpl": None, "noi_dung": "…85%…"}}
EFF = Effectivity(V.con_hieu_luc, "trung_binh", "x")


class GhiMessages:
    def __init__(self):
        self.da_goi: list[list[dict]] = []

    def chat(self, model, messages, json_schema=None):
        self.da_goi.append(messages)
        if json_schema is HOI_LAI_SCHEMA:
            return json.dumps({"chieu": [{"ma": "chu_the", "cau": "Bạn ở phía nào?"}]}), Usage(1, 1, 0.0)
        assert json_schema is ANSWER_SCHEMA
        return json.dumps({"answer": "Ít nhất 85% mức lương."}), Usage(1, 1, 0.0)


def test_assemble_hanh_van_voi_system_soul_dung_dau():
    llm = GhiMessages()
    st = assemble({"intent": "tra_cuu", "expanded": [DB[11]],
                   "tier1": [Tier1Result(Claim("Ít nhất 85%.", 11, "85%"), True, R.ok, EFF)],
                   "tier2": [Tier2Verdict(0, True, "ok")], "abstain_threshold": 0.5},
                  DB, llm, "m")
    assert st["result_type"] is ResultType.answer
    m = llm.da_goi[0]
    assert m[0]["role"] == "system" and m[0]["content"] == soul()
    assert m[1]["role"] == "user"
