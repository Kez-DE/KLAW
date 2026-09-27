"""Vòng đời một việc đọc tài liệu và tập dữ kiện của nó (spec 2026-09-15).

Từ quyết định 2026-09-26 (`docs/decisions/2026-09-26-luu-khuon-goc-va-dien-tai-cho.md`)
tệp tải lên ĐƯỢC LƯU: `.docx`, `.doc` (dưới dạng `.docx` đã quy đổi) và PDF
thành **khuôn gốc** ở bảng `khuon_goc` (migration 036), để "Bản tải lên" hiện
đúng từng trang như tệp. Ảnh thì không: chúng giữ đường OCR và chỉ phần đã đọc
được lưu. Khuôn gốc sống ĐÚNG BẰNG đời cuộc hội thoại — xoá hội thoại (mềm hay
cứng) hoặc xoá tài khoản là xoá cứng nó qua khoá ngoại tới
`viec_doc_tai_lieu` — và không đi vào log, trace, hồ sơ tài khoản, bộ nhớ dài
hạn hay dataset: dữ liệu cá nhân trong tài liệu của khách thường thuộc về
người thứ ba chưa từng dùng KLAW và chưa đồng ý gì cả.

Ngoài DB, tệp chỉ chạm đĩa trong thư mục tạm của LibreOffice/`pdftoppm`
(`doc_tai_lieu._chay_soffice`, `dung_trang.anh_trang`), xoá ngay khi trả về
hoặc ném lỗi; chỉ một tiến trình bị giết/hết bộ nhớ đúng lúc đang chuyển đổi
mới để sót tệp đó lại trong `/tmp` của container.
"""

import hashlib
import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.services.doc_tai_lieu import (
    AnhTaiLieu,
    ChoTrong,
    DiaChi,
    DinhDangChu,
    DonViVanBan,
    GianCach,
    MocTab,
    NguonChu,
)

logger = logging.getLogger(__name__)

# FR-005 — hai trần tuyệt đối. Vượt thì từ chối và NÊU ĐÚNG trần nào bị vượt:
# "tệp quá lớn" không cho người dùng biết phải làm gì, "quá 10 trang" thì có.
# 10 trang, đếm bằng dàn trang THẬT (quyết định 2026-09-26): tài liệu trong
# trần được gửi trọn cho mô hình, không cắt ngầm.
TRAN_TRANG = 10
TRAN_BYTE = 20 * 1024 * 1024

# FR-029/030 — từ ngưỡng này trở lên thì chuyển sang chạy nền. Hợp đồng lao
# động, quyết định, thông báo thật gần như luôn dưới ngưỡng, nên đường nền chỉ
# bật khi gặp tài liệu bất thường.
NGUONG_NEN_TRANG = 10

TRANG_THAI = ("dang_doc", "can_chon_loai", "xong", "hong", "huy")


def _han_muc_tai_lieu() -> dict:
    """Hai trần của tính năng này, đọc từ `config/han_muc.yaml` như mọi hạn mức
    khác của dự án: số là DỮ LIỆU, đổi số không phải sửa code."""
    import yaml

    from src.services.bao_ve import HAN_MUC_PATH

    return yaml.safe_load(HAN_MUC_PATH.read_text(encoding="utf-8"))["tai_lieu"]


_HM = _han_muc_tai_lieu()

# FR-036/037 — cái PHANH thay cho trần thời gian. Chủ dự án bỏ trần thời gian
# ngày 2026-09-15 vì "điều khách hàng muốn là ra được câu trả lời", nên một lần
# đọc được chạy lâu; nó chỉ không được tốn vô hạn. Trần chi phí NGÀY sẵn có dùng
# chung cho mọi người dùng, nên nếu chỉ dựa vào nó thì một tài liệu dị dạng của
# MỘT người làm cạn hạn mức của TẤT CẢ.
TRAN_CHI_PHI_TAI_LIEU_USD = _HM["chi_phi_usd"]
_USD_MOI_NGHIN_KY_TU = _HM["usd_moi_nghin_ky_tu"]

# FR-037 — số lần rút lại CÓ TRẢ TIỀN trên một tài liệu (`nhan_rut_lai`). `doc-lai`
# không trừ `tai_lieu_ngay`, nên không có trần này thì một tệp đã lưu là số lượt
# gọi mô hình không giới hạn.
TRAN_THU_LAI = int(_HM["so_lan_thu"])

# Số tài liệu mỗi ngày theo gói — FR-004. Cùng nguồn dữ liệu với hạn mức hỏi đáp
# và soạn thảo, nên đổi số vẫn chỉ là sửa `config/han_muc.yaml`.
TAI_LIEU_NGAY = {goi: int(v["tai_lieu_ngay"]) for goi, v in _HM["theo_goi"].items()}


def uoc_chi_phi(so_ky_tu: int) -> float:
    """Ước chi phí một lần đọc, TRƯỚC khi gọi mô hình.

    Tuyến tính theo độ dài tài liệu. Đây là phòng ngừa chứ không phải cưỡng chế:
    nó chặn được tài liệu khổng lồ trước khi tiêu đồng nào, còn ca ước sai thì
    `vuot_chi_phi_thuc` bắt lại sau khi gọi.
    """
    return max(0, so_ky_tu) / 1000 * _USD_MOI_NGHIN_KY_TU


def vuot_tran_uoc(so_ky_tu: int) -> bool:
    """Ước chi phí có vượt trần không. 0 = TẮT, cùng quy ước `bao_ve.kiem_tran_chi_phi`."""
    return TRAN_CHI_PHI_TAI_LIEU_USD > 0 and uoc_chi_phi(so_ky_tu) > TRAN_CHI_PHI_TAI_LIEU_USD


def kiem_tran_chi_phi_tai_lieu(so_ky_tu: int) -> None:
    """Chặn trước khi gọi mô hình."""
    if vuot_tran_uoc(so_ky_tu):
        raise VuotTran("chi_phi", TRAN_CHI_PHI_TAI_LIEU_USD, uoc_chi_phi(so_ky_tu))


