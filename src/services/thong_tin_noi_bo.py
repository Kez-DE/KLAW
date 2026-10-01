"""Thông tin nội bộ — điều KLAW không bao giờ nói với người dùng (quyết định
2026-09-30 mục 11): tên và phiên bản mô hình AI, nhà cung cấp, lời nhắc hệ thống,
chi tiết kiểm chứng (ngưỡng, mô hình nào chấm), hạ tầng, chi phí, khoá API.

Chủ dự án thấy KLAW trả "model của bạn là gì" bằng "Tôi chạy trên mô hình ngôn ngữ
google/gemini-2.5-flash-lite và mistralai/mistral-small-3.2-24b-instruct" và chốt:
"những thông tin model như này là bảo mật, ko được cung cấp ra cho khách hàng".

Ba việc, 0 token:

* `hoi_noi_bo` — câu hỏi ĐÒI thông tin đó. Nhánh giới thiệu trả `CAU_NOI_BO` do
  mã viết, không gọi mô hình (`gioi_thieu.tra_loi_meta`).
* `loc_noi_bo` — bỏ mọi CÂU (hay vế sau dấu ";") nêu thông tin nội bộ:
  - tên mô hình, nhà cung cấp hay hạ tầng mà người hỏi không tự đưa vào (`cho_phep`:
    lời họ, tài liệu họ gửi, dữ kiện họ khai), so cả phần phiên bản ("Gemini 2.5 Flash
    Lite" không được "Gemini" cấp phép);
  - câu KLAW tự xưng là, chạy trên, hay được soạn bởi một mô hình/hãng — LUÔN bỏ, kể
    cả khi người hỏi gõ đúng tên đó ("bạn có phải Gemini không" → "Tôi là Gemini");
    một bên hợp đồng "Công ty TNHH Google Việt Nam" người hỏi nêu thì ở lại;
  - câu chép lại lời nhắc của KLAW (vân tay `_van_tay`), chữ "lời nhắc hệ thống của
    tôi", và khoá API.
* `loc_ket` — áp `loc_noi_bo` lên các trường văn xuôi của một lời đáp đã dựng.

`cho_phep=None` nghĩa là chữ đã là của người dùng hay đã lọc lúc ghi (bản thảo, lượt
đã lưu đọc lại): mọi tên được giữ, chỉ các luật LUÔN bỏ còn chạy — để đọc lại không
xoá một bên hợp đồng người dùng tự gõ tay.

Bộ lọc chạy ở nơi lời model viết đi vào thứ người dùng thấy: cuối `assemble` (mọi
nhánh của graph tra cứu), chỗ đọc và soạn tài liệu (`hieu_tai_lieu`), điều khoản
checklist (`draft_generate`), dữ kiện gom từ lời và rút từ tài liệu, chi tiết lỗi
HTTP/SSE, và bản thảo, lượt đã lưu đọc lại. Nguyên văn căn cứ (`citations[].quote`)
không bao giờ đi qua đây. Bản ghi nội bộ (traces, eval, log) giữ nguyên.
"""

import logging
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from src.config import get_settings

logger = logging.getLogger(__name__)

CAU_NOI_BO = "Thông tin kỹ thuật nội bộ của KLAW, như mô hình AI và nhà cung cấp, không được công bố."
CAU_NOI_BO_MOI = f"{CAU_NOI_BO} Tôi có thể giúp bạn tra cứu quy định, soạn hoặc rà soát văn bản."
# Chi tiết lỗi bị bỏ hết câu (nó chỉ nói tên nhà cung cấp hay model).
LOI_CHUNG = "Chưa thực hiện được lúc này. Bạn thử lại sau."

# Hãng, mô hình, hạ tầng — chữ thường. ponytail: danh sách đóng cộng tên đang cấu hình
# (`_ten_cau_hinh`); một hãng ngoài cả hai lọt — thêm khi đổi nhà cung cấp. Mọi tên ở
# đây đếm được 0 lần trong 113.758 điều khoản của kho (đo 2026-10-01).
TEN_HANG = (
    r"chat\s*gpt|gpt|openai|open\s*router|anthropic|claude|gemini|gemma|google|deepmind"
    r"|mistral|mixtral|deepseek|llama|qwen|grok|cohere|voyage|hugging\s*face"
    r"|copilot|perplexity|moonshot|kimi|minimax|zhipu|glm|nemotron|nvidia|bedrock|vertex\s+ai|azure"
    r"|railway|supabase|postgres|pgvector|vercel|cloudflare|langgraph|langchain"
)
# Phần phiên bản đi sau tên ("Gemini 2.5 Flash Lite", "Claude 3.5 Sonnet").
_DUOI_PHIEN_BAN = (
    r"(?:\s+(?:\d[\w.]*|v\d[\w.]*|pro|flash|lite|mini|nano|ultra|turbo|small|medium|large"
    r"|instruct|sonnet|opus|haiku|thinking|preview|exp|nemo|r1|k2)\b)*"
)

