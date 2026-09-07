"""Yêu cầu nâng/gia hạn gói (spec 2A §6.3). Duyệt thuộc gói 2B (tạm SQL tay)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.services.bao_ve import _doc_han_muc, plan_hieu_luc_tu
from src.services.db import get_engine

GIA_HAN_TRUOC_NGAY = 7


class GoiKhongHopLe(ValueError):  # noqa: N818 — tên khớp API `nang_goi.tao_yeu_cau` dùng, không phải lỗi hệ thống
    pass


class GoiConHieuLuc(ValueError):  # noqa: N818
    pass


class DangCho(ValueError):  # noqa: N818
    pass


_SQL_USER = text("SELECT plan, plan_het_han FROM users WHERE sub = :sub")
_SQL_TAO = text(
    "INSERT INTO yeu_cau_nang_goi (user_sub, loai, goi_hien_tai, goi_muon) VALUES (:sub, :loai, :ht, :muon)"
    " RETURNING id, loai, goi_hien_tai, goi_muon, trang_thai, tao_luc, xu_ly_luc"
)
_SQL_MOI_NHAT = text(
    "SELECT id, loai, goi_hien_tai, goi_muon, trang_thai, tao_luc, xu_ly_luc FROM yeu_cau_nang_goi"
    " WHERE user_sub = :sub ORDER BY tao_luc DESC, id DESC LIMIT 1"
)


def tao_yeu_cau(sub: str, goi_muon: str) -> dict:
    d = _doc_han_muc()
    if goi_muon not in d["goi"] or goi_muon == d["goi_mac_dinh"]:
        raise GoiKhongHopLe(goi_muon)
    with get_engine().connect() as c:
        u = c.execute(_SQL_USER, {"sub": sub}).mappings().one()
    hieu_luc = plan_hieu_luc_tu(str(u["plan"]), u["plan_het_han"])
    if hieu_luc == goi_muon:
        het = u["plan_het_han"]
        if het is None or het - datetime.now(UTC) > timedelta(days=GIA_HAN_TRUOC_NGAY):
            raise GoiConHieuLuc()
        loai = "gia_han"
    else:
        loai = "nang_goi"
    try:
        with get_engine().begin() as c:
            r = c.execute(_SQL_TAO, {"sub": sub, "loai": loai, "ht": hieu_luc, "muon": goi_muon}).mappings().one()
            return dict(r)
    except IntegrityError as e:  # unique index: đã có yêu cầu cho_duyet
        raise DangCho() from e


def moi_nhat(sub: str) -> dict | None:
    with get_engine().connect() as c:
        r = c.execute(_SQL_MOI_NHAT, {"sub": sub}).mappings().one_or_none()
    return dict(r) if r is not None else None
