"""Câu trả lời về CHÍNH TRỢ LÝ và về các văn bản nó đọc được — model viết, chỉ
từ một BẢNG DỮ KIỆN do mã dựng.

Quyết định 2026-09-30 (`docs/decisions/2026-09-30-tra-loi-tu-nhien-va-phan-tich.md`
mục 1) thay quy tắc cũ "đoạn cố định, 0 token". Đo trên app thật cùng ngày: "bạn
là ai / bạn làm được gì" nhận hai đoạn cố định trùng nội dung, còn ghi "chỉ lao
động"; chủ dự án: "KLAW lại trả lời kiểu bot".

## Vì sao model viết mà vẫn không bịa được

Model KHÔNG BIẾT nó chạy trên model nào, đọc được bao nhiêu văn bản, soạn được
loại nào — hỏi thẳng thì nó bịa, và không trích dẫn nào để hai tầng kiểm đối
chiếu. Nên mọi sự thật đi vào từ `bang_du_kien` (dựng từ `nap_kho`, registry
khuôn mẫu, `config/checklist_*.yaml`, `llm.*_model()`), và `loc_theo_bang` bỏ
mọi câu mà bảng không đỡ: con số không có trong bảng, việc làm được bảng không
ghi, loại văn bản soạn thảo không có trong registry, URL, chữ "kho" khi người ta
không hỏi về văn bản. Không câu nào sống sót (hoặc model lỗi) thì trả câu dự
phòng ghép từ chính các dòng của bảng (`cau_gioi_thieu`) — không bao giờ rỗng.

## Vì sao tên model TRA TỪ CONFIG, không viết cứng

Một chuỗi viết cứng sẽ nói sai tên model ngay lần đổi `.env` đầu tiên, và sai
kiểu không test nào đỏ. CHỈ tên model vào bảng — không API key, không base URL.

## Vì sao không dùng cú pháp markdown

Giao diện KHÔNG dịch markdown: `frontend/src/lib/van-xuoi.ts` chỉ cắt đoạn và
nhận dòng mở bằng "- " thành danh sách. Dấu `**` hay nháy ngược hiện nguyên trên
màn hình, nên `loc_theo_bang` gỡ chúng.
"""

import json
import logging
import re
import unicodedata
from pathlib import Path

from src.services import khuon_mau
from src.services.kho import (
    CAU_GIOI_HAN,
    DO_SAU_CHI_LUAT_GOC,
    DO_SAU_DU_BA_TANG,
    danh_sach_bo_luat,
    dung_cau_tra_loi,
    tom_tat_linh_vuc,
)
from src.services.llm import Usage, generate_model, judge_model, router_model
from src.services.prompts import messages

logger = logging.getLogger(__name__)

PROMPT_PATH = Path("prompts/gioi_thieu.v1.md")

META_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tra_loi"],
    "properties": {"tra_loi": {"type": "string"}},
}

# ══ Nhận diện dạng câu hỏi — QUY TẮC, 0 token ════════════════════════════════
#
# Rẻ được là nhờ ngữ cảnh, đúng như `kho.moi_so_hieu_trong`: các biểu thức dưới
# đây chỉ chạy khi `route` đã kết luận câu hỏi là `gioi_thieu`, nên chúng không
# phải tự phân biệt "hỏi về trợ lý" với "hỏi nội dung luật" — chỉ phải tách
# DẠNG trong một câu đã biết là hỏi về trợ lý.

# Model / công nghệ. `\bai\s+(?:nào|gì)\b` chứ không phải `ai` trần: "ai" trong
# tiếng Việt là đại từ nghi vấn. "bạn là ai" giờ rơi về `_RE_LA_AI` (hỏi VAI —
# danh tính), KHÔNG còn rơi về khía cạnh năng lực như bản trước (T3 tách riêng)
# — pattern ở đây chỉ bắt "AI" theo nghĩa công nghệ khi đi kèm "nào"/"gì" ("AI
# nào", "AI gì"). `_khop` gỡ `_RE_LA_AI`/`_RE_BAN_CHAT` khi chúng đứng SAU một
# dấu hiệu model/nguồn, nên "model của bạn là ai" và "bạn chạy bằng mô hình gì"
# vẫn chỉ ra khía cạnh model.
_RE_MODEL = re.compile(
    r"\bmodel\b|mô\s*hình|\bllm\b|\bgpt\b|chatgpt|\bclaude\b|gemini|deepseek|"
    r"chạy\s+(?:bằng|trên)|dùng\s+(?:model|mô\s*hình|công\s*nghệ)|"
    r"\bai\s+(?:nào|gì)\b|công\s+nghệ\s+(?:nào|gì)"
)

# Nguồn dữ liệu / có tin được không.
_RE_NGUON = re.compile(
    r"dữ\s*liệu|nguồn|lấy\s+(?:từ\s+)?đâu|ở\s+đâu|tin\s+(?:được|cậy)|đáng\s+tin|"
    r"cập\s+nhật|hợp\s+nhất|\bvbpl\b"
)

# Danh tính — "là ai" hỏi VAI: "bạn là ai", "klaw là ai", "bạn tên gì", "bạn
# tên là gì", "giới thiệu về bạn", "em là ai". Chủ dự án nêu đích danh câu này
# phải khác "bạn là gì" — hai câu chỉ lệch một từ.
_RE_LA_AI = re.compile(r"\blà\s+ai\b|tên\s+(?:là\s+)?gì\b|giới\s+thiệu")

# Bản chất — "là gì" hỏi BẢN CHẤT: "bạn là gì", "bạn là cái gì", "klaw là gì",
# "bản chất của bạn là gì" (khớp qua "là gì"), "bạn có phải luật sư/người thật
# không". Không cần loại trừ `_RE_MODEL`/`_RE_NGUON` bằng tay ở đây: hai biểu
# thức đó được thử TRƯỚC trong `cau_gioi_thieu`, nên "model của bạn là gì" và
# "dữ liệu ... là gì" đã rẽ nhánh trước khi tới đây.
_RE_BAN_CHAT = re.compile(r"\blà\s+(?:cái\s+)?gì\b|\bcó\s+phải\b")

