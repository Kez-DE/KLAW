"""Đọc câu BÃI BỎ ĐIỀU KHOẢN từ nguyên văn văn bản đi bãi bỏ → seed có bằng chứng.

Chủ dự án chốt 2026-09-30 (quyết định 2026-09-30 mục 9): mỗi điều, khoản, điểm bị một
văn bản khác bãi bỏ được ghi kèm điều khoản đi bãi bỏ, câu trích nguyên văn và nguồn
chính thống; điều khoản đó bị ẩn khỏi truy hồi, trích dẫn và thân trang văn bản.

    python -m scripts.trich_bai_bo [--ghi]      # mặc định: chỉ in báo cáo

Đầu vào: cạnh loai 23 ("hết hiệu lực 1 phần") đi ra và cạnh loai 20 ("sửa đổi, bổ sung")
đi vào văn bản deep đang được hiện — văn bản đi sửa cũng bãi bỏ điều khoản ("12. Bãi bỏ
khoản 5 Điều 6") —, cộng các cặp đã đối chiếu tay (`CAP_THEM`, `DOI_CHIEU_TAY`). Nguyên văn
văn bản đi bãi bỏ lấy từ JSON gateway Bộ Tư pháp (các thư mục `--tho`, thư mục trước thắng),
không có thì từ `provisions` của nó trong DB.
Đầu ra: `data/seed/bai_bo_dieu_khoan.yaml` (nạp bằng `scripts.nap_bai_bo_dieu_khoan`).

Parser THUẦN, tất định, 0 model. Ba dạng câu được nhận, mọi dạng khác bị bỏ:

  A. Câu tự nêu động từ: "Bãi bỏ khoản 3 Điều 4 và Điều 18 Nghị định số X …".
  B. Mục dưới một câu dẫn bãi bỏ: "Các quy định sau đây hết hiệu lực …" rồi
     "b) Khoản 5 Điều 9; các Điều 21, 22 Nghị định số X;".
  C. Khoản bãi bỏ trong một Điều đi sửa MỘT văn bản: "Điều 4. Sửa đổi, bổ sung một số
     điều của Nghị định số X" … "12. Bãi bỏ khoản 5 Điều 6; khoản 4 Điều 8.".

Một đoạn chỉ được ghi khi đọc TRỌN thành danh sách điều khoản (`muc_tieu`): chữ nào
ngoài văn phạm "điểm/khoản/Điều + số" (cụm từ, mẫu, phụ lục, "các quy định về …") làm
cả đoạn bị bỏ; "đoạn"/"khổ" bỏ đúng cụm của nó. Lời văn mới trong ngoặc kép là luật
được sửa, không phải câu của văn bản này — bị bỏ qua.
"""

import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

_MAP = str.maketrans({"Ð": "Đ", "ð": "đ", "\u00a0": " ", "–": "-", "—": "-"})


def _chuan(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "").translate(_MAP)).strip()


# ── Số hiệu văn bản trong câu ─────────────────────────────────────────────────
_RE_SO = re.compile(r"(?<![\d/])(\d{1,4})\s*/\s*(\d{4})\s*/\s*([A-ZĐa-zđ0-9]+(?:\s*-\s*[A-ZĐa-zđ0-9]+)*)")
_RE_NAY = re.compile(r"\b(?:bộ luật|luật|pháp lệnh|nghị định|nghị quyết|thông tư|quyết định)\s+này\b", re.I)
_RE_LOAI = re.compile(r"\b(?:bộ luật|luật|pháp lệnh|nghị định|nghị quyết|thông tư|quyết định)\b", re.I)


def khoa_so_hieu(s: str) -> str:
    """ "10/2025/TT- BNNMT" và "10/2025/TT-BNNMT" là một văn bản."""
    m = _RE_SO.search(_chuan(s))
    return f"{int(m[1])}/{m[2]}/{m[3].replace(' ', '')}".upper() if m else ""


