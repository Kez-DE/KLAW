"""Phiên hội thoại theo tài khoản (spec 2026-09-07 §4, §5.1).

Mọi hàm đọc/ghi nhận `sub` và lọc theo `user_sub` — không có đường nào đọc phiên
mà không có chủ. "Ẩn" là quy tắc HIỆN theo gói (`han_muc.yaml: phien_luu`), tính
lúc đọc chứ không ghi vào DB: nâng gói thì phiên cũ hiện lại mà không cần sửa dòng nào.
"""

import json
import logging

from sqlalchemy import text

from src.services.bao_ve import phien_luu_toi_da
from src.services.db import get_engine

logger = logging.getLogger(__name__)

TIEU_DE_TOI_DA = 80
LUOT_LICH_SU = 3
TRA_LOI_TOI_DA = 2000
DUONG_DAN_TOI_DA = 50

LOI_KHONG_THAY = "Không tìm thấy phiên này."
LOI_PHIEN_AN = "Gói hiện tại chỉ giữ các phiên gần nhất; phiên này đang ẩn. Nâng gói để mở lại."

_SQL_TAO = text("INSERT INTO hoi_thoai (user_sub, tieu_de) VALUES (:sub, :tieu_de) RETURNING id")
_SQL_LAY = text(
    "SELECT id::text AS id, tieu_de, tao_luc, cap_nhat_luc FROM hoi_thoai"
    " WHERE id = :id AND user_sub = :sub AND xoa_luc IS NULL"
)
# Số phiên còn sống MỚI HƠN phiên này (theo cặp (cap_nhat_luc, id) để tất định).
_SQL_HANG = text(
    "SELECT count(*)::int FROM hoi_thoai h"
    " WHERE h.user_sub = :sub AND h.xoa_luc IS NULL"
    "   AND (h.cap_nhat_luc, h.id) > (SELECT cap_nhat_luc, id FROM hoi_thoai WHERE id = :id)"
)
_SQL_LICH_SU = text(
    "SELECT cau_hoi, tra_loi FROM luot_hoi_thoai WHERE hoi_thoai_id = :id ORDER BY thu_tu DESC LIMIT :n"
)
_SQL_GHI = text(
    "INSERT INTO luot_hoi_thoai (hoi_thoai_id, thu_tu, cau_hoi, tra_loi, trace_id)"
    " VALUES (:id, (SELECT coalesce(max(thu_tu), 0) + 1 FROM luot_hoi_thoai WHERE hoi_thoai_id = :id),"
    "         :cau_hoi, CAST(:tra_loi AS jsonb), :trace_id) RETURNING thu_tu"
)
_SQL_CHAM = text("UPDATE hoi_thoai SET cap_nhat_luc = now() WHERE id = :id")
_SQL_DEM = text("SELECT count(*)::int FROM hoi_thoai WHERE user_sub = :sub AND xoa_luc IS NULL")
_SQL_DANH_SACH = text(
    "SELECT h.id::text AS id, h.tieu_de, h.tao_luc, h.cap_nhat_luc,"
    "       (SELECT count(*)::int FROM luot_hoi_thoai l WHERE l.hoi_thoai_id = h.id) AS so_luot"
    " FROM hoi_thoai h WHERE h.user_sub = :sub AND h.xoa_luc IS NULL"
    " ORDER BY h.cap_nhat_luc DESC, h.id DESC LIMIT :limit OFFSET :offset"
)
_SQL_LUOT = text(
    "SELECT thu_tu, cau_hoi, tra_loi, trace_id, tao_luc FROM luot_hoi_thoai WHERE hoi_thoai_id = :id ORDER BY thu_tu"
)
_SQL_DOI_TEN = text("UPDATE hoi_thoai SET tieu_de = :tieu_de WHERE id = :id AND user_sub = :sub AND xoa_luc IS NULL")
_SQL_XOA_MEM = text("UPDATE hoi_thoai SET xoa_luc = now() WHERE id = :id AND user_sub = :sub AND xoa_luc IS NULL")


def tieu_de_mac_dinh(cau_hoi: str) -> str:
    """Câu hỏi đầu, cắt còn ≤80 ký tự tại ranh giới từ, thêm "…" nếu cắt."""
    gon = " ".join(cau_hoi.split())
    if len(gon) <= TIEU_DE_TOI_DA:
        return gon
    cat = gon[:TIEU_DE_TOI_DA].rsplit(" ", 1)[0].rstrip()
    return f"{cat}…"


