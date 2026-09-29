"""Bản PDF đã ký (vanban.chinhphu.vn) và ảnh trang 1 cho văn bản được hiện — quyết
định 2026-09-28 mục 9, cố gắng tối đa (K6). Chạy tay, không theo lịch.

    python -m scripts.nap_pdf_ban_ky --cache DIR [--as-of YYYY-MM-DD] [--them-id TỆP] [--gioi-han 800] [--ghi]

1. Tìm (≤1 request/giây tới *.chinhphu.vn, backoff trên 429/5xx; mọi kết luận vào
   `DIR`, chạy lại thì tiếp từ chỗ dừng): văn bản đã có `link_chinhphu` lấy docid từ
   đó; không thì tìm số hiệu ở trang "Hệ thống văn bản" (postback ASP.NET) và nhận
   MỘT docid có đúng số hiệu (`cung_so`) và ngày ban hành bằng ngày trong kho. Trang
   chi tiết phải qua `kiem_trang_chinhphu` (tiêu đề chứa số hiệu, ô "Ngày ban hành" =
   ngày trong kho); link là tệp `*.signed.pdf` đầu tiên trên datafiles.chinhphu.vn.
   GET tệp: HTTP 200 + `application/pdf` + mở đầu `%PDF`. Trang 1 render bằng
   `pdftoppm -png -r 60 -f 1 -l 1` (cạnh dài ≤1200 px); PNG >300 KB thì hạ độ phân giải.
2. Bằng chứng vào `data/seed/pdf_ban_ky.yaml` (commit): doc_id → số hiệu, trang, pdf,
   lúc kiểm, kích thước và sha256 của PDF.
3. DB nạp TỪ seed + ảnh trong `DIR`: `documents.link_pdf_ban_ky`, `anh_van_ban`. Dry-run
   (ROLLBACK) trừ khi `--ghi`; chạy lại không đổi gì.
"""

import argparse
import hashlib
import json
import re
import struct
import subprocess
import tempfile
import time
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import yaml
from sqlalchemy import Engine, text

from scripts.lam_moi_hieu_luc import UA, cung_so, kiem_trang_chinhphu
from src.services.db import get_engine
from src.services.hien_thi import hien_thi_luc
from src.services.trich_dan import link_ban_ky

SEED = Path("data/seed/pdf_ban_ky.yaml")
TRANG_TIM = "https://vanban.chinhphu.vn/he-thong-van-ban?classid=1&mode=1"
MAU_TRANG = "https://vanban.chinhphu.vn/?pageid=27160&docid={}"
NGHI = 1.0
TRAN_ANH = 307_200  # = ck_anh_van_ban_kich_thuoc (migration 040)
DO_PHAN_GIAI = (60, 45, 30)
CANH_TOI_DA = 1200
_THU_LAI = {429, 500, 502, 503, 504}
_O_TIM = "ctrl_191017_163$"
_RE_DONG = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_RE_DOCID = re.compile(r"docid=(\d+)")
_RE_SO = re.compile(r'<span class="code">\s*([^<]*?)\s*</span>')
_RE_NGAY = re.compile(r'<span class="issued-date">\s*(\d\d)/(\d\d)/(\d{4})')
_RE_KY = re.compile(r"https://datafiles\.chinhphu\.vn/[^\"'<>\s]+?\.signed\.pdf", re.I)
_RE_AN = {
    n: re.compile(rf'name="{re.escape(n)}" id="[^"]*" value="([^"]*)"')
    for n in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")
}


def docid_tim_duoc(html: str, so_ky_hieu: str, ngay: date | None) -> tuple[str | None, str | None]:
    """Trang kết quả tìm → (docid, None) khi đúng MỘT docid có cùng số hiệu và cùng ngày
    ban hành; không thì (None, lý do). Hai docid cùng khớp là mơ hồ: không chọn."""
    khop = set()
    for dong in _RE_DONG.findall(html):
        d, so, ng = _RE_DOCID.search(dong), _RE_SO.search(dong), _RE_NGAY.search(dong)
        if d and so and ng and cung_so(so_ky_hieu, so[1]) and date(int(ng[3]), int(ng[2]), int(ng[1])) == ngay:
            khop.add(d[1])
    if len(khop) == 1:
        return khop.pop(), None
    return None, (f"{len(khop)} docid cùng số hiệu và ngày: {sorted(khop)}" if khop else "tìm không thấy")


def link_ky(trang: str) -> str | None:
    """Link `*.signed.pdf` đầu tiên của trang chi tiết (tệp khác, vd `91_.pdf`, là bản chưa ký)."""
    m = _RE_KY.search(trang)
    return link_ban_ky(m[0]) if m else None


