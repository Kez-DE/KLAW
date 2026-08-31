"""Ghi và tổng hợp traces — dữ liệu cho chương đánh giá.

Tách từ `src/api/routes.py` (task-1, klaw-04-drafting-fe-deploy) để các
endpoint khác (`/soan-thao`, `/soat` — Task 5) dùng lại được thay vì
copy-paste. Di chuyển nguyên khối, KHÔNG đổi hành vi, cột, hay thời điểm gọi.
"""

from sqlalchemy import text

from src.services.db import get_engine

# ══ Quy ước cộng dồn traces (task-10, yêu cầu #3) ═══════════════════════════
# 5 điểm gọi LLM trong pipeline — route, rewrite_query, generate_claims (khoá
# TRẦN token_in/token_out/cost_usd — generate_claims.py đã chiếm chúng trước
# route/rewrite_query có khoá riêng), verify_tier2 (tier2_*), và assemble
# (hành văn câu trả lời cuối, assemble_*) — MỖI NODE GHI ĐÈ đúng khoá của
# riêng mình vào state["traces"], KHÔNG cộng dồn. Ba danh sách dưới đây cộng
# RÕ RÀNG 5 khoá thành TỔNG chi phí của một request — cố ý không dùng quy tắc
# ngầm kiểu "mọi khoá kết thúc bằng _token_in", vì một khoá tương lai trùng
# hậu tố mà không phải chi phí THẬT của request này sẽ bị cộng nhầm. Thêm một
# node gọi LLM thứ 6 → sửa cả BA danh sách này (không sửa chỗ khác).
_TOKEN_IN_KEYS = (
    "route_token_in", "rewrite_query_token_in", "token_in", "tier2_token_in", "assemble_token_in",
)
_TOKEN_OUT_KEYS = (
    "route_token_out", "rewrite_query_token_out", "token_out", "tier2_token_out", "assemble_token_out",
)
_COST_KEYS = (
    "route_cost_usd", "rewrite_query_cost_usd", "cost_usd", "tier2_cost_usd", "assemble_cost_usd",
)


def _tong_hop_traces(traces: dict) -> dict:
    """Tổng chi phí một request + hai cặp cột Task 10 nối xuống DB (tên model
    tầng 2, kích thước expand). Xem quy ước cộng dồn ở trên.

    `generate_model`/`judge_model` lấy từ `tier2_generate_model`/
    `tier2_judge_model` (Task 6 đặt vào `state["traces"]` mỗi lần tầng 2 THẬT
    SỰ chạy) — KHÔNG gọi lại `generate_model()`/`judge_model()` từ Settings,
    vì đó là cấu hình TĨNH của deployment chứ không phải bằng chứng "request
    NÀY đã dùng model nào": mục đích của hai cột này là CHỨNG MINH bằng số
    liệu của chính request, không lặp lại một khai báo cấu hình. Cả hai NULL
    khi tầng 2 không chạy (ngoai_pham_vi, insufficient_evidence, hoặc tắt qua
    `VERIFY_TIER2_ENABLED=false`) — NULL nghĩa là "không chạy", không phải
    "quên ghi". `expand_before`/`expand_after` tương tự: NULL khi node
    `expand` không chạy (route ra ngoai_pham_vi rẽ thẳng sang assemble).
    """
    return {
        "token_in": sum(traces.get(k) or 0 for k in _TOKEN_IN_KEYS),
        "token_out": sum(traces.get(k) or 0 for k in _TOKEN_OUT_KEYS),
        "cost_usd": sum(traces.get(k) or 0.0 for k in _COST_KEYS),
        "generate_model": traces.get("tier2_generate_model"),
        "judge_model": traces.get("tier2_judge_model"),
        "expand_before": traces.get("expand_before"),
        "expand_after": traces.get("expand_after"),
    }


_SQL_INSERT_TRACE = text(
    "INSERT INTO traces (id, endpoint, query, config_name, result_type, retrieved_ids,"
    " claims_raw, claims_after_tier1, claims_after_tier2, latency_ms, token_in, token_out,"
    " cost_usd, generate_model, judge_model, expand_before, expand_after)"
    " VALUES (:id, :endpoint, :query, :config_name, :result_type, :retrieved_ids,"
    " :claims_raw, :claims_after_tier1, :claims_after_tier2, :latency_ms, :token_in, :token_out,"
    " :cost_usd, :generate_model, :judge_model, :expand_before, :expand_after)"
)


def _ghi_traces(trace_id: str, endpoint: str, query: str, config_name: str, st: dict, latency_ms: int) -> None:
    """Ghi MỘT hàng `traces` thật cho request này. Có thể raise — resilience
    (best-effort, không chặn response khi ghi lỗi) là quyết định của CALLER
    (`tra_cuu`), không phải của hàm ghi DB này (single responsibility: hàm
    này chỉ lo INSERT đúng, không tự quyết lỗi của nó nghiêm trọng tới đâu).
    """
    traces = st.get("traces") or {}
    rt = st.get("result_type")
    params = {
        "id": trace_id, "endpoint": endpoint, "query": query, "config_name": config_name,
        "result_type": rt.value if hasattr(rt, "value") else rt,
        "retrieved_ids": st.get("retrieved") or [],
        "claims_raw": traces.get("claims_raw", 0),
        "claims_after_tier1": sum(1 for r in (st.get("tier1") or []) if r.ok),
        "claims_after_tier2": sum(1 for v in (st.get("tier2") or []) if v.supported),
        "latency_ms": latency_ms,
        **_tong_hop_traces(traces),
    }
    with get_engine().begin() as c:
        c.execute(_SQL_INSERT_TRACE, params)
