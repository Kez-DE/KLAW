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

from src.agents.graph_soan_thao import cac_loai, load_checklist_cached
from src.agents.nodes.gioi_thieu import chac_chan_meta
from src.services import khuon_mau
from src.services.kho import xin_dang_bang

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

# một nguồn, thêm Intent mới chỉ sửa một chỗ — TRỪ `tai_lieu`, ý định DUY NHẤT
# có điều kiện: nó chỉ được chào ra khi hội thoại thật sự có tài liệu, nên nó
# sống ở `schema_v4()` chứ không ở đây (quyết định chủ sở hữu 2026-09-16 Q4).
_INTENT_ENUM = INTENT_SCHEMA["properties"]["intent"]["enum"]


def schema_v2() -> dict:
    """Schema strict của template v2 (spec soạn-thảo-trong-chat §4.1). Enum loại
    dựng LÚC GỌI từ checklist trên đĩa — thêm một file YAML là router biết ngay,
    không có danh sách viết tay để lệch. Strict đòi mọi khoá `required`, nên đây
    là schema riêng thay vì v1 cộng khoá optional (cùng lý do QUERIES_V2_SCHEMA)."""
    loai = _cac_loai_router()
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["intent", "loai_van_ban", "thay_the", "ly_do"],
        "properties": {
            "intent": {"type": "string", "enum": _INTENT_ENUM},
            "loai_van_ban": {"type": "string", "enum": [*loai, "khong_ro"]},
            "thay_the": {"type": "array", "items": {"type": "string", "enum": loai}, "maxItems": 2},
            "ly_do": {"type": "string"},
        },
    }


def schema_v3() -> dict:
    """Schema strict của template v3 (spec bộ-nhớ-tính-cách-soạn-thảo §7.4) — v2
    cộng hai trường `dang_tra_loi` (dạng câu trả lời) và `y_dinh_phu` (ý định
    phụ soạn thảo bên cạnh tra cứu). Cùng lý do `schema_v2` không phải `INTENT_SCHEMA`
    cộng khoá optional: strict đòi mọi khoá `required`."""
    s = schema_v2()
    s["required"] = [*s["required"], "dang_tra_loi", "y_dinh_phu"]
    s["properties"]["dang_tra_loi"] = {"type": "string", "enum": ["van_xuoi", "bang"]}
    s["properties"]["y_dinh_phu"] = {"type": "string", "enum": ["soan_thao", "khong"]}
    return s


def schema_v4(co_tai_lieu: bool) -> dict:
    """Schema strict của template v4 — v3 cộng ý định `tai_lieu`, CHỈ khi hội
    thoại đang giữ tài liệu.

    Mở enum vô điều kiện là mời model rẽ một câu hỏi luật bình thường sang node
    đọc tài liệu khi không có tài liệu nào để đọc — một ngõ cụt câm, không phải
    một câu trả lời sai nhìn thấy được. Cùng khuôn điều kiện với `{dang_soan}`
    của v3: thứ gì không tồn tại trong phiên thì model không được chào.

    Dựng dict `intent` MỚI thay vì `.append` vào `_INTENT_ENUM`: `schema_v2`/
    `schema_v3` dùng CHUNG đúng list đó, nên một lần bồi thêm sẽ rò `tai_lieu`
    sang mọi bản template cũ cho tới khi tiến trình khởi động lại.
    """
    s = schema_v3()
    s["properties"]["intent"] = {
        "type": "string",
        "enum": [*_INTENT_ENUM, Intent.tai_lieu.value] if co_tai_lieu else list(_INTENT_ENUM),
    }
    return s


def _tai_lieu_trong_phien(rows: list[dict] | None) -> str:
    """`{tai_lieu_trong_phien}` của route.v4 — tài liệu hội thoại này đang giữ.

    Một dòng mỗi tài liệu, `"(không)"` khi chưa có cái nào (cùng quy ước
    `_dang_soan`). QT-3: khác `{dang_soan}` (dựng từ tên checklist trong repo),
    khối này mang CHỮ CỦA NGƯỜI DÙNG — tên tệp và mô tả — nên template v4 tự
    khai nó là dữ liệu chứ không phải chỉ dẫn.
    """
    if not rows:
        return "(không)"
    return "\n".join(
        f"- {r.get('ten_tep') or '(không tên)'} — {r.get('mo_ta') or 'chưa mô tả'}"
        f" ({r.get('so_don_vi') or 0} đơn vị)"
        for r in rows
    )


def _cac_loai_router() -> list[str]:
    """Mã loại router được chọn: mọi checklist cộng mọi khuôn mẫu (khuôn mẫu, §4) —
    một loại chỉ có khuôn mẫu chỉ tới được `hieu_tai_lieu`, vì `gom_du_kien` và
    `assemble._goi_y_soan_thao` vẫn kiểm `cac_loai()` của checklist."""
    return sorted(cac_loai() | khuon_mau.cac_loai())


