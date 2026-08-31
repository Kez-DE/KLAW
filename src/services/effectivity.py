"""Suy luận hiệu lực 3 mức (spec 5.2) — phép kiểm thứ tư của verifier tầng 1.

Thuần Python + một truy vấn SQL. KHÔNG gọi LLM: câu hỏi "điều luật này còn
hiệu lực không?" phải trả lời được bằng ngày tháng và quan hệ văn bản, không
bằng trí nhớ của mô hình.

Vì sao cần ba mức thay vì đọc `tinh_trang` của MOJ:

  `tinh_trang` SAI 4/6 trên chính chuỗi nghị định lương tối thiểu — 122/2015,
  141/2017, 157/2018 và 90/2019 đều đã bị thay nhưng vẫn mang "CHL" (còn hiệu
  lực). Tin thẳng vào nó nghĩa là hệ thống đóng dấu "đã kiểm chứng" cho luật
  đã chết — đúng chế độ hỏng mà cả khoá luận tồn tại để chống.

  * **Mức 1** — `ngay_het_hieu_luc` đã qua. Trường của chính CSDL quốc gia, tin
    được, nhưng chỉ 1/6 ca có.
  * **Mức 2a** — cạnh đồ thị chấm dứt hiệu lực, đọc theo ĐÚNG CHIỀU của từng
    loại quan hệ. Bắt được ca MOJ bỏ sót, `tin_cay = cao` vì có văn bản đích
    danh làm chứng.
  * **Mức 2b** — khi đồ thị IM LẶNG: cùng chủ đề + hiệu lực sau ⇒ suy ra đã bị
    thay. `tin_cay = trung_binh` vì đây là suy luận, không phải bằng chứng.
  * **Mức 3** — `HHL1P` (hết hiệu lực một phần). CSDL quốc gia không công bố dữ
    liệu cấp điều khoản nên KHÔNG kết luận được điều cụ thể còn hay hết.

Mức 2 kế thừa lỗi của đồ thị nên có ba guard, mỗi guard là một bất biến phát
biểu được bằng lời (xem `danh_gia`), không phải bảng tra văn bản.

Nguồn dữ liệu là một crawl HuggingFace bên thứ ba, vintage không rõ — mặc định
khi không biết luôn là `chua_xac_dinh` với `tin_cay` thấp, KHÔNG BAO GIỜ là
"còn hiệu lực".
"""

import logging
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)

# ── Bảng tác động: (chiều, loai) → cạnh này nói gì về SỐ PHẬN của `doc` ──────
# Đo trên cả 46 cạnh trong DB: chiều của parquet nhất quán 46/46 — tên quan hệ
# LUÔN phát biểu theo góc nhìn của `from_document_id`. Nên `loai` một mình
# KHÔNG đủ, phải kèm chiều:
#
#   ĐI VÀO  (to_document_id = tôi)
#     loai 21 "Thay thế"            → văn bản `from` THAY tôi     (from hiệu lực SAU: 5/5)
#     loai 20 "Sửa đổi, bổ sung"    → văn bản `from` SỬA tôi      (from hiệu lực SAU: 22/23)
#     loai 22/23                    → TÔI khai tử `from`; KHÔNG nói gì về tôi
#   ĐI RA   (from_document_id = tôi)
#     loai 22 "VB quy định hết hiệu lực"      → văn bản `to` khai tử TÔI  (to SAU: 13/13)
#     loai 23 "... hết hiệu lực 1 phần"       → `to` khai tử tôi MỘT PHẦN (to SAU: 5/5)
#
# Đọc 22/23 theo chiều ĐI VÀO là bẫy chết người: NĐ 293/2025 — luật lương tối
# thiểu HIỆN HÀNH — có đúng hai cạnh 22/23 đi vào, từ NĐ 74/2024 mà chính nó
# vừa thay thế và từ NĐ 128/2025; đọc sai chiều là tuyên luật hiện hành đã chết.
# Đọc theo chiều ĐI RA thì chính 18 cạnh 22/23 đó thành bằng chứng TRỰC TIẾP
# cho văn bản BỊ khai tử, nâng phán quyết của nó từ suy luận lên đồ thị-xác-nhận.
#
# 1/5/11/12 là mã MOJ (Bãi bỏ · Đình chỉ · Tạm ngưng · Thay thế), giữ sẵn cho
# một loader về sau nạp cạnh MOJ — chiều của 242 dòng đó CHƯA đo, xem report.
TAC_DONG = {
    ("di_vao", 1): "thay_the", ("di_vao", 5): "thay_the", ("di_vao", 11): "thay_the",
    ("di_vao", 12): "thay_the", ("di_vao", 21): "thay_the",
    ("di_vao", 20): "sua_doi",
    ("di_ra", 22): "thay_the",
    ("di_ra", 23): "sua_doi",
}

# ── So chủ đề ─────────────────────────────────────────────────────────────────
# Từ chức năng + từ loại văn bản: có mặt trong hầu hết tiêu đề nên không phân
# biệt được chủ đề. "sửa/đổi/bổ/sung" nằm đây là CỐ Ý — luật sửa đổi đúng là
# cùng chủ đề với luật bị sửa; việc nó không được coi là kẻ thay thế do
# `_la_van_ban_sua_doi` lo, không phải do tách từ.
TU_BO = frozenset({
    "nghị", "định", "luật", "bộ", "thông", "tư", "quy", "của", "về", "và", "số",
    "việt", "nam", "quyết", "chi", "tiết", "hướng", "dẫn", "một", "các", "điều",
    "thi", "hành", "sửa", "đổi", "bổ", "sung", "liên", "tịch", "cho", "với",
    "trong", "này", "khi", "theo", "đối",
})

