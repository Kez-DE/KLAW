"""Node rewrite_query — dân sinh → ngôn ngữ pháp lý (pain point #3, Plan 2).

LUÔN giữ query gốc ở vị trí 0: rewrite tệ không được làm mất kết quả đúng.
Ablate được bằng cách bỏ node này khỏi graph.

Sinh THÊM biến thể thay vì THAY THẾ query gốc bằng một bản "chuẩn hoá" duy
nhất: nếu mô hình bịa một thuật ngữ không có trong corpus, RRF ở tầng truy
hồi vẫn còn query gốc để hợp nhất, không mất trắng kết quả đúng.

Traces dùng khoá `rewrite_query_*` — cùng lý do route dùng `route_*`.
"""

import json
from pathlib import Path

PROMPT_PATH = Path("prompts/rewrite_query.v1.md")

QUERIES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["queries"],
    "properties": {"queries": {"type": "array", "items": {"type": "string"}, "maxItems": 3}},
}


def rewrite_query(state: dict, llm, model: str) -> dict:
    prior_traces = state.get("traces") or {}
    goc = state["query"]
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(cau_hoi=goc)
    usage = None
    try:
        raw, usage = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=QUERIES_SCHEMA)
        them = [q for q in json.loads(raw).get("queries", []) if q and q.strip() != goc.strip()]
    except Exception:
        them = []
    queries = [goc, *them[:2]]
    return {
        **state,
        "queries": queries,
        "traces": {
            **prior_traces,
            "rewrite_query_model": model,
            "rewrite_query_variants": len(queries) - 1,
            "rewrite_query_token_in": usage.token_in if usage else 0,
            "rewrite_query_token_out": usage.token_out if usage else 0,
            "rewrite_query_cost_usd": usage.cost_usd if usage else 0.0,
        },
    }
