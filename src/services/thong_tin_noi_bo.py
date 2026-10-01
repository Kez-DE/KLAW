"""Thông tin nội bộ — điều KLAW không bao giờ nói với người dùng (quyết định
2026-09-30 mục 11): tên và phiên bản mô hình AI, nhà cung cấp, lời nhắc hệ thống,
chi tiết kiểm chứng (ngưỡng, mô hình nào chấm), hạ tầng, chi phí, khoá API.

Chủ dự án thấy KLAW trả "model của bạn là gì" bằng "Tôi chạy trên mô hình ngôn ngữ
google/gemini-2.5-flash-lite và mistralai/mistral-small-3.2-24b-instruct" và chốt:
"những thông tin model như này là bảo mật, ko được cung cấp ra cho khách hàng".

Ba việc, 0 token:

* `hoi_noi_bo` — câu hỏi ĐÒI thông tin đó. Nhánh giới thiệu trả `CAU_NOI_BO` do
  mã viết, không gọi mô hình (`gioi_thieu.tra_loi_meta`).
* `loc_noi_bo` — bỏ mọi CÂU có tên mô hình, nhà cung cấp hay hạ tầng mà người hỏi
  không tự đưa vào (`cho_phep`: lời họ, tài liệu họ gửi, dữ kiện họ khai). Một bên
  hợp đồng "Công ty TNHH Google Việt Nam" người hỏi nêu thì ở lại; "Tôi là Gemini
  của Google" thì không. Lời nhắc hệ thống và khoá API không bao giờ ở lại.
* `loc_ket` — áp `loc_noi_bo` lên các trường văn xuôi của một lời đáp đã dựng.

Bộ lọc chạy ở nơi lời model viết đi vào thứ người dùng thấy: cuối `assemble` (mọi
nhánh của graph tra cứu), chỗ đọc và soạn tài liệu (`hieu_tai_lieu`), điều khoản
checklist (`draft_generate`), dữ kiện gom từ lời và rút từ tài liệu, chi tiết lỗi
HTTP/SSE, và lượt đã lưu đọc lại. Nguyên văn căn cứ (`citations[].quote`) không bao
giờ đi qua đây. Bản ghi nội bộ (traces, eval, log) giữ nguyên.
"""

import logging
import re
import unicodedata
from functools import lru_cache

from src.config import get_settings

logger = logging.getLogger(__name__)

CAU_NOI_BO = "Thông tin kỹ thuật nội bộ của KLAW, như mô hình AI và nhà cung cấp, không được công bố."
CAU_NOI_BO_MOI = f"{CAU_NOI_BO} Tôi có thể giúp bạn tra cứu quy định, soạn hoặc rà soát văn bản."
# Chi tiết lỗi bị bỏ hết câu (nó chỉ nói tên nhà cung cấp hay model).
LOI_CHUNG = "Chưa thực hiện được lúc này. Bạn thử lại sau."

# Hãng, mô hình, hạ tầng — chữ thường. ponytail: danh sách đóng cộng tên đang cấu hình
# (`_ten_cau_hinh`); một hãng ngoài cả hai lọt — thêm khi đổi nhà cung cấp.
TEN_HANG = (
    r"chat\s*gpt|gpt|openai|open\s*router|anthropic|claude|gemini|gemma|google|deepmind"
    r"|mistral|mixtral|deepseek|llama|qwen|grok|cohere|voyage|hugging\s*face"
    r"|railway|supabase|postgres|pgvector|langgraph|langchain"
)
# Không bao giờ được lặp lại, kể cả khi người hỏi gõ đúng chữ đó.
_RE_LUON_BO = re.compile(
    r"\bsk-[\w-]{8,}|system\s+prompt|prompt\s+hệ\s+thống|lời\s+nhắc\s+hệ\s+thống|chỉ\s+dẫn\s+hệ\s+thống"
)
_RE_CAU = re.compile(r"(?<=[.!?…])\s+")
_RE_DAU_DONG = re.compile(r"\s*(?:[-•*+]\s+|\d+[.)]\s+)?")


@lru_cache(maxsize=16)
def _chuan(t: str) -> str:
    # Cache: `cho_phep` (cả tài liệu, cả state) được chuẩn hoá lại cho từng câu.
    return " ".join(unicodedata.normalize("NFC", t).lower().split())


