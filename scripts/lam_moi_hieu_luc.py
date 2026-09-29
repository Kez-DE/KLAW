"""Làm mới tình trạng hiệu lực từ gateway Bộ Tư pháp và kiểm link vbpl.vn bằng
máy, cho mọi văn bản trong kho — chạy tay, không theo lịch (quyết định
2026-09-28 mục 2, 6, 8, 12).

    python -m scripts.lam_moi_hieu_luc [--chi-deep] [--tu-id ID] [--dry-run] [--cache DIR]
    python -m scripts.lam_moi_hieu_luc --tu-seed [--dry-run]

1. Hiệu lực: GET `{moj_api_base}/doc/{id}` (≤1 request / `moj_rate_limit_sleep`
   giây, backoff luỹ thừa trên 400/429/5xx — `MojClient`). Các trường hiệu lực của
   response (`docNum`, mã `effStatus`, `effFrom`, `effTo`, `agencyName`), URL và lúc
   đọc vào seed bằng chứng `data/seed/hieu_luc_gateway.jsonl` (commit), rồi DB nạp
   TỪ seed đó: `tinh_trang` = mã, `ngay_hieu_luc` = `effFrom`, `ngay_het_hieu_luc` =
   `effTo`, `co_quan_ban_hanh` = `agencyName` khi đang NULL, `hieu_luc_kiem_luc` =
   lúc đọc. `--tu-seed` chỉ làm bước nạp này, 0 request: dựng lại kho (ingest +
   `load_incoming_edges`) rồi chạy nó là có lại đúng trạng thái lượt làm mới đã
   đọc. KHÔNG đụng `provisions` hay chữ. Phán quyết hiệu lực vẫn là việc của
   `src/services/effectivity.py` lúc chạy; cột ở đây chỉ là dữ kiện của nó.
2. Ghi đè có bằng chứng (mục 12): cột có trong `data/seed/hieu_luc_ghi_de.yaml`
   THẮNG gateway ở mọi lượt nạp — nguyên văn chính thống cho thấy tình trạng của
   CSDL quốc gia đã cũ, nên lượt làm mới không được ghi ngược lại; chỗ gateway nói
   khác được báo.
3. Link: GET `https://vbpl.vn/van-ban/chi-tiet/{id}` (≤1 request/giây, User-Agent
   nêu rõ), kiểm HTTP 200 + `<title>` chứa số hiệu + `article:published_time`
   + 7 giờ = `ngay_ban_hanh`; ghi bằng chứng vào `data/seed/link_vbpl_da_kiem.yaml`
   rồi nạp qua `scripts.nap_link_cong_luat.nap_da_kiem` (dòng trượt → NULL). Chỉ
   trượt về NỘI DUNG mới xoá link (`ket_luan_duoc`); trang chung "Văn bản pháp
   luật", 403, 429/5xx, lỗi mạng là vbpl.vn đang không phục vụ: giữ dòng seed cũ.
   Trượt mà văn bản đã có `link_chinhphu` (docid đã biết) thì kiểm dự phòng trang
   vanban.chinhphu.vn đó (tiêu đề + ô "Ngày ban hành"); kết quả vào `ly_do`.
4. Cầu dao: một nguồn lỗi `NGAT_SAU` lần liền nhau thì thôi gửi request tới nó (id
   còn lại giữ như cũ); lượt chạy làm hơn 5 % văn bản đã kiểm mất link đạt hoặc rơi
   từ tình trạng đã biết về "chưa rõ" thì KHÔNG ghi DB hay seed (`ngat_ghi`).

Chạy lại được và tiếp tục được: mọi response gateway (ĐỦ `documentContent`, cùng
dạng `data/raw/moj/*.json` để đợt sau dựng provisions không cần tải lại) và đầu
trang vbpl.vn được giữ trong `--cache` (mặc định `data/raw/lam_moi/<hôm nay>/`);
id đã có trong cache không tải lại. Trang vbpl.vn không kết luận được không vào
cache, lần sau kiểm lại: đo 2026-09-28, vbpl.vn trả trang chung với HTTP 200 cho
86/2010/NĐ-CP rồi vài giờ sau trả đúng trang; 17:02–17:21 UTC cùng ngày nó trả
trang chung cho 23/23 id còn gateway trả 503 mọi request. Lần làm mới sau dùng
thư mục của ngày đó.
"""

import argparse
import html
import json
import re
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import yaml
from sqlalchemy import Engine, text

from scripts.build_seed import TINH_TRANG_MAP
from scripts.nap_link_cong_luat import ID_GATEWAY, KIEM_BOI_MAY, MAU_VBPL, SEED_DA_KIEM, nap_da_kiem
from src.config import get_settings
from src.models.domain import khoa_so_ky_hieu
from src.services.db import get_engine, run_migrations
from src.services.moj_client import MojClient

