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

from src.services.kho import CAU_GIOI_HAN
from src.services.llm import generate_model, judge_model, router_model

# ══ Nhận diện dạng câu hỏi — QUY TẮC, 0 token ════════════════════════════════
#
# Rẻ được là nhờ ngữ cảnh, đúng như `kho.moi_so_hieu_trong`: các biểu thức dưới
# đây chỉ chạy khi `route` đã kết luận câu hỏi là `gioi_thieu`, nên chúng không
# phải tự phân biệt "hỏi về trợ lý" với "hỏi nội dung luật" — chỉ phải tách
# DẠNG trong một câu đã biết là hỏi về trợ lý.

# Model / công nghệ. `\bai\s+(?:nào|gì)\b` chứ không phải `ai` trần: "ai" trong
# tiếng Việt là đại từ nghi vấn, và "bạn là ai" phải rơi về bài năng lực (dạng
# 2) chứ không phải bảng model — `test_dang_LA_roi_ve_bai_nang_luc…` khoá đúng
# câu đó.
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
    "Chào bạn. Mình tra cứu pháp luật lao động Việt Nam và soạn thảo văn bản pháp "
    "lý lao động.\n"
    "\n"
    "Bạn cứ kể thẳng chuyện đang gặp, càng cụ thể càng tốt — mình trả lời kèm điều "
    "luật bạn bấm được để đọc nguyên văn. Muốn biết mình làm được những gì thì hỏi "
    "luôn câu đó."
)

# Dạng 5 — cảm ơn.
CAM_ON = (
    "Không có gì. Chỗ nào trong câu trả lời bạn thấy chưa chắc thì bấm vào trích "
    "dẫn để đọc nguyên văn điều luật — hoặc hỏi tiếp, mình còn ở đây."
)