# Khoá API: so trên chữ GỐC, phân biệt hoa thường — "Số hợp đồng: SK-2024-000123" không
# phải khoá. Không bao giờ được lặp lại, kể cả khi người hỏi gõ.
_RE_KHOA = re.compile(r"(?<![A-Za-z0-9])sk-(?:or-v1-|proj-|ant-)[A-Za-z0-9_-]{8,}|(?<![A-Za-z0-9])sk-[A-Za-z0-9]{20,}")
# Chữ "lời nhắc hệ thống": được lặp lại khi người hỏi tự đưa vào (một hợp đồng dịch vụ
# chatbot "bàn giao system prompt cho Bên A"); lời nhắc CỦA KLAW thì không bao giờ.
_RE_LOI_NHAC = re.compile(r"system\s+prompt|prompt\s+hệ\s+thống|lời\s+nhắc\s+hệ\s+thống|chỉ\s+dẫn\s+hệ\s+thống")
_RE_LOI_NHAC_CUA_TOI = re.compile(
    # Không "chỉ dẫn của mình" trần: Luật Thương mại có "thực hiện đúng chỉ dẫn của mình".
    r"(?:system\s+prompt|prompt(?:\s+hệ\s+thống)?|(?:lời\s+nhắc|chỉ\s+dẫn|hướng\s+dẫn)\s+hệ\s+thống)"
    r"\s+(?:của\s+)?(?:tôi|mình|klaw)\b"
    r"|\bmy\s+(?:system\s+)?(?:prompt|instructions)\b|chỉ\s+dẫn\s+(?:mà\s+)?tôi\s+(?:được\s+giao|nhận)"
)
# Lời đáp về chính KLAW (`gioi_thieu`, `hoi_ve_kho`): bảng dữ kiện cũ kể "model khác
# họ đọc lại", "ba model ở ba vai" — mục 11(c) cấm, và bảng hiện tại không có chữ nào ở đây.
_RE_META = re.compile(r"\bmodel\b|\bllm\b|khác\s+họ")
_RE_CAU = re.compile(r"(?<=[.!?…])\s+")
# Vế sau dấu ";" của một câu bị bỏ vì tên hay tự xưng: "Đúng, tôi là Gemini; tranh chấp phải
# qua hòa giải" giữ vế sau. Câu chép lời nhắc thì bỏ cả câu — vế của nó ngắn hơn vân tay.
_RE_VE = re.compile(r"(?<=;)\s+")
_RE_CHU = re.compile(r"[^\W\d_]")
_RE_DAU_DONG = re.compile(r"\s*(?:[-•*+]\s+|\d+[.)]\s+)?")


@lru_cache(maxsize=16)
def _chuan(t: str) -> str:
    # Cache: `cho_phep` (cả tài liệu, cả state) được chuẩn hoá lại cho từng câu.
    return " ".join(unicodedata.normalize("NFC", t).lower().split())


@lru_cache(maxsize=16)
def _gon(t: str) -> str:
    """Bỏ khoảng trắng, gạch nối: "Chat GPT" và "chatgpt", "gemini 2.5" và "gemini-2.5"."""
    return re.sub(r"[\s_-]+", "", _chuan(t))


def _ten_cau_hinh() -> tuple[str, ...]:
    """Tên các model ĐANG cấu hình: cả slug, hãng trước "/", mã model sau "/" — đổi `.env`
    sang một hãng danh sách tĩnh không có thì tên đó vẫn bị chặn. Không tách theo "-":
    "meta-llama/…" sẽ chặn chữ "meta" (và "metadata"), "openai/text-embedding-…" chặn "text"."""
    s = get_settings()
    ra: set[str] = set()
    for ma in (
        s.openrouter_model_name,
        s.openrouter_generate_model_name,
        s.openrouter_judge_model_name,
        s.openrouter_embedding_model_name,
        s.openrouter_rerank_model_name,
    ):
        ra |= {x.lower() for x in (ma, *ma.split("/")) if len(x) >= 4}
    return tuple(sorted(ra, key=len, reverse=True))


@lru_cache(maxsize=8)
def _re_ten(cau_hinh: tuple[str, ...]) -> re.Pattern:
    # Gạch nối trong tên cấu hình khớp cả khoảng trắng: "kimi-k2" bắt "Kimi K2".
    them = "".join("|" + re.escape(x).replace(r"\-", r"[\s-]") for x in cau_hinh)
    return re.compile(rf"\b(?:{TEN_HANG}{them})[\w.:/-]*{_DUOI_PHIEN_BAN}")


def _ten(c: str) -> list[re.Match]:
    return list(_re_ten(_ten_cau_hinh()).finditer(c))


def _ten_ngoai(t: str, cho_phep: str | None) -> list[str]:
    """Tên nội bộ trong `t` mà `cho_phep` không chứa. So TỪNG phần quanh "/" có tên hãng
    ("google/facebook" chỉ xét "google"), cả đuôi phiên bản, sau khi bỏ khoảng trắng."""
    if cho_phep is None:
        return []
    cho, ra = _gon(cho_phep), []
    for m in _ten(_chuan(t)):
        ten = " ".join(m.group(0).rstrip(".:/-").split())
        if any(_re_ten(_ten_cau_hinh()).match(p) and _gon(p) not in cho for p in ten.split("/")):
            ra.append(ten)
    return ra


