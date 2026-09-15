"""Neo một dữ kiện về đoạn trích trong tài liệu (spec 2026-09-15 §FR-007..FR-010).

Đây là chỗ đóng góp trung tâm của KLAW được mở sang một loại nguồn mới. Với
trích dẫn điều luật, tính hợp lệ là phép tra bảng trên `provisions` chứ không
phải suy luận của mô hình. Với dữ kiện tài liệu, tính hợp lệ là phép tra chuỗi
trên chính văn bản vừa đọc — cùng một nguyên tắc, cùng một hàm chuẩn hoá.

`normalize` được **nhập lại** từ `verify_tier1`, không viết bản thứ hai. Hai hàm
chuẩn hoá song song trong một hệ là một lỗ hổng chờ ngày nở: bên nới hơn sẽ đóng
dấu "đã kiểm chứng" cho đúng thứ bên kia loại, và không ai thấy cho tới khi một
con số sai đi vào một lá đơn.
"""

from dataclasses import dataclass
from enum import StrEnum

from src.agents.nodes.verify_tier1 import QUOTE_TOI_THIEU, normalize
from src.services.doc_tai_lieu import DonViVanBan

__all__ = ["LyDoNeo", "Neo", "loc_co_neo", "normalize", "xac_minh"]


class LyDoNeo(StrEnum):
    """Ba chế độ hỏng, ba mã — cùng lý do `Tier1Reason` không gộp nhãn.

    "Mô hình quên trích", "trích một mẩu quá ngắn để định danh" và "viết lại nội
    dung rồi gọi đó là trích dẫn" đòi ba cách sửa khác nhau ở prompt. Gộp lại
    thành "không hợp lệ" là vứt đi phần dữ liệu có giá trị nhất của chương đánh
    giá.
    """

    ok = "ok"
    trich_rong = "trich_rong"
    trich_qua_ngan = "trich_qua_ngan"
    trich_khong_khop = "trich_khong_khop"


@dataclass(frozen=True)
class Neo:
    """Bằng chứng cho một dữ kiện, hoặc lý do nó không có bằng chứng."""

    ly_do: LyDoNeo
    chi_so_don_vi: int | None = None
    trang: int | None = None
    offset_dau: int | None = None


def xac_minh(trich: str, don_vi: list[DonViVanBan]) -> Neo:
    """Tra `trich` trong `don_vi`. Hàm thuần: không LLM, không I/O, không DB.

    So với TỪNG đơn vị một, không nối danh sách thành một chuỗi rồi so. Nối lại
    tạo ra những vết ghép không có trong tài liệu, và một đoạn trích vắt qua
    ranh giới hai ô bảng sẽ khớp dù nó không nguyên văn ở bất kỳ đâu.
    """
    q = normalize(trich)
    if not q:
        return Neo(LyDoNeo.trich_rong)
    if len(q) < QUOTE_TOI_THIEU:
        # Một mẩu quá ngắn khớp được ở quá nhiều chỗ, nên nó không định danh
        # được vị trí nào cả. Vẫn là tra chuỗi, chỉ là tra chuỗi vô nghĩa.
        return Neo(LyDoNeo.trich_qua_ngan)

    for d in don_vi:
        if q in normalize(d.noi_dung):
            return Neo(LyDoNeo.ok, chi_so_don_vi=d.chi_so, trang=d.trang, offset_dau=d.offset_dau)
    return Neo(LyDoNeo.trich_khong_khop)


def loc_co_neo(
    facts: list[dict], don_vi: list[DonViVanBan]
) -> tuple[list[dict], list[dict]]:
    """Chia dữ kiện thành (giữ, bỏ) theo kết quả neo — FR-007.

    Dữ kiện bị bỏ KHÔNG bao giờ đi tiếp ra giao diện, nhưng vẫn được trả về để
    ghi vào `traces`: tỉ lệ bỏ tách theo từng lý do là số liệu đánh giá, y hệt
    tỉ lệ loại của tầng 1.
    """
    giu: list[dict] = []
    bo: list[dict] = []
    for f in facts:
        neo = xac_minh(str(f.get("trich") or ""), don_vi)
        ban_ghi = {**f, "neo": neo}
        (giu if neo.ly_do is LyDoNeo.ok else bo).append(ban_ghi)
    return giu, bo
