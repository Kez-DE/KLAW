"""Câu trả lời về CHÍNH TRỢ LÝ — nhận diện bằng QUY TẮC, trả lời bằng TRA BẢNG,
0 token LLM.

ĐO ĐƯỢC trên UI 2026-09-02, hai dòng liền nhau trong bảng `traces`:

    09:21:36  "bạn làm được những gì"  → gioi_thieu
    09:22:22  "model của bạn là gì"    → gioi_thieu

Hai câu hỏi KHÁC NHAU nhận về đúng cùng một đoạn văn 1.104 ký tự, TỪNG CHỮ MỘT
— hằng số `GIOI_THIEU` cũ trong `assemble.py`. Đoạn đó mở bằng "Chào bạn." rồi
liệt kê năng lực: hợp lý cho câu thứ nhất, vô nghĩa cho câu thứ hai, và vô nghĩa
cho một lời chào đơn thuần. Chủ dự án đọc xong nói "vẫn máy móc".

## Vì sao KHÔNG để model tự sinh câu trả lời về chính mình

Nguyên tắc trung tâm của đề tài: mọi đường trả lời phải kết thúc ở MỘT TRONG HAI
— một phép tra bảng xác định, hoặc một claim đã qua đủ hai tầng kiểm. "Model tự
suy ra" không phải một đường trả lời.

Câu hỏi về chính trợ lý là chỗ nguyên tắc ấy dễ bị bỏ qua nhất, vì nó trông như
một câu tán gẫu. Nhưng model KHÔNG BIẾT nó đang chạy trên model nào, kho có gì,
hay ở đây làm được việc gì — nó sẽ bịa, và đây là loại ảo giác verifier KHÔNG
bắt được: không có trích dẫn nào để đối chiếu từng chữ. Cùng lớp lỗi mà
`services/kho.py` đã giải đúng cho câu hỏi về kho, nên giải cùng một cách.

## Vì sao tách DẠNG chứ không thêm `result_type`

`gioi_thieu` vẫn là MỘT loại kết quả; chỉ nội dung `answer` đổi theo dạng câu
hỏi. Một loại mới phải sửa đồng bộ bảy chỗ (`Intent`, prompt route, `_RE_TAT`,
`ResultType`, `assemble`, `schemas.py`, `klaw.ts`) và đó là lớp lỗi đã sập bốn
lần trong dự án này. Bảy chỗ kia không đổi một dòng nào vì việc này.

## Vì sao tên model TRA TỪ CONFIG, không viết cứng

Config đang chạy `deepseek/deepseek-v4-flash-0731` cho vai sinh — khác hẳn mặc
định trong `config.py`. Một chuỗi viết cứng sẽ nói sai tên model ngay hôm nay,
và sai kiểu không test nào đỏ. `router_model()`/`generate_model()`/`judge_model()`
là cùng ba hàm mà `graph_tra_cuu` gọi để chọn model thật, nên không có đường thứ
hai để lệch pha.

CHỈ tên model được nêu. Không API key, không base URL, không một giá trị nào
khác từ `.env` — `test_cau_hoi_ve_model_KHONG_ro_ri_gi_ngoai_TEN_MODEL` canh
điều đó trên máy ĐANG CÓ key thật trong `.env.local`, nên phép canh ấy đo được
chứ không phải một lời hứa.

## Vì sao không dùng cú pháp markdown

Giao diện KHÔNG dịch markdown: `frontend/src/lib/van-xuoi.ts` chỉ cắt đoạn và
nhận dòng mở bằng "- " thành danh sách, phần còn lại vào thẳng `<p>` dưới dạng
chữ thô. Nên dấu nháy ngược quanh tên model sẽ hiện ra nguyên trên màn hình.
Danh sách gạch đầu dòng thì dùng được — và đó là thứ duy nhất dùng được.
"""

import re
import unicodedata
from pathlib import Path