# ══ Tự xưng — LUÔN bỏ, dù người hỏi gõ đúng tên ═══════════════════════════════
#
# Một tên hãng mà `cho_phep` cấp phép ("Công ty TNHH Google Việt Nam" trong hợp đồng,
# "bạn có phải Gemini không") vẫn không được đứng trong câu KLAW nói nó LÀ, CHẠY TRÊN,
# DÙNG, hay ĐƯỢC SOẠN BỞI mô hình/hãng đó. Xét theo khung chữ quanh tên: `_TRUOC` khớp
# đuôi phần đứng trước tên, `_SAU` khớp đầu phần đứng sau. Tên đứng sau "Công ty", "TNHH"
# là một pháp nhân — bên hợp đồng, không bao giờ là mô hình.
# ponytail: danh sách khung đóng. "tôi" trong một lá đơn là người dùng: "Tôi dùng Google
# Drive để lưu…" trong đơn họ soạn cũng bị bỏ — chấp nhận, hiếm hơn nhiều so với câu tự xưng.

_AI = (
    r"(?:mô\s+hình|model|phiên\s+bản|trợ\s+lý|chatbot|\bai\b|llm|hệ\s+thống|công\s+cụ|trí\s+tuệ\s+nhân\s+tạo"
    r"|assistant|language\s+model|version|system)"
)
_CUM_AI = rf"(?:{_AI}\b[^.!?;\n]{{0,40}}?)?"
_TOI = r"\b(?:tôi|mình|klaw)"
_TRUOC = tuple(
    re.compile(p + r"$")
    for p in (
        # Là: "tôi là Gemini", "đúng, tôi chính là mô hình ngôn ngữ do Google…".
        rf"{_TOI}\s+(?:(?:chính|cũng|đúng|thực\s+ra|vốn|hiện)\s+)?(?:là|chính\s+là)\s+(?:(?:một|1)\s+)?{_CUM_AI}",
        rf"\b(?:i\s+am|i'm|i’m|i\s+was|this\s+is|you\s+are\s+(?:talking|chatting)\s+(?:to|with))\s+(?:(?:a|an|the)\s+)?{_CUM_AI}",
        # Được làm ra bởi: "tôi được phát triển bởi Google", "xây dựng trên mô hình của…".
        rf"{_TOI}\s+(?:(?:được|do)\s+)?(?:\S+\s+)?(?:phát\s+triển|huấn\s+luyện|tạo(?:\s+ra)?|xây\s+dựng|train"
        rf"|thiết\s+kế|làm\s+ra|lập\s+trình|vận\s+hành|cung\s+cấp)\s+(?:bởi|từ|trên|dựa\s+trên|bằng)\s+{_CUM_AI}",
        # Chạy trên / dùng: "tôi chạy trên Gemini", "tôi dùng Claude".
        rf"{_TOI}\s+(?:(?:đang|hiện|chỉ|vẫn)\s+)*(?:chạy|dựa|hoạt\s+động)\s+(?:trên|bằng|vào|nhờ)\s+(?:nền\s+tảng\s+)?{_CUM_AI}",
        rf"{_TOI}\s+(?:(?:đang|hiện|chỉ|vẫn|có)\s+)*(?:dùng|sử\s+dụng|xài)\s+{_CUM_AI}",
        # Việc của KLAW làm bằng mô hình: "tôi đọc tài liệu bằng Gemini qua OpenRouter".
        rf"{_TOI}\s+(?:\S+\s+){{0,2}}?(?:đọc|viết|soạn|trả\s+lời|xử\s+lý|phân\s+tích|tạo|dịch|tóm\s+tắt|kiểm\s+chứng"
        rf"|thẩm\s+định|chấm)\b[^.!?;\n]{{0,40}}?\b(?:bằng|qua|nhờ)\s+{_CUM_AI}",
        rf"\b(?:i|we|klaw)\s+(?:am\s+|was\s+|'m\s+|’m\s+|is\s+)?(?:\S+\s+){{0,2}}?(?:built|made|powered|trained|developed"
        rf"|created|run|running|served|hosted|based|deployed|use|uses|using|rely|relies)\s+"
        rf"(?:(?:on|by|with|through|via|using|upon)\s+)?{_CUM_AI}",
        # Nhãn: "Mô hình AI soạn thảo: Gemini 2.5 Flash Lite".
        r"(?:mô\s+hình|model|\bai\b|llm|công\s+cụ\s+ai|trợ\s+lý\s+ai)[^:\n]{0,30}:\s*",
    )
)
# Khung hai đầu: phần trước như dưới, VÀ phần sau tên khớp `sau`.
_TRUOC_SAU = (
    # "tôi được Google huấn luyện", "tôi do Google phát triển".
    (
        re.compile(rf"{_TOI}\s+(?:\S+\s+){{0,2}}?(?:được|do|bởi)\s+{_CUM_AI}$"),
        re.compile(
            r"^\s*(?:\S+\s+){0,4}?(?:phát\s+triển|huấn\s+luyện|tạo|xây\s+dựng|train|thiết\s+kế|làm\s+ra|lập\s+trình"
            r"|vận\s+hành|cung\s+cấp)"
        ),
    ),
)
# Văn bản này do mô hình soạn: "Điều khoản này do mô hình ngôn ngữ lớn của Google soạn",
# "Bản thảo do Gemini 2.5 Flash Lite soạn qua OpenRouter". Cần một động từ soạn trong câu
# ("Hợp đồng ký bởi Google" không phải), và "bằng/qua" chỉ tính khi có danh từ mô hình hay
# câu nói về chính lời KLAW: "hợp đồng soạn bằng Google Docs vẫn có giá trị" ở lại.
_RE_DO = re.compile(rf"\b(?:do|bởi|by)\s+{_CUM_AI}$|\b(?:bằng|qua|nhờ|via|using|through)\s+{_AI}\b[^.!?;\n]{{0,40}}?$")
_RE_BANG = re.compile(r"\b(?:bằng|qua|nhờ|via|using|through)\s+$")
_RE_LOI_KLAW = re.compile(
    r"câu\s+trả\s+lời|bản\s+thảo|(?:văn\s+bản|điều\s+khoản|phần|câu|nội\s+dung)\s+này"
    r"|this\s+(?:answer|response|draft|text)"
)
_RE_SOAN = re.compile(
    r"\b(?:soạn|viết|tạo|sinh|dịch|tóm\s+tắt|rà\s+soát|chấm|thẩm\s+định|kiểm\s+chứng"
    r"|drafted|written|generated|created|reviewed|produced)"
)
# Tên đứng trước: "Gemini là mô hình tôi dùng", "DeepSeek V3 viết phần này".
_RE_TEN_TRUOC = re.compile(
    r"^[^.!?;\n]{0,40}?\b(?:là\s+(?:mô\s+hình|model|ai|llm)\s+(?:mà\s+)?(?:tôi|klaw|mình)\b"
    r"|(?:mà\s+)?(?:tôi|klaw)\s+(?:đang\s+)?(?:dùng|chạy|sử\s+dụng|xài)\b"
    r"|(?:đã\s+)?(?:soạn|viết|tạo|sinh)(?:\s+ra)?\s+(?:văn\s+bản|câu\s+trả\s+lời|bản\s+thảo|điều\s+khoản|hợp\s+đồng"
    r"|phần|nội\s+dung)\s+này)"
)
_RE_PHAP_NHAN = re.compile(
    r"(?:công\s+ty|cty|tnhh|tập\s+đoàn|chi\s+nhánh|văn\s+phòng\s+đại\s+diện|ngân\s+hàng)\s+(?:[^\s.!?;]+\s+){0,3}$"
)


