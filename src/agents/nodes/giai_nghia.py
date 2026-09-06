"""Node đầu vào của lượt hỏi NỐI TIẾP: làm câu hỏi tự đứng được, không hơn.

ĐO ĐƯỢC 2026-09-02, bảng `traces`, ba lượt liền nhau của chủ dự án:

    10:19  "tôi đang chuẩn bị nghỉ việc"   answer            21 claim   42,1s
    10:19  "bạn làm được những gì"         gioi_thieu         0 claim    1,1s
    10:20  "liệt kê bảng cho tôi"          partial_coverage   0 claim    8,5s

Lượt thứ ba trỏ về CÁI BẢNG trong câu trả lời của lượt thứ nhất. `TraCuuRequest`
chỉ có `query` nên nó được xử lý như một câu độc lập, và một câu rỗng nội dung
pháp lý thì khớp NHIỄU: 120/2025/QH15 (Luật Phòng chống ma túy) và 8532 (Luật
Thương mại). Pipeline lõi không hỏng — lượt đầu cho 21 luận điểm qua cả hai
tầng — cái thiếu là ngữ cảnh giữa các lượt.

## Nguyên tắc ràng buộc (spec mục 2), và vì sao client-gửi-lịch-sử là an toàn

Lịch sử hội thoại CHỈ dùng để làm câu hỏi tự đứng được. Nó KHÔNG BAO GIỜ chống
đỡ một khẳng định: câu sau khi giải nghĩa đi qua ĐỦ truy hồi → tầng 1 → tầng 2
như một câu hỏi mới. Hệ quả là một lịch sử bịa (client gửi gì cũng được, và khối
lịch sử đi thẳng vào một prompt) chỉ tạo ra một câu hỏi KHÁC, rồi câu đó vẫn
phải chịu đủ hai tầng kiểm — không có đường nào lách verifier, nên không cần
session phía server.

## Vì sao node này vẫn cần MỘT lưới chặn riêng

Hai tầng kiểm chứng đọc câu TRẢ LỜI, không đọc câu HỎI. Một số Điều bịa trong
câu hỏi đi qua chúng mà không vướng gì: nó chỉ lặng lẽ lái truy hồi sang một
điều luật người hỏi chưa từng nhắc, và câu trả lời sau đó có trích dẫn thật cho
một câu hỏi thật ra không phải của họ. Đây là lớp ảo giác thứ hai mà verifier mù
với (lớp thứ nhất là câu hỏi lại — xem `hoi_lai.py`), nên chỗ chặn duy nhất là
`dinh_danh_bia`: một phép SO TẬP trên chính chuỗi, 0 token, TRƯỚC khi câu đã
giải nghĩa được đem đi tra.

## Vì sao lỗi hạ tầng ở đây phải NỔ, khác `rewrite_query`

Đây là bước QUYẾT ĐỊNH câu nào được đem đi tra — cùng hạng với `route`, không
phải một bước mở rộng như `rewrite_query`. Một 429 rơi êm thành "không đủ ngữ
cảnh" sẽ đẩy một câu hỏi hợp lệ vào đường ngõ cụt mà không ai biết vì sao, và
chương đánh giá đọc dòng đó thành một lượt abstain thật. Nên `llm.chat` nằm
NGOÀI `try`, đúng khuôn `route.py`; chỉ ĐẦU RA dị dạng của model mới rơi về mặc
định an toàn.
"""

import json
import logging
from pathlib import Path
from typing import NamedTuple

from src.agents.nodes.assemble import _so_dieu_trong
from src.agents.nodes.hoi_lai import moc_phap_ly_trong
from src.services.kho import moi_so_hieu_trong
from src.services.llm import Usage
from src.services.prompts import messages

logger = logging.getLogger(__name__)

PROMPT_PATH = Path("prompts/giai_nghia.v1.md")

# Câu trả lời cũ bị cắt còn bấy nhiêu ký tự khi dựng prompt. `"liệt kê bảng"`
# cần biết câu trả lời trước CÓ một cái bảng — chừng đó là đủ; toàn văn (câu trả
# lời thật của lượt 10:19 dài hơn 4.000 ký tự) làm prompt phình mà không thêm
# tín hiệu, và prompt này chạy MỖI lượt nối tiếp.
#
# Cắt Ở ĐÂY, không ở biên HTTP: đây là một trần NGÂN SÁCH PROMPT, nên client
# không phải biết con số này, và một lượt gửi toàn văn không bị 422 oan.
TOI_DA_TRA_LOI = 400

# `"cau_hoi_day_du": ""` là cách nói "không đủ ngữ cảnh", KHÔNG dùng `null`.
# `"type": ["string", "null"]` không phải hình dạng mọi provider structured
# output nhận, và một schema bị từ chối ở tầng API biến mọi lượt nối tiếp thành
# lỗi hạ tầng. Chuỗi rỗng thì mọi provider đều trả được, và `giai_nghia` quy nó
# về `None` ngay tại biên Python — nơi spec mục 3 đòi `str | None`.
GIAI_NGHIA_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cau_hoi_day_du", "ly_do"],
    "properties": {
        "cau_hoi_day_du": {"type": "string"},
        "ly_do": {"type": "string"},
    },
}


