"""Node generate_claims — LLM sinh khẳng định KÈM provision_id và quote nguyên văn.

Prompt nằm ở prompts/generate_claims.v*.md (artifact có version trong git).
JSON hỏng KHÔNG làm sập: ghi schema_error=True để đo tỉ lệ, coi như thiếu căn cứ.

Node này CỐ Ý KHÔNG lọc claim theo quote — kiểm quote có phải substring của
provisions.noi_dung là việc của tầng 1 (Task 5). Tỉ lệ claim bị tầng 1 loại là
một con số chính của khóa luận: nó đo mức mô hình sinh trích dẫn sai khi bị
buộc phải trích dẫn. Tự lọc ở đây sẽ xoá mất bằng chứng định lượng đó.
"""

import json
from dataclasses import dataclass
from pathlib import Path

PROMPT_PATH = Path("prompts/generate_claims.v1.md")

CLAIMS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["insufficient_evidence", "claims"],
    "properties": {
        "insufficient_evidence": {"type": "boolean"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "provision_id", "quote"],
                "properties": {
                    "text": {"type": "string"},
                    "provision_id": {"type": "integer"},
                    "quote": {"type": "string"},
                },
            },
        },
    },
}


@dataclass(frozen=True)
class Claim:
    text: str
    provision_id: int
    quote: str


def build_context(provisions: list[dict]) -> str:
    """Định danh văn bản bằng so_ky_hieu (Global Constraint) — KHÔNG dùng ten/title
    của văn bản. so_ky_hieu được đưa tường minh cho model, không chỉ ẩn bên trong
    chuỗi duong_dan."""
    parts: list[str] = []
    for p in provisions:
        parts.append(
            f"[provision_id={p['id']}] so_ky_hieu={p['so_ky_hieu']} duong_dan={p['duong_dan']}\n"
            f"{p.get('tieu_de') or ''}\n{p.get('noi_dung') or ''}".strip()
        )
    return "\n\n---\n\n".join(parts)


def generate_claims(state: dict, llm, model: str) -> dict:
    prior_traces = state.get("traces") or {}
    expanded = state.get("expanded") or []
    if not expanded:
        return {
            **state,
            "draft_claims": [],
            "insufficient_evidence": True,
            "schema_error": False,
            "traces": {**prior_traces, "claims_raw": 0, "token_in": 0, "token_out": 0, "cost_usd": 0.0},
        }

    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(cau_hoi=state["query"], context=build_context(expanded))
    raw, usage = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=CLAIMS_SCHEMA)
    try:
        data = json.loads(raw)
        claims = [Claim(**c) for c in data.get("claims", [])]
        insufficient = bool(data.get("insufficient_evidence"))
        schema_error = False
    except (json.JSONDecodeError, TypeError, ValueError):
        claims, insufficient, schema_error = [], True, True

    return {
        **state,
        "draft_claims": claims,
        "insufficient_evidence": insufficient,
        "schema_error": schema_error,
        "traces": {
            **prior_traces,
            "claims_raw": len(claims),
            "token_in": usage.token_in,
            "token_out": usage.token_out,
            "cost_usd": usage.cost_usd,
        },
    }
