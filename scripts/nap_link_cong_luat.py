"""Nạp link trang công khai của ba cổng luật vào `documents.link_*` từ HAI seed
(spec 2026-09-06 §4; quyết định 2026-09-28 mục 2). UPDATE thuần, idempotent,
cùng khuôn `scripts/nap_linh_vuc.py`.

    python -m scripts.nap_link_cong_luat

1. `data/seed/link_cong_luat.yaml` — link đã mở và ghi `kiem_luc`/`kiem_boi`
   (`chinhphu`, `tvpl`, và `vbpl` nếu có). Script chỉ kiểm hình thức rồi nạp.
2. `data/seed/link_vbpl_da_kiem.yaml` — link vbpl.vn do MÁY kiểm
   (`kiem_boi: may-doi-chieu-tieu-de`, sinh bởi `scripts/lam_moi_hieu_luc.py`):
   HTTP 200, `<title>` chứa đúng số hiệu, `article:published_time` + 7 giờ bằng
   `ngay_ban_hanh`, kèm URL canonical. vbpl.vn phục vụ bot bình thường từ
   2026-09-28 (trước đó trả 403); mẫu cũ `…/vbpq-toanvan.aspx?ItemID=` nay
   chuyển hướng về trang chủ nên KHÔNG được nạp. Chỉ dòng seed này ghi
   `link_vbpl`; dòng có `ly_do` (trượt) ghi NULL, để link từng đạt mà nay trượt
   biến mất.

Các phép kiểm dừng chứ không bỏ qua im lặng: một link sai host dưới nhãn
"chính thức" hại uy tín hơn không có link. Seed (YAML, `yaml.safe_load` đọc
`2026-09-06` thành `datetime.date`):

    "139264":
      vbpl: null
      chinhphu: https://vanban.chinhphu.vn/?pageid=27160&docid=198540
      tvpl: null
      kiem_luc: 2026-09-06
      kiem_boi: chu-du-an
"""

import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from sqlalchemy import Engine, text

from src.services.db import get_engine, run_migrations

SEED_PATH = Path("data/seed/link_cong_luat.yaml")
SEED_DA_KIEM = Path("data/seed/link_vbpl_da_kiem.yaml")

# Đúng ba host, không subdomain lạ, không http. Cột nào host nấy.
HOST_CHO_PHEP: dict[str, str] = {
    "vbpl": "vbpl.vn",
    "chinhphu": "vanban.chinhphu.vn",
    "tvpl": "thuvienphapluat.vn",
}
_KHOA_HOP_LE = {*HOST_CHO_PHEP, "kiem_luc", "kiem_boi"}

# `link_vbpl` chỉ ghi khi seed có link: seed người để `vbpl: null` ở mọi dòng, và
# ghi đè NULL sẽ xoá link máy đã kiểm (seed 2) mỗi lần chạy lại.
_SQL = text(
    "UPDATE documents SET link_vbpl = COALESCE(:vbpl, link_vbpl), link_chinhphu = :chinhphu,"
    " link_tvpl = :tvpl WHERE id = :doc_id"
)

# ── Seed máy kiểm ────────────────────────────────────────────────────────────
MAU_VBPL = "https://vbpl.vn/van-ban/chi-tiet/{id}"
KIEM_BOI_MAY = "may-doi-chieu-tieu-de"
# Văn bản trong kho mà `documents.id` KHÔNG phải id gateway/vbpl.vn. Luật Khiếu nại
# nạp từ vanban.chinhphu.vn (`scripts/fetch_chinhphu.py`); bản gateway cùng số
# hiệu là 27325 (`scripts/fetch_moj.KHONG_NAP`, bị loại vì lỗi nguồn ở Điều 31).
ID_GATEWAY: dict[str, str] = {"cp-162374": "27325"}
_KHOA_DA_KIEM = {"so_ky_hieu", "url", "canonical", "kiem_boi", "kiem_luc", "ly_do"}
_SQL_DA_KIEM = text("UPDATE documents SET link_vbpl = :vbpl WHERE id = :doc_id")


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