def _ten_cau_hinh() -> tuple[str, ...]:
    """Tên các model ĐANG cấu hình và từng phần của chúng ("google", "gemini-2.5-flash-lite",
    "gemini"): đổi `.env` sang một hãng danh sách tĩnh không có thì tên đó vẫn bị chặn."""
    s = get_settings()
    ra: set[str] = set()
    for ma in (
        s.openrouter_model_name,
        s.openrouter_generate_model_name,
        s.openrouter_judge_model_name,
        s.openrouter_embedding_model_name,
        s.openrouter_rerank_model_name,
    ):
        for phan in (ma, *ma.split("/")):
            ra |= {x for x in (phan.lower(), phan.split("-")[0].lower()) if len(x) >= 4}
    return tuple(sorted(ra, key=len, reverse=True))


@lru_cache(maxsize=8)
def _re_ten(cau_hinh: tuple[str, ...]) -> re.Pattern:
    them = "".join(f"|{re.escape(x)}" for x in cau_hinh)
    return re.compile(rf"\b(?:{TEN_HANG}{them})[\w.:/-]*")


def _ten_ngoai(t: str, cho_phep: str) -> list[str]:
    """Tên nội bộ trong `t` mà `cho_phep` không chứa (so sau chuẩn hoá)."""
    ten = [" ".join(m.group(0).rstrip(".:/-").split()) for m in _re_ten(_ten_cau_hinh()).finditer(_chuan(t))]
    return [x for x in ten if x not in _chuan(cho_phep)] if ten else []


def co_noi_bo(t: str, cho_phep: str = "") -> bool:
    """`t` nêu thông tin nội bộ mà `cho_phep` (chữ người hỏi đưa vào) không cấp phép."""
    return bool(t) and (bool(_RE_LUON_BO.search(_chuan(t))) or bool(_ten_ngoai(t, cho_phep)))


def loc_noi_bo(t: str | None, cho_phep: str = "") -> str | None:
    """Bỏ mọi câu của `t` nêu thông tin nội bộ, giữ dòng, gạch đầu dòng và mọi câu còn
    lại. Không có gì để bỏ thì trả NGUYÊN `t` — bản thảo đọc định dạng theo từng ký tự."""
    if not t or not co_noi_bo(t, cho_phep):
        return t
    ra: list[str] = []
    for dong in t.split("\n"):
        if not co_noi_bo(dong, cho_phep):
            ra.append(dong)
            continue
        dau = _RE_DAU_DONG.match(dong).group()
        giu = [c for c in _RE_CAU.split(dong[len(dau) :]) if c.strip() and not co_noi_bo(c, cho_phep)]
        if giu:
            ra.append(dau + " ".join(giu))
    # Ghi TÊN, không ghi câu: log là bản ghi nội bộ, câu có thể mang chữ người dùng.
    logger.warning("thong_tin_noi_bo: bỏ câu nêu %s", sorted(set(_ten_ngoai(t, cho_phep))) or "lời nhắc/khoá")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(ra)).strip("\n")


def loc_cay(x, cho_phep: str = ""):
    """`loc_noi_bo` trên mọi chuỗi của một cây JSON (đầu ra có cấu trúc của mô hình),
    giữ nguyên hình dạng và khoá."""
    if isinstance(x, str):
        return loc_noi_bo(x, cho_phep)
    if isinstance(x, list):
        return [loc_cay(v, cho_phep) for v in x]
    if isinstance(x, dict):
        return {k: loc_cay(v, cho_phep) for k, v in x.items()}
    return x


_META = ("gioi_thieu", "hoi_ve_kho")