# Ngưỡng Jaccard. ĐO trên toàn bộ 57 văn bản trong `documents`: cặp cùng chủ đề
# thấp nhất là 122/2015 vs 293/2025 = 0.458 (tiêu đề 122/2015 dài hơn hẳn vì
# liệt kê từng loại tổ chức sử dụng lao động); cặp khác chủ đề cao nhất mà một
# trong sáu nghị định chạm tới là 337/2025 "hợp đồng lao động điện tử" = 0.333.
# 0.4 nằm giữa khe [0.333, 0.458], cách đều hai bên ~0.06.
NGUONG_CHU_DE = 0.4

# "Ð" (U+00D0) nhìn y hệt "Đ" (U+0110) và có thật trong corpus (2 lần, tài liệu
# 96172); corpus cũng không thuần NFC (96117 có 'ư'+U+0323 thay vì 'ự'). Cùng
# một bộ ba chuẩn hoá mà `xref.py` đã phải trả giá ở Plan 1.
_MAP_D = str.maketrans({"Ð": "Đ", "ð": "đ"})

# "122/2015/NĐ-CP", "91/2015/QH13" — tiêu đề corpus NHÚNG số ký hiệu vào chính
# tiêu đề ("Nghị định số 122/2015/NĐ-CP Quy định mức lương..."). Không cắt thì
# "2015" thành từ chủ đề và hai văn bản chả liên quan cùng năm sẽ "cùng chủ đề".
_RE_SO_KY_HIEU = re.compile(r"\S*\d+\s*/\s*\d{2,4}\s*/\s*[^\s,;.]+")

_RE_SUA_DOI = re.compile(r"sửa\s*đổi")


class EffectivityVerdict(StrEnum):
    con_hieu_luc = "con_hieu_luc"
    chua_hieu_luc = "chua_hieu_luc"
    het_hieu_luc = "het_hieu_luc"
    bi_thay_the = "bi_thay_the"
    bi_sua_doi = "bi_sua_doi"
    mot_phan_khong_xac_dinh = "mot_phan_khong_xac_dinh"
    can_doi_chieu_tay = "can_doi_chieu_tay"
    chua_xac_dinh = "chua_xac_dinh"


@dataclass(frozen=True)
class Effectivity:
    verdict: EffectivityVerdict
    tin_cay: str          # cao | trung_binh | thap
    ly_do: str


def _chuan_hoa(s: str | None) -> str:
    return unicodedata.normalize("NFC", s or "").translate(_MAP_D).lower()


def _danh_tu_chinh(ten: str | None) -> list[str]:
    """Danh từ chính của tiêu đề, GIỮ THỨ TỰ: bỏ số ký hiệu, bỏ mọi token có
    chữ số, bỏ từ chức năng, bỏ token ≤ 2 ký tự (âm tiết đệm như "xã", "tử").
    Thứ tự cần cho `_dau_de` — tiêu đề văn bản Việt Nam nêu đối tượng điều
    chỉnh ngay từ đầu ("... Quy định MỨC LƯƠNG tối thiểu ...")."""
    s = _RE_SO_KY_HIEU.sub(" ", _chuan_hoa(ten))
    return [
        t for t in re.findall(r"\w+", s)
        if len(t) > 2 and t not in TU_BO and not any(c.isdigit() for c in t)
    ]


def _tu_chinh(ten: str | None) -> set[str]:
    return set(_danh_tu_chinh(ten))


def _dau_de(ten: str | None) -> str | None:
    """Danh từ chính ĐẦU TIÊN — đối tượng mà văn bản điều chỉnh."""
    tu = _danh_tu_chinh(ten)
    return tu[0] if tu else None


def _do_giong(ten_a: str | None, ten_b: str | None) -> float:
    """Jaccard trên tập danh từ chính. 0.0 khi một bên không còn từ nào."""
    a, b = _tu_chinh(ten_a), _tu_chinh(ten_b)
    return len(a & b) / len(a | b) if a and b else 0.0


def cung_chu_de(ten_a: str | None, ten_b: str | None) -> bool:
    """Hai tiêu đề có nói về cùng một chủ đề không?

    **Quy tắc, không phải bảng tra** — phát biểu bằng một câu: chuẩn hoá tiêu đề
    (NFC · Ð→Đ · thường hoá), bỏ phần định danh (số ký hiệu, năm) và từ chức
    năng, rồi coi là cùng chủ đề khi hai tiêu đề BẮT ĐẦU bằng cùng một danh từ
    chính VÀ phần danh từ còn lại trùng nhau ≥ `NGUONG_CHU_DE` (Jaccard).

    Không có `doc_id`, không có `so_ky_hieu`, không có nhánh riêng cho lĩnh vực
    nào — áp y hệt cho văn bản thứ bảy chưa từng thấy.

        "Nghị định ... mức lương tối thiểu vùng" vs "... mức lương tối thiểu"
            → đầu đề "mức" = "mức"; 4/5 = 0.8 ✓
        "Luật Việc làm" vs "Luật Bảo hiểm xã hội"
            → đầu đề "việc" ≠ "bảo" ✗

    Vì sao cần điều kiện đầu đề chứ không chỉ Jaccard: tiêu đề ngắn làm mẫu số
    nhỏ nên chỉ Jaccard thôi thì "Bộ luật Tố tụng dân sự" và "Bộ luật Dân sự"
    ra 0.5 — ĐÚNG BẰNG cặp cùng chủ đề thật thấp nhất trong corpus
    (122/2015 vs 153/2016). Không ngưỡng nào tách được hai cặp đó; đầu đề thì
    tách sạch ("tụng" ≠ "dân"). Đã đo trên cả 21 văn bản deep, không phải suy
    đoán — xem `docs`/report Task 2.
    """
    dau_a, dau_b = _dau_de(ten_a), _dau_de(ten_b)
    if dau_a is None or dau_a != dau_b:
        return False
    return _do_giong(ten_a, ten_b) >= NGUONG_CHU_DE


