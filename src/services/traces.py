"""Ghi và tổng hợp traces — dữ liệu cho chương đánh giá.

Tách từ `src/api/routes.py` (task-1, klaw-04-drafting-fe-deploy) để các
endpoint khác (`/soan-thao`, `/soat` — Task 5) dùng lại được thay vì
copy-paste. Di chuyển nguyên khối, KHÔNG đổi hành vi, cột, hay thời điểm gọi.
"""

import hashlib

from sqlalchemy import text

from src.agents.nodes.verify_tier1 import normalize
from src.services.db import get_engine

# ══ `/soat` — DẤU của tài liệu, không phải tài liệu ═════════════════════════


def dau_van_ban(van_ban: str, so_clause: int) -> str:
    """Thứ được ghi vào `traces.query` cho `/soat`, thay cho toàn văn tài liệu.

    Hai endpoint, hai loại dữ liệu khác nhau, nên hai cách xử lý khác nhau:

    * `/tra-cuu.query` là CÂU NGƯỜI DÙNG HỎI — dữ liệu của chính họ, ngắn (đo
      trên DB: max 96 ký tự, trung bình 39), và eval cần nguyên văn. GIỮ.
    * `/soat.text` là TÀI LIỆU của người dùng, và dữ liệu cá nhân trong đó
      thường thuộc về NGƯỜI THỨ BA: người lao động có tên trong hợp đồng, số
      CCCD của họ, mức lương của họ. Người đó chưa từng dùng KLAW và chưa đồng ý
      gì cả — không ô checkbox nào trên giao diện xin phép được thay cho họ.
      Đo trước khi sửa: 30 dòng, `max(length(query))` = 2.000.000 ký tự, trung
      bình 66.793. KHÔNG LƯU.

    Ba đại lượng dưới đây là đủ cho mọi thứ số liệu cần, và không một ký tự nội
    dung nào:

    * `sha256` của dạng đã chuẩn hoá — nhận ra hai lần soát CÙNG một tài liệu
      (đo trùng lặp, và là khoá dùng được nếu sau này cache `/soat`). Chuẩn hoá
      bằng CHÍNH `verify_tier1.normalize`, không viết hàm thứ hai.
    * `len` — độ dài THÔ (không phải sau chuẩn hoá): nó trả lời "người dùng dán
      vào bao lớn", tức đại lượng gắn với `latency_ms`.
    * `clauses` — số Điều `extract_clauses` tách được, đại lượng còn lại giải
      thích được độ trễ.

    Hash là một chiều: không có đường nào từ dấu này về lại tài liệu.
    """
    h = hashlib.sha256(normalize(van_ban).encode("utf-8")).hexdigest()
    return f"soat sha256={h} len={len(van_ban)} clauses={so_clause}"


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
#
# Plan 4: `draft_generate_*` LÀ điểm gọi LLM thứ 6 đó — của graph `/soan-thao`.
# Nó thiếu ở đây cho tới giờ, và hệ quả ĐO ĐƯỢC: 32/32 dòng `/api/v1/soan-thao`
# trong `traces` có `cost_usd = 0` dù mỗi request tốn một lượt LLM thật. Điều đó
# biến trần chi phí ngày — đọc CHÍNH cột này — thành một cổng không thấy một
# trong hai endpoint tiêu tiền. `draft_generate` trả usage ở
# `state["usage_generate"]` chứ không vào `state["traces"]`, nên
# `graph_soan_thao.n_generate` nối nó vào đây, chỗ duy nhất hàm dưới biết đọc.
#
# 2026-09-09: `gom_du_kien_*` là điểm gọi LLM thứ 8 — node hỏi dữ kiện của luồng
# soạn thảo trong hội thoại (`nodes/gom_du_kien.py`, Task 19). Cùng lý lẽ và cùng
# chế độ hỏng như hai khoá ngay trên: nó chạy trên MỌI lượt soạn thảo, nên vắng ở
# ba danh sách này là một lượt LLM vô hình với trần chi phí ngày.
#
# 2026-09-02: `giai_nghia_*` là điểm gọi LLM thứ 7 — node đầu vào của lượt hỏi
# NỐI TIẾP (`nodes/giai_nghia.py`). Nó ghi khoá riêng chứ không dùng chung với
# `route_*` vì nó chạy TRƯỚC `route`, nên khoá dùng chung sẽ bị `route` ghi đè
# mất. Vắng ở ba danh sách này thì mỗi lượt hỏi nối tiếp là một lượt LLM VÔ HÌNH
# với trần chi phí ngày — đúng chế độ hỏng mà `draft_generate_*` đã gây ra một
# lần (32/32 dòng `/soan-thao` mang `cost_usd = 0`).
#
# Phase 3 (PostgreSQL/FastAPI review) — `hieu_tai_lieu_*` là điểm gọi LLM thứ 9
# (`nodes/hieu_tai_lieu.py`, đường đọc/soạn tài liệu). CÙNG chế độ hỏng, lần
# THỨ BA: nó đã tồn tại từ trước lát cắt này (thiếu ở đây từ ngày node đó có
# usage thật), nhưng Phase 3 Half B đưa NHIỀU lượt hơn hẳn qua đúng node này
# (mọi câu hỏi VỀ một tài liệu đã gửi, không chỉ lượt đính kèm), nên phạm vi
# request bị bỏ sót khỏi trần chi phí ngày rộng ra đúng lúc lát cắt này chạy.
#
# 2026-09-18 (Phase 16 fix round): `rut_du_kien_*` (`nodes/rut_du_kien.py`, rút
# trường theo mẫu từ tài liệu) — CÙNG chế độ hỏng, lần THỨ TƯ: ghi khoá riêng
# từ ngày đầu, chưa từng có mặt ở ba danh sách này.
_TOKEN_IN_KEYS = (
    "route_token_in", "rewrite_query_token_in", "token_in", "tier2_token_in", "assemble_token_in",
    "draft_generate_token_in", "giai_nghia_token_in", "gom_du_kien_token_in", "hieu_tai_lieu_token_in",
    "rut_du_kien_token_in",
)
_TOKEN_OUT_KEYS = (
    "route_token_out", "rewrite_query_token_out", "token_out", "tier2_token_out", "assemble_token_out",
    "draft_generate_token_out", "giai_nghia_token_out", "gom_du_kien_token_out", "hieu_tai_lieu_token_out",
    "rut_du_kien_token_out",
)
_COST_KEYS = (
    "route_cost_usd", "rewrite_query_cost_usd", "cost_usd", "tier2_cost_usd", "assemble_cost_usd",
    "draft_generate_cost_usd", "giai_nghia_cost_usd", "gom_du_kien_cost_usd", "hieu_tai_lieu_cost_usd",
    "rut_du_kien_cost_usd",
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
    " cost_usd, generate_model, judge_model, expand_before, expand_after, cache_hit, user_sub)"
    " VALUES (:id, :endpoint, :query, :config_name, :result_type, :retrieved_ids,"
    " :claims_raw, :claims_after_tier1, :claims_after_tier2, :latency_ms, :token_in, :token_out,"
    " :cost_usd, :generate_model, :judge_model, :expand_before, :expand_after, :cache_hit,"
    " :user_sub)"
)