UA = "klaw-thesis/1.0 (kiem-link-van-ban; +https://github.com/Kez-DE/KLAW)"
NGHI_VBPL = 1.0
_THU_LAI_VBPL = {429, 500, 502, 503, 504}
_LECH_UTC_VN = timedelta(hours=7)
# Cầu dao nguồn. K2 thật (2026-09-28, 1.822 id): 10 id gateway lỗi, nhiều nhất 2
# id liền nhau; gateway sập thì mỗi id tốn ~53 giây backoff (~27 giờ cả kho).
NGAT_SAU = 5

SEED_HIEU_LUC = Path("data/seed/hieu_luc_gateway.jsonl")
SEED_GHI_DE = Path("data/seed/hieu_luc_ghi_de.yaml")
_HOST_GATEWAY = "vbpl-bientap-gateway.moj.gov.vn"
# Bằng chứng ghi đè chỉ từ nguồn nhà nước (quyết định mục 1, 13), không trang thương mại.
NGUON_CHINH_THONG = frozenset(
    {_HOST_GATEWAY, "vbpl.vn", "vanban.chinhphu.vn", "datafiles.chinhphu.vn", "congbao.chinhphu.vn"}
)
_COT = ("tinh_trang", "ngay_hieu_luc", "ngay_het_hieu_luc")
_TINH_TRANG_DA_BIET = set(TINH_TRANG_MAP.values())
_KHOA_BANG_CHUNG = {"id", "docNum", "effStatus", "effFrom", "effTo", "agencyName", "url", "luc"}
_KHOA_GHI_DE = {"so_ky_hieu", *_COT, "dieu_khoan", "url", "lay_luc"}

_RE_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_RE_CANON = re.compile(r'<link[^>]*rel="canonical"[^>]*href="([^"]+)"', re.I)
_RE_XUAT_BAN = re.compile(r'<meta[^>]*property="article:published_time"[^>]*content="([^"]+)"', re.I)
_RE_NGAY_CP = re.compile(r"Ngày ban hành\s*</td>\s*<td>\s*(\d\d)-(\d\d)-(\d{4})")
_RE_CHI_TIET = re.compile(r"https://vbpl\.vn/van-ban/chi-tiet/[a-z0-9-]+--[a-z0-9-]+")

_SQL_DOCS = text(
    "SELECT id, so_ky_hieu, depth, ngay_ban_hanh, tinh_trang, ngay_hieu_luc, ngay_het_hieu_luc,"
    " co_quan_ban_hanh, link_chinhphu FROM documents"
    " WHERE (NOT :chi_deep OR depth = 'deep') AND (CAST(:tu_id AS text) IS NULL OR id >= :tu_id) ORDER BY id"
)
_SQL_DOCS_NAP = text(
    "SELECT id, so_ky_hieu, depth, tinh_trang, ngay_hieu_luc, ngay_het_hieu_luc, co_quan_ban_hanh,"
    " hieu_luc_kiem_luc FROM documents ORDER BY id FOR UPDATE"
)
_SQL_HIEU_LUC = text(
    "UPDATE documents SET tinh_trang = :tinh_trang, ngay_hieu_luc = :ngay_hieu_luc,"
    " ngay_het_hieu_luc = :ngay_het_hieu_luc, co_quan_ban_hanh = :co_quan_ban_hanh,"
    " hieu_luc_kiem_luc = :hieu_luc_kiem_luc WHERE id = :id"
)


def _ngay(v: str | None) -> date | None:
    return date.fromisoformat(v[:10]) if v else None


def cot_tu_gateway(d: dict) -> dict:
    """Response `/doc/{id}` (khoá `data`) → các cột hiệu lực. Mã `effStatus` chưa
    biết → `chua_xac_dinh` (bị ẩn theo mục 8), không bao giờ đoán thành CHL."""
    return {
        "so_ky_hieu": d.get("docNum"),
        "tinh_trang": TINH_TRANG_MAP.get((d.get("effStatus") or {}).get("code") or "", "chua_xac_dinh"),
        "ngay_hieu_luc": _ngay(d.get("effFrom")),
        "ngay_het_hieu_luc": _ngay(d.get("effTo")),
        "ngay_ban_hanh": _ngay(d.get("issueDate")),
        "co_quan": (d.get("agencyName") or "").strip() or None,
    }


