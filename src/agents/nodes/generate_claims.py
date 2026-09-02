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

PROMPT_PATH = Path("prompts/generate_claims.v1.md")

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
                "required": ["text", "provision_id", "quote"],
                "properties": {
                    "text": {"type": "string"},
                    "provision_id": {"type": "integer"},
                    "quote": {"type": "string"},
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
            # 72,1-73,6% số Điều trong corpus có `noi_dung` CHỈ LÀ TIÊU ĐỀ (đo ở
            # `verify_tier1._cay_con`), nên với phần lớn khối Điều hai trường này
            # trùng khít và in cả hai là lặp nguyên một dòng — nhân với 272 điều
            # khoản của một ca thật thì đó là nhiễu thật, không phải chi tiết.
            tieu_de = (p.get("tieu_de") or "").strip()
            noi_dung = (p.get("noi_dung") or "").strip()
            than.append(
                f"[provision_id={p['id']}] duong_dan={p['duong_dan']} hieu_luc={verdict}\n"
                + (noi_dung if tieu_de == noi_dung else f"{tieu_de}\n{noi_dung}").strip()
            )
        # `so_ky_hieu` và `loai_van_ban` lấy của dòng đầu nhóm — nhóm nay khoá theo
        # `document_id` nên MỌI dòng trong nhóm chắc chắn cùng một văn bản, cùng một
        # số hiệu, cùng một loại (JOIN documents trong `expand._SQL_PROV`). Rỗng/NULL
        # ⇒ "không rõ", không bịa một loại để model áp thứ bậc lên thứ ta không biết.
        dau = cac_p[0]
        loai = dau.get("loai_van_ban") or "không rõ"
        khoi.append(f"VĂN BẢN so_ky_hieu={dau['so_ky_hieu']} loai_van_ban={loai}\n\n"
                    + "\n\n".join(than))
    return "\n\n---\n\n".join(khoi)


def generate_claims(state: dict, llm, model: str) -> dict:
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

    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(cau_hoi=state["query"], context=build_context(expanded))
    raw, usage = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=CLAIMS_SCHEMA)
    try:
        data = json.loads(raw)
        claims = [Claim(**c) for c in data.get("claims", [])]
        insufficient = bool(data.get("insufficient_evidence"))
        schema_error = False
    except (json.JSONDecodeError, TypeError, ValueError):
        claims, insufficient, schema_error = [], True, True

    return {
        **state,
        "draft_claims": claims,
        "insufficient_evidence": insufficient,
        "schema_error": schema_error,
        "traces": {
            **prior_traces,
            "claims_raw": len(claims),
            "token_in": usage.token_in,
            "token_out": usage.token_out,
            "cost_usd": usage.cost_usd,
        },
    }