def _ten_loai(loai: str) -> str:
    return load_checklist_cached(loai).ten if loai in cac_loai() else khuon_mau.nap(loai)["ten"]


def danh_sach_loai() -> str:
    """Một dòng `mã — tên` cho mỗi loại, điền vào `{danh_sach_loai}` của v2."""
    return "\n".join(f"- `{loai}` — {_ten_loai(loai)}" for loai in _cac_loai_router())


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
    # Hỏi về NỘI DUNG một tài liệu người hỏi đã gửi trong hội thoại này. Ý định
    # DUY NHẤT có điều kiện: chỉ `schema_v4(co_tai_lieu=True)` chào nó ra, nên
    # nó KHÔNG nằm trong `INTENT_SCHEMA`/`_INTENT_ENUM` (v1/v2/v3 không biết).
    # Lượt ĐÍNH KÈM tài liệu không đi qua đây chút nào — nó rẽ tất định 0 token
    # ở `graph_tra_cuu._vao_graph`; nhánh này chỉ cho lượt NỐI TIẾP hỏi về một
    # tài liệu đã gửi từ lượt trước.
    tai_lieu = "tai_lieu"


def _dang_soan(sd: dict | None, bt: dict | None = None) -> str:
    """`{dang_soan}` của route.v3 (Task 19) — cho model biết hội thoại này có
    đang mở một phiên soạn thảo hay không, và đã gom được bao nhiêu dữ kiện,
    để nó phân biệt một câu trả lời dữ kiện/yêu cầu sửa bản thảo với một câu
    hỏi luật thật sự (xem prompt). `"(không)"` khi chưa mở phiên soạn nào.

    Một `loai` không tra được checklist (YAML bị gỡ hay đổi tên sau khi phiên đã
    mở bản thảo loại đó) cũng là `"(không)"`, KHÔNG phải một ngoại lệ: module này
    cố ý không nuốt lỗi (xem docstring đầu file), nên `ValueError` ở đây thành
    HTTP 500 cho MỌI lượt sau của phiên — kể cả một câu hỏi luật bình thường
    không dính gì tới soạn thảo. `gom_du_kien` đã có nhánh `khong_ro_loai` để rơi
    vào."""
    loai = (sd or {}).get("loai")
    if not loai:
        return _khuon_mau_dang_mo(bt)
    try:
        ten = load_checklist_cached(loai).ten
    except ValueError:
        return "(không)"
    return f"{ten} (đã có {len(sd.get('facts') or {})} dữ kiện)"


def _khuon_mau_dang_mo(bt: dict | None) -> str:
    """Dòng `{dang_soan}` khi không có checklist đang gom mà hội thoại có một KHUÔN MẪU
    đang mở (dòng nhẹ `ban_thao_tong_quat_dang_mo`, `nguon = 'khuon_mau'`) — thiết kế
    §4: router thấy bản thảo đang mở, không có phép đè nào sau nó. Chỉ dựng từ dữ liệu
    repo (tên loại trong registry, số điều): không bao giờ tiêu đề mô hình viết hay chữ
    người dùng (QT-3). Bản HTML hay bản trên tệp tải lên: "(không)", như trước."""
    if (bt or {}).get("nguon") != "khuon_mau":
        return "(không)"
    lk = bt.get("loai_khuon")
    try:
        ten = khuon_mau.nap(lk)["ten"] if lk in khuon_mau.cac_loai() else "văn bản tự soạn"
    except ValueError:
        ten = "văn bản tự soạn"
    n = int((bt.get("audit") or {}).get("so_dieu_khoan") or 0)
    return f"{ten} (bản thảo Word đang mở, {n} điều)"


