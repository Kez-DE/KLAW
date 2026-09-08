"""Phía admin của tài khoản (spec 2026-09-08 cms-quan-ly-tai-khoan §5.2): khoá/mở khoá,
tìm, chi tiết, tổng quan. Không hàm nào ở đây đổi `plan` — việc đó của `nang_goi`."""

from sqlalchemy import text

from src.services import nhat_ky, thong_bao
from src.services.db import get_engine


class TrangThaiKhongDoi(ValueError):  # noqa: N818
    pass


_SQL_KHOA_USER = text("SELECT khoa_luc FROM users WHERE sub = CAST(:sub AS uuid) FOR UPDATE")
_SQL_KHOA = text(
    "UPDATE users SET khoa_luc = now(), khoa_ly_do = :ly_do WHERE sub = CAST(:sub AS uuid)"
    " RETURNING sub::text AS sub, khoa_luc, khoa_ly_do"
)
_SQL_MO_KHOA = text(
    "UPDATE users SET khoa_luc = NULL, khoa_ly_do = NULL WHERE sub = CAST(:sub AS uuid)"
    " RETURNING sub::text AS sub, khoa_luc, khoa_ly_do"
)


def khoa(sub: str, ly_do: str, boi: str, ip: str | None = None) -> dict:
    with get_engine().begin() as c:
        u = c.execute(_SQL_KHOA_USER, {"sub": sub}).mappings().one_or_none()
        if u is None:
            raise LookupError(sub)
        if u["khoa_luc"] is not None:
            raise TrangThaiKhongDoi("đã khoá")
        r = c.execute(_SQL_KHOA, {"ly_do": ly_do, "sub": sub}).mappings().one()
        nhat_ky.ghi("khoa_tai_khoan", doi_tuong=sub, chi_tiet={"ly_do": ly_do}, boi=boi, ip=ip, c=c)
        thong_bao.ghi(
            nguoi_nhan=sub,
            loai="tai_khoan_khoa",
            tieu_de="Tài khoản đã bị tạm khoá",
            noi_dung=f"Lý do: {ly_do}. Liên hệ hỗ trợ để được mở lại.",
            duong_dan="/tai-khoan",
            khoa_gom=thong_bao.KHOA_TAI_KHOAN.format(sub=sub, loai="tai_khoan_khoa"),
            c=c,
        )
        return dict(r)


def mo_khoa(sub: str, boi: str, ip: str | None = None) -> dict:
    with get_engine().begin() as c:
        u = c.execute(_SQL_KHOA_USER, {"sub": sub}).mappings().one_or_none()
        if u is None:
            raise LookupError(sub)
        if u["khoa_luc"] is None:
            raise TrangThaiKhongDoi("đang mở")
        r = c.execute(_SQL_MO_KHOA, {"sub": sub}).mappings().one()
        nhat_ky.ghi("mo_khoa_tai_khoan", doi_tuong=sub, chi_tiet={}, boi=boi, ip=ip, c=c)
        thong_bao.vo_hieu(thong_bao.KHOA_TAI_KHOAN.format(sub=sub, loai="tai_khoan_khoa"), c=c)
        thong_bao.ghi(
            nguoi_nhan=sub,
            loai="tai_khoan_mo",
            tieu_de="Tài khoản đã được mở lại",
            noi_dung="Bạn hỏi và soạn văn bản lại được rồi.",
            duong_dan="/tai-khoan",
            khoa_gom=thong_bao.KHOA_TAI_KHOAN.format(sub=sub, loai="tai_khoan_mo"),
            c=c,
        )
        return dict(r)
