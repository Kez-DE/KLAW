"""Node rewrite_query — dân sinh → ngôn ngữ pháp lý (pain point #3, Plan 2).

LUÔN giữ query gốc ở vị trí 0: rewrite tệ không được làm mất kết quả đúng.
Ablate được bằng cách bỏ node này khỏi graph.

Sinh THÊM biến thể thay vì THAY THẾ query gốc bằng một bản "chuẩn hoá" duy
nhất: nếu mô hình bịa một thuật ngữ không có trong corpus, RRF ở tầng truy
hồi vẫn còn query gốc để hợp nhất, không mất trắng kết quả đúng.

Traces dùng khoá `rewrite_query_*` — cùng lý do route dùng `route_*`.

Lỗi hạ tầng (mạng, LlmClient raise) KHÔNG được để nổ ra ngoài node này — khác
với `route` (xem docstring route.py): đây là bước MỞ RỘNG query chứ không
phải bước quyết định có trả lời hay không, nên fallback về đúng query gốc
luôn là hành vi AN TOÀN. Nhưng an toàn không có nghĩa là vô hình — OpenRouter
đang trả 429 thật — nên lỗi bị BỎ QUA VÀ ĐẾM (`logger.warning` +
`traces["rewrite_query_degraded"] = True`, cùng khuôn `xref.py`/
`effectivity.py` dùng cho dữ liệu bị loại), để Task 9 phân biệt được "rewrite
không giúp" (chạy được, không cải thiện Recall@5) với "rewrite không chạy"
(degraded=True, mẫu đó không nên tính vào phép đo).
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROMPT_PATH = Path("prompts/rewrite_query.v1.md")

QUERIES_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["queries"],
    "properties": {"queries": {"type": "array", "items": {"type": "string"}, "maxItems": 3}},
}

# v2 (spec 2026-09-06 §5.5): "luật sư nghĩ trước khi mở sách". `llm.chat` gửi
# schema với `strict: True`, và chế độ strict đòi MỌI property nằm trong
# `required` — nên đây là schema RIÊNG, chọn theo template, không phải v1 cộng
# vài khoá optional (strict sẽ từ chối, v2 fail im lặng rồi rơi về fallback).
QUERIES_V2_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["quan_he", "vai", "linh_vuc", "ba_lop", "du_kien_van_ban", "queries"],
    "properties": {
        "quan_he": {"type": "string"},
        "vai": {"type": "string"},
        "linh_vuc": {"type": "string"},
        "ba_lop": {"type": "array", "items": {"type": "string"}},
        "du_kien_van_ban": {"type": "array", "items": {"type": "string"}},
        "queries": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    },
}
_KHOA_NHAN_DIEN = ("quan_he", "vai", "ba_lop", "du_kien_van_ban")


def rewrite_query(state: dict, llm, model: str, prompt_path: Path | None = None) -> dict:
    prior_traces = state.get("traces") or {}
    goc = state["query"]
    mau = (prompt_path or PROMPT_PATH).read_text(encoding="utf-8")
    prompt = mau.format(cau_hoi=goc)
    # Template nhắc tới `quan_he` là template v2 — chọn schema theo NỘI DUNG
    # template, không theo tên file, để một bản v3 cùng hình dạng vẫn chạy.
    la_v2 = "quan_he" in mau
    usage = None
    degraded = False
    linh_vuc: str | None = None
    nhan_dien: dict = {}
    try:
        raw, usage = llm.chat(
            model, [{"role": "user", "content": prompt}], json_schema=QUERIES_V2_SCHEMA if la_v2 else QUERIES_SCHEMA
        )
        data = json.loads(raw)
        them = [q for q in data.get("queries", []) if q and q.strip() != goc.strip()]
        if la_v2:
            lv = data.get("linh_vuc")
            linh_vuc = lv.strip() if isinstance(lv, str) and lv.strip() else None
            nhan_dien = {k: data.get(k) for k in _KHOA_NHAN_DIEN}
    except Exception as e:
        logger.warning(
            "rewrite_query: lỗi khi gọi LLM (%s: %s) — bỏ qua, fallback về query gốc, không bịa biến thể",
            type(e).__name__,
            e,
        )
        them, degraded = [], True
    queries = [goc, *them[:2]]
    return {
        **state,
        "queries": queries,
        "linh_vuc_du_doan": linh_vuc,
        "traces": {
            **prior_traces,
            "rewrite_query_model": model,
            "rewrite_query_variants": len(queries) - 1,
            "rewrite_query_degraded": degraded,
            "rewrite_query_token_in": usage.token_in if usage else 0,
            "rewrite_query_token_out": usage.token_out if usage else 0,
            "rewrite_query_cost_usd": usage.cost_usd if usage else 0.0,
            **({"rewrite_query_nhan_dien": nhan_dien} if nhan_dien else {}),
        },
    }
