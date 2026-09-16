"""Một câu treo không được làm hỏng cả lượt đo, và 77 câu phải chạy được trong
một buổi.

ĐO ĐƯỢC 2026-09-16: lượt `assemble.v3` trên `deepseek/deepseek-v4-flash-0731`
chạy 1 giờ 53 phút mà không ghi nổi một tệp kết quả — 2,3 giây CPU, một luồng
kẹt trong `_ssl__SSLSocket_read`. Chạy tuần tự, một câu treo là cả lượt treo, và
77 câu ở tốc độ đó là tám tiếng.

Hai sửa, đều ở bộ chạy chứ không ở sản phẩm:
- trần thời gian mỗi câu: hết giờ thì câu đó thành một hàng `loi`, đúng đường mà
  `chay` đã dùng cho mọi lỗi khác — KHÔNG được tính vào tử số lẫn mẫu số;
- chạy song song có trần: cùng cam kết, nhưng xong trong một buổi.
"""

import asyncio

import pytest

from eval.run_cau_tra_loi import mot_cau


class GraphTreo:
    async def ainvoke(self, _st):
        await asyncio.sleep(30)


class GraphNo:
    async def ainvoke(self, _st):
        raise RuntimeError("429 xuyên thủng")


async def test_cau_qua_tran_gio_thanh_hang_loi_chu_khong_treo_ca_luot():
    h = await mot_cau(GraphTreo(), {"id": "cq-1", "cau_hoi": "x"}, asyncio.Semaphore(1), tran_giay=0.05)
    assert h["id"] == "cq-1"
    assert "TimeoutError" in h["loi"]


async def test_cau_no_van_giu_nguyen_duong_cu_mot_hang_loi():
    h = await mot_cau(GraphNo(), {"id": "cq-2", "cau_hoi": "x"}, asyncio.Semaphore(1), tran_giay=5)
    assert h["loi"].startswith("RuntimeError")


async def test_semaphore_gioi_han_so_cau_chay_cung_luc():
    dang_chay = 0
    dinh = 0

    class GraphDem:
        async def ainvoke(self, _st):
            nonlocal dang_chay, dinh
            dang_chay += 1
            dinh = max(dinh, dang_chay)
            await asyncio.sleep(0.02)
            dang_chay -= 1
            raise RuntimeError("đủ rồi")  # tránh phải dựng state thật

    sem = asyncio.Semaphore(2)
    g = GraphDem()
    await asyncio.gather(*(mot_cau(g, {"id": str(i), "cau_hoi": "x"}, sem, tran_giay=5) for i in range(6)))
    assert dinh == 2


@pytest.mark.parametrize("tran", [0.01])
async def test_tran_gio_khong_nuot_ket_qua_cua_cau_chay_kip(tran):
    class GraphNhanh:
        async def ainvoke(self, _st):
            raise RuntimeError("nhanh")

    h = await mot_cau(GraphNhanh(), {"id": "cq-3", "cau_hoi": "x"}, asyncio.Semaphore(1), tran_giay=tran)
    assert "RuntimeError" in h["loi"] and "TimeoutError" not in h["loi"]
