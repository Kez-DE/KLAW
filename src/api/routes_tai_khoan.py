"""`GET /han-muc` · `POST /nguoi-dung` — tài khoản người dùng (Pha 2).

`bao_ve.kiem_han_muc` cưỡng chế hạn mức ngày/tháng của gói (spec 2A §4.2),
nhưng người dùng không có cách nào biết mình còn bao nhiêu cho tới khi bị 429
giữa một câu hỏi. Hai endpoint này lấp đúng khoảng đó, và cả hai chỉ ĐỌC LẠI
thứ cổng bảo vệ đã đếm — không bộ đếm thứ hai nào được dựng. Hai bộ đếm sẽ lệch
nhau và không cách nào biết bên nào đúng; cùng lý lẽ đã khiến
`bao_ve.chi_phi_hom_nay` đọc thẳng `traces` thay vì nuôi một biến riêng.

## Vì sao KHÔNG dùng `Depends(cong_bao_ve)`

`cong_bao_ve` ném 429 khi hết hạn mức. Đặt nó trước `/han-muc` nghĩa là
đúng endpoint sinh ra để nói "bạn hết lượt rồi" sẽ tự khoá mình lại ĐÚNG LÚC
người dùng cần nó nhất. Nó cũng ghi một lượt vào `rate_limit_luot` cho mỗi lần
mở trang tài khoản — xem hạn mức không phải là dùng hạn mức.

Cái được giữ lại là hai cổng đầu (`kiem_api_key` → danh tính), vì cả hai
endpoint đều nói về MỘT người cụ thể và không trả lời được nếu không biết đó là
ai. Không cổng nào bị bỏ vì lười: hai endpoint này không gọi LLM, không gọi
embedding, và đọc đúng hai dòng DB.
"""

import logging

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from src.models.schemas import HanMucResponse, MucHanMuc, NguoiDungResponse, PhienHanMuc
from src.services import bao_ve
from src.services.bao_ve import (
    han_muc,
    kiem_api_key,
    mui_gio,
    ten_goi,
    xac_thuc_nguoi_goi,
)

logger = logging.getLogger(__name__)

router = APIRouter()

GHI_CHU_CACHE = (
    "Chỉ lượt gọi LLM thật mới tính. Lượt trả lời lấy từ bộ đệm KHÔNG tính vào "
    "hạn mức (traces.cache_hit), và các trang tra cứu văn bản thì không tính bao giờ."
)
GHI_CHU_TAT = (
    "Hạn mức theo người dùng chưa bật trên bản triển khai này (Supabase auth chưa "
    "cấu hình), nên hệ thống không đếm lượt theo tài khoản. Trần chi phí ngày và "
    "giới hạn tần suất vẫn hoạt động."
)


async def _nguoi_goi(request: Request) -> dict | None:
    """`{"sub", "email"}` của người gọi, hoặc None khi auth chưa cấu hình.

    `xac_minh` có thể gọi mạng (nạp JWKS khi TTL hết) nên vào threadpool — cùng
    lý do `cong_bao_ve` làm vậy. Thiếu bọc này là chặn event loop cho mọi
    request khác; dự án đã dính đúng lỗi đó hai lần.
    """
    kiem_api_key(request)
    return await run_in_threadpool(xac_thuc_nguoi_goi, request)


@router.get("/han-muc", response_model=HanMucResponse)
async def han_muc_con_lai(request: Request) -> HanMucResponse:
    """Hạn mức còn lại. KHÔNG đi qua `cong_bao_ve` — xem docstring module.

    TẠM: đường khách và `het_han_luc` do Task 4 hoàn thiện; ở đây chỉ đủ để hình
    v2 của `HanMucResponse` dựng được sau khi hạn mức tháng cũ bị gỡ.
    """
    nguoi = await _nguoi_goi(request)
    if nguoi is None:
        return HanMucResponse(
            ap_dung=False, plan=None, ten_goi=None, mui_gio=str(mui_gio()), muc=[],
            phien=PhienHanMuc(luot_toi_da=None), het_han_luc=None, ghi_chu=GHI_CHU_TAT,
        )

    # Gọi qua `bao_ve.<tên>` chứ không tên đã import: `monkeypatch.setattr` của
    # test (và mọi lớp bọc tương lai) tác động lên thuộc tính MODULE, còn tên đã
    # import giữ tham chiếu tới object cũ. Cùng khuôn `routes.py` dùng cho `_g`.
    sub = nguoi["sub"]
    try:
        plan = await run_in_threadpool(bao_ve.ghi_nhan_nguoi_dung, sub, nguoi["email"])
        muc = await run_in_threadpool(bao_ve.mo_ta_muc, sub, plan)
    except Exception as e:
        # Hỏng ở tầng đếm là TỪ CHỐI, không phải trả một con số đoán. Một
        # `con_lai` bịa ra khi DB hỏng tệ hơn một lỗi — người dùng tin nó, rồi
        # gõ câu hỏi tiếp theo và nhận 429 mà không hiểu vì sao.
        logger.exception("han_muc: không đọc được hạn mức của %s — TỪ CHỐI", sub)
        raise HTTPException(
            status_code=503,
            detail="Không đọc được hạn mức của tài khoản, vui lòng thử lại.",
        ) from e

    return HanMucResponse(
        ap_dung=True, plan=plan, ten_goi=ten_goi(plan), mui_gio=str(mui_gio()),
        muc=[MucHanMuc(**m) for m in muc],
        phien=PhienHanMuc(luot_toi_da=han_muc(plan, "luot_moi_phien")),
        het_han_luc=None, ghi_chu=GHI_CHU_CACHE,
    )


@router.post("/nguoi-dung", response_model=NguoiDungResponse)
async def nguoi_dung(request: Request) -> NguoiDungResponse:
    """Ghi nhận người dùng sau đăng nhập, trả về gói của họ.

    Frontend gọi đúng một lần sau khi Supabase trả token, để dòng `users` tồn
    tại TRƯỚC lượt hỏi đầu tiên. Không bắt buộc — `cong_bao_ve` cũng upsert
    (JIT provisioning) — nhưng nó là chỗ FE lấy `plan` để vẽ trang tài khoản mà
    không phải tiêu một lượt hỏi AI để biết mình đang ở gói nào.

    Idempotent: `ON CONFLICT (sub) DO UPDATE` — gọi lại chỉ làm mới
    `last_seen_at`, không sinh dòng thứ hai.
    """
    nguoi = await _nguoi_goi(request)
    if nguoi is None:
        # KHÔNG 200 với một `sub` bịa: đó là dữ liệu rác vĩnh viễn trong đúng
        # bảng mà hạn mức tháng đếm theo. 501 nói đúng sự thật — tính năng này
        # cần một thứ bản triển khai hiện tại không có.
        raise HTTPException(status_code=501, detail=(
            "Chưa cấu hình xác thực (Supabase) — không có danh tính nào để ghi nhận."
        ))
    try:
        plan = await run_in_threadpool(
            bao_ve.ghi_nhan_nguoi_dung, nguoi["sub"], nguoi["email"]
        )
    except Exception as e:
        logger.exception("nguoi_dung: không ghi được dòng users (%s)", nguoi["sub"])
        raise HTTPException(
            status_code=503,
            detail="Không lưu được thông tin tài khoản, vui lòng thử lại.",
        ) from e
    return NguoiDungResponse(sub=nguoi["sub"], email=nguoi["email"], plan=plan)