# ── Danh sách điều khoản ──────────────────────────────────────────────────────
_SO = r"\d+[a-zđ]?(?![\w/])"
_CHU = r"[a-zđ]\d?(?![\w/])"
_DON_VI = {"điều": _SO, "khoản": _SO, "điểm": _CHU, "đoạn": r"\d+(?![\w/])", "khổ": r"thứ \w+"}
# Số trơn nối tiếp ("các Điều 21, 22 và 28") thuộc cùng cụm; nhắc lại tên đơn vị
# ("Điều 44 và Điều 58") là cụm MỚI — khoản đang chờ chỉ thuộc Điều ngay sau nó —
# trừ sau "đến" ("Điều 21 đến Điều 24").
_RE_DON_VI = re.compile(
    r"(?P<dv>điều|khoản|điểm|đoạn|khổ)\s+(?P<ds>(?:{x})(?:\s*(?:,|và)\s*(?:{x})|\s*đến\s*(?:(?P=dv)\s+)?(?:{x}))*)".format(
        x="|".join(dict.fromkeys(_DON_VI.values()))
    ),
    re.I,
)
_RE_NOI = re.compile(r"\s*(?:,|và|;)?\s*(?:các|từ)?\s*", re.I)
_RE_DAU = re.compile(r"^(?:(?:các\s+)?quy\s+định\s+(?:tại|của)\s+)?", re.I)
_KHOANG_TOI_DA = 60


def _danh_sach(dv: str, ds: str) -> list[str] | None:
    """ "21, 22 và 28" / "21 đến 24" / "a, b" → từng số hiệu; khoảng "đến" chỉ trên số trơn."""
    tach = re.split(r"\s*(,|và|đến)\s*", re.sub(rf"\b{dv}\s+", "", ds, flags=re.I))
    ra = [tach[0].lower()]
    for sep, so in zip(tach[1::2], tach[2::2], strict=True):
        if sep == "đến":
            a, b = ra[-1], so.lower()
            if not (a.isdigit() and b.isdigit()) or not 0 < int(b) - int(a) <= _KHOANG_TOI_DA:
                return None
            ra += [str(n) for n in range(int(a) + 1, int(b) + 1)]
        else:
            ra.append(so.lower())
    return ra


def muc_tieu(doan: str) -> list[str]:
    """Đoạn "điểm c khoản 2 và điểm a khoản 3 Điều 94" → `["Điều 94 > Khoản 2 > Điểm c", …]`.

    Đọc TRÁI SANG PHẢI như câu luật: điểm/khoản chờ tới Điều đóng nó. Đoạn không đọc
    trọn (chữ lạ, khoản không có Điều, khoản của nhiều Điều cùng lúc) → `[]`, không đoán.
    """
    s = _RE_DAU.sub("", _chuan(doan).rstrip(" .;:,"))
    ra: list[str] = []
    cho_diem: list[str] = []
    cho_khoan: list[tuple[str, list[str]]] = []
    hong = False  # cụm có "đoạn"/"khổ": một phần khoản, không ẩn được — bỏ cả cụm
    i = 0
    while i < len(s):
        n = _RE_NOI.match(s, i)
        i = n.end() if n and n.end() > i else i
        if i >= len(s):
            break
        m = _RE_DON_VI.match(s, i)
        if m is None:
            return []
        i = m.end()
        dv = m["dv"].lower()
        so = _danh_sach(dv, m["ds"])
        if so is None:
            return []
        if dv in ("đoạn", "khổ"):
            hong = True
        elif dv == "điểm":
            cho_diem += so
        elif dv == "khoản":
            if cho_diem:
                if len(so) != 1:
                    return []
                cho_khoan.append((so[0], cho_diem))
                cho_diem = []
            else:
                cho_khoan += [(k, []) for k in so]
        else:  # điều
            if cho_khoan or cho_diem:
                if len(so) != 1 or (cho_khoan and cho_diem):
                    return []
                d = f"Điều {so[0]}"
                cum = [f"{d} > Khoản {k}" + (f" > Điểm {x}" if x else "") for k, ds in cho_khoan for x in (ds or [""])]
                cum += [f"{d} > Điểm {x}" for x in cho_diem]
            else:
                cum = [f"Điều {x}" for x in so]
            if not hong:
                ra += cum
            cho_diem, cho_khoan, hong = [], [], False
    return [] if cho_diem or cho_khoan or hong else list(dict.fromkeys(ra))