def vuot_chi_phi_thuc(chi_phi_usd: float) -> bool:
    """Chi phí THẬT sau khi gọi có vượt trần không — cưỡng chế, không phải ước."""
    if TRAN_CHI_PHI_TAI_LIEU_USD <= 0:
        return False
    return chi_phi_usd > TRAN_CHI_PHI_TAI_LIEU_USD


def han_muc_ngay(goi: str) -> int:
    """Số tài liệu một gói được đọc mỗi ngày — FR-004.

    Gói lạ rơi về `free`: một tên gói chưa biết không được mở rộng quyền, cùng
    hướng fail-closed với mọi cổng khác trong `bao_ve`.
    """
    return TAI_LIEU_NGAY.get(goi, TAI_LIEU_NGAY["free"])


def da_dung_hom_nay(engine: Engine, user_sub: str) -> int:
    """Số việc đọc đã tạo trong ngày, theo múi giờ hạn mức.

    Đếm cả việc HỎNG: một tệp hỏng vẫn tốn công đọc, và không đếm nó thì gửi
    tệp rác liên tục trở thành đường vòng qua hạn mức. Việc bị dừng vì chạm trần
    chi phí thì KHÔNG tính (FR-038) — đó là hệ thống từ chối, không phải người
    dùng tiêu lượt.

    Cùng nguyên tắc đó, `ly_do_hong` tiền tố `he_thong_` (fix round 2, task
    review — Minor #4: `ChuyenDoiKhongSanSang`, ví dụ thiếu LibreOffice hay
    quá tải chuyển đổi .doc) cũng KHÔNG tính: một máy chủ thiếu công cụ hay
    đang quá tải là lỗi của HỆ THỐNG, không phải người dùng gửi một tệp có vấn
    đề — tính vào hạn mức của họ là phạt người dùng cho một việc họ không gây
    ra và không sửa được bằng cách đổi tệp.

    `vuot_tran_so_trang` cũng KHÔNG tính (quyết định 2026-09-26): tài liệu vượt
    trần số trang bị từ chối lúc tải lên, trước khi tốn một lượt mô hình nào.

    Mọi miễn trừ trên chỉ dành cho việc KHÔNG giữ khuôn gốc: miễn trừ là "hệ
    thống từ chối, người dùng không nhận được gì", còn một tệp nằm lại trong
    `khuon_goc` là một tài liệu đã lưu (rút lại được, kể cả loại tổng quát).
    Không có điều kiện này thì mỗi tài khoản lưu được không giới hạn tệp mỗi
    ngày, và một lượt `doc-lai` chạm trần chi phí hoàn lại lượt của một tệp đã
    đếm. Lượt tải lên bị ước chi phí từ chối không lưu tệp
    (`routes_tai_lieu.tai_len`), nên nó vẫn được miễn đúng FR-038.
    """
    from src.services.bao_ve import moc_ngay

    with engine.connect() as c:
        return c.execute(
            text(
                "SELECT count(*) FROM viec_doc_tai_lieu "
                "WHERE user_sub = :u AND tao_luc >= :m "
                "AND (ly_do_hong IS NULL "
                "OR EXISTS (SELECT 1 FROM khuon_goc k WHERE k.viec_id = viec_doc_tai_lieu.id) OR "
                # `left(…, 9) <> 'he_thong_'` — KHÔNG `LIKE 'he_thong_%'` (fix
                # round 3, task review): `_` trong LIKE là ký tự đại diện MỘT
                # KÝ TỰ BẤT KỲ, không phải gạch dưới nghĩa đen, nên mẫu đó
                # khớp rộng hơn tiền tố thật (vd "heXthongY..." cũng khớp).
                # Vô hại hôm nay vì chưa có `ly_do_hong` nào mang hình dạng
                # đó, nhưng là một bẫy cho lần thêm giá trị kế tiếp. `left()`
                # so khớp CHUỖI, không có ký tự đại diện nào để hiểu lầm.
                "(ly_do_hong NOT IN ('vuot_tran_chi_phi', 'vuot_tran_so_trang') "
                "AND left(ly_do_hong, 9) <> 'he_thong_'))"
            ),
            {"u": user_sub, "m": moc_ngay()},
        ).scalar_one()