def _ghi_traces(
    trace_id: str, endpoint: str, query: str, config_name: str, st: dict, latency_ms: int,
    cache_hit: bool = False, user_sub: str | None = None,
) -> None:
    """Ghi MỘT hàng `traces` thật cho request này. Có thể raise — resilience
    (best-effort, không chặn response khi ghi lỗi) là quyết định của CALLER
    (`tra_cuu`), không phải của hàm ghi DB này (single responsibility: hàm
    này chỉ lo INSERT đúng, không tự quyết lỗi của nó nghiêm trọng tới đâu).

    `cache_hit=True` cho lượt phục vụ TỪ CACHE. Lượt đó vẫn ghi một dòng — nó
    vẫn là một request thật và bảng traces là nơi đếm lưu lượng — nhưng phải
    phân biệt được: latency ~10ms và cost $0 của nó trộn vào cùng cột với lượt
    gọi thật (p50 10s) sẽ kéo p50 và chi phí trung bình xuống một cách vô
    nghĩa, và bảng số liệu của khoá luận thành số của cache. Mọi cột chi phí/
    claim của dòng đó là 0 THẬT (không có lượt LLM nào chạy), không phải 0 vì
    quên ghi — chính cờ này là thứ nói ra sự khác biệt đó.

    `user_sub` = `sub` Supabase của người gọi, None khi auth chưa cấu hình (eval,
    dev local) hoặc endpoint không xác thực. KHÔNG chỉ là số liệu: hạn mức
    ngày/tháng ĐẾM chính cột này (`bao_ve.dem_luot`), nên một lượt LLM ghi thiếu
    `user_sub` là một lượt người dùng được dùng miễn phí. `cache_hit` và
    `result_type` là hai cột còn lại của phép đếm đó — cache hit không gọi LLM,
    còn `loi`/`out_of_scope` không phải thứ người dùng mua; cả ba không trừ lượt.
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
        "cache_hit": cache_hit,
        "user_sub": user_sub,
        **_tong_hop_traces(traces),
    }
    with get_engine().begin() as c:
        c.execute(_SQL_INSERT_TRACE, params)