from src.services.kho import (
    CAU_GIOI_HAN,
    DO_SAU_CHI_LUAT_GOC,
    DO_SAU_DU_BA_TANG,
    danh_sach_bo_luat,
    dung_cau_tra_loi,
    tom_tat_linh_vuc,
)
from src.services.llm import generate_model, judge_model, router_model

# ══ Nhận diện dạng câu hỏi — QUY TẮC, 0 token ════════════════════════════════
#
# Rẻ được là nhờ ngữ cảnh, đúng như `kho.moi_so_hieu_trong`: các biểu thức dưới
# đây chỉ chạy khi `route` đã kết luận câu hỏi là `gioi_thieu`, nên chúng không
# phải tự phân biệt "hỏi về trợ lý" với "hỏi nội dung luật" — chỉ phải tách
# DẠNG trong một câu đã biết là hỏi về trợ lý.

# Model / công nghệ. `\bai\s+(?:nào|gì)\b` chứ không phải `ai` trần: "ai" trong
# tiếng Việt là đại từ nghi vấn. "bạn là ai" giờ rơi về `_RE_LA_AI` (hỏi VAI —
# danh tính), KHÔNG còn rơi về bài năng lực như bản trước (T3 tách riêng, xem
# `DANH_TINH`) — pattern ở đây chỉ bắt "AI" theo nghĩa công nghệ khi đi kèm
# "nào"/"gì" ("AI nào", "AI gì"). `_RE_MODEL` luôn được thử TRƯỚC
# `_RE_LA_AI`/`_RE_BAN_CHAT` trong `cau_gioi_thieu`, nên "model của bạn là ai"
# và "bạn chạy bằng mô hình gì" vẫn ra bảng model — ba biểu thức không tranh
# nhau vì THỨ TỰ kiểm quyết định, không phải vì tự loại trừ nhau trong mẫu.
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


# ══ Lời đáp từng dạng ════════════════════════════════════════════════════════

# Dạng 1 — chào hỏi đơn thuần. NGẮN, cộng một câu mời hỏi.
#
# Không dội bài năng lực vào mặt người ta: một lời chào là một lời chào, và
# `test_loi_chao_KHONG_doi_ca_bai_nang_luc_vao_mat_nguoi_ta` khoá tỉ lệ độ dài
# (< 1/3 bài năng lực) thay vì khoá lời, để sửa câu chữ không làm nó đỏ oan.
CHAO = (
    "Chào bạn. Tôi tra cứu pháp luật lao động Việt Nam và soạn thảo văn bản pháp "
    "lý lao động.\n"
    "\n"
    "Bạn cứ kể thẳng chuyện đang gặp, càng cụ thể càng tốt — tôi trả lời kèm điều "
    "luật bạn bấm được để đọc nguyên văn. Muốn biết tôi làm được những gì thì hỏi "
    "luôn câu đó."
)

# Dạng 5 — cảm ơn.
CAM_ON = (
    "Không có gì. Chỗ nào trong câu trả lời bạn thấy chưa chắc thì bấm vào trích "
    "dẫn để đọc nguyên văn điều luật — hoặc hỏi tiếp, tôi còn ở đây."
)

# Dạng 6 — danh tính ("là ai" hỏi VAI). Mở đúng câu chủ dự án yêu cầu nguyên
# văn. Ba việc nêu ra đều có đường thật trong mã — tra cứu là `/api/v1/tra-cuu`,
# soạn thảo là `/api/v1/soan-thao`, rà soát là `/api/v1/soat` — không phải
# quảng cáo, và KHÔNG thêm việc thứ tư.
DANH_TINH = "\n\n".join((
    "Xin chào! Tôi là KLAW — trợ lý AI chuyên về pháp luật Việt Nam.",
    "Tôi giúp bạn ba việc:",
    "\n".join((
        "- 📖 Tra cứu pháp luật — nêu quy định kèm trích dẫn tới đúng điều, khoản, điểm của văn bản gốc.",
        "- 📝 Soạn thảo văn bản — hợp đồng lao động, nội quy lao động, quyết định kỷ luật.",
        "- 🔍 Rà soát văn bản — đối chiếu nội dung bắt buộc theo luật và chỉ ra điều khoản trái luật.",
    )),
    # Đoạn "Điều tôi khác các trợ lý khác…" đã gỡ (ex.md §4.2): người hỏi "bạn
    # là ai" không hỏi điểm khác biệt, và cùng đoạn đó còn nằm trong `NGUON` —
    # một câu ghép hai khía cạnh sẽ nói nó hai lần (FR-011).
    "Bạn đang cần tra cứu vấn đề gì, hay cần soạn văn bản nào?",
))

