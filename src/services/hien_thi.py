"""Quy tắc hiển thị — MỘT định nghĩa cho mọi đường đọc của người dùng (quyết
định 2026-09-28 mục 8–10, `docs/decisions/2026-09-28-trich-dan-day-du-va-lien-
ket-nguon.md`).

Một văn bản được HIỆN khi và chỉ khi đồng thời:

  1. `documents.tinh_trang` là mã còn hiệu lực đã biết của Bộ Tư pháp:
     `TINH_TRANG_HIEN`. Lượt làm mới toàn kho 2026-09-28 thấy gateway có mã
     `CCHL` (chưa có hiệu lực, 2 văn bản), được nạp thành `chua_hieu_luc`.
     "Chưa có hiệu lực" không phải "không còn hiệu lực", nên nó được hiện với
     nhãn của nó; văn bản ban hành mà hiệu lực sau cũng có thể mang CHL, và
     điều kiện 2 (`chua_hieu_luc`) giữ nó.
  2. Phán quyết của `effectivity` (nơi DUY NHẤT KLAW phán về hiệu lực) tại
     `as_of` là còn sống: `VERDICT_HIEN`.
  3. Có link chính thống đã kiểm — đúng luật của `trich_dan.lien_ket`.

Văn bản ẩn VẪN ở trong DB và trong đồ thị hiệu lực (để chỉ ra văn bản thay thế
và kiểm trích dẫn cũ) nhưng không bao giờ được liệt kê, đếm, tìm, truy hồi làm
căn cứ, trích dẫn hay mở thành trang văn bản.
`tests/test_services/test_hien_thi_bat_bien.py` canh mọi truy vấn đọc
`documents`/`provisions`/`chunks` ở tầng người dùng.

Người đọc không bao giờ thấy `ly_do`, `tin_cay` hay mã nội bộ (mục 10): chỉ nhãn
và, khi có, MỘT câu thường nêu văn bản sửa đổi/thay thế (`mo_ta`, `canh_bao`).
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import date

from fastapi import HTTPException
from sqlalchemy import Connection, Engine, text

from src.services.effectivity import Effectivity, VanBanNeu, danh_gia_toan_bo
from src.services.effectivity import EffectivityVerdict as V
from src.services.kho import _khop_so_hieu
from src.services.trich_dan import cach_trich, lien_ket, truong_trich_dan

TINH_TRANG_HIEN = ("CHL", "HHL1P", "chua_hieu_luc")

VERDICT_HIEN = frozenset({V.con_hieu_luc, V.bi_sua_doi, V.mot_phan_khong_xac_dinh, V.chua_hieu_luc})

# Đã chết theo KLAW. Chỉ văn bản thuộc nhóm này (hoặc Bộ Tư pháp khai HHL) mới
# được nói "không còn hiệu lực"; văn bản ẩn vì thiếu link hay chưa rõ tình trạng
# thì KHÔNG — nói vậy là nói sai về một văn bản có thể đang sống.
_DA_CHET = frozenset({V.het_hieu_luc, V.bi_thay_the})

THONG_DIEP_HET = "{} không còn hiệu lực nên không có trong phạm vi tra cứu."
THONG_DIEP_CHUA = "{} hiện chưa có trong phạm vi tra cứu."


def duoc_hien(van_ban: dict, e: Effectivity | None) -> bool:
    """Vị từ THUẦN của quy tắc — `van_ban` cần `tinh_trang`, `link_vbpl`, `link_chinhphu`."""
    return (
        van_ban.get("tinh_trang") in TINH_TRANG_HIEN
        and e is not None
        and e.verdict in VERDICT_HIEN
        and lien_ket(van_ban.get("link_vbpl"), van_ban.get("link_chinhphu")) is not None
    )


# Lọc tình trạng ở SQL; link lọc bằng CHÍNH `lien_ket` trong Python — một bản
# SQL thứ hai của luật host/đường dẫn là hai định nghĩa sẽ lệch nhau.
_SQL_UNG_VIEN = text(
    "SELECT id, tinh_trang, link_vbpl, link_chinhphu FROM documents WHERE tinh_trang = ANY(CAST(:tt AS text[]))"
)


def tap_hien_thi(conn: Connection, eff: dict[str, Effectivity]) -> frozenset[str]:
    """`documents.id` được hiện. `eff` là `danh_gia_toan_bo` mà người gọi đã tính
    TRƯỚC khi mở `conn` — gọi nó khi đang giữ `conn` là một request chiếm hai
    suất pool (xem `routes_tim_kiem._tim_kiem_sync`)."""
    rows = conn.execute(_SQL_UNG_VIEN, {"tt": list(TINH_TRANG_HIEN)}).mappings()
    return frozenset(r["id"] for r in rows if duoc_hien(r, eff.get(r["id"])))


def hien_thi_luc(engine: Engine, as_of: date) -> frozenset[str]:
    """Cho đường chưa giữ connection nào: phán quyết toàn kho (memo), rồi MỘT connection."""
    eff = danh_gia_toan_bo(engine, as_of)
    with engine.connect() as c:
        return tap_hien_thi(c, eff)


# ── Lời cho người đọc ────────────────────────────────────────────────────────


def mo_ta(e: Effectivity) -> str | None:
    """MỘT câu thường cho người đọc, không mã nội bộ, không "độ tin cậy", không
    ngày ISO. Chỉ nêu văn bản khi phán quyết có văn bản làm chứng."""
    ds = ", ".join(v.so_ky_hieu for v in e.van_ban)
    if e.verdict in (V.bi_sua_doi, V.mot_phan_khong_xac_dinh):
        return f"Đã được sửa đổi, bổ sung bởi {ds}." if ds else None
    if e.verdict == V.chua_hieu_luc and e.tu_ngay is not None:
        return f"Có hiệu lực từ ngày {e.tu_ngay:%d/%m/%Y}."
    if e.verdict in _DA_CHET:
        return f"Đã được thay thế bởi {ds}." if ds else None
    return None


# Nửa đầu của câu cảnh báo cạnh một trích dẫn. `mo_ta` là nửa sau.
_CANH_BAO = {
    V.mot_phan_khong_xac_dinh: "còn hiệu lực một phần.",
    V.bi_sua_doi: "— nguyên văn trích ở đây là bản trước khi sửa đổi.",
    V.chua_hieu_luc: "chưa có hiệu lực.",
    V.het_hieu_luc: "không còn hiệu lực.",
    V.bi_thay_the: "không còn hiệu lực.",
    V.chua_xac_dinh: "hiện chưa có trong phạm vi tra cứu.",
}


def canh_bao(so_ky_hieu: str, e: Effectivity) -> str | None:
    """Câu cảnh báo hiệu lực cho người đọc, mở bằng `"<số hiệu> "` (giao diện
    ghép cảnh báo với trích dẫn theo tiền tố đó). `None` = không cảnh báo."""
    if e.verdict == V.can_doi_chieu_tay:
        ds = ", ".join(v.so_ky_hieu for v in e.van_ban)
        return f"{so_ky_hieu} — điều khoản này có văn bản sửa đổi, bổ sung{f': {ds}' if ds else ''}; cần đối chiếu ngày áp dụng."
    dau = _CANH_BAO.get(e.verdict)
    if dau is None:
        return None
    return " ".join(x for x in (f"{so_ky_hieu} {dau}", mo_ta(e)) if x)


_SQL_VAN_BAN_NEU = text(
    "SELECT id, so_ky_hieu, ten, link_vbpl, link_chinhphu"
    " FROM documents WHERE id = ANY(CAST(:ids AS text[])) OR so_ky_hieu = ANY(CAST(:sk AS text[]))"
)


def nap_van_ban_dan(conn: Connection, neu: Iterable[VanBanNeu], hien: frozenset[str]) -> dict[VanBanNeu, dict]:
    """Văn bản được nêu tên → `schemas.VanBanDan`, MỘT truy vấn cho cả tập. `doc_id`
    chỉ khi chính văn bản đó được hiện; không tìm thấy thì chỉ còn số hiệu."""
    neu = list(dict.fromkeys(neu))
    if not neu:
        return {}
    rows = (
        conn.execute(
            _SQL_VAN_BAN_NEU,
            {
                "ids": [n.doc_id for n in neu if n.doc_id],
                "sk": [n.so_ky_hieu for n in neu if not n.doc_id],
            },
        )
        .mappings()
        .all()
    )
    theo_id = {r["id"]: r for r in rows}
    theo_so: dict[str, dict] = {}
    # ponytail: số hiệu trùng nhau (33 dòng 'Không số', vài cặp khác) — ưu tiên
    # văn bản đang hiện; nguồn chỉ có số hiệu là bản ghi VBHN, hiếm khi trùng.
    for r in sorted(rows, key=lambda r: (r["id"] not in hien, r["id"])):
        theo_so.setdefault(r["so_ky_hieu"], r)
    ra = {}
    for n in neu:
        r = theo_id.get(n.doc_id) if n.doc_id else theo_so.get(n.so_ky_hieu)
        if r is None:
            ra[n] = {"doc_id": None, "so_ky_hieu": n.so_ky_hieu, "ten_van_ban": None, "lien_ket": None}
            continue
        t = truong_trich_dan(dict(r))
        ra[n] = {
            "doc_id": r["id"] if r["id"] in hien else None,
            # Số hiệu của bằng chứng (đã làm sạch ở `effectivity._neu`), không
            # giá trị DB thô — một dòng corpus mang 'số: 34/2024/QH15'.
            "so_ky_hieu": n.so_ky_hieu,
            "ten_van_ban": t["ten_van_ban"],
            "lien_ket": t["lien_ket"],
        }
    return ra


def hieu_luc_ra(e: Effectivity, dan: dict[VanBanNeu, dict]) -> dict:
    """`schemas.HieuLucOut` của một phán quyết. `dan` từ `nap_van_ban_dan` trên
    đúng các `e.van_ban` của trang; `van_ban_lien_quan` là văn bản `mo_ta` nêu."""
    m = mo_ta(e)
    return {
        "verdict": e.verdict.value,
        "tin_cay": e.tin_cay,
        "ly_do": e.ly_do,
        "mo_ta": m,
        "van_ban_lien_quan": [dan[v] for v in e.van_ban if v in dan] if m else [],
    }


# ── Văn bản ẩn: trang văn bản và câu hỏi nêu tên nó ─────────────────────────


def van_ban_thay(
    e: Effectivity | None, eff: Mapping[str, Effectivity] | None = None, hien: frozenset[str] = frozenset()
) -> tuple[VanBanNeu, ...]:
    """Văn bản thay thế theo đồ thị — chỉ khi văn bản thật sự đã chết. Văn bản
    thay mà chính nó cũng đã chết thì đi tiếp theo cạnh thay thế của NÓ (cùng
    guard `effectivity._van_ban_thay`) tới văn bản đầu tiên được hiện hoặc còn
    sống: 90/2019 → 38/2022 → 74/2024 → 293/2025. Nhánh cụt ở một văn bản đã
    chết không ai thay thì không nêu — nêu nó là chỉ người đọc sang một văn bản
    cũng không còn hiệu lực. `eff` vắng: chỉ văn bản thay trực tiếp."""
    if e is None or e.verdict not in _DA_CHET:
        return ()
    eff = eff or {}
    ra: list[VanBanNeu] = []
    da_qua: set[VanBanNeu] = set()
    hang = list(e.van_ban)
    while hang:
        v = hang.pop(0)
        if v in da_qua:
            continue
        da_qua.add(v)
        tiep = eff.get(v.doc_id) if v.doc_id and v.doc_id not in hien else None
        if tiep is not None and tiep.verdict in _DA_CHET:
            hang += tiep.van_ban
        else:
            ra.append(v)
    return tuple(ra)


def thong_diep_an(van_ban: dict, e: Effectivity | None, goi_ten: bool = False) -> str:
    """Câu nói thẳng vì sao một văn bản ẩn không mở được. `goi_ten` — nêu tên văn
    bản ("Nghị định số 90/2019/NĐ-CP không còn…") cho lượt hỏi đáp; trang văn
    bản dùng "Văn bản này"."""
    chet = van_ban.get("tinh_trang") == "HHL" or (e is not None and e.verdict in _DA_CHET)
    goi = (
        goi_ten
        and cach_trich(None, van_ban.get("loai_van_ban"), van_ban.get("so_ky_hieu"), None, None, van_ban.get("ten"))
    ) or "Văn bản này"
    return (THONG_DIEP_HET if chet else THONG_DIEP_CHUA).format(goi)


def cau_van_ban_an(thong_diep: str, thay_the: Iterable[str]) -> str:
    """MỘT câu cho người hỏi đã nêu tên một văn bản ẩn — lượt tra cứu và lượt về
    kho dùng chung, để hai chỗ không nói hai cách."""
    ds = ", ".join(thay_the)
    return f"{thong_diep} Văn bản thay thế: {ds}." if ds else thong_diep


def van_ban_an(
    conn: Connection,
    van_ban: dict,
    eff: Mapping[str, Effectivity],
    hien: frozenset[str],
    goi_ten: bool = False,
) -> dict:
    """`schemas.VanBanAnOut` cho một văn bản ẩn: `thong_diep_an` và văn bản thay
    thế kèm link (`van_ban_thay`)."""
    e = eff.get(van_ban.get("id"))
    thay = van_ban_thay(e, eff, hien)
    dan = nap_van_ban_dan(conn, thay, hien)
    return {
        "ma": "khong_hien_thi",
        "so_ky_hieu": van_ban.get("so_ky_hieu") or "",
        "ten_van_ban": truong_trich_dan(van_ban)["ten_van_ban"],
        "thong_diep": thong_diep_an(van_ban, e, goi_ten),
        "thay_the": [dan[v] for v in thay],
    }


_SQL_DOC = text(
    "SELECT id, so_ky_hieu, ten, loai_van_ban, tinh_trang, link_vbpl, link_chinhphu FROM documents WHERE id = :i"
)


def chan_neu_an(engine: Engine, doc_id: str, as_of: date) -> frozenset[str]:
    """HTTP 404 `khong_hien_thi` khi `doc_id` có trong kho mà bị ẩn; không thì trả
    tập được hiện cho route dùng tiếp. Văn bản không tồn tại thì KHÔNG chặn ở đây
    — route giữ 404 cũ của nó. Gọi TRƯỚC khi route mở connection của mình (cùng
    lý do pool ở `tap_hien_thi`)."""
    eff = danh_gia_toan_bo(engine, as_of)
    with engine.connect() as c:
        hien = tap_hien_thi(c, eff)
        if doc_id in hien:
            return hien
        doc = c.execute(_SQL_DOC, {"i": doc_id}).mappings().one_or_none()
        if doc is None:
            return hien
        an = van_ban_an(c, dict(doc), eff, hien)
    raise HTTPException(status_code=404, detail={k: an[k] for k in ("ma", "thong_diep", "thay_the")})


_SQL_THEO_SO = text(
    "SELECT id, so_ky_hieu, ten, loai_van_ban, tinh_trang, link_vbpl, link_chinhphu FROM documents"
    " WHERE so_ky_hieu LIKE ANY(CAST(:mau AS text[]))"
)


# Số hiệu văn bản trong câu hỏi: `số/năm` đi SAU tên loại văn bản ("nghị định
# 90/2019", "NĐ 12/2022", "Thông tư số 10/2020"), hoặc số hiệu đủ hậu tố
# ("90/2019/NĐ-CP"). `số/năm` trơn không đủ: "ký tháng 01/2025", "kỳ lương
# 10/2025" là ngày tháng, và khi gần hết kho bị ẩn, bắt chúng là báo về một
# thông tư nông nghiệp người hỏi không hề nhắc tới. Lượt về kho vẫn dùng
# `kho.moi_so_hieu_trong` (người hỏi ở đó đang hỏi về chính kho).
_RE_SO_HIEU_VAN_BAN = re.compile(
    r"(?<!\w)(?:nghị\s+định|nđ|thông\s+tư(?:\s+liên\s+tịch)?|ttlt|tt|bộ\s+luật|luật|pháp\s+lệnh"
    r"|quyết\s+định|qđ|nghị\s+quyết|nq)\s*(?:số\s*)?:?\s*(\d{1,4}/\d{4})(?![\d/])"
    r"|(?<![\d/])(\d{1,4}/\d{4}/[^\s,.;:!?()]+)",
    re.IGNORECASE,
)


def so_hieu_van_ban_trong(cau_hoi: str) -> list[str]:
    """Số hiệu văn bản câu hỏi nêu, theo thứ tự, không trùng: `số/năm` hoặc số
    hiệu đủ hậu tố (khớp đúng hậu tố — "hợp đồng số 01/2025/HĐLĐ" không khớp
    thông tư 01/2025 nào)."""
    return list(dict.fromkeys(a or b for a, b in _RE_SO_HIEU_VAN_BAN.findall(unicodedata.normalize("NFC", cau_hoi))))


def van_ban_an_duoc_nhac(engine: Engine, cau_hoi: str, as_of: date) -> list[dict]:
    """Văn bản ẩn mà câu hỏi nêu số hiệu ("Nghị định 90/2019 còn hiệu lực không")
    → `VanBanAnOut`. 0 truy vấn khi câu hỏi không nêu số hiệu văn bản nào. Một số
    hiệu khớp cả văn bản đang hiện thì không báo gì: người hỏi đang nói văn bản đó."""
    sos = so_hieu_van_ban_trong(cau_hoi)
    if not sos:
        return []
    eff = danh_gia_toan_bo(engine, as_of)
    ra: list[dict] = []
    with engine.connect() as c:
        hien = tap_hien_thi(c, eff)
        # LIKE chỉ trên `số/năm` (chữ số và "/", không ký tự đại diện nào lọt
        # vào); hậu tố so trong Python, không phân biệt hoa thường.
        mau = [f"%{'/'.join(so.split('/')[:2])}%" for so in sos]
        rows = [dict(r) for r in c.execute(_SQL_THEO_SO, {"mau": mau}).mappings()]
        for so in sos:
            khop = [r for r in rows if _khop_so_hieu(so.upper(), (r["so_ky_hieu"] or "").upper())]
            if any(r["id"] in hien for r in khop):
                continue
            ra += [van_ban_an(c, r, eff, hien, goi_ten=True) for r in khop]
    return ra