def _la_van_ban_sua_doi(ten: str | None) -> bool:
    """Tiêu đề tự khai là văn bản sửa đổi ("Luật sửa đổi, bổ sung một số điều
    của Bộ luật Tố tụng hình sự"). Văn bản như vậy CÙNG chủ đề với văn bản nó
    sửa — Jaccard tới 1.0 — nhưng nó SỬA chứ không THAY, nên không được làm ứng
    viên kế nhiệm ở Mức 2b."""
    return bool(_RE_SUA_DOI.search(_chuan_hoa(ten)))


def _cung_thu_bac(doc: dict, ung_vien: dict) -> bool:
    """Guard thứ bậc: một văn bản chỉ bị THAY THẾ bởi văn bản cùng loại (Nghị
    định thay Nghị định, Bộ luật thay Bộ luật). Một Nghị định hướng dẫn KHÔNG
    thay thế được Bộ luật mà nó hướng dẫn — thiếu guard này, NĐ 145/2020 bị suy
    ra là đã thay thế Bộ luật Lao động 45/2019.

    Bỏ qua khi một trong hai phía không có `loai_van_ban` (không bịa thứ bậc).
    Giới hạn đã biết: một Luật thật sự được thay bằng một Bộ luật sẽ bị bỏ sót —
    sai về phía an toàn (`con_hieu_luc`/`chua_xac_dinh`, không phải khai tử sai).
    """
    a, b = doc.get("loai_van_ban"), ung_vien.get("loai_van_ban")
    return a is None or b is None or a == b


def _tac_dong(canh: dict) -> str | None:
    """`thay_the` | `sua_doi` | None. `chieu` khuyết = `di_vao` (mặc định an
    toàn: cạnh đi vào là hình dạng cũ, cũng là hình dạng mã MOJ dùng)."""
    return TAC_DONG.get((canh.get("chieu") or "di_vao", canh.get("loai")))


def _canh_dung_chieu(canh: dict, ngay_hieu_luc_doc: date, as_of: date) -> str:
    """Phân loại một cạnh đi vào: `ok` | `hong` | `nguoc` | `sap_toi`."""
    hl = canh.get("from_ngay_hieu_luc")
    if hl is None:
        return "hong"
    # Bất biến: không văn bản nào bị thay bởi văn bản hiệu lực TRƯỚC chính nó.
    if hl <= ngay_hieu_luc_doc:
        return "nguoc"
    if hl > as_of:
        return "sap_toi"
    return "ok"


def _ke_khai_tu(canh: dict) -> str:
    """Câu chữ `ly_do` phải đúng chiều — cạnh đi ra nói "văn bản kia QUY ĐỊNH
    tôi hết hiệu lực", không phải "văn bản kia thay thế tôi"."""
    sk = canh.get("from_so_ky_hieu")
    if canh.get("chieu") == "di_ra":
        return f"{sk} quy định văn bản này hết hiệu lực"
    return f"bị {sk} thay thế"


def _ke_sua_doi(canh: dict) -> str:
    sk = canh.get("from_so_ky_hieu")
    if canh.get("chieu") == "di_ra":
        return f"{sk} quy định văn bản này hết hiệu lực một phần"
    return f"bị {sk} sửa đổi, bổ sung"


def _bao_ngay_mau_thuan(doc: dict, canh: dict, ngay_hieu_luc_doc: date) -> None:
    """Cạnh mang quan hệ chấm dứt nhưng ngày không cho phép — dữ liệu bẩn.
    BỎ QUA và ĐẾM (`logger.warning`, cùng khuôn `xref.py` dùng cho dữ liệu bị
    loại), không im lặng và cũng không tin."""
    logger.warning(
        "bỏ qua cạnh chieu=%s loai=%s giữa %s và %s: ngày mâu thuẫn "
        "(%s không sau %s)",
        canh.get("chieu") or "di_vao", canh.get("loai"), doc.get("so_ky_hieu"),
        canh.get("from_so_ky_hieu"), canh.get("from_ngay_hieu_luc"), ngay_hieu_luc_doc,
    )


