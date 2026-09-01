"""SSE phải phát nhịp tim, nếu không proxy cắt stream giữa chừng.

Khoảng lặng ĐO ĐƯỢC giữa các bước: `tier2` mất **9,1 giây** không phát gì
(bước đến ở 1,0s → 3,3s → 7,5s → 16,6s → 17,5s). Nhiều reverse proxy đặt
`proxy_read_timeout` mặc định 60s, nhưng cấu hình chặt hơn — hoặc một lượt tra
cứu chậm hơn thường lệ — sẽ đóng kết nối ngay giữa lúc graph đang chạy đúng.

Người dùng thấy: thanh tiến trình đứng ở bước 4 rồi mất kết nối, trong khi
backend vẫn chạy tới cùng và VẪN TÍNH TIỀN lượt đó.

Dòng `: ping` là comment của giao thức SSE — `EventSource` bỏ qua, không sinh
sự kiện, không lọt vào `onmessage`. Nó chỉ giữ ống nước có nước chảy.
"""

import asyncio

import pytest

from src.api import routes_luong


@pytest.mark.asyncio
async def test_im_lang_lau_van_co_nhip_tim(monkeypatch):
    monkeypatch.setattr(routes_luong, "_NHIP_GIAY", 0.05)
    hang: asyncio.Queue = asyncio.Queue()

    async def bom_cham():
        await asyncio.sleep(0.22)          # ~4 nhịp trôi qua
        hang.put_nowait(("buoc", {"buoc": "tier2", "thu_tu": 4}))
        await asyncio.sleep(0.01)
        hang.put_nowait(None)

    task = asyncio.create_task(bom_cham())
    ra = [m async for m in routes_luong.phat_sse(hang)]
    await task

    ping = [m for m in ra if m.startswith(":")]
    buoc = [m for m in ra if "event: buoc" in m]
    assert len(ping) >= 2, f"im lặng 0,22s ở nhịp 0,05s phải có ≥2 ping, thấy {len(ping)}"
    assert len(buoc) == 1, "nhịp tim không được nuốt hay nhân bản sự kiện thật"
    assert ra[-1].startswith("event: buoc"), "sự kiện thật phải là cái cuối, không phải ping"


@pytest.mark.asyncio
async def test_khong_im_lang_thi_khong_chen_ping(monkeypatch):
    """Nhịp tim chỉ để lấp im lặng — stream bận thì nó không được xen vào."""
    monkeypatch.setattr(routes_luong, "_NHIP_GIAY", 5.0)
    hang: asyncio.Queue = asyncio.Queue()
    for i in range(3):
        hang.put_nowait(("buoc", {"buoc": f"b{i}", "thu_tu": i}))
    hang.put_nowait(None)

    ra = [m async for m in routes_luong.phat_sse(hang)]
    assert not [m for m in ra if m.startswith(":")]
    assert len(ra) == 3
