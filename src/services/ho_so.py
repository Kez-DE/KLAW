"""Tổng hợp hồ sơ tài khoản (spec 2A §6.2) — chỉ đọc, chỉ của `sub`."""

from sqlalchemy import text

from src.services.bao_ve import mui_gio
from src.services.db import get_engine

NHAN_PHAN_LOAI = {
    "answer": "Trả lời có căn cứ",
    "partial_coverage": "Trả lời một phần",
    "abstain": "Dừng vì thiếu căn cứ",
    "out_of_scope": "Ngoài phạm vi",
    "soan_thao": "Bản thảo",
}
_SQL_USER = text("SELECT email, plan, plan_het_han, created_at FROM users WHERE sub = :sub")
_SQL_SO_PHIEN = text("SELECT count(*)::int FROM hoi_thoai WHERE user_sub = :sub AND xoa_luc IS NULL")
_SQL_TONG = text(
    "SELECT endpoint, count(*)::int AS n FROM traces WHERE user_sub = :sub AND NOT cache_hit"
    " AND (result_type IS NULL OR result_type NOT IN ('loi', 'out_of_scope')) GROUP BY endpoint"
)
# Hoạt động là hoạt động: KHÔNG loại out_of_scope, chỉ loại lỗi và bộ đệm.
_SQL_HOAT_DONG = text(
    "SELECT (ts AT TIME ZONE :tz)::date AS ngay, count(*)::int AS so_luot FROM traces"
    " WHERE user_sub = :sub AND NOT cache_hit AND result_type IS DISTINCT FROM 'loi'"
    " AND ts >= now() - interval '365 days' GROUP BY 1 ORDER BY 1"
)
_SQL_PHAN_LOAI = text(
    "SELECT CASE WHEN endpoint = '/api/v1/soan-thao' THEN 'soan_thao' ELSE result_type END AS khoa,"
    " count(*)::int AS so FROM traces WHERE user_sub = :sub AND NOT cache_hit"
    " AND result_type IS DISTINCT FROM 'loi' GROUP BY 1 ORDER BY 2 DESC"
)


def tong_hop(sub: str) -> dict | None:
    with get_engine().connect() as c:
        u = c.execute(_SQL_USER, {"sub": sub}).mappings().one_or_none()
        if u is None:
            return None
        so_phien = int(c.execute(_SQL_SO_PHIEN, {"sub": sub}).scalar_one())
        tong = {r["endpoint"]: r["n"] for r in c.execute(_SQL_TONG, {"sub": sub}).mappings()}
        hoat_dong = [dict(r) for r in c.execute(_SQL_HOAT_DONG, {"sub": sub, "tz": str(mui_gio())}).mappings()]
        phan_loai = [
            {"khoa": r["khoa"], "nhan": NHAN_PHAN_LOAI.get(r["khoa"], "Khác"), "so": r["so"]}
            for r in c.execute(_SQL_PHAN_LOAI, {"sub": sub}).mappings()
            if r["khoa"] is not None
        ]
    return {
        "email": u["email"],
        "plan_tho": u["plan"],
        "plan_het_han": u["plan_het_han"],
        "tao_luc": u["created_at"],
        "so_phien": so_phien,
        "tong_hoi_dap": tong.get("/api/v1/tra-cuu", 0),
        "tong_ban_thao": tong.get("/api/v1/soan-thao", 0),
        "hoat_dong": hoat_dong,
        "phan_loai": phan_loai,
    }
