"""Phiên hội thoại theo tài khoản (spec 2026-09-07 §4, §5.1).

Mọi hàm đọc/ghi nhận `sub` và lọc theo `user_sub` — không có đường nào đọc phiên
mà không có chủ.
"""

import json

from sqlalchemy import text

from src.services.db import get_engine

TIEU_DE_TOI_DA = 80
LUOT_LICH_SU = 6
TRA_LOI_TOI_DA = 1200
DUONG_DAN_TOI_DA = 50

LOI_KHONG_THAY = "Không tìm thấy phiên này."
LOI_PHIEN_DAY = "Phiên này đã đủ {n} lượt. Mở phiên mới để tiếp tục."

_SQL_TAO = text("INSERT INTO hoi_thoai (user_sub, tieu_de) VALUES (:sub, :tieu_de) RETURNING id")
_SQL_LAY = text(
    "SELECT id::text AS id, tieu_de, tao_luc, cap_nhat_luc, khong_ghi_nho FROM hoi_thoai"
    " WHERE id = :id AND user_sub = :sub AND xoa_luc IS NULL"
)
_SQL_DEM_LUOT = text("SELECT count(*)::int FROM luot_hoi_thoai WHERE hoi_thoai_id = :id")
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
    "SELECT h.id::text AS id, h.tieu_de, h.tao_luc, h.cap_nhat_luc, h.khong_ghi_nho,"
    "       (SELECT count(*)::int FROM luot_hoi_thoai l WHERE l.hoi_thoai_id = h.id) AS so_luot"
    " FROM hoi_thoai h WHERE h.user_sub = :sub AND h.xoa_luc IS NULL"
    " ORDER BY h.cap_nhat_luc DESC, h.id DESC LIMIT :limit OFFSET :offset"
)
_SQL_LUOT = text(
    "SELECT thu_tu, cau_hoi, tra_loi, trace_id, tao_luc FROM luot_hoi_thoai WHERE hoi_thoai_id = :id ORDER BY thu_tu"
)
_SQL_DOI_TEN = text("UPDATE hoi_thoai SET tieu_de = :tieu_de WHERE id = :id AND user_sub = :sub AND xoa_luc IS NULL")
_SQL_XOA_MEM = text("UPDATE hoi_thoai SET xoa_luc = now() WHERE id = :id AND user_sub = :sub AND xoa_luc IS NULL")

_SQL_BO_NHO = text(
    "SELECT user_sub::text AS user_sub, tom_tat, tom_tat_den_thu_tu, ho_so, khong_ghi_nho"
    " FROM hoi_thoai WHERE id = :id AND xoa_luc IS NULL"
)
_SQL_GHI_BO_NHO = text(
    "UPDATE hoi_thoai SET tom_tat = :tom_tat, tom_tat_den_thu_tu = :den, ho_so = CAST(:ho_so AS jsonb) WHERE id = :id"
)
_SQL_GHI_HO_SO = text("UPDATE hoi_thoai SET ho_so = CAST(:ho_so AS jsonb) WHERE id = :id")
_SQL_LUOT_KHOANG = text(
    "SELECT thu_tu, cau_hoi, tra_loi FROM luot_hoi_thoai"
    " WHERE hoi_thoai_id = :id AND thu_tu BETWEEN :tu AND :den ORDER BY thu_tu"
)
_SQL_KHONG_GHI_NHO = text(
    "UPDATE hoi_thoai SET khong_ghi_nho = :co WHERE id = :id AND user_sub = :sub AND xoa_luc IS NULL"
)
_SQL_HO_SO_CUA_CHU = text("SELECT ho_so FROM hoi_thoai WHERE id = :id AND user_sub = :sub AND xoa_luc IS NULL")


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


def dem_luot(id: str) -> int:
    with get_engine().connect() as c:
        return int(c.execute(_SQL_DEM_LUOT, {"id": id}).scalar_one())


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


def danh_sach(sub: str, limit: int, offset: int) -> tuple[list[dict], int]:
    """Phiên còn sống của `sub`, mới nhất trước. Không còn ẩn theo gói (spec 2A §4.3)."""
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_DEM, {"sub": sub}).scalar_one())
        items = [
            dict(r) for r in c.execute(_SQL_DANH_SACH, {"sub": sub, "limit": limit, "offset": offset}).mappings().all()
        ]
    return items, tong