class VuotTran(Exception):  # noqa: N818
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

    `du_lieu` ở đây chỉ được dùng để tính dấu vân. Tệp tự nó được lưu ở
    đường khác, `luu_khuon_goc`, sau khi đã đọc được và nằm trong trần trang.
    """
    kiem_kich_thuoc(len(du_lieu))
    # Hash thẳng trên BYTES. `traces.dau_van_ban` nhận `str` vì nó dùng cho văn
    # bản người dùng dán; tài liệu ở đây là nhị phân, và `.decode(errors=replace)`
    # vừa tốn một bản sao vừa làm hai tệp khác nhau có thể trùng dấu vân.
    dau = f"sha256:{hashlib.sha256(du_lieu).hexdigest()} len={len(du_lieu)}"
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
    # Lý do hỏng chỉ sống cùng trạng thái `hong`: rút lại (`doc_lai`) là thử
    # lại được, và một lần thử lại thành công không được ra `xong` kèm lý do
    # hỏng của lần trước.
    #
    # `chi_phi_usd` CỘNG DỒN mọi lượt rút của việc (tải lên và mọi `doc-lai`):
    # ghi đè bằng lượt cuối là xoá khỏi sổ số tiền đã tiêu.
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE viec_doc_tai_lieu SET trang_thai = :s, cap_nhat_luc = now(), "
                "ly_do_hong = CASE WHEN :s = 'hong' THEN COALESCE(:r, ly_do_hong) END, "
                "so_trang = COALESCE(:p, so_trang), "
                "chi_phi_usd = chi_phi_usd + COALESCE(CAST(:c AS double precision), 0) "
                "WHERE id = :i AND user_sub = :u"
            ),
            {"s": trang_thai, "r": ly_do_hong, "p": so_trang, "c": chi_phi_usd, "i": viec_id, "u": user_sub},
        )


def nhan_rut_lai(engine: Engine, viec_id: str, user_sub: str, *, tra_phi: bool) -> bool:
    """Đưa việc về `dang_doc` để rút lại, trừ khi nó ĐANG đọc; `False` là đã có
    một lượt đang chạy.

    Kiểm và ghi là MỘT câu UPDATE có điều kiện chứ không phải đọc rồi ghi: hai
    lần bấm "rút lại" sát nhau thì Postgres khoá dòng, lần sau thấy `dang_doc`
    của lần trước và không khớp — không có lượt rút trả tiền thứ hai.

    `tra_phi` (lượt rút sẽ gọi mô hình) tốn một lượt FR-037 trong CÙNG câu đó:
    hết `TRAN_THU_LAI` lượt thì `VuotTran("thu_lai")` và dòng giữ nguyên.
    """
    tang = 1 if tra_phi else 0
    with engine.begin() as c:
        so_dong = c.execute(
            text(
                "UPDATE viec_doc_tai_lieu SET trang_thai = 'dang_doc', ly_do_hong = NULL, "
                "cap_nhat_luc = now(), so_lan_thu = so_lan_thu + :p "
                "WHERE id = :i AND user_sub = :u AND trang_thai <> 'dang_doc' "
                "AND (:p = 0 OR so_lan_thu < :t)"
            ),
            {"i": viec_id, "u": user_sub, "p": tang, "t": TRAN_THU_LAI},
        ).rowcount
        if so_dong == 1:
            return True
        da_thu = c.execute(
            text("SELECT so_lan_thu FROM viec_doc_tai_lieu WHERE id = :i AND user_sub = :u"),
            {"i": viec_id, "u": user_sub},
        ).scalar()
    if tra_phi and da_thu is not None and da_thu >= TRAN_THU_LAI:
        raise VuotTran("thu_lai", TRAN_THU_LAI, da_thu)
    return False


def dat_loai(engine: Engine, viec_id: str, user_sub: str, loai: str) -> None:
    """Ghi loại văn bản hệ thống đã nhận ra (hoặc người dùng đã chọn)."""
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE viec_doc_tai_lieu SET loai = :l, cap_nhat_luc = now() "
                "WHERE id = :i AND user_sub = :u"
            ),
            {"l": loai, "i": viec_id, "u": user_sub},
        )


def luu_du_kien(engine: Engine, viec_id: str, hoi_thoai_id: str, du_kien: list[dict]) -> int:
    """Ghi tập dữ kiện đã qua neo. Chỉ nhận dữ kiện CÓ neo hợp lệ.

    `nguon` lấy từ chính kết quả neo (`tai_lieu` hay `tai_lieu_ocr`), không phải
    từ chỗ người gọi nghĩ dữ kiện đến từ đâu: hạng bằng chứng do phép tra chuỗi
    quyết định, không do ý định.
    """
    if not du_kien:
        return 0
    with engine.connect() as c:
        # Cùng một tài liệu hỏi rút dữ kiện hai lần ra cùng bộ `khoa`. Bộ trường
        # là ĐỘNG (`hieu_tai_lieu`), nên không khai trước được một ràng buộc duy
        # nhất ở DB — chống trùng nằm ở đây.
        #
        # BỎ QUA khoá đã có, không ghi đè: một giá trị người dùng đã sửa thắng
        # bản mô hình vừa đọc lại (FR-012, FR-015). Muốn đọc lại một trường thì
        # xoá dòng đó — `xoa_luc` làm khoá ấy trống trở lại.
        da_co = {
            r[0]
            for r in c.execute(
                text("SELECT khoa FROM du_kien_tai_lieu WHERE viec_id = :v AND xoa_luc IS NULL"),
                {"v": viec_id},
            )
        }
    du_kien = [d for d in du_kien if d["key"] not in da_co]
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
            "ng": d.get("nguon") or "tai_lieu",
            "dt": d["neo"].do_tin,
        }
        for d in du_kien
    ]
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO du_kien_tai_lieu "
                "(viec_id, hoi_thoai_id, khoa, nhan, gia_tri, nguon, trich, chi_so_don_vi, trang, offset_dau, do_tin) "
                "VALUES (:v, :h, :k, :n, :g, :ng, :t, :c, :p, :o, :dt)"
            ),
            hang,
        )
    return len(hang)


# Biểu diễn văn bản đã đọc — quyết định 2026-09-16
# (`docs/decisions/2026-09-16-luu-bieu-dien-tai-lieu-theo-hoi-thoai.md`).
# Cột `don_vi` giữ CHỮ của tài liệu, nên nó không bao giờ đi cùng `SELECT *`:
# mỗi lần kéo nó ra là một lần nội dung của bên thứ ba đi qua dây mà không ai
# cần. Chỉ `don_vi_cua` đọc nó, và chỉ khi có người thật sự sắp neo vào nó.
_COT_VIEC = (
    "id, user_sub, hoi_thoai_id, ten_tep, dau_van_ban, so_byte, so_trang, loai, "
    "trang_thai, ly_do_hong, chi_phi_usd, so_lan_thu, tao_luc, cap_nhat_luc, mo_ta"
)


def _hang_dinh_dang(r: DinhDangChu) -> dict:
    """Một `DinhDangChu` → JSON. Bỏ mọi trường ĐANG Ở MẶC ĐỊNH: một run điển
    hình khai đúng một thuộc tính, và ghi đủ mười khoá cho từng run của một
    biểu mẫu vài nghìn run là nhân đôi cột `don_vi` để cất toàn số 0.

    `khai` thành mảng-cặp chứ không thành object: JSON không giữ thứ tự khoá
    như một hợp đồng, mà thứ tự ấy là thứ `_TEN_RPR` đã chốt — và một khoá
    lặp (`w:rPr` hỏng khai hai lần) sẽ bị object nuốt mất một.
    """
    ra: dict[str, Any] = {"dau": r.dau, "cuoi": r.cuoi}
    for ten in ("doan", "so", "dam", "nghieng", "gach", "co", "phong"):
        if v := getattr(r, ten):
            ra[ten] = v
    if r.khai:
        ra["khai"] = [list(k) for k in r.khai]
    return ra


def _dinh_dang_tu_hang(tho: Any) -> tuple[DinhDangChu, ...]:
    """JSON → `DinhDangChu`. Một dòng lưu TRƯỚC trường này (hoặc một dòng
    hỏng hình dạng) về `()` — "không biết định dạng gì", đúng mặc định của
    `DonViVanBan.dinh_dang`, chứ không đoán lại từ nội dung."""
    if not isinstance(tho, list):
        return ()
    ra: list[DinhDangChu] = []
    for r in tho:
        if not isinstance(r, dict):
            continue
        ra.append(
            DinhDangChu(
                dau=int(r.get("dau") or 0),
                cuoi=int(r.get("cuoi") or 0),
                doan=int(r.get("doan") or 0),
                so=int(r.get("so") or 0),
                dam=bool(r.get("dam")),
                nghieng=bool(r.get("nghieng")),
                gach=bool(r.get("gach")),
                co=int(r.get("co") or 0),
                phong=str(r.get("phong") or ""),
                khai=tuple((str(k[0]), str(k[1])) for k in (r.get("khai") or ()) if len(k) == 2),
            )
        )
    return tuple(ra)


_TRUONG_GC = ("doan", "truoc", "sau", "dong", "trai", "phai", "dau_dong", "treo")


def _hang_gian_cach(g: GianCach) -> dict:
    """Một `GianCach` → JSON. Cùng luật `_hang_dinh_dang`: bỏ mọi trường đang ở
    MẶC ĐỊNH, vì một đoạn điển hình khai đúng một hai thuộc tính và ghi đủ
    mười ba khoá cho từng đoạn của một biểu mẫu vài trăm đoạn là cất toàn số 0.

    `moc`/`khai` thành mảng-cặp chứ không object: cùng lý do `DinhDangChu.khai`
    — JSON không giữ thứ tự khoá như một hợp đồng, mà thứ tự ấy chính là thứ
    `_moc_tab`/`_gian_cach_doan` đã chốt.
    """
    ra: dict[str, Any] = {}
    for ten in _TRUONG_GC:
        if v := getattr(g, ten):
            ra[ten] = v
    if g.luat_dong:
        ra["luat_dong"] = g.luat_dong
    if g.moc:
        ra["moc"] = [[m.val, m.pos, m.leader] for m in g.moc]
    if g.tab:
        ra["tab"] = list(g.tab)
    if g.khai:
        ra["khai"] = [list(k) for k in g.khai]
    return ra


def _gian_cach_tu_hang(tho: Any) -> tuple[GianCach, ...]:
    """JSON → `GianCach`. Một dòng lưu TRƯỚC trường này (hoặc một dòng hỏng
    hình dạng) về `()` — "không biết giãn cách gì", đúng mặc định của
    `DonViVanBan.gian_cach`, chứ không đoán lại từ nội dung."""
    if not isinstance(tho, list):
        return ()
    ra: list[GianCach] = []
    for g in tho:
        if not isinstance(g, dict):
            continue
        ra.append(
            GianCach(
                **{ten: int(g.get(ten) or 0) for ten in _TRUONG_GC},
                luat_dong=str(g.get("luat_dong") or ""),
                moc=tuple(
                    MocTab(val=str(m[0]), pos=int(m[1]), leader=str(m[2]))
                    for m in (g.get("moc") or ())
                    if len(m) == 3
                ),
                tab=tuple(int(t) for t in (g.get("tab") or ())),
                khai=tuple((str(k[0]), str(k[1])) for k in (g.get("khai") or ()) if len(k) == 2),
            )
        )
    return tuple(ra)


def _canh_tu_hang(tho: Any) -> tuple[tuple[str, str, str], ...]:
    """JSON → `DonViVanBan.bang_vien_canh`/`o_vien_canh`.

    Bỏ RIÊNG phần tử sai hình dạng, không bỏ cả dãy: một cạnh hỏng vẫn để năm
    cạnh còn lại vẽ đúng, và `hieu_tai_lieu._vien_o_bang` mới là chỗ quyết
    định lùi cả bảng về nét đều khi cái nó nhận không dùng được.
    """
    if not isinstance(tho, list):
        return ()
    return tuple((str(c[0]), str(c[1]), str(c[2])) for c in tho if isinstance(c, list) and len(c) == 3)


def _hang_anh(a: AnhTaiLieu) -> dict:
    """Một `AnhTaiLieu` → JSON. Chỉ MÔ TẢ; bytes đi đường `luu_anh` bên dưới.

    Giữ đủ sáu trường kể cả khi ở mặc định (khác `_hang_dinh_dang`/
    `_hang_gian_cach`, vốn bỏ mặc định): một tài liệu điển hình có 0–3 ảnh,
    nên phép bỏ ấy tiết kiệm được vài chục byte trong khi làm mất khả năng
    đọc thẳng một dòng để biết ảnh đó khai gì.
    """
    return {
        "phan": a.phan,
        "kieu": a.kieu,
        "rong": a.rong,
        "cao": a.cao,
        "vung": a.vung,
        "thu_tu": a.thu_tu,
    }


def _anh_tu_hang(tho: Any) -> tuple[AnhTaiLieu, ...]:
    """JSON → `DonViVanBan.anh`. Một dòng lưu TRƯỚC trường này (hoặc một phần
    tử sai hình dạng) về `()` — "tài liệu này không có ảnh nào", đúng mặc định
    của dataclass.

    Bỏ RIÊNG phần tử không có `phan`: một mô tả ảnh không nói được nó là ảnh
    nào thì không tra ra bytes, và vẽ một khung rỗng ở chỗ đó tệ hơn không vẽ
    gì — cùng luật fail-closed `_canh_tu_hang` đã theo.
    """
    if not isinstance(tho, list):
        return ()
    ra: list[AnhTaiLieu] = []
    for a in tho:
        if not isinstance(a, dict) or not a.get("phan"):
            continue
        try:
            ra.append(
                AnhTaiLieu(
                    phan=str(a["phan"]),
                    kieu=str(a.get("kieu") or ""),
                    rong=int(a.get("rong") or 0),
                    cao=int(a.get("cao") or 0),
                    vung=str(a.get("vung") or "than"),
                    thu_tu=int(a.get("thu_tu") or 0),
                )
            )
        except (TypeError, ValueError):
            continue
    return tuple(ra)


def _le_tu_hang(tho: Any) -> tuple[tuple[str, int], ...]:
    """JSON → `DonViVanBan.le_trang`. Số đọc không ra bỏ RIÊNG thuộc tính đó,
    cùng luật `_le_trang` lúc đọc tệp."""
    if not isinstance(tho, list):
        return ()
    ra: list[tuple[str, int]] = []
    for x in tho:
        if not isinstance(x, list) or len(x) != 2:
            continue
        try:
            ra.append((str(x[0]), int(x[1])))
        except (TypeError, ValueError):
            continue
    return tuple(ra)


def _hang_cho_trong(c: ChoTrong) -> dict:
    """Một `ChoTrong` → JSON, đúng bộ khoá hợp đồng của TỪNG định dạng: PDF
    (có `hop`) mang `hop`/`co_chu`, DOCX mang `doan`/`dau`/`cuoi`."""
    if c.hop:
        return {"so": c.so, "kieu": c.kieu, "hop": list(c.hop), "co_chu": c.co_chu, "nhan": c.nhan}
    return {"so": c.so, "kieu": c.kieu, "doan": c.doan, "dau": c.dau, "cuoi": c.cuoi, "nhan": c.nhan}


def _so_tu_nhien(x: Any) -> bool:
    # `bool` là con của `int` trong Python; `True` không phải chỉ số.
    return type(x) is int and x >= 0


def _dia_chi_tu_hang(tho: Any) -> DiaChi | None:
    """JSON → `DonViVanBan.dia_chi`. Sai hình dạng → `None` ("không có địa
    chỉ"): bộ áp đi theo một địa chỉ hỏng là sửa nhầm chỗ, còn không có địa chỉ
    thì đơn vị lùi về đường HTML — hỏng an toàn."""
    if not isinstance(tho, dict):
        return None
    phan, chi_muc = tho.get("phan"), tho.get("chi_muc")
    if not isinstance(phan, str) or not phan or not isinstance(chi_muc, list) or not chi_muc:
        return None
    if not all(_so_tu_nhien(i) for i in chi_muc):
        return None
    return DiaChi(phan=phan, chi_muc=tuple(chi_muc))


def _hop_tu_hang(tho: Any) -> tuple[float, float, float, float] | None:
    """JSON → một hộp `(x0, y0, x1, y1)`; sai hình dạng → `None`."""
    if not isinstance(tho, list) or len(tho) != 4 or not all(type(v) in (int, float) for v in tho):
        return None
    x0, y0, x1, y1 = (float(v) for v in tho)
    return (x0, y0, x1, y1) if x0 <= x1 and y0 <= y1 else None


def _cho_trong_tu_hang(tho: Any) -> tuple[ChoTrong, ...]:
    """JSON → `DonViVanBan.cho_trong`. Bỏ RIÊNG phần tử sai hình dạng, cùng
    luật `_canh_tu_hang`: phép sửa trỏ theo `so`, không theo vị trí trong dãy,
    nên một chỗ hỏng không làm lệch chỗ khác — phép sửa trỏ vào chỗ đã bỏ thì
    bộ áp báo "không hợp lệ" chứ không đoán."""
    if not isinstance(tho, list):
        return ()
    ra: list[ChoTrong] = []
    for c in tho:
        if not isinstance(c, dict) or not _so_tu_nhien(c.get("so")) or c.get("kieu") not in ("cham", "tab", "o"):
            continue
        nhan = c["nhan"] if isinstance(c.get("nhan"), str) else ""
        if "hop" in c:
            hop, co = _hop_tu_hang(c["hop"]), c.get("co_chu")
            if hop is None or c["kieu"] != "cham" or type(co) not in (int, float) or co <= 0:
                continue
            ra.append(ChoTrong(so=c["so"], kieu="cham", nhan=nhan, hop=hop, co_chu=float(co)))
            continue
        doan, dau, cuoi = c.get("doan"), c.get("dau"), c.get("cuoi")
        if not (_so_tu_nhien(doan) and _so_tu_nhien(dau) and _so_tu_nhien(cuoi)):
            continue
        # `o` (ô rỗng, G5): đoạn đầu của ô, không ký tự nào — `doan`/`dau`/`cuoi` 0.
        if (c["kieu"] == "cham" and dau >= cuoi) or (c["kieu"] == "tab" and dau != cuoi):
            continue
        if c["kieu"] == "o" and (doan, dau, cuoi) != (0, 0, 0):
            continue
        ra.append(ChoTrong(so=c["so"], kieu=c["kieu"], nhan=nhan, doan=doan, dau=dau, cuoi=cuoi))
    return tuple(ra)


def _doan_chu_tu_hang(tho: Any) -> tuple[str, ...]:
    """JSON → `DonViVanBan.doan_chu`. Cả dãy hoặc không gì: một phần tử hỏng làm
    lệch chỉ số `doan` của mọi đoạn sau, nên đọc ra rỗng (prompt lùi về danh
    sách chỗ trống, `thay` theo đoạn bị bỏ) chứ không đoán."""
    if not isinstance(tho, list) or not all(isinstance(s, str) for s in tho):
        return ()
    return tuple(tho)


def _hang_don_vi(d: DonViVanBan) -> dict:
    return {
        "chi_so": d.chi_so,
        "trang": d.trang,
        "offset_dau": d.offset_dau,
        "noi_dung": d.noi_dung,
        "nguon_chu": str(d.nguon_chu),
        "do_tin": d.do_tin,
        "vung": d.vung,
        "bang": list(d.bang) if d.bang else None,
        # Phase 9 U5 — thiếu khoá này thì `don_vi_cua` đọc lại luôn ra mặc
        # định `trai` của dataclass, bất kể `doc_tai_lieu.doc()` đã đọc đúng
        # `giua`/`phai` từ tệp: căn lề bị mất NGAY TẠI ranh giới lưu/đọc này,
        # không phải ở tầng đối chiếu (`hieu_tai_lieu._can_le_theo_dong`) —
        # đo được trên draft thật, mọi khối ra `can_le: "trai"` dù bảng đọc
        # trực tiếp từ tệp đã có `giua` cho quốc hiệu/tiêu ngữ.
        "can_le": d.can_le,
        # Phase 11 R1/R6 — cùng lý do can_le ở trên: thiếu hai khoá này thì
        # `don_vi_cua` đọc lại ra mặc định (nhịp 1, tỉ lệ rỗng) của dataclass,
        # mất tỉ lệ cột/nhịp gộp NGAY tại ranh giới lưu/đọc, dù `doc_tai_lieu.
        # doc()` đã đọc đúng từ `w:tblGrid`/`w:gridSpan`.
        "bang_nhip": d.bang_nhip,
        "bang_ti_le": list(d.bang_ti_le) if d.bang_ti_le else [],
        # Cùng lý do hai khoá trên: viền (`w:tblBorders`) và chiều cao hàng
        # (`w:trHeight`) đã đọc đúng từ tệp sẽ mất ngay tại ranh giới lưu/đọc
        # này nếu không ghi ra — và một khối ký không viền sẽ mọc lại viền.
        "bang_vien": d.bang_vien,
        "bang_cao": d.bang_cao,
        # Cùng lý do: viền TỪNG CẠNH (`w:tblBorders`/`w:tcBorders`), luật
        # chiều cao hàng (`@w:hRule`) và lề trang (`w:pgMar`) đã đọc đúng từ
        # tệp sẽ mất ngay tại ranh giới này nếu không ghi ra — và một biểu mẫu
        # chỉ kẻ khung ngoài sẽ dựng lại thành một cái lưới kẻ đủ mọi ô.
        "bang_cao_luat": d.bang_cao_luat,
        "bang_vien_canh": [list(c) for c in d.bang_vien_canh],
        "o_vien_canh": [list(c) for c in d.o_vien_canh],
        "le_trang": [list(x) for x in d.le_trang],
        # Cùng lý do mọi khoá trên: định dạng chữ (`w:rPr`) đã đọc đúng từ tệp
        # mất ngay tại ranh giới lưu/đọc này nếu không ghi ra — và một biểu
        # mẫu in đậm quốc hiệu sẽ dựng lại thành chữ thường.
        "dinh_dang": [_hang_dinh_dang(r) for r in d.dinh_dang],
        # Cùng lý do mọi khoá trên: giãn cách/thụt lề/mốc tab (`w:spacing`,
        # `w:ind`, `w:tabs`) đã đọc đúng từ tệp mất ngay tại ranh giới lưu/đọc
        # này nếu không ghi ra — và dòng "……" để điền tay của một biểu mẫu sẽ
        # dựng lại thành một dòng cụt.
        "gian_cach": [_hang_gian_cach(g) for g in d.gian_cach],
        # Cùng lý do mọi khoá trên: MÔ TẢ ảnh đã tách (`a:blip`/`v:imagedata`
        # giải qua `.rels`) mất ngay tại ranh giới lưu/đọc này nếu không ghi ra
        # — và logo letterhead sẽ biến mất khỏi bản dựng lại dù bytes của nó
        # đã nằm yên trong `anh_tai_lieu`.
        "anh": [_hang_anh(a) for a in d.anh],
        # P2b — khoá TUỲ CHỌN, chỉ có mặt khi nguồn khai (hợp đồng "Đơn vị văn
        # bản additions"): địa chỉ OOXML, chỗ trống, hộp dòng PDF. Cùng lý do mọi
        # khoá trên: thiếu ở đây là mất ngay tại ranh giới lưu/đọc, và bộ áp
        # (P3a/P3b) sẽ không còn biết điền vào đâu.
        **({"dia_chi": {"phan": d.dia_chi.phan, "chi_muc": list(d.dia_chi.chi_muc)}} if d.dia_chi else {}),
        **({"cho_trong": [_hang_cho_trong(c) for c in d.cho_trong]} if d.cho_trong else {}),
        **({"hop": list(d.hop)} if d.hop else {}),
        **({"doan_chu": list(d.doan_chu)} if d.doan_chu else {}),
    }


def luu_don_vi(engine: Engine, viec_id: str, don_vi: list[DonViVanBan]) -> None:
    """Ghi biểu diễn đã đọc vào chính dòng việc đọc.

    Ghi cho MỌI tài liệu đọc được, kể cả tài liệu không nhận ra loại — đó là
    toàn bộ điểm của quyết định: lượt hỏi kế tiếp phải còn thứ để neo vào, chứ
    không phải chỉ 29 loại có checklist mới đi tiếp được.
    """
    with engine.begin() as c:
        c.execute(
            text("UPDATE viec_doc_tai_lieu SET don_vi = CAST(:d AS jsonb) WHERE id = :i"),
            {"d": json.dumps([_hang_don_vi(d) for d in don_vi], ensure_ascii=False), "i": viec_id},
        )


def luu_anh(engine: Engine, viec_id: str, anh_byte: dict[str, tuple[str, bytes]]) -> int:
    """Ghi bytes ảnh đã tách vào `anh_tai_lieu` (migration 035), trả số dòng ghi.

    Gọi NGAY cạnh `luu_don_vi` và chỉ ở đó: mô tả ảnh nằm trong `don_vi` chỉ
    dựng lại được khi bytes của nó có mặt, nên hai phép ghi phải đi cùng nhau
    hoặc cùng vắng.

    `ON CONFLICT DO NOTHING` chứ không ghi đè: khoá `(viec_id, phan)` là danh
    tính của đúng một ảnh trong đúng một tệp, nên một lần ghi thứ hai là cùng
    bytes ấy — ghi đè chỉ tốn một lượt viết. Cũng là thứ làm cho một lần tải
    lại/thử lại cùng tài liệu không nhân đôi con dấu.

    Tài liệu không có ảnh nào KHÔNG chạm DB: phần lớn biểu mẫu rơi vào đây (đo
    trên tám biểu mẫu thật của chủ dự án: 2/8 có ảnh).
    """
    if not anh_byte:
        return 0
    hang = [
        {"v": viec_id, "p": phan, "k": kieu, "s": len(du_lieu), "d": du_lieu}
        for phan, (kieu, du_lieu) in sorted(anh_byte.items())
    ]
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO anh_tai_lieu (viec_id, phan, kieu, so_byte, du_lieu) "
                "VALUES (:v, :p, :k, :s, :d) ON CONFLICT (viec_id, phan) DO NOTHING"
            ),
            hang,
        )
    return len(hang)


def luu_khuon_goc(engine: Engine, viec_id: str, dinh_dang: str, noi_dung: bytes, kho: list) -> None:
    """Ghi khuôn gốc của một việc đọc vào `khuon_goc` (migration 036).

    Gọi cạnh `luu_don_vi`/`luu_anh`, sau khi tệp đã đọc được và đã qua trần
    số trang — một tệp bị từ chối không để lại byte nào. `so_trang` là
    `len(kho)`: một nguồn sự thật, và `ck_khuon_goc_kho` khoá hai cột bằng nhau.
    """
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO khuon_goc (viec_id, dinh_dang, noi_dung, so_byte, so_trang, kho) "
                "VALUES (:v, :d, :n, :s, :t, CAST(:k AS jsonb))"
            ),
            {"v": viec_id, "d": dinh_dang, "n": noi_dung, "s": len(noi_dung), "t": len(kho), "k": json.dumps(kho)},
        )


def khuon_goc_cua(engine: Engine, viec_id: str, user_sub: str) -> dict[str, Any] | None:
    """`{dinh_dang, noi_dung, so_trang, kho, don_vi}` của một việc, hoặc `None`
    khi không có (ảnh, tài liệu trước 2026-09-26) hoặc không phải của mình.
    `don_vi` (mảng JSON đã lưu) cho khoá `o` của `GET …/trang`.

    Chủ sở hữu lọc bằng JOIN sang `viec_doc_tai_lieu` ở tầng dữ liệu, cùng
    khuôn `anh_cua`: một `viec_id` của người khác ra `None` ở ĐÂY, và tầng API
    trả 404 y như một việc không có thật.
    """
    with engine.connect() as c:
        r = (
            c.execute(
                text(
                    "SELECT k.dinh_dang, k.noi_dung, k.so_trang, k.kho, v.don_vi FROM khuon_goc k "
                    "JOIN viec_doc_tai_lieu v ON v.id = k.viec_id "
                    "WHERE k.viec_id = :i AND v.user_sub = :u"
                ),
                {"i": viec_id, "u": user_sub},
            )
            .mappings()
            .first()
        )
    return {**dict(r), "noi_dung": bytes(r["noi_dung"])} if r else None


def khuon_goc_nhe(engine: Engine, viec_id: str, user_sub: str) -> dict[str, Any] | None:
    """`{dinh_dang, so_trang}` — `khuon_goc_cua` KHÔNG kèm bytes. Graph hỏi hàm này
    mỗi lượt đọc tài liệu chỉ để biết có khuôn gốc không; kéo tới 20 MB qua dây
    cho một câu trả lời có/không là việc không ai cần. Cùng luật chủ sở hữu."""
    with engine.connect() as c:
        r = (
            c.execute(
                text(
                    "SELECT k.dinh_dang, k.so_trang FROM khuon_goc k "
                    "JOIN viec_doc_tai_lieu v ON v.id = k.viec_id "
                    "WHERE k.viec_id = :i AND v.user_sub = :u"
                ),
                {"i": viec_id, "u": user_sub},
            )
            .mappings()
            .first()
        )
    return dict(r) if r else None


def anh_cua(engine: Engine, viec_id: str, user_sub: str, phan: str) -> tuple[str, bytes] | None:
    """`(kiểu MIME, bytes)` của MỘT ảnh, hoặc `None` khi không có hoặc không
    phải của mình.

    Lọc theo `user_sub` bằng JOIN sang `viec_doc_tai_lieu` — bảng ảnh không có
    cột chủ sở hữu riêng (xem migration 035). Một `viec_id` của người khác trả
    `None` ở ĐÂY, tầng dữ liệu, không phải ở một phép kiểm thứ hai tại tầng
    API: cùng nguyên tắc `don_vi_cua`/`ban_thao`/`hoi_thoai` đã theo, và là thứ
    làm cho con dấu của một người không bao giờ rời khỏi tài khoản đã tải nó
    lên (quyết định 2026-09-18, phần "media là dữ liệu cá nhân của bên thứ ba").
    """
    with engine.connect() as c:
        r = c.execute(
            text(
                "SELECT a.kieu, a.du_lieu FROM anh_tai_lieu a "
                "JOIN viec_doc_tai_lieu v ON v.id = a.viec_id "
                "WHERE a.viec_id = :i AND a.phan = :p AND v.user_sub = :u"
            ),
            {"i": viec_id, "p": phan, "u": user_sub},
        ).first()
    return (str(r[0]), bytes(r[1])) if r else None


def don_vi_cua(engine: Engine, viec_id: str, user_sub: str) -> list[DonViVanBan] | None:
    """Biểu diễn đã đọc của một việc, hoặc `None` khi không có hoặc không phải của mình.

    `None` nói "không có tài liệu nào như vậy cho bạn" và `[]` nói "có, nhưng
    chưa đọc ra đơn vị nào" (dòng cũ trước migration 031). Gộp hai ca lại thì
    người gọi hết đường phân biệt 404 với một tài liệu rỗng.
    """
    with engine.connect() as c:
        r = c.execute(
            text("SELECT don_vi FROM viec_doc_tai_lieu WHERE id = :i AND user_sub = :u"),
            {"i": viec_id, "u": user_sub},
        ).first()
    if r is None:
        return None
    return [
        DonViVanBan(
            chi_so=d["chi_so"],
            trang=d["trang"],
            offset_dau=d["offset_dau"],
            noi_dung=d["noi_dung"],
            nguon_chu=NguonChu(d.get("nguon_chu") or NguonChu.lop_chu),
            do_tin=d.get("do_tin"),
            vung=d.get("vung") or "than",
            # JSON không có tuple. Trả về list thì `DonViVanBan` hết bằng chính
            # nó sau một vòng lưu–đọc, và phép so sánh hỏng im lặng.
            bang=tuple(d["bang"]) if d.get("bang") else None,
            # Phase 9 U5 — `.get(...) or "trai"` để một dòng lưu TRƯỚC phase
            # này (chưa từng có khoá `can_le`) vẫn đọc ra được, đúng mặc định
            # `DonViVanBan.can_le` — không suy đoán gì hơn những gì đã lưu.
            can_le=d.get("can_le") or "trai",
            # Phase 11 R1/R6 — cùng lý do can_le ở trên: một dòng lưu TRƯỚC
            # phase này không có hai khoá này, về đúng mặc định dataclass.
            bang_nhip=d.get("bang_nhip") or 1,
            bang_ti_le=tuple(d.get("bang_ti_le") or ()),
            # Một dòng lưu TRƯỚC bản vá viền không có hai khoá này: về đúng
            # mặc định dataclass (`bang_vien=True` — vẽ viền như trước bản vá,
            # xem `DonViVanBan.bang_vien`), không suy đoán lại từ nội dung.
            bang_vien=bool(d.get("bang_vien", True)),
            bang_cao=int(d.get("bang_cao") or 0),
            # Một dòng lưu TRƯỚC bản vá viền-từng-cạnh không có bốn khoá này:
            # về đúng mặc định dataclass (rỗng / `""`), tức ba nơi vẽ lùi đúng
            # về nét đều của `bang_vien` và lề mặc định của chính chúng.
            bang_cao_luat=str(d.get("bang_cao_luat") or ""),
            bang_vien_canh=_canh_tu_hang(d.get("bang_vien_canh")),
            o_vien_canh=_canh_tu_hang(d.get("o_vien_canh")),
            le_trang=_le_tu_hang(d.get("le_trang")),
            dinh_dang=_dinh_dang_tu_hang(d.get("dinh_dang")),
            gian_cach=_gian_cach_tu_hang(d.get("gian_cach")),
            anh=_anh_tu_hang(d.get("anh")),
            dia_chi=_dia_chi_tu_hang(d.get("dia_chi")),
            cho_trong=_cho_trong_tu_hang(d.get("cho_trong")),
            hop=_hop_tu_hang(d.get("hop")),
            doan_chu=_doan_chu_tu_hang(d.get("doan_chu")),
        )
        for d in (r[0] or [])
    ]


def tai_lieu_cua_hoi_thoai(engine: Engine, hoi_thoai_id: str, user_sub: str) -> list[dict]:
    """Những tài liệu của cuộc hội thoại còn neo được, mới nhất trước.

    Chỉ dòng `xong` và CÓ `don_vi`: một việc đang đọc hay đã hỏng không có gì
    để hỏi, và đưa nó vào danh sách chỉ làm mô hình nhắc tới một tài liệu nó
    không đọc được. `co_ocr` tính bằng phép chứa của jsonb nên nội dung tài
    liệu không rời khỏi Postgres chỉ để đếm một cờ.
    """
    with engine.connect() as c:
        return [
            {**dict(r), "id": str(r["id"])}
            for r in c.execute(
                text(
                    "SELECT id, ten_tep, so_trang, loai, mo_ta, "
                    "       jsonb_array_length(don_vi) AS so_don_vi, "
                    "       don_vi @> '[{\"nguon_chu\": \"ocr\"}]' AS co_ocr "
                    "FROM viec_doc_tai_lieu "
                    "WHERE hoi_thoai_id = :h AND user_sub = :u "
                    "      AND trang_thai = 'xong' AND don_vi IS NOT NULL "
                    "ORDER BY tao_luc DESC"
                ),
                {"h": hoi_thoai_id, "u": user_sub},
            ).mappings()
        ]


def lay_viec(engine: Engine, viec_id: str, user_sub: str) -> dict[str, Any] | None:
    with engine.connect() as c:
        r = (
            c.execute(
                text(
                    f"SELECT {_COT_VIEC}, COALESCE(jsonb_array_length(don_vi), 0) AS so_don_vi, "
                    "EXISTS (SELECT 1 FROM khuon_goc k WHERE k.viec_id = viec_doc_tai_lieu.id) AS co_khuon_goc "
                    "FROM viec_doc_tai_lieu WHERE id = :i AND user_sub = :u"
                ),
                {"i": viec_id, "u": user_sub},
            )
            .mappings()
            .first()
        )
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
    dọn mà vẫn giữ cuộc hội thoại — và, từ 2026-09-16, cũng là đường
    `routes_hoi_thoai.xoa` gọi: xoá MỀM một cuộc hội thoại không làm cascade
    nổ, nên nếu không gọi ở đây thì biểu diễn tài liệu ở lại vô thời hạn.

    Xoá cả dòng chứ không chỉ rỗng hoá `don_vi`/`mo_ta`: dòng đi thì biểu diễn
    đi cùng, và một cột được nulled trên một dòng vẫn còn sống là một thứ nữa
    phải nhớ dọn ở lần sau.
    """
    with engine.begin() as c:
        return c.execute(
            text(
                "DELETE FROM viec_doc_tai_lieu WHERE hoi_thoai_id = :h AND user_sub = :u"
            ),
            {"h": hoi_thoai_id, "u": user_sub},
        ).rowcount
