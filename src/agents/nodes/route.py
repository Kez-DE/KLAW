"""Node route — phân loại ý định. Mặc định an toàn là tra_cuu.

Traces dùng khoá `route_*`, không phải token_in/token_out/cost_usd trần mà
generate_claims đã chiếm — cùng lý do verify_tier2 dùng `tier2_*` (xem
verify_tier2.py): route chạy TRƯỚC generate_claims trong pipeline, khoá trần
dùng chung sẽ bị node chạy sau ghi đè mất.

Lỗi hạ tầng KHÔNG bị nuốt ở đây — khác `rewrite_query` (xem docstring
rewrite_query.py), và đây là CHỦ ĐÍCH chứ không phải quên đối xứng: route là
bước quyết định có tra cứu hay không, một 429 âm thầm rơi thành
`ngoai_pham_vi` sẽ từ chối oan một câu hỏi hợp lệ mà không ai biết vì sao —
nên lỗi hạ tầng (không nằm trong except bên dưới) phải NỔ RA NGOÀI, không
được rơi êm vào nhánh mặc định.
"""

import json
from enum import StrEnum
from pathlib import Path

PROMPT_PATH = Path("prompts/route.v1.md")

INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["intent"],
    "properties": {"intent": {"type": "string", "enum": ["tra_cuu", "soan_thao", "ngoai_pham_vi"]}},
}


class Intent(StrEnum):
    tra_cuu = "tra_cuu"
    soan_thao = "soan_thao"
    ngoai_pham_vi = "ngoai_pham_vi"


def route(state: dict, llm, model: str) -> dict:
    prior_traces = state.get("traces") or {}
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(cau_hoi=state["query"])
    usage = None
    try:
        raw, usage = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=INTENT_SCHEMA)
        intent = Intent(json.loads(raw)["intent"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError, RuntimeError):
        # Route sai sang ngoai_pham_vi làm hệ thống từ chối oan.
        # Mặc định tra_cuu, để verifier và abstain quyết định.
        intent = Intent.tra_cuu
    return {
        **state,
        "intent": intent,
        "traces": {
            **prior_traces,
            "route_model": model,
            "route_token_in": usage.token_in if usage else 0,
            "route_token_out": usage.token_out if usage else 0,
            "route_cost_usd": usage.cost_usd if usage else 0.0,
        },
    }