def kiem_hang_da_kiem(doc_id: str, hang: dict, so_ky_hieu_db: str, bay_gio: datetime) -> str | None:
    """Một dòng seed máy kiểm → `link_vbpl` sẽ ghi (URL, hoặc None khi dòng trượt).

    Chặt hơn `kiem_hang`, vì không có người nào nhìn trang: URL phải ĐÚNG mẫu
    `/van-ban/chi-tiet/{id gateway của chính dòng này}`, canonical phải là trang
    chi tiết kết thúc bằng `--{id}` đó, và số hiệu trong seed phải bằng số hiệu
    trong DB — một dòng lệch id là một link "chính thức" dẫn sang văn bản khác.
    """
    la = set(hang) - _KHOA_DA_KIEM
    if la:
        raise ValueError(f"{doc_id}: khoá lạ {sorted(la)}")
    if hang.get("kiem_boi") != KIEM_BOI_MAY:
        raise ValueError(f"{doc_id}: kiem_boi phải là {KIEM_BOI_MAY!r}, được {hang.get('kiem_boi')!r}")
    kiem_luc = hang.get("kiem_luc")
    if not isinstance(kiem_luc, datetime) or kiem_luc.tzinfo is None:
        raise ValueError(f"{doc_id}: kiem_luc phải là thời điểm có múi giờ")
    if kiem_luc > bay_gio:
        raise ValueError(f"{doc_id}: kiem_luc {kiem_luc} ở tương lai")
    if hang.get("so_ky_hieu") != so_ky_hieu_db:
        raise ValueError(f"{doc_id}: so_ky_hieu seed {hang.get('so_ky_hieu')!r} ≠ DB {so_ky_hieu_db!r}")
    gid = ID_GATEWAY.get(doc_id, doc_id)
    url = kiem_url("vbpl", hang.get("url"))
    if url != MAU_VBPL.format(id=gid):
        raise ValueError(f"{doc_id}: url {url!r} không phải {MAU_VBPL.format(id=gid)!r}")
    if hang.get("ly_do"):
        return None
    canonical = kiem_url("vbpl", hang.get("canonical"))
    if not re.fullmatch(rf"https://vbpl\.vn/van-ban/chi-tiet/[a-z0-9-]+--{re.escape(gid)}", canonical or ""):
        raise ValueError(f"{doc_id}: canonical {canonical!r} không phải trang chi tiết của {gid}")
    return url


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


def nap_da_kiem(seed: Path, engine: Engine) -> dict[str, int]:
    """Seed máy kiểm → `link_vbpl`. Kiểm HẾT rồi mới ghi, một transaction."""
    if not seed.exists():
        raise FileNotFoundError(f"chưa có {seed}")
    tho = yaml.safe_load(seed.read_text(encoding="utf-8")) or {}
    if not isinstance(tho, dict):
        raise ValueError(f"{seed}: phải là map doc_id → hàng")
    run_migrations("019")
    bay_gio = datetime.now().astimezone()
    with engine.begin() as conn:
        so_db = dict(
            conn.execute(
                text("SELECT id, so_ky_hieu FROM documents WHERE id = ANY(:ids)"), {"ids": [str(k) for k in tho]}
            ).all()
        )
        thieu = sorted(str(k) for k in tho if str(k) not in so_db)
        if thieu:
            raise ValueError(f"doc_id không có trong documents: {thieu}")
        link = {str(k): kiem_hang_da_kiem(str(k), hang or {}, so_db[str(k)], bay_gio) for k, hang in tho.items()}
        cap_nhat = sum(conn.execute(_SQL_DA_KIEM, {"doc_id": k, "vbpl": v}).rowcount for k, v in link.items())
    dat = sum(v is not None for v in link.values())
    return {"cap_nhat": cap_nhat, "dat": dat, "truot": len(link) - dat}


if __name__ == "__main__":
    print(nap(SEED_PATH, get_engine()))
    if SEED_DA_KIEM.exists():
        print(nap_da_kiem(SEED_DA_KIEM, get_engine()))
