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
  * **Mức 2a** — cạnh đồ thị "Thay thế"/"Sửa đổi, bổ sung" đi vào. Bắt được ca
    MOJ bỏ sót, `tin_cay = cao` vì có văn bản đích danh làm chứng.
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

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from sqlalchemy import Engine, text

# ── Mã quan hệ ────────────────────────────────────────────────────────────────
# 1/5/11/12 là mã MOJ (Bãi bỏ · Đình chỉ · Tạm ngưng · Thay thế); 20-23 là dải
# TỰ SUY RA mà `scripts/load_incoming_edges.py` ghi (xem `migrations/007`).
# `nap_ngu_canh` hiện chỉ nạp 20-23 — dải duy nhất đã ĐO được chiều (xem dưới)
# — nhưng `danh_gia` nhận cả hai để một loader về sau nạp thêm cạnh MOJ mà
# không phải sửa logic.
LOAI_THAY_THE = {1, 5, 11, 12, 21}
LOAI_SUA_DOI = {20}

# `loai` 22/23 ("Văn bản quy định hết hiệu lực [1 phần]") CỐ Ý vắng mặt ở trên.
# Đo trên cả 46 cạnh trong DB, chiều của parquet nhất quán 46/46: tên quan hệ
# luôn nói theo góc nhìn của `from_document_id`. Nên một cạnh ĐI VÀO mang
#   loai 20/21 = "văn bản `from` sửa/thay TÔI"      → tín hiệu khai tử
#   loai 22/23 = "TÔI làm văn bản `from` hết hiệu lực" → tín hiệu NGƯỢC
# 13/13 cạnh loai 22 và 5/5 cạnh loai 23 đều đi từ văn bản hiệu lực TRƯỚC, đúng
# như chiều này dự đoán. Coi 22/23 là khai tử sẽ tuyên NĐ 293/2025 — luật lương
# tối thiểu HIỆN HÀNH — là đã chết, vì nó có cạnh 22 đi vào từ NĐ 74/2024 mà
# chính nó vừa thay thế.

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

    # ── Mức 2a: cạnh đồ thị nói "bị thay thế" ────────────────────────────────
    for c in canh_di_vao:
        if c.get("loai") not in LOAI_THAY_THE:
            continue
        match _canh_dung_chieu(c, bd, as_of):
            case "hong":
                canh_hong.append(str(c.get("from_document_id") or c.get("from_so_ky_hieu")))
            case "nguoc":
                continue  # guard 1 — không vu cho văn bản cũ là kẻ thay thế
            case "sap_toi":
                sap_toi.append(f"{c.get('from_so_ky_hieu')} từ {c.get('from_ngay_hieu_luc')}")
            case "ok":
                if cung_chu_de(ten_doc, c.get("from_ten")):
                    return Effectivity(
                        EffectivityVerdict.bi_thay_the, "cao",
                        f"cạnh Thay thế trong đồ thị: bị {c.get('from_so_ky_hieu')} thay thế "
                        f"từ {c.get('from_ngay_hieu_luc')}")
                return Effectivity(
                    EffectivityVerdict.can_doi_chieu_tay, "thap",
                    f"có cạnh thay thế từ {c.get('from_so_ky_hieu')} nhưng KHÁC chủ đề "
                    f"({c.get('from_ten')!r} vs {ten_doc!r}) — nghi lỗi dữ liệu MOJ, "
                    "phải đối chiếu tay")

    # ── Mức 2b: đồ thị im lặng, suy luận từ chính corpus ─────────────────────
    # Cùng chủ đề + hiệu lực sau + đã có hiệu lực ⇒ văn bản trước bị thay thế.
    # Chọn ứng viên GIỐNG NHẤT (hoà thì sớm nhất) chứ không phải sớm nhất: tiêu
    # đề ngắn dễ chạm ngưỡng với một chủ đề lân cận, và lấy sớm nhất sẽ nêu tên
    # kẻ thay thế sai ngay cả khi phán quyết đúng.
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
        if c.get("loai") not in LOAI_SUA_DOI:
            continue
        match _canh_dung_chieu(c, bd, as_of):
            case "hong":
                canh_hong.append(str(c.get("from_document_id") or c.get("from_so_ky_hieu")))
            case "ok":
                return Effectivity(
                    EffectivityVerdict.mot_phan_khong_xac_dinh, "thap",
                    f"bị {c.get('from_so_ky_hieu')} sửa đổi, bổ sung từ "
                    f"{c.get('from_ngay_hieu_luc')}; CSDL quốc gia không công bố dữ liệu "
                    "cấp điều khoản nên không xác định được điều này còn hiệu lực hay không")

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
        ghi_chu = f"; sẽ bị {', '.join(sap_toi)} thay thế" if sap_toi else ""
        return Effectivity(EffectivityVerdict.con_hieu_luc, "trung_binh",
                           "không có tín hiệu chấm dứt nào trong đồ thị lẫn trong corpus; "
                           f"theo tình trạng MOJ = CHL, chưa đối chiếu cấp điều khoản{ghi_chu}")

    return Effectivity(EffectivityVerdict.chua_xac_dinh, "thap",
                       f"tình trạng MOJ = {tinh_trang!r} không nằm trong bảng mã đã biết "
                       "(CHL · HHL · HHL1P) — không suy ra được hiệu lực")


_SQL_DOC = text(
    "SELECT id, so_ky_hieu, loai_van_ban, ten, ngay_hieu_luc, ngay_het_hieu_luc,"
    " tinh_trang FROM documents WHERE id = :i"
)

# LEFT JOIN chứ không JOIN: cạnh trỏ tới văn bản đã biến mất phải NỔI LÊN với
# `from_*` toàn NULL để `danh_gia` trả `chua_xac_dinh`, chứ không bị JOIN nuốt
# mất rồi âm thầm rơi vào nhánh "còn hiệu lực".
_SQL_CANH = text(
    "SELECT r.loai, r.from_document_id, d2.ten AS from_ten,"
    " d2.so_ky_hieu AS from_so_ky_hieu, d2.ngay_hieu_luc AS from_ngay_hieu_luc"
    ' FROM "references" r LEFT JOIN documents d2 ON d2.id = r.from_document_id'
    " WHERE r.to_document_id = :i AND r.loai BETWEEN 20 AND 23"
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

    Chỉ nạp cạnh `loai` 20-23 — dải đã ĐO được chiều trên cả 46 cạnh. Cạnh MOJ
    gốc (`loai` 0-15) chưa nạp vì chiều của chúng chưa được kiểm; `danh_gia` vẫn
    nhận mã MOJ nên chỉ cần nới câu SQL này khi đã đo xong.
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