def tao_phien(sub: str, cau_hoi: str) -> str:
    with get_engine().begin() as c:
        return str(c.execute(_SQL_TAO, {"sub": sub, "tieu_de": tieu_de_mac_dinh(cau_hoi)}).scalar_one())


def lay_phien(sub: str, id: str) -> dict | None:
    with get_engine().connect() as c:
        r = c.execute(_SQL_LAY, {"sub": sub, "id": id}).mappings().one_or_none()
    return dict(r) if r is not None else None


def phien_bi_an(sub: str, plan: str, id: str) -> bool:
    """Phiên nằm ngoài N phiên mới nhất của gói. Gọi SAU `lay_phien` (phiên phải của `sub`)."""
    with get_engine().connect() as c:
        moi_hon = c.execute(_SQL_HANG, {"sub": sub, "id": id}).scalar_one()
    return int(moi_hon) >= phien_luu_toi_da(plan)


def _luot_thanh_lich_su(cau_hoi: str, tra_loi: dict) -> dict:
    # Cùng khuôn với `dungLichSu` phía FE: answer cắt 2000, đường dẫn duy nhất, ≤50.
    duong_dan: list[str] = []
    for c in tra_loi.get("citations") or []:
        d = c.get("duong_dan") if isinstance(c, dict) else None
        if isinstance(d, str) and d and d not in duong_dan:
            duong_dan.append(d[:500])
    return {
        "cau_hoi": cau_hoi,
        "tra_loi": str(tra_loi.get("answer") or "")[:TRA_LOI_TOI_DA],
        "duong_dan": duong_dan[:DUONG_DAN_TOI_DA],
    }


def lich_su_gan_nhat(id: str, n: int = LUOT_LICH_SU) -> list[dict]:
    with get_engine().connect() as c:
        rows = c.execute(_SQL_LICH_SU, {"id": id, "n": n}).mappings().all()
    return [_luot_thanh_lich_su(r["cau_hoi"], r["tra_loi"] or {}) for r in reversed(rows)]


def ghi_luot(id: str, cau_hoi: str, tra_loi: dict, trace_id: str | None) -> int:
    """Một transaction: thêm lượt (thu_tu = max+1) và chạm `cap_nhat_luc`. Có thể raise —
    caller (`_ghi_luot_nhe`) quyết định phát `loi_luu`."""
    with get_engine().begin() as c:
        thu_tu = c.execute(
            _SQL_GHI,
            {
                "id": id,
                "cau_hoi": cau_hoi,
                "tra_loi": json.dumps(tra_loi, ensure_ascii=False),
                "trace_id": trace_id,
            },
        ).scalar_one()
        c.execute(_SQL_CHAM, {"id": id})
    return int(thu_tu)


def danh_sach(sub: str, plan: str, limit: int, offset: int) -> tuple[list[dict], int, int]:
    toi_da = phien_luu_toi_da(plan)
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_DEM, {"sub": sub}).scalar_one())
        tong_hien = min(tong, toi_da)
        con = max(0, min(limit, tong_hien - offset))
        items = (
            [dict(r) for r in c.execute(_SQL_DANH_SACH, {"sub": sub, "limit": con, "offset": offset}).mappings().all()]
            if con > 0
            else []
        )
    return items, tong_hien, tong - tong_hien


def chi_tiet(sub: str, id: str) -> dict | None:
    phien = lay_phien(sub, id)
    if phien is None:
        return None
    with get_engine().connect() as c:
        luot = [dict(r) for r in c.execute(_SQL_LUOT, {"id": id}).mappings().all()]
    return {**phien, "luot": luot}


def doi_ten(sub: str, id: str, tieu_de: str) -> dict | None:
    with get_engine().begin() as c:
        n = c.execute(_SQL_DOI_TEN, {"sub": sub, "id": id, "tieu_de": tieu_de.strip()}).rowcount
    return lay_phien(sub, id) if n else None


def xoa_mem(sub: str, id: str) -> bool:
    with get_engine().begin() as c:
        return c.execute(_SQL_XOA_MEM, {"sub": sub, "id": id}).rowcount > 0
