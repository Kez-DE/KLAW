"""Nửa sau của mọi ngõ cụt: hỏi lại đúng DỮ KIỆN TÌNH HUỐNG còn thiếu.

ĐO ĐƯỢC 2026-09-02: khi truy vấn không dựng nổi một luận điểm nào, mọi nhánh
của `assemble` đều kết thúc bằng một danh sách văn bản — hoặc bằng không gì cả.
Cả hai đều đẩy việc suy luận về phía người hỏi, tức trả lại đúng câu hỏi mà họ
đến để nhờ trả lời.

## Vì sao gọi LLM, và vì sao model KHÔNG được tự chọn từ vựng

Một câu hỏi lại chung chung ("bạn cho thêm thông tin nhé") chính là cái máy móc
mà pha này tồn tại để bỏ, nên câu hỏi phải bám vào câu hỏi thật — việc đó cần
model. Nhưng TỪ VỰNG CHIỀU HỎI là hằng số trong mã (`CHIEU`): model chỉ chọn
TRONG danh sách đó chiều nào còn thiếu, và prompt được BƠM từ chính `CHIEU` nên
file prompt không thể lệch pha với mã.

## Vì sao bộ lọc bằng quy tắc là BẮT BUỘC, không phải một lớp trang trí

"Hợp đồng của bạn dưới 12 tháng không?" đã KHẲNG ĐỊNH mốc 12 tháng có ý nghĩa
pháp lý. Không trích dẫn nào chống đỡ khẳng định đó, và hai tầng kiểm chứng
KHÔNG bắt được — chúng kiểm claim, còn ở đây không có claim nào để kiểm. Đây là
lớp ảo giác duy nhất trong hệ thống mà verifier mù với, nên chỗ chặn duy nhất là
một bộ lọc trên chính chuỗi, TRƯỚC khi nó tới màn hình. Bị loại thì rơi về câu
hằng số của đúng chiều đó — câu đã sinh KHÔNG được hiển thị.

Vì thế mọi câu trong `CHIEU` đều phải tự qua được bộ lọc của chính nó
(`test_moi_cau_hang_so_deu_qua_duoc_bo_loc_cua_chinh_no`): một câu mặc định tự
vướng bộ lọc sẽ làm đường suy biến trả về rỗng, tức vẫn là màn hình trắng.
"""

import json
import logging
import re
from pathlib import Path
from typing import NamedTuple

from src.services.llm import Usage
from src.services.prompts import messages

logger = logging.getLogger(__name__)

PROMPT_PATH = Path("prompts/hoi_lai.v1.md")

# Trần HAI chiều (hạ từ ba — Task 14, phản hồi trực tiếp của chủ đề tài: hỏi
# nhiều thành một tờ khai, không phải một câu hỏi). Ép Ở MÃ, không chỉ ở prompt:
# `maxItems` trong schema và trần này cùng canh một con số, vì một model bỏ qua
# lời dặn vẫn phải bị cắt.
TOI_DA = 2

# Sáu chiều — DỮ KIỆN của người hỏi, không phải quy tắc pháp luật. Mỗi câu ở đây
# vừa là hướng dẫn cho model (được bơm vào prompt) vừa là CÂU DỰ BỊ dùng khi câu
# model sinh bị bộ lọc loại, nên chúng phải đọc được nguyên vẹn một mình.
#
# Cố ý KHÔNG có chiều nào chứa con số: xem docstring module. "Hợp đồng của bạn
# ghi thời hạn thế nào" hỏi cái ghi trên giấy của họ; "hợp đồng của bạn dưới 12
# tháng không" thì đã phát biểu thay cho luật.
CHIEU = {
    "chu_the": "Bạn đang ở phía nào — người lao động hay công ty?",
    "loai_hop_dong": "Hợp đồng của bạn ghi thời hạn thế nào — bao lâu, hay không ghi thời hạn?",
    "tham_nien": "Bạn đã làm ở chỗ đó bao lâu rồi?",
    "vung_luong": "Công ty bạn đóng ở tỉnh hay thành phố nào?",
    "thoi_diem": "Chuyện này xảy ra vào khoảng thời gian nào?",
    "van_ban_da_co": "Bạn đang giữ những giấy tờ nào về việc này — hợp đồng, quyết định, thông báo?",
}