def route(state: dict, llm, model: str, prompt_path: Path | None = None) -> dict:
    prior_traces = state.get("traces") or {}
    mau = (prompt_path or PROMPT_PATH).read_text(encoding="utf-8")
    # Template nhắc `dang_tra_loi` là template v3; `loai_van_ban` (không kèm
    # `dang_tra_loi`) là v2 — chọn theo NỘI DUNG, không theo tên file, để một
    # bản v4 cùng hình dạng vẫn chạy đúng schema.
    la_v3 = "dang_tra_loi" in mau
    la_v2 = la_v3 or "loai_van_ban" in mau
    # v4 = v3 cộng khối tài liệu của hội thoại. Nhận theo NỘI DUNG như hai bản
    # trước, không theo tên file.
    la_v4 = "{tai_lieu_trong_phien}" in mau
    co_tai_lieu = bool(state.get("tai_lieu_phien"))
    # `dang_soan` truyền LUÔN, kể cả cho template v1/v2 không có `{dang_soan}`:
    # `str.format` bỏ qua kwargs thừa, nên không cần một nhánh điều kiện thứ ba.
    prompt = mau.format(
        cau_hoi=state["query"],
        danh_sach_loai=danh_sach_loai() if la_v2 else "",
        dang_soan=_dang_soan(state.get("soan_thao_dang_mo"), state.get("ban_thao_tong_quat_dang_mo")),
        tai_lieu_trong_phien=_tai_lieu_trong_phien(state.get("tai_lieu_phien")),
    )
    # llm.chat(...) NẰM NGOÀI try: lỗi hạ tầng thật (content rỗng, usage thiếu
    # — xem ValueError ở llm.py chat()/_usage_from()) phải NỔ RA NGOÀI, đúng
    # ruling gốc của module này (docstring đầu file). Bọc nó CÙNG phần parse
    # bên dưới sẽ khiến "OpenRouter chết" và "model trả intent không nhận ra"
    # rơi vào MỘT nhánh fallback tra_cuu như nhau — hai chế độ hỏng khác nhau
    # mà số liệu độ chính xác route sau này không tách lại được (silent-failure
    # review, sau task-10).
    raw, usage = llm.chat(
        model,
        [{"role": "user", "content": prompt}],
        json_schema=(
            schema_v4(co_tai_lieu) if la_v4
            else (schema_v3() if la_v3 else (schema_v2() if la_v2 else INTENT_SCHEMA))
        ),
    )
    data: dict = {}
    try:
        data = json.loads(raw)
        intent = Intent(data["intent"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError, RuntimeError):
        # Route sai sang ngoai_pham_vi làm hệ thống từ chối oan.
        # Mặc định tra_cuu, để verifier và abstain quyết định.
        intent = Intent.tra_cuu
        data = data if isinstance(data, dict) else {}
    # Ý định phụ chỉ có nghĩa khi ý định CHÍNH là tra_cuu — người hỏi vừa hỏi
    # luật vừa nhờ soạn. Khi intent CHÍNH đã là soan_thao, gợi ý dựng ở nhánh
    # dưới đây (cùng đường cũ) là đủ, không cần thêm cờ y_dinh_phu.
    # Phép kiểm 0 token: `tai_lieu` mà hội thoại không giữ tài liệu nào thì
    # `hieu_tai_lieu` không có gì để đọc — hạ về mặc định an toàn thay vì rẽ vào
    # một ngõ cụt câm. Với lượt ĐÍNH KÈM thì `_vao_graph` đã rẽ trước `route`,
    # nên `tai_lieu_ids` cũng tính là "có tài liệu" cho người gọi trực tiếp.
    if intent is Intent.tai_lieu and not (state.get("tai_lieu_phien") or state.get("tai_lieu_ids")):
        intent = Intent.tra_cuu
    # Deterministic guard over the LLM verdict — see gioi_thieu.chac_chan_meta.
    ep_meta = intent not in (Intent.gioi_thieu, Intent.hoi_ve_kho) and chac_chan_meta(state["query"])
    if ep_meta:
        intent = Intent.gioi_thieu
    y_dinh_phu = data.get("y_dinh_phu") if la_v3 else None
    y_dinh_phu = "soan_thao" if y_dinh_phu == "soan_thao" and intent is Intent.tra_cuu else None
    goi_y: dict | None = None
    if la_v2 and (intent is Intent.soan_thao or y_dinh_phu == "soan_thao"):
        lv = data.get("loai_van_ban")
        goi_y = {
            "loai": lv if isinstance(lv, str) and lv != "khong_ro" else None,
            "ly_do": str(data.get("ly_do") or "")[:300],
            "thay_the": [t for t in (data.get("thay_the") or []) if isinstance(t, str)][:2],
        }
    # Quy tắc 0 token: câu hỏi tự xin "dạng bảng" (services.kho.xin_dang_bang)
    # THẮNG lựa chọn của model — cùng quy tắc `n_assemble` đã áp cho `hoi_ve_kho`.
    dang = "bang" if xin_dang_bang(state["query"]) else (data.get("dang_tra_loi") if la_v3 else "van_xuoi")
    dang_tra_loi = dang if dang in ("van_xuoi", "bang") else "van_xuoi"
    return {
        **state,
        "intent": intent,
        **({"soan_thao_goi_y": goi_y} if la_v2 else {}),
        **({"dang_tra_loi": dang_tra_loi, "y_dinh_phu": y_dinh_phu} if la_v3 else {}),
        "traces": {
            **prior_traces,
            "route_model": model,
            "route_ep_meta": ep_meta,
            "route_token_in": usage.token_in if usage else 0,
            "route_token_out": usage.token_out if usage else 0,
            "route_cost_usd": usage.cost_usd if usage else 0.0,
        },
    }
