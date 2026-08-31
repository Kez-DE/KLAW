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
from src.models.schemas import (
    MucLucItem,
    ProvisionOut,
    TraCuuRequest,
    TraCuuResponse,
    VanBanMucLucResponse,
    VanBanProvisionsResponse,
)
from src.services.db import get_engine
# _tong_hop_traces re-exported here: test_tra_cuu.py imports it from routes, not services.traces.
from src.services.traces import _ghi_traces, _tong_hop_traces  # noqa: F401

logger = logging.getLogger(__name__)

router = APIRouter()

_graph = None


def _g():
    global _graph
    if _graph is None:
        _graph = build_graph_tra_cuu()
    return _graph


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


# ══ GET /van-ban/{doc_id} (Task 7, step 2) — ba dạng LAZY ═══════════════════
# BLDS (doc_id 95942) có 689 Điều — không dạng nào dưới đây được kéo cả cây.
# `so_dieu` là `str`, KHÔNG PHẢI `int`: số hiệu Điều trong luật VN không liên
# tục và có dạng "27a" (Bộ luật khác trong corpus dùng dạng này). "2 Điều
# trước/sau" của `around` được tính theo THỨ TỰ TRONG CÂY (`thu_tu`), KHÔNG
# PHẢI phép toán số học trên `so_hieu_cap` — cùng lý do.

_SQL_VAN_BAN_DOC = text("SELECT so_ky_hieu, ten FROM documents WHERE id = :doc_id")

_SQL_VAN_BAN_MUC_LUC = text(
    "SELECT id, cap, so_hieu_cap, tieu_de, thu_tu FROM provisions"
    " WHERE document_id = :doc_id AND cap IN ('phan', 'chuong', 'muc', 'tieu_muc')"
    " ORDER BY thu_tu"
)

_SQL_VAN_BAN_DIEU_BY_SO_HIEU = text(
    "SELECT id FROM provisions WHERE document_id = :doc_id AND cap = 'dieu' AND so_hieu_cap = :so_dieu"
)

_SQL_VAN_BAN_PROVISION_GOC = text("SELECT document_id, cap FROM provisions WHERE id = :pid")

# Đi NGƯỢC `parent_id` tới Điều cha gần nhất — CTE đệ quy (không phải một hop
# cố định) vì đo được cả hai cấu trúc thật trong corpus: Điểm có thể là con
# TRỰC TIẾP của Điều (10 dòng) hoặc con của Khoản (6.969 dòng). `UNION` (không
# `UNION ALL`) khử trùng nên một `parent_id` vòng (nếu có) không chạy vô hạn —
# cùng lý do `verify_tier1._SQL_CAY` đã dùng UNION cho đường đi XUÔI.
_SQL_VAN_BAN_DIEU_CHA = text(
    "WITH RECURSIVE nguoc AS ("
    "  SELECT id, parent_id, cap FROM provisions WHERE id = :pid"
    "  UNION"
    "  SELECT p.id, p.parent_id, p.cap FROM provisions p JOIN nguoc ON p.id = nguoc.parent_id"
    ") SELECT id FROM nguoc WHERE cap = 'dieu' LIMIT 1"
)

_SQL_VAN_BAN_DIEU_TRUOC = text(
    "SELECT id FROM provisions WHERE document_id = :doc_id AND cap = 'dieu'"
    " AND thu_tu < (SELECT thu_tu FROM provisions WHERE id = :dieu_id)"
    " ORDER BY thu_tu DESC LIMIT 2"
)
_SQL_VAN_BAN_DIEU_SAU = text(
    "SELECT id FROM provisions WHERE document_id = :doc_id AND cap = 'dieu'"
    " AND thu_tu > (SELECT thu_tu FROM provisions WHERE id = :dieu_id)"
    " ORDER BY thu_tu ASC LIMIT 2"
)

# Một Điều + TOÀN BỘ Khoản/Điểm con — con trực tiếp (Khoản, hoặc Điểm nếu nó
# nằm thẳng dưới Điều) HOẶC cháu trực tiếp (Điểm dưới Khoản). Không cần đệ quy
# sâu hơn: `dieu > khoan > diem` là đáy của cây (xem `Cap` trong domain.py).
_SQL_VAN_BAN_CAY_DIEU = text(
    "SELECT id, cap, so_hieu_cap, duong_dan, tieu_de, noi_dung FROM provisions"
    " WHERE id = :dieu_id OR parent_id = :dieu_id"
    "    OR parent_id IN (SELECT id FROM provisions WHERE parent_id = :dieu_id)"
    " ORDER BY thu_tu"
)