def danh_gia(
    doc: dict,
    canh_di_vao: list[dict],
    as_of: date,
    ung_vien_ke_nhiem: Sequence[dict] = (),
) -> Effectivity:
    """Phán quyết hiệu lực của `doc` tại thời điểm `as_of`.

    `canh_di_vao`: cạnh `"references"` có `to_document_id = doc["id"]`, mỗi cạnh
    mang `loai`, `from_so_ky_hieu`, `from_ten`, `from_ngay_hieu_luc`.
    `ung_vien_ke_nhiem`: văn bản đã hiệu lực và hiệu lực SAU `doc` — nguyên liệu
    của Mức 2b. Cả hai do `nap_ngu_canh` lấy từ DB.

    Bốn guard của Mức 2, mỗi cái là một bất biến phát biểu được bằng lời:

      1. **Chiều thời gian** — không văn bản nào bị thay bởi văn bản hiệu lực
         TRƯỚC chính nó; bỏ qua cạnh đó, không nêu tên nó trong `ly_do`.
      2. **Chiều quan hệ** — chỉ `loai` 20/21 (và mã MOJ tương đương) mới nói
         "văn bản kia tác động lên TÔI"; 22/23 nói ngược lại.
      3. **Cùng chủ đề** (`cung_chu_de`) — cạnh "Thay thế" giữa hai văn bản khác
         chủ đề gần chắc là lỗi dữ liệu (Luật Việc làm "thay thế" Luật BHXH);
         hạ xuống `can_doi_chieu_tay`, KHÔNG kết luận đã chết.
      4. **Thứ bậc** (`_cung_thu_bac`, chỉ Mức 2b) — chỉ văn bản CÙNG loại mới
         thay thế được nhau. Một Nghị định hướng dẫn không khai tử được Bộ luật
         mà nó hướng dẫn.
      5. **Chiều bằng chứng** (chỉ Mức 2b) — phỏng đoán từ tiêu đề không được
         lật một khai báo CỤ THỂ của sổ đăng ký (MOJ khai `HHL1P` thì giữ
         `mot_phan_khong_xac_dinh`, khẳng định yếu hơn và an toàn hơn), và
         không áp lên chính văn bản ĐI SỬA — tiêu đề của nó rút về gần trắng.

    Guard 1, 3 và 4 KHÔNG phải trang trí: bản đầu tiên thiếu 1 và 4 đã tuyên
    nhầm 4 văn bản còn sống trong corpus là đã bị thay thế, trong đó có Bộ luật
    Lao động 45/2019 — văn bản trung tâm của cả đề tài.
    """
    ten_doc = doc.get("ten")

    # ── Mức 1: ngày hết hiệu lực đã qua ──────────────────────────────────────
    het = doc.get("ngay_het_hieu_luc")
    if het and het <= as_of:
        return Effectivity(EffectivityVerdict.het_hieu_luc, "cao",
                           f"ngày hết hiệu lực {het} đã qua tại {as_of}")

    # Mọi so sánh chiều bên dưới cần ngày hiệu lực của chính `doc`.
    bd = doc.get("ngay_hieu_luc")
    if bd is None:
        return Effectivity(EffectivityVerdict.chua_xac_dinh, "thap",
                           f"văn bản {doc.get('so_ky_hieu')} thiếu ngày hiệu lực — "
                           "không so được chiều thời gian với bất kỳ văn bản nào")

    canh_hong: list[str] = []
    sap_toi: list[str] = []

    # ── Mức 2a: cạnh đồ thị nói "bị chấm dứt hiệu lực" ───────────────────────
    for c in canh_di_vao:
        if _tac_dong(c) != "thay_the":
            continue
        match _canh_dung_chieu(c, bd, as_of):
            case "hong":
                canh_hong.append(str(c.get("from_document_id") or c.get("from_so_ky_hieu")))
            case "nguoc":
                _bao_ngay_mau_thuan(doc, c, bd)  # guard 1 — bỏ qua VÀ đếm
            case "sap_toi":
                sap_toi.append(f"{c.get('from_so_ky_hieu')} từ {c.get('from_ngay_hieu_luc')}")
            case "ok":
                if cung_chu_de(ten_doc, c.get("from_ten")):
                    return Effectivity(
                        EffectivityVerdict.bi_thay_the, "cao",
                        f"đồ thị xác nhận: {_ke_khai_tu(c)} từ {c.get('from_ngay_hieu_luc')}")
                return Effectivity(
                    EffectivityVerdict.can_doi_chieu_tay, "thap",
                    f"có cạnh chấm dứt hiệu lực với {c.get('from_so_ky_hieu')} nhưng KHÁC "
                    f"chủ đề ({c.get('from_ten')!r} vs {ten_doc!r}) — nghi lỗi dữ liệu MOJ, "
                    "phải đối chiếu tay")

    # ── Mức 2b: đồ thị im lặng, suy luận từ chính corpus ─────────────────────
    # Cùng chủ đề + hiệu lực sau + đã có hiệu lực ⇒ văn bản trước bị thay thế.
    # Chọn ứng viên GIỐNG NHẤT (hoà thì sớm nhất) chứ không phải sớm nhất: tiêu
    # đề ngắn dễ chạm ngưỡng với một chủ đề lân cận, và lấy sớm nhất sẽ nêu tên
    # kẻ thay thế sai ngay cả khi phán quyết đúng.
    #
    # Guard 5 — **CHỈ suy luận khi MOJ nói CHL.** Mức 2b không có cạnh đồ thị
    # nào: nó là phỏng đoán từ độ giống TIÊU ĐỀ. Nó tồn tại cho đúng một tình
    # huống — MOJ khai "còn hiệu lực" cho một văn bản mà chính corpus mâu thuẫn
    # (đo được: sai 4/6 trên chuỗi lương tối thiểu). Khi MOJ đã khai HHL1P thì
    # sổ đăng ký ĐÃ nói một điều cụ thể, và `mot_phan_khong_xac_dinh` là khẳng
    # định YẾU HƠN, an toàn hơn `bi_thay_the`; để phỏng đoán từ tiêu đề lật một
    # khai báo của sổ đăng ký là đi ngược chiều mạnh-yếu của bằng chứng.
    #
    # ĐO 2026-09-01, ngay khi corpus mở từ 21 lên 47 văn bản toàn văn — hai ca
    # tuyên nhầm, cả hai đều HHL1P và cả hai đều là văn bản ĐANG SỐNG:
    #   67/2025/QH15 Thuế thu nhập DOANH NGHIỆP "bị thay bởi"
    #     109/2025/QH15 Thuế thu nhập CÁ NHÂN            (Jaccard 0.5, đầu đề "thuế")
    #   71/2025/QH15 Công nghiệp công nghệ số "bị thay bởi"
    #     133/2025/QH15 "CÔNG NGHỆ CAO"                  (Jaccard 0.5, đầu đề "công")
    # Không nới `NGUONG_CHU_DE` được: cặp cùng chủ đề THẬT thấp nhất trong corpus
    # là 0.458, nằm DƯỚI cả hai ca sai. Ngưỡng không tách được chúng; chiều bằng
    # chứng thì tách sạch — không ca đúng nào của Mức 2b mang tình trạng HHL1P.
    # Chặn ĐÚNG chiều lật, không rộng hơn: `chua_xac_dinh` (36+ dòng chỉ-metadata
    # nạp từ parquet, MOJ không khai gì) KHÔNG phải một khai báo, nên với chúng
    # suy luận là tín hiệu DUY NHẤT có — chặn ở đó chỉ làm mù thêm. `HHL` đã bị
    # Mức 1/Mức 3 bắt trước. Còn lại đúng một ca cần chặn: `HHL1P`.
    #
    # Vế thứ hai — **văn bản ĐI SỬA không phải chủ thể của Mức 2b.** `TU_BO` bỏ
    # "sửa/đổi/bổ/sung/một/số/điều/của", nên tiêu đề một luật sửa đổi rút về
    # gần như trắng và độ giống tính trên phần còn lại là ngẫu nhiên. Ca thật
    # cùng ngày: "Luật Sửa đổi, bổ sung một số điều của Bộ luật Hình sự"
    # (12/2017/QH14) rút về đúng {"hình"} — "sự" bị lọc vì ≤2 ký tự — và khớp
    # 1.0 với "LUẬT THI HÀNH ÁN HÌNH SỰ" (127/2025/QH15), cũng rút về {"hình"}.
    # `_la_van_ban_sua_doi` đã lọc phía ỨNG VIÊN từ trước; đây là cùng lý do,
    # phía còn lại. Sửa ở đây chứ không siết `NGUONG_CHU_DE` hay bỏ bộ lọc
    # ≤2 ký tự: cả hai đụng vào một ngưỡng đã hiệu chuẩn bằng số đo, và bỏ bộ
    # lọc sẽ giết "Bộ luật Hình sự" — cũng rút về {"hình"} — một ca ĐÚNG.
    if doc.get("tinh_trang") == "HHL1P" or _la_van_ban_sua_doi(ten_doc):
        ung_vien_ke_nhiem = ()
    ke_nhiem = sorted(
        (
            (-_do_giong(ten_doc, u.get("ten")), u.get("ngay_hieu_luc"), u)
            for u in ung_vien_ke_nhiem
            if u.get("ngay_hieu_luc") is not None
            and bd < u["ngay_hieu_luc"] <= as_of
            and _cung_thu_bac(doc, u)
            and not _la_van_ban_sua_doi(u.get("ten"))
            and cung_chu_de(ten_doc, u.get("ten"))
        ),
        key=lambda x: (x[0], x[1]),
    )
    if ke_nhiem:
        u = ke_nhiem[0][2]
        return Effectivity(
            EffectivityVerdict.bi_thay_the, "trung_binh",
            f"suy luận cùng chủ đề: {u.get('so_ky_hieu')} cùng chủ đề và đã có hiệu lực từ "
            f"{u['ngay_hieu_luc']}, sau {bd} của văn bản này — đồ thị KHÔNG có cạnh xác nhận, "
            "cần đối chiếu nếu dùng cho mục đích pháp lý")

    # ── Mức 2c: cạnh Sửa đổi, bổ sung ────────────────────────────────────────
    # Không áp guard cùng chủ đề: luật sửa đổi gộp (VD "sửa đổi 37 luật có liên
    # quan đến quy hoạch") sửa đúng những văn bản khác chủ đề nhau.
    for c in canh_di_vao:
        if _tac_dong(c) != "sua_doi":
            continue
        match _canh_dung_chieu(c, bd, as_of):
            case "hong":
                canh_hong.append(str(c.get("from_document_id") or c.get("from_so_ky_hieu")))
            case "nguoc":
                _bao_ngay_mau_thuan(doc, c, bd)
            case "ok":
                return Effectivity(
                    EffectivityVerdict.mot_phan_khong_xac_dinh, "thap",
                    f"{_ke_sua_doi(c)} từ {c.get('from_ngay_hieu_luc')}; CSDL quốc gia không "
                    "công bố dữ liệu cấp điều khoản nên không xác định được điều này còn "
                    "hiệu lực hay không")

    # ── Chưa hiệu lực ────────────────────────────────────────────────────────
    if bd > as_of:
        return Effectivity(EffectivityVerdict.chua_hieu_luc, "cao",
                           f"ngày hiệu lực {bd} còn ở tương lai so với {as_of}")

    # ── Mức 3 và mặc định — không biết thì NÓI là không biết ─────────────────
    tinh_trang = doc.get("tinh_trang")
    if tinh_trang == "HHL1P":
        return Effectivity(
            EffectivityVerdict.mot_phan_khong_xac_dinh, "thap",
            "văn bản hết hiệu lực một phần; CSDL quốc gia không công bố dữ liệu "
            "cấp điều khoản nên không xác định được điều này còn hiệu lực hay không")
    if tinh_trang == "HHL":
        return Effectivity(EffectivityVerdict.het_hieu_luc, "cao", "tình trạng MOJ = HHL")

    if canh_hong:
        return Effectivity(
            EffectivityVerdict.chua_xac_dinh, "thap",
            f"cạnh hiệu lực đi vào trỏ tới văn bản không có trong `documents` "
            f"({', '.join(canh_hong)}) — không đọc được ngày để kết luận")

    if tinh_trang == "CHL":
        # `thap`, KHÁC brief (brief ghim `trung_binh`) — ruling của chủ đề tài
        # 2026-08-30, ĐỪNG "sửa lại cho khớp brief". Lý do: phán quyết này chỉ
        # dựa vào `tinh_trang` của MOJ, thứ đã ĐO được là sai 4/6 trên chính
        # chuỗi lương tối thiểu, trong khi suy luận cùng chủ đề đúng 6/6 và
        # đang mang `trung_binh`. Để hai nguồn cùng nhãn là nói dối người đọc
        # về chất lượng bằng chứng.
        ghi_chu = f"; sẽ bị {', '.join(sap_toi)} thay thế" if sap_toi else ""
        return Effectivity(EffectivityVerdict.con_hieu_luc, "thap",
                           "không có tín hiệu chấm dứt nào trong đồ thị lẫn trong corpus; "
                           f"theo tình trạng MOJ = CHL, chưa đối chiếu cấp điều khoản{ghi_chu}")

    return Effectivity(EffectivityVerdict.chua_xac_dinh, "thap",
                       f"tình trạng MOJ = {tinh_trang!r} không nằm trong bảng mã đã biết "
                       "(CHL · HHL · HHL1P) — không suy ra được hiệu lực")


