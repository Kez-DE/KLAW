"""`GET /van-ban/{doc_id}/hieu-luc` — phán quyết hiệu lực hai cấp (Pha 2).

Đây là chỗ DUY NHẤT giao diện được phép lấy nhãn hiệu lực, nên nó là chỗ duy
nhất phải bảo đảm nhãn đó không phải `documents.tinh_trang`.

`kiem-ke-fe-lovable.md`: FE Lovable render `tinh_trang` thô ở 11 vị trí, và bộ
lọc mặc định của nó (`tinhTrang: ["Còn hiệu lực"]`) GIẤU ĐI đúng bốn nghị định
lương tối thiểu mà KLAW phát hiện là đã bị thay — CSDL quốc gia vẫn đánh cả bốn
là `CHL`. Không endpoint nào trong file này trả `tinh_trang`; nó không nằm
trong model, không nằm trong câu SQL, và có một test quét cả response.

Hai cấp, vì bằng chứng có ở hai cấp:
  * VĂN BẢN — `effectivity.danh_gia_theo_id` (Mức 1 ngày hết hiệu lực, Mức 2 đồ
    thị quan hệ, Mức 3 `HHL1P`).
  * ĐIỀU KHOẢN — `effectivity.ap_sua_doi` trên `sua_doi_dieu_khoan` (Mức 4,
    nguồn Công báo/VBHN). Đây là tầng biến nhãn mù "hết hiệu lực một phần"
    thành "Khoản 1 Điều 139 bị sửa bởi 113/2025/QH15 từ 01/7/2026".

Không LLM, không embedding ⇒ không cổng `cong_bao_ve` (endpoint đọc thuần).
"""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from src.config import as_of_hieu_luc
from src.models.schemas import (
    DieuKhoanHieuLucOut,
    HieuLucOut,
    SuaBoiOut,
    VanBanHieuLucResponse,
)
from src.services.db import get_engine
from src.services.effectivity import (
    Effectivity,
    ap_sua_doi,
    danh_gia_theo_id,
    nap_sua_doi_theo_van_ban,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# CỐ Ý không chọn `tinh_trang`: một cột không được đọc thì không có đường nào rò
# ra response. Cùng kỷ luật với `VanBanHieuLucResponse` (không có field đó).
_SQL_DOC = text("SELECT id, so_ky_hieu, ten FROM documents WHERE id = :doc_id")


def _ra(e: Effectivity) -> HieuLucOut:
    return HieuLucOut(verdict=e.verdict.value, tin_cay=e.tin_cay, ly_do=e.ly_do)


def _hieu_luc_sync(doc_id: str, as_of: date) -> VanBanHieuLucResponse:
    engine = get_engine()
    with engine.connect() as c:
        doc = c.execute(_SQL_DOC, {"doc_id": doc_id}).mappings().one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"văn bản '{doc_id}' không tồn tại")

    goc = danh_gia_theo_id(engine, doc_id, as_of)

    # `ap_sua_doi(goc, ...)` chứ không một phán quyết dựng riêng: Mức 4 là một
    # LỚP PHỦ làm phán quyết cấp văn bản CỤ THỂ hơn, không phải một cơ chế thứ
    # hai chạy song song. Nó cũng tự tôn trọng `_KHOA_O_CAP_VAN_BAN` — một Điều
    # của văn bản đã bị thay thế toàn bộ thì đã chết, bất kể footnote nói gì.
    dieu_khoan = [
        DieuKhoanHieuLucOut(
            provision_id=p["provision_id"], duong_dan=p["duong_dan"], cap=p["cap"],
            so_hieu_cap=p["so_hieu_cap"], tieu_de=p["tieu_de"],
            hieu_luc=_ra(ap_sua_doi(goc, ban_ghi, as_of)),
            sua_boi=[
                SuaBoiOut(
                    vi_tri=b["vi_tri"], so_ky_hieu=b["sua_boi_so_ky_hieu"],
                    duong_dan=b["sua_boi_duong_dan"], tu_ngay=b["tu_ngay"],
                    nguon=b["nguon"], do_tin_cay=b["do_tin_cay"],
                )
                for b in ban_ghi
            ],
        )
        for p, ban_ghi in nap_sua_doi_theo_van_ban(engine, doc_id)
    ]

    return VanBanHieuLucResponse(
        doc_id=doc["id"], so_ky_hieu=doc["so_ky_hieu"], bo_luat=doc["ten"],
        as_of=as_of, van_ban=_ra(goc), dieu_khoan=dieu_khoan,
    )


@router.get("/van-ban/{doc_id}/hieu-luc", response_model=VanBanHieuLucResponse)
async def hieu_luc(doc_id: str, as_of_date: date | None = None) -> VanBanHieuLucResponse:
    """Hiệu lực của `doc_id` tại `as_of_date` (mặc định: hôm nay), hai cấp.

    `dieu_khoan` chỉ liệt kê điều khoản CÓ bằng chứng cấp điều khoản — và cả tổ
    tiên của chúng trong cùng văn bản, vì câu trả lời thường dẫn "Điều 139"
    trong khi bản ghi neo ở "Điều 139 > Khoản 1"; bỏ tổ tiên là để một trích
    dẫn cấp Điều đi qua mà không cảnh báo gì. KHÔNG lan xuống anh em: Khoản 2
    không có bản ghi thì không đeo nhãn.

    Rỗng là kết quả HỢP LỆ (19.131/19.135 điều khoản không có bản ghi nào), và
    KHÔNG có nghĩa là không có phán quyết cấp văn bản.
    """
    return await run_in_threadpool(_hieu_luc_sync, doc_id, as_of_hieu_luc(as_of_date))