# Dùng khi model không cho được chiều nào dùng được (lỗi mạng, JSON sai hình
# dạng, danh sách rỗng). Ba chiều áp được cho gần như mọi câu hỏi lao động, nên
# đường suy biến vẫn hỏi được một câu thật thay vì trả về chuỗi rỗng — một chuỗi
# rỗng ở đây LÀ màn hình trắng.
MAC_DINH = ("chu_the", "loai_hop_dong", "thoi_diem")

# Câu dẫn — HẰNG SỐ, không do model sinh, cùng lý do với `kho.CAU_GIOI_HAN`.
CAU_DAN = "Để trả lời chắc chắn, tôi cần bạn cho biết thêm:"

# Ba dạng đều là một PHÁT BIỂU VỀ LUẬT đội lốt câu hỏi. `Ð` U+00D0 nằm cạnh `Đ`
# U+0110 vì corpus có cả hai và một bộ lọc chỉ biết một chữ sẽ để lọt dạng còn
# lại. `\s*` quanh dấu gạch chéo để "145 / 2020 /" không lách qua.
# Số viết bằng CHỮ và bằng chữ số là cùng một phát biểu pháp luật, chỉ khác
# chính tả. ĐO ĐƯỢC 2026-09-02 (review): cả ba pattern đầu đều BẮT BUỘC có chữ số
# Ả Rập (`all('\\d' in p.pattern ...) == True`), nên bộ lọc chặn "dưới 12 tháng" mà
# để lọt "dưới một năm" — và bảy ca test cũ đều viết bằng chữ số nên không cái nào
# đỏ. Lỗ hổng im lặng ở đúng chỗ module này tự nhận là "chỗ chặn duy nhất".
#
# Tập từ số tiếng Việt là tập ĐÓNG, liệt kê được — nên mở rộng theo hướng này
# giữ đúng bản chất "quy tắc, 0 token" của bộ lọc, không biến nó thành một danh
# sách từ khoá pháp lý mở (xem docstring `bi_loai` về vì sao KHÔNG làm thế).
# `lăm` và `mốt` là DẠNG GHÉP bắt buộc của tiếng Việt, không phải biến thể tuỳ
# chọn: 5 trong số ghép luôn là "lăm" ("mười lăm", "bốn mươi lăm"), 1 là "mốt"
# ("hai mươi mốt"). Thiếu chúng thì "bốn mươi lăm ngày" lọt qua trong khi "bốn
# mươi năm ngày" — cách không ai viết — bị bắt. Đo được 2026-09-02.
_SO_BANG_CHU = (
    "không|một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|bẩy|tám|chín|mười|mươi"
    "|trăm|nghìn|ngàn|triệu|tỷ|tỉ|nửa|rưỡi"
)
# Đơn vị mang MỐC PHÁP LÝ trong luật lao động (thời hạn báo trước, thử việc, mức
# lương). CỐ Ý KHÔNG có "lần": "Bạn đi muộn mấy lần?" là câu hỏi dữ kiện hợp lệ,
# và "một số lần" / "một vài" không phát biểu mốc nào.
_DON_VI_MOC = "ngày|tuần|tháng|năm|giờ|phút|đồng|phần trăm"

_RE_BI_LOAI = (
    re.compile(r"[ĐÐđ]iều\s*\d+"),                                # số Điều
    re.compile(r"\d+\s*/\s*\d{4}\s*/"),                           # số hiệu văn bản
    re.compile(rf"\d+\s*({_DON_VI_MOC}|%)", re.IGNORECASE),        # chữ số kèm đơn vị
    # Số viết bằng chữ kèm đơn vị. `(?:…\s+)+` cho số ghép ("mười hai tháng",
    # "ba mươi ngày", "năm triệu đồng") mà không cần liệt kê từng số ghép.
    re.compile(rf"\b(?:(?:{_SO_BANG_CHU})\s+)+(?:{_DON_VI_MOC})\b", re.IGNORECASE),
)