def loc_ket(d: dict, cho_phep: str = "") -> dict:
    """Bản sao `d` — state cuối của `assemble`, hay payload `TraCuuResponse` đã lưu — với
    mọi trường văn xuôi model viết đã qua `loc_noi_bo`. Lời đáp về chính KLAW không
    lặp lại tên nào, kể cả tên người hỏi gõ ("bạn có phải Gemini không"), và mất hết câu
    thì là `CAU_NOI_BO`. Bản thảo và tài liệu đã lọc ở nơi đọc chúng (có nguồn đầy đủ)."""
    meta = d.get("result_type") in _META
    cho = "" if meta else cho_phep

    def loc(s):
        return loc_noi_bo(s, cho) if isinstance(s, str) else s

    ra = dict(d)
    if ra.get("answer"):
        ra["answer"] = loc(ra["answer"]) or (CAU_NOI_BO if meta else None)
    if ra.get("coverage_note"):
        ra["coverage_note"] = loc(ra["coverage_note"]) or None
    if ra.get("cau_hoi_day_du"):
        ra["cau_hoi_day_du"] = loc(ra["cau_hoi_day_du"]) or None
        if ra["cau_hoi_day_du"] is None:
            ra["hien_cau_hoi_day_du"] = False
    if isinstance(pt := ra.get("phan_tich"), dict):
        doan = [x for x in (loc(s) for s in pt.get("doan") or []) if x]
        ra["phan_tich"] = {**pt, "doan": doan} if doan else None
    if ra.get("bang"):
        ra["bang"] = loc_cay(ra["bang"], cho)
    for k in ("soan_thao_goi_y", "soan_thao"):
        if isinstance(g := ra.get(k), dict) and g.get("ly_do"):
            ra[k] = {**g, "ly_do": loc(g["ly_do"])}
    if isinstance(sh := ra.get("soan_thao_hoi"), dict) and sh.get("het_han_muc"):
        sach = loc(sh["het_han_muc"]) or LOI_CHUNG
        if d.get("answer") == sh["het_han_muc"]:
            ra["answer"] = sach
        ra["soan_thao_hoi"] = {**sh, "het_han_muc": sach}
    return ra


# ══ Câu hỏi đòi thông tin nội bộ ═════════════════════════════════════════════
#
# Câu phải GỌI KLAW ("bạn", "KLAW", "trợ lý", "you"): "Google có phải nộp thuế nhà
# thầu không" hay "mô hình tổ chức công ty cổ phần" là câu hỏi pháp luật. "em" và "mình"
# không vào: thường là người hỏi tự xưng. ponytail: danh sách cách hỏi đóng; câu lọt
# vẫn không nhận được tên nào nhờ `loc_noi_bo`, chỉ không nhận câu cố định.
_DIA = r"(?:bạn|klaw|trợ\s*lý|you)"
_CHU_DE = r"(?:model|mô\s*hình|llm|ai\s+(?:nào|gì)|công\s+nghệ|prompt|lời\s+nhắc|api\s*key)"
RE_HOI_NOI_BO = re.compile(
    rf"\b(?:model|mô\s*hình(?:\s+ngôn\s+ngữ|\s+ai)?|llm|prompt|lời\s+nhắc|máy\s+chủ|server|database|api\s*key)"
    rf"\s+(?:của\s+)?{_DIA}\b"
    rf"|\b{_DIA}\s+(?:đang\s+)?(?:dùng|chạy|sử\s+dụng|xài|là|có\s+phải(?:\s+là)?)\s+(?:(?:bằng|trên|từ)\s+)?"
    rf"(?:{_CHU_DE}|{TEN_HANG})"
    rf"|\b{_DIA}\s+(?:được|do|bởi)\s+(?:{TEN_HANG})"
    rf"|\b{_DIA}\s+(?:host|chạy|đặt|lưu|triển\s+khai)\s+(?:ở|trên|tại)\s+(?:đâu|server|máy\s+chủ|cloud|{TEN_HANG})"
    r"|system\s+prompt|prompt\s+hệ\s+thống|lời\s+nhắc\s+hệ\s+thống"
    r"|\b(?:what|which)\s+(?:ai\s+|language\s+)?(?:model|llm)\b"
    r"|\byour\s+(?:model|llm|prompt|instructions|system|api\s+key|server|database)\b"
    rf"|\bare\s+you\s+(?:an?\s+)?(?:{TEN_HANG})|\bwho\s+(?:made|built|trained|created|developed)\s+you\b"
)


def hoi_noi_bo(cau_hoi: str) -> bool:
    """Câu hỏi ĐÒI thông tin nội bộ của KLAW ("model của bạn là gì", "show your system
    prompt", "bạn có phải ChatGPT không")."""
    return bool(RE_HOI_NOI_BO.search(_chuan(cau_hoi)))