# Năng lực — làm được gì. MẶC ĐỊNH của bộ phân rã: câu không khớp khía cạnh
# nào rơi về đây.
_RE_NANG_LUC = re.compile(
    r"làm\s+được|giúp\s+được|giúp\s+gì|hoạt\s+động|năng\s+lực|chức\s+năng|"
    r"hỗ\s+trợ\s+(?:gì|được)|làm\s+gì|làm\s+những\s+gì"
)

# Phạm vi kho — ba khía cạnh RIÊNG vì người hỏi phân biệt được chúng: "có
# những Bộ luật gì" ≠ "có những lĩnh vực gì" ≠ "kho có gì".
_RE_BO_LUAT = re.compile(r"bộ\s*luật|bo\s*luat")
# The `bo_luat` facet only when the question asks what KLAW holds ("có những Bộ
# luật gì", "bao nhiêu bộ luật") — decision 2026-09-30 item 2: "cần nắm những bộ
# luật gì" asks which laws govern a case, and a bare name ("Bộ luật Hàng hải có
# hiệu lực không") is a kho lookup, not the list.
_RE_HOI_BO_LUAT = re.compile(
    r"(?:\bcó|gồm|chứa|phủ|đọc(?:\s+được)?)\s+(?:(?:những|các|bao\s+nhiêu|mấy)\s+)?bộ\s*luật"
    r"|bao\s+nhiêu\s+bộ\s*luật|danh\s+sách\s+(?:các\s+)?bộ\s*luật"
)
_RE_LINH_VUC = re.compile(r"lĩnh\s*vực|lãnh\s*vực|linh\s*vuc")
# "bao nhiêu điều luật" (trace fa18ddce): an article count is a count over the
# kho too. Not bare "điều": "bao nhiêu điều kiện" counts conditions.
_RE_KHO = re.compile(r"\bkho\b|bao\s+nhiêu\s+(?:văn\s+bản|điều\s+luật)|những\s+văn\s+bản\s+(?:nào|gì)|văn\s+bản\s+nào")

# Soạn thảo / rà soát.
_RE_SOAN_THAO = re.compile(r"soạn|rà\s*soát|soát\s+được")

# Cảm ơn. Dạng thứ NĂM, không nằm trong bốn dạng brief nêu: `docs/bo-luat-agent.md`
# (dòng 5) ghi "cảm ơn" cũng rơi vào `intent=gioi_thieu`, nên không có dạng này
# thì một lời cảm ơn nhận về đúng bức tường chữ 1.104 ký tự đã bị báo lỗi.
# Neo `^`: chỉ câu MỞ ĐẦU bằng lời cảm ơn, để "cảm ơn, mà dữ liệu lấy ở đâu"
# vẫn đi vào dạng nguồn ở trên.
_RE_CAM_ON = re.compile(r"^(?:cảm|cám)\s*ơn|^thank|^tks\b|^thx\b")

# Chào hỏi ĐƠN THUẦN — khớp TOÀN BỘ câu (`fullmatch`), không phải một cụm trong
# câu. "chào bạn, bạn làm được những gì" là một câu HỎI có lời chào dẫn vào; trả
# nó lời chào ngắn là bỏ mất câu hỏi thật, nên nó phải KHÔNG khớp ở đây và rơi
# xuống dạng năng lực.
_RE_CHAO = re.compile(
    r"(?:xin\s+)?(?:chào|chao|hello|hi+|hey|helo|alo|ê)"
    r"(?:\s+(?:bạn|ban|klaw|trợ\s+lý|ạ|à|nhé|nha|mọi\s+người|cả\s+nhà))*"
)

_RE_KHONG_PHAI_CHU = re.compile(r"[^\w\s]", re.UNICODE)


def _chuan(cau_hoi: str) -> str:
    """Chữ thường, dấu câu thành khoảng trắng, khoảng trắng gộp lại.

    Cần cho `_RE_CHAO.fullmatch`: "Chào bạn!" và "chào bạn." phải khớp cùng một
    biểu thức, và nhồi dấu câu vào chính biểu thức đó làm nó không đọc được.
    """
    return _RE_KHONG_PHAI_CHU.sub(" ", cau_hoi.lower()).strip()


# ══ Bảng dữ kiện và câu dự phòng ═════════════════════════════════════════════

# Cảm ơn, khi model không viết được: câu dự phòng cố định, đúng sự thật.
CAM_ON = (
    "Không có gì. Chỗ nào trong câu trả lời bạn thấy chưa chắc thì bấm vào trích "
    "dẫn để đọc nguyên văn điều luật — hoặc hỏi tiếp, tôi còn ở đây."
)

_TIEN_TO_CHECKLIST = "checklist_"
# Cùng thư mục `config/` mà `graph_soan_thao.cac_loai()` đã glob — không import
# thẳng từ đó vì đó là một graph soạn thảo nặng (langgraph, sqlalchemy...) cho
# một quan hệ ngược chiều (node giới thiệu phụ thuộc vào graph khác); glob lại
# ba dòng này rẻ hơn nhiều so với kéo cả graph đó vào.
_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


def _loai_soan_thao() -> str:
    """Đếm & nhóm loại văn bản soạn thảo từ `config/checklist_*.yaml` LÚC GỌI,
    không phải hằng số đóng băng lúc import — cùng lý do tên model tra từ
    config thay vì viết cứng: bản trước ghi cứng "ba loại" trong khi
    kho đã có 27 file, và một con số cũ nằm trong lời tự giới thiệu là kiểu sai
    không test nào tự bắt được.

    Nhóm bằng TIỀN TỐ tên file, không liệt kê tay 27 cái tên: thêm một checklist
    mới vào một nhóm đã có (vd. thêm một loại hợp đồng) tự cập nhật số nhóm,
    không đụng dòng nào ở đây.
    """
    ten = [p.stem.removeprefix(_TIEN_TO_CHECKLIST) for p in _CONFIG_DIR.glob(f"{_TIEN_TO_CHECKLIST}*.yaml")]
    nhom = {
        "hợp đồng": sum(1 for t in ten if t.startswith("hop_dong") or t == "hdld"),
        "đơn từ": sum(1 for t in ten if t.startswith("don_")),
        "quyết định": sum(1 for t in ten if t.startswith("quyet_dinh")),
        "quy chế": sum(1 for t in ten if t.startswith("quy_che")),
    }
    ke = ", ".join(f"{soluong} {ten_nhom}" for ten_nhom, soluong in nhom.items() if soluong)
    return f"{len(ten)} loại văn bản ({ke}, và vài loại khác)"