# ── Cấu trúc câu của văn bản đi bãi bỏ ────────────────────────────────────────
_RE_DIEU = re.compile(r"^Điều\s+(\d+[a-zđ]?)\s*[.:]", re.I)
_RE_KHOAN = re.compile(r"^(\d+[a-zđ]?)\s*[.)]\s")
_RE_DIEM = re.compile(r"^([a-zđ])\s*\)\s")
_RE_GACH = re.compile(r"^[-+•]\s")
_RE_BAI_BO = re.compile(r"bãi\s+bỏ", re.I)
_RE_DONG_TU_SAU = re.compile(
    r"^\s*(?:(?:các|những)\s+)?(?:quy\s+định\s+(?:tại|của)\s+|điều,\s*khoản(?:,\s*điểm)?\s+sau(?:\s+đây)?\s*:\s*)?",
    re.I,
)
# "bãi bỏ các nội dung quy định tại:" (45/2021/NĐ-CP) là câu dẫn thường; "các nội dung
# quy định về thuế … tại" (32/2013/QH13) thì giới hạn nội dung.
_RE_DAN_CAM = re.compile(
    r"nội\s+dung(?!\s+(?:quy\s+định\s+)?tại\s*:$)|cụm\s+từ|quy\s+định\s+về|sửa\s+đổi|thay\s+thế|\btrừ\b"
    r"|tạm\s+ngưng|đình\s+chỉ",
    re.I,
)
_RE_TRU = re.compile(r"\btrừ\b", re.I)
_RE_DA_SUA = re.compile(r"\s*[,(]?\s*đã\s+được\s+sửa\s+đổi", re.I)  # ngay sau số hiệu
_RE_NGAY = re.compile(r"từ\s+ngày\s+(\d{1,2})(?:\s+tháng\s+|/)(\d{1,2})(?:\s+năm\s+|/)(\d{4})", re.I)


@dataclass(frozen=True)
class Trich:
    """Một câu bãi bỏ của văn bản đi bãi bỏ, cho MỘT văn bản bị bãi bỏ."""

    vi_tri: str  # "Điều 21 khoản 4 điểm b" — điều khoản đi bãi bỏ
    trich: str  # nguyên văn (câu dẫn/tiêu đề " … " câu), khoảng trắng đã gộp
    dieu_khoan: list[str] = field(default_factory=list)  # "Điều 9 > Khoản 5" …
    tu_ngay: date | None = None  # ngày câu tự nêu; None = ngày hiệu lực của văn bản
    kiem_boi: str = "trich-bai-bo"  # "doi-chieu-tay": dòng `DOI_CHIEU_TAY`


def _cap(dong: str) -> int | None:
    if _RE_DIEU.match(dong):
        return 0
    if _RE_KHOAN.match(dong):
        return 1
    if _RE_DIEM.match(dong):
        return 2
    return 3 if _RE_GACH.match(dong) else None


def _ngoac_cuoi(dong: str) -> bool | None:
    """Dấu ngoặc kép cuối dòng mở (True) hay đóng (False) một đoạn trích; None: không có.
    '"' mở khi đứng sau khoảng trắng/đầu dòng/':' '(', còn lại là đóng."""
    for k in range(len(dong) - 1, -1, -1):
        ch = dong[k]
        if ch in "“„":
            return True
        if ch == "”":
            return False
        if ch == '"':
            return k == 0 or dong[k - 1].isspace() or dong[k - 1] in ":("
    return None


def _than(dong: str) -> str:
    """Bỏ số thứ tự đầu dòng ("b) ", "12. ", "- ")."""
    for r in (_RE_KHOAN, _RE_DIEM, _RE_GACH):
        if m := r.match(dong):
            return dong[m.end() :]
    return dong