# Dạng 2 — làm được gì / là ai. MẶC ĐỊNH: câu không khớp dạng nào rơi về đây.
#
# CỐ Ý không nhúng số liệu corpus (số văn bản, số điều khoản): chúng đổi mỗi lần
# mở rộng kho, và một con số cũ nằm trong lời tự giới thiệu là kiểu sai khó phát
# hiện nhất — không test nào đỏ, không ai đọc lại. Câu hỏi về kho đã có đường
# riêng (`intent=hoi_ve_kho` → `services/kho.py`) đọc thẳng từ DB.
#
# Nói được mình làm gì mà không nói được mình KHÔNG làm gì thì là quảng cáo,
# không phải câu trả lời trung thực — nên đoạn giới hạn nằm ngay trong này chứ
# không nằm ở một trang khác người hỏi phải tự tìm.
#
# KHÔNG còn mở bằng "Chào bạn.": lời chào nay là dạng 1, và một câu chào dán
# trước bảng model hay trước câu trả lời về nguồn dữ liệu là đúng chỗ người đọc
# thấy máy móc.
NANG_LUC = (
    "Mình tra cứu pháp luật Việt Nam và soạn thảo văn bản pháp lý lao động.\n"
    "\n"
    "Điều mình làm khác các trợ lý khác: mỗi câu mình nói đều neo vào một trích dẫn "
    "bạn bấm được để mở đúng nguyên văn điều luật, và trước khi hiển thị, câu trích "
    "đó đã được đối chiếu từng chữ với văn bản gốc. Không đủ căn cứ thì mình nói "
    "thẳng là không đủ — mình không đoán.\n"
    "\n"
    "Bạn hỏi được: quyền lợi khi bị trừ lương hay cho nghỉ việc, thời giờ làm việc "
    "và nghỉ phép, hợp đồng lao động, kỷ luật lao động, an toàn lao động, và nội "
    "dung của sáu Bộ luật (Dân sự, Hình sự, Tố tụng dân sự, Tố tụng hình sự, Lao "
    "động, Hàng hải). Mình soạn được hợp đồng lao động, nội quy lao động và quyết "
    "định kỷ luật.\n"
    "\n"
    "Mình chưa phủ: thuế, đất đai, hôn nhân gia đình, doanh nghiệp, đầu tư, sở hữu "
    "trí tuệ. Chiều sâu cũng không đều — riêng Lao động mới có đủ luật, nghị định, "
    "thông tư và chế tài. Và kho của mình là văn bản gốc, không phải bản hợp nhất, "
    "nên việc quan trọng thì bạn vẫn nên đối chiếu bản hiện hành."
)

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
    "Kho của mình dựng từ cơ sở dữ liệu quốc gia về văn bản pháp luật — bản công "
    "bố của cơ quan nhà nước, không phải một bản chép lại trên mạng.",
    "Hai điều bạn nên biết trước khi tin:",
    "- Kho là văn bản GỐC, không phải bản hợp nhất. Mình bảo đảm trích đúng nguyên "
    "văn và đúng nguồn, và gắn nhãn hiệu lực cho từng trích dẫn — nhưng bản gốc "
    "không tự mang theo các lần sửa đổi về sau, nên việc quan trọng thì bạn vẫn "
    "nên đối chiếu bản hiện hành.\n"
    "- Mỗi câu mình nói phải qua hai tầng kiểm mới được hiện ra: tầng một so từng "
    "chữ câu trích với điều khoản trong kho, tầng hai để một model khác đọc lại "
    "xem điều khoản đó có thật sự chống đỡ được câu đó không. Không qua được thì "
    "mình nói thẳng là không đủ, không viết cho đủ bài.",
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
        "Mình không phải một model. Mình là một đường trả lời có ba model đứng ở ba "
        "vai khác nhau:",
        "\n".join((
            f"- Định tuyến câu hỏi: {router_model()}",
            f"- Sinh luận điểm và hành văn: {generate_model()}",
            f"- Thẩm định lại từng luận điểm: {judge_model()}",
        )),
        "Chỗ đáng nói không phải ba cái tên mà là dòng thứ ba: model thẩm định cố ý "
        "khác HỌ với model sinh. Một model đọc lại bài của chính họ mình thì thiên "
        "vị chính nó, và tầng thẩm định trở thành một sự yên tâm giả.",
        "Tầng kiểm trước đó thì không phải model nào cả: mỗi câu trích được so từng "
        "chữ với nguyên văn điều khoản trong kho. Đó là một phép so chuỗi — nó không "
        "có cách nào tự thuyết phục được chính nó.",
    ))


def cau_gioi_thieu(cau_hoi: str) -> str:
    """Một lời đáp cho MỖI dạng câu hỏi, chọn bằng quy tắc.

    Thứ tự CÓ Ý NGHĨA — dạng hẹp trước dạng rộng:

    1. `_RE_MODEL` trước `_RE_NGUON` vì "model" là dấu hiệu hẹp hơn "dữ liệu" hay
       "ở đâu", và câu hỏi về model chính là câu đã đo được lỗi. Câu ghép cả hai
       ("model của bạn lấy dữ liệu ở đâu") nhận lời đáp về model — một lựa chọn,
       không phải một sự tình cờ.
    2. `_RE_CAM_ON` neo `^` nên nó KHÔNG cướp "cảm ơn, mà dữ liệu lấy ở đâu".
    3. `_RE_CHAO` dùng `fullmatch` nên nó chỉ bắt lời chào ĐƠN THUẦN.

    Không khớp dạng nào → `NANG_LUC`. Đây là mặc định an toàn hiện nay: lời đáp
    đầy đủ nhất, và là lời đáp duy nhất trong nhóm nói ra cả thứ mình KHÔNG làm.
    Mặc định ngược lại (im lặng, hoặc một câu chào) đưa người hỏi về đúng màn
    hình trắng mà cả pha này tồn tại để bỏ đi.
    """
    c = _chuan(cau_hoi)
    if _RE_MODEL.search(c):
        return _model()
    if _RE_NGUON.search(c):
        return NGUON
    if _RE_CAM_ON.search(c):
        return CAM_ON
    if _RE_CHAO.fullmatch(c):
        return CHAO
    return NANG_LUC