# Dạng 7 — bản chất ("là gì" hỏi BẢN CHẤT). Khác `DANH_TINH` đúng ở đoạn thứ
# hai: một bản tham chiếu không tự thuật được CƠ CHẾ chống ảo giác (hai tầng
# kiểm), và đó là lý do dạng này tồn tại riêng thay vì dội bài danh tính hay
# bài năng lực vào câu hỏi "là gì". Đừng cắt đoạn đó cho ngắn.
BAN_CHAT = "\n\n".join((
    "Về bản chất, tôi là một chương trình — một trợ lý AI làm riêng cho pháp luật Việt Nam, tên KLAW.",
    "\n".join((
        "- Tôi không phải luật sư, không phải thẩm phán, không phải cơ quan nhà nước. Tôi không có quyền ra phán quyết, và không đại diện cho bạn tại toà.",
        "- Tôi chạy trên mô hình ngôn ngữ, nhưng câu trả lời không thành hình vì mô hình tự tin. Mỗi trích dẫn phải qua hai tầng kiểm mới được hiện ra: tầng một so từng chữ câu trích với nguyên văn điều khoản trong chính văn bản luật — một phép so chuỗi thuần, nó không có cách nào tự thuyết phục được chính nó; tầng hai để một model khác họ đọc lại xem điều khoản đó có chống đỡ được câu đó không.",
        "- Không đủ căn cứ thì tôi nói thẳng là không đủ, không viết cho đủ bài.",
    )),
    "Việc quan trọng thì bạn vẫn nên đưa trích dẫn tôi dẫn cho luật sư xem cùng.",
))

_TIEN_TO_CHECKLIST = "checklist_"
# Cùng thư mục `config/` mà `graph_soan_thao.cac_loai()` đã glob — không import
# thẳng từ đó vì đó là một graph soạn thảo nặng (langgraph, sqlalchemy...) cho
# một quan hệ ngược chiều (node giới thiệu phụ thuộc vào graph khác); glob lại
# ba dòng này rẻ hơn nhiều so với kéo cả graph đó vào.
_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