class _May:
    """Một client, một nhịp chung cho mọi host *.chinhphu.vn."""

    def __init__(self) -> None:
        self.c = httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=120)
        self.luc = 0.0
        self.an: dict[str, str] | None = None

    def goi(self, cach: str, url: str, **kw) -> httpx.Response:
        for lan in range(4):
            time.sleep(max(0.0, self.luc + NGHI - time.monotonic()))
            try:
                r = self.c.request(cach, url, **kw)
            except httpx.TransportError:
                r = None
            self.luc = time.monotonic()
            if r is not None and r.status_code not in _THU_LAI:
                return r
            time.sleep(2 ** (lan + 1))
        raise RuntimeError(f"{url}: lỗi tạm thời sau 4 lần")  # không cache: lần sau thử lại

    def tim(self, so_ky_hieu: str) -> str:
        if self.an is None:
            trang = self.goi("GET", TRANG_TIM).text
            self.an = {n: m[1] for n, r in _RE_AN.items() if (m := r.search(trang))}
        o = {"txtSearchKeyword": so_ky_hieu, "btnSearch": "Tìm kiếm", "drdRecordPerPage": "50", "hidSiteId": "4"}
        return self.goi("POST", TRANG_TIM, data={**self.an, **{_O_TIM + k: v for k, v in o.items()}}).text


def _ve(pdf: Path, *tham: str) -> bytes:
    with tempfile.TemporaryDirectory() as t:
        lenh = ["pdftoppm", "-png", *tham, "-f", "1", "-l", "1", str(pdf), str(Path(t) / "a")]
        subprocess.run(lenh, check=True, capture_output=True, timeout=120)
        return next(Path(t).glob("a*.png")).read_bytes()


def anh_trang_1(pdf: Path) -> tuple[bytes, int, int, int]:
    """PNG trang 1 ≤ `TRAN_ANH` byte, cạnh dài ≤ `CANH_TOI_DA` → (png, rộng, cao, dpi).
    `-scale-to` đè `-r`, nên chỉ dùng nó khi trang to hơn trần (bản đồ, khổ A3)."""
    for dpi in DO_PHAN_GIAI:
        png = _ve(pdf, "-r", str(dpi))
        if max(struct.unpack(">II", png[16:24])) > CANH_TOI_DA:
            png = _ve(pdf, "-r", str(dpi), "-scale-to", str(CANH_TOI_DA))
        if len(png) <= TRAN_ANH:
            rong, cao = struct.unpack(">II", png[16:24])
            return png, rong, cao, dpi
    raise ValueError(f"trang 1 của {pdf.name} vẫn >{TRAN_ANH} byte ở {DO_PHAN_GIAI[-1]} dpi")


def tim_mot(may: _May, vb: dict, cache: Path) -> dict:
    """Kết luận cho MỘT văn bản (đã ghi vào cache): `pdf` khi có, không thì `ly_do`."""
    luc = datetime.now(UTC).isoformat(timespec="seconds")
    ra = {"so_ky_hieu": vb["so_ky_hieu"], "kiem_luc": luc}
    m = _RE_DOCID.search(vb.get("link_chinhphu") or "")
    docid, ly_do = (m[1], None) if m else docid_tim_duoc(may.tim(vb["so_ky_hieu"]), vb["so_ky_hieu"], vb["ngay"])
    if docid is None:
        return ra | {"ly_do": f"vanban.chinhphu.vn: {ly_do}"}
    ra["trang"] = MAU_TRANG.format(docid)
    r = may.goi("GET", ra["trang"])
    if ly_do := kiem_trang_chinhphu(vb["so_ky_hieu"], vb["ngay"], r.status_code, r.text):
        return ra | {"ly_do": f"trang chi tiết: {ly_do}"}
    if (url := link_ky(r.text)) is None:
        return ra | {"ly_do": "trang chi tiết không có tệp *.signed.pdf"}
    p = may.goi("GET", url)
    loai = p.headers.get("content-type", "")
    if p.status_code != 200 or not loai.startswith("application/pdf") or not p.content.startswith(b"%PDF"):
        return ra | {"pdf_truot": url, "ly_do": f"PDF: HTTP {p.status_code}, {loai!r}"}
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(p.content)
        f.flush()
        png, rong, cao, dpi = anh_trang_1(Path(f.name))
    (cache / "anh" / f"{vb['id']}.png").write_bytes(png)
    return ra | {
        "pdf": url,
        "so_byte_pdf": len(p.content),
        "sha256_pdf": hashlib.sha256(p.content).hexdigest(),
        "anh": {"so_byte": len(png), "rong": rong, "cao": cao, "dpi": dpi},
    }


