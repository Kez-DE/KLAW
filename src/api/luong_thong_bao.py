"""SSE hộp thư thông báo (spec 2026-09-08 cms-quan-ly-tai-khoan §5.5).

Polling PHÍA MÁY CHỦ: hỏi DB mỗi `chu_ky_giay`, chỉ phát khi số chưa đọc đổi; `: ping`
khi im lặng quá `nhip_giay`; đóng sau `toi_da_giay` để không giữ tài nguyên vô hạn —
client tự nối lại. Nguồn sự thật là `GET …/thong-bao`; luồng này chỉ đẩy nhanh.
"""

import asyncio
import functools
import json
from collections.abc import AsyncIterator

from fastapi.encoders import jsonable_encoder
from starlette.concurrency import run_in_threadpool

from src.services import thong_bao


def sse(ten: str, du_lieu: dict) -> str:
    return f"event: {ten}\ndata: {json.dumps(jsonable_encoder(du_lieu), ensure_ascii=False)}\n\n"


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
    while loop.time() - bat_dau < toi_da_giay:
        so = await run_in_threadpool(thong_bao.dem_chua_doc, nguoi_nhan)
        if so != truoc:
            yield sse("so_chua_doc", {"so": so})
            if truoc is not None and so > truoc:
                moi = await run_in_threadpool(
                    functools.partial(thong_bao.danh_sach, nguoi_nhan, chi_chua_doc=True, limit=1)
                )
                if moi:
                    yield sse("thong_bao_moi", moi[0])
            truoc = so
            lan_phat = loop.time()
        elif loop.time() - lan_phat >= nhip_giay:
            yield ": ping\n\n"
            lan_phat = loop.time()
        await asyncio.sleep(chu_ky_giay)