def _ngay(s: str) -> date | None:
    m = _RE_NGAY.search(s)
    return date(int(m[3]), int(m[2]), int(m[1])) if m else None


def _doc_doan(doan: str, cat_ten_van_ban: bool) -> list[str]:
    """Các đoạn ';' của phần nêu điều khoản; đoạn cuối cắt tên văn bản ("của Nghị định số")."""
    phan = doan.split(";")
    if cat_ten_van_ban:
        cuoi = phan[-1]
        if m := _RE_LOAI.search(cuoi):
            cuoi = cuoi[: m.start()]
        phan[-1] = re.sub(r"(?:\s*\b(?:của|tại|trong|thuộc|số))+\s*$", "", cuoi, flags=re.I)
    return [x for p in phan for x in muc_tieu(p)]


def _sau_van_ban_khac(doan: str) -> str:
    """Bỏ mọi đoạn ';' tới đoạn cuối còn nêu một văn bản khác (số hiệu, "… này", hay tên loại
    văn bản ở đoạn không phải cuối — "Điều 7 của Luật Y; …" không thuộc văn bản đang đọc)."""
    phan = doan.split(";")
    moc = max(
        (
            k
            for k, p in enumerate(phan)
            if _RE_SO.search(p) or _RE_NAY.search(p) or (k < len(phan) - 1 and _RE_LOAI.search(p))
        ),
        default=-1,
    )
    return ";".join(phan[moc + 1 :])