def tim_het(engine: Engine, ids: list[str], cache: Path, gioi_han: int) -> dict[str, dict]:
    (cache / "ket-qua").mkdir(parents=True, exist_ok=True)
    (cache / "anh").mkdir(exist_ok=True)
    with engine.connect() as c:
        vbs = {
            r["id"]: {**r, "ngay": r["ngay_ban_hanh"]}
            for r in c.execute(
                text("SELECT id, so_ky_hieu, ngay_ban_hanh, link_chinhphu FROM documents WHERE id = ANY(:i)"),
                {"i": ids},
            ).mappings()
        }
    may, moi, ket = _May(), 0, {}
    for i in sorted(vbs):
        f = cache / "ket-qua" / f"{i}.json"
        if not f.exists():
            if moi >= gioi_han:
                continue
            moi += 1
            f.write_text(json.dumps(tim_mot(may, vbs[i], cache), ensure_ascii=False, indent=1), encoding="utf-8")
            print(
                f"[{moi}] {vbs[i]['so_ky_hieu']} ({i}): {json.loads(f.read_text()).get('pdf') or 'không'}", flush=True
            )
        ket[i] = json.loads(f.read_text(encoding="utf-8"))
    return ket


def nap(engine: Engine, seed: dict, cache: Path, ghi: bool) -> dict:
    """DB ← seed: link + ảnh. Chỉ ghi dòng khác đi; dry-run thì ROLLBACK."""
    dem = {"link": 0, "anh": 0}
    with engine.connect() as c, c.begin() as tx:
        for doc_id, h in seed.items():
            url = link_ban_ky(h["pdf"])
            if url is None:
                raise ValueError(f"{doc_id}: {h['pdf']!r} không phải tệp PDF trên datafiles.chinhphu.vn")
            png = (cache / "anh" / f"{doc_id}.png").read_bytes()
            rong, cao = struct.unpack(">II", png[16:24])
            dem["link"] += c.execute(
                text("UPDATE documents SET link_pdf_ban_ky = :u WHERE id = :d AND link_pdf_ban_ky IS DISTINCT FROM :u"),
                {"u": url, "d": doc_id},
            ).rowcount
            dem["anh"] += c.execute(
                text(
                    "INSERT INTO anh_van_ban (doc_id, png, so_byte, rong, cao) VALUES (:d, :p, :n, :r, :c)"
                    " ON CONFLICT (doc_id) DO UPDATE SET png = EXCLUDED.png, so_byte = EXCLUDED.so_byte,"
                    " rong = EXCLUDED.rong, cao = EXCLUDED.cao, tao_luc = now()"
                    " WHERE anh_van_ban.png IS DISTINCT FROM EXCLUDED.png"
                ),
                {"d": doc_id, "p": png, "n": len(png), "r": rong, "c": cao},
            ).rowcount
        if not ghi:
            tx.rollback()
    return dem


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cache", type=Path, required=True, help="thư mục kết luận + ảnh (chạy lại thì tiếp)")
    p.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="ngày tính tập được hiện")
    p.add_argument("--them-id", type=Path, help="tệp id thêm vào tập được hiện, cách nhau bằng khoảng trắng")
    p.add_argument("--gioi-han", type=int, default=800, help="số văn bản tra MỚI tối đa trong lượt này")
    p.add_argument("--ghi", action="store_true", help="ghi DB (mặc định: dry-run, ROLLBACK)")
    a = p.parse_args()
    engine = get_engine()
    ids = set(hien_thi_luc(engine, a.as_of)) | set(a.them_id.read_text().split() if a.them_id else [])
    ket = tim_het(engine, sorted(ids), a.cache, a.gioi_han)
    seed = {i: {k: v for k, v in h.items() if k != "anh"} for i, h in sorted(ket.items()) if h.get("pdf")}
    SEED.write_text(
        "# Bản PDF đã ký trên datafiles.chinhphu.vn — sinh bởi `python -m scripts.nap_pdf_ban_ky`, đừng sửa tay.\n"
        "# Đạt = trang vanban.chinhphu.vn qua `kiem_trang_chinhphu` + tệp *.signed.pdf HTTP 200 application/pdf.\n"
        + yaml.safe_dump(seed, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    ly_do: dict[str, int] = {}
    for h in ket.values():
        if not h.get("pdf"):
            k = re.sub(r"\d{3,}|\[.*\]", "N", h["ly_do"])[:90]
            ly_do[k] = ly_do.get(k, 0) + 1
    print(
        json.dumps(
            {
                "hien": len(ids),
                "da_tra": len(ket),
                "co_pdf": len(seed),
                "ly_do": ly_do,
                "db": nap(engine, seed, a.cache, a.ghi),
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    if not a.ghi:
        print("DRY-RUN — DB đã ROLLBACK (seed đã ghi).")


if __name__ == "__main__":
    main()