def _so(s: str | None) -> str:
    """Khoá so số hiệu của phép kiểm: `khoa_so_ky_hieu` + bỏ tiền tố "… số:" mà 3
    dòng parquet mang ('Luật số 51/2024/QH15'; gateway và vbpl.vn ghi '51/2024/QH15').
    Chỉ tiền tố: đuôi lạ ('(1)', 'TT- BTC') là nguyên văn nguồn, gateway ghi y hệt."""
    return re.sub(r"^\D*\bsố\s*:?\s*(?=\d)", "", khoa_so_ky_hieu(s), flags=re.I).casefold()


def cung_so(so_kho: str | None, so_nguon: str | None) -> bool:
    return _so(so_kho) == _so(so_nguon)


def _tieu_de(trang: str) -> str:
    m = _RE_TITLE.search(trang)
    return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else ""


def _canonical(dau: str) -> str | None:
    m = _RE_CANON.search(dau)
    return html.unescape(m.group(1)) if m else None


def _co_so(so_ky_hieu: str, tieu_de: str) -> bool:
    """Tiêu đề chứa số hiệu theo ranh giới: 45/2019 không khớp trong 145/2019."""
    so = re.escape(_so(so_ky_hieu))
    return re.search(rf"(?<![\w/]){so}(?![\w/])", khoa_so_ky_hieu(tieu_de).casefold()) is not None


def ket_luan_duoc(status: int | None, canonical: str | None) -> bool:
    """Kết quả tải một trang vbpl.vn có nói được gì về VĂN BẢN không. Chỉ 404/410,
    hay một trang chi tiết thật (canonical có slug `…--{id}`, của id này hay id
    khác), mới là kết luận. Trang chung "Văn bản pháp luật" (canonical
    `/van-ban/chi-tiet/{id}` không slug), trang chủ, 403, 429/5xx, lỗi mạng là
    vbpl.vn đang không phục vụ: không được xoá link đã kiểm vì nó."""
    if status in (404, 410):
        return True
    return status == 200 and _RE_CHI_TIET.fullmatch(canonical or "") is not None


def kiem_trang_chinhphu(so_ky_hieu: str, ngay_ban_hanh: date | None, status: int | None, trang: str) -> str | None:
    """Phép kiểm dự phòng trên vanban.chinhphu.vn (quyết định mục 2: vbpl.vn →
    vanban.chinhphu.vn; owner rule 2026-09-28 (b): chỉ khi đã biết docid) → lý do
    trượt hoặc None. Cùng hai phép kiểm nội dung: tiêu đề chứa số hiệu, ô "Ngày ban
    hành" (dd-mm-yyyy, giờ VN) bằng ngày trong kho."""
    if status != 200:
        return f"HTTP {status}"
    tieu_de = _tieu_de(trang)
    if not _co_so(so_ky_hieu, tieu_de):
        return f"tiêu đề {tieu_de!r} không chứa số hiệu {so_ky_hieu!r}"
    m = _RE_NGAY_CP.search(trang)
    tren_trang = date(int(m[3]), int(m[2]), int(m[1])) if m else None
    if tren_trang is None or tren_trang != ngay_ban_hanh:
        return f"ngày ban hành trên trang {tren_trang} ≠ trong kho {ngay_ban_hanh}"
    return None


def kiem_trang_vbpl(
    so_ky_hieu: str, ngay_ban_hanh: date | None, gid: str, status: int | None, url_cuoi: str, dau: str
) -> tuple[str | None, str | None]:
    """Phép kiểm máy một trang vbpl.vn → (canonical, lý do trượt hoặc None).

    Kiểm chính điều người mở sẽ thấy ở đầu trang (SSR): trang là trang chi tiết
    của ĐÚNG id này (canonical kết thúc `--{id}`; mẫu cũ chuyển về trang chủ vẫn
    trả 200, id vbpl.vn không hiển thị thì ra trang chung "Văn bản pháp luật"),
    tiêu đề chứa số hiệu theo ranh giới (45/2019 không khớp trong 145/2019), ngày
    xuất bản (UTC) + 7 giờ bằng ngày ban hành trong kho.
    """
    if status != 200:
        return None, f"HTTP {status} tại {url_cuoi}"
    tieu_de = _tieu_de(dau)
    canonical = _canonical(dau)
    if not canonical or not re.fullmatch(rf"https://vbpl\.vn/van-ban/chi-tiet/[a-z0-9-]+--{re.escape(gid)}", canonical):
        return canonical, f"canonical {canonical!r} (tiêu đề {tieu_de!r}) không phải trang chi tiết của {gid}"
    if not _co_so(so_ky_hieu, tieu_de):
        return canonical, f"tiêu đề {tieu_de!r} không chứa số hiệu {so_ky_hieu!r}"
    m = _RE_XUAT_BAN.search(dau)
    if not m:
        return canonical, "thiếu article:published_time"
    tren_trang = (datetime.fromisoformat(m.group(1)) + _LECH_UTC_VN).date()
    if tren_trang != ngay_ban_hanh:
        return canonical, f"ngày ban hành trên trang {tren_trang} ≠ trong kho {ngay_ban_hanh}"
    return canonical, None