# ══ Phân rã KHÍA CẠNH — một câu hỏi mang được nhiều ý ════════════════════════
#
# Bản trước kiểm các biểu thức theo thứ tự rồi TRẢ NGAY kết quả đầu tiên. Hợp
# cho câu đơn, mất ý cho câu ghép: "bạn làm được gì, có những bộ luật gì, có
# những lĩnh vực pháp luật gì" nhận đúng một bài năng lực, hai ý sau rơi mất
# (ex.md §2.3). Router vẫn chỉ trả MỘT `intent` — phân rã nằm ở đây, trong nhóm
# câu hỏi về KLAW và kho, không kéo mọi luồng pháp lý vào thiết kế mới.

# Thứ tự mặc định khi hai khía cạnh khớp cùng một vị trí (FR-013).
KHIA_CANH = ("danh_tinh", "ban_chat", "nang_luc", "bo_luat", "linh_vuc", "kho",
             "soan_thao", "nguon", "model")

_RE_KHIA_CANH = {
    "danh_tinh": _RE_LA_AI,
    "ban_chat": _RE_BAN_CHAT,
    "nang_luc": _RE_NANG_LUC,
    "bo_luat": _RE_HOI_BO_LUAT,
    "linh_vuc": _RE_LINH_VUC,
    "kho": _RE_KHO,
    "soan_thao": _RE_SOAN_THAO,
    "nguon": _RE_NGUON,
    "model": _RE_MODEL,
}

# Ba khía cạnh phải đọc kho thật mới trả lời được.
_KHIA_CANH_KHO = ("bo_luat", "linh_vuc", "kho")


def _khop(c: str) -> dict[str, int]:
    """Khía cạnh → vị trí khớp ĐẦU TIÊN trong câu đã chuẩn hoá. Rỗng nghĩa là
    câu không nêu khía cạnh nào (→ mặc định `nang_luc` ở `khia_canh`)."""
    vi = {ten: m.start() for ten, bt in _RE_KHIA_CANH.items() if (m := bt.search(c))}

    # `model`/`nguon` là dấu hiệu HẸP hơn "là ai"/"là gì". Khi chúng đứng TRƯỚC
    # trong câu thì "là ai"/"là gì" là vị ngữ của CHÍNH CHÚNG: "model của bạn là
    # ai" hỏi model, "dữ liệu của bạn là gì" hỏi nguồn. Đứng SAU thì đó là một
    # khía cạnh thật của câu ghép ("bạn là ai và dữ liệu lấy từ đâu") và được
    # giữ — bản trước không phân biệt được hai ca này vì nó trả ngay ở khớp đầu.
    hep = min((vi[t] for t in ("model", "nguon") if t in vi), default=None)
    if hep is not None:
        for t in ("danh_tinh", "ban_chat"):
            if vi.get(t, -1) > hep:
                vi.pop(t)

    # `kho` chỉ thêm khi KHÔNG hỏi đích danh Bộ luật hay lĩnh vực: khối tóm tắt
    # kho đã liệt kê cả hai thứ đó, nên giữ cả hai là nói hai lần (FR-011).
    if "bo_luat" in vi or "linh_vuc" in vi:
        vi.pop("kho", None)
    return vi


def _thu_tu(vi: dict[str, int], mac_dinh: str = "nang_luc") -> list[str]:
    return sorted(vi, key=lambda t: (vi[t], KHIA_CANH.index(t))) or [mac_dinh]


def khia_canh(cau_hoi: str) -> list[str]:
    """Các khía cạnh trong câu hỏi, THEO THỨ TỰ người hỏi nêu (FR-013).

    Mặc định `["nang_luc"]` khi không khớp gì — lời đáp đầy đủ nhất, thay cho
    màn hình trắng mà cả pha này tồn tại để bỏ đi. Chỉ đúng cho lượt
    `gioi_thieu`; lượt `hoi_ve_kho` dùng `khia_canh_kho`.
    """
    return _thu_tu(_khop(_chuan(cau_hoi)))


TOI_DA_LINH_VUC = 6

# Deterministic router guard. Production 2026-09-16: the LLM router sent
# "bạn làm được gì, có những bộ luật gì, có những lĩnh vực pháp luật gì" to
# retrieval and the user got partial_coverage about an unrelated decree. A
# question that plainly addresses the assistant or the corpus never needs
# retrieval, so it is pinned to gioi_thieu before the graph branches. Kept
# narrow: second-person "bạn/KLAW làm được gì / là ai / là gì", "những bộ
# luật|lĩnh vực gì|nào", "kho có/phủ", "model của bạn", "dữ liệu lấy". A
# digit or an article/decree word means a real legal question — never pinned.
#
# Decision 2026-09-30 item 2: a branch alone no longer pins. The question must
# also address KLAW or its documents (`_RE_NOI_VOI_KLAW`, `_RE_NEO_KHO`), and the
# asker's own situation vetoes the pin (`ke_tinh_huong`). Trace 88117154: "tôi
# đang gặp sự cố tranh chấp nhà đất, cần nắm rõ những bộ luật gì" matched the
# anchorless "những bộ luật gì" branch and got the list of six Bộ luật.
_RE_META_MANH = re.compile(
    r"\b(?:bạn|klaw)\s+(?:làm|giúp|hỗ\s*trợ)\s+(?:được\s+)?(?:những\s+)?gì"
    r"|\b(?:bạn|klaw)\s+là\s+(?:ai|(?:cái\s+)?gì)\b"
    r"|những\s+(?:bộ\s+luật|lĩnh\s+vực)(?:\s+pháp\s+luật)?\s+(?:gì|nào)"
    r"|\bkho\s+(?:của\s+bạn\s+)?(?:có|phủ|gồm)"
    r"|model\s+(?:của\s+)?bạn|\bbạn\s+(?:dùng|chạy)\s+(?:model|mô\s*hình|ai)"
    r"|dữ\s*liệu\s+(?:của\s+bạn\s+)?(?:lấy|từ)"
    r"|bao\s+nhiêu\s+(?:văn\s+bản|bộ\s+luật)"
)
# "tài khoản" is an account, not a clause ("tôi vừa đăng ký tài khoản, KLAW hỗ trợ gì").
_RE_NOI_DUNG_LUAT = re.compile(r"\d|\bđiều\b|(?<!tài )\bkhoản\b|nghị\s*định|thông\s*tư")
# A legal event in the asker's case. Not first-person words alone: "tôi mới dùng
# lần đầu, bạn làm được những gì" and "câu hỏi của tôi là: bạn là ai" address
# KLAW, and vetoing them sent a meta question to retrieval (review 2026-09-30).
# Written without diacritics and matched on the folded question, so "toi dang
# gap su co tranh chap nha dat" is the same case; folding is safe here because
# the veto only ever sends a question to tra_cuu. ponytail: closed event list;
# a situation it misses is left to the router — a route prompt line for item 2
# needs a new prompt version (route.v5 is frozen, `test_route_prompt_mac_dinh_v5`).
_RE_SU_VIEC = re.compile(
    r"\b(?:tranh\s+chap|khoi\s+kien|bi\s+kien|kien\s+tung|sa\s+thai|duoi\s+viec|no\s+luong|tru\s+luong"
    r"|ly\s+hon|thua\s+ke|lua\s+dao|tai\s+nan|boi\s+thuong|mat\s+quyen\s+loi)\b"
)