HOI_LAI_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["chieu"],
    "properties": {
        "chieu": {
            "type": "array",
            "maxItems": TOI_DA,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ma", "cau"],
                "properties": {
                    # `enum` là chỗ ép "model chọn TRONG danh sách" thành ràng
                    # buộc chứ không phải lời dặn. Bơm từ `CHIEU` để không có
                    # bản sao thứ hai của danh sách khoá.
                    "ma": {"type": "string", "enum": list(CHIEU)},
                    "cau": {"type": "string"},
                },
            },
        }
    },
}


class KetQuaHoiLai(NamedTuple):
    """`usage` khác None cả khi `nguon == "loi"`: JSON sai hình dạng vẫn đã tiêu
    token thật, và một lượt gọi không đếm được là một lượt gọi vô hình với trần
    chi phí ngày."""

    cau: str
    usage: Usage | None
    nguon: str  # "llm" | "loi"


# Một bộ nhận diện cho CẢ HAI nơi cần "mốc pháp lý trong một câu": bộ lọc câu
# hỏi lại ở dưới, và `giai_nghia.dinh_danh_bia`. Từ vựng số/đơn vị đã sống ở
# đây, nên hàm sống cùng nó — bản thứ hai của cùng quy tắc sẽ lệch pha đúng vào
# ngày ai đó thêm một đơn vị.
_RE_MOC = (
    re.compile(rf"(\d+)\s*({_DON_VI_MOC}|%)", re.IGNORECASE),
    re.compile(rf"\b((?:(?:{_SO_BANG_CHU})\s+)+)({_DON_VI_MOC})\b", re.IGNORECASE),
)


def moc_phap_ly_trong(chu: str) -> set[str]:
    """Tập mốc pháp lý xuất hiện trong `chu`, đã chuẩn hoá về `"<số> <đơn vị>"`.

    Chuẩn hoá vì hai nơi gọi cần SO TẬP, không cần vị trí: `"45 ngày"` trong câu
    đã giải nghĩa phải khớp `"45  ngày"` trong lịch sử, còn không thì phép trừ
    tập sẽ báo bịa cho một mốc người dùng đã nhắc.
    """
    ra: set[str] = set()
    for r in _RE_MOC:
        for m in r.finditer(chu):
            so = " ".join(m.group(1).split()).lower()
            ra.add(f"{so} {m.group(2).lower()}")
    return ra


def bi_loai(cau: str) -> bool:
    """Câu hỏi lại có phát biểu một quy tắc pháp luật không — xem docstring
    module. Quy tắc, 0 token, và cố ý THÔ: thà loại oan một câu sạch (rơi về câu
    hằng số, người hỏi vẫn được hỏi đúng chiều đó) còn hơn để lọt một mốc pháp
    lý không có căn cứ nào chống đỡ."""
    return any(r.search(cau) for r in _RE_BI_LOAI)


def _cau_dung_duoc(ma: str, cau: str) -> str:
    """Câu của model nếu qua được bộ lọc, còn không thì câu hằng số của chiều đó.

    Gộp khoảng trắng: một `cau` có xuống dòng sẽ phá vỡ danh sách gạch đầu dòng
    mà `catDoan` phía giao diện đang dựa vào để hiện ra chấm đầu dòng.
    """
    gon = " ".join((cau or "").split())
    if not gon:
        return CHIEU[ma]
    if bi_loai(gon):
        # Đếm được bằng log, không im lặng: bộ lọc này là lưới an toàn cuối cho
        # đúng lớp ảo giác mà verifier mù với, nên tần suất nó nổ là số liệu.
        logger.warning("hoi_lai: câu sinh cho chiều %s phát biểu quy tắc pháp luật, "
                       "thay bằng câu hằng số — bị loại: %r", ma, gon)
        return CHIEU[ma]
    return gon


