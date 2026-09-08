"""Thông báo — KLAW sở hữu, hai người đọc (spec 2026-09-08 cms-quan-ly-tai-khoan §5.2).

`nguoi_nhan is None` là hộp thư admin, tường minh ở mọi hàm; không dùng chuỗi
rỗng hay giá trị đặc biệt. `khoa_gom` + chỉ mục duy nhất (WHERE NOT het_hieu_luc)
chặn nhân bản: ghi lặp trong lúc chưa xử lý không tạo thêm dòng.
"""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.services.db import get_engine
from src.services.nhat_ky import ket_noi

KHOA_YEU_CAU = "yeu_cau:{sub}"
KHOA_KET_QUA = "ket_qua:{id}"
KHOA_TAI_KHOAN = "tai_khoan:{sub}:{loai}"

_SQL_GHI = text(
    "INSERT INTO thong_bao (nguoi_nhan, loai, tieu_de, noi_dung, duong_dan, khoa_gom)"
    " VALUES (CAST(:nn AS uuid), :loai, :td, :nd, :dd, :kg)"
    " ON CONFLICT (khoa_gom) WHERE NOT het_hieu_luc DO NOTHING RETURNING id"
)
_SQL_VO_HIEU = text("UPDATE thong_bao SET het_hieu_luc = TRUE WHERE khoa_gom = :kg AND NOT het_hieu_luc")
_NGUOI = " nguoi_nhan IS NOT DISTINCT FROM CAST(:nn AS uuid) AND NOT het_hieu_luc"
_SQL_DANH_SACH = text(
    "SELECT id, loai, tieu_de, noi_dung, duong_dan, khoa_gom, da_doc, tao_luc FROM thong_bao WHERE"
    + _NGUOI
    + " AND (NOT CAST(:chua_doc AS boolean) OR NOT da_doc) ORDER BY tao_luc DESC, id DESC LIMIT :limit"
)
_SQL_DEM = text("SELECT count(*)::int FROM thong_bao WHERE" + _NGUOI + " AND NOT da_doc")
_SQL_DA_DOC = text(
    "UPDATE thong_bao SET da_doc = TRUE WHERE id = ANY(CAST(:ids AS bigint[])) AND NOT da_doc AND" + _NGUOI
)


def ghi(
    *,
    nguoi_nhan: str | None,
    loai: str,
    tieu_de: str,
    noi_dung: str,
    duong_dan: str,
    khoa_gom: str,
    c: Connection | None = None,
) -> int | None:
    with ket_noi(c) as k:
        r = k.execute(
            _SQL_GHI,
            {"nn": nguoi_nhan, "loai": loai, "td": tieu_de, "nd": noi_dung, "dd": duong_dan, "kg": khoa_gom},
        ).scalar_one_or_none()
    return int(r) if r is not None else None


def vo_hieu(khoa_gom: str, c: Connection | None = None) -> int:
    with ket_noi(c) as k:
        return k.execute(_SQL_VO_HIEU, {"kg": khoa_gom}).rowcount


def danh_sach(nguoi_nhan: str | None, *, chi_chua_doc: bool = False, limit: int = 50) -> list[dict]:
    with get_engine().connect() as c:
        rows = c.execute(_SQL_DANH_SACH, {"nn": nguoi_nhan, "chua_doc": chi_chua_doc, "limit": limit}).mappings()
        return [dict(r) for r in rows]


def dem_chua_doc(nguoi_nhan: str | None) -> int:
    with get_engine().connect() as c:
        return int(c.execute(_SQL_DEM, {"nn": nguoi_nhan}).scalar_one())


def danh_dau_da_doc(ids: list[int], nguoi_nhan: str | None) -> int:
    """Chỉ đánh dấu dòng ĐÚNG người nhận; id của người khác không có tác dụng."""
    if not ids:
        return 0
    with get_engine().begin() as c:
        return c.execute(_SQL_DA_DOC, {"ids": ids, "nn": nguoi_nhan}).rowcount


def hop_thu(nguoi_nhan: str | None, chi_chua_doc: bool = False) -> dict:
    """Hình `DanhSachThongBaoOut` — dùng chung cho router admin và router người dùng."""
    return {"so_chua_doc": dem_chua_doc(nguoi_nhan), "items": danh_sach(nguoi_nhan, chi_chua_doc=chi_chua_doc)}
