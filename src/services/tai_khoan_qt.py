"""Phía admin của tài khoản (spec 2026-09-08 cms-quan-ly-tai-khoan §5.2): khoá/mở khoá,
tìm, chi tiết, tổng quan. Không hàm nào ở đây đổi `plan` — việc đó của `nang_goi`."""

from sqlalchemy import text

from src.services import ho_so, nhat_ky, thong_bao
from src.services.bao_ve import _doc_han_muc, moc_ngay, ten_goi
from src.services.db import get_engine
from src.services.nang_goi import KhongTonTai


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
            raise KhongTonTai(sub)
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


def mo_khoa(sub: str, ly_do: str, boi: str, ip: str | None = None) -> dict:
    with get_engine().begin() as c:
        u = c.execute(_SQL_KHOA_USER, {"sub": sub}).mappings().one_or_none()
        if u is None:
            raise KhongTonTai(sub)
        if u["khoa_luc"] is None:
            raise TrangThaiKhongDoi("đang mở")
        r = c.execute(_SQL_MO_KHOA, {"sub": sub}).mappings().one()
        nhat_ky.ghi("mo_khoa_tai_khoan", doi_tuong=sub, chi_tiet={"ly_do": ly_do}, boi=boi, ip=ip, c=c)
        thong_bao.vo_hieu(thong_bao.KHOA_TAI_KHOAN.format(sub=sub, loai="tai_khoan_khoa"), c=c)
        # Vô hiệu dòng cũ TRƯỚC khi ghi — chỉ mục duy nhất chặn dòng thứ hai
        # trở đi nếu dòng đầu còn hiệu lực, khiến người dùng không được báo.
        thong_bao.vo_hieu(thong_bao.KHOA_TAI_KHOAN.format(sub=sub, loai="tai_khoan_mo"), c=c)
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


# ── Đọc: tìm, chi tiết, danh sách yêu cầu, tổng quan, danh mục gói ───────────
# `plan`/`plan_het_han` trả THÔ ở đây — gói HIỆU LỰC là việc của caller (router),
# không phải của tầng đọc này.

_LOC_LUOT = (
    " AND NOT t.cache_hit AND t.endpoint = '/api/v1/tra-cuu'"
    " AND (t.result_type IS NULL OR t.result_type NOT IN ('loi', 'out_of_scope'))"
)
_SQL_TIM_DEM = text("SELECT count(*)::int FROM users WHERE email ILIKE :q")
_SQL_TIM = text(
    "SELECT u.sub::text AS sub, u.email, u.plan, u.plan_het_han, u.khoa_luc, u.created_at AS tao_luc,"
    " (SELECT count(*)::int FROM hoi_thoai h WHERE h.user_sub = u.sub AND h.xoa_luc IS NULL) AS so_phien,"
    " (SELECT count(*)::int FROM traces t WHERE t.user_sub = u.sub"
    "  AND t.ts >= now() - interval '30 days'" + _LOC_LUOT + ") AS luot_30_ngay"
    " FROM users u WHERE u.email ILIKE :q ORDER BY u.created_at DESC LIMIT :limit OFFSET :offset"
)
_SQL_KHOA_CUA = text("SELECT khoa_luc, khoa_ly_do FROM users WHERE sub = CAST(:sub AS uuid)")
_SQL_THEO_SUBS = text("SELECT sub::text AS sub, email FROM users WHERE sub = ANY(CAST(:subs AS uuid[]))")


def theo_subs(subs: list[str]) -> dict[str, str | None]:
    """`sub -> email` cho một danh sách sub (dùng cho bảng trực tuyến); rỗng thì không chạm DB."""
    if not subs:
        return {}
    with get_engine().connect() as c:
        rows = c.execute(_SQL_THEO_SUBS, {"subs": subs}).mappings().all()
    return {r["sub"]: r["email"] for r in rows}