def nhap_phien(sub: str, luot: list[dict]) -> str:
    """Mang đoạn chat của khách vào tài khoản (spec 2A §8.4): một transaction, tiêu đề
    từ câu đầu, `thu_tu` theo thứ tự nhận. Không đụng `traces`."""
    with get_engine().begin() as c:
        pid = str(c.execute(_SQL_TAO, {"sub": sub, "tieu_de": tieu_de_mac_dinh(luot[0]["cau_hoi"])}).scalar_one())
        for lu in luot:
            c.execute(
                _SQL_GHI,
                {
                    "id": pid,
                    "cau_hoi": lu["cau_hoi"],
                    "tra_loi": json.dumps(lu["tra_loi"], ensure_ascii=False),
                    "trace_id": lu.get("trace_id"),
                },
            )
        c.execute(_SQL_CHAM, {"id": pid})
    return pid


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


def bo_nho_cua_phien(id: str) -> dict:
    """Ba lớp bộ nhớ của phiên (spec 2026-09-09 §6.1). Không lọc theo chủ: caller
    (`_chuan_bi_phien`) đã kiểm chủ bằng `lay_phien` trước đó."""
    with get_engine().connect() as c:
        r = c.execute(_SQL_BO_NHO, {"id": id}).mappings().one()
    return {
        "tom_tat": r["tom_tat"],
        "tom_tat_den_thu_tu": int(r["tom_tat_den_thu_tu"] or 0),
        "ho_so": dict(r["ho_so"] or {}),
        "khong_ghi_nho": bool(r["khong_ghi_nho"]),
        "user_sub": r["user_sub"],
    }


def ghi_bo_nho(id: str, tom_tat: str | None, den_thu_tu: int, ho_so: dict) -> None:
    with get_engine().begin() as c:
        c.execute(
            _SQL_GHI_BO_NHO,
            {"id": id, "tom_tat": tom_tat, "den": den_thu_tu, "ho_so": json.dumps(ho_so, ensure_ascii=False)},
        )


def ghi_ho_so(id: str, ho_so: dict) -> None:
    with get_engine().begin() as c:
        c.execute(_SQL_GHI_HO_SO, {"id": id, "ho_so": json.dumps(ho_so, ensure_ascii=False)})


def luot_khoang(id: str, tu: int, den: int) -> list[dict]:
    """Các lượt `tu..den` (kể cả hai đầu), câu trả lời cắt `TRA_LOI_TOI_DA` — đầu vào cho tóm tắt cuộn."""
    if den < tu:
        return []
    with get_engine().connect() as c:
        rows = c.execute(_SQL_LUOT_KHOANG, {"id": id, "tu": tu, "den": den}).mappings().all()
    return [
        {
            "thu_tu": int(r["thu_tu"]),
            "cau_hoi": r["cau_hoi"],
            "tra_loi": str((r["tra_loi"] or {}).get("answer") or "")[:TRA_LOI_TOI_DA],
        }
        for r in rows
    ]


def dat_khong_ghi_nho(sub: str, id: str, co: bool) -> bool:
    with get_engine().begin() as c:
        return c.execute(_SQL_KHONG_GHI_NHO, {"sub": sub, "id": id, "co": co}).rowcount > 0


def dat_ho_so_khoa(sub: str, id: str, khoa: str, gia_tri: str | None) -> dict | None:
    """Người dùng sửa một khoá từ dòng "Dựa trên": nguồn thành `nguoi_noi`; `None` = xoá khoá.
    Trả hồ sơ mới, hoặc None khi phiên không thuộc `sub`."""
    with get_engine().begin() as c:
        r = c.execute(_SQL_HO_SO_CUA_CHU, {"id": id, "sub": sub}).mappings().one_or_none()
        if r is None:
            return None
        ho_so = dict(r["ho_so"] or {})
        if gia_tri is None:
            ho_so.pop(khoa, None)
        else:
            ho_so[khoa] = {"gia_tri": gia_tri, "nguon": "nguoi_noi"}
        c.execute(_SQL_GHI_HO_SO, {"id": id, "ho_so": json.dumps(ho_so, ensure_ascii=False)})
    return ho_so
