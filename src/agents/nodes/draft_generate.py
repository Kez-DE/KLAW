"""Node sinh văn bản — LLM viết điều khoản kèm key và can_cu_provision_id.

Lỗi hạ tầng (mạng, key sai, rate limit) từ `llm.chat()` KHÔNG bị bọc/nuốt —
cùng khuôn generate_claims.py: lệnh gọi LLM đứng NGOÀI try/except, chỉ phần
PARSE JSON được bọc. Một JSON lệch schema là dữ liệu OUTPUT của model
(`schema_error=True`, để đo tỉ lệ), khác hẳn một lỗi hạ tầng — gộp hai loại
vào một `except Exception` rộng sẽ biến "OpenRouter trả 500" thành trông y
hệt "model trả JSON hỏng", và giấu mất lỗi hạ tầng thật sự cần biết ngay.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from src.agents.nodes.generate_claims import build_context
from src.services.prompts import messages
from src.services.thong_tin_noi_bo import loc_cay

PROMPT_PATH = Path("prompts/draft_generate.v1.md")

CLAUSES_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["clauses"],
    "properties": {"clauses": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["key", "ten", "noi_dung", "can_cu_provision_id"],
        "properties": {"key": {"type": "string"}, "ten": {"type": "string"},
                       "noi_dung": {"type": "string"},
                       "can_cu_provision_id": {"type": "integer"}}}}},
}


@dataclass(frozen=True)
class DraftClause:
    key: str
    ten: str
    noi_dung: str
    can_cu_provision_id: int


def draft_generate(state: dict, llm, model: str) -> dict:
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        loai_van_ban=state["loai_van_ban"],
        facts=json.dumps(state["facts"], ensure_ascii=False),
        muc=json.dumps([m["key"] for m in state["muc"]], ensure_ascii=False),
        context=build_context(state.get("expanded") or []),
    )
    raw, usage = llm.chat(model, messages(prompt), json_schema=CLAUSES_SCHEMA)
    # Quyết định 2026-09-30 mục 11: điều khoản không nêu tên model hay hãng mà dữ kiện của
    # người hỏi không có — một bên tên "Công ty TNHH Google Việt Nam" họ khai thì ở lại.
    nguon = json.dumps(state["facts"], ensure_ascii=False)
    try:
        clauses = [DraftClause(**loc_cay(c, nguon)) for c in json.loads(raw).get("clauses", [])]
        schema_error = False
    except (json.JSONDecodeError, TypeError, ValueError):
        clauses, schema_error = [], True
    return {**state, "clauses": clauses, "schema_error": schema_error, "usage_generate": usage,
            "self_audit": True}


if __name__ == "__main__":
    # ponytail: check chạy được duy nhất cho nhánh parse/lỗi schema — chạy
    # bằng `python -m src.agents.nodes.draft_generate` từ gốc repo (để
    # PROMPT_PATH tương đối và import `src.*` phân giải đúng).
    from src.services.llm import Usage

    class _FakeLlm:
        def __init__(self, raw: str) -> None:
            self._raw = raw

        def chat(self, model, messages, json_schema=None):
            return self._raw, Usage(10, 10, 0.0)

    state = {"loai_van_ban": "HĐLĐ", "facts": {}, "muc": [{"key": "luong"}], "expanded": []}

    ok = draft_generate(state, _FakeLlm(
        '{"clauses": [{"key": "luong", "ten": "Lương", "noi_dung": "x", "can_cu_provision_id": 1}]}'
    ), "model")
    assert ok["schema_error"] is False
    assert ok["clauses"] == [DraftClause("luong", "Lương", "x", 1)]
    assert ok["self_audit"] is True

    bad = draft_generate(state, _FakeLlm("không phải JSON"), "model")
    assert bad["schema_error"] is True and bad["clauses"] == []

    print("draft_generate self-check OK")
