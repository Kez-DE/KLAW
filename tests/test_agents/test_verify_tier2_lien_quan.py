"""Tầng 2 chấm thêm ĐỘ LIÊN QUAN — `verify_tier2.v2` (cai_thien.md §6 GĐ3).

Tách khỏi `test_verify_tier2.py` (hợp đồng v1, chạy trong lane CI trả tiền) để
file này thuần: một `FakeLlm` và hai template có sẵn trên đĩa, không mạng.

Điều được khoá ở đây là một bất đối xứng CÓ CHỦ Ý: prompt v1 KHÔNG hỏi
`relevant`/`overstated`, nên nó phải cho mặc định NỚI (mọi verdict coi như đúng
chủ đề — đúng hành vi đang được đo làm baseline); prompt v2 CÓ hỏi, nên im lặng
của judge là "không chắc", và không chắc thì không được dựng thành văn xuôi.
"""

import json
from pathlib import Path

from src.agents.nodes.generate_claims import Claim
from src.agents.nodes.verify_tier1 import Tier1Reason as R
from src.agents.nodes.verify_tier1 import Tier1Result
from src.agents.nodes.verify_tier2 import (
    VERDICTS_SCHEMA,
    VERDICTS_V2_SCHEMA,
    verify_tier2,
    verify_tier2_and_trace,
)
from src.services.llm import Usage

V2 = Path("prompts/verify_tier2.v2.md")

DB = {11: {"id": 11, "duong_dan": "45/2019/QH14 > Điều 26",
           "noi_dung": "Ít nhất phải bằng 85% mức lương của công việc đó."}}


class FakeLlm:
    def __init__(self, payload):
        self.payload = payload
        self.schema = None
        self.prompt = ""

    def chat(self, model, messages, json_schema=None):
        self.schema = json_schema
        self.prompt = messages[-1]["content"]
        return json.dumps(self.payload), Usage(1, 1, 0.0)


def _ok(i):
    return Tier1Result(Claim(f"c{i}", 11, "85%"), True, R.ok, None, khop_tai=11)


def test_template_v2_chon_schema_v2_va_doc_ca_hai_co():
    llm = FakeLlm({"verdicts": [
        {"claim_index": 0, "supported": True, "relevant": True, "overstated": False, "reason": "x"},
        {"claim_index": 1, "supported": True, "relevant": False, "overstated": True, "reason": "y"},
    ]})
    out = verify_tier2([_ok(0), _ok(1)], DB, llm, "m", prompt_path=V2)
    assert llm.schema is VERDICTS_V2_SCHEMA
    assert (out[0].supported, out[0].relevant, out[0].overstated) == (True, True, False)
    assert (out[1].supported, out[1].relevant, out[1].overstated) == (True, False, True)


def test_v2_thieu_co_thi_mac_dinh_KHONG_lien_quan():
    """Fail-closed đúng như `supported`: judge không nói gì về độ liên quan thì
    khẳng định đó không được dựng thành câu, không phải được cho qua."""
    llm = FakeLlm({"verdicts": [{"claim_index": 0, "supported": True, "reason": "x"}]})
    out = verify_tier2([_ok(0)], DB, llm, "m", prompt_path=V2)
    assert out[0].supported is True and out[0].relevant is False


def test_v2_thieu_han_verdict_thi_khong_ho_tro_va_khong_lien_quan():
    llm = FakeLlm({"verdicts": []})
    out = verify_tier2([_ok(0)], DB, llm, "m", prompt_path=V2)
    assert out[0].supported is False and out[0].relevant is False


def test_v2_json_hong_ca_batch_ve_mac_dinh_dong():
    class Hong(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            return "không phải json", Usage(1, 1, 0.0)

    out = verify_tier2([_ok(0), _ok(1)], DB, Hong({}), "m", prompt_path=V2)
    assert [(v.supported, v.relevant) for v in out] == [(False, False), (False, False)]


def test_duong_v1_giu_nguyen_mac_dinh_noi():
    """MẶC ĐỊNH của hệ thống. Nếu v1 mà `relevant=False` thì bộ lọc văn xuôi của
    `assemble` sẽ quét sạch mọi căn cứ — hồi quy toàn phần, im lặng."""
    llm = FakeLlm({"verdicts": [{"claim_index": 0, "supported": True, "reason": "x"}]})
    out = verify_tier2([_ok(0)], DB, llm, "m")
    assert llm.schema is VERDICTS_SCHEMA
    assert out[0].relevant is True and out[0].overstated is False


def test_prompt_v2_mang_muc_tieu_tu_khung_va_cau_hoi():
    llm = FakeLlm({"verdicts": [{"claim_index": 0, "supported": True, "relevant": True,
                                 "overstated": False, "reason": "x"}]})
    verify_tier2([_ok(0)], DB, llm, "m", prompt_path=V2,
                 khung_yeu_cau={"muc_tieu": "biết có được trừ lương không"},
                 cau_hoi="công ty trừ lương tôi vì đi muộn")
    assert "biết có được trừ lương không" in llm.prompt
    assert "công ty trừ lương tôi vì đi muộn" in llm.prompt


def test_khong_co_khung_thi_muc_tieu_roi_ve_cau_hoi():
    llm = FakeLlm({"verdicts": [{"claim_index": 0, "supported": True, "relevant": True,
                                 "overstated": False, "reason": "x"}]})
    verify_tier2([_ok(0)], DB, llm, "m", prompt_path=V2, cau_hoi="công ty trừ lương tôi vì đi muộn")
    assert llm.prompt.count("công ty trừ lương tôi vì đi muộn") == 2, "vừa là mục tiêu vừa là câu hỏi"


def test_traces_ghi_dung_prompt_da_chay():
    llm = FakeLlm({"verdicts": [{"claim_index": 0, "supported": True, "relevant": True,
                                 "overstated": False, "reason": "x"}]})
    _, traces = verify_tier2_and_trace([_ok(0)], DB, llm, "m", None, prompt_path=V2)
    assert traces["tier2_prompt"] == str(V2)
    _, traces_v1 = verify_tier2_and_trace([_ok(0)], DB, FakeLlm({"verdicts": []}), "m")
    assert traces_v1["tier2_prompt"] == "prompts/verify_tier2.v1.md"
