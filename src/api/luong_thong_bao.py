"""SSE hộp thư thông báo (spec 2026-09-08 cms-quan-ly-tai-khoan §5.5).

Polling PHÍA MÁY CHỦ: hỏi DB mỗi `chu_ky_giay`, chỉ phát khi số chưa đọc đổi; `: ping`
khi im lặng quá `nhip_giay`; đóng sau `toi_da_giay` để không giữ tài nguyên vô hạn —
client tự nối lại. Nguồn sự thật là `GET …/thong-bao`; luồng này chỉ đẩy nhanh.
"""

import asyncio
import functools
import json
import time
from collections.abc import AsyncIterator

from fastapi.encoders import jsonable_encoder
from starlette.concurrency import run_in_threadpool

from src.models.schemas import ThongBaoOut
from src.services import thong_bao


def sse(ten: str, du_lieu: dict) -> str:
    return f"event: {ten}\ndata: {json.dumps(jsonable_encoder(du_lieu), ensure_ascii=False)}\n\n"


# Trực tuyến = có ít nhất một luồng `/thong-bao/luong` đang mở (frontend mở luồng cho mọi
# người đã đăng nhập). Không lưu gì xuống DB: `sub -> (số luồng đang mở, mốc mở đầu tiên)`.
# ponytail: sổ trong tiến trình — đúng với một worker uvicorn; nhiều worker cần kho chung.
_TRUC_TUYEN: dict[str, tuple[int, float]] = {}


def dang_ky(sub: str) -> None:
    """Một luồng của `sub` vừa mở."""
    so, tu_luc = _TRUC_TUYEN.get(sub, (0, time.time()))
    _TRUC_TUYEN[sub] = (so + 1, tu_luc)


def huy(sub: str) -> None:
    """Một luồng của `sub` vừa đóng; hết luồng thì rời sổ."""
    so, tu_luc = _TRUC_TUYEN.get(sub, (0, 0.0))
    if so <= 1:
        _TRUC_TUYEN.pop(sub, None)
    else:
        _TRUC_TUYEN[sub] = (so - 1, tu_luc)


def dang_truc_tuyen() -> dict[str, float]:
    """`sub -> epoch giây của lần mở đầu tiên còn hiệu lực`; bản sao, không phải sổ gốc."""
    return {sub: tu_luc for sub, (_, tu_luc) in _TRUC_TUYEN.items()}


async def phat(
    nguoi_nhan: str | None,
    *,
    chu_ky_giay: float = 5.0,
    nhip_giay: float = 15.0,
    toi_da_giay: float = 1800.0,
) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    bat_dau = loop.time()
    lan_phat = bat_dau
    truoc: int | None = None
    if nguoi_nhan is not None:
        dang_ky(nguoi_nhan)
    try:
        # ponytail: mỗi kết nối mở là một COUNT mỗi 5 s; chuyển sang LISTEN/NOTIFY khi số
        # luồng đồng thời lên hàng trăm.
        while loop.time() - bat_dau < toi_da_giay:
            try:
                so = await run_in_threadpool(thong_bao.dem_chua_doc, nguoi_nhan)
                if so != truoc:
                    yield sse("so_chua_doc", {"so": so})
                    if truoc is not None and so > truoc:
                        moi = await run_in_threadpool(
                            functools.partial(thong_bao.danh_sach, nguoi_nhan, chi_chua_doc=True, limit=1)
                        )
                        if moi:
                            yield sse("thong_bao_moi", ThongBaoOut.model_validate(moi[0]).model_dump())
                    truoc = so
                    lan_phat = loop.time()
                elif loop.time() - lan_phat >= nhip_giay:
                    yield ": ping\n\n"
                    lan_phat = loop.time()
            except Exception:
                # một lần DB lỗi không được giết luồng; client vẫn có REST làm nguồn sự thật
                await asyncio.sleep(chu_ky_giay)
                continue
            await asyncio.sleep(chu_ky_giay)
    finally:
        # Chạy cả khi client ngắt (GeneratorExit) hay hết `toi_da_giay`.
        if nguoi_nhan is not None:
            huy(nguoi_nhan)
