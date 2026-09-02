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
from pathlib import Path

from src.services.kho import CAU_GIOI_HAN
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

# Dạng 6 — danh tính ("là ai" hỏi VAI). Mở đúng câu chủ dự án yêu cầu nguyên
# văn. Ba việc nêu ra đều có đường thật trong mã — tra cứu là `/api/v1/tra-cuu`,
# soạn thảo là `/api/v1/soan-thao`, rà soát là `/api/v1/soat` — không phải
# quảng cáo, và KHÔNG thêm việc thứ tư.
DANH_TINH = "\n\n".join((
    "Xin chào! Tôi là KLAW — trợ lý AI chuyên về pháp luật Việt Nam.",
    "Mình giúp bạn ba việc:",
    "\n".join((
        "- 📖 Tra cứu pháp luật — nêu quy định kèm trích dẫn tới đúng điều, khoản, điểm của văn bản gốc.",
        "- 📝 Soạn thảo văn bản — hợp đồng lao động, nội quy lao động, quyết định kỷ luật.",
        "- 🔍 Rà soát văn bản — đối chiếu nội dung bắt buộc theo luật và chỉ ra điều khoản trái luật.",
    )),
    "Điều mình khác các trợ lý khác: mỗi câu mình nói đều neo vào một trích dẫn bạn bấm được, và trước khi hiển thị, câu trích đó đã được đối chiếu từng chữ với văn bản gốc trong kho. Không đủ căn cứ thì mình nói thẳng là không đủ — mình không đoán.",
    "Bạn đang cần tra cứu vấn đề gì, hay cần soạn văn bản nào?",
))