def dung_cau_hoi_lai(chon: list, da_biet: frozenset[str] = frozenset()) -> str:
    """Tầng THUẦN — không mạng, không LLM. Tách khỏi `hoi_lai` để bộ lọc và
    đường suy biến kiểm được trong bộ test mặc định, cùng khuôn
    `kho.dung_cau_tra_loi`.

    `da_biet` (bộ nhớ phiên, spec 2026-09-09 §6) là các chiều hồ sơ ĐÃ có giá
    trị — khi rơi về đường suy biến `MAC_DINH`, bỏ luôn những chiều này: hỏi
    lại đúng dữ kiện người hỏi vừa cho biết là màn hình trắng đội lốt câu hỏi.
    Sau khi bỏ mà không còn chiều nào (mọi chiều mặc định đều đã biết) thì trả
    chuỗi rỗng — `_ngo_cut` nối `coverage_note` bằng cách bỏ qua phần tử rỗng,
    nên một chuỗi rỗng ở đây không để lại dòng trống nào.
    """
    cau_theo_ma: dict[str, str] = {}
    for c in chon:
        if not isinstance(c, dict):
            continue
        ma = str(c.get("ma") or "")
        # `ma` lạ thì BỎ, không in nguyên ra: `enum` trong schema đã chặn, nhưng
        # mặc định an toàn khi model trả giá trị ngoài danh sách phải là im lặng
        # về nó, không phải đưa một mã máy cho người hỏi đọc.
        if ma in CHIEU and ma not in cau_theo_ma:
            cau_theo_ma[ma] = str(c.get("cau") or "")
        if len(cau_theo_ma) == TOI_DA:
            break
    if not cau_theo_ma:
        # Cùng trần `TOI_DA` với nhánh model-chọn ngay trên — trước bản này
        # trùng với `len(MAC_DINH) == 3` nên không lộ; hạ `TOI_DA` xuống 2
        # (Task 14) mà quên cắt ở đây thì đúng lỗi hỏng mạng/JSON sai hình
        # dạng lại hỏi NHIỀU câu hơn cả đường thường — ngược mục tiêu trần.
        cau_theo_ma = dict.fromkeys([ma for ma in MAC_DINH if ma not in da_biet][:TOI_DA], "")
        if not cau_theo_ma:
            return ""
    return "\n".join([CAU_DAN, *(f"- {_cau_dung_duoc(ma, cau)}"
                                 for ma, cau in cau_theo_ma.items())])


# Câu dẫn của ĐUÔI hỏi thêm — khác `CAU_DAN` (đuôi của một NGÕ CỤT): đây gắn
# vào cuối một câu trả lời ĐÃ CÓ luận điểm (QT-5), nên giọng phải nhẹ hơn "để
# trả lời chắc chắn" — câu trả lời đã chắc, chỉ hỏi thêm để chính xác hơn.
CAU_DAN_DUOI = "Để chính xác hơn, bạn cho tôi biết thêm:"

# Chiều duy nhất mà `suy_dien` (0 token) suy được hôm nay. Hằng số hoá để đuôi
# hỏi và node suy diễn không lệch nhau khi một trong hai đổi.
CHIEU_SUY_DIEN = "chu_the"


# Trần của riêng ĐUÔI hỏi thêm (spec 2026-09-16 §FR-008/FR-021). Không phải trần
# của cả `coverage_note`: nửa sau của một NGÕ CỤT do `hoi_lai()` dựng không bị
# đợt này đụng tới.
TRAN_DUOI = 160