def ke_tinh_huong(cau_hoi: str) -> bool:
    """True when the question names a legal event in the asker's case: a
    question about the law, never a meta one (decision 2026-09-30 item 2).
    `route` turns a meta verdict on such a question back into tra_cuu."""
    return bool(_RE_SU_VIEC.search(_bo_dau(_chuan(cau_hoi))))


def chac_chan_meta(cau_hoi: str) -> bool:
    """True when the question is unmistakably about KLAW or the corpus: a meta
    branch, an anchor naming KLAW or its documents, no legal-content marker and
    no situation. The router's LLM verdict is then overridden to gioi_thieu."""
    c = _chuan(cau_hoi)
    return (
        bool(_RE_META_MANH.search(c))
        and bool(_RE_NOI_VOI_KLAW.search(c) or _RE_NEO_KHO.search(c))
        and not _RE_NOI_DUNG_LUAT.search(c)
        and not ke_tinh_huong(cau_hoi)
    )


# Guard in the other direction (decision 2026-09-29 item 4). Production
# 2026-09-29: the LLM router labelled "pháp luật Việt Nam chia thành những gì"
# `hoi_ve_kho` and the user got the KLAW introduction. A question about the
# Vietnamese legal system is answered from statute, so `route` turns such a
# meta verdict back into tra_cuu. Bare "hiến pháp"/"văn bản quy phạm" are left
# out: "có Hiến pháp 2013 không" asks whether the kho holds the document.
# Written without diacritics and matched on the folded question, so "luat",
# "luật" and a mistyped tone ("hệ thông") all match.
_LUAT_VIET_NAM = (
    r"(?:\b(?:luat(?:\s+phap)?|hien\s+phap)\s+(?:(?:cua|o|tai|nuoc)\s+)*(?:viet\s*nam|vn)"
    r"|\bluat(?:\s+phap)?\s+nuoc\s+ta)\b"
)
_CAU_TRUC_PHAP_LUAT = (
    r"\bhe\s+thong\s+(?:van\s+ban\s+)?(?:quy\s+pham\s+)?phap\s+luat"
    r"|\bloai\s+van\s+ban\s+(?:quy\s+pham\s+)?phap\s+luat"
    r"|\bvan\s+ban\s+(?:quy\s+pham\s+)?phap\s+luat\s+(?:duoc\s+)?(?:gom|chia|phan)\b"
    r"|\bnganh\s+luat|\bvb\s*qppl\b"
)
_RE_HE_THONG_PHAP_LUAT = re.compile(f"{_LUAT_VIET_NAM}|{_CAU_TRUC_PHAP_LUAT}")
# "luật VN" / "luật nước ta" alone also opens an ordinary case ("Theo luật VN thì
# tôi bị nợ lương 3 tháng phải làm sao"). For the dead-end follow-up it counts
# only when the law itself is what gets divided or listed.
_RE_CAU_TRUC_PHAP_LUAT = re.compile(
    rf"{_LUAT_VIET_NAM}\s+(?:hien\s+(?:nay|tai|hanh)\s+)?(?:duoc\s+)?"
    r"(?:chia|gom|bao\s+gom|phan|co\s+(?:may|nhung|cac|bao\s+nhieu))\b"
    rf"|\bthu\s+bac\b|{_CAU_TRUC_PHAP_LUAT}"
)
# Positive signs that the question addresses KLAW. Not a bare pronoun: "em" is
# usually the user speaking of themselves ("cho em hỏi"), and "bạn" mostly
# opens a polite question ("chào bạn", "bạn có thể cho mình biết", "… vậy bạn").
# ponytail: accented, plus the unaccented forms that collide with nothing;
# folding would merge bạn/bản and kho/khó, so "ban co nhung …" typed without
# diacritics is not recognised. Add forms when a trace shows one forced to
# tra_cuu.
_RE_NOI_VOI_KLAW = re.compile(
    r"\bklaw\b|trợ\s*l[ýí]|\btro\s*ly\b|\bcủa\s+bạn\b"
    r"|\b(?:app|ứng\s+dụng|ung\s+dung|hệ\s+thống|chương\s+trình|phần\s+mềm|web(?:site)?)\s+(?:này|nay)\b"
    r"|\b(?:bạn|em)\s+là\s+(?:ai|(?:cái\s+)?gì)\b"
    r"|\bbạn\s+(?:(?:làm|giúp|hỗ\s*trợ)\s+(?:được\s+)?(?:những\s+)?gì|dùng|chạy"
    r"|(?:đang\s+)?có\s+(?:những|các|bao\s+nhiêu|mấy))\b"
    r"|\btra\s+(?:cứu\s+)?được\b|\btra\s+(?:cuu\s+)?duoc\b|\bhỗ\s*trợ\b|\bho\s*tro\b"
)
# Explicit corpus markers. Narrower than the kho facets: "văn bản nào" is also
# how a legal-system question asks ("văn bản nào có hiệu lực cao nhất").
_RE_DAU_KHO = re.compile(
    r"\bkho\b|dữ\s*liệu|\bdu\s*lieu\b"
    r"|bao\s+nhiêu\s+(?:văn\s+bản|điều\s+luật)|\bbao\s+nhieu\s+(?:van\s+ban|dieu\s+luat)\b"
)
# The pin's anchor (decision 2026-09-30 item 2) names the kho itself; a document
# count alone ("có bao nhiêu văn bản hướng dẫn luật đất đai") is left to the router.
_RE_NEO_KHO = re.compile(r"\bkho\b|dữ\s*liệu|\bdu\s*lieu\b")


