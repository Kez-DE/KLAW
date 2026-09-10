"""Node `gom_du_kien` — soạn thảo hội thoại (spec 2026-09-09 §8.2): trích dữ kiện cho loại văn
bản đang soạn bằng structured output có lược đồ dựng LÚC GỌI từ `FactFieldOut` (rules.yaml),
gộp vào trạng thái soạn thảo của phiên, và tính trường bắt buộc còn thiếu. `du` của model chỉ
là gợi ý: Python phủ quyết khi còn trường bắt buộc trống, trừ khi người dùng bảo "cứ soạn".
Khuôn theo tutorial "information gathering" của LangGraph: pha gom kết thúc bằng chính
structured output, không bằng một cờ riêng."""

import json
import logging
import re
from pathlib import Path

from src.agents.graph_soan_thao import load_checklist_cached, load_facts_meta_cached, rules_cho
from src.services.bo_nho import khoi_tinh_huong
from src.services.prompts import messages
from src.services.rules import mo_ta_facts

logger = logging.getLogger(__name__)
PROMPT_PATH = Path("prompts/gom_du_kien.v1.md")
TOI_DA_HOI = 6
CUM_CU_SOAN = ("cứ soạn", "soạn luôn", "soạn đi", "bỏ qua", "soạn tạm")
_RE_CU_SOAN = re.compile("|".join(re.escape(c) for c in CUM_CU_SOAN), re.IGNORECASE)


def truong_cua(loai: str) -> list[dict]:
    return mo_ta_facts(rules_cho(loai), load_facts_meta_cached())


def schema_du_kien(loai: str) -> dict:
    props: dict = {}
    for t in truong_cua(loai):
        props[t["key"]] = {"type": "string", "enum": ["", *t["lua_chon"]]} if t.get("lua_chon") else {"type": "string"}
    props["du"] = {"type": "boolean"}
    props["ghi_chu"] = {"type": "string"}
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


def con_thieu(loai: str, facts: dict) -> list[dict]:
    return [t for t in truong_cua(loai) if t["bat_buoc"] and not str((facts or {}).get(t["key"]) or "").strip()]


def _dong_truong(truong: list[dict], facts: dict) -> str:
    return "\n".join(
        f"- `{t['key']}` ({t['nhan']}, {'bắt buộc' if t['bat_buoc'] else 'tuỳ chọn'}"
        + (f", chọn một trong: {', '.join(t['lua_chon'])}" if t.get("lua_chon") else "")
        + f"): hiện có = {facts.get(t['key']) or '(trống)'}"
        for t in truong
    )


def gom_du_kien(state: dict, llm, model: str) -> dict:
    prior = state.get("traces") or {}
    dang = dict(state.get("soan_thao_dang_mo") or {})
    loai = dang.get("loai") or (state.get("soan_thao_goi_y") or {}).get("loai")
    if not loai:
        return {**state, "soan_thao_dang_mo": None, "traces": {**prior, "gom_du_kien_nguon": "khong_ro_loai"}}
    facts = dict(dang.get("facts") or {})
    truong = truong_cua(loai)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        ten=load_checklist_cached(loai).ten,
        truong=_dong_truong(truong, facts),
        tinh_huong=khoi_tinh_huong(state.get("ho_so") or {}),
        cau_hoi=state.get("query", ""),
    )
    nguon = "llm"
    try:
        raw, usage = llm.chat(model, messages(prompt), json_schema=schema_du_kien(loai))
        ra = json.loads(raw)
        if not isinstance(ra, dict):
            raise TypeError(f"phản hồi phải là object, được {type(ra).__name__}")
    except Exception as e:
        logger.warning(
            "gom_du_kien: lỗi (%s: %s) — giữ facts cũ, hỏi lại phần thiếu", type(e).__name__, e, exc_info=True
        )
        ra, usage, nguon = {}, None, "loi"
    for t in truong:
        v = str(ra.get(t["key"]) or "").strip()
        if v:
            facts[t["key"]] = v
    thieu = con_thieu(loai, facts)
    cu_soan = bool(_RE_CU_SOAN.search(state.get("query", "")))
    du = not thieu or cu_soan
    return {
        **state,
        "soan_thao_dang_mo": {
            **dang,
            "loai": loai,
            "facts": facts,
            "ban_thao_id": dang.get("ban_thao_id"),
            "so_lan_sua": int(dang.get("so_lan_sua") or 0),
            "con_thieu": thieu[:TOI_DA_HOI],
            "du": du,
            "cu_soan": cu_soan,
        },
        "traces": {
            **prior,
            "gom_du_kien_nguon": nguon,
            "gom_du_kien_token_in": usage.token_in if usage else 0,
            "gom_du_kien_token_out": usage.token_out if usage else 0,
            "gom_du_kien_cost_usd": usage.cost_usd if usage else 0.0,
        },
    }
