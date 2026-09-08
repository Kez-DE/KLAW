"""Nhật ký quản trị — CHỈ GHI THÊM (spec 2026-09-08 cms-quan-ly-tai-khoan §5.1, §5.2).

Bản pháp lý của mọi thao tác admin. Module này không có hàm sửa hay xoá, và
`tests/test_services/test_nhat_ky.py` grep toàn `src/` để khẳng định không nơi
nào khác làm việc đó. Thông lệ lấy từ Audit Logs của OpenAI: bản ghi kiểm toán
phải bất biến thì mới dùng để điều tra được.
"""

import csv as _csv
import io
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.services.db import get_engine

COT_CSV = ["id", "tao_luc", "hanh_dong", "doi_tuong", "boi", "tac_nhan_loai", "ip", "chi_tiet"]

_SQL_GHI = text(
    "INSERT INTO nhat_ky_quan_tri (hanh_dong, doi_tuong, chi_tiet, boi, tac_nhan_loai, ip)"
    " VALUES (:hd, CAST(:dt AS uuid), CAST(:ct AS jsonb), :boi, :tn, :ip) RETURNING id"
)
_LOC = (
    " WHERE (CAST(:tu AS timestamptz) IS NULL OR tao_luc >= :tu)"
    " AND (CAST(:den AS timestamptz) IS NULL OR tao_luc < :den)"
    " AND (CAST(:hd AS text) IS NULL OR hanh_dong = :hd)"
    " AND (CAST(:dt AS text) IS NULL OR doi_tuong = CAST(:dt AS uuid))"
)
_SQL_DEM = text("SELECT count(*)::int FROM nhat_ky_quan_tri" + _LOC)
_SQL_DANH_SACH = text(
    "SELECT id, hanh_dong, doi_tuong::text AS doi_tuong, chi_tiet, boi, tac_nhan_loai, ip, tao_luc"
    " FROM nhat_ky_quan_tri" + _LOC + " ORDER BY tao_luc DESC, id DESC LIMIT :limit OFFSET :offset"
)


@contextmanager
def ket_noi(c: Connection | None) -> Iterator[Connection]:
    """Dùng transaction ngoài nếu có, không thì mở một transaction mới.

    `nang_goi.duyet` ghi nhật ký TRONG cùng transaction đổi gói: hoặc cả hai
    cùng commit, hoặc không gì cả — một gói được đổi mà không có dòng nhật ký
    là đúng lỗ hổng mà bảng này tồn tại để bịt.
    """
    if c is not None:
        yield c
        return
    with get_engine().begin() as moi:
        yield moi


def ghi(
    hanh_dong: str,
    *,
    doi_tuong: str | None,
    chi_tiet: dict,
    boi: str,
    tac_nhan_loai: str = "admin",
    ip: str | None = None,
    c: Connection | None = None,
) -> int:
    with ket_noi(c) as k:
        r = k.execute(
            _SQL_GHI,
            {
                "hd": hanh_dong,
                "dt": doi_tuong,
                "ct": json.dumps(chi_tiet, ensure_ascii=False),
                "boi": boi,
                "tn": tac_nhan_loai,
                "ip": ip,
            },
        ).scalar_one()
    return int(r)


def danh_sach(
    *,
    tu: datetime | None,
    den: datetime | None,
    hanh_dong: str | None,
    doi_tuong: str | None,
    limit: int,
    offset: int,
) -> tuple[int, list[dict]]:
    p = {"tu": tu, "den": den, "hd": hanh_dong, "dt": doi_tuong}
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_DEM, p).scalar_one())
        rows = [dict(r) for r in c.execute(_SQL_DANH_SACH, {**p, "limit": limit, "offset": offset}).mappings()]
    return tong, rows


def csv(rows: list[dict]) -> str:
    """CSV UTF-8 có tiêu đề; `chi_tiet` là JSON một dòng (csv tự bao ngoặc kép khi cần)."""
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow(COT_CSV)
    for r in rows:
        tl = r["tao_luc"]
        w.writerow(
            [
                r["id"],
                tl.isoformat() if isinstance(tl, datetime) else tl,
                r["hanh_dong"],
                r["doi_tuong"] or "",
                r["boi"],
                r["tac_nhan_loai"],
                r["ip"] or "",
                json.dumps(r["chi_tiet"], ensure_ascii=False),
            ]
        )
    return buf.getvalue()