# ── Seed bằng chứng hiệu lực + seed ghi đè ───────────────────────────────────
def hang_bang_chung(doc_id: str, data: dict, luc: datetime) -> dict:
    """Response `/doc/{id}` → một dòng `SEED_HIEU_LUC`: đúng các trường mà
    `cot_tu_gateway` dùng để ghi, nguyên văn gateway, cùng URL và lúc đọc."""
    return {
        "id": doc_id,
        "docNum": data.get("docNum"),
        "effStatus": {"code": (data.get("effStatus") or {}).get("code")},
        "effFrom": data.get("effFrom"),
        "effTo": data.get("effTo"),
        "agencyName": data.get("agencyName"),
        "url": f"{get_settings().moj_api_base.rstrip('/')}/doc/{ID_GATEWAY.get(doc_id, doc_id)}",
        "luc": luc.isoformat(),
    }


def doc_bang_chung(p: Path) -> dict[str, dict]:
    """`SEED_HIEU_LUC` → id → dòng. Máy sinh nhưng là tệp commit nên vẫn kiểm: đủ
    khoá, URL `/doc/{id}` của gateway cho đúng id, lúc đọc có múi giờ và không ở
    tương lai, không trùng id. Sai là dừng."""
    ra: dict[str, dict] = {}
    if not p.exists():
        return ra
    bay_gio = datetime.now(UTC)
    for i, dong in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        h = json.loads(dong)
        noi = f"{p}:{i} ({h.get('id')})"
        if set(h) != _KHOA_BANG_CHUNG:
            raise ValueError(f"{noi}: khoá phải đúng {sorted(_KHOA_BANG_CHUNG)}, được {sorted(h)}")
        u = urlsplit(h["url"])
        if (u.scheme, u.hostname) != ("https", _HOST_GATEWAY) or not u.path.endswith(
            f"/doc/{ID_GATEWAY.get(h['id'], h['id'])}"
        ):
            raise ValueError(f"{noi}: url {h['url']!r} không phải /doc/{{id}} của {_HOST_GATEWAY}")
        luc = datetime.fromisoformat(h["luc"])
        if luc.tzinfo is None or luc > bay_gio:
            raise ValueError(f"{noi}: luc {h['luc']!r} phải có múi giờ và không ở tương lai")
        if h["id"] in ra:
            raise ValueError(f"{noi}: trùng id")
        ra[h["id"]] = h
    return ra


def ghi_bang_chung(p: Path, bang: dict[str, dict]) -> None:
    p.write_text("".join(json.dumps(bang[k], ensure_ascii=False) + "\n" for k in sorted(bang)), encoding="utf-8")


def kiem_ghi_de(doc_id: str, hang: dict, bay_gio: datetime) -> dict:
    """Một dòng `SEED_GHI_DE` (người viết) → chính dòng đó, sau khi kiểm chặt vì
    nó thắng CSDL quốc gia: ít nhất một cột của `_COT`; tình trạng là mã đã biết;
    ngày là YYYY-MM-DD hoặc null (xoá ngày gateway ghi sai); `dieu_khoan` nêu điều
    khoản; `url` https trên nguồn nhà nước; `lay_luc` có múi giờ, không ở tương
    lai; `so_ky_hieu` để bắt dòng lệch id (so với DB lúc nạp)."""
    noi = f"{SEED_GHI_DE}: {doc_id}"
    if la := set(hang) - _KHOA_GHI_DE:
        raise ValueError(f"{noi}: khoá lạ {sorted(la)}")
    if not any(k in hang for k in _COT):
        raise ValueError(f"{noi}: không ghi đè cột nào trong {_COT}")
    if "tinh_trang" in hang and hang["tinh_trang"] not in _TINH_TRANG_DA_BIET:
        raise ValueError(f"{noi}: tinh_trang phải thuộc {sorted(_TINH_TRANG_DA_BIET)}, được {hang['tinh_trang']!r}")
    for k in _COT[1:]:
        if hang.get(k) is not None and type(hang[k]) is not date:
            raise ValueError(f"{noi}: {k} phải là ngày YYYY-MM-DD (không trong nháy) hoặc null")
    if not str(hang.get("dieu_khoan") or "").strip():
        raise ValueError(f"{noi}: thiếu dieu_khoan (điều khoản chính thống cho thấy tình trạng khác)")
    u = urlsplit(str(hang.get("url") or ""))
    if u.scheme != "https" or u.hostname not in NGUON_CHINH_THONG:
        raise ValueError(
            f"{noi}: url {hang.get('url')!r} phải là https trên nguồn nhà nước {sorted(NGUON_CHINH_THONG)}"
        )
    lay_luc = hang.get("lay_luc")
    if not isinstance(lay_luc, datetime) or lay_luc.tzinfo is None or lay_luc > bay_gio:
        raise ValueError(f"{noi}: lay_luc phải là thời điểm có múi giờ, không ở tương lai")
    if not hang.get("so_ky_hieu"):
        raise ValueError(f"{noi}: thiếu so_ky_hieu")
    return hang


