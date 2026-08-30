"""Node assemble — quyết định một trong BỐN loại kết quả (spec 6.2). Đây là nơi
mọi thứ hội tụ thành câu trả lời người dùng đọc, và là nơi lời hứa của khoá
luận (nguồn gốc + nguyên văn, KHÔNG bảo đảm là bản hiện hành) hiện ra hoặc bị
phản bội.

answer            : có claim qua cả hai tầng, tỉ lệ verified ≥ ngưỡng
partial_coverage  : chỉ trúng tầng nông → nêu luật, KHÔNG diễn giải. 0 TOKEN
abstain           : không đủ căn cứ. HÀNH VI ĐÚNG, không phải lỗi
out_of_scope      : route xác định ngoài phạm vi. 0 TOKEN

`intent == soan_thao` KHÔNG có nhánh riêng — nó rơi vào đúng pipeline
tra_cuu-shaped bên dưới (chỉ `ngoai_pham_vi` mới lập tức ra out_of_scope):
coverage_note của out_of_scope tự nói "soạn thảo chỉ trong lĩnh vực lao động",
nghĩa là soạn thảo vẫn cần câu trả lời được neo bằng trích dẫn đã kiểm chứng
giống hệt tra cứu, không phải một tính năng tách rời.

Cảnh báo hiệu lực PHẢI chịu tải: Plan 1 đo được cả 6 nghị định lương tối thiểu
liên quan trên MOJ chỉ có PDF scan (`hasContent: false`), và MOJ tự đánh 4/6
nghị định đã bị thay thế là "còn hiệu lực". Task 2 sửa được cả 4 và
`Effectivity.ly_do` nêu đích danh văn bản thay thế — nên khi verdict rơi vào
`CANH_BAO`, nguyên văn `ly_do` phải lên tới người dùng, không phải chỉ nằm
trong traces.
"""

import json
import logging
from enum import StrEnum
from pathlib import Path
from typing import TypedDict

from src.services.effectivity import EffectivityVerdict as V
from src.services.llm import Usage

logger = logging.getLogger(__name__)

PROMPT_PATH = Path("prompts/assemble.v1.md")

ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer"],
    "properties": {"answer": {"type": "string"}},
}

# Khớp mặc định của Settings.abstain_threshold (src/config.py) — GIẢ ĐỊNH cần
# xác nhận, KHÔNG được tinh chỉnh trên tập báo cáo (chỉ trên tập dev tách
# riêng). state["abstain_threshold"] ghi đè được cho graph thật; hằng số này
# chỉ là fallback khi state không mang nó (vd. gọi assemble() đơn lẻ).
ABSTAIN_THRESHOLD_DEFAULT = 0.5

# Ba verdict brief đòi hỏi tường minh (bi_thay_the/het_hieu_luc/mot_phan_khong_xac_dinh)
# cộng chua_hieu_luc (chưa có hiệu lực — người hỏi cần biết) và can_doi_chieu_tay
# (nghi lỗi dữ liệu MOJ). KHÔNG gồm con_hieu_luc (đúng nghĩa không cảnh báo) hay
# chua_xac_dinh (xem CONCERN trong report — brief không liệt kê, giữ đúng brief).
CANH_BAO = {
    V.mot_phan_khong_xac_dinh:
        "Văn bản này hết hiệu lực một phần. Cơ sở dữ liệu quốc gia không công bố "
        "dữ liệu bãi bỏ cấp điều khoản, nên không xác định được điều luật này còn "
        "hiệu lực hay không.",
    V.bi_thay_the: "Văn bản này đã bị thay thế.",
    V.het_hieu_luc: "Văn bản này đã hết hiệu lực.",
    V.chua_hieu_luc: "Văn bản này chưa có hiệu lực.",
    V.can_doi_chieu_tay:
        "Trạng thái hiệu lực của văn bản này không xác định được tự động, cần đối chiếu tay.",
}


class ResultType(StrEnum):
    answer = "answer"
    partial_coverage = "partial_coverage"
    abstain = "abstain"
    out_of_scope = "out_of_scope"


class Citation(TypedDict):
    """Dict thường (TypedDict chỉ để gõ kiểu) — test tra bằng `c["so_ky_hieu"]`."""

    provision_id: int
    duong_dan: str
    bo_luat: str
    so_ky_hieu: str
    quote: str
    hieu_luc: str | None
    tin_cay: str | None


def _base(state: dict, rt: ResultType, usage: Usage | None = None, degraded: bool = False, **kw: object) -> dict:
    """Khung chung cho cả bốn loại kết quả — MỌI nhánh đều ghi `traces`
    (Global Constraint), kể cả ba nhánh 0 token: `assemble_token_*=0` không chỉ
    là giá trị mặc định, nó là BẰNG CHỨNG đo được cho tuyên bố "0 TOKEN" trong
    docstring module, không phải một lời khẳng định suông.
    """
    prior_traces = state.get("traces") or {}
    return {
        **state,
        "result_type": rt,
        "answer": None,
        "citations": [],
        "warnings": [],
        "coverage_note": None,
        "traces": {
            **prior_traces,
            "assemble_result_type": rt.value,
            "assemble_degraded": degraded,
            "assemble_token_in": usage.token_in if usage else 0,
            "assemble_token_out": usage.token_out if usage else 0,
            "assemble_cost_usd": usage.cost_usd if usage else 0.0,
        },
        **kw,
    }


