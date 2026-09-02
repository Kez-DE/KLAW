"""Verify tầng 2 — LLM judge, CHỈ cho claim ĐÃ QUA tầng 1.

Tầng 1 (Task 5) đã bảo đảm bằng TRA BẢNG: điều luật tồn tại, nằm trong tập đã
truy hồi, quote NGUYÊN VĂN khớp một dòng của nó. Việc còn lại là câu hỏi NGỮ
NGHĨA mà tra bảng không trả lời được: đoạn luật đó có THẬT SỰ chống đỡ khẳng
định hay chỉ liên quan bề mặt? Một quote nguyên văn hoàn toàn có thể được dùng
để chống đỡ một khẳng định nó không hề nói — đó là việc CỦA tầng này. Đừng lặp
lại bốn phép kiểm của tầng 1 ở đây: chúng đã xong với 0 token.

Model PHẢI khác họ với generate (spec 7b.2, xem `src.services.llm.judge_model`):
LLM-as-judge có self-preference bias — mô hình đánh giá cao chính đầu ra của họ
mình — nên cùng một họ ở cả hai vai biến tầng 2 thành một sự yên tâm giả. Hàm ở
đây KHÔNG tự gọi `judge_model()`: `model` là tham số, để caller (và ablation cố
ý phá ràng buộc để ĐO bias) toàn quyền quyết định model nào được dùng, và để
tầng này ghi lại ĐÚNG cái đã dùng, không phải cái LẼ RA nên dùng.

Batch THẬT: mọi claim gửi trong MỘT request (một mảng "pairs", một lần
`llm.chat`), không lặp gọi từng claim. Khớp verdict với claim bằng
`claim_index` TRA TỪ ĐIỂN, không bằng vị trí mảng trả về: nếu judge trả verdict
không theo đúng thứ tự gửi — hoàn toàn có thể xảy ra — ghép theo VỊ TRÍ sẽ âm
thầm gán phán quyết của claim A cho claim B, và không phép kiểm hạ nguồn nào
bắt được (xem `test_hoan_vi_thu_tu_van_gan_dung_claim_index`).

Mặc định an toàn: JSON hỏng, verdict thiếu, hoặc một mục verdict dị dạng đều
→ `supported=False` cho (các) claim liên quan, không phải `True` — prompt cũng
quy tắc "mặc định false khi không chắc", im lặng của judge không phải đồng ý.
Nhưng lỗi HẠ TẦNG (mạng, `LlmClient` raise vì response thiếu `usage`) KHÔNG
được nuốt chung với "judge trả JSON hỏng": chỉ những gì bắt nguồn từ chính nội
dung JSON của judge mới rơi vào nhánh mặc định false; lỗi hạ tầng phải nổ ra để
hiện ra, không được biến thành một hàng số liệu trông như đã kiểm chứng.

`verify_tier2` giữ ĐÚNG chữ ký của brief (trả `list[Tier2Verdict]`, không kèm
traces) — test hợp đồng của brief gọi thẳng nó. `verify_tier2_and_trace` là
phần mở rộng NGOÀI BRIEF: dùng lại đúng MỘT lần gọi LLM đó (không gọi hai lần),
nhưng trả thêm `traces` ghi Usage THẬT (Task 3) và CẢ HAI tên model, để khoá
luận chứng minh được generate/judge khác họ bằng số liệu chứ không chỉ tuyên bố
suông. Khoá đặt tên `tier2_*` — KHÔNG dùng `token_in`/`token_out`/`cost_usd`
trần mà `generate_claims` đã chiếm: quy ước gộp `traces` giữa nhiều node còn
CHƯA CHỐT (Task 4 note, chờ Task 10 nối thành một hàng INSERT vào bảng
`traces`), và hiện mỗi node GHI ĐÈ đúng field của mình chứ không cộng dồn —
dùng chung khoá trần sẽ làm node chạy sau xoá mất số liệu của node chạy trước,
đúng lúc pipeline có HAI vai LLM khác nhau (generate và judge) cùng ghi.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from src.agents.nodes.verify_tier1 import Tier1Result
from src.services.llm import Usage, generate_model

logger = logging.getLogger(__name__)

PROMPT_PATH = Path("prompts/verify_tier2.v1.md")

VERDICTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdicts"],
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim_index", "supported", "reason"],
                "properties": {
                    "claim_index": {"type": "integer"},
                    "supported": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
            },
        },
    },
}


@dataclass(frozen=True)
class Tier2Verdict:
    claim_index: int
    supported: bool
    reason: str


def _dieu_luat_cho_judge(r: Tier1Result, db_provisions: dict[int, dict]) -> str:
    """Văn bản điều luật đưa cho judge — ĐÚNG DÒNG quote đã khớp (`khop_tai`),
    KHÔNG PHẢI nguyên văn `claim.provision_id`.

    Task 5 đo: 73,6% số Điều có `noi_dung` CHỈ LÀ TIÊU ĐỀ, thân nằm ở Khoản/Điểm
    con — đúng nơi `khop_tai` trỏ tới. Tra theo `claim.provision_id` trong các
    ca đó đưa cho judge một tiêu đề RỖNG NỘI DUNG, judge không còn gì để chấm.
    Khi `khop_tai` khác `provision_id` (quote nằm ở con), nối thêm dòng của
    điều được dẫn làm ngữ cảnh — nhưng CHỈ dòng đó, không gộp cả cây con: judge
    cần thấy quote khớp ở ĐÚNG DÒNG nào, đúng tinh thần so-từng-dòng của tầng 1.
    """
    def _dong(pid: int) -> str:
        # Judge chấm một khẳng định dựa trên điều luật RỖNG sẽ trả verdict vô
        # nghĩa mà vẫn được tin dùng — tệ hơn không gọi judge. Id thiếu là bất
        # biến vỡ, phải nổ chứ không âm thầm đưa "(?) " cho mô hình.
        if pid not in db_provisions:
            raise KeyError(f"db_provisions thiếu provisions.id={pid} cần cho judge — bất biến vỡ")
        p = db_provisions[pid]
        return f"({p.get('duong_dan', '?')}) {p.get('noi_dung', '')}"

    dong = _dong(r.khop_tai if r.khop_tai is not None else r.claim.provision_id)
    if r.khop_tai is None or r.khop_tai == r.claim.provision_id:
        return dong
    tieu_de = _dong(r.claim.provision_id)
    return f"{tieu_de}\n{dong}"


def _build_prompt(qua: list[Tier1Result], db_provisions: dict[int, dict]) -> str:
    pairs = [
        f"claim_index={pos}\nKHẲNG ĐỊNH: {r.claim.text}\nĐIỀU LUẬT: {_dieu_luat_cho_judge(r, db_provisions)}"
        for pos, r in enumerate(qua)
    ]
    return PROMPT_PATH.read_text(encoding="utf-8").format(pairs="\n\n---\n\n".join(pairs))


def _parse_verdicts(raw: str) -> dict[int, dict]:
    """`claim_index` → verdict thô, tra được dù judge trả sai thứ tự.

    Chỉ lỗi bắt nguồn từ JSON của CHÍNH judge mới bị nuốt ở đây — mặc định trả
    rỗng khiến MỌI claim rơi vào nhánh "thiếu verdict" ở `_run_judge`, không
    phải raise. Một mục dị dạng trong mảng KHÔNG được kéo cả batch về rỗng —
    chỉ mục đó bị bỏ qua, các mục hợp lệ khác vẫn dùng được (yêu cầu #3: 'batch
    lỗi giữa chừng' khác với 'toàn bộ JSON hỏng').
    """
    try:
        data = json.loads(raw)
        mang = data.get("verdicts") if isinstance(data, dict) else None
        if not isinstance(mang, list):
            raise ValueError("thiếu mảng 'verdicts' hợp lệ")
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("tầng 2: JSON từ judge hỏng (%s) — toàn bộ batch mặc định supported=False: %r", e, raw[:200])
        return {}

    got: dict[int, dict] = {}
    for item in mang:
        idx = item.get("claim_index") if isinstance(item, dict) else None
        if not isinstance(idx, int):
            logger.warning("tầng 2: một verdict dị dạng bị bỏ qua (thiếu claim_index hợp lệ): %r", item)
            continue
        got[idx] = item
    return got


def _run_judge(
    tier1: list[Tier1Result], db_provisions: dict[int, dict], llm, model: str
) -> tuple[list[Tier2Verdict], Usage | None]:
    qua = [r for r in tier1 if r.ok]
    if not qua:
        return [], None

    prompt = _build_prompt(qua, db_provisions)
    # KHÔNG try/except quanh lời gọi này: lỗi hạ tầng (mạng, LlmClient raise vì
    # thiếu 'usage') phải nổ, không bị nuốt chung với "judge trả JSON hỏng".
    raw, usage = llm.chat(model, [{"role": "user", "content": prompt}], json_schema=VERDICTS_SCHEMA)
    got = _parse_verdicts(raw)

    out: list[Tier2Verdict] = []
    for pos in range(len(qua)):
        v = got.get(pos)
        if v is None:
            logger.warning("tầng 2: claim_index=%d không có verdict từ judge — mặc định supported=False", pos)
        supported = v.get("supported") is True if v else False
        reason = v.get("reason") if v and isinstance(v.get("reason"), str) else None
        out.append(Tier2Verdict(pos, supported, reason or "judge không trả verdict hợp lệ → mặc định không hỗ trợ"))
    return out, usage


def verify_tier2(tier1: list[Tier1Result], db_provisions: dict[int, dict], llm, model: str) -> list[Tier2Verdict]:
    """Batch mọi claim ĐÃ QUA tầng 1 vào MỘT lời gọi judge. Xem docstring module."""
    verdicts, _usage = _run_judge(tier1, db_provisions, llm, model)
    return verdicts


def verify_tier2_and_trace(
    tier1: list[Tier1Result],
    db_provisions: dict[int, dict],
    llm,
    model: str,
    prior_traces: dict | None = None,
) -> tuple[list[Tier2Verdict], dict]:
    """Như `verify_tier2`, cộng `traces` (Global Constraint) ghi Usage THẬT và
    CẢ HAI tên model — xem docstring module về khoá `tier2_*`."""
    verdicts, usage = _run_judge(tier1, db_provisions, llm, model)
    traces = {
        **(prior_traces or {}),
        # Điều kiện theo `usage`, giống ba khoá bên dưới — KHÔNG vô điều kiện:
        # `usage is None` nghĩa là `_run_judge` không hề gọi LLM (qua_t1 rỗng).
        # Hai cột này là BẰNG CHỨNG "judge đã chạy trên request thật" (docstring
        # routes.py) — ghi tên model khi chưa judge biến "chưa judge" thành
        # "đã judge" trong số liệu (silent-failure review, sau task-10).
        "tier2_generate_model": generate_model() if usage else None,
        "tier2_judge_model": model if usage else None,
        "tier2_token_in": usage.token_in if usage else 0,
        "tier2_token_out": usage.token_out if usage else 0,
        "tier2_cost_usd": usage.cost_usd if usage else 0.0,
    }
    return verdicts, traces
