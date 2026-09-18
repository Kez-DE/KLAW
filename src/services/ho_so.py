"""Tổng hợp hồ sơ tài khoản (spec 2A §6.2) — chỉ đọc, chỉ của `sub`."""

from collections.abc import Iterable

from sqlalchemy import text

from src.services.bao_ve import mui_gio
from src.services.bo_nho import ENDPOINT_TRACE as _BO_NHO_ENDPOINT
from src.services.db import get_engine

# Mọi giá trị `ResultType` của `agents/nodes/assemble.py` (bảy loại) cộng
# `soan_thao` — khoá tổng hợp riêng cho endpoint `/soan-thao`, không phải một
# `result_type`. Thiếu một loại ở đây KHÔNG mất dòng, nhưng nó thành một dòng
# "Khác" riêng: SQL gộp theo `result_type` THÔ, còn nhãn chỉ gán ở Python, nên
# `gioi_thieu` + `huong_dan_soan_thao` + `hoi_ve_kho` từng ra BA dòng cùng đọc
# "Khác" trên trang hồ sơ.
NHAN_PHAN_LOAI = {
    "answer": "Trả lời có căn cứ",
    "partial_coverage": "Trả lời một phần",
    "abstain": "Dừng vì thiếu căn cứ",
    "out_of_scope": "Ngoài phạm vi",
    "gioi_thieu": "Giới thiệu trợ lý",
    "huong_dan_soan_thao": "Hướng dẫn soạn thảo",
    # R5 — nhãn người dùng đọc không gọi corpus là "kho"; khoá `hoi_ve_kho` là
    # định danh nội bộ (`result_type` trong `traces`) nên giữ nguyên.
    "hoi_ve_kho": "Câu hỏi về phạm vi dữ liệu",
    "soan_thao": "Bản thảo",
}
KHOA_KHAC = "khac"
NHAN_KHAC = "Khác"
_SQL_USER = text("SELECT email, plan, plan_het_han, created_at FROM users WHERE sub = :sub")
_SQL_SO_PHIEN = text("SELECT count(*)::int FROM hoi_thoai WHERE user_sub = :sub AND xoa_luc IS NULL")
_SQL_TONG = text(
    "SELECT endpoint, count(*)::int AS n FROM traces WHERE user_sub = :sub AND NOT cache_hit"
    " AND (result_type IS NULL OR result_type NOT IN ('loi', 'out_of_scope')) GROUP BY endpoint"
)
# Hoạt động là hoạt động: KHÔNG loại out_of_scope, chỉ loại lỗi, bộ đệm, và các
# dòng `bo_nho` (tóm tắt chạy nền — không phải một lượt hỏi thật của người dùng).
_SQL_HOAT_DONG = text(
    "SELECT (ts AT TIME ZONE :tz)::date AS ngay, count(*)::int AS so_luot FROM traces"
    " WHERE user_sub = :sub AND NOT cache_hit AND result_type IS DISTINCT FROM 'loi'"
    " AND endpoint IS DISTINCT FROM :bo_nho_endpoint"
    " AND ts >= now() - interval '365 days' GROUP BY 1 ORDER BY 1"
)
_SQL_PHAN_LOAI = text(
    "SELECT CASE WHEN endpoint = '/api/v1/soan-thao' THEN 'soan_thao' ELSE result_type END AS khoa,"
    " count(*)::int AS so FROM traces WHERE user_sub = :sub AND NOT cache_hit"
    " AND result_type IS DISTINCT FROM 'loi' AND endpoint IS DISTINCT FROM :bo_nho_endpoint"
    " GROUP BY 1 ORDER BY 2 DESC"
)


def _gop_phan_loai(dong: Iterable[tuple[str | None, int]]) -> list[dict]:
    """Gộp mọi `result_type` KHÔNG có nhãn về MỘT dòng "Khác", sắp theo số giảm dần.

    Gộp ở Python chứ không ở SQL vì bảng `traces` chỉ biết chuỗi thô; nhãn là
    quyết định của tầng này. Và gộp phần DƯ chứ không chỉ thêm nhãn: loại
    `result_type` thứ tám thêm sau này sẽ lại đẻ ra một dòng "Khác" thứ hai nếu
    chỗ này chỉ dựa vào việc `NHAN_PHAN_LOAI` được cập nhật kịp.
    """
    gop: dict[str, int] = {}
    for khoa, so in dong:
        if khoa is None:
            continue
        k = khoa if khoa in NHAN_PHAN_LOAI else KHOA_KHAC
        gop[k] = gop.get(k, 0) + int(so)
    return [
        {"khoa": k, "nhan": NHAN_PHAN_LOAI.get(k, NHAN_KHAC), "so": n}
        for k, n in sorted(gop.items(), key=lambda kv: -kv[1])
    ]


def tong_hop(sub: str) -> dict | None:
    with get_engine().connect() as c:
        u = c.execute(_SQL_USER, {"sub": sub}).mappings().one_or_none()
        if u is None:
            return None
        so_phien = int(c.execute(_SQL_SO_PHIEN, {"sub": sub}).scalar_one())
        tong = {r["endpoint"]: r["n"] for r in c.execute(_SQL_TONG, {"sub": sub}).mappings()}
        hoat_dong = [
            dict(r)
            for r in c.execute(
                _SQL_HOAT_DONG, {"sub": sub, "tz": str(mui_gio()), "bo_nho_endpoint": _BO_NHO_ENDPOINT}
            ).mappings()
        ]
        phan_loai = _gop_phan_loai(
            (r["khoa"], r["so"])
            for r in c.execute(_SQL_PHAN_LOAI, {"sub": sub, "bo_nho_endpoint": _BO_NHO_ENDPOINT}).mappings()
        )
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
