import logging
import time
import uuid

import httpx
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from starlette.concurrency import run_in_threadpool

from src.agents.graph_tra_cuu import build_graph_tra_cuu
from src.config import get_settings
from src.models.schemas import TraCuuRequest, TraCuuResponse
from src.services.db import get_engine

logger = logging.getLogger(__name__)

router = APIRouter()

_graph = None


def _g():
    global _graph
    if _graph is None:
        _graph = build_graph_tra_cuu()
    return _graph


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


@router.post("/tra-cuu", response_model=TraCuuResponse)
async def tra_cuu(req: TraCuuRequest) -> TraCuuResponse:
    """spec 8.0a. `result_type` là enum bốn giá trị (không phải cờ `abstained`
    boolean): `partial_coverage` không thể ép vào "đã trả lời"/"đã từ chối" mà
    không mất thông tin, và ABSTAIN là hành vi ĐÚNG của hệ thống — không phải
    lỗi cần che giấu bằng một cờ nhị phân.
    """
    s = get_settings()
    trace_id = str(uuid.uuid4())
    bat_dau = time.monotonic()
    try:
        st = await _g().ainvoke({"query": req.query, "as_of_date": req.as_of_date, "trace_id": trace_id})
    except (httpx.HTTPStatusError, httpx.TransportError, OperationalError) as e:
        # Lỗi hạ tầng NHẤT THỜI, nhận diện được theo LOẠI ngoại lệ — OpenRouter
        # 429/5xx cạn retry (httpx) hoặc Postgres không kết nối được
        # (OperationalError): 503, đúng nghĩa "client NÊN thử lại". Chi tiết
        # đầy đủ vào log server (không lộ ra response — LlmClient không bao
        # giờ đưa OPENROUTER_API_KEY vào message ngoại lệ, nhưng response vẫn
        # chỉ mang TÊN loại lỗi, không mang str(e), để không mở rộng bề mặt rò
        # rỉ nếu một ngoại lệ tương lai vô tình mang theo dữ liệu nhạy cảm).
        logger.exception("tra_cuu: lỗi hạ tầng nhất thời khi chạy graph (trace_id=%s)", trace_id)
        raise HTTPException(status_code=503, detail=f"tra cứu thất bại: {type(e).__name__}") from e
    except Exception as e:
        # Không thuộc hai loại rõ ràng-nhất-thời ở trên — bug thật (KeyError,
        # AttributeError...) hoặc ValueError của chính LlmClient khi OpenRouter
        # trả nội dung dị dạng (content rỗng/usage thiếu, xem llm.py) — 500,
        # KHÔNG ngụ ý client nên tự ý thử lại. Giới hạn đã biết: ValueError đó
        # về BẢN CHẤT cũng là dấu hiệu OpenRouter không ổn định, nhưng llm.py
        # dùng ValueError trần (không phải exception riêng) nên không tách
        # được khỏi ValueError từ một bug thật bằng KIỂU — nâng cấp lên một
        # exception riêng nếu cần tách rạch hơn.
        logger.exception("tra_cuu: lỗi không xác định khi chạy graph (trace_id=%s)", trace_id)
        raise HTTPException(status_code=500, detail=f"tra cứu thất bại: {type(e).__name__}") from e
    latency_ms = int((time.monotonic() - bat_dau) * 1000)

    config_name = req.config_name or s.eval_config_name
    try:
        await run_in_threadpool(_ghi_traces, trace_id, "/api/v1/tra-cuu", req.query, config_name, st, latency_ms)
    except Exception:
        # Telemetry hỏng không phải lý do từ chối người dùng một câu trả lời
        # đã tính ĐÚNG — khác lỗi hạ tầng của chính graph ở trên, cái đó PHẢI
        # nổ ra vì nó quyết định result_type; ghi traces không quyết định gì.
        logger.exception("tra_cuu: ghi traces thất bại (trace_id=%s) — KHÔNG chặn response", trace_id)

    rt = st["result_type"]
    return TraCuuResponse(
        result_type=rt.value if hasattr(rt, "value") else rt,
        answer=st.get("answer"), citations=st.get("citations") or [],
        warnings=st.get("warnings") or [], coverage_note=st.get("coverage_note"),
        trace_id=trace_id, config_name=config_name,
    )


@router.get("/status")
async def agent_status():
    """Kiểm tra trạng thái agent."""
    return {"status": "ready", "agent": "LangGraph Agent v1.0"}