def trich_van_ban(dong: list[str], so_hieu: str) -> list[Trich]:
    """Mọi câu bãi bỏ điều khoản của văn bản `so_hieu` trong nguyên văn `dong` (theo thứ tự)."""
    dong = [_chuan(d) for d in dong]
    khoa = khoa_so_hieu(so_hieu)
    trong_ngoac, cap, vi_tri = [], [], []
    # Trong/ngoài ngoặc kép theo DẤU NGOẶC CUỐI mỗi dòng (`_ngoac_cuoi`): văn bản thật mở
    # bằng '"' rồi đóng bằng '”' (59/2014/NĐ-CP Điều 1), và một dấu lạc (42/2017/NĐ-CP) làm
    # phép đếm chẵn lẻ lệch tới hết văn bản; dòng kết bằng dấu đóng thì luôn ra khỏi ngoặc.
    mo_ngoac = False
    dk = {"Điều": "", "khoản": "", "điểm": ""}
    for d in dong:
        mo = mo_ngoac or d.startswith(("“", '"', "„"))
        if (x := _ngoac_cuoi(d)) is not None:
            mo_ngoac = x
        trong_ngoac.append(mo)
        c = _cap(d)
        cap.append(c)
        if not mo:
            if c == 0:
                dk = {"Điều": _RE_DIEU.match(d)[1], "khoản": "", "điểm": ""}
            elif c == 1:
                dk = {**dk, "khoản": _RE_KHOAN.match(d)[1], "điểm": ""}
            elif c == 2:
                dk = {**dk, "điểm": _RE_DIEM.match(d)[1]}
        vi_tri.append(" ".join(f"{k} {v}" for k, v in dk.items() if v))

    def cha(i: int, bo_dong_thuong: bool = False) -> int | None:
        """Dòng cha: dòng ngoài ngoặc gần nhất cấp cao hơn. Câu dẫn (dạng B) có thể là một
        dòng không số thứ tự; tiêu đề đi sửa (dạng C) thì luôn có (`bo_dong_thuong`)."""
        for j in range(i - 1, -1, -1):
            if trong_ngoac[j] or (bo_dong_thuong and cap[j] is None):
                continue
            if cap[j] is None or cap[i] is None or cap[j] < cap[i]:
                return j
        return None

    # Luật sửa đổi MỘT văn bản ("Quốc hội ban hành Luật sửa đổi, bổ sung một số điều của Luật
    # bảo hiểm y tế số 25/2008/QH12", 46/2014/QH13): tiêu đề Điều đi sửa không nhắc lại số hiệu.
    dau = next((k for k, c in enumerate(cap) if c == 0 and not trong_ngoac[k]), len(dong))
    so_loi_ban_hanh = {
        khoa_so_hieu(x[0])
        for d in dong[:dau]
        if re.search(r"ban\s+hành\b.*\bsửa\s+đổi", d, re.I)
        for x in _RE_SO.finditer(d)
    }
    chi_sua = so_loi_ban_hanh == {khoa}

    ra: list[Trich] = []
    for i, goc in enumerate(dong):
        if trong_ngoac[i]:
            continue
        # Lời văn mới trích trong câu ("… như sau: “Điều 7. …”") cũng là luật được sửa.
        d = re.sub(r"“[^”]*(?:”|$)|\"[^\"]*(?:\"|$)", " ", goc)
        so = [m for m in _RE_SO.finditer(d) if khoa_so_hieu(m[0]) == khoa]
        if so:
            m = so[0]
            dong_tu = list(_RE_BAI_BO.finditer(d[: m.start()]))
            j = cha(i)
            if dong_tu:  # dạng A
                phan = _RE_DONG_TU_SAU.sub("", d[dong_tu[-1].end() : m.start()], count=1)
                trich, ngay = goc, _ngay(d[: dong_tu[-1].start()])
            elif cap[i] is not None and j is not None and _la_cau_dan(dong[j]):  # dạng B
                phan = d[len(d) - len(_than(d)) : m.start()]
                trich, ngay = f"{dong[j]} … {goc}", _ngay(dong[j])
            else:
                continue
            duoi = d[m.end() :].split(". ")[0]
            if _RE_TRU.search(duoi):
                continue  # "…, trừ …" thu hẹp phạm vi — không ẩn cả điều khoản
            if _RE_DA_SUA.match(duoi):
                continue  # số điều khoản của BẢN ĐÃ SỬA; kho giữ bản gốc — có thể lệch số
            if muc := _doc_doan(_sau_van_ban_khac(phan), cat_ten_van_ban=True):
                ra.append(Trich(vi_tri[i], trich, muc, ngay))
            continue
        # Dạng C: khoản/điểm "Bãi bỏ …" không nêu văn bản, trong Điều/khoản đi sửa MỘT văn bản.
        if _RE_SO.search(d) or _RE_NAY.search(d) or _RE_LOAI.search(d) or cap[i] is None:
            continue
        than = _than(d)
        if not (dt := re.match(r"bãi\s+bỏ\s+", than, re.I)) or (j := cha(i, bo_dong_thuong=True)) is None:
            continue
        # Tiêu đề Điều có thể tách thành hai đoạn ("Điều 77. Sửa đổi … của Luật giáo dục đại
        # học" + "Sửa đổi, bổ sung, bãi bỏ … số 08/2012/QH13 như sau:", 74/2014/QH13).
        k = j + 1
        while k < i and cap[k] is None and not trong_ngoac[k]:
            k += 1
        tieu_de = " ".join(dong[j:k])
        so_tieu_de = [khoa_so_hieu(x[0]) for x in _RE_SO.finditer(tieu_de)]
        if so_tieu_de != [khoa] and not (so_tieu_de == [] and chi_sua and cap[j] == 0):
            continue
        if not re.search(r"sửa\s+đổi|bãi\s+bỏ", tieu_de, re.I) or _RE_DA_SUA.search(tieu_de):
            continue
        if muc := _doc_doan(_RE_DONG_TU_SAU.sub("", than[dt.end() :], count=1), cat_ten_van_ban=False):
            ra.append(Trich(vi_tri[i], f"{tieu_de} … {goc}", muc, None))
    return ra