def duoi_hoi_them(ho_so: dict, vua_suy_dien: str | None = None) -> str:
    """Đuôi của một câu trả lời ĐÃ CÓ luận điểm (QT-5): 0 token, tối đa MỘT câu.

    HỢP ĐỒNG 2026-09-16 (spec `2026-09-16-tra-loi-ngan-dung-muc-tieu` §FR-011):
    đuôi chỉ xuất hiện khi CHÍNH LƯỢT NÀY vừa suy ra một giả định, và chỉ hỏi
    đúng chiều vừa suy ra. `vua_suy_dien` là giá trị mà `suy_dien` suy được
    trong lượt (`traces["suy_dien_chu_the"]`) — rỗng nghĩa là lượt này không
    đoán gì, nên không có gì để xác nhận lại.

    Bản trước hỏi tới `TOI_DA` chiều còn trống trong `MAC_DINH` bất kể chúng có
    làm đổi kết luận hay không — ĐO ĐƯỢC là hành vi máy móc rõ nhất của mặt trả
    lời (`cai_thien.md` §4.2.7). Nhưng bỏ hẳn đuôi thì phá vế "nêu giả định rồi
    hỏi đúng dữ kiện đó" của quyết định 2026-09-09, thứ `eval/run_mo_ho` đang
    chấm. Thu hẹp giữ được cả hai.

    `suy_dien` chỉ suy vai KHI hồ sơ còn trống vai, nên một giá trị `suy_dien`
    mang sang từ lượt trước KHÔNG kèm tín hiệu và không mở lại câu hỏi.
    """
    if not vua_suy_dien:
        return ""
    # Người dùng đã tự nói vai thì không hỏi lại, kể cả khi tín hiệu suy diễn bị
    # truyền nhầm vào đây (FR-012): dữ kiện người nói luôn thắng giả định.
    if ((ho_so or {}).get(CHIEU_SUY_DIEN) or {}).get("nguon") == "nguoi_noi":
        return ""
    duoi = f"{CAU_DAN_DUOI}\n- {CHIEU[CHIEU_SUY_DIEN]}"
    # Vượt trần thì BỎ HẲN, không xén: một câu hỏi bị cắt làm đôi tệ hơn là
    # không hỏi, và câu trả lời phía trên vốn đã đủ chắc.
    return "" if len(duoi) > TRAN_DUOI else duoi


def _du_kien_con_thieu(khung_yeu_cau: dict | None, da_biet) -> list[dict]:
    """Dữ kiện trong khung yêu cầu còn đáng hỏi: có câu hỏi, chưa nằm trong hồ sơ,
    và câu hỏi tự nó không phát biểu một quy tắc pháp luật.

    `bi_loai` chạy LẠI ở đây dù `rewrite_query.khung_yeu_cau_tu` đã lọc một lần:
    module này tự nhận là chỗ chặn DUY NHẤT cho lớp ảo giác mà verifier mù với
    (xem docstring module), nên nó không được tin một khâu khác đã chặn hộ.
    """
    ra: list[dict] = []
    for m in (khung_yeu_cau or {}).get("du_kien_quyet_dinh_con_thieu") or []:
        if not isinstance(m, dict):
            continue
        cau = " ".join(str(m.get("cau") or "").split())
        if not cau or str(m.get("ma") or "") in da_biet or bi_loai(cau):
            continue
        ra.append({**m, "cau": cau})
    return ra


def duoi_tu_khung(khung_yeu_cau: dict | None, ho_so: dict | None) -> str:
    """Đuôi hỏi thêm lấy TỪ khung yêu cầu (cai_thien.md §6 GĐ4) — 0 token.

    Khác `duoi_hoi_them` (sáu chiều hồ sơ chung, chỉ hỏi chiều vừa suy ra): ở đây
    câu hỏi là dữ kiện QUYẾT ĐỊNH của chính vụ việc — lý do chấm dứt, hành vi vi
    phạm — thứ `CHIEU` không có từ vựng để hỏi. Chỉ dữ kiện `lam_doi_ket_luan`
    mới được hỏi: một câu trả lời đã đủ thì không có câu hỏi cuối.

    Rỗng khi khung không có dữ kiện nào như vậy, hoặc người hỏi đã nói nó rồi
    (`ho_so[ma].gia_tri`) — dữ kiện người nói luôn thắng suy đoán của model.
    """
    da_biet = {k for k, v in (ho_so or {}).items() if isinstance(v, dict) and v.get("gia_tri")}
    for m in _du_kien_con_thieu(khung_yeu_cau, da_biet):
        if not m.get("lam_doi_ket_luan"):
            continue
        duoi = f"{CAU_DAN_DUOI}\n- {m['cau']}"
        # Vượt trần thì BỎ HẲN, không xén — cùng quy tắc `duoi_hoi_them`.
        return "" if len(duoi) > TRAN_DUOI else duoi
    return ""