def _bo_dau(c: str) -> str:
    return "".join(k for k in unicodedata.normalize("NFD", c.replace("đ", "d")) if not unicodedata.combining(k))


def hoi_he_thong_phap_luat(cau_hoi: str) -> bool:
    """True when the question asks about the Vietnamese legal system and neither
    addresses KLAW nor names the corpus (kho, dữ liệu, a document or article
    count, Bộ luật, lĩnh vực): those stay on the kho data, which answers them
    and closes with CAU_GIOI_HAN."""
    c = _chuan(cau_hoi)
    if not _RE_HE_THONG_PHAP_LUAT.search(_bo_dau(c)):
        return False
    return not any(r.search(c) for r in (_RE_NOI_VOI_KLAW, _RE_DAU_KHO, _RE_BO_LUAT, _RE_LINH_VUC))


def hoi_cau_truc_phap_luat(cau_hoi: str) -> bool:
    """A legal-system question that asks how the system is built (its parts,
    kinds of documents, hierarchy), not a case that merely names "luật VN"."""
    return hoi_he_thong_phap_luat(cau_hoi) and bool(_RE_CAU_TRUC_PHAP_LUAT.search(_bo_dau(_chuan(cau_hoi))))


# KLAW-self facets. On a `hoi_ve_kho` turn "là gì", "làm gì", "hoạt động",
# "mô hình" are ordinary words of a question about the law or the kho, so these
# answer only a question that addresses KLAW (decision 2026-09-29 item 4).
_KHIA_CANH_KLAW = ("danh_tinh", "ban_chat", "nang_luc", "model")


def khia_canh_kho(cau_hoi: str) -> list[str]:
    """Facets of a `hoi_ve_kho` turn: KLAW-self facets only when the question
    addresses KLAW, and `["kho"]` when nothing is left (trace fa18ddce: a kho
    question naming no facet got the KLAW introduction)."""
    c = _chuan(cau_hoi)
    vi = _khop(c)
    if not _RE_NOI_VOI_KLAW.search(c):
        vi = {t: v for t, v in vi.items() if t not in _KHIA_CANH_KLAW}
    return _thu_tu(vi, "kho")


def chi_hoi_kho(cac_khia_canh: list[str]) -> bool:
    """Only corpus facets — the caller keeps the existing `hoi_ve_kho` text and
    table path (ex.md §3.3) instead of composing."""
    return all(t in _KHIA_CANH_KHO for t in cac_khia_canh)


def can_kho(cac_khia_canh: list[str]) -> bool:
    """Lượt này có cần nạp kho không — chỗ gọi dùng nó để nạp ĐÚNG MỘT LẦN cho
    mọi khía cạnh (FR-014)."""
    return any(t in cac_khia_canh for t in _KHIA_CANH_KHO)


# Khi một khía cạnh kho được hỏi mà kho chưa nạp được: nói THẲNG là chưa đọc
# được, KHÔNG bịa tên Bộ luật hay lĩnh vực nào. Một câu duy nhất, kể cả khi câu
# hỏi nêu hai khía cạnh kho.
THIEU_KHO = ("Danh sách Bộ luật và lĩnh vực tôi đọc từ dữ liệu pháp luật lúc trả lời; "
             "lượt này tôi chưa đọc được.")

# Đúng MỘT lời mời tiếp tục, gắn với nội dung vừa hỏi (FR-015).
HOI_TIEP_KHO = "Bạn muốn xem danh sách văn bản của lĩnh vực nào?"
HOI_TIEP_SOAN = "Bạn cần soạn loại văn bản nào?"
HOI_TIEP_NANG_LUC = "Bạn đang cần tra cứu vấn đề gì, hay cần soạn văn bản nào?"

# Lời chào dẫn vào, chỉ lượt đầu (ex.md §4.3). Lượt nối tiếp không chào lại.
_RE_MO_DAU_CHAO = re.compile(r"^(?:xin\s+)?(?:chào|chao|hello|hi|hey|helo|alo)\b")


def _liet_ke(x: list[str]) -> str:
    return x[0] if len(x) == 1 else ", ".join(x[:-1]) + " và " + x[-1]


# Phase 14 (R5) — lời cho NGƯỜI ĐỌC nói tên thứ đang trích ("Bộ luật", "văn bản
# luật", "pháp luật Việt Nam"), không gọi corpus là "kho": xem
# `services/kho.CAU_GIOI_HAN` cho lý lẽ đầy đủ. Tham số `kho`, `_KHIA_CANH_KHO`
# và mọi chú thích ở file này giữ tên cũ — đây là việc đổi LỜI, không đổi mã.
def _khoi_bo_luat(kho: list[dict]) -> str:
    ten = [d["ten_ngan"] for d in danh_sach_bo_luat(kho)]
    if not ten:
        return "Tôi hiện chưa có Bộ luật nào."
    return f"Tôi hiện có {len(ten)} Bộ luật: {_liet_ke(ten)}."