def _la_cau_dan(dong: str) -> bool:
    """Câu dẫn của một danh sách bãi bỏ TRỌN điều khoản: có động từ bãi bỏ/hết hiệu lực, không
    giới hạn nội dung (cụm từ, "nội dung quy định về", trừ …), kết bằng ':' hoặc "hiệu lực"."""
    return bool(
        re.search(r"bãi\s+bỏ|hết\s+hiệu\s+lực", dong, re.I)
        and not _RE_DAN_CAM.search(dong)
        and (dong.endswith(":") or re.search(r"hiệu\s+lực(?:\s+thi\s+hành)?\.?$", dong, re.I))
    )


# ── Chạy: cạnh loai 20/23 của văn bản được hiện → seed ────────────────────────
SEED = Path("data/seed/bai_bo_dieu_khoan.yaml")
THU_MUC_THO = (Path("data/raw/moj"),)
# Cặp (bị bãi bỏ, đi bãi bỏ) đã đối chiếu tay mà đồ thị chưa có cạnh loai 23 lúc chạy (N1:
# cạnh parquet ghi nhầm "thay thế"; `load_incoming_edges.CANH_DOI_CHIEU_NGUYEN_VAN` sửa).
CAP_THEM = (("169188", "178259"), ("169363", "178259"))
# Câu bãi bỏ mà parser CỐ Ý không đọc (mục 9(b)), đã đối chiếu tay với toàn văn gateway:
# (id bị bãi bỏ, id đi bãi bỏ, điều khoản đi bãi bỏ, điều khoản bị bãi bỏ, các dòng nguyên văn
# nối " … "). `trich_tay` kiểm từng dòng còn NGUYÊN VĂN, đúng thứ tự, mỗi lần sinh seed.
DOI_CHIEU_TAY: tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    # 49/2026/NĐ-CP: "(đã được sửa đổi …)" là câu parser bỏ; khoản 12 Điều 4 của 226/2025/NĐ-CP
    # "Sửa đổi, bổ sung khoản 4 và bổ sung khoản 5 vào Điều 77" — khoản 4 có trong bản gốc kho giữ.
    (
        "169363",
        "187157",
        "Điều 16 khoản 3 điểm d",
        ("Điều 77 > Khoản 4",),
        (
            "3. Các quy định sau đây hết hiệu lực kể từ ngày Nghị định này có hiệu lực thi hành:",
            "d) Khoản 4 Điều 77 của Nghị định số 102/2024/NĐ-CP (đã được sửa đổi, bổ sung tại khoản 12 Điều 4"
            " của Nghị định số 226/2025/NĐ-CP);",
        ),
    ),
    # 226/2025/NĐ-CP Điều 7: gạch đầu dòng dưới câu dẫn bãi bỏ cả cụm từ lẫn điều khoản; mục gạch
    # không nêu số hiệu nên parser không đọc. Chỉ mục đọc trọn thành điều khoản được ghi.
    (
        "169188",
        "181906",
        "Điều 7 khoản 3 điểm c",
        ("Điều 7",),
        (
            "3. Thay thế, bổ sung, bãi bỏ các điều, từ, cụm từ tại Nghị định số 101/2024/NĐ-CP",
            "c) Bãi bỏ điều, các từ, cụm từ như sau:",
            "- Điều 7;",
        ),
    ),
    (
        "169363",
        "181906",
        "Điều 7 khoản 4 điểm c",
        ("Điều 69 > Khoản 1 > Điểm b",),
        (
            "4. Thay thế, bổ sung, bãi bỏ các điểm, từ, cụm từ, mẫu tại Nghị định số 102/2024/NĐ-CP",
            "c) Bãi bỏ một số điểm, khoản, cụm từ, mẫu như sau:",
            "- Điểm b khoản 1 Điều 69;",
        ),
    ),
)
_DAU_SEED = """\
# Điều khoản BỊ BÃI BỎ bởi văn bản khác (quyết định 2026-09-30 mục 9, migration 043).
# Sinh bằng `python -m scripts.trich_bai_bo --ghi`; nạp bằng
# `python -m scripts.nap_bai_bo_dieu_khoan --ghi` (`ingest` tự nạp lại sau mỗi lượt).
# `trich`: nguyên văn (khoảng trắng đã gộp) văn bản đi bãi bỏ, câu dẫn/tiêu đề " … " câu;
# `dieu_khoan`: phần sau số hiệu của `provisions.duong_dan`; `tu_ngay`: ngày câu tự nêu,
# không có thì ngày hiệu lực của văn bản đi bãi bỏ.
"""


