"""Làm mới tình trạng hiệu lực từ gateway Bộ Tư pháp và kiểm link vbpl.vn bằng
máy, cho mọi văn bản trong kho — chạy tay, không theo lịch (quyết định
2026-09-28 mục 2, 6, 8).

    python -m scripts.lam_moi_hieu_luc [--chi-deep] [--tu-id ID] [--dry-run] [--cache DIR]

1. Hiệu lực: GET `{moj_api_base}/doc/{id}` (≤1 request / `moj_rate_limit_sleep`
   giây, backoff luỹ thừa trên 400/429/5xx — `MojClient`). Ghi `tinh_trang` =
   `effStatus.code`, `ngay_hieu_luc` = `effFrom`, `ngay_het_hieu_luc` = `effTo`,
   `co_quan_ban_hanh` = `agencyName` khi đang NULL, `hieu_luc_kiem_luc` = lúc
   đọc. KHÔNG đụng `provisions` hay chữ. Phán quyết hiệu lực vẫn là việc của
   `src/services/effectivity.py` lúc chạy; cột ở đây chỉ là dữ kiện của nó.
2. Link: GET `https://vbpl.vn/van-ban/chi-tiet/{id}` (≤1 request/giây, User-Agent
   nêu rõ), kiểm HTTP 200 + `<title>` chứa số hiệu + `article:published_time`
   + 7 giờ = `ngay_ban_hanh`; ghi bằng chứng vào `data/seed/link_vbpl_da_kiem.yaml`
   rồi nạp qua `scripts.nap_link_cong_luat.nap_da_kiem` (dòng trượt → NULL).
   Trượt mà văn bản đã có `link_chinhphu` (docid đã biết) thì kiểm dự phòng trang
   vanban.chinhphu.vn đó (tiêu đề + ô "Ngày ban hành"); kết quả vào `ly_do`.

Chạy lại được và tiếp tục được: mọi response gateway (ĐỦ `documentContent`, cùng
dạng `data/raw/moj/*.json` để đợt sau dựng provisions không cần tải lại) và đầu
trang vbpl.vn được giữ trong `--cache` (mặc định `data/raw/lam_moi/<hôm nay>/`);
id đã có trong cache không tải lại — trừ trang vbpl.vn TRƯỢT: nó bị bỏ khỏi cache
để lần chạy sau kiểm lại (đo 2026-09-28: vbpl.vn từng trả trang chung "Văn bản pháp
luật" với HTTP 200 cho 86/2010/NĐ-CP, vài giờ sau trả đúng trang). Lần làm mới sau
dùng thư mục của ngày đó.
"""

import argparse
import html
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import yaml
from sqlalchemy import text

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

_RE_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_RE_CANON = re.compile(r'<link[^>]*rel="canonical"[^>]*href="([^"]+)"', re.I)
_RE_XUAT_BAN = re.compile(r'<meta[^>]*property="article:published_time"[^>]*content="([^"]+)"', re.I)
_RE_NGAY_CP = re.compile(r"Ngày ban hành\s*</td>\s*<td>\s*(\d\d)-(\d\d)-(\d{4})")