def doc_ghi_de(p: Path) -> dict[str, dict]:
    tho = (yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None) or {}
    if not isinstance(tho, dict):
        raise ValueError(f"{p}: phải là map doc_id → hàng")
    bay_gio = datetime.now(UTC)
    return {str(k): kiem_ghi_de(str(k), v or {}, bay_gio) for k, v in tho.items()}


def tinh_cot(docs: list[dict], bang_chung: dict[str, dict], ghi_de: dict[str, dict]) -> tuple[list[dict], dict]:
    """Dòng DB + seed bằng chứng + seed ghi đè → (dòng cần UPDATE, báo cáo). Thuần.

    Gateway: tình trạng = mã; ngày gateway để trống thì GIỮ ngày đang có — NULL ở
    đây không phải "không có hạn" mà là "bản ghi gateway thiếu dữ kiện", và
    `effectivity` Mức 1 cần đúng ngày đó; cơ quan chỉ điền khi đang NULL. Ghi đè
    áp sau cùng nên luôn thắng; gateway (khác null) nói khác thì BÁO, không ghi.
    """
    co = {d["id"] for d in docs}
    if thieu := sorted(set(ghi_de) - co):
        raise ValueError(f"{SEED_GHI_DE}: doc_id không có trong documents: {thieu}")
    cap_nhat, lech_so, noi_khac, doi_sau = [], [], [], []
    doi_nong, ngay_doi = Counter(), Counter()
    ap = mat = 0
    for d in docs:
        h, gd = bang_chung.get(d["id"]), ghi_de.get(d["id"]) or {}
        if h is None and not gd:
            continue
        ten = f"{d['so_ky_hieu']} ({d['id']})"
        if gd and not cung_so(d["so_ky_hieu"], gd["so_ky_hieu"]):
            raise ValueError(f"{SEED_GHI_DE}: {d['id']} so_ky_hieu {gd['so_ky_hieu']!r} ≠ DB {d['so_ky_hieu']!r}")
        moi = {k: d[k] for k in (*_COT, "co_quan_ban_hanh", "hieu_luc_kiem_luc")}
        cot = None
        # `docNum` null (Hiến pháp 2013): không có số để so; `build_seed` đã đối chiếu tiêu đề.
        if h is not None and h["docNum"] is not None and not cung_so(d["so_ky_hieu"], h["docNum"]):
            lech_so.append(f"{ten}: gateway docNum {h['docNum']!r}")
        elif h is not None:
            cot, ap = cot_tu_gateway(h), ap + 1
            moi["tinh_trang"] = cot["tinh_trang"]
            moi.update({k: cot[k] for k in _COT[1:] if cot[k] is not None})
            moi["co_quan_ban_hanh"] = d["co_quan_ban_hanh"] or cot["co_quan"]
            moi["hieu_luc_kiem_luc"] = datetime.fromisoformat(h["luc"])
        for k in _COT:
            if k in gd:
                if cot is not None and cot[k] is not None and cot[k] != gd[k]:
                    noi_khac.append(f"{ten}: {k} gateway {cot[k]} — giữ ghi đè {gd[k]} ({gd['dieu_khoan']})")
                moi[k] = gd[k]
        if moi["tinh_trang"] != d["tinh_trang"]:
            doi = f"{d['tinh_trang']} → {moi['tinh_trang']}"
            if d["depth"] == "deep":
                doi_sau.append(f"{d['so_ky_hieu']}: {doi}")
            else:
                doi_nong[doi] += 1
            mat += d["tinh_trang"] != "chua_xac_dinh" and moi["tinh_trang"] == "chua_xac_dinh"
        for k in _COT[1:]:
            if cot is not None and cot[k] is None and d[k] is not None and k not in gd:
                ngay_doi[f"{k}: gateway trống, giữ ngày trong kho"] += 1
            elif moi[k] != d[k]:
                ngay_doi[f"{k}: {'điền mới' if d[k] is None else 'đổi'}"] += 1
                if d["depth"] == "deep":
                    doi_sau.append(f"{d['so_ky_hieu']}: {k} {d[k]} → {moi[k]}")
        if moi != {k: d[k] for k in moi}:
            cap_nhat.append({"id": d["id"], **moi})
    return cap_nhat, {
        "bang_chung_ap": ap,
        "bang_chung_khong_co_trong_db": len(set(bang_chung) - co),
        "lech_so_ky_hieu": lech_so,
        "ghi_de": {"dong": len(ghi_de), "gateway_noi_khac": noi_khac},
        "tinh_trang_doi_tang_sau": doi_sau,
        "tinh_trang_doi_tang_nong_metadata": dict(doi_nong),
        "ngay": dict(ngay_doi),
        "mat_tinh_trang": mat,
        "cap_nhat": len(cap_nhat),
    }


