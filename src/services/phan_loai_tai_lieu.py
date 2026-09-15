"""Nhận ra tài liệu người dùng tải lên là loại văn bản gì (spec 2026-09-15c).

Đây là chỗ KLAW thôi hỏi và bắt đầu suy luận. Bắt người dùng chọn một trong 29
loại trước khi đọc được tờ giấy họ đang cầm là hành vi của một biểu mẫu, không
phải của một trợ lý pháp lý.

**Tất định trước, mô hình sau — và ở đây tất định là đủ.** Giấy tờ pháp lý Việt
Nam gần như luôn tự khai tên ở dòng đầu: "HỢP ĐỒNG LAO ĐỘNG", "ĐƠN KHỞI KIỆN",
"QUYẾT ĐỊNH BỔ NHIỆM". Tra bảng trên chính chữ đó là 0 token, lặp lại được, và
giải thích được — cùng nguyên tắc `route.R-INT-001` đã đặt cho định tuyến ý định.

**Dám nói không biết.** Tài liệu ngoài 29 loại trả `None`. Ép nó vào loại gần
nhất nghĩa là rút sai bộ trường, và người dùng nhìn một bảng dữ kiện sai mà
không hiểu vì sao. Thà hỏi một câu còn hơn đoán sai một cách im lặng — cùng
nguyên tắc `abstain` của phần trả lời.
"""

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

THU_MUC_CHECKLIST = Path("config")

# Chỉ đọc phần đầu tài liệu. Tên văn bản nằm ở đó; một chữ "hợp đồng lao động"
# ở trang 40 của một bản nội quy không được lật ngược kết luận.
SO_DON_VI_DAU = 12

# Dòng phải GẦN NHƯ CHỈ gồm tên loại mới được coi là tiêu đề. Một câu dẫn
# chiếu như "Căn cứ Bộ luật Lao động số 45/2019/QH14" loãng hơn nhiều, và nếu
# không chặn ở đây thì nó khớp "hợp đồng lao động" — đã đo, đã xảy ra.
NGUONG_THUAN = 0.8

# Từ quá phổ biến trong mọi tên văn bản — có mặt chúng không nói lên gì.
_TU_CHUNG = {"va", "cua", "ve", "trong", "tai", "cho", "voi", "cac", "mot", "o"}


@dataclass(frozen=True)
class KetQuaPhanLoai:
    """Kết luận kèm chỗ nó đọc được, để người dùng sửa được khi sai."""

    loai: str
    ten: str
    do_tin: float
    can_cu: str
    """Dòng trong tài liệu đã dẫn tới kết luận này."""


def _khong_dau(s: str) -> str:
    """Bỏ dấu ĐỂ SO TÊN VĂN BẢN — không phải để nới phép kiểm trích dẫn.

    Hai việc khác nhau: ở đây ta đoán người dùng đang cầm giấy gì, và họ gõ máy
    không dấu hoặc OCR nuốt dấu là chuyện thường. Còn `verify_tier1.normalize`
    vẫn giữ dấu tuyệt đối, vì ở đó một chữ sai dấu là một điều luật khác.
    """
    s = unicodedata.normalize("NFD", (s or "").lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9\s]", " ", s)


def _tu(s: str) -> list[str]:
    return [t for t in _khong_dau(s).split() if len(t) > 1 and t not in _TU_CHUNG]


@lru_cache(maxsize=1)
def _bang_ten() -> list[tuple[str, str, list[str]]]:
    """(loai, ten, từ khoá) cho mọi checklist. Nguồn là chính `config/checklist_*.yaml`
    — thêm một loại văn bản là tự nhận ra được, không phải sửa file này."""
    ra = []
    for tep in sorted(THU_MUC_CHECKLIST.glob("checklist_*.yaml")):
        d = yaml.safe_load(tep.read_text(encoding="utf-8")) or {}
        loai, ten = d.get("loai"), d.get("ten")
        if loai and ten:
            ra.append((loai, ten, _tu(ten)))
    return ra


def phan_loai(don_vi) -> KetQuaPhanLoai | None:
    """Loại văn bản đọc được từ phần đầu tài liệu, hoặc `None` khi không chắc.

    Hai phép đo, và phép thứ hai mới là phép quan trọng:

    * **phủ** = bao nhiêu phần tên chính thức của loại có mặt trong dòng.
    * **thuần** = bao nhiêu phần của DÒNG là tên loại đó.

    Chỉ dùng "phủ" thì dòng `Căn cứ Bộ luật Lao động số 45/2019/QH14` khớp
    "hợp đồng lao động" — đo được, đã xảy ra. Một tiêu đề văn bản gần như CHỈ
    gồm tên loại, còn một câu dẫn chiếu thì loãng; "thuần" tách đúng hai thứ đó.

    Xếp hạng theo số từ khớp trước: "thoả thuận chấm dứt hợp đồng lao động"
    phải thắng "hợp đồng lao động" trên chính tờ thoả thuận, vì nó cụ thể hơn.
    """
    dau = list(don_vi)[:SO_DON_VI_DAU]
    if not dau:
        return None

    tot: tuple[int, float, KetQuaPhanLoai] | None = None
    for d in dau:
        tu_dong = set(_tu(d.noi_dung))
        if len(tu_dong) < 2:
            continue
        for loai, ten, tu_khoa in _bang_ten():
            if len(tu_khoa) < 2:
                continue
            khop = len(tu_dong & set(tu_khoa))
            if khop < 2:
                continue
            thuan = khop / len(tu_dong)
            if thuan < NGUONG_THUAN:
                continue
            phu = khop / len(set(tu_khoa))
            diem = round(min(1.0, (thuan + phu) / 2), 3)
            khoa_xep = (khop, thuan)
            if tot is None or khoa_xep > (tot[0], tot[1]):
                tot = (
                    khop,
                    thuan,
                    KetQuaPhanLoai(
                        loai=loai, ten=ten, do_tin=diem, can_cu=d.noi_dung.strip()[:200]
                    ),
                )
    return tot[2] if tot else None
