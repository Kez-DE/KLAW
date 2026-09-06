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
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["tra_cuu", "soan_thao", "ngoai_pham_vi", "gioi_thieu", "hoi_ve_kho"],
        }
    },
}


class Intent(StrEnum):
    tra_cuu = "tra_cuu"
    soan_thao = "soan_thao"
    ngoai_pham_vi = "ngoai_pham_vi"
    # Câu hỏi VỀ CHÍNH TRỢ LÝ ("bạn làm được những gì", "klaw là gì"). Trước
    # bản này nó rơi vào `ngoai_pham_vi` — prompt định tuyến ghi rõ nhánh đó
    # gồm cả "không phải câu hỏi pháp luật" — nên người hỏi nhận về "Câu hỏi
    # này nằm ngoài phạm vi của hệ thống" trong khi câu trả lời đúng nằm ngay
    # bên dưới lời từ chối. Hệ thống BIẾT và vẫn chọn im lặng.
    gioi_thieu = "gioi_thieu"
    # Câu hỏi VỀ CHÍNH KHO DỮ LIỆU ("hiện có bao nhiêu bộ luật", "kho của bạn
    # phủ những gì", "có Nghị định 145/2020 không"). Trước bản này nó rơi vào
    # `tra_cuu` — prompt tự dặn "không chắc thì chọn tra_cuu" — nên câu hỏi về
    # KHO bị đem đi truy hồi NỘI DUNG luật: 30 điều khoản tầng sâu, 0 luận
    # điểm, `answer` rỗng. Câu trả lời là một phép `count(*)` chứ không phải
    # một lượt suy luận, nên nó có đường riêng: xem `src/services/kho.py`.
    hoi_ve_kho = "hoi_ve_kho"


def route(state: dict, llm, model: str, prompt_path: Path | None = None) -> dict:
    prior_traces = state.get("traces") or {}
    prompt = (prompt_path or PROMPT_PATH).read_text(encoding="utf-8").format(cau_hoi=state["query"])
    # llm.chat(...) NẰM NGOÀI try: lỗi hạ tầng thật (content rỗng, usage thiếu
    # — xem ValueError ở llm.py chat()/_usage_from()) phải NỔ RA NGOÀI, đúng
    # ruling gốc của module này (docstring đầu file). Bọc nó CÙNG phần parse
    # bên dưới sẽ khiến "OpenRouter chết" và "model trả intent không nhận ra"
    # rơi vào MỘT nhánh fallback tra_cuu như nhau — hai chế độ hỏng khác nhau
    # mà số liệu độ chính xác route sau này không tách lại được (silent-failure
    # review, sau task-10).
    raw, usage = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=INTENT_SCHEMA)
    try:
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