def nap_hieu_luc(engine: Engine, bang_chung: dict[str, dict], ghi_de: dict[str, dict], ghi: bool) -> dict:
    """`tinh_cot` trên TOÀN bộ `documents`, MỘT transaction; `ghi=False` chỉ báo cáo."""
    run_migrations("038")
    with engine.begin() as c:
        cap_nhat, bao = tinh_cot([dict(r) for r in c.execute(_SQL_DOCS_NAP).mappings()], bang_chung, ghi_de)
        for u in cap_nhat if ghi else ():
            c.execute(_SQL_HIEU_LUC, u)
    return bao


# ── Tải ──────────────────────────────────────────────────────────────────────
def _ghi(p: Path, obj: dict) -> None:
    """Ghi qua tệp tạm rồi đổi tên: một lần ngắt giữa chừng không để lại JSON cụt
    mà lần sau tưởng là cache hợp lệ."""
    tam = p.with_suffix(".tam")
    tam.write_text(json.dumps(obj, ensure_ascii=False, default=str), encoding="utf-8")
    tam.replace(p)


def _lay_gateway(client: MojClient, gid: str, thu_muc: Path) -> tuple[dict | None, datetime | None, str | None]:
    p = thu_muc / f"{gid}.json"
    if not p.exists():
        try:
            _ghi(p, client.fetch_doc(gid))
        except (httpx.HTTPError, ValueError) as e:  # hết lượt thử lại: ghi lý do, không dừng cả đợt
            return None, None, f"{type(e).__name__}: {str(e)[:200]}"
    return json.loads(p.read_text(encoding="utf-8")), datetime.fromtimestamp(p.stat().st_mtime, UTC), None


def _lay_vbpl(http: httpx.Client, gid: str, thu_muc: Path) -> dict:
    p = thu_muc / f"{gid}.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    for lan in range(5):
        time.sleep(NGHI_VBPL)
        try:
            r = http.get(MAU_VBPL.format(id=gid))
        except httpx.TransportError as e:
            if lan == 4:
                return {"status": None, "url": MAU_VBPL.format(id=gid), "dau": "", "loi": str(e)[:200]}
        else:
            if r.status_code not in _THU_LAI_VBPL or lan == 4:
                break
        time.sleep(3.0 * 2**lan)
    ban = {
        "status": r.status_code,
        "url": str(r.url),
        "dau": r.text.split("</head>")[0],
        "luc": datetime.now(UTC).isoformat(),
    }
    if ket_luan_duoc(ban["status"], _canonical(ban["dau"])):  # không kết luận được: lần sau tải lại
        _ghi(p, ban)
    return ban


def _du_phong_chinhphu(d: dict) -> str | None:
    """GET `link_chinhphu` đã biết (≤1 request/giây, không cache: chỉ chạy cho
    văn bản vbpl.vn trượt) → lý do trượt hoặc None."""
    time.sleep(NGHI_VBPL)
    try:
        r = httpx.get(d["link_chinhphu"], timeout=30, follow_redirects=True, headers={"User-Agent": UA})
    except httpx.TransportError as e:
        return f"không mở được: {str(e)[:200]}"
    return kiem_trang_chinhphu(d["so_ky_hieu"], d["ngay_ban_hanh"], r.status_code, r.text)


def lan_luot(ten: str, gids: list[str], lay: Callable[[str], object], hong: Callable[[object], bool]) -> dict:
    """`lay(gid)` lần lượt; `hong(kết quả)` `NGAT_SAU` lần liền nhau là nguồn đang
    sập thì thôi gửi request. Id chưa tải vắng mặt trong kết quả (giữ như cũ)."""
    ra, lien = {}, 0
    for i, gid in enumerate(gids, 1):
        ra[gid] = lay(gid)
        lien = lien + 1 if hong(ra[gid]) else 0
        if lien >= NGAT_SAU:
            print(f"[{ten}] NGẮT sau {lien} lỗi liền nhau (tới {gid}); {len(gids) - i} id không tải", flush=True)
            break
        if i % 100 == 0:
            print(f"[{ten}] {i}/{len(gids)}", flush=True)
    return ra


