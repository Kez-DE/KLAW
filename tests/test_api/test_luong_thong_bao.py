# tests/test_api/test_luong_thong_bao.py
"""Generator SSE hộp thư (spec 2B §5.5): phát khi số đếm đổi, nhịp tim, dừng đúng hạn."""

import asyncio

import pytest

from src.api import luong_thong_bao
from src.services import thong_bao


def test_sse_dung_khung():
    assert luong_thong_bao.sse("so_chua_doc", {"so": 2}) == 'event: so_chua_doc\ndata: {"so": 2}\n\n'


@pytest.mark.asyncio
async def test_phat_khi_so_doi_va_ping(monkeypatch):
    dem = iter([0, 1])
    monkeypatch.setattr(thong_bao, "dem_chua_doc", lambda nn: next(dem, 1))
    monkeypatch.setattr(
        thong_bao,
        "danh_sach",
        lambda nn, chi_chua_doc=False, limit=50: [
            {"id": 9, "loai": "yeu_cau_moi", "tieu_de": "t", "noi_dung": "n", "duong_dan": "/x", "da_doc": False,
             "tao_luc": "2026-09-08T00:00:00+00:00"}
        ],
    )
    khung = [k async for k in luong_thong_bao.phat(None, chu_ky_giay=0.01, nhip_giay=0.03, toi_da_giay=0.15)]
    chuoi = "".join(khung)
    assert 'event: so_chua_doc\ndata: {"so": 0}' in chuoi and 'event: so_chua_doc\ndata: {"so": 1}' in chuoi
    assert chuoi.count("event: thong_bao_moi") == 1 and '"id": 9' in chuoi, "phát một lần khi số tăng, không lặp"
    assert ": ping\n\n" in chuoi


@pytest.mark.asyncio
async def test_phat_dung_sau_toi_da(monkeypatch):
    monkeypatch.setattr(thong_bao, "dem_chua_doc", lambda nn: 0)
    t0 = asyncio.get_running_loop().time()
    async for _ in luong_thong_bao.phat("00000000-0000-0000-0000-000000000001", chu_ky_giay=0.01, nhip_giay=1, toi_da_giay=0.05):
        pass
    assert asyncio.get_running_loop().time() - t0 < 1