def trich_tay(dong: list[str], d: str, r: str) -> list[Trich]:
    """Dòng `DOI_CHIEU_TAY` của cặp (`d` bị bãi bỏ, `r` đi bãi bỏ). Mỗi dòng trích phải có
    NGUYÊN VĂN, đúng thứ tự, trong toàn văn `dong` của `r` — lệch là `ValueError`, không ghi."""
    dong = [_chuan(x) for x in dong]
    ra = []
    for dd, rr, vi_tri, dieu_khoan, cac_dong in DOI_CHIEU_TAY:
        if (dd, rr) != (d, r):
            continue
        i = -1
        for x in cac_dong:
            try:
                i = dong.index(_chuan(x), i + 1)
            except ValueError:
                raise ValueError(f"DOI_CHIEU_TAY {r} {vi_tri}: không thấy nguyên văn {x!r}") from None
        ra.append(Trich(vi_tri, " … ".join(map(_chuan, cac_dong)), list(dieu_khoan), None, "doi-chieu-tay"))
    return ra


def dong_nguyen_van(conn, doc_id: str, thu_muc: tuple[Path, ...]) -> list[str]:
    """Các đoạn `<p>` của toàn văn gateway; không có tệp thì `noi_dung` điều khoản trong DB."""
    from bs4 import BeautifulSoup
    from sqlalchemy import text

    for m in thu_muc:
        if (p := m / f"{doc_id}.json").exists():
            soup = BeautifulSoup(
                (json.loads(p.read_text(encoding="utf-8")).get("documentContent") or {}).get("content") or "",
                "html.parser",
            )
            for br in soup.find_all("br"):
                br.replace_with(" ")
            return [t for x in soup.find_all("p") if (t := _chuan(x.get_text(" ")))]
    return [
        _chuan(x)
        for x in conn.execute(
            text("SELECT noi_dung FROM provisions WHERE document_id = :i AND cap <> 'mo_dau' ORDER BY thu_tu"),
            {"i": doc_id},
        ).scalars()
    ]


def hang_seed(conn, cap: list[tuple[str, str]], thu_muc: tuple[Path, ...], kiem_luc: datetime) -> tuple[list, list]:
    """(dòng seed, cặp bị bỏ kèm lý do). Mọi điều khoản của một câu phải có trong kho, không
    thì bỏ cả câu: số lệch là dấu hiệu đọc nhầm văn bản."""
    from sqlalchemy import text

    ids = sorted({x for c in cap for x in c})
    van_ban = {
        r["id"]: dict(r)
        for r in conn.execute(
            text("SELECT id, so_ky_hieu, ngay_hieu_luc, link_vbpl FROM documents WHERE id = ANY(:ids)"), {"ids": ids}
        ).mappings()
    }
    ra, bo = [], []
    for d, r in cap:
        vd, vr = van_ban[d], van_ban[r]
        co = {
            dd.split(" > ", 1)[1]
            for dd in conn.execute(text("SELECT duong_dan FROM provisions WHERE document_id = :i"), {"i": d}).scalars()
            if " > " in dd
        }
        dong = dong_nguyen_van(conn, r, thu_muc)
        trich = trich_van_ban(dong, vd["so_ky_hieu"]) + trich_tay(dong, d, r)
        if not trich:
            bo.append((vd["so_ky_hieu"], vr["so_ky_hieu"], "không có câu bãi bỏ trọn điều khoản đọc được"))
        for t in trich:
            tu_ngay = t.tu_ngay or vr["ngay_hieu_luc"]
            if thieu := [x for x in t.dieu_khoan if x not in co]:
                bo.append((vd["so_ky_hieu"], vr["so_ky_hieu"], f"{t.vi_tri}: không có trong kho {thieu}"))
            # Cùng ngày là hợp lệ: luật sửa trước khi luật gốc có hiệu lực (12/2017/QH14 bãi bỏ
            # BLHS 100/2015/QH13 Điều 292 từ đúng 01/01/2018). TRƯỚC ngày đó là đọc nhầm văn bản.
            elif tu_ngay is None or (vd["ngay_hieu_luc"] and tu_ngay < vd["ngay_hieu_luc"]):
                bo.append((vd["so_ky_hieu"], vr["so_ky_hieu"], f"{t.vi_tri}: ngày {tu_ngay} không sau văn bản"))
            else:
                link = vr["link_vbpl"] or ""
                ra.append(
                    {
                        "van_ban": vd["so_ky_hieu"],
                        "van_ban_id": d,
                        "boi": vr["so_ky_hieu"],
                        "boi_id": r,
                        "boi_dieu_khoan": t.vi_tri,
                        "dieu_khoan": t.dieu_khoan,
                        "trich": t.trich,
                        "url": link if link.startswith("https://vbpl.vn/") else f"https://vbpl.vn/van-ban/chi-tiet/{r}",
                        "tu_ngay": tu_ngay,
                        "kiem_boi": t.kiem_boi,
                        "kiem_luc": kiem_luc,
                    }
                )
    return ra, bo