def _tai_het(docs: list[dict], cache: Path) -> tuple[dict, dict]:
    """Hai vòng tải song song — hai host, mỗi host một nhịp và một cầu dao riêng."""
    s = get_settings()
    (cache / "moj").mkdir(parents=True, exist_ok=True)
    (cache / "vbpl").mkdir(parents=True, exist_ok=True)
    gids = [ID_GATEWAY.get(d["id"], d["id"]) for d in docs]

    def vong_gateway() -> dict:
        client = MojClient(base=s.moj_api_base, sleep=s.moj_rate_limit_sleep)
        return lan_luot("gateway", gids, lambda g: _lay_gateway(client, g, cache / "moj"), lambda r: r[2] is not None)

    def vong_vbpl() -> dict:
        with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": UA}) as http:
            return lan_luot(
                "vbpl",
                gids,
                lambda g: _lay_vbpl(http, g, cache / "vbpl"),
                lambda t: not ket_luan_duoc(t["status"], _canonical(t["dau"])),
            )

    with ThreadPoolExecutor(max_workers=2) as ex:
        g, v = ex.submit(vong_gateway), ex.submit(vong_vbpl)
        return g.result(), v.result()


def doi_chieu_link(docs: list[dict], vb: dict[str, dict], cu: dict[str, dict]) -> tuple[dict, dict]:
    """Trang vbpl.vn đã tải → (dòng seed link cho mọi id đã kiểm, báo cáo).

    Trượt KHÔNG kết luận được (`ket_luan_duoc`), hay id cầu dao chưa cho tải: giữ
    dòng seed cũ nếu có — link đã kiểm không mất vì vbpl.vn đang không phục vụ.
    `mat_link` đếm link từng đạt nay trượt về nội dung (cho `ngat_ghi`)."""
    seed, ly_do, truot, du_phong, giu = {}, Counter(), [], [], []
    mat = 0
    for d in docs:
        gid = ID_GATEWAY.get(d["id"], d["id"])
        trang = vb.get(gid)
        if trang is None:
            canonical, ld = None, f"chưa kiểm: vbpl.vn ngắt sau {NGAT_SAU} lỗi liền nhau"
        else:
            canonical, ld = kiem_trang_vbpl(
                d["so_ky_hieu"], d["ngay_ban_hanh"], gid, trang["status"], trang["url"], trang["dau"]
            )
            if trang.get("loi"):
                ld = f"không mở được: {trang['loi']}"
        if ld and d["id"] in cu and (trang is None or not ket_luan_duoc(trang["status"], canonical)):
            seed[d["id"]] = cu[d["id"]]
            giu.append(f"{d['so_ky_hieu']} ({d['id']}): {ld}")
            continue
        # ponytail: link_chinhphu là seed NGƯỜI (link_cong_luat.yaml) — kết quả chỉ
        # ghi vào ly_do + báo cáo, không sửa cột; trượt ở đây = gỡ tay khỏi seed đó.
        if ld and d["link_chinhphu"]:
            ld_cp = _du_phong_chinhphu(d)
            ld += f"; dự phòng {d['link_chinhphu']}: {ld_cp or 'đạt'}"
            du_phong.append(f"{d['so_ky_hieu']} ({d['id']}): {ld_cp or 'đạt'}")
        hang = {
            "so_ky_hieu": d["so_ky_hieu"],
            "url": MAU_VBPL.format(id=gid),
            "canonical": canonical,
            "kiem_boi": KIEM_BOI_MAY,
            "kiem_luc": datetime.fromisoformat(trang["luc"]) if trang and trang.get("luc") else datetime.now(UTC),
        }
        if ld:
            hang["ly_do"] = ld
            ly_do[re.sub(r"'.*|\d{4}-\d\d-\d\d.*| tại .*", "…", ld)] += 1
            truot.append(f"{d['so_ky_hieu']} ({d['id']}): {ld}")
            mat += d["id"] in cu and "ly_do" not in cu[d["id"]]
        seed[d["id"]] = hang
    dat = sum("ly_do" not in h for h in seed.values())
    return seed, {
        "dat": dat,
        "truot": len(seed) - dat,
        "ly_do": dict(ly_do),
        "chi_tiet": truot,
        "giu_dong_cu_vi_khong_ket_luan": giu,
        "mat_link": mat,
        "chinhphu_du_phong": du_phong,
    }


def ngat_ghi(mat: int, tong: int) -> str | None:
    """Cầu dao ghi. Một lượt thường gần như không mất gì (K2: 0 link đạt mất, 0
    tình trạng rơi về chưa rõ); mất hơn 5 % văn bản đã kiểm là nguồn đổi giao diện
    hay đang hỏng, không phải kho đổi."""
    if mat * 20 > tong:
        return (
            f"NGẮT: {mat}/{tong} văn bản sẽ mất link đạt hoặc rơi về 'chưa rõ' (>5 %) — KHÔNG ghi DB hay seed;"
            " xem báo cáo và kiểm tay nguồn trước"
        )
    return None


