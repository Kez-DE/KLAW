"""Node generate_claims — LLM sinh khẳng định KÈM provision_id và quote nguyên văn.

Prompt nằm ở prompts/generate_claims.v*.md (artifact có version trong git).
JSON hỏng KHÔNG làm sập: ghi schema_error=True để đo tỉ lệ, coi như thiếu căn cứ.

Node này CỐ Ý KHÔNG lọc claim theo quote — kiểm quote có phải substring của
provisions.noi_dung là việc của tầng 1 (Task 5). Tỉ lệ claim bị tầng 1 loại là
một con số chính của khóa luận: nó đo mức mô hình sinh trích dẫn sai khi bị
buộc phải trích dẫn. Tự lọc ở đây sẽ xoá mất bằng chứng định lượng đó.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from src.services.effectivity import EffectivityVerdict
from src.services.prompts import messages

PROMPT_PATH = Path("prompts/generate_claims.v2.md")

CLAIMS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["insufficient_evidence", "claims"],
    "properties": {
        "insufficient_evidence": {"type": "boolean"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "provision_id", "quote", "hang"],
                "properties": {
                    "text": {"type": "string"},
                    "provision_id": {"type": "integer"},
                    "quote": {"type": "string"},
                    # Task 15: hàng của bảng so sánh khi `dang_tra_loi == "bang"` —
                    # null cho câu trả lời văn xuôi bình thường. `anyOf` chứ không
                    # `"type": ["object", "null"]`: schema strict (llm.py) đòi mọi
                    # thuộc tính có trong `required`, và cách null-được-phép hợp lệ
                    # với validator strict này là `anyOf`.
                    "hang": {
                        "anyOf": [
                            {"type": "null"},
                            {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["doi_tuong", "tieu_chi"],
                                "properties": {
                                    "doi_tuong": {"type": "string"},
                                    "tieu_chi": {"type": "string"},
                                },
                            },
                        ]
                    },
                },
            },
        },
    },
}


# GĐ3 (cai_thien.md §6) — vai trò của một khẳng định trong câu trả lời. Tuple
# chứ không set: thứ tự ở đây LÀ thứ tự ưu tiên mà `assemble` xếp căn cứ.
VAI_TRO = ("ket_luan", "dieu_kien", "ngoai_le", "che_tai")

# generate_claims.v3 — v2 cộng `vai_tro` + `tra_loi_muc_tieu`. Dựng TỪ
# `CLAIMS_SCHEMA` chứ không chép lại: hai bản sao của cùng một schema sẽ lệch
# pha đúng vào ngày ai đó sửa một bên. Chọn theo NỘI DUNG template (cùng khuôn
# `rewrite_query.py`), không theo tên file.
_ITEM_V2 = CLAIMS_SCHEMA["properties"]["claims"]["items"]
CLAIMS_V3_SCHEMA = {
    **CLAIMS_SCHEMA,
    "properties": {
        **CLAIMS_SCHEMA["properties"],
        "claims": {
            "type": "array",
            "items": {
                **_ITEM_V2,
                "required": [*_ITEM_V2["required"], "vai_tro", "tra_loi_muc_tieu"],
                "properties": {
                    **_ITEM_V2["properties"],
                    "vai_tro": {"type": "string", "enum": list(VAI_TRO)},
                    "tra_loi_muc_tieu": {"type": "boolean"},
                },
            },
        },
    },
}


@dataclass(frozen=True)
class Claim:
    text: str
    provision_id: int
    quote: str
    # Task 15 — bảng so sánh dựng TỪ luận điểm đã kiểm (`assemble.dung_bang_tu_luan_diem`).
    # `None` cho một khẳng định văn xuôi bình thường; `{"doi_tuong": ..., "tieu_chi": ...}`
    # khi `dang_tra_loi == "bang"` (router v3) và mô hình xác định được cả hai.
    hang: dict | None = None
    # GĐ3 — `None` khi prompt sinh là v2 (không hỏi vai trò). `assemble` chỉ bật
    # đường xếp/khử trùng theo vai trò khi có ít nhất một claim mang vai trò, nên
    # `None` giữ nguyên hành vi v2.
    vai_tro: str | None = None
    # Mô hình TỰ chấm "có trả lời mục tiêu không" — ghi lại để đối chiếu với
    # `tier2.relevant` (người chấm độc lập), KHÔNG dùng để lọc: tự chấm của
    # người viết không phải một phép kiểm.
    tra_loi_muc_tieu: bool | None = None


def build_context(provisions: list[dict]) -> str:
    """Gộp theo VĂN BẢN, mỗi điều khoản mang thêm verdict hiệu lực (Pha 3a, spec
    2026-09-02 §7).

    Định danh văn bản bằng so_ky_hieu (Global Constraint) — KHÔNG dùng ten/title
    của văn bản. so_ky_hieu được đưa tường minh cho model, không chỉ ẩn bên trong
    chuỗi duong_dan; việc gộp nhóm không được làm mờ nó, cũng không được làm mờ
    `provision_id` mà model buộc phải dẫn chính xác.

    Vì sao GỘP: bản trước dàn PHẲNG, mỗi điều khoản một khối ngăn bằng `---`, nên
    một tập vài chục điều khoản (đo 2026-09-02: 30 dòng ở một ca, 272 ở một ca
    khác) trông như vài chục nguồn NGANG HÀNG — trong khi phần lớn chỉ là các
    Khoản/Điểm của cùng vài Điều trong cùng một văn bản. Giữ nguyên thứ tự truy
    hồi: văn bản nào có điều khoản xếp hạng cao nhất thì đứng trước (dict giữ
    thứ tự chèn).

    Vì sao có `hieu_luc` và `loai_van_ban`: hai thứ này đã nằm ngay trong cùng bản
    ghi mà bản trước không đọc tới. Không có chúng, model không có cách nào ưu
    tiên văn bản còn áp dụng (gốc của lỗi lương tối thiểu ở Plan 1: bốn nghị định
    đã bị thay thế được trình bày ngang hàng với bản hiện hành) và không phân biệt
    được Bộ luật với Thông tư để áp thứ bậc hiệu lực.

    Verdict LẤY LẠI từ `expanded` (expand() đã tính qua cạnh đi vào thật), KHÔNG
    tính lại: tính lại ở tầng này sẽ ăn `canh_di_vao` rỗng và luôn ra
    `con_hieu_luc` — đúng cái bẫy `graph_tra_cuu.n_tier1` đang chặn.

    RÀNG BUỘC: hiệu lực vào bối cảnh CHỈ để model chọn nguồn. Model không được
    phát biểu về hiệu lực trong `text` của claim (`prompts/assemble.v1.md` quy tắc
    10: hệ thống tự gắn nhãn hiệu lực từ dữ liệu đã kiểm ở tầng citation) — lệnh
    cấm đó nằm ở quy tắc 4 của prompt, chỗ duy nhất model đọc được.
    """
    # Gộp theo `document_id`, KHÔNG theo `so_ky_hieu`: `so_ky_hieu` KHÔNG duy
    # nhất. ĐO ĐƯỢC trên DB thật 2026-09-02 (review): `65/2006/QH11` có HAI dòng
    # trong `documents` — "Luật sư số 65/2006/QH11" (loai=Luật) và "Nghị quyết số
    # 65/2006/QH11" (loai=Nghị quyết). Gộp theo khoá đó thì hai văn bản khác nhau
    # thành MỘT đầu mục, và `loai_van_ban` của đầu mục lấy của phần tử đầu nhóm —
    # nên quy tắc 4 của prompt (ưu tiên văn bản cấp cao hơn) tính sai giữa hai
    # văn bản nó tưởng là một.
    #
    # Trích dẫn KHÔNG hỏng vì mỗi dòng thân bài vẫn mang `provision_id` riêng và
    # tier 1 kiểm quote theo đúng id đó, không đi qua đầu mục. Ca này cũng đang
    # BẤT HOẠT vì phía "Luật sư" có 0 provision nên không vào được `expand()` —
    # nhưng đó là may rủi dữ liệu, không phải mã chặn, và `document_id` (khoá
    # ngoại, chắc chắn duy nhất) đã nằm sẵn trong mỗi dict.
    nhom: dict[str, list[dict]] = {}
    for p in provisions:
        nhom.setdefault(str(p["document_id"]), []).append(p)

    khoi: list[str] = []
    for cac_p in nhom.values():
        than: list[str] = []
        for p in cac_p:
            # `getattr` trên chính `p.get(...)`: bắt CẢ ca thiếu khoá và ca None
            # bằng một biểu thức. Mặc định `chua_xac_dinh`, TUYỆT ĐỐI KHÔNG
            # `con_hieu_luc` — một điều khoản chưa từng được đánh giá hiện ra
            # "còn hiệu lực" là chế độ hỏng nguy hiểm nhất của cả đề tài
            # (src/services/effectivity.py; graph_tra_cuu.n_tier1 chặn đúng ca này).
            verdict = getattr(p.get("effectivity"), "verdict", None) or EffectivityVerdict.chua_xac_dinh
            # KHÔNG in `tieu_de` — Task 1 (2026-09-02) review: `prov_parser.py`
            # (dòng 21) tài liệu hoá `noi_dung` ĐÃ LÀ toàn văn (nhãn + thân).
            # Với hang_bang/khoan/diem, `tieu_de` là nhãn TỔNG HỢP
            # (`f"{NHAN[cap]} {so_hieu_cap}"`, `prov_parser.py` dòng 995-999,
            # vd. "Khoản 1", "Vùng III") — KHÔNG phải một dòng tồn tại tách
            # biệt trong nguồn. In nó thành dòng RIÊNG đứng trước `noi_dung`
            # (bản trước bản này) khiến một model chép "nguyên văn" cả hai dòng
            # tạo ra `quote` không còn là substring của `noi_dung` — tầng 1 loại
            # đúng, nhưng vì build_context tự thêm chữ không có trong nguồn, chứ
            # không phải model bịa (task-1-report.md: 3/5 lần chạy thật dính ca
            # này, mọi claim của lượt đó rớt sạch → abstain dù nguồn có thật).
            # `duong_dan` trên dòng metadata đã đủ cho model biết đây là Khoản/
            # Vùng nào — không mất thông tin nào khi bỏ dòng tieu_de.
            noi_dung = (p.get("noi_dung") or "").strip()
            than.append(f"[provision_id={p['id']}] duong_dan={p['duong_dan']} hieu_luc={verdict}\n{noi_dung}")
        # `so_ky_hieu` và `loai_van_ban` lấy của dòng đầu nhóm — nhóm nay khoá theo
        # `document_id` nên MỌI dòng trong nhóm chắc chắn cùng một văn bản, cùng một
        # số hiệu, cùng một loại (JOIN documents trong `expand._SQL_PROV`). Rỗng/NULL
        # ⇒ "không rõ", không bịa một loại để model áp thứ bậc lên thứ ta không biết.
        dau = cac_p[0]
        loai = dau.get("loai_van_ban") or "không rõ"
        khoi.append(f"VĂN BẢN so_ky_hieu={dau['so_ky_hieu']} loai_van_ban={loai}\n\n"
                    + "\n\n".join(than))
    return "\n\n---\n\n".join(khoi)


def _claim_tu(c: dict) -> Claim:
    """Một claim thô → `Claim`. `vai_tro` lạ (ngoài `VAI_TRO`) rơi về None chứ
    KHÔNG làm hỏng cả batch: vai trò chỉ dùng để xếp chỗ trong văn xuôi, còn
    trích dẫn của chính claim đó vẫn phải qua đủ hai tầng kiểm như mọi claim."""
    # `isinstance` trước: một phần tử KHÔNG phải dict phải rơi vào đúng TypeError
    # mà `generate_claims` đã bắt (→ schema_error), không thành AttributeError lọt lưới.
    if isinstance(c, dict) and "vai_tro" in c and c.get("vai_tro") not in VAI_TRO:
        c = {**c, "vai_tro": None}
    return Claim(**c)


def generate_claims(state: dict, llm, model: str, prompt_path: Path | None = None) -> dict:
    # Import cục bộ, không ở đầu module: `src.services.bo_nho` kéo theo
    # `src.services.traces`, mà `traces.py` import `normalize` từ
    # `verify_tier1.py`, và `verify_tier1.py` import `Claim` từ CHÍNH module
    # này — một import ở đầu file sẽ dựng vòng tròn lúc nạp module.
    from src.services.bo_nho import khoi_tinh_huong

    prior_traces = state.get("traces") or {}
    expanded = state.get("expanded") or []
    if not expanded:
        return {
            **state,
            "draft_claims": [],
            "insufficient_evidence": True,
            "schema_error": False,
            "traces": {**prior_traces, "claims_raw": 0, "token_in": 0, "token_out": 0, "cost_usd": 0.0},
        }

    mau = (prompt_path or PROMPT_PATH).read_text(encoding="utf-8")
    khung = state.get("khung_yeu_cau") or {}
    prompt = mau.format(
        cau_hoi=state["query"],
        context=build_context(expanded),
        tinh_huong=khoi_tinh_huong(state.get("ho_so") or {}),
        # Router v3 (Task 13) — "van_xuoi" khi state chưa mang khoá này (router
        # v2 hoặc test cũ gọi generate_claims() trực tiếp).
        dang_tra_loi=state.get("dang_tra_loi") or "van_xuoi",
        # GĐ2 — khung yêu cầu do chính lượt `rewrite_query` dựng. Rỗng khi
        # rewrite v2 (mặc định): `str.format` bỏ qua kwargs thừa nên v2 không đổi.
        muc_tieu=khung.get("muc_tieu") or "",
        cau_hoi_phap_ly=khung.get("cau_hoi_phap_ly") or "",
    )
    raw, usage = llm.chat(model, messages(prompt),
                          json_schema=CLAIMS_V3_SCHEMA if "vai_tro" in mau else CLAIMS_SCHEMA)
    try:
        data = json.loads(raw)
        claims = [_claim_tu(c) for c in data.get("claims", [])]
        insufficient = bool(data.get("insufficient_evidence"))
        schema_error = False
    except (json.JSONDecodeError, TypeError, ValueError):
        claims, insufficient, schema_error = [], True, True

    # Chỉ ghi khi CÓ vai trò: với prompt v2 (mặc định) traces giữ nguyên đúng bốn
    # khoá cũ — một khoá rỗng thêm vào mọi lượt làm hỏng phép so baseline.
    theo_vai_tro: dict[str, int] = {}
    for c in claims:
        if c.vai_tro:
            theo_vai_tro[c.vai_tro] = theo_vai_tro.get(c.vai_tro, 0) + 1

    return {
        **state,
        "draft_claims": claims,
        "insufficient_evidence": insufficient,
        "schema_error": schema_error,
        "traces": {
            **prior_traces,
            **({"claims_theo_vai_tro": theo_vai_tro} if theo_vai_tro else {}),
            "claims_raw": len(claims),
            "token_in": usage.token_in,
            "token_out": usage.token_out,
            "cost_usd": usage.cost_usd,
        },
    }
