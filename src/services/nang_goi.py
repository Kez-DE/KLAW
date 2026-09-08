"""Yêu cầu nâng/gia hạn gói và ĐƯỜNG ĐỔI GÓI DUY NHẤT (spec 2A §6.3, spec 2B §5.2)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.services import nhat_ky, thong_bao
from src.services.bao_ve import _doc_han_muc, mui_gio, plan_hieu_luc_tu, ten_goi
from src.services.db import get_engine

GIA_HAN_TRUOC_NGAY = 7


class GoiKhongHopLe(ValueError):  # noqa: N818 — tên khớp API `nang_goi.tao_yeu_cau` dùng, không phải lỗi hệ thống
    pass


class GoiConHieuLuc(ValueError):  # noqa: N818
    pass


class DangCho(ValueError):  # noqa: N818
    pass


class ChuaCoHoSo(ValueError):  # noqa: N818
    pass


_SQL_USER = text("SELECT plan, plan_het_han FROM users WHERE sub = :sub")
_SQL_TAO = text(
    "INSERT INTO yeu_cau_nang_goi (user_sub, loai, goi_hien_tai, goi_muon) VALUES (:sub, :loai, :ht, :muon)"
    " RETURNING id, loai, goi_hien_tai, goi_muon, trang_thai, tao_luc, xu_ly_luc, ly_do"
)
_SQL_MOI_NHAT = text(
    "SELECT id, loai, goi_hien_tai, goi_muon, trang_thai, tao_luc, xu_ly_luc, ly_do FROM yeu_cau_nang_goi"
    " WHERE user_sub = :sub ORDER BY tao_luc DESC, id DESC LIMIT 1"
)


def tao_yeu_cau(sub: str, goi_muon: str) -> dict:
    d = _doc_han_muc()
    if goi_muon not in d["goi"] or goi_muon == d["goi_mac_dinh"]:
        raise GoiKhongHopLe(goi_muon)
    with get_engine().connect() as c:
        u = c.execute(_SQL_USER, {"sub": sub}).mappings().one_or_none()
    if u is None:  # JWT hợp lệ nhưng chưa có dòng `users` (`nguoi_dung_bat_buoc` không tự tạo)
        raise ChuaCoHoSo()
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


class KhongTonTai(LookupError):  # noqa: N818
    pass


class DaXuLy(ValueError):  # noqa: N818
    pass


class TaiKhoanKhoa(ValueError):  # noqa: N818
    pass


class KhongCoGiDeThuHoi(ValueError):  # noqa: N818
    pass


NGUON_HOP_LE = ("admin", "thanh_toan")

_SQL_THEO_THAM_CHIEU = text(
    "SELECT y.id, y.trang_thai, y.user_sub::text AS sub, u.plan, u.plan_het_han"
    " FROM yeu_cau_nang_goi y JOIN users u ON u.sub = y.user_sub WHERE y.tham_chieu = :tc"
)
_SQL_KHOA_YEU_CAU = text(
    "SELECT y.id, y.user_sub::text AS sub, y.loai, y.goi_muon, y.trang_thai, y.tham_chieu,"
    " u.plan, u.plan_het_han, u.khoa_luc"
    " FROM yeu_cau_nang_goi y JOIN users u ON u.sub = y.user_sub WHERE y.id = :id FOR UPDATE OF y, u"
)
# Đường ĐỔI GÓI DUY NHẤT trong src/ — test grep ở tests/test_api/test_admin_routes.py.
_SQL_DOI_GOI = text("UPDATE users SET plan = :plan, plan_het_han = :han WHERE sub = CAST(:sub AS uuid)")
_SQL_XU_LY = text(
    "UPDATE yeu_cau_nang_goi SET trang_thai = :tt, xu_ly_luc = now(), xu_ly_boi = :boi,"
    " nguon = :nguon, tham_chieu = :tc, ly_do = :ly_do WHERE id = :id"
)


def _han_moi(loai: str, het_han_cu: datetime | None, now: datetime, chu_ky_ngay: int) -> datetime:
    """`nang_goi` tính từ `now` (ChatGPT/Claude: nâng gói hiệu lực ngay, chu kỳ tính lại);
    `gia_han` nối tiếp hạn còn hiệu lực (Stripe: renewal nối `current_period_end`)."""
    moc = now
    if loai == "gia_han" and het_han_cu is not None and het_han_cu > now:
        moc = het_han_cu
    return moc + timedelta(days=chu_ky_ngay)


def _dinh_dang(han: datetime) -> str:
    return han.astimezone(mui_gio()).strftime("%H:%M ngày %d/%m/%Y")


def duyet(yeu_cau_id: int, nguon: str, tham_chieu: str, boi: str, ip: str | None = None) -> dict:
    """Duyệt một yêu cầu và đổi gói. Idempotent theo `tham_chieu`: gọi lại trả kết quả cũ,
    KHÔNG cộng thêm chu kỳ — điều kiện để webhook thanh toán dùng lại được."""
    if nguon not in NGUON_HOP_LE:
        raise ValueError(f"nguon không hợp lệ: {nguon}")
    chu_ky = int(_doc_han_muc()["chu_ky_pro_ngay"])
    with get_engine().begin() as c:
        cu = c.execute(_SQL_THEO_THAM_CHIEU, {"tc": tham_chieu}).mappings().one_or_none()
        if cu is not None and cu["trang_thai"] == "da_duyet":
            return {
                "id": cu["id"],
                "trang_thai": "da_duyet",
                "sub": cu["sub"],
                "plan": cu["plan"],
                "plan_het_han": cu["plan_het_han"],
            }
        y = c.execute(_SQL_KHOA_YEU_CAU, {"id": yeu_cau_id}).mappings().one_or_none()
        if y is None:
            raise KhongTonTai(yeu_cau_id)
        if y["trang_thai"] != "cho_duyet":
            # Thua cuộc đua FOR UPDATE với CHÍNH tham_chieu vừa gửi: đây là ca webhook gửi
            # trùng mà idempotency key tồn tại để bắt — trả kết quả cũ, không phải DaXuLy.
            if y["trang_thai"] == "da_duyet" and y["tham_chieu"] == tham_chieu:
                return {
                    "id": y["id"],
                    "trang_thai": "da_duyet",
                    "sub": y["sub"],
                    "plan": y["plan"],
                    "plan_het_han": y["plan_het_han"],
                }
            raise DaXuLy(yeu_cau_id)
        if y["khoa_luc"] is not None:
            raise TaiKhoanKhoa(y["sub"])
        han = _han_moi(y["loai"], y["plan_het_han"], datetime.now(UTC), chu_ky)
        c.execute(_SQL_DOI_GOI, {"plan": y["goi_muon"], "han": han, "sub": y["sub"]})
        c.execute(
            _SQL_XU_LY,
            {"tt": "da_duyet", "boi": boi, "nguon": nguon, "tc": tham_chieu, "ly_do": None, "id": yeu_cau_id},
        )
        nhat_ky.ghi(
            "duyet_yeu_cau",
            doi_tuong=y["sub"],
            chi_tiet={
                "yeu_cau_id": yeu_cau_id,
                "loai": y["loai"],
                "goi": y["goi_muon"],
                "plan_het_han": han.isoformat(),
                "tham_chieu": tham_chieu,
            },
            boi=boi,
            tac_nhan_loai=nguon,
            ip=ip,
            c=c,
        )
        ten = ten_goi(y["goi_muon"])
        thong_bao.ghi(
            nguoi_nhan=y["sub"],
            loai="yeu_cau_duyet",
            tieu_de=f"Gói {ten} đã được mở",
            noi_dung=f"Tôi đã mở gói {ten} cho bạn tới {_dinh_dang(han)}.",
            duong_dan="/tai-khoan",
            khoa_gom=thong_bao.KHOA_KET_QUA.format(id=yeu_cau_id),
            c=c,
        )
        thong_bao.vo_hieu(thong_bao.KHOA_YEU_CAU.format(sub=y["sub"]), c=c)
        return {"id": yeu_cau_id, "trang_thai": "da_duyet", "sub": y["sub"], "plan": y["goi_muon"], "plan_het_han": han}


def tu_choi(yeu_cau_id: int, ly_do: str, boi: str, ip: str | None = None) -> dict:
    """Từ chối và lưu lý do. Không đụng `users`; unique index chỉ chặn `cho_duyet` nên
    người dùng gửi lại được."""
    with get_engine().begin() as c:
        y = c.execute(_SQL_KHOA_YEU_CAU, {"id": yeu_cau_id}).mappings().one_or_none()
        if y is None:
            raise KhongTonTai(yeu_cau_id)
        if y["trang_thai"] != "cho_duyet":
            raise DaXuLy(yeu_cau_id)
        c.execute(
            _SQL_XU_LY, {"tt": "tu_choi", "boi": boi, "nguon": "admin", "tc": None, "ly_do": ly_do, "id": yeu_cau_id}
        )
        nhat_ky.ghi(
            "tu_choi_yeu_cau",
            doi_tuong=y["sub"],
            chi_tiet={"yeu_cau_id": yeu_cau_id, "ly_do": ly_do},
            boi=boi,
            ip=ip,
            c=c,
        )
        thong_bao.ghi(
            nguoi_nhan=y["sub"],
            loai="yeu_cau_tu_choi",
            tieu_de="Yêu cầu nâng gói chưa được duyệt",
            noi_dung=f"Lý do: {ly_do}",
            duong_dan="/tai-khoan",
            khoa_gom=thong_bao.KHOA_KET_QUA.format(id=yeu_cau_id),
            c=c,
        )
        thong_bao.vo_hieu(thong_bao.KHOA_YEU_CAU.format(sub=y["sub"]), c=c)
        return {"id": yeu_cau_id, "trang_thai": "tu_choi", "ly_do": ly_do}