_SQL_DOC = text(
    "SELECT id, so_ky_hieu, loai_van_ban, ten, ngay_hieu_luc, ngay_het_hieu_luc,"
    " tinh_trang FROM documents WHERE id = :i"
)

# Hai chiều, một danh sách. Cột `from_*` ở NHÁNH THỨ HAI trỏ tới `to_document_id`
# — tên cột giữ nguyên vì chúng có nghĩa "văn bản ĐỐI DIỆN trong cạnh này", và
# `chieu` mới là thứ nói bên nào là ai. Xem bảng `TAC_DONG` đầu file.
#
#   di_vao: loai 20/21, `to_document_id = tôi`   → văn bản kia sửa/thay tôi
#   di_ra : loai 22/23, `from_document_id = tôi` → văn bản kia khai tử tôi
#
# LEFT JOIN chứ không JOIN: cạnh trỏ tới văn bản đã biến mất phải NỔI LÊN với
# `from_*` toàn NULL để `danh_gia` trả `chua_xac_dinh`, chứ không bị JOIN nuốt
# mất rồi âm thầm rơi vào nhánh "còn hiệu lực".
_SQL_CANH = text(
    "SELECT r.loai, 'di_vao' AS chieu, r.from_document_id, d2.ten AS from_ten,"
    " d2.so_ky_hieu AS from_so_ky_hieu, d2.ngay_hieu_luc AS from_ngay_hieu_luc"
    ' FROM "references" r LEFT JOIN documents d2 ON d2.id = r.from_document_id'
    " WHERE r.to_document_id = :i AND r.loai IN (20, 21)"
    " UNION ALL"
    " SELECT r.loai, 'di_ra', r.to_document_id, d2.ten,"
    " d2.so_ky_hieu, d2.ngay_hieu_luc"
    ' FROM "references" r LEFT JOIN documents d2 ON d2.id = r.to_document_id'
    " WHERE r.from_document_id = :i AND r.loai IN (22, 23)"
)