def _khoi_linh_vuc(kho: list[dict]) -> str:
    """Lĩnh vực kèm độ sâu — bỏ khoá `""` (văn bản chưa gắn lĩnh vực): một ô
    trống đọc được trong bảng, nhưng trong câu văn xuôi nó thành một tên lĩnh
    vực rỗng."""
    lv = [d for d in tom_tat_linh_vuc(kho) if d["linh_vuc"]]
    if not lv:
        return "Tôi hiện chưa gắn lĩnh vực cho văn bản nào."
    # Real corpus: 55 MOJ labels, most documents unclassified. Name the largest
    # TOI_DA_LINH_VUC (already sorted by count) and count the rest — ex.md §4.2
    # caps a scope list at six items.
    ten = [f"{d['linh_vuc']} ({d['so_van_ban']} văn bản)" for d in lv[:TOI_DA_LINH_VUC]]
    con = len(lv) - len(ten)
    cau = f"Các lĩnh vực đang phủ gồm {_liet_ke(ten)}" + (f" và {con} lĩnh vực khác." if con else ".")
    sau = [d["linh_vuc"] for d in lv if d["do_sau"] == DO_SAU_DU_BA_TANG]
    nong = sum(1 for d in lv if d["do_sau"] == DO_SAU_CHI_LUAT_GOC)
    if sau:
        cau += f" {', '.join(sau)} là lĩnh vực sâu nhất"
        cau += f"; {nong} lĩnh vực khác hiện mới có luật gốc." if nong else "."
    elif nong:
        cau += f" {nong} lĩnh vực hiện mới có luật gốc."
    return cau


def _pham_vi(kho: list[dict]) -> str:
    """Số văn bản được HIỆN (cùng tập với `kho._tom_tat` và trang Tra cứu) và số
    văn bản có toàn văn. Dòng không mang cờ `hien` (bảng dựng tay trong test) là
    được hiện, như `kho._duoc_hien`."""
    hien = [r for r in kho if r.get("hien", True)]
    sau = sum(1 for r in hien if r["depth"] == "deep")
    return (
        f"Tôi đọc được {len(hien)} văn bản pháp luật Việt Nam, trong đó {sau} văn bản có toàn văn "
        "tra được tới từng điều khoản; phần sâu nhất là pháp luật lao động."
    )


def _soan_thao() -> str:
    """Loại có khuôn mẫu Word (registry `khuon_mau`, đọc LÚC GỌI) cộng số loại
    checklist — một loại mới thêm vào registry tự có mặt ở đây."""
    ten = sorted({khuon_mau.nap(loai)["ten"] for loai in khuon_mau.cac_loai()})
    return (
        f"Tôi soạn được {len(ten)} loại văn bản có khuôn mẫu Word: {', '.join(ten)}. "
        f"Tôi rà soát được {_loai_soan_thao()} theo checklist nội dung bắt buộc. "
        "Loại khác thì tôi vẫn soạn theo yêu cầu của bạn."
    )


def bang_du_kien(cau_hoi: str, kho: list[dict] | None) -> dict[str, str]:
    """BẢNG DỮ KIỆN — nguồn duy nhất của lời đáp về KLAW (quyết định 2026-09-30
    mục 1, 6). Mỗi dòng là một câu người đọc thấy được nguyên văn (qua model hay
    qua câu dự phòng), nên không dòng nào gọi corpus là "kho".

    `kho` là snapshot `nap_kho` đã nạp sẵn; `None` (chỗ gọi chưa nạp) thì bảng
    KHÔNG có dòng số liệu nào — thà thiếu còn hơn bịa. `cau_hoi` chỉ dùng cho dòng
    `kho` (`dung_cau_tra_loi` tra đúng số hiệu người hỏi nêu).
    """
    bang = {
        "vai_tro": "Tôi là KLAW, trợ lý AI tra cứu pháp luật Việt Nam, sâu nhất ở pháp luật lao động.",
        "viec": "\n".join(
            (
                "- Tra cứu pháp luật theo tình huống của bạn: mỗi quy định kèm trích dẫn tới đúng điều, khoản, "
                "điểm, bấm vào là đọc được nguyên văn.",
                "- Soạn thảo văn bản ngay trên trang: bấm vào chỗ trống để điền, rồi tải về tệp Word (.docx); "
                "cần đăng nhập để lưu bản thảo.",
                "- Rà soát văn bản: đối chiếu nội dung bắt buộc theo luật và chỉ ra điều khoản trái luật.",
                "- Đọc tệp Word (.docx, .doc) hoặc PDF bạn tải lên ở chế độ nền, rồi trả lời câu hỏi về tệp đó "
                "ngay trong khung chat.",
                "- Nhớ các lượt trước trong cùng cuộc trò chuyện để hiểu câu hỏi nối tiếp.",
            )
        ),
        "soan_thao": _soan_thao(),
        "ban_chat": (
            "Tôi là một chương trình chạy trên mô hình ngôn ngữ, không phải luật sư, thẩm phán hay cơ "
            "quan nhà nước: tôi không ra phán quyết, không đại diện cho bạn tại tòa, và câu trả lời của "
            "tôi không thay thế tư vấn của luật sư."
        ),
        "kiem_chung": (
            "Mỗi trích dẫn phải qua hai tầng kiểm mới được hiện ra: tầng một so từng chữ câu trích "
            "với nguyên văn điều khoản trong chính văn bản luật; tầng hai để một model khác họ đọc lại "
            "xem điều khoản đó có chống đỡ được câu đó không. Không đủ căn cứ thì tôi nói thẳng là "
            "không đủ, không đoán luật hay kết quả vụ việc."
        ),
        "nguon": (
            "Văn bản tôi đọc lấy từ Cơ sở dữ liệu quốc gia về văn bản pháp luật — bản công bố của cơ quan "
            "nhà nước. Tôi đọc bản gốc, không phải bản hợp nhất, và gắn nhãn hiệu lực cho từng trích dẫn; "
            "việc quan trọng thì bạn nên đối chiếu bản hiện hành."
        ),
        # Chỉ TÊN model, từ chính ba hàm `graph_tra_cuu` gọi để chọn model thật.
        "model": (
            f"Ba model ở ba vai: định tuyến câu hỏi {router_model()}; sinh luận điểm và hành văn "
            f"{generate_model()}; thẩm định lại từng luận điểm {judge_model()} — model thẩm định cố ý "
            "khác họ với model sinh."
        ),
    }
    if kho is not None:
        bang["pham_vi"] = _pham_vi(kho)
        bang["bo_luat"] = _khoi_bo_luat(kho)
        bang["linh_vuc"] = _khoi_linh_vuc(kho)
        bang["kho"] = dung_cau_tra_loi(cau_hoi, kho).removesuffix(CAU_GIOI_HAN).rstrip()
    return bang