def _van_ban_sync(
    doc_id: str, so_dieu: str | None, around: int | None
) -> VanBanMucLucResponse | VanBanProvisionsResponse:
    """Thân đồng bộ (SQLAlchemy sync) của GET /van-ban/{doc_id} — route PHẢI
    gọi qua `run_in_threadpool` (xem `_ghi_traces` ở trên: thiếu bọc này đã
    từng là một lỗi thật trong dự án). `HTTPException` raise ở đây vẫn nổ
    đúng qua threadpool tới route.
    """
    with get_engine().connect() as conn:
        doc = conn.execute(_SQL_VAN_BAN_DOC, {"doc_id": doc_id}).mappings().one_or_none()
        if doc is None:
            raise HTTPException(status_code=404, detail=f"văn bản '{doc_id}' không tồn tại")

        if so_dieu is None and around is None:
            muc_luc = [
                MucLucItem(**dict(r))
                for r in conn.execute(_SQL_VAN_BAN_MUC_LUC, {"doc_id": doc_id}).mappings().all()
            ]
            return VanBanMucLucResponse(
                doc_id=doc_id, so_ky_hieu=doc["so_ky_hieu"], bo_luat=doc["ten"], muc_luc=muc_luc
            )

        if so_dieu is not None:
            tam_id = conn.execute(
                _SQL_VAN_BAN_DIEU_BY_SO_HIEU, {"doc_id": doc_id, "so_dieu": so_dieu}
            ).scalar_one_or_none()
            if tam_id is None:
                raise HTTPException(
                    status_code=404, detail=f"Điều {so_dieu} không tồn tại trong văn bản '{doc_id}'"
                )
            dieu_ids = [tam_id]
        else:
            goc = conn.execute(_SQL_VAN_BAN_PROVISION_GOC, {"pid": around}).mappings().one_or_none()
            if goc is None or goc["document_id"] != doc_id:
                # KHÔNG âm thầm trả rỗng — around trỏ sang provision của một
                # văn bản khác (hoặc không tồn tại) là lỗi của caller, phải nổ.
                raise HTTPException(
                    status_code=404, detail=f"provision {around} không thuộc văn bản '{doc_id}'"
                )
            if goc["cap"] == "dieu":
                tam_id = around
            else:
                tam_id = conn.execute(_SQL_VAN_BAN_DIEU_CHA, {"pid": around}).scalar_one_or_none()
                if tam_id is None:
                    raise HTTPException(
                        status_code=404, detail=f"provision {around} không thuộc Điều nào"
                    )
            truoc = conn.execute(
                _SQL_VAN_BAN_DIEU_TRUOC, {"doc_id": doc_id, "dieu_id": tam_id}
            ).scalars().all()
            sau = conn.execute(
                _SQL_VAN_BAN_DIEU_SAU, {"doc_id": doc_id, "dieu_id": tam_id}
            ).scalars().all()
            dieu_ids = [*reversed(truoc), tam_id, *sau]

        provisions: list[ProvisionOut] = []
        for dieu_id in dieu_ids:
            rows = conn.execute(_SQL_VAN_BAN_CAY_DIEU, {"dieu_id": dieu_id}).mappings().all()
            provisions.extend(ProvisionOut(**dict(r), la_tam=(dieu_id == tam_id)) for r in rows)

        return VanBanProvisionsResponse(
            doc_id=doc_id, so_ky_hieu=doc["so_ky_hieu"], bo_luat=doc["ten"], provisions=provisions
        )


@router.get("/van-ban/{doc_id}", response_model=VanBanMucLucResponse | VanBanProvisionsResponse)
async def van_ban(
    doc_id: str, so_dieu: str | None = None, around: int | None = None
) -> VanBanMucLucResponse | VanBanProvisionsResponse:
    """Lazy — BLDS 689 điều, không trả cả cây (fe-contract.md).

    không tham số → metadata + danh mục Chương/Mục
    ?so_dieu=25   → một Điều + Khoản/Điểm con
    ?around=<pid> → Điều chứa provision đó + 2 Điều trước/sau, mỗi Điều kèm
                    con của nó (dạng FE dùng nhiều nhất — click-to-verify).
                    `pid` thường là id của một Khoản (`khop_tai_id`), không
                    phải Điều — 73,6% số Điều chỉ có tiêu đề (verify_tier1).
    """
    if so_dieu is not None and around is not None:
        raise HTTPException(
            status_code=422, detail="chỉ được chọn một trong hai: so_dieu hoặc around"
        )
    return await run_in_threadpool(_van_ban_sync, doc_id, so_dieu, around)