def _tu_xung(c: str) -> bool:
    """Câu chuẩn hoá `c` có tên hãng/mô hình đứng trong một khung tự xưng hay tác giả."""
    for m in _ten(c):
        truoc, sau = c[max(0, m.start() - 120) : m.start()], c[m.end() :]
        if _RE_PHAP_NHAN.search(truoc):
            continue
        if (
            any(r.search(truoc) for r in _TRUOC)
            or any(a.search(truoc) and b.match(sau) for a, b in _TRUOC_SAU)
            or ((_RE_DO.search(truoc) or (_RE_BANG.search(truoc) and _RE_LOI_KLAW.search(c))) and _RE_SOAN.search(c))
            or _RE_TEN_TRUOC.match(sau)
        ):
            return True
    return False


# ══ Vân tay lời nhắc — câu chép lại lời nhắc của KLAW ═════════════════════════
#
# Cụm 10 từ liền nhau (dấu câu bỏ) của các lời nhắc, trừ cụm cắt qua `{chỗ_điền}`, cụm
# nằm trọn trong ngoặc kép (câu mẫu mô hình được dặn viết), và mọi cụm cũng có trong lời
# nhắc NGOÀI vân tay: lời nhắc định tuyến/viết lại/sinh luận điểm/thẩm định (ví dụ của
# chúng là chữ luật: 11 điều khoản trúng ở n = 10) và lời nhắc viết câu trả lời
# (`assemble.*`, `giai_thich_chung`: ví dụ của chúng là câu trả lời thật — 49 trường của
# lượt đã lưu trúng). Đo 2026-10-01 với cả bộ lọc: 0/113.758
# điều khoản của kho đổi; luật LUÔN bỏ đánh dấu 3/723 lời đáp eval, 1/1.245 trường của
# 324 lượt đã lưu, 0/777 trường của 52 bản thảo, 1/356 câu giới thiệu — tất cả là rò thật
# (eval `trap-soul-09` in nguyên SOUL; "Tôi chạy trên mô hình ngôn ngữ google/gemini-…").
# Mọi dòng ≥ 12 từ của soul.v1–v3 bị bắt (91/91). ponytail: câu chép ngắn hơn 10 từ lọt, và
# lời nhắc ngoài vân tay không được bảo vệ; nhánh giới thiệu tự kiểm thêm lời nhắc của nó
# ở n = 5 (`gioi_thieu._cau_duoc_do`).
_THU_MUC_LOI_NHAC = Path(__file__).resolve().parents[2] / "prompts"
_NGOAI_VAN_TAY = (
    "route",
    "rewrite_query",
    "generate_claims",
    "verify_tier2",
    "assemble",
    "giai_thich_chung",
)
# Không pipeline nào gửi nó (`docs/soul-va-trich-dan-bam-duoc.md`), và nó chép lại SOUL:
# trừ cụm của nó thì mất cả câu mở đầu SOUL — câu `trap-soul-09` in ra.
_KHONG_DUNG = ("klaw_agent_standalone",)
_N_VAN_TAY = 10
_RE_TRICH_MAU = re.compile(r'"[^"]{1,300}"|“[^”]{1,300}”|«[^»]{1,300}»')  # cả câu mẫu xuống dòng


def _tu(t: str) -> list[str]:
    return re.findall(r"\w+", _chuan(t))