# ponytail: quét cả bảng rồi lọc chủ đề trong Python. `documents` có 57 dòng —
# lọc theo NGÀY trong SQL (rẻ, có index) và để quy tắc chủ đề ở đúng MỘT chỗ là
# `danh_gia`, nơi test được mà không cần Postgres. Nếu corpus lên hàng vạn văn
# bản thì thêm tiền lọc bằng `tsv`/trigram trước khi tới đây.
_SQL_UNG_VIEN = text(
    "SELECT so_ky_hieu, loai_van_ban, ten, ngay_hieu_luc FROM documents"
    " WHERE id <> :i AND ngay_hieu_luc > :bd AND ngay_hieu_luc <= :as_of"
)


def nap_ngu_canh(engine: Engine, doc_id: str, as_of: date) -> tuple[dict, list[dict], list[dict]]:
    """Đọc `(doc, canh_di_vao, ung_vien_ke_nhiem)` cho `danh_gia`.

    Nạp cạnh `loai` 20-23 THEO ĐÚNG CHIỀU của từng loại (xem `_SQL_CANH`): 20/21
    đọc ngược vào, 22/23 đọc xuôi ra. Cạnh MOJ gốc (`loai` 0-15) chưa nạp vì
    chiều của 242 dòng đó chưa được đo; `danh_gia` vẫn nhận mã MOJ nên chỉ cần
    nới câu SQL này SAU KHI đã đo, không phải trước.
    """
    with engine.connect() as conn:
        doc = dict(conn.execute(_SQL_DOC, {"i": doc_id}).mappings().one())
        canh = [dict(r) for r in conn.execute(_SQL_CANH, {"i": doc_id}).mappings().all()]
        ung_vien = (
            [dict(r) for r in conn.execute(
                _SQL_UNG_VIEN, {"i": doc_id, "bd": doc["ngay_hieu_luc"], "as_of": as_of}
            ).mappings().all()]
            if doc["ngay_hieu_luc"] is not None else []
        )
    return doc, canh, ung_vien