def _loai_soan_thao() -> str:
    """Đếm & nhóm loại văn bản soạn thảo từ `config/checklist_*.yaml` LÚC GỌI,
    không phải hằng số đóng băng lúc import — cùng lý do `_model()` tra tên
    model từ config thay vì viết cứng: bản trước ghi cứng "ba loại" trong khi
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


# Khía cạnh `nang_luc` — làm được gì. MẶC ĐỊNH: câu không khớp khía cạnh nào
# rơi về đây.
#
# Bản trước (`_NANG_LUC_MAU`) trộn bốn mục đích trong một đoạn: năng lực, điểm
# khác biệt, danh sách phạm vi VIẾT CỨNG (sáu tên Bộ luật, bốn tên lĩnh vực) và
# cảnh báo độ sâu. Mọi câu hỏi về năng lực nhận cả bốn, và danh sách viết cứng
# lệch khỏi DB ngay lần nạp kho sau (ex.md §2.4, §2.5). Ba khía cạnh kia nay có
# khối riêng, dựng từ `kho.py` lúc chạy.
#
# CỐ Ý không nhúng số liệu corpus nào ở đây — kể cả số loại văn bản soạn thảo:
# nó thuộc khía cạnh `soan_thao`, chỉ nói khi người ta hỏi (ex.md §4.2).
NANG_LUC = "\n".join((
    "KLAW hiện làm ba việc chính:",
    "- Tra cứu và giải thích quy định theo tình huống của bạn, kèm trích dẫn mở được.",
    "- Soạn và rà soát văn bản pháp lý lao động theo checklist.",
    # "không đủ căn cứ" chứ không phải cụm cùng nghĩa bắt đầu bằng "chưa":
    # `test_giong_tra_loi.CUM_BI_CAM` cấm cụm kia vì đó là giọng bản abstain cũ.
    "- Nói rõ khi không đủ căn cứ, thay vì đoán luật hoặc kết quả vụ việc.",
))

# Dạng 4 — dữ liệu lấy từ đâu / có tin được không.
#
# Nêu TÊN nguồn, không in URL: `MOJ_API_BASE` là một endpoint nội bộ, và một
# đường dẫn API dán vào câu trả lời cho người dùng vừa không giúp gì vừa là một
# giá trị `.env` bị đưa ra ngoài.
#
# Đóng bằng chính `kho.CAU_GIOI_HAN` chứ không viết lại: đó là bản DUY NHẤT của
# câu giới hạn phạm vi, và một bản sao thứ hai sẽ lệch pha đúng vào ngày ai đó
# sửa một trong hai.
NGUON = "\n\n".join((
    "Văn bản tôi đọc lấy từ cơ sở dữ liệu quốc gia về văn bản pháp luật — bản "
    "công bố của cơ quan nhà nước, không phải một bản chép lại trên mạng.",
    "Hai điều bạn nên biết trước khi tin:",
    "- Tôi đọc bản GỐC của văn bản, không phải bản hợp nhất. Tôi bảo đảm trích đúng nguyên "
    "văn và đúng nguồn, và gắn nhãn hiệu lực cho từng trích dẫn — nhưng bản gốc "
    "không tự mang theo các lần sửa đổi về sau, nên việc quan trọng thì bạn vẫn "
    "nên đối chiếu bản hiện hành.\n"
    "- Mỗi câu tôi nói phải qua hai tầng kiểm mới được hiện ra: tầng một so từng "
    "chữ câu trích với điều khoản trong chính văn bản luật, tầng hai để một model khác đọc lại "
    "xem điều khoản đó có thật sự chống đỡ được câu đó không. Không qua được thì "
    "tôi nói thẳng là không đủ, không viết cho đủ bài.",
    CAU_GIOI_HAN,
))


def _model() -> str:
    """Dạng 3 — model nào / chạy bằng gì. TRA TỪ CONFIG, dựng lúc chạy.

    Không phải hằng số ở cấp module, và đó là chủ đích: một hằng số được đóng
    băng lúc import sẽ nói sai ngay sau lần đổi model đầu tiên.

    Nêu VAI của từng model chứ không chỉ liệt kê ba cái tên, vì điểm đáng nói ở
    đây là quan hệ giữa chúng: model thẩm định cố ý khác họ với model sinh
    (`llm.judge_model` cảnh báo khi hai cái trùng họ). Đó là một quyết định
    chống ảo giác, không phải một chi tiết kỹ thuật.
    """
    return "\n\n".join((
        "Tôi không phải một model. Tôi là một đường trả lời có ba model đứng ở ba "
        "vai khác nhau:",
        "\n".join((
            f"- Định tuyến câu hỏi: {router_model()}",
            f"- Sinh luận điểm và hành văn: {generate_model()}",
            f"- Thẩm định lại từng luận điểm: {judge_model()}",
        )),
        "Chỗ đáng nói không phải ba cái tên mà là dòng thứ ba: model thẩm định cố ý "
        "khác HỌ với model sinh. Một model đọc lại bài của chính họ thì thiên "
        "vị chính nó, và tầng thẩm định trở thành một sự yên tâm giả.",
        "Tầng kiểm trước đó thì không phải model nào cả: mỗi câu trích được so từng "
        "chữ với nguyên văn điều khoản trong chính văn bản luật. Đó là một phép so chuỗi — nó không "
        "có cách nào tự thuyết phục được chính nó.",
    ))


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
    "bo_luat": _RE_BO_LUAT,
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
_RE_META_MANH = re.compile(
    r"\b(?:bạn|klaw)\s+(?:làm|giúp|hỗ\s*trợ)\s+(?:được\s+)?(?:những\s+)?gì"
    r"|\b(?:bạn|klaw)\s+là\s+(?:ai|(?:cái\s+)?gì)\b"
    r"|những\s+(?:bộ\s+luật|lĩnh\s+vực)(?:\s+pháp\s+luật)?\s+(?:gì|nào)"
    r"|\bkho\s+(?:của\s+bạn\s+)?(?:có|phủ|gồm)"
    r"|model\s+(?:của\s+)?bạn|\bbạn\s+(?:dùng|chạy)\s+(?:model|mô\s*hình|ai)"
    r"|dữ\s*liệu\s+(?:của\s+bạn\s+)?(?:lấy|từ)"
    r"|bao\s+nhiêu\s+(?:văn\s+bản|bộ\s+luật)"
)
_RE_NOI_DUNG_LUAT = re.compile(r"\d|\bđiều\b|\bkhoản\b|nghị\s*định|thông\s*tư")


def chac_chan_meta(cau_hoi: str) -> bool:
    """True when the question is unmistakably about KLAW or the corpus and
    carries no legal-content marker; the router's LLM verdict is then
    overridden to gioi_thieu (0 tokens)."""
    c = _chuan(cau_hoi)
    return bool(_RE_META_MANH.search(c)) and not _RE_NOI_DUNG_LUAT.search(c)


# Guard in the other direction (decision 2026-09-29 item 4). Production
# 2026-09-29: the LLM router labelled "pháp luật Việt Nam chia thành những gì"
# `hoi_ve_kho` and the user got the KLAW introduction. A question about the
# Vietnamese legal system is answered from statute, so `route` turns such a
# meta verdict back into tra_cuu. Bare "hiến pháp"/"văn bản quy phạm" are left
# out: "có Hiến pháp 2013 không" asks whether the kho holds the document.
# Written without diacritics and matched on the folded question, so "luat",
# "luật" and a mistyped tone ("hệ thông") all match.
_RE_HE_THONG_PHAP_LUAT = re.compile(
    r"\b(?:luat(?:\s+phap)?|hien\s+phap)\s+(?:(?:cua|o|tai|nuoc)\s+)*(?:viet\s*nam|vn)\b"
    r"|\bluat(?:\s+phap)?\s+nuoc\s+ta\b"
    r"|\bhe\s+thong\s+(?:van\s+ban\s+)?(?:quy\s+pham\s+)?phap\s+luat"
    r"|\bloai\s+van\s+ban\s+(?:quy\s+pham\s+)?phap\s+luat"
    r"|\bvan\s+ban\s+(?:quy\s+pham\s+)?phap\s+luat\s+(?:duoc\s+)?(?:gom|chia|phan)\b"
    r"|\bnganh\s+luat|\bvb\s*qppl\b"
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
    ten = [d["linh_vuc"] for d in lv[:TOI_DA_LINH_VUC]]
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


def _mot_khoi(t: str, cau_hoi: str, kho: list[dict] | None) -> str:
    if t == "danh_tinh":
        return DANH_TINH
    if t == "ban_chat":
        return BAN_CHAT
    if t == "nang_luc":
        return NANG_LUC
    if t == "bo_luat":
        return _khoi_bo_luat(kho)
    if t == "linh_vuc":
        return _khoi_linh_vuc(kho)
    if t == "kho":
        return dung_cau_tra_loi(cau_hoi, kho)
    if t == "soan_thao":
        return (f"Tôi soạn được {_loai_soan_thao()}; hỏi cụ thể loại nào để xem "
                "checklist chi tiết.")
    if t == "nguon":
        return NGUON
    return _model()


def _cau_hoi_tiep(cac: list[str]) -> str:
    if can_kho(cac):
        return HOI_TIEP_KHO
    if "soan_thao" in cac:
        return HOI_TIEP_SOAN
    if "nang_luc" in cac:
        return HOI_TIEP_NANG_LUC
    return ""


def cau_gioi_thieu(cau_hoi: str, kho: list[dict] | None = None,
                   luot_dau: bool = True, cac_khia_canh: list[str] | None = None) -> str:
    """Lời đáp ghép từ các khía cạnh câu hỏi nêu, theo đúng thứ tự người hỏi.

    `kho` là snapshot đã nạp sẵn (`kho.nap_kho`), truyền vào chứ không tự truy
    vấn: node này là tầng THUẦN, và một lượt chỉ được nạp kho một lần (FR-014).
    `None` nghĩa là chỗ gọi chưa nạp — khi đó khía cạnh kho nhận `THIEU_KHO`
    chứ KHÔNG nhận một danh sách bịa. `cac_khia_canh` là các khía cạnh chỗ gọi
    đã tính (`khia_canh_kho` cho lượt `hoi_ve_kho`); `None` thì tính từ câu hỏi.

    Chào hỏi và cảm ơn xử lý TRƯỚC phân rã, như bản trước:
    - `_RE_CAM_ON` neo `^` VÀ chỉ ăn khi câu không nêu khía cạnh nào, nên "cảm
      ơn, mà dữ liệu lấy ở đâu" vẫn đi vào khối nguồn.
    - `_RE_CHAO` dùng `fullmatch` nên nó chỉ bắt lời chào ĐƠN THUẦN; "chào bạn,
      bạn làm được những gì" là một câu HỎI có lời chào dẫn vào.
    """
    c = _chuan(cau_hoi)
    vi = _khop(c)
    if _RE_CAM_ON.search(c) and not vi:
        return CAM_ON
    if _RE_CHAO.fullmatch(c):
        return CHAO

    cac = cac_khia_canh or _thu_tu(vi)
    khoi: list[str] = []
    for t in cac:
        if t in _KHIA_CANH_KHO and kho is None:
            if THIEU_KHO not in khoi:
                khoi.append(THIEU_KHO)
            continue
        khoi.append(_mot_khoi(t, cau_hoi, kho))

    # `NGUON` và khối `kho` đều TỰ đóng bằng `CAU_GIOI_HAN`, nên câu ghép cả
    # hai nói nó hai lần (FR-011). Giữ bản CUỐI để câu giới hạn vẫn đứng sát
    # cuối phần nội dung, gỡ các bản trước.
    cuoi = max((i for i, k in enumerate(khoi) if CAU_GIOI_HAN in k), default=-1)
    van = "\n\n".join(k if i == cuoi else k.removesuffix(CAU_GIOI_HAN).rstrip()
                      for i, k in enumerate(khoi))

    # Đúng MỘT lời mời tiếp tục, và nó phải là câu CUỐI — nên quyết định trước
    # khi ghép `CAU_GIOI_HAN` vào: khối cuối tự kết bằng một câu hỏi (`DANH_TINH`)
    # thì không thêm câu thứ hai.
    hoi = _cau_hoi_tiep(cac)
    if hoi and (van.rstrip().endswith("?") or hoi in van):
        hoi = ""

    # Câu giới hạn phạm vi đóng MỘT LẦN, và chỉ khi thật sự có một khối phạm vi
    # kho để giới hạn. `NGUON` và khối `kho` đã mang sẵn nó.
    if kho is not None and can_kho(cac) and CAU_GIOI_HAN not in van:
        van += "\n\n" + CAU_GIOI_HAN
    if hoi:
        van += "\n\n" + hoi

    if luot_dau and _RE_MO_DAU_CHAO.match(c):
        van = "Chào bạn. " + van
    return van