_SQL_DOCS = text(
    "SELECT id, so_ky_hieu, depth, ngay_ban_hanh, tinh_trang, ngay_hieu_luc, ngay_het_hieu_luc,"
    " co_quan_ban_hanh, link_chinhphu FROM documents"
    " WHERE (NOT :chi_deep OR depth = 'deep') AND (CAST(:tu_id AS text) IS NULL OR id >= :tu_id) ORDER BY id"
)
# Ngày gateway để trống thì GIỮ ngày đang có (parquet/lần nạp đầu) thay vì xoá:
# NULL ở đây không phải "không có hạn" mà là "bản ghi gateway thiếu dữ kiện", và
# `effectivity` Mức 1 cần đúng ngày đó.
_SQL_HIEU_LUC = text(
    "UPDATE documents SET tinh_trang = :tinh_trang,"
    " ngay_hieu_luc = COALESCE(:ngay_hieu_luc, ngay_hieu_luc),"
    " ngay_het_hieu_luc = COALESCE(:ngay_het_hieu_luc, ngay_het_hieu_luc),"
    " co_quan_ban_hanh = COALESCE(co_quan_ban_hanh, :co_quan), hieu_luc_kiem_luc = :luc"
    " WHERE id = :id"
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


def _co_so(so_ky_hieu: str, tieu_de: str) -> bool:
    """Tiêu đề chứa số hiệu theo ranh giới: 45/2019 không khớp trong 145/2019."""
    so = re.escape(_so(so_ky_hieu))
    return re.search(rf"(?<![\w/]){so}(?![\w/])", khoa_so_ky_hieu(tieu_de).casefold()) is not None


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
    m = _RE_CANON.search(dau)
    canonical = html.unescape(m.group(1)) if m else None
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
    if r.status_code not in _THU_LAI_VBPL:  # lỗi tạm không vào cache: lần sau tải lại
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


def _tai_het(docs: list[dict], cache: Path) -> tuple[dict, dict]:
    """Hai vòng tải song song — hai host, mỗi host một nhịp riêng."""
    s = get_settings()
    (cache / "moj").mkdir(parents=True, exist_ok=True)
    (cache / "vbpl").mkdir(parents=True, exist_ok=True)
    gids = [ID_GATEWAY.get(d["id"], d["id"]) for d in docs]

    def vong_gateway() -> dict:
        client = MojClient(base=s.moj_api_base, sleep=s.moj_rate_limit_sleep)
        ra = {}
        for i, gid in enumerate(gids, 1):
            ra[gid] = _lay_gateway(client, gid, cache / "moj")
            if i % 100 == 0:
                print(f"[gateway] {i}/{len(gids)}", flush=True)
        return ra

    def vong_vbpl() -> dict:
        with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": UA}) as http:
            ra = {}
            for i, gid in enumerate(gids, 1):
                ra[gid] = _lay_vbpl(http, gid, cache / "vbpl")
                if i % 100 == 0:
                    print(f"[vbpl] {i}/{len(gids)}", flush=True)
            return ra

    with ThreadPoolExecutor(max_workers=2) as ex:
        g, v = ex.submit(vong_gateway), ex.submit(vong_vbpl)
        return g.result(), v.result()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--chi-deep", action="store_true", help="chỉ văn bản tầng sâu (78 dòng, ~4 phút)")
    p.add_argument("--tu-id", help="bắt đầu từ id này (theo thứ tự chữ của id), bỏ qua các id trước")
    p.add_argument("--dry-run", action="store_true", help="tải + kiểm + in thay đổi, KHÔNG ghi DB hay seed")
    p.add_argument("--cache", type=Path, help="thư mục giữ response (mặc định data/raw/lam_moi/<hôm nay>)")
    a = p.parse_args()
    cache = a.cache or Path(get_settings().data_raw_dir) / "lam_moi" / date.today().isoformat()

    engine = get_engine()
    with engine.connect() as c:
        docs = [dict(r) for r in c.execute(_SQL_DOCS, {"chi_deep": a.chi_deep, "tu_id": a.tu_id}).mappings()]
    print(f"{len(docs)} văn bản · cache {cache}", flush=True)
    gw, vb = _tai_het(docs, cache)

    cap_nhat, loi_gw, lech_so, ma = [], [], [], Counter()
    doi_sau, doi_nong, ngay_doi = [], Counter(), Counter()
    seed_moi, ly_do, truot, du_phong = {}, Counter(), [], []
    for d in docs:
        gid = ID_GATEWAY.get(d["id"], d["id"])
        data, luc, loi = gw[gid]
        if loi:
            loi_gw.append(f"{d['so_ky_hieu']} ({d['id']}): {loi}")
        elif not cung_so(d["so_ky_hieu"], data.get("docNum")):
            lech_so.append(f"{d['so_ky_hieu']} ({d['id']}): gateway docNum {data.get('docNum')!r}")
        else:
            cot = cot_tu_gateway(data)
            ma[(data.get("effStatus") or {}).get("code")] += 1
            cap_nhat.append(
                {
                    "id": d["id"],
                    "luc": luc,
                    **{k: cot[k] for k in ("tinh_trang", "ngay_hieu_luc", "ngay_het_hieu_luc", "co_quan")},
                }
            )
            if cot["tinh_trang"] != d["tinh_trang"]:
                if d["depth"] == "deep":
                    doi_sau.append(f"{d['so_ky_hieu']}: {d['tinh_trang']} → {cot['tinh_trang']}")
                else:
                    doi_nong[f"{d['tinh_trang']} → {cot['tinh_trang']}"] += 1
            for k in ("ngay_hieu_luc", "ngay_het_hieu_luc"):
                if cot[k] is None and d[k] is not None:
                    ngay_doi[f"{k}: gateway trống, giữ ngày trong kho"] += 1
                elif cot[k] is not None and cot[k] != d[k]:
                    ngay_doi[f"{k}: {'điền mới' if d[k] is None else 'đổi'}"] += 1
                    if d["depth"] == "deep":
                        doi_sau.append(f"{d['so_ky_hieu']}: {k} {d[k]} → {cot[k]}")

        trang = vb[gid]
        canonical, ld = kiem_trang_vbpl(
            d["so_ky_hieu"], d["ngay_ban_hanh"], gid, trang["status"], trang["url"], trang["dau"]
        )
        if trang.get("loi"):
            ld = f"không mở được: {trang['loi']}"
        if ld:  # vbpl.vn có lúc trả trang chung (200) cho trang có thật: trượt thì tải lại lần sau
            (cache / "vbpl" / f"{gid}.json").unlink(missing_ok=True)
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
            "kiem_luc": datetime.fromisoformat(trang["luc"]) if trang.get("luc") else datetime.now(UTC),
        }
        if ld:
            hang["ly_do"] = ld
            ly_do[re.sub(r"'.*|\d{4}-\d\d-\d\d.*| tại .*", "…", ld)] += 1
            truot.append(f"{d['so_ky_hieu']} ({d['id']}): {ld}")
        seed_moi[d["id"]] = hang

    dat = sum("ly_do" not in h for h in seed_moi.values())
    print(
        json.dumps(
            {
                "gateway": {
                    "doc_duoc": len(cap_nhat),
                    "loi": loi_gw,
                    "lech_so_ky_hieu": lech_so,
                    "ma_effStatus": dict(ma),
                },
                "tinh_trang_doi_tang_sau": doi_sau,
                "tinh_trang_doi_tang_nong_metadata": dict(doi_nong),
                "ngay": dict(ngay_doi),
                "vbpl": {"dat": dat, "truot": len(seed_moi) - dat, "ly_do": dict(ly_do), "chi_tiet": truot},
                "chinhphu_du_phong": du_phong,
            },
            ensure_ascii=False,
            indent=1,
            default=str,
        ),
        flush=True,
    )
    if a.dry_run:
        print("DRY-RUN — không ghi DB, không ghi seed.")
        return

    run_migrations("038")
    with engine.begin() as c:
        for u in cap_nhat:
            c.execute(_SQL_HIEU_LUC, u)
        con = {r[0] for r in c.execute(text("SELECT id FROM documents")).all()}
    cu = yaml.safe_load(SEED_DA_KIEM.read_text(encoding="utf-8")) if SEED_DA_KIEM.exists() else {}
    gop = {str(k): v for k, v in (cu or {}).items() if str(k) in con} | seed_moi
    SEED_DA_KIEM.write_text(
        "# Link vbpl.vn do MÁY kiểm — sinh bởi `python -m scripts.lam_moi_hieu_luc`, đừng sửa tay.\n"
        "# Đạt = HTTP 200 + <title> chứa số hiệu + article:published_time (+7 giờ) = ngay_ban_hanh.\n"
        "# Dòng có `ly_do` là bằng chứng TRƯỢT: không nạp link.\n"
        + yaml.safe_dump(dict(sorted(gop.items())), allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    print({"hieu_luc_cap_nhat": len(cap_nhat), **nap_da_kiem(SEED_DA_KIEM, engine)})


if __name__ == "__main__":
    main()
