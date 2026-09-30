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
import re
from pathlib import Path

from src.agents.nodes.hoi_lai import bi_loai
from src.services.bo_nho import _vuong_luoi_chan, ho_so_theo_linh_vuc, khoi_tinh_huong

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

# v3 (cai_thien.md GĐ2): the same turn also yields the request frame — what the
# asker needs, the legal question behind it, and the decisive facts still missing.
# Strict schema again, so a separate object; chosen when the template mentions
# `muc_tieu`.
QUERIES_V3_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "quan_he", "vai", "linh_vuc", "ba_lop", "du_kien_van_ban",
        "muc_tieu", "cau_hoi_phap_ly", "du_kien_quyet_dinh_con_thieu", "queries",
    ],
    "properties": {
        **QUERIES_V2_SCHEMA["properties"],
        "muc_tieu": {"type": "string"},
        "cau_hoi_phap_ly": {"type": "string"},
        "du_kien_quyet_dinh_con_thieu": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ma", "cau", "lam_doi_ket_luan"],
                "properties": {
                    "ma": {"type": "string"},
                    "cau": {"type": "string"},
                    "lam_doi_ket_luan": {"type": "boolean"},
                },
            },
        },
    },
}
TOI_DA_DU_KIEN_THIEU = 3
_RE_MA = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


def _dong_khung(gia_tri: object, toi_da: int = 200) -> str:
    """One trimmed line for a frame field; anything that fails the number/PII
    net (`bo_nho._vuong_luoi_chan`) is dropped — the frame is a reading, never
    a place for an article number the two verification tiers cannot see."""
    s = " ".join(str(gia_tri or "").split())[:toi_da]
    return "" if not s or _vuong_luoi_chan(s) else s


def khung_yeu_cau_tu(data: dict, ho_so: dict | None) -> dict | None:
    """Pure: validate and filter the model's frame. Returns None when nothing
    usable survives, so callers can fall back to the pre-frame behaviour.

    Each missing-fact question must pass `hoi_lai.bi_loai` (no legal thresholds
    stated as questions) and must not name a profile key the asker already
    filled — a stated fact beats anything the model wants to re-ask.
    """
    muc_tieu = _dong_khung(data.get("muc_tieu"))
    cau_hoi_phap_ly = _dong_khung(data.get("cau_hoi_phap_ly"), 300)
    da_biet = {k for k, v in (ho_so or {}).items() if isinstance(v, dict) and v.get("gia_tri")}
    thieu: list[dict] = []
    for m in data.get("du_kien_quyet_dinh_con_thieu") or []:
        if not isinstance(m, dict):
            continue
        ma = str(m.get("ma") or "").strip().lower()
        cau = _dong_khung(m.get("cau"))
        if not _RE_MA.match(ma) or ma in da_biet or not cau or bi_loai(cau):
            continue
        if not cau.endswith("?"):
            cau += "?"
        thieu.append({"ma": ma, "cau": cau, "lam_doi_ket_luan": m.get("lam_doi_ket_luan") is True})
        if len(thieu) == TOI_DA_DU_KIEN_THIEU:
            break
    if not (muc_tieu or cau_hoi_phap_ly or thieu):
        return None
    return {"muc_tieu": muc_tieu, "cau_hoi_phap_ly": cau_hoi_phap_ly, "du_kien_quyet_dinh_con_thieu": thieu}


def rewrite_query(state: dict, llm, model: str, prompt_path: Path | None = None) -> dict:
    prior_traces = state.get("traces") or {}
    goc = state["query"]
    mau = (prompt_path or PROMPT_PATH).read_text(encoding="utf-8")
    # Nền (`ho_so_nen`) KHÔNG vào prompt: mô hình dùng khối tình huống để viết truy vấn, và
    # chính bước này phán định lĩnh vực — đọc nền ở đây là để ký ức lao động lái truy hồi
    # rồi tự quyết nó có liên quan không (trace c8a98c3d: 9 điều BLLĐ từ hai biến thể cho
    # câu hỏi về hệ thống pháp luật). Nền chỉ vào lượt SAU phán định, khi là lao động.
    # ponytail: câu lao động của người có nền được viết truy vấn không có vai từ nền; gọi
    # lại lần hai có nền khi đo được recall hụt ở ca đó.
    ho_so, nen = state.get("ho_so") or {}, state.get("ho_so_nen") or {}
    prompt = mau.format(cau_hoi=goc, tinh_huong=khoi_tinh_huong(ho_so))
    # Template nhắc tới `quan_he` là template v2 — chọn schema theo NỘI DUNG
    # template, không theo tên file, để một bản v3 cùng hình dạng vẫn chạy.
    la_v3 = "muc_tieu" in mau
    la_v2 = la_v3 or "quan_he" in mau
    schema = QUERIES_V3_SCHEMA if la_v3 else QUERIES_V2_SCHEMA if la_v2 else QUERIES_SCHEMA
    usage = None
    degraded = False
    linh_vuc: str | None = None
    nhan_dien: dict = {}
    khung: dict | None = None
    try:
        raw, usage = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=schema)
        data = json.loads(raw)
        them = [q for q in data.get("queries", []) if q and q.strip() != goc.strip()]
        if la_v2:
            lv = data.get("linh_vuc")
            linh_vuc = lv.strip() if isinstance(lv, str) and lv.strip() else None
            nhan_dien = {k: data.get(k) for k in _KHOA_NHAN_DIEN}
        ho_so = ho_so_theo_linh_vuc(ho_so, nen, linh_vuc)
        if la_v3:
            khung = khung_yeu_cau_tu(data, ho_so)
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
        "ho_so": ho_so,
        "khung_yeu_cau": khung,
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