def danh_gia_theo_id(engine: Engine, doc_id: str, as_of: date) -> Effectivity:
    doc, canh, ung_vien = nap_ngu_canh(engine, doc_id, as_of)
    return danh_gia(doc, canh, as_of, ung_vien)


# ══ Mức 4 — bản đồ sửa đổi CẤP ĐIỀU KHOẢN (nguồn: Công báo, VBHN) ═══════════
#
# Ba mức trên đều phán quyết ở cấp VĂN BẢN, vì CSDL quốc gia chỉ công bố tới đó:
# `referenceProvisions` của MOJ khác null đúng 0/272. Nên `HHL1P` chỉ nói "hết
# hiệu lực một phần" mà không nói PHẦN NÀO, và Mức 3 buộc phải trả
# `mot_phan_khong_xac_dinh` cho cả 220 Điều của Bộ luật Lao động — kể cả 216
# Điều không ai đụng tới, lẫn 4 Điều thật sự đã đổi.
#
# Văn bản hợp nhất của Công báo lấp đúng khoảng trống đó, và lấp bằng CẤU TRÚC:
# `<w:footnoteReference>` nằm trong `<w:p>` nào thì `<w:p>` đó CHÍNH LÀ khoản bị
# sửa (xem `vbhn_parser.py`). Không LLM ở bất kỳ bước nào.
#
# `ap_sua_doi` là một LỚP PHỦ, không phải cơ chế thứ hai: nó nhận phán quyết cấp
# văn bản của `danh_gia` rồi làm nó CỤ THỂ hơn khi — và chỉ khi — có bằng chứng
# cấp điều khoản. Không có bản ghi thì trả về ĐÚNG object cũ (`is base`), nên
# 19.131/19.135 điều khoản không đổi một ký tự nào.

# Phán quyết đã dứt khoát ở cấp văn bản: sửa đổi cấp khoản không lật lại được.
# Một Điều của văn bản đã bị thay thế toàn bộ thì đã chết, bất kể footnote VBHN
# nói gì; và một văn bản chưa tới ngày hiệu lực thì chưa có gì để sửa.
_KHOA_O_CAP_VAN_BAN = frozenset({
    EffectivityVerdict.bi_thay_the,
    EffectivityVerdict.het_hieu_luc,
    EffectivityVerdict.chua_hieu_luc,
})

_THU_TU_TIN_CAY = ("cao", "trung_binh", "thap")


def _ke_sua_boi(b: dict) -> str:
    """Nêu ĐÍCH DANH văn bản đi sửa. Không có số hiệu thì nói là không có —
    `f"{None}"` in ra chữ "None" và người đọc sẽ tưởng đó là tên văn bản."""
    sk = b.get("sua_boi_so_ky_hieu")
    if not sk:
        return "một văn bản chưa đọc được số hiệu"
    dd = b.get("sua_boi_duong_dan")
    return f"{dd} của {sk}" if dd else sk