def cau_hoi_lai_tu_khung(khung_yeu_cau: dict | None, da_biet: frozenset[str] = frozenset()) -> str:
    """Nửa sau của một NGÕ CỤT, lấy từ khung yêu cầu — 0 token, tối đa `TOI_DA`.

    Dùng THAY cho lượt `hoi_lai` (LLM) khi khung có dữ kiện hỏi được: khung đã
    bám vào chính vụ việc, nên một lượt gọi model để hỏi lại sáu chiều chung là
    tiền tiêu cho một câu hỏi kém cụ thể hơn. Rỗng ⇒ caller rơi về `hoi_lai`.

    Dữ kiện `lam_doi_ket_luan` đứng trước (sort ỔN ĐỊNH, giữ thứ tự khung cho
    các mục cùng hạng): trần là hai câu, nên thứ tự quyết định câu nào bị cắt.
    """
    cac = _du_kien_con_thieu(khung_yeu_cau, da_biet)
    cac.sort(key=lambda m: not m.get("lam_doi_ket_luan"))
    if not cac:
        return ""
    return "\n".join([CAU_DAN, *(f"- {m['cau']}" for m in cac[:TOI_DA])])


def hoi_lai(cau_hoi: str, llm, model: str, da_biet: frozenset[str] = frozenset()) -> KetQuaHoiLai:
    """Chuỗi đã hoàn chỉnh, ghép được thẳng vào `coverage_note`.

    KHÔNG BAO GIỜ raise: đây là khâu cuối của một lượt đã không có câu trả lời,
    và không quyết định hạ nguồn nào phụ thuộc nó — để một lỗi ở đây thành HTTP
    500 là biến một ngõ cụt thành một trang lỗi. Cùng lập luận với đường suy
    biến hành văn của `assemble`, khác `route.py` (lỗi ở đó là quyết định định
    tuyến nên phải nổ).

    `da_biet` (bộ nhớ phiên) là các chiều hồ sơ ĐÃ có giá trị — chúng bị bỏ
    khỏi cả prompt (model không thấy để chọn) lẫn khỏi `chon` sau khi model trả
    lời (`enum` của schema vẫn liệt kê đủ sáu chiều nên vẫn phải lọc lại đây),
    để không hỏi lại một dữ kiện đã biết.
    """
    chieu_con = {ma: cau for ma, cau in CHIEU.items() if ma not in da_biet}
    if not chieu_con:
        # Bộ nhớ phiên đã lấp đủ sáu chiều: prompt sẽ chở một danh sách RỖNG, mọi
        # chiều model chọn bị lọc lại ở `chon`, và `dung_cau_hoi_lai` trả "" — đúng
        # kết quả, sau một lượt LLM trả tiền cho không. Không có gì để hỏi thì
        # không gọi.
        return KetQuaHoiLai("", None, "llm")
    prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
        cau_hoi=cau_hoi,
        toi_da=TOI_DA,
        chieu="\n".join(f"- `{ma}`: {cau}" for ma, cau in chieu_con.items()),
    )
    usage: Usage | None = None
    try:
        raw, usage = llm.chat(model, messages(prompt), json_schema=HOI_LAI_SCHEMA)
        chon = json.loads(raw)["chieu"]
        if not isinstance(chon, list):
            raise TypeError(f"'chieu' phải là list, được {type(chon).__name__}")
        chon = [c for c in chon if c.get("ma") in chieu_con]
    except Exception as e:
        # `exc_info=True`: không có nó, operator biết TÊN exception (đã có trong
        # log) nhưng không biết dòng nào trong khối try ném ra nó — với một
        # `AttributeError` do lỗi lập trình thì đó là khoảng cách giữa "thấy có
        # lỗi" và "biết sửa ở đâu".
        #
        # `nguon` giữ đúng hai giá trị "llm"/"loi", KHÔNG nhét tên exception vào:
        # trace là chiều để đếm, và một nhãn vô hạn cardinality thì không đếm được.
        # Chỗ đúng để phân biệt loại lỗi là log, và log đã có cả tên lẫn traceback.
        logger.warning("hoi_lai: không sinh được chiều hỏi (%s: %s) — rơi về câu hằng số",
                       type(e).__name__, e, exc_info=True)
        return KetQuaHoiLai(dung_cau_hoi_lai([], da_biet=da_biet), usage, "loi")
    return KetQuaHoiLai(dung_cau_hoi_lai(chon, da_biet=da_biet), usage, "llm")
