"""Vòng đời một việc đọc tài liệu và tập dữ kiện của nó (spec 2026-09-15).

Tệp gốc KHÔNG bao giờ chạm đĩa. Nó vào bằng bytes, đi qua `doc_tai_lieu`, và
người gọi buông tham chiếu ngay sau đó — kể cả khi việc hỏng giữa chừng. Thứ
được lưu là dữ kiện đã rút cùng dấu vân một chiều của tài liệu, cùng chính sách
`traces.dau_van_ban` đã đặt cho `/soat`: dữ liệu cá nhân trong tài liệu của
khách thường thuộc về người thứ ba chưa từng dùng KLAW và chưa đồng ý gì cả.
"""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.services.traces import dau_van_ban

logger = logging.getLogger(__name__)

# FR-005 — hai trần tuyệt đối. Vượt thì từ chối và NÊU ĐÚNG trần nào bị vượt:
# "tệp quá lớn" không cho người dùng biết phải làm gì, "quá 100 trang" thì có.
TRAN_TRANG = 100
TRAN_BYTE = 20 * 1024 * 1024

# FR-029/030 — từ ngưỡng này trở lên thì chuyển sang chạy nền. Hợp đồng lao
# động, quyết định, thông báo thật gần như luôn dưới ngưỡng, nên đường nền chỉ
# bật khi gặp tài liệu bất thường.
NGUONG_NEN_TRANG = 10

TRANG_THAI = ("dang_doc", "xong", "hong", "huy")


class VuotTran(Exception):
    """Tài liệu vượt một trần tuyệt đối. `tran` nói rõ trần nào."""

    def __init__(self, tran: str, gioi_han: int, thuc_te: int) -> None:
        super().__init__(f"vượt trần {tran}: {thuc_te} > {gioi_han}")
        self.tran = tran
        self.gioi_han = gioi_han
        self.thuc_te = thuc_te


def kiem_kich_thuoc(so_byte: int) -> None:
    if so_byte > TRAN_BYTE:
        raise VuotTran("so_byte", TRAN_BYTE, so_byte)


def kiem_so_trang(so_trang: int) -> None:
    if so_trang > TRAN_TRANG:
        raise VuotTran("so_trang", TRAN_TRANG, so_trang)


def chay_nen(so_trang: int | None) -> bool:
    return bool(so_trang) and so_trang >= NGUONG_NEN_TRANG


def hop_nhat_sua(cu: dict, gia_tri_moi: str) -> dict:
    """Dữ kiện sau khi người dùng sửa — FR-014, FR-015.

    Đoạn trích chứng minh giá trị CŨ. Giữ nó nằm cạnh giá trị MỚI là nói dối
    bằng cách bày ra một bằng chứng cho một điều nó không chứng minh. Nên `trich`
    bị gỡ, `trich_goc` được giữ để người dùng còn đối chiếu, và `nguon` đổi để
    giao diện không trình bày giá trị này như thể đến từ tài liệu.

    Dữ kiện vốn do người dùng tự nhập thì sửa vẫn là người dùng nhập — không có
    gì để giữ và không có gì để đổi.
    """
    moi = dict(cu)
    moi["gia_tri"] = gia_tri_moi
    moi.setdefault("trich_goc", None)
    if cu.get("nguon") == "nguoi_dung_nhap":
        return moi
    moi["trich_goc"] = cu.get("trich_goc") or cu.get("trich")
    moi["trich"] = None
    moi["nguon"] = "nguoi_dung_sua"
    return moi


def thanh_facts(du_kien: list[dict]) -> dict[str, str]:
    """Tập dữ kiện -> `facts` của luồng soạn thảo — FR-019, FR-020.

    Chỉ mang những trường THỰC SỰ có giá trị. Trường không có dữ kiện không xuất
    hiện ở đây, nên `gom_du_kien.con_thieu` tự tính đúng phần còn trống mà không
    cần biết gì về tài liệu.
    """
    return {
        d["khoa"]: str(d["gia_tri"]).strip()
        for d in du_kien
        if not d.get("xoa_luc") and str(d.get("gia_tri") or "").strip()
    }


# ═══ Truy cập dữ liệu ═══════════════════════════════════════════════════════
# SQL thô trên Core Engine, khuôn `services/ban_thao.py`. Mọi truy vấn lọc theo
# `user_sub`: một việc đọc và dữ kiện của nó không bao giờ đi qua ranh giới tài
# khoản.


def tao_viec(
    engine: Engine,
    *,
    user_sub: str,
    hoi_thoai_id: str,
    ten_tep: str,
    du_lieu: bytes,
    loai: str | None,
) -> str:
    """Ghi một việc đọc ở trạng thái `dang_doc`, trả `id`.

    `du_lieu` chỉ được dùng để tính dấu vân rồi bỏ; không nhánh nào ghi nó ra
    đĩa hay vào DB (FR-022, FR-023).
    """
    kiem_kich_thuoc(len(du_lieu))
    dau = dau_van_ban(du_lieu.decode("utf-8", errors="replace"), 0)
    with engine.begin() as c:
        return str(
            c.execute(
                text(
                    "INSERT INTO viec_doc_tai_lieu "
                    "(user_sub, hoi_thoai_id, ten_tep, dau_van_ban, so_byte, loai) "
                    "VALUES (:u, :h, :t, :d, :b, :l) RETURNING id"
                ),
                {"u": user_sub, "h": hoi_thoai_id, "t": ten_tep, "d": dau, "b": len(du_lieu), "l": loai},
            ).scalar_one()
        )