def _in(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str), flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--chi-deep", action="store_true", help="chỉ văn bản tầng sâu (78 dòng, ~4 phút)")
    p.add_argument("--tu-id", help="bắt đầu từ id này (theo thứ tự chữ của id), bỏ qua các id trước")
    p.add_argument("--dry-run", action="store_true", help="tải + kiểm + in thay đổi, KHÔNG ghi DB hay seed")
    p.add_argument("--cache", type=Path, help="thư mục giữ response (mặc định data/raw/lam_moi/<hôm nay>)")
    p.add_argument("--tu-seed", action="store_true", help="0 request: chỉ nạp DB từ hai seed hiệu lực đã commit")
    a = p.parse_args()
    engine = get_engine()
    ghi_de = doc_ghi_de(SEED_GHI_DE)  # seed người sai thì dừng NGAY, trước một giờ tải
    if a.tu_seed:
        _in(nap_hieu_luc(engine, doc_bang_chung(SEED_HIEU_LUC), ghi_de, ghi=not a.dry_run))
        if a.dry_run:
            print("DRY-RUN — không ghi DB.")
        return

    cache = a.cache or Path(get_settings().data_raw_dir) / "lam_moi" / date.today().isoformat()
    with engine.connect() as c:
        docs = [dict(r) for r in c.execute(_SQL_DOCS, {"chi_deep": a.chi_deep, "tu_id": a.tu_id}).mappings()]
        con = {r[0] for r in c.execute(text("SELECT id FROM documents")).all()}
    print(f"{len(docs)} văn bản · cache {cache}", flush=True)
    gw, vb = _tai_het(docs, cache)

    bang_moi, loi_gw, ma = {}, [], Counter()
    for d in docs:
        gid = ID_GATEWAY.get(d["id"], d["id"])
        data, luc, loi = gw.get(gid) or (None, None, f"chưa tải: gateway ngắt sau {NGAT_SAU} lỗi liền nhau")
        if loi:
            loi_gw.append(f"{d['so_ky_hieu']} ({d['id']}): {loi}")
            continue
        ma[(data.get("effStatus") or {}).get("code")] += 1
        bang_moi[d["id"]] = hang_bang_chung(d["id"], data, luc)
    # Id không đọc được lượt này giữ bằng chứng cũ (DB của nó cũng giữ như cũ).
    bang_gop = {k: v for k, v in doc_bang_chung(SEED_HIEU_LUC).items() if k in con} | bang_moi
    cu = yaml.safe_load(SEED_DA_KIEM.read_text(encoding="utf-8")) if SEED_DA_KIEM.exists() else {}
    cu = {str(k): v for k, v in (cu or {}).items() if str(k) in con}
    seed_link, bao_link = doi_chieu_link(docs, vb, cu)
    bao_hl = nap_hieu_luc(engine, bang_gop, ghi_de, ghi=False)
    ngat = ngat_ghi(bao_link["mat_link"] + bao_hl["mat_tinh_trang"], len(docs))
    _in(
        {
            "gateway": {"doc_duoc": len(bang_moi), "loi": loi_gw, "ma_effStatus": dict(ma)},
            "hieu_luc": bao_hl,
            "vbpl": bao_link,
            "ngat_ghi": ngat,
        }
    )
    if a.dry_run:
        print("DRY-RUN — không ghi DB, không ghi seed.")
        return
    if ngat:
        raise SystemExit(ngat)

    ghi_bang_chung(SEED_HIEU_LUC, bang_gop)
    SEED_DA_KIEM.write_text(
        "# Link vbpl.vn do MÁY kiểm — sinh bởi `python -m scripts.lam_moi_hieu_luc`, đừng sửa tay.\n"
        "# Đạt = HTTP 200 + <title> chứa số hiệu + article:published_time (+7 giờ) = ngay_ban_hanh.\n"
        "# Dòng có `ly_do` là bằng chứng TRƯỢT: không nạp link.\n"
        + yaml.safe_dump(dict(sorted((cu | seed_link).items())), allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    # DB nạp TỪ seed vừa ghi: trạng thái DB luôn dựng lại được từ repo.
    bao = nap_hieu_luc(engine, doc_bang_chung(SEED_HIEU_LUC), ghi_de, ghi=True)
    print({"hieu_luc_cap_nhat": bao["cap_nhat"], **nap_da_kiem(SEED_DA_KIEM, engine)})


if __name__ == "__main__":
    main()
