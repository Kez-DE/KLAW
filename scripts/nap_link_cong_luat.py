"""Nạp link trang công khai của ba cổng luật vào `documents.link_*` từ
`data/seed/link_cong_luat.yaml` (spec 2026-09-06 §4). UPDATE thuần, idempotent,
cùng khuôn `scripts/nap_linh_vuc.py`.

    python -m scripts.nap_link_cong_luat

KHÔNG có GET kiểm sống: `vbpl.vn` và `phapluat.gov.vn` trả 403 cho bot (đo trong
plan 8 lĩnh vực). Link trong seed là link NGƯỜI đã mở bằng trình duyệt thật và
ghi `kiem_luc`/`kiem_boi`; script chỉ kiểm hình thức rồi nạp. Ba phép kiểm dừng
chứ không bỏ qua im lặng: một link sai host dưới nhãn "chính thức" hại uy tín
hơn không có link.

Seed (YAML, `yaml.safe_load` đọc `2026-09-06` thành `datetime.date`):

    "139264":
      vbpl: https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=139264
      chinhphu: null
      tvpl: null
      kiem_luc: 2026-09-06
      kiem_boi: chu-du-an
"""

from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from sqlalchemy import Engine, text

from src.services.db import get_engine, run_migrations

SEED_PATH = Path("data/seed/link_cong_luat.yaml")

# Đúng ba host, không subdomain lạ, không http. Cột nào host nấy.
HOST_CHO_PHEP: dict[str, str] = {
    "vbpl": "vbpl.vn",
    "chinhphu": "vanban.chinhphu.vn",
    "tvpl": "thuvienphapluat.vn",
}
_KHOA_HOP_LE = {*HOST_CHO_PHEP, "kiem_luc", "kiem_boi"}

_SQL = text("UPDATE documents SET link_vbpl = :vbpl, link_chinhphu = :chinhphu, link_tvpl = :tvpl WHERE id = :doc_id")


def kiem_url(cot: str, url: object) -> str | None:
    """`None` đi qua (chưa có link). Chuỗi phải là `https://` và hostname đúng
    bằng host của cột — `urlsplit().hostname` nên `https://evil/vbpl.vn` không lọt."""
    if url is None:
        return None
    if not isinstance(url, str):
        raise ValueError(f"{cot}: phải là chuỗi hoặc null, được {type(url).__name__}")
    u = urlsplit(url)
    if u.scheme != "https":
        raise ValueError(f"{cot}: chỉ nhận https, được {url!r}")
    if u.hostname != HOST_CHO_PHEP[cot]:
        raise ValueError(f"{cot}: host {u.hostname!r} không phải {HOST_CHO_PHEP[cot]!r}")
    return url


def kiem_hang(doc_id: str, hang: dict, hom_nay: date) -> dict[str, str | None]:
    la = set(hang) - _KHOA_HOP_LE
    if la:
        raise ValueError(f"{doc_id}: khoá lạ {sorted(la)}")
    kiem_luc = hang.get("kiem_luc")
    if not isinstance(kiem_luc, date):
        raise ValueError(f"{doc_id}: kiem_luc phải là ngày YYYY-MM-DD (không trong nháy)")
    if kiem_luc > hom_nay:
        raise ValueError(f"{doc_id}: kiem_luc {kiem_luc} ở tương lai")
    if not hang.get("kiem_boi"):
        raise ValueError(f"{doc_id}: thiếu kiem_boi")
    return {cot: kiem_url(cot, hang.get(cot)) for cot in HOST_CHO_PHEP}


def nap(seed: Path, engine: Engine) -> dict[str, object]:
    """Kiểm HẾT rồi mới ghi, trong MỘT transaction — seed sai một dòng thì DB
    không đổi dòng nào."""
    if not seed.exists():
        raise FileNotFoundError(f"chưa có {seed}")
    tho = yaml.safe_load(seed.read_text(encoding="utf-8")) or {}
    if not isinstance(tho, dict):
        raise ValueError(f"{seed}: phải là map doc_id → hàng")
    hom_nay = date.today()
    hang_sach = {str(doc_id): kiem_hang(str(doc_id), hang or {}, hom_nay) for doc_id, hang in tho.items()}

    run_migrations("019")
    with engine.begin() as conn:
        co = {
            r[0]
            for r in conn.execute(text("SELECT id FROM documents WHERE id = ANY(:ids)"), {"ids": list(hang_sach)}).all()
        }
        thieu = sorted(set(hang_sach) - co)
        if thieu:
            raise ValueError(f"doc_id không có trong documents: {thieu}")
        cap_nhat = 0
        for doc_id, cot in hang_sach.items():
            cap_nhat += conn.execute(_SQL, {"doc_id": doc_id, **cot}).rowcount
    co_link = sum(1 for cot in hang_sach.values() if any(cot.values()))
    return {"cap_nhat": cap_nhat, "co_it_nhat_mot_link": co_link, "tong_dong_seed": len(hang_sach)}


if __name__ == "__main__":
    print(nap(SEED_PATH, get_engine()))