@lru_cache(maxsize=8)
def _van_tay(teps: tuple[str, ...], n: int) -> frozenset[tuple[str, ...]]:
    """Mọi cụm `n` từ liền nhau của các lời nhắc `teps`, trừ cụm cắt qua `{chỗ_điền}` và
    cụm nằm trọn trong ngoặc kép."""
    ra: set[tuple[str, ...]] = set()
    for tep in teps:
        t = re.sub(r"\{[^{}]*\}", " \x00 ", unicodedata.normalize("NFC", Path(tep).read_text(encoding="utf-8")))
        tu: list[tuple[str, bool]] = []
        dau = 0
        for m in [*_RE_TRICH_MAU.finditer(t), None]:
            cuoi = m.start() if m else len(t)
            tu += [(w, False) for w in re.findall(r"\w+|\x00", t[dau:cuoi].lower())]
            if m:
                tu += [(w, True) for w in re.findall(r"\w+", m.group().lower())]
                dau = m.end()
        for i in range(len(tu) - n + 1):
            g = tu[i : i + n]
            if not any(w == "\x00" for w, _ in g) and not all(q for _, q in g):
                ra.add(tuple(w for w, _ in g))
    return frozenset(ra)


@lru_cache(maxsize=1)
def _tep_van_tay() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(lời nhắc lấy vân tay, lời nhắc ngoài vân tay)."""
    tep = [p for p in sorted(_THU_MUC_LOI_NHAC.glob("*.md")) if not p.name.startswith(_KHONG_DUNG)]
    return (
        tuple(str(p) for p in tep if not p.name.startswith(_NGOAI_VAN_TAY)),
        tuple(str(p) for p in tep if p.name.startswith(_NGOAI_VAN_TAY)),
    )


@lru_cache(maxsize=1)
def _van_tay_chung() -> frozenset[tuple[str, ...]]:
    """Vân tay `_N_VAN_TAY` từ, TRỪ mọi cụm cũng có trong lời nhắc ngoài vân tay: cụm chung
    với lời nhắc viết câu trả lời là câu mẫu mô hình được dặn viết ("đây là giải thích
    chung, chưa đối chiếu được với điều khoản cụ thể" — SOUL cũng dặn câu đó), cụm chung
    với lời nhắc định tuyến/sinh luận điểm là chữ luật."""
    lay, ngoai = _tep_van_tay()
    return _van_tay(lay, _N_VAN_TAY) - _van_tay(ngoai, _N_VAN_TAY)


@lru_cache(maxsize=16)
def _noi(t: str) -> str:
    return f" {' '.join(_tu(t))} "


def chep_loi_nhac(t: str, teps: tuple[str, ...] | None, n: int = _N_VAN_TAY, cho_phep: str | None = "") -> bool:
    """`t` có một cụm `n` từ của lời nhắc `teps` (None: vân tay chung `_van_tay_chung`) mà
    `cho_phep` không có (người dùng tự trích cụm đó thì được lặp lại)."""
    vt, tu = (_van_tay_chung() if teps is None else _van_tay(teps, n)), _tu(t)
    trung = [g for i in range(len(tu) - n + 1) if (g := tuple(tu[i : i + n])) in vt]
    if not trung or cho_phep is None:
        return bool(trung)
    return any(f" {' '.join(g)} " not in _noi(cho_phep) for g in trung)


def co_noi_bo(t: str, cho_phep: str | None = "", meta: bool = False) -> bool:
    """`t` nêu thông tin nội bộ mà `cho_phep` (chữ người hỏi đưa vào; None = mọi tên là
    của người dùng) không cấp phép. `meta`: lời đáp về chính KLAW, thêm `_RE_META`."""
    if not t:
        return False
    c = _chuan(t)
    return bool(
        _RE_KHOA.search(t)
        or _RE_LOI_NHAC_CUA_TOI.search(c)
        or (cho_phep is not None and (m := _RE_LOI_NHAC.search(c)) and m.group(0) not in _chuan(cho_phep))
        or (meta and _RE_META.search(c))
        or _ten_ngoai(t, cho_phep)
        or _tu_xung(c)
        or chep_loi_nhac(t, None, cho_phep=cho_phep)
    )


def _giu_cau(c: str, cho_phep: str | None, meta: bool) -> list[str]:
    """Phần giữ lại được của câu `c`: cả câu, các vế sạch sau dấu ";", hay không gì."""
    if not co_noi_bo(c, cho_phep, meta):
        return [c]
    if chep_loi_nhac(c, None, cho_phep=cho_phep):
        return []
    return [v for v in _RE_VE.split(c) if v.strip() and not co_noi_bo(v, cho_phep, meta)]


def loc_noi_bo(t: str | None, cho_phep: str | None = "", meta: bool = False) -> str | None:
    """Bỏ mọi câu của `t` nêu thông tin nội bộ, giữ dòng, gạch đầu dòng và mọi câu còn
    lại. Không có gì để bỏ thì trả NGUYÊN `t` — bản thảo đọc định dạng theo từng ký tự."""
    if not t or not co_noi_bo(t, cho_phep, meta):
        return t
    ra: list[str] = []
    for dong in t.split("\n"):
        if not co_noi_bo(dong, cho_phep, meta):
            ra.append(dong)
            continue
        dau = _RE_DAU_DONG.match(dong).group()
        giu = [v for c in _RE_CAU.split(dong[len(dau) :]) if c.strip() for v in _giu_cau(c, cho_phep, meta)]
        # Mảnh không còn chữ nào ("1.", "2.") là số mục của câu vừa bỏ.
        giu = [v for v in giu if _RE_CHU.search(v)]
        if giu:
            ra.append(dau + " ".join(giu))
    # Ghi TÊN, không ghi câu: log là bản ghi nội bộ, câu có thể mang chữ người dùng.
    logger.warning("thong_tin_noi_bo: bỏ câu nêu %s", sorted(set(_ten_ngoai(t, cho_phep))) or "tự xưng/lời nhắc/khoá")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(ra)).strip("\n")


def loc_cay(x, cho_phep: str | None = "", meta: bool = False, giu: frozenset[str] = frozenset()):
    """`loc_noi_bo` trên mọi chuỗi của một cây JSON (đầu ra có cấu trúc của mô hình),
    giữ nguyên hình dạng và khoá. Khoá trong `giu` (nguyên văn tài liệu, dữ kiện người
    dùng khai) đi qua nguyên vẹn."""
    if isinstance(x, str):
        return loc_noi_bo(x, cho_phep, meta)
    if isinstance(x, list):
        return [loc_cay(v, cho_phep, meta, giu) for v in x]
    if isinstance(x, dict):
        return {k: v if k in giu else loc_cay(v, cho_phep, meta, giu) for k, v in x.items()}
    return x


_META = ("gioi_thieu", "hoi_ve_kho")
# Chữ của người dùng trong một lượt đã dựng: câu trích và neo tài liệu của họ, tên tệp, dữ
# kiện họ khai, ô khuôn gốc họ điền.
_GIU = frozenset({"trich", "neo", "neo_a", "neo_b", "du_kien", "ten_tep", "facts", "khuon"})


def loc_ket(d: dict, cho_phep: str | None = "") -> dict:
    """Bản sao `d` — state cuối của `assemble`, hay payload `TraCuuResponse` đã lưu — với
    mọi trường văn xuôi model viết đã qua `loc_noi_bo`. Lời đáp về chính KLAW không
    lặp lại tên nào, kể cả tên người hỏi gõ ("bạn có phải Gemini không"), và mất hết câu
    thì là `CAU_NOI_BO`; một câu trả lời có trích dẫn mất hết câu cũng vậy, thay vì rỗng.
    Phần tài liệu và bản thảo đã lọc ở nơi đọc chúng (có nguồn đầy đủ), nên ở đây chỉ qua
    các luật LUÔN bỏ (`cho_phep=None`) — đủ cho lượt đã lưu trước bản vá."""
    meta = d.get("result_type") in _META
    cho = "" if meta else cho_phep

    def loc(s):
        return loc_noi_bo(s, cho, meta) if isinstance(s, str) else s

    ra = dict(d)
    if ra.get("answer"):
        ra["answer"] = loc(ra["answer"]) or (CAU_NOI_BO if meta or d.get("citations") else None)
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
        ra["bang"] = loc_cay(ra["bang"], cho, meta)
    for k in ("soan_thao_goi_y", "soan_thao"):
        if isinstance(g := ra.get(k), dict) and g.get("ly_do"):
            ra[k] = {**g, "ly_do": loc(g["ly_do"])}
    if isinstance(sh := ra.get("soan_thao_hoi"), dict) and sh.get("het_han_muc"):
        sach = loc(sh["het_han_muc"]) or LOI_CHUNG
        if d.get("answer") == sh["het_han_muc"]:
            ra["answer"] = sach
        ra["soan_thao_hoi"] = {**sh, "het_han_muc": sach}
    for k in ("tai_lieu", "ban_thao"):
        if isinstance(ra.get(k), dict):
            ra[k] = loc_cay(ra[k], None, giu=_GIU)
    return ra


# ══ Câu hỏi đòi thông tin nội bộ ═════════════════════════════════════════════
#
# Câu phải GỌI KLAW ("bạn", "KLAW", "trợ lý", "you", "b", "bn", "mày") và hỏi ĐÚNG thứ
# nội bộ: "Google có phải nộp thuế nhà thầu không", "mô hình tổ chức công ty cổ phần",
# "nếu bạn dùng mô hình hộ kinh doanh" hay "mô hình của bạn tôi là hộ kinh doanh" là câu
# hỏi pháp luật. Viết KHÔNG DẤU và so trên câu đã bỏ dấu, nên "ban dung model gi" và
# "bạn dùng model gì" là một. Danh từ chung (mô hình, công nghệ, nền tảng, server…) phải
# có từ hỏi ngay sau ("mô hình nào", "công nghệ gì"): "nếu bạn sử dụng công nghệ nhận
# diện khuôn mặt để chấm công" là câu hỏi luật. Không "đặt/lưu ở đâu": "biển quảng cáo
# bạn đặt ở đâu", "hồ sơ nhân sự bạn lưu ở đâu" là câu hỏi luật. ponytail: danh sách
# cách hỏi đóng; câu lọt vẫn không nhận được tên nào nhờ `loc_noi_bo`, chỉ không nhận
# câu cố định.
_A = r"(?:ban|bn|b|klaw|tro\s*ly(?:\s+ao)?|may|m|bot|chatbot|you)"
# Từ hỏi. "không", "chưa" còn là phủ định ("nếu hạ tầng của bạn không đạt chuẩn") nên
# chỉ tính khi đứng cuối câu hay trước một liên từ/tiểu từ.
_CUOI = r"(?=\s*(?:[?.,!;:]|$)|\s+(?:va|con|hay|voi|ma|nhe|nha|vay|v|a|ah|ha|nhi|ta|the|nua)\b)"
_HOI = (
    r"(?:\s*\?|\s+(?:gi|j|nao|a|ah|ak|ha|vay|v|dau|sao|nhi|bao\s+nhieu)\b"
    rf"|\s+(?:khong|ko|k|kg|hok|hong|chua)\b{_CUOI})"
)
_TEN_Q = rf"(?:{TEN_HANG})[\w.:/-]*"
_MODEL = r"(?:m[o0]d+e?l+|mdoel|modle|llm)"
_VAT_RIENG = rf"(?:{_MODEL}|{_TEN_Q})(?:\s+[\w.-]+){{0,3}}?{_HOI}"
_VAT_CHUNG = (
    r"(?:mo\s*hinh(?:\s+(?:ngon\s+ngu(?:\s+lon)?|ai))?|ai|tri\s+tue\s+nhan\s+tao|cong\s+nghe(?:\s+ai)?|nen\s+tang"
    r"|database|co\s+so\s+du\s+lieu|server|may\s+chu|api|nha\s+cung\s+cap)\s+(?:nao|gi|j)\b"
)
_VAT_CUA = (
    rf"(?:{_MODEL}|mo\s*hinh(?:\s+(?:ngon\s+ngu(?:\s+lon)?|ai))?|prompt|loi\s+nhac(?:\s+he\s+thong)?"
    r"|chi\s+dan\s+(?:he\s+thong|ban\s+dau)|huong\s+dan\s+(?:he\s+thong|ban\s+dau)|may\s+chu|server|database"
    r"|co\s+so\s+du\s+lieu|api\s*key|khoa\s+api|nha\s+cung\s+cap|ha\s+tang|nen\s+tang|cong\s+nghe|chi\s+phi(?:\s+van\s+hanh)?"
    r"|nguong)"
)
_LAM_RA = r"(?:phat\s+trien|tao(?:\s+ra)?|xay\s+dung|train|huan\s+luyen|lam\s+ra|thiet\s+ke|lap\s+trinh)"
RE_HOI_NOI_BO = re.compile(
    # Model của bạn là gì — không "của bạn tôi/mình/ấy" (bạn của người hỏi).
    rf"\b{_VAT_CUA}\s+(?:cua\s+)?{_A}\b(?!\s+(?:toi|minh|ay|anh|chi|em|be|ta|nay))(?:\s+\S+){{0,3}}?{_HOI}"
    # Bạn dùng model gì / bạn có phải ChatGPT không / KLAW chạy trên nền tảng gì.
    rf"|\b{_A}\s+(?:co\s+)?(?:dang\s+)?(?:dung|xai|chay|su\s+dung|xay\s+dung|dua|la|chinh\s+la|phai(?:\s+la)?|thuoc)"
    rf"\s+(?:(?:bang|tren|tu|voi|vao)\s+)?(?:(?:nhung|cac|loai|mot)\s+)?(?:{_VAT_RIENG}|{_VAT_CHUNG})"
    # Ai làm ra bạn.
    rf"|\b{_A}\s+(?:duoc|do|boi|la\s+(?:san\s+pham\s+)?cua)\s+(?:(?:cong\s+ty|hang|ben|to\s+chuc|nha\s+cung\s+cap)\s+)?(?:nao|ai)(?:\s+(?:{_LAM_RA}|lam)\b|{_CUOI})"
    rf"|\b{_A}\s+(?:duoc|do)\s+(?:\w+\s+){{0,2}}?{_LAM_RA}\s+(?:boi|tu|o)\s+(?:(?:cong\s+ty|hang|ben|to\s+chuc)\s+)?(?:nao|ai|dau|{_TEN_Q})"
    rf"|\b{_A}\s+(?:duoc|do|boi)\s+{_TEN_Q}(?:\s+\S+){{0,3}}?{_HOI}"
    rf"|\bai\s+(?:da\s+)?(?:{_LAM_RA}|so\s+huu|van\s+hanh)\s+(?:ra\s+)?{_A}\b"
    rf"|\b(?:cong\s+ty|hang|ben|to\s+chuc)\s+nao\s+(?:da\s+)?(?:{_LAM_RA}|dung\s+sau|dang\s+sau|cung\s+cap|van\s+hanh)\s+(?:ra\s+)?{_A}\b"
    rf"|\b(?:{_MODEL}|mo\s*hinh(?:\s+ai)?|ai|cong\s+nghe|cong\s+ty|hang)\s+(?:nao|gi)\s+(?:dung\s+sau|dang\s+sau|chay|cung\s+cap|tao\s+ra|nam\s+sau)\s+{_A}\b"
    # Hạ tầng.
    rf"|\b{_A}\s+(?:duoc\s+)?(?:host|hosting|trien\s+khai|deploy|chay)\s+(?:o|tren|tai)\s+(?:dau|server|may\s+chu|cloud|nen\s+tang|{_TEN_Q})"
    rf"|\b(?:du\s+lieu|server|may\s+chu|database|co\s+so\s+du\s+lieu)\s+(?:cua\s+)?{_A}\s+(?:duoc\s+)?(?:dat|luu|host|chay)\s+(?:o|tren|tai)\s+(?:dau|server|may\s+chu|cloud|{_TEN_Q})"
    # Chi phí.
    r"|\b(?:moi|1|mot)\s+(?:cau(?:\s+hoi)?|luot(?:\s+hoi)?|lan\s+hoi|cau\s+tra\s+loi|request)\s+(?:\S+\s+){0,2}?(?:ton|het|mat)\s+(?:bao\s+nhieu|may)"
    r"|\bchi\s+phi\s+(?:cho\s+)?(?:moi|1|mot)\s+(?:cau(?:\s+hoi)?|luot(?:\s+hoi)?|lan\s+hoi|request)"
    rf"|\bton\s+bao\s+nhieu\s+token|\b{_A}\s+(?:ton|het|mat)\s+bao\s+nhieu\s+(?:tien|token)"
    rf"|\bchi\s+phi\s+(?:van\s+hanh|api|token|model|mo\s+hinh)\s+(?:cua\s+)?{_A}\b"
    # Lời nhắc.
    r"|system\s+prompt|prompt\s+he\s+thong|loi\s+nhac\s+he\s+thong|chi\s+dan\s+he\s+thong"
    rf"|\b(?:in|chep|nhac|doc|dua|viet|hien|tiet\s+lo|liet\s+ke|cho\s+(?:toi|minh|tui|em)\s+(?:xem|biet))\s+(?:lai\s+)?(?:ra\s+)?"
    r"(?:nguyen\s+van\s+)?(?:toan\s+bo\s+|het\s+)?(?:cac\s+|nhung\s+)?(?:huong\s+dan|chi\s+dan|loi\s+nhac|prompt|quy\s+tac|chi\s+thi|lenh)"
    rf"\s+(?:he\s+thong|ban\s+dau|goc|duoc\s+giao|(?:ma\s+)?{_A}\s+(?:nhan|duoc|da)|cua\s+{_A}|o\s+tren|phia\s+tren|truoc\s+do)"
    # Kiểm chứng.
    r"|\bnguong\s+(?:kiem\s+chung|tin\s+cay|diem|cham|tham\s+dinh)"
    rf"|\b(?:tang\s+(?:hai|2|mot|1)|kiem\s+chung|tham\s+dinh)\s+(?:do|bang|dung|boi)\s+(?:{_MODEL}|mo\s*hinh|ai|{_TEN_Q})"
    rf"|\b(?:{_MODEL}|mo\s*hinh|ai)\s+(?:nao|gi)\s+(?:cham|kiem\s+chung|tham\s+dinh|kiem\s+tra)"
    # Tiếng Anh.
    r"|\b(?:what|which)\s+(?:ai\s+|language\s+)?(?:model|llm|ai)s?\s+(?:are|do|does|did|is|powers?|runs?|drives?)\s+(?:you|klaw|this|it)\b"
    rf"|\b(?:are\s+you|is\s+(?:this|it|klaw))\s+(?:an?\s+|using\s+|powered\s+by\s+|based\s+on\s+|built\s+(?:on|with)\s+|running\s+on\s+)?{_TEN_Q}"
    r"|\bwho\s+(?:made|built|trained|created|developed|owns|runs|hosts|powers)\s+(?:you|klaw|this)\b"
    r"|\b(?:which|what)\s+(?:company|vendor|provider|firm|lab)\s+(?:made|built|trained|created|developed|powers|runs|hosts|provides|is\s+behind)\s+(?:you|klaw|this)\b"
    r"|\byour\s+(?:ai\s+|model\s+|llm\s+|cloud\s+)?(?:model|llm|provider|vendor|api\s+key|tech(?:nology)?\s+stack)\b"
    r"|\byour\s+(?:system\s+|initial\s+|original\s+|hidden\s+)?(?:prompt|instructions)\b"
    r"|\b(?:print|show|reveal|repeat|output|display|tell\s+me|give\s+me)\s+(?:me\s+)?(?:the\s+)?(?:full\s+|entire\s+|exact\s+|original\s+|initial\s+|hidden\s+)?(?:system\s+)?(?:prompt|instructions)\b"
    r"|\brepeat\s+(?:the\s+)?(?:text|words|everything)\s+above|\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions"
    r"|\bwhere\s+(?:are\s+you|is\s+(?:klaw|this|it))\s+(?:hosted|deployed|running|stored)|\bwhere\s+do\s+you\s+run\b"
    r"|\b(?:what|which)\s+(?:database|server|cloud|infrastructure|hosting)\s+(?:are|do|does|is)\s+(?:you|klaw|this)\b"
    r"|\bhow\s+much\s+(?:does|do|is|will)\s+(?:(?:each|a|one|every|it|this|the)\s+)?(?:query|question|request|answer|call|message|turn|prompt)s?\s+cost"
    r"|\bcost\s+(?:per|of\s+(?:each|a|one))\s+(?:query|question|request|call|answer|token)|\bhow\s+much\s+do\s+you\s+cost"
    r"|\bverification\s+threshold|\bwhich\s+model\s+(?:judges|verifies|checks)"
)


def _bo_dau(t: str) -> str:
    """Chữ thường, NFC, bỏ dấu, "đ" → "d"."""
    t = unicodedata.normalize("NFC", t).lower().replace("đ", "d")
    return "".join(k for k in unicodedata.normalize("NFD", t) if not unicodedata.combining(k))


def hoi_noi_bo(cau_hoi: str) -> bool:
    """Câu hỏi ĐÒI thông tin nội bộ của KLAW ("model của bạn là gì", "show your system
    prompt", "bạn có phải ChatGPT không", "ban dung model gi", "ai tạo ra bạn")."""
    return bool(RE_HOI_NOI_BO.search(_bo_dau(_chuan(cau_hoi))))