_COT_YC = "id, loai, goi_hien_tai, goi_muon, trang_thai, tao_luc, xu_ly_luc, ly_do"
_SQL_YEU_CAU_CUA = text(
    f"SELECT {_COT_YC} FROM yeu_cau_nang_goi WHERE user_sub = CAST(:sub AS uuid)"
    " ORDER BY tao_luc DESC, id DESC LIMIT 50"
)
_SQL_YEU_CAU_ID = text(f"SELECT {_COT_YC} FROM yeu_cau_nang_goi WHERE id = :id")
_LOC_YC = (
    " FROM yeu_cau_nang_goi y JOIN users u ON u.sub = y.user_sub"
    " WHERE (CAST(:tt AS text) IS NULL OR y.trang_thai = :tt)"
    " AND (CAST(:q AS text) IS NULL OR u.email ILIKE :q)"
)
_SQL_YC_DEM = text("SELECT count(*)::int" + _LOC_YC)
_SQL_YC = text(
    "SELECT y.id, y.user_sub::text AS user_sub, u.email, y.loai, y.goi_hien_tai, y.goi_muon, y.trang_thai,"
    " y.tao_luc, y.xu_ly_luc, y.xu_ly_boi, y.ly_do, u.plan, u.plan_het_han, u.khoa_luc"
    + _LOC_YC
    + " ORDER BY y.tao_luc DESC, y.id DESC LIMIT :limit OFFSET :offset"
)
_SQL_TONG_QUAN = text(
    "SELECT"
    " (SELECT count(*)::int FROM users) AS tong_tai_khoan,"
    " (SELECT count(*)::int FROM users WHERE plan <> :mac_dinh AND khoa_luc IS NULL"
    "   AND (plan_het_han IS NULL OR plan_het_han > now())) AS dang_ca_nhan,"
    " (SELECT count(*)::int FROM yeu_cau_nang_goi WHERE trang_thai = 'cho_duyet') AS cho_duyet,"
    " (SELECT count(*)::int FROM users WHERE plan <> :mac_dinh"
    "   AND plan_het_han > now() AND plan_het_han <= now() + interval '7 days') AS het_han_7_ngay,"
    " (SELECT count(*)::int FROM users WHERE created_at >= now() - interval '7 days') AS moi_7_ngay,"
    " (SELECT count(*)::int FROM users WHERE khoa_luc IS NOT NULL) AS dang_khoa,"
    " (SELECT count(*)::int FROM traces t WHERE t.ts >= :moc" + _LOC_LUOT + ") AS hoi_dap_hom_nay"
)


def tim(q: str, limit: int, offset: int) -> tuple[int, list[dict]]:
    """Tìm tài khoản theo email (khớp một phần, không phân biệt hoa thường)."""
    p = {"q": f"%{q.strip()}%"}
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_TIM_DEM, p).scalar_one())
        rows = [dict(r) for r in c.execute(_SQL_TIM, {**p, "limit": limit, "offset": offset}).mappings()]
    return tong, rows


def chi_tiet(sub: str) -> dict | None:
    """Hồ sơ đầy đủ của một tài khoản: `ho_so.tong_hop` + trạng thái khoá + lịch sử yêu cầu."""
    d = ho_so.tong_hop(sub)
    if d is None:
        return None
    with get_engine().connect() as c:
        k = c.execute(_SQL_KHOA_CUA, {"sub": sub}).mappings().one()
        yc = [dict(r) for r in c.execute(_SQL_YEU_CAU_CUA, {"sub": sub}).mappings()]
    return {**d, "sub": sub, "khoa_luc": k["khoa_luc"], "khoa_ly_do": k["khoa_ly_do"], "yeu_cau": yc}


def yeu_cau_theo_id(id: int) -> dict | None:
    """Một yêu cầu nâng/gia hạn gói theo id, không kèm thông tin tài khoản."""
    with get_engine().connect() as c:
        r = c.execute(_SQL_YEU_CAU_ID, {"id": id}).mappings().one_or_none()
    return dict(r) if r is not None else None


def danh_sach_yeu_cau(trang_thai: str | None, q: str | None, limit: int, offset: int) -> tuple[int, list[dict]]:
    """Danh sách yêu cầu nâng/gia hạn gói cho admin, lọc theo trạng thái và/hoặc email."""
    p = {"tt": trang_thai, "q": f"%{q.strip()}%" if q else None}
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_YC_DEM, p).scalar_one())
        rows = [dict(r) for r in c.execute(_SQL_YC, {**p, "limit": limit, "offset": offset}).mappings()]
    return tong, rows


def tong_quan() -> dict:
    """Bảy số đếm cho trang tổng quan admin."""
    with get_engine().connect() as c:
        r = c.execute(_SQL_TONG_QUAN, {"mac_dinh": _doc_han_muc()["goi_mac_dinh"], "moc": moc_ngay()}).mappings().one()
    return dict(r)


def danh_sach_goi() -> dict:
    """Danh mục gói CHỈ đọc từ `config/han_muc.yaml` — không chạm DB."""
    d = _doc_han_muc()
    return {
        "goi": [
            {"ma": ma, "ten": ten_goi(ma), "han_muc": {k: int(v) for k, v in hm.items()}} for ma, hm in d["goi"].items()
        ],
        "goi_mac_dinh": str(d["goi_mac_dinh"]),
        "chu_ky_pro_ngay": int(d["chu_ky_pro_ngay"]),
    }