class KetQuaGiaiNghia(NamedTuple):
    """`usage` khác None cả khi `nguon != "llm"`: một JSON dị dạng hay một câu bị
    lưới chặn loại vẫn đã tiêu token thật, và một lượt gọi không đếm được là một
    lượt vô hình với trần chi phí ngày."""

    cau_hoi_day_du: str | None
    ly_do: str
    usage: Usage | None
    # NĂM giá trị CỐ ĐỊNH: "llm" (giải nghĩa được), "khong_du_ngu_canh" (model
    # tự nói không biết), "sai_dinh_dang" (JSON dị dạng), "bi_loai" (lưới chặn
    # nổ), "luot_dau" (lịch sử rỗng, không gọi LLM). Cardinality hữu hạn để
    # trace đếm được — cùng lý do `hoi_lai.nguon` giữ đúng hai giá trị và không
    # nhét tên exception vào. "luot_dau" đáng một giá trị riêng chứ không phải
    # `None`: nó là bằng chứng đo được cho tuyên bố "lượt đầu 0 token thêm".
    nguon: str


def ngu_canh(lich_su: list[dict]) -> str:
    """Khối lịch sử ĐÚNG NHƯ nó đi vào prompt.

    Là chỗ duy nhất dựng khối này, và `dinh_danh_bia` so với chính đầu ra của
    hàm này: model chỉ có thể lấy một số Điều từ những gì nó ĐƯỢC CHO XEM, nên
    tập đối chiếu của lưới chặn phải là đúng tập đó, không phải toàn văn lịch
    sử. So với toàn văn sẽ tha cho một số Điều nằm ngoài đoạn đã cắt — mà cái đó
    thì model chưa từng thấy, tức nó bịa ra.
    """
    khoi: list[str] = []
    for i, luot in enumerate(lich_su, start=1):
        tra_loi = str(luot.get("tra_loi") or "")
        cat = tra_loi[:TOI_DA_TRA_LOI] + ("…" if len(tra_loi) > TOI_DA_TRA_LOI else "")
        duong_dan = [str(d) for d in (luot.get("duong_dan") or []) if d]
        khoi.append(
            f"Lượt {i}\n"
            f"  Người hỏi: {luot.get('cau_hoi') or ''}\n"
            f"  KLAW đã trả lời: {cat}"
            + (f"\n  Điều khoản đã dẫn: {'; '.join(duong_dan)}" if duong_dan else "")
        )
    return "\n".join(khoi)


def dinh_danh_bia(cau_da_giai: str, cau_goc: str, lich_su: list[dict]) -> list[str]:
    """Định danh pháp lý có trong câu ĐÃ GIẢI NGHĨA mà KHÔNG có ở câu gốc lẫn
    trong khối lịch sử. Rỗng nghĩa là sạch.

    Quy tắc, 0 token, và cố ý THÔ theo đúng một chiều: thà loại oan một câu sạch
    (rơi về đường ngõ cụt, người hỏi vẫn được hỏi lại) còn hơn để một số Điều
    không ai nhắc lái cả lượt truy hồi.

    Hai họ định danh, mỗi họ dùng lại bộ nhận diện ĐÃ CÓ thay vì dựng bản thứ
    hai của cùng quy tắc:

    * số Điều — `assemble._so_dieu_trong` (đã chuẩn hoá `Ð` U+00D0 / `Đ` U+0110,
      corpus có cả hai);
    * số hiệu văn bản — `kho.moi_so_hieu_trong`, dạng `số/năm`. Cố ý dùng bản
      LỎNG này chứ không phải `assemble._RE_SO_KY_HIEU` (đòi đủ hậu tố loại văn
      bản): ở đây cần bắt MỌI số hiệu bịa, kể cả "145/2020" viết thiếu đuôi —
      đúng cách người ta thật sự gõ;
    * **mốc pháp lý** — `hoi_lai.moc_phap_ly_trong` (số + đơn vị thời hạn/tiền/
      phần trăm, cả dạng viết bằng chữ). ĐO ĐƯỢC 2026-09-02 (review): thiếu họ
      này thì `dinh_danh_bia("… báo trước 45 ngày … trừ 30% lương …", cau_goc,
      [])` trả RỖNG, dù prompt (ràng buộc 2) cấm đúng bốn thứ đó. Và KHÔNG tầng
      nào kiểm tiền đề của câu HỎI — hai tầng kiểm đối chiếu câu TRẢ LỜI với văn
      bản, nên một mốc bịa đi vào truy hồi rồi mọi khẳng định sinh ra sau đó đều
      kiểm chứng được, về một câu hỏi không ai đặt.
    """
    nguon = "\n".join([cau_goc, ngu_canh(lich_su)])
    dieu = sorted(_so_dieu_trong(cau_da_giai) - _so_dieu_trong(nguon), key=int)
    so_hieu = sorted(set(moi_so_hieu_trong(cau_da_giai)) - set(moi_so_hieu_trong(nguon)))
    moc = sorted(moc_phap_ly_trong(cau_da_giai) - moc_phap_ly_trong(nguon))
    return [f"Điều {d}" for d in dieu] + so_hieu + moc