# Dòng của bảng mà mỗi khía cạnh cần — câu dự phòng ghép đúng các dòng này, mỗi
# dòng MỘT lần kể cả khi hai khía cạnh cùng cần nó (FR-011).
_DONG_CUA = {
    "danh_tinh": ("vai_tro",),
    "ban_chat": ("ban_chat", "kiem_chung"),
    "nang_luc": ("viec",),
    "bo_luat": ("bo_luat",),
    "linh_vuc": ("linh_vuc",),
    "kho": ("kho",),
    "soan_thao": ("soan_thao",),
    "nguon": ("nguon", "kiem_chung"),
    "model": ("model",),
}


def _cau_hoi_tiep(cac: list[str]) -> str:
    if can_kho(cac):
        return HOI_TIEP_KHO
    if "soan_thao" in cac:
        return HOI_TIEP_SOAN
    if any(t in cac for t in ("nang_luc", "danh_tinh", "ban_chat")):
        return HOI_TIEP_NANG_LUC
    return ""


def _du_phong(cau_hoi: str, bang: dict[str, str], cac: list[str], luot_dau: bool = True) -> str:
    """Câu dự phòng — các dòng của bảng cho các khía cạnh được hỏi, theo thứ tự
    người hỏi, rồi câu giới hạn (chỉ khi hỏi về văn bản và bảng có số liệu) và
    đúng MỘT lời mời tiếp."""
    c = _chuan(cau_hoi)
    if _RE_CAM_ON.search(c) and not _khop(c):
        return CAM_ON
    if _RE_CHAO.fullmatch(c):
        return f"Chào bạn. {bang['vai_tro']}\n\n{HOI_TIEP_NANG_LUC}"
    khoa = dict.fromkeys(k for t in cac for k in _DONG_CUA[t])
    van = "\n\n".join(dict.fromkeys(bang.get(k, THIEU_KHO) for k in khoa))
    if "kho" in bang and can_kho(cac):
        van += "\n\n" + CAU_GIOI_HAN
    if hoi := _cau_hoi_tiep(cac):
        van += "\n\n" + hoi
    if luot_dau and _RE_MO_DAU_CHAO.match(c):
        van = "Chào bạn. " + van
    return van


def cau_gioi_thieu(
    cau_hoi: str, kho: list[dict] | None = None, luot_dau: bool = True, cac_khia_canh: list[str] | None = None
) -> str:
    """Câu dự phòng dựng thẳng từ câu hỏi và snapshot kho — cho chỗ gọi không có
    model, và để test đọc được sự thật của từng khía cạnh. `kho=None` thì khía
    cạnh kho nhận `THIEU_KHO`, KHÔNG nhận một danh sách bịa."""
    return _du_phong(cau_hoi, bang_du_kien(cau_hoi, kho), cac_khia_canh or khia_canh(cau_hoi), luot_dau)


def co_khia_canh(cau_hoi: str) -> bool:
    """Câu có nêu khía cạnh nào không. Lượt nối tiếp dùng nó để tính khía cạnh
    trên câu NGƯỜI DÙNG GÕ khi câu đó tự nói được, không trên câu đã giải nghĩa:
    trace 8eb13b06, "bạn là ai" viết lại thành "KLAW là ai và làm được gì" thêm
    một khía cạnh không ai hỏi."""
    return bool(_khop(_chuan(cau_hoi)))


# ══ Lọc lời model theo bảng ════════════════════════════════════════════════════

_RE_CHU_KHO = re.compile(r"\bkho\b", re.IGNORECASE)
_RE_CAU = re.compile(r"(?<=[.!?…])\s+")
_RE_VE = re.compile(r"[,;:—–]|\s-\s|\s(?:nhưng|còn|song)\s")
_RE_PHU_DINH = re.compile(r"\b(?:không|chưa|chẳng)\b")
# Lời khuyên cho người hỏi ("bạn nên liên hệ luật sư") không phải việc KLAW tự nhận.
_RE_KHUYEN = re.compile(r"\b(?:bạn|anh|chị)\s+(?:nên|cần)\b|\bhãy\b|\bnên\b")
_RE_RO_RI = re.compile(r"https?:|www\.|\bsk-|api[\s_]?key")
# Việc KLAW có thể tự nhận. Một câu khẳng định (không phủ định) mang một cụm ở
# đây phải khớp CÙNG biểu thức đó trong các dòng việc làm được của bảng; câu phủ
# định chỉ cần khớp ở đâu đó trong bảng ("không đại diện cho bạn tại tòa").
# ponytail: danh sách đóng, bắt lớp bịa hay gặp (việc bảng không ghi, loại văn
# bản không có khuôn); một việc bịa nằm ngoài danh sách thì lọt — thêm cụm khi
# trace cho thấy một câu như thế.
_VIEC = tuple(
    re.compile(p)
    for p in (
        r"tra\s*cứu",
        r"trích\s*dẫn",
        r"soạn",
        r"rà\s*soát",
        r"tải\s+(?:lên|về|xuống)|upload|download|đính\s+kèm",
        r"\.docx|\bword\b",
        r"\bpdf\b",
        r"tư\s*vấn",
        r"đại\s*diện|bào\s*chữa|tranh\s*tụng",
        r"phán\s*quyết|xét\s+xử",
        r"\bnộp\b",
        r"\bemail\b|thư\s+điện\s+tử|\bsms\b|tin\s+nhắn",
        r"nhắc\s+(?:lịch|hạn)|đặt\s+lịch|lịch\s+hẹn",
        r"dịch\s+(?:sang|ra|thuật)|tiếng\s+anh|phiên\s+dịch",
        r"\bký\s+(?:số|điện\s+tử|thay)",
        r"\bin\s+(?:ra|văn\s+bản)",
        r"thanh\s+toán|chuyển\s+khoản",
        r"dự\s*đoán|thắng\s+kiện",
        r"ghi\s*nhớ|\bnhớ\b|lưu\s+(?:lại|trữ)",
        r"\bảnh\b|hình\s+ảnh|chụp",
        r"giọng\s+nói|gọi\s+điện",
        r"liên\s+hệ|kết\s+nối",
        r"cập\s*nhật",
        r"\bđiền\b",
        r"tính\s+(?:toán|tiền|thuế|lương|giúp)",
        r"đọc\s+(?:tệp|file|tài\s+liệu)",
    )
)
_DONG_VIEC = ("viec", "soan_thao")
# Một câu nhận soạn/rà soát một LOẠI văn bản: hai từ sau danh từ loại phải có
# trong dòng soạn thảo ("đơn ly hôn" qua, "đơn xin visa" không).
_RE_SOAN = re.compile(r"soạn|viết|lập|rà\s*soát|\bmẫu\b")
_RE_LOAI_VB = re.compile(
    r"\b(?:hợp\s+đồng|đơn|nội\s+quy|quyết\s+định|biên\s+bản|thỏa\s+ước|thoả\s+ước"
    r"|thỏa\s+thuận|thoả\s+thuận|quy\s+chế|giấy|công\s+văn|di\s+chúc)((?:\s+\w+){0,2})"
)
_TU_NOI = frozenset(
    "va hoac hay cho cua theo nhu nay do nao gi cac nhung mau duoc khac moi o tren roi de voi ban toi".split()
)