# Dạng 7 — bản chất ("là gì" hỏi BẢN CHẤT). Khác `DANH_TINH` đúng ở đoạn thứ
# hai: một bản tham chiếu không tự thuật được CƠ CHẾ chống ảo giác (hai tầng
# kiểm), và đó là lý do dạng này tồn tại riêng thay vì dội bài danh tính hay
# bài năng lực vào câu hỏi "là gì". Đừng cắt đoạn đó cho ngắn.
BAN_CHAT = "\n\n".join((
    "Về bản chất, mình là một chương trình — một trợ lý AI làm riêng cho pháp luật Việt Nam, tên KLAW.",
    "\n".join((
        "- Mình không phải luật sư, không phải thẩm phán, không phải cơ quan nhà nước. Mình không có quyền ra phán quyết, và không đại diện cho bạn tại toà.",
        "- Mình chạy trên mô hình ngôn ngữ, nhưng câu trả lời không thành hình vì mô hình tự tin. Mỗi trích dẫn phải qua hai tầng kiểm mới được hiện ra: tầng một so từng chữ câu trích với nguyên văn điều khoản trong kho — một phép so chuỗi thuần, nó không có cách nào tự thuyết phục được chính nó; tầng hai để một model khác họ đọc lại xem điều khoản đó có chống đỡ được câu đó không.",
        "- Không đủ căn cứ thì mình nói thẳng là không đủ, không viết cho đủ bài.",
    )),
    "Việc quan trọng thì bạn vẫn nên đưa trích dẫn mình dẫn cho luật sư xem cùng.",
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


# Dạng 2 — làm được gì. MẶC ĐỊNH: câu không khớp dạng nào rơi về đây.
#
# KHÔNG còn trả lời "là ai" (T3 tách sang `DANH_TINH`/`BAN_CHAT` ở trên — chủ
# dự án đọc và nói "bạn là ai" phải ra danh tính, không phải bài năng lực).
# Dạng này giờ CHỈ còn trả lời "làm được những gì", đúng tên của nó.
#
# CỐ Ý không nhúng số liệu corpus (số văn bản, số điều khoản): chúng đổi mỗi lần
# mở rộng kho, và một con số cũ nằm trong lời tự giới thiệu là kiểu sai khó phát
# hiện nhất — không test nào đỏ, không ai đọc lại. Câu hỏi về kho đã có đường
# riêng (`intent=hoi_ve_kho` → `services/kho.py`) đọc thẳng từ DB. Số loại văn
# bản soạn thảo là NGOẠI LỆ được phép nêu: nó tra từ `_loai_soan_thao()` lúc
# gọi, không viết cứng, nên không lệch pha kiểu "ba loại" cũ.
#
# Nói được mình làm gì mà không nói được mình CHƯA SÂU tới đâu thì là quảng
# cáo, không phải câu trả lời trung thực — nên đoạn giới hạn nằm ngay trong này
# chứ không nằm ở một trang khác người hỏi phải tự tìm. Kho vừa mở sang 8 lĩnh
# vực (T1) nhưng KHÔNG đều: chỉ Lao động có đủ luật + nghị định + thông tư +
# chế tài, các lĩnh vực khác mới có luật gốc — nói "chưa phủ" các lĩnh vực đó
# (câu cũ) nay SAI, nên đoạn giới hạn đổi từ liệt kê CÁI GÌ CHƯA CÓ sang nói
# ĐỘ SÂU không đều.
#
# KHÔNG còn mở bằng "Chào bạn.": lời chào nay là dạng 1, và một câu chào dán
# trước bảng model hay trước câu trả lời về nguồn dữ liệu là đúng chỗ người đọc
# thấy máy móc.
_NANG_LUC_MAU = "\n\n".join((
    "Mình tra cứu pháp luật Việt Nam và soạn thảo văn bản pháp lý lao động.",
    "Điều mình làm khác các trợ lý khác: mỗi câu mình nói đều neo vào một trích dẫn "
    "bạn bấm được để mở đúng nguyên văn điều luật, và trước khi hiển thị, câu trích "
    "đó đã được đối chiếu từng chữ với văn bản gốc. Không đủ căn cứ thì mình nói "
    "thẳng là không đủ — mình không đoán.",
    "Bạn hỏi được: quyền lợi khi bị trừ lương hay cho nghỉ việc, thời giờ làm việc "
    "và nghỉ phép, hợp đồng lao động, kỷ luật lao động, an toàn lao động, và nội "
    "dung của sáu Bộ luật (Dân sự, Hình sự, Tố tụng dân sự, Tố tụng hình sự, Lao "
    "động, Hàng hải). Mình soạn được {soan_thao}, hỏi cụ thể loại nào để biết "
    "checklist chi tiết.",
    "Chiều sâu không đều: riêng Lao động có đủ luật, nghị định, thông tư và chế "
    "tài. Các lĩnh vực khác — như thuế, đất đai, hôn nhân gia đình, doanh nghiệp — "
    "hiện chỉ có luật gốc, chưa có văn bản hướng dẫn. Và kho của mình là văn bản "
    "gốc, không phải bản hợp nhất, nên việc quan trọng thì bạn vẫn nên đối chiếu "
    "bản hiện hành.",
))


def _nang_luc() -> str:
    """Dựng lúc GỌI, không phải hằng số đóng băng lúc import: số loại văn bản
    soạn thảo phải khớp `config/checklist_*.yaml` THẬT tại thời điểm trả lời,
    cùng lý do `_model()` không phải hằng số cấp module."""
    return _NANG_LUC_MAU.format(soan_thao=_loai_soan_thao())

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
    2. `_RE_LA_AI`/`_RE_BAN_CHAT` SAU `_RE_MODEL`/`_RE_NGUON`: "model của bạn là
       ai" và "bạn chạy bằng mô hình gì" phải vẫn ra bảng model, không rơi vào
       danh tính/bản chất — do THỨ TỰ kiểm, không phải do mẫu tự loại trừ nhau.
       Giữa hai dạng mới: `là ai` hỏi VAI → `DANH_TINH`, `là gì` hỏi BẢN CHẤT →
       `BAN_CHAT`. "bạn là ai" và "bạn là gì" chỉ khác một từ và PHẢI ra hai lời
       đáp khác nhau — đây là phép canh trung tâm chủ dự án yêu cầu.
    3. `_RE_CAM_ON` neo `^` nên nó KHÔNG cướp "cảm ơn, mà dữ liệu lấy ở đâu".
    4. `_RE_CHAO` dùng `fullmatch` nên nó chỉ bắt lời chào ĐƠN THUẦN.

    Không khớp dạng nào → `_nang_luc()`. Đây là mặc định an toàn hiện nay: lời
    đáp đầy đủ nhất, và là lời đáp duy nhất trong nhóm nói ra cả thứ mình CHƯA
    sâu tới đâu. Mặc định ngược lại (im lặng, hoặc một câu chào) đưa người hỏi
    về đúng màn hình trắng mà cả pha này tồn tại để bỏ đi.
    """
    c = _chuan(cau_hoi)
    if _RE_MODEL.search(c):
        return _model()
    if _RE_NGUON.search(c):
        return NGUON
    if _RE_LA_AI.search(c):
        return DANH_TINH
    if _RE_BAN_CHAT.search(c):
        return BAN_CHAT
    if _RE_CAM_ON.search(c):
        return CAM_ON
    if _RE_CHAO.fullmatch(c):
        return CHAO
    return _nang_luc()