def _goi(cau_hoi: str, lich_su: list[dict], llm, model: str) -> KetQuaGiaiNghia:
    """Một lượt giải nghĩa. Tầng gần LLM nhất, tách khỏi phần ghi state để phần
    dựng prompt và lưới chặn kiểm được mà không cần một `KLawState`."""
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        cau_hoi=cau_hoi, lich_su=ngu_canh(lich_su))
    # NGOÀI try — xem docstring module: lỗi hạ tầng ở một bước quyết định phải
    # nổ ra ngoài, không được rơi êm thành "không đủ ngữ cảnh".
    raw, usage = llm.chat(model, messages(prompt), json_schema=GIAI_NGHIA_SCHEMA)
    try:
        ra = json.loads(raw)
        day_du = " ".join(str(ra.get("cau_hoi_day_du") or "").split())
        ly_do = str(ra.get("ly_do") or "")
    except Exception as e:
        # `exc_info=True` cùng lý do với `hoi_lai`: operator cần biết DÒNG nào
        # ném ra, không chỉ tên exception.
        logger.warning("giai_nghia: đầu ra dị dạng (%s: %s) — coi như không giải nghĩa được",
                       type(e).__name__, e, exc_info=True)
        return KetQuaGiaiNghia(None, "", usage, "sai_dinh_dang")

    if not day_du:
        # Model tự nói không đủ ngữ cảnh (ràng buộc 5 của prompt). Đây là câu trả
        # lời ĐÚNG, không phải một lỗi — mặc định an toàn khi không chắc.
        return KetQuaGiaiNghia(None, ly_do, usage, "khong_du_ngu_canh")

    if bia := dinh_danh_bia(day_du, cau_hoi, lich_su):
        # Đếm được bằng log, không im lặng: lưới này là chỗ chặn duy nhất cho
        # đúng lớp ảo giác mà verifier mù với, nên tần suất nó nổ là số liệu.
        logger.warning(
            "giai_nghia: câu đã giải nghĩa thêm định danh pháp lý không có ở câu gốc lẫn "
            "lịch sử (%s) — bỏ, đi đường ngõ cụt. Câu bị loại: %r",
            ", ".join(bia), day_du,
        )
        return KetQuaGiaiNghia(None, ly_do, usage, "bi_loai")

    return KetQuaGiaiNghia(day_du, ly_do, usage, "llm")


def giai_nghia(state: dict, llm, model: str) -> dict:
    """Node đầu vào. `query` bị THAY bằng câu đã giải nghĩa để cả pipeline chạy
    trên nó; `cau_hoi_goc` giữ nguyên câu người dùng gõ.

    `cau_hoi_goc` KHÔNG phải là cái đi vào `traces.query` (endpoint ghi thẳng
    `req.query`, xem `api/routes.py`) — nó là bằng chứng trong state rằng câu
    hỏi đã bị thay, để một node hạ nguồn hay một lượt gỡ lỗi không phải suy ra
    điều đó từ `cau_hoi_day_du`.

    Lịch sử rỗng → RA NGAY, 0 token. Graph đã có nhánh vào không đi qua node này
    cho lượt đầu (`_vao_graph`), nên nhánh ở đây là lưới thứ hai: một chỗ gọi
    trực tiếp hàm này với lịch sử rỗng cũng không được tốn một lượt gọi nào.
    """
    prior_traces = state.get("traces") or {}
    goc = state["query"]
    lich_su = state.get("lich_su") or []

    ket = (_goi(goc, lich_su, llm, model) if lich_su
           else KetQuaGiaiNghia(None, "lượt đầu, không có lịch sử", None, "luot_dau"))
    return {
        **state,
        "cau_hoi_goc": goc,
        "cau_hoi_day_du": ket.cau_hoi_day_du,
        # Không giải nghĩa được thì KHÔNG sửa câu hỏi. `_re_sau_giai_nghia` rẽ
        # lượt đó sang `assemble` (đường ngõ cụt đã có), nên `query` ở đây chỉ
        # còn phục vụ `hoi_lai` — và nó phải hỏi lại về đúng câu người ta gõ.
        "query": ket.cau_hoi_day_du or goc,
        "traces": {
            **prior_traces,
            "giai_nghia_model": model,
            "giai_nghia_nguon": ket.nguon,
            "giai_nghia_token_in": ket.usage.token_in if ket.usage else 0,
            "giai_nghia_token_out": ket.usage.token_out if ket.usage else 0,
            "giai_nghia_cost_usd": ket.usage.cost_usd if ket.usage else 0.0,
        },
    }