def assemble(state: dict, db_provisions: dict[int, dict], llm, model: str) -> dict:
    if state.get("intent") == "ngoai_pham_vi":
        return _base(
            state, ResultType.out_of_scope,
            coverage_note="Câu hỏi ngoài phạm vi hệ thống: 6 Bộ luật của Việt Nam; "
                          "soạn thảo chỉ trong lĩnh vực lao động.",
        )

    deep = state.get("expanded") or []
    shallow = state.get("hits_shallow") or []

    # PARTIAL_COVERAGE — nhánh xác định, KHÔNG gọi LLM: chỉ trúng tầng nông thì
    # nêu luật liên quan chứ không được diễn giải nội dung chưa được kiểm chứng.
    if not deep and shallow:
        luat = sorted({f"{p['so_ky_hieu']} ({p.get('ten') or ''})".strip() for p in shallow})
        dieu = ", ".join(p["duong_dan"] for p in shallow[:3])
        return _base(state, ResultType.partial_coverage, coverage_note=(
            f"Câu hỏi thuộc {'; '.join(luat)} — liên quan {dieu}. "
            "KLAW phủ sâu 6 Bộ luật và các văn bản hướng dẫn về lao động; "
            "chưa phủ nghị định/thông tư hướng dẫn lĩnh vực này nên không diễn giải chi tiết."
        ))

    if state.get("insufficient_evidence"):
        return _base(state, ResultType.abstain)

    tier1 = state.get("tier1") or []
    tier2 = {v.claim_index: v for v in (state.get("tier2") or [])}
    qua_t1 = [r for r in tier1 if r.ok]

    if not tier1 or not qua_t1:
        return _base(state, ResultType.abstain)

    # Khớp tier2 theo VỊ TRÍ trong qua_t1 (claim_index của Tier2Verdict được đánh
    # số lại từ 0 trên chính tập đã qua tầng 1 — xem verify_tier2._build_prompt).
    # Thiếu verdict cho một vị trí ⇒ KHÔNG verified, vô điều kiện — không có
    # nhánh "tier2 rỗng toàn bộ thì coi như đã qua": verify_tier2 luôn trả đúng
    # len(qua_t1) verdict khi qua_t1 khác rỗng (kể cả lỗi JSON, nó default
    # supported=False chứ không trả rỗng), nên tier2 rỗng trong khi qua_t1 khác
    # rỗng chỉ có thể là caller quên nối tầng 2 — mặc định "coi như supported"
    # ở đúng chỗ đó sẽ âm thầm bỏ qua tầng 2 cho toàn bộ batch, ngược hẳn quy tắc
    # "mặc định false khi không chắc" mà verify_tier2 đã lập.
    verified = [r for pos, r in enumerate(qua_t1) if (v := tier2.get(pos)) is not None and v.supported]
    ty_le = len(verified) / len(tier1)
    if not verified or ty_le < float(state.get("abstain_threshold", ABSTAIN_THRESHOLD_DEFAULT)):
        return _base(state, ResultType.abstain)

    citations: list[Citation] = []
    warnings: list[str] = []
    for r in verified:
        # `khop_tai` là dòng THẬT chứa quote — có thể là Khoản con của
        # claim.provision_id (73,6% số Điều chỉ có tiêu đề, xem verify_tier1.py
        # `_cay_con`). Hiển thị theo khop_tai để duong_dan trỏ đúng dòng có nội
        # dung; provision_id trong citation vẫn giữ nguyên claim.provision_id vì
        # đó mới là điều luật claim THỰC SỰ dẫn — chỉ màn hiển thị đổi, không
        # đổi cái được neo. Rơi về claim.provision_id khi khop_tai vắng (None,
        # hoặc trỏ tới id không có trong db_provisions) để không hiển thị citation
        # rỗng trường.
        khop_tai = r.khop_tai
        row_id = khop_tai if khop_tai is not None and khop_tai in db_provisions else r.claim.provision_id
        p = db_provisions.get(row_id, {})
        eff = r.effectivity
        citations.append({
            "provision_id": r.claim.provision_id,
            "duong_dan": p.get("duong_dan", ""),
            "bo_luat": p.get("ten", ""),
            "so_ky_hieu": p.get("so_ky_hieu", ""),
            "quote": r.claim.quote,
            "hieu_luc": eff.verdict.value if eff else None,
            "tin_cay": eff.tin_cay if eff else None,
        })
        if eff and eff.verdict in CANH_BAO:
            msg = f"{p.get('so_ky_hieu', '')}: {CANH_BAO[eff.verdict]}"
            if msg not in warnings:
                warnings.append(msg)

    claims_txt = "\n".join(f"- {r.claim.text}" for r in verified)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(cau_hoi=state.get("query", ""), claims=claims_txt)
    usage: Usage | None = None
    degraded = False
    try:
        raw, usage = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=ANSWER_SCHEMA)
        answer = json.loads(raw)["answer"]
    except Exception as e:
        # Suy biến AN TOÀN, không phải lỗi im lặng: nội dung fallback là chính
        # các claim ĐÃ qua cả hai tầng verify, nên không phải rủi ro ảo giác —
        # chỉ kém trau chuốt hơn. Khác `route.py` (lỗi hạ tầng phải nổ vì đó là
        # quyết định định tuyến): đây là bước hành văn CUỐI CÙNG, không còn
        # quyết định hạ nguồn nào phụ thuộc vào nó. Vẫn ĐẾM qua traces/log —
        # không được vô hình, cùng khuôn rewrite_query.py.
        logger.warning(
            "assemble: lỗi khi gọi LLM hành văn (%s: %s) — fallback nối các claim đã kiểm chứng, "
            "không bịa câu trả lời",
            type(e).__name__, e,
        )
        answer = " ".join(r.claim.text for r in verified)
        degraded = True

    return _base(state, ResultType.answer, usage=usage, degraded=degraded,
                 answer=answer, citations=citations, warnings=warnings)