def _so(t: str) -> set[str]:
    """Mọi dãy chữ số, bỏ dấu phân cách hàng nghìn/thập phân: "1.825" và "1825",
    "2.5" và "25" là cùng một con số với phép so này."""
    return set(re.findall(r"\d+", re.sub(r"(?<=\d)[.,](?=\d)", "", t)))


def _cau_duoc_do(cau: str, toan: str, viec: str, so_bang: set[str], tu_soan: set[str], cho_phep_kho: bool) -> bool:
    t = cau.lower()
    if _RE_RO_RI.search(t) or (not cho_phep_kho and _RE_CHU_KHO.search(t)) or not _so(t) <= so_bang:
        return False
    for ve in _RE_VE.split(t):
        if _RE_KHUYEN.search(ve):
            continue
        for r in _VIEC:
            if (m := r.search(ve)) and not r.search(toan if _RE_PHU_DINH.search(ve[: m.start()]) else viec):
                return False
        if _RE_SOAN.search(ve) and not _RE_PHU_DINH.search(ve):
            for m in _RE_LOAI_VB.finditer(ve):
                if any(w not in tu_soan for w in _bo_dau(m.group(1)).split() if w not in _TU_NOI):
                    return False
    return True


def loc_theo_bang(tho: str, bang: dict[str, str], cho_phep_kho: bool = False) -> str:
    """Giữ đúng những câu bảng dữ kiện đỡ được, mỗi câu MỘT lần, giữ nguyên đoạn
    và gạch đầu dòng. Bỏ câu có: URL hay khoá; chữ "kho" khi không hỏi về văn bản;
    con số không có trong bảng; việc làm được bảng không ghi; loại văn bản soạn
    thảo không có trong bảng. Rỗng nghĩa là không còn câu nào."""
    toan = "\n".join(bang.values()).lower()
    viec = "\n".join(bang[k] for k in _DONG_VIEC if k in bang).lower()
    so_bang, tu_soan = _so(toan), set(re.findall(r"\w+", _bo_dau(bang.get("soan_thao", "").lower())))
    da_co: set[str] = set()
    ra: list[str] = []
    for dong in tho.replace("**", "").replace("`", "").splitlines():
        dau = "- " if dong.lstrip().startswith("- ") else ""
        giu = []
        for cau in _RE_CAU.split(dong.strip().removeprefix("- ").strip()):
            khoa = " ".join(cau.lower().split())
            if khoa and khoa not in da_co and _cau_duoc_do(cau, toan, viec, so_bang, tu_soan, cho_phep_kho):
                da_co.add(khoa)
                giu.append(cau)
        if giu:
            ra.append(dau + " ".join(giu))
        elif not dong.strip():
            ra.append("")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(ra)).strip()


def tra_loi_meta(
    cau_hoi: str,
    bang: dict[str, str],
    cac: list[str],
    llm,
    model: str,
    cau_hoi_day_du: str | None = None,
    luot_dau: bool = True,
) -> tuple[str, Usage | None, str]:
    """`(lời đáp, usage, nguon)` — `nguon` ∈ {"llm", "du_phong", "loi"}.

    MỘT lượt model viết lời đáp cho đúng câu người dùng GÕ (`cau_hoi`; câu đã
    giải nghĩa chỉ để hiểu ngữ cảnh), chỉ từ `bang`, rồi `loc_theo_bang`. KHÔNG
    BAO GIỜ raise, cùng hợp đồng `assemble.giai_thich_chung`: lỗi model hay không
    câu nào sống sót thì trả câu dự phòng từ bảng. `usage` trả cả khi hỏng — tiền
    đã trả phải vào trace. Câu giới hạn phạm vi do mã thêm, chỉ khi hỏi về văn bản
    (quyết định 2026-09-30 mục 5), đứng trước lời mời tiếp nếu đoạn cuối là câu hỏi.
    """
    du_phong = _du_phong(cau_hoi, bang, cac, luot_dau)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        cau_hoi=cau_hoi,
        cau_hoi_day_du=cau_hoi_day_du or cau_hoi,
        luot="đầu cuộc trò chuyện" if luot_dau else "nối tiếp — không chào lại",
        bang_du_kien="\n\n".join(bang.values()),
    )
    usage: Usage | None = None
    try:
        raw, usage = llm.chat(model, messages(prompt, co_soul=False), json_schema=META_SCHEMA)
        tho = str(json.loads(raw)["tra_loi"])
    except Exception as e:
        logger.warning(
            "gioi_thieu: model không viết được lời đáp (%s: %s) — dùng câu dự phòng từ bảng", type(e).__name__, e
        )
        return du_phong, usage, "loi"
    van = loc_theo_bang(tho, bang, cho_phep_kho=can_kho(cac))
    if not van:
        logger.warning("gioi_thieu: không câu nào của model được bảng đỡ — dùng câu dự phòng: %r", tho[:200])
        return du_phong, usage, "du_phong"
    if "kho" in bang and can_kho(cac) and CAU_GIOI_HAN not in van:
        dau, _, cuoi = van.rpartition("\n\n")
        van = f"{dau}\n\n{CAU_GIOI_HAN}\n\n{cuoi}" if dau and cuoi.endswith("?") else f"{van}\n\n{CAU_GIOI_HAN}"
    return van, usage, "llm"