def cap_ung_vien(canh: list[tuple[int, str, str]], hien: frozenset[str]) -> list[tuple[str, str]]:
    """Cạnh `(loai, from, to)` → cặp (bị bãi bỏ, đi bãi bỏ) mà bị bãi bỏ đang được hiện: loai 23
    đọc xuôi (`to` khai tử `from` một phần), loai 20 đọc ngược (`from` sửa `to`) — cùng chiều
    của `effectivity._SQL_CANH`. Cộng các cặp đối chiếu tay."""
    cap = {(f, t) if loai == 23 else (t, f) for loai, f, t in canh}
    return sorted({c for c in cap if c[0] in hien} | set(CAP_THEM) | {(d, r) for d, r, *_ in DOI_CHIEU_TAY})


def _cap_ung_vien(engine, as_of: date) -> list[tuple[str, str]]:
    from sqlalchemy import text

    from src.services.hien_thi import hien_thi_luc

    with engine.connect() as c:
        canh = c.execute(
            text(
                'SELECT DISTINCT r.loai, r.from_document_id, r.to_document_id FROM "references" r'
                " JOIN documents d ON d.id = CASE r.loai WHEN 23 THEN r.from_document_id ELSE r.to_document_id END"
                " WHERE r.loai IN (20, 23) AND d.depth = 'deep'"
            )
        ).all()
    return cap_ung_vien(canh, hien_thi_luc(engine, as_of))


if __name__ == "__main__":
    import yaml

    from src.services.db import get_engine

    tho = tuple(Path(sys.argv[k + 1]) for k, a in enumerate(sys.argv) if a == "--tho") or THU_MUC_THO
    e = get_engine()
    cap = _cap_ung_vien(e, date.today())
    with e.connect() as c:
        hang, bo = hang_seed(c, cap, tho, datetime.now(UTC).replace(microsecond=0))
    print(
        f"{len(cap)} cặp; {len({(h['van_ban_id'], h['boi_id']) for h in hang})} cặp có câu bãi bỏ đọc được;"
        f" {len(hang)} câu; {sum(len(h['dieu_khoan']) for h in hang)} điều khoản"
    )
    for x in bo:
        print("  bỏ:", *x)
    if "--ghi" in sys.argv:

        class _KhongNeo(yaml.SafeDumper):  # ngày/giờ dùng chung không thành &id001/*id001
            def ignore_aliases(self, data):
                return True

        SEED.write_text(
            _DAU_SEED + yaml.dump(hang, Dumper=_KhongNeo, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8",
        )
        print(f"đã ghi {SEED}")