def ap_sua_doi(base: Effectivity, ban_ghi: Sequence[dict], as_of: date) -> Effectivity:
    """Làm CỤ THỂ phán quyết cấp văn bản bằng bản đồ sửa đổi cấp điều khoản.

    `ban_ghi` — dòng `sua_doi_dieu_khoan` của CHÍNH điều khoản này và của hậu
    duệ nó (xem `nap_sua_doi`), mỗi dòng có `vi_tri`, `sua_boi_so_ky_hieu`,
    `sua_boi_duong_dan`, `tu_ngay`, `nguon`, `do_tin_cay`.

    Ba nhánh, theo đúng thứ tự cấp thiết:

      1. **Đã tới ngày** ⇒ `bi_sua_doi`. Nguyên văn trong CSDL là bản TRƯỚC sửa
         đổi: trích dẫn vẫn đúng nguồn gốc, nhưng KHÔNG còn là bản hiện hành, và
         `ly_do` phải nói ra cả hai vế đó.
      2. **Chưa đọc được ngày** ⇒ `can_doi_chieu_tay`. Biết có sửa nhưng không
         biết từ bao giờ thì KHÔNG được mặc định là đã tới — cùng mặc định an
         toàn với cả file này.
      3. **Ngày còn ở tương lai** ⇒ `con_hieu_luc` kèm cảnh báo "sẽ bị". Nói "đã
         bị sửa" lúc này là sai theo chiều ngược lại: văn bản gốc đang ĐÚNG, và
         người dùng cần biết nó sắp đổi chứ không phải nó đã hỏng.
    """
    if not ban_ghi or base.verdict in _KHOA_O_CAP_VAN_BAN:
        return base

    da_toi = sorted((b for b in ban_ghi if b.get("tu_ngay") and b["tu_ngay"] <= as_of),
                    key=lambda b: b["tu_ngay"], reverse=True)
    chua_ro_ngay = [b for b in ban_ghi if not b.get("tu_ngay")]
    sap_toi = sorted((b for b in ban_ghi if b.get("tu_ngay") and b["tu_ngay"] > as_of),
                     key=lambda b: b["tu_ngay"])

    if da_toi:
        ke = "; ".join(
            f"{b['vi_tri']} bị sửa bởi {_ke_sua_boi(b)} từ {b['tu_ngay']}" for b in da_toi)
        return Effectivity(
            EffectivityVerdict.bi_sua_doi, _tin_cay_thap_nhat(da_toi),
            f"{ke} (nguồn: {_nguon(da_toi)}). Nguyên văn trong CSDL là bản TRƯỚC sửa đổi — "
            "trích dẫn đúng văn bản gốc nhưng KHÔNG phải bản hiện hành")

    if chua_ro_ngay:
        ke = "; ".join(f"{b['vi_tri']} bị sửa bởi {_ke_sua_boi(b)}" for b in chua_ro_ngay)
        return Effectivity(
            EffectivityVerdict.can_doi_chieu_tay, "thap",
            f"{ke} (nguồn: {_nguon(chua_ro_ngay)}), nhưng KHÔNG đọc được ngày hiệu lực từ "
            "ghi chú hợp nhất — không kết luận được điều khoản này đã đổi hay chưa")

    ke = "; ".join(f"{b['vi_tri']} sẽ bị {_ke_sua_boi(b)} sửa từ {b['tu_ngay']}"
                   for b in sap_toi)
    return Effectivity(
        EffectivityVerdict.con_hieu_luc, _tin_cay_thap_nhat(sap_toi),
        f"nguyên văn còn đúng tại {as_of}; {ke} (nguồn: {_nguon(sap_toi)})")


def _tin_cay_thap_nhat(ban_ghi: Sequence[dict]) -> str:
    """Một phán quyết dựa trên nhiều bản ghi không thể chắc hơn bản ghi yếu nhất."""
    muc = [b.get("do_tin_cay") for b in ban_ghi]
    return next((t for t in reversed(_THU_TU_TIN_CAY) if t in muc), "thap")


def _nguon(ban_ghi: Sequence[dict]) -> str:
    """Công báo yêu cầu ghi rõ nguồn khi phát hành lại thông tin — `ly_do` đi
    thẳng ra câu trả lời người dùng, nên nguồn phải nằm trong đó."""
    return ", ".join(dict.fromkeys(b.get("nguon") or "?" for b in ban_ghi))


# `t.id = p.id OR ...` — bản ghi của CHÍNH nó và của HẬU DUỆ nó, không phải của
# tổ tiên. Vì sao cần hậu duệ: câu trả lời thường dẫn cả "Điều 139", còn bản ghi
# lại neo ở "Điều 139 > Khoản 1"; tra đúng `provision_id` thôi thì claim dẫn cấp
# Điều đi qua mà không một cảnh báo nào — đúng lỗ hổng im lặng mà Mức 4 tồn tại
# để bịt. Vì sao KHÔNG lấy của tổ tiên: khoản 8a mới thêm neo về Điều 154 cha;
# lan ngược xuống sẽ dán nhãn "bị sửa" lên cả 9 khoản không ai đụng tới.
#
# `duong_dan` là đường dẫn phân cấp có thật (`"45/2019/QH14 > Điều 139 > Khoản 1"`)
# nên tiền tố + `' > '` là phép "là hậu duệ của". Nối thêm `' > '` chứ không chỉ
# `'%'`: `"Điều 13"` là tiền tố chuỗi của `"Điều 139"` nhưng KHÔNG phải tổ tiên nó.
# ĐÃ ĐO: 0/19.135 `duong_dan` chứa `%` hay `_`, nên LIKE không cần escape.
_SQL_SUA_DOI = text(
    "SELECT p.id AS provision_id, s.vi_tri, s.sua_boi_so_ky_hieu, s.sua_boi_duong_dan,"
    " s.tu_ngay, s.nguon, s.do_tin_cay"
    " FROM provisions p"
    " JOIN provisions t ON t.id = p.id"
    "   OR (t.document_id = p.document_id AND t.duong_dan LIKE p.duong_dan || ' > %')"
    " JOIN sua_doi_dieu_khoan s ON s.provision_id = t.id"
    " WHERE p.id = ANY(:ids)"
)


def nap_sua_doi(engine: Engine, provision_ids: Sequence[int]) -> dict[int, list[dict]]:
    """`provisions.id` → bản ghi sửa đổi của nó và của hậu duệ nó.

    Một truy vấn cho CẢ tập id (thường là toàn bộ provision của một câu trả
    lời), không phải một truy vấn mỗi claim.
    """
    ids = list(provision_ids)
    if not ids:
        return {}
    ra: dict[int, list[dict]] = {}
    with engine.connect() as conn:
        for r in conn.execute(_SQL_SUA_DOI, {"ids": ids}).mappings().all():
            ra.setdefault(r["provision_id"], []).append(dict(r))
    return ra