def dat_trang_thai(
    engine: Engine,
    viec_id: str,
    user_sub: str,
    trang_thai: str,
    *,
    ly_do_hong: str | None = None,
    so_trang: int | None = None,
    chi_phi_usd: float | None = None,
) -> None:
    if trang_thai not in TRANG_THAI:
        raise ValueError(f"trạng thái lạ: {trang_thai}")
    if trang_thai == "hong" and not ly_do_hong:
        # Cùng ràng buộc `ck_viec_doc_hong_co_ly_do` ở DB, chặn sớm hơn một tầng
        # để lỗi chỉ ra đúng dòng gọi sai.
        raise ValueError("trạng thái 'hong' phải có ly_do_hong")
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE viec_doc_tai_lieu SET trang_thai = :s, cap_nhat_luc = now(), "
                "ly_do_hong = COALESCE(:r, ly_do_hong), so_trang = COALESCE(:p, so_trang), "
                "chi_phi_usd = COALESCE(:c, chi_phi_usd) "
                "WHERE id = :i AND user_sub = :u"
            ),
            {"s": trang_thai, "r": ly_do_hong, "p": so_trang, "c": chi_phi_usd, "i": viec_id, "u": user_sub},
        )


def luu_du_kien(engine: Engine, viec_id: str, hoi_thoai_id: str, du_kien: list[dict]) -> int:
    """Ghi tập dữ kiện đã qua neo. Chỉ nhận dữ kiện CÓ neo hợp lệ."""
    if not du_kien:
        return 0
    hang = [
        {
            "v": viec_id,
            "h": hoi_thoai_id,
            "k": d["key"],
            "n": d.get("nhan"),
            "g": d["gia_tri"],
            "t": d["trich"],
            "c": d["neo"].chi_so_don_vi,
            "p": d["neo"].trang,
            "o": d["neo"].offset_dau,
        }
        for d in du_kien
    ]
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO du_kien_tai_lieu "
                "(viec_id, hoi_thoai_id, khoa, nhan, gia_tri, nguon, trich, chi_so_don_vi, trang, offset_dau) "
                "VALUES (:v, :h, :k, :n, :g, 'tai_lieu', :t, :c, :p, :o)"
            ),
            hang,
        )
    return len(hang)


def lay_viec(engine: Engine, viec_id: str, user_sub: str) -> dict[str, Any] | None:
    with engine.connect() as c:
        r = c.execute(
            text("SELECT * FROM viec_doc_tai_lieu WHERE id = :i AND user_sub = :u"),
            {"i": viec_id, "u": user_sub},
        ).mappings().first()
    return dict(r) if r else None


def du_kien_cua_hoi_thoai(engine: Engine, hoi_thoai_id: str, user_sub: str) -> list[dict]:
    with engine.connect() as c:
        return [
            dict(r)
            for r in c.execute(
                text(
                    "SELECT d.* FROM du_kien_tai_lieu d "
                    "JOIN viec_doc_tai_lieu v ON v.id = d.viec_id "
                    "WHERE d.hoi_thoai_id = :h AND v.user_sub = :u AND d.xoa_luc IS NULL "
                    "ORDER BY d.tao_luc"
                ),
                {"h": hoi_thoai_id, "u": user_sub},
            ).mappings()
        ]


def sua_du_kien(engine: Engine, du_kien_id: str, user_sub: str, gia_tri_moi: str) -> dict | None:
    with engine.begin() as c:
        cu = c.execute(
            text(
                "SELECT d.* FROM du_kien_tai_lieu d JOIN viec_doc_tai_lieu v ON v.id = d.viec_id "
                "WHERE d.id = :i AND v.user_sub = :u AND d.xoa_luc IS NULL"
            ),
            {"i": du_kien_id, "u": user_sub},
        ).mappings().first()
        if not cu:
            return None
        moi = hop_nhat_sua(dict(cu), gia_tri_moi)
        c.execute(
            text(
                "UPDATE du_kien_tai_lieu SET gia_tri = :g, nguon = :n, trich = :t, trich_goc = :tg "
                "WHERE id = :i"
            ),
            {"g": moi["gia_tri"], "n": moi["nguon"], "t": moi["trich"], "tg": moi.get("trich_goc"), "i": du_kien_id},
        )
    return moi


def xoa_du_kien(engine: Engine, du_kien_id: str, user_sub: str) -> bool:
    with engine.begin() as c:
        return (
            c.execute(
                text(
                    "UPDATE du_kien_tai_lieu d SET xoa_luc = now() FROM viec_doc_tai_lieu v "
                    "WHERE v.id = d.viec_id AND d.id = :i AND v.user_sub = :u AND d.xoa_luc IS NULL"
                ),
                {"i": du_kien_id, "u": user_sub},
            ).rowcount
            > 0
        )


def xoa_theo_hoi_thoai(engine: Engine, hoi_thoai_id: str, user_sub: str) -> int:
    """FR-024 — xoá toàn bộ dữ kiện của một cuộc hội thoại bằng một thao tác.

    Xoá theo hội thoại cũng xảy ra TỰ ĐỘNG khi hội thoại bị xoá, nhờ
    `ON DELETE CASCADE` ở migration 026. Hàm này là đường người dùng chủ động
    dọn mà vẫn giữ cuộc hội thoại.
    """
    with engine.begin() as c:
        return c.execute(
            text(
                "DELETE FROM viec_doc_tai_lieu WHERE hoi_thoai_id = :h AND user_sub = :u"
            ),
            {"h": hoi_thoai_id, "u": user_sub},
        ).rowcount
