"""`POST /tra-cuu/luong` — SSE phát BƯỚC THẬT của graph (Pha 2).

## Phán quyết: stream BƯỚC, không stream token

Graph chạy `route → tien_de → rewrite → retrieve → expand → generate → tier1 →
tier2 → assemble`, và văn xuôi chỉ sinh ở bước CUỐI. Stream token vì vậy cho
đúng một trải nghiệm: **im lặng ~50 giây rồi chảy chữ ~10 giây** (p95 đo được
50.289ms trên 204 dòng traces) — tệ hơn cả chỉ báo bước hiện có, vì nó thay một
thanh tiến trình bằng một màn hình trắng đúng lúc người dùng cần biết máy còn
sống hay không.

Stream bước biến chỉ báo "ước lượng theo thời gian" mà giao diện đang phải nói
dối thành tiến trình THẬT, kèm con số đã tính được ở từng bước.

## POST, không phải GET/EventSource

`EventSource` chỉ gửi được GET và **không đặt được header**, nên nó không mang
nổi `Authorization: Bearer` mà `cong_bao_ve` yêu cầu. FE buộc phải dùng
`fetch` + `ReadableStream` (hoặc `@microsoft/fetch-event-source`); đã vậy thì
POST là lựa chọn đúng — nó cũng giữ câu hỏi ra khỏi URL, khỏi lịch sử trình
duyệt và khỏi log của mọi proxy trên đường.

## Graph chạy trong TASK RIÊNG, không phải con của request

Đây là phần dễ bỏ sót nhất và cũng đắt nhất. Nếu graph là con của request thì
client đóng socket (bấm nút Huỷ) sẽ huỷ luôn nó — mà LLM ĐÃ tiêu tiền trước
đó, và dòng `traces` thì chưa kịp ghi. Hệ quả: mọi lượt bị huỷ là một lượt
MIỄN PHÍ, và hạn mức ngày/tháng (`bao_ve.dem_luot` đếm chính bảng `traces`)
trở thành trang trí — một lỗ hổng bấm được bằng một nút bấm có sẵn trên giao
diện.

Chạy trong task riêng cũng giữ được lượt ghi cache: câu trả lời đã tốn tiền
vẫn nằm lại cho request sau, thay vì bị vứt cùng cái socket.
"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from src.api.routes import (
    BUOC_TRA_CUU,
    _chuan_bi_phien,
    _ghi_luot_nhe,
    buoc_cua_luot,
    chay_tra_cuu,
    tra_cuu_response,
)
from src.config import get_settings
from src.models.schemas import TraCuuRequest
from src.services import bo_nho
from src.services import hoi_thoai as hoi_thoai_svc
from src.services.bao_ve import cong_bao_ve_khach

logger = logging.getLogger(__name__)

router = APIRouter()

_NHAN = dict(BUOC_TRA_CUU)

# Bước "cache" không phải một node của graph — nó là nhánh KHÔNG chạy node nào.
_NHAN["cache"] = "Lấy câu trả lời từ bộ đệm"


def _thu_tu_va_tong(req: TraCuuRequest) -> tuple[dict[str, int], int]:
    """Số thứ tự và tổng số bước của LƯỢT NÀY.

    Per-request, không phải hằng số module: `giai_nghia` chỉ chạy ở lượt hỏi nối
    tiếp (`routes.buoc_cua_luot`), nên một bảng thứ tự dùng chung sẽ cho lượt đầu
    một thanh tiến trình mở màn ở "bước 2/10" với một bước 1 không bao giờ tới.
    `_NHAN` thì vẫn dùng chung — nhãn của một bước không phụ thuộc lượt nào.
    """
    buoc = buoc_cua_luot(req)
    thu_tu = {ten: i for i, (ten, _) in enumerate(buoc, start=1)}
    thu_tu["cache"] = len(buoc)
    return thu_tu, len(buoc)

# Giữ tham chiếu mạnh tới task đang chạy: `asyncio.create_task` chỉ giữ tham
# chiếu YẾU, nên một task không được ai giữ có thể bị thu gom giữa chừng — và
# lượt LLM đó biến mất khỏi `traces` đúng như thể client đã rời đi.
_DANG_CHAY: set[asyncio.Task] = set()

# Header chống đệm. Không có chúng, một reverse proxy gom cả stream rồi giao
# một lần — tức biến SSE thành một response bình thường đến muộn, mất trắng lý
# do endpoint này tồn tại.
_HEADER = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse(ten: str, du_lieu: dict) -> str:
    """Một khung SSE. `json.dumps` không sinh ký tự xuống dòng thật nên payload
    luôn nằm gọn trên MỘT dòng `data:` — nhiều dòng sẽ bị client nối lại bằng
    `\\n` và JSON vẫn parse được, nhưng chỉ vì may."""
    return f"event: {ten}\ndata: {json.dumps(du_lieu, ensure_ascii=False)}\n\n"


async def _chay_nen(
    req: TraCuuRequest,
    user_sub: str | None,
    trace_id: str,
    hang: asyncio.Queue,
    hoi_thoai_id: str | None,
    bo_nho_phien: dict | None,
    soan_thao: dict | None = None,
    tai_lieu_phien: list[dict] | None = None,
    ban_thao_tong_quat: dict | None = None,
) -> None:
    """Chạy graph tới cùng và đẩy sự kiện vào `hang`. KHÔNG dừng khi client rời.

    `hang` không giới hạn kích thước nên `put` không bao giờ chặn — client bỏ
    đi giữa chừng thì hàng đợi giữ vài sự kiện nhỏ rồi bị thu gom cùng task.

    `soan_thao` (Task 19) — trạng thái soạn thảo đang mở của phiên
    (`_chuan_bi_phien`), truyền THẲNG vào `chay_tra_cuu` để đường SSE này dựng
    state giống hệt đường POST (`routes.tra_cuu`).
    """

    thu_tu, tong = _thu_tu_va_tong(req)

    async def phat(ten: str, chi_tiet: dict) -> None:
        await hang.put(("buoc", {
            "buoc": ten,
            # Node lạ (thêm vào graph mà quên khai trong `BUOC_TRA_CUU`) vẫn
            # được phát, kèm nhãn nói thẳng là chưa khai — nuốt nó đi làm một
            # bước thật biến mất khỏi thanh tiến trình mà không ai biết.
            "nhan": _NHAN.get(ten, f"Bước {ten} (chưa khai nhãn)"),
            "thu_tu": thu_tu.get(ten),
            "tong": tong,
            "chi_tiet": chi_tiet,
        }))

    try:
        payload, config_name = await chay_tra_cuu(
            req,
            user_sub,
            trace_id,
            phat,
            bo_nho=bo_nho_phien,
            hoi_thoai_id=hoi_thoai_id,
            soan_thao=soan_thao,
            tai_lieu_phien=tai_lieu_phien,
            ban_thao_tong_quat=ban_thao_tong_quat,
        )
        # Dựng qua CHÍNH model của `/tra-cuu`: shape của hai đường không thể
        # lệch nhau, và một payload dị dạng nổ ở đây thành `event: loi` chứ
        # không thành một JSON thiếu trường mà FE tự đoán.
        resp = tra_cuu_response(payload, trace_id, config_name)
        # MỘT lần dump: cái phát ra và cái lưu vào phiên là cùng một JSON.
        du = resp.model_dump(mode="json")
        await hang.put(("ket_qua", du))
        if hoi_thoai_id is not None:
            loi_luu = await _ghi_luot_nhe(hoi_thoai_id, req.query, du, trace_id)
            if loi_luu is not None:
                await hang.put(("loi_luu", {"hoi_thoai_id": hoi_thoai_id, "detail": loi_luu}))
            else:
                try:
                    await run_in_threadpool(bo_nho.luu_suy_dien, hoi_thoai_id, payload.get("ho_so") or {})
                except Exception:
                    logger.exception("bo_nho: không lưu được giả định suy_dien (phien=%s)", hoi_thoai_id)
                if user_sub is not None:
                    bo_nho.len_lich_cap_nhat(hoi_thoai_id, user_sub, payload.get("result_type"))
            # Task 19 — cùng khối chốt `soan_thao_dang_mo` với `routes.tra_cuu`;
            # xem chú thích ở đó cho lý do bỏ qua khi ý định là `tra_cuu`.
            sd = payload.get("soan_thao_dang_mo")
            if sd and payload.get("intent") != "tra_cuu":
                try:
                    await run_in_threadpool(
                        hoi_thoai_svc.ghi_soan_thao,
                        user_sub,
                        hoi_thoai_id,
                        {
                            "loai": sd["loai"],
                            "facts": sd["facts"],
                            "ban_thao_id": sd.get("ban_thao_id"),
                            "so_lan_sua": sd.get("so_lan_sua", 0),
                        },
                    )
                except Exception:
                    logger.exception("hoi_thoai: không ghi được soan_thao_dang_mo (phien=%s)", hoi_thoai_id)
    except HTTPException as e:
        # `chay_tra_cuu` đã phân loại 503 (hạ tầng nhất thời) / 500 (bug thật)
        # và `detail` của nó chỉ mang TÊN loại ngoại lệ, không mang `str(e)`.
        await hang.put(("loi", {
            "status": e.status_code, "detail": e.detail, "trace_id": trace_id,
        }))
    except Exception:
        logger.exception("tra_cuu_luong: lỗi ngoài dự kiến (trace_id=%s)", trace_id)
        await hang.put(("loi", {
            "status": 500, "detail": "tra cứu thất bại", "trace_id": trace_id,
        }))
    finally:
        # Sentinel đóng stream. Trong `finally` để một lỗi ở chính lượt `put`
        # phía trên cũng không treo client vô hạn.
        await hang.put(None)


# Khoảng lặng ĐO ĐƯỢC giữa hai bước: `tier2` mất **9,1 giây** không phát gì.
# Nhiều reverse proxy đóng kết nối rảnh sớm hơn thế dưới cấu hình chặt, và khi
# đó người dùng thấy tiến trình đứng rồi mất kết nối — trong khi graph vẫn chạy
# tới cùng và VẪN TÍNH TIỀN lượt đó. 15 giây đủ thưa để không tốn gì, đủ dày để
# giữ ống nước có nước chảy.
_NHIP_GIAY = 15.0


async def phat_sse(hang: asyncio.Queue):
    """Bơm hàng đợi ra SSE, chèn `: ping` khi im lặng quá `_NHIP_GIAY`.

    `: ping` là **comment** của giao thức SSE — `EventSource` bỏ qua hoàn toàn,
    không sinh sự kiện, không lọt vào `onmessage`. Nó không phải một loại sự
    kiện thứ tư mà FE phải xử lý.

    Tách khỏi `tra_cuu_luong` để test được mà không phải dựng cả graph.
    """
    while True:
        try:
            muc = await asyncio.wait_for(hang.get(), timeout=_NHIP_GIAY)
        except TimeoutError:
            yield ": ping\n\n"
            continue
        if muc is None:
            return
        yield _sse(*muc)


@router.post("/tra-cuu/luong")
async def tra_cuu_luong(
    req: TraCuuRequest, user_sub: str | None = Depends(cong_bao_ve_khach)
) -> StreamingResponse:
    """Như `POST /tra-cuu`, nhưng phát tiến trình theo BƯỚC qua SSE.

    Bốn loại sự kiện:
      * `bat_dau` — `{trace_id, config_name, hoi_thoai_id, cac_buoc: [{buoc,
        nhan, thu_tu}]}`, gửi NGAY. Không có nó, FE lại phải tự ước lượng danh
        sách bước — đúng thứ endpoint này sinh ra để thay thế. `hoi_thoai_id`
        là phiên vừa tạo/mở (spec 2026-09-07 §5.2); `null` khi ẩn danh.
      * `buoc` — một node vừa xong: `{buoc, nhan, thu_tu, tong, chi_tiet}`.
      * `ket_qua` — payload y hệt `TraCuuResponse` của `POST /tra-cuu`;
        hoặc `loi` — `{status, detail, trace_id}`.
      * `loi_luu` — `{hoi_thoai_id, detail}`, phát SAU `ket_qua` khi câu trả lời
        đã tính xong nhưng ghi vào phiên thất bại. Câu trả lời không mất, chỉ
        chưa lưu được vào lịch sử.

    Tham số sai vẫn ra **422 bình thường** (pydantic chạy trước thân hàm), và
    cổng `cong_bao_ve` vẫn ra 401/429/503 bình thường — chỉ lỗi phát sinh SAU
    khi stream đã mở mới đi qua `event: loi`, vì lúc đó mã HTTP đã gửi rồi.
    `_chuan_bi_phien` chạy TRƯỚC khi mở stream nên 404/403 của nó cũng ra mã
    HTTP thường, không phải `event: loi`.
    """
    trace_id = str(uuid.uuid4())
    req, hoi_thoai_id, bn, soan_thao, tai_lieu_phien, ban_thao_tong_quat = await _chuan_bi_phien(req, user_sub)
    hang: asyncio.Queue = asyncio.Queue()
    hang.put_nowait(("bat_dau", {
        "trace_id": trace_id,
        "config_name": req.config_name or get_settings().eval_config_name,
        "hoi_thoai_id": hoi_thoai_id,
        "cac_buoc": [
            {"buoc": ten, "nhan": nhan, "thu_tu": i}
            for i, (ten, nhan) in enumerate(buoc_cua_luot(req), start=1)
        ],
    }))

    task = asyncio.create_task(
        _chay_nen(
            req, user_sub, trace_id, hang, hoi_thoai_id, bn, soan_thao, tai_lieu_phien, ban_thao_tong_quat
        )
    )
    _DANG_CHAY.add(task)
    task.add_done_callback(_DANG_CHAY.discard)

    return StreamingResponse(phat_sse(hang), media_type="text/event-stream", headers=_HEADER)
