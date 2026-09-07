"""Chế độ khách (spec 2A §8): X-Khach-Id, 10 lượt/24h, soạn thảo cần đăng nhập."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve
from src.services.db import get_engine
from tests.test_api.test_tra_cuu_phien import SUPABASE


@pytest.fixture
def ghi_lai_rate_limit(monkeypatch):
    goi: list[tuple] = []

    def gia(khoa, so_luot=None, cua_so_giay=None):
        goi.append((khoa, so_luot, cua_so_giay))

    monkeypatch.setattr(bao_ve, "kiem_rate_limit", gia)
    monkeypatch.setattr(bao_ve, "kiem_tran_chi_phi", lambda: None)
    return goi


@pytest.mark.asyncio
async def test_khach_khong_header_401(client, cai_dat, graph_gia_lap):
    cai_dat(supabase_url=SUPABASE)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"})
    assert r.status_code == 401 and r.json()["detail"] == bao_ve.LOI_KHACH_DANG_NHAP


@pytest.mark.asyncio
async def test_khach_co_header_duoc_hoi_va_dem_dung_khoa(client, cai_dat, graph_gia_lap, ghi_lai_rate_limit):
    cai_dat(supabase_url=SUPABASE)
    kid = str(uuid.uuid4())
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"}, headers={"X-Khach-Id": kid})
    assert r.status_code == 200
    assert (f"khach:{kid}", 10, 86400) in ghi_lai_rate_limit
    khoa = [g[0] for g in ghi_lai_rate_limit]
    assert any(k.startswith("khach-ip:") for k in khoa) and any(k.startswith("ip-ngay:") for k in khoa)


@pytest.mark.asyncio
async def test_khach_header_khong_phai_uuid_401(client, cai_dat, graph_gia_lap):
    cai_dat(supabase_url=SUPABASE)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"}, headers={"X-Khach-Id": "abc"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_khach_soan_thao_401(client, cai_dat, ghi_lai_rate_limit):
    cai_dat(supabase_url=SUPABASE)
    # Body lấy từ một test /soan-thao hiện có (tests/test_api/test_soan_thao*.py) — dependency chạy
    # sau khi parse body nên body phải hợp lệ.
    body = {"loai_van_ban": "hdld", "facts": {}}
    r = await client.post("/api/v1/soan-thao", json=body, headers={"X-Khach-Id": str(uuid.uuid4())})
    assert r.status_code == 401 and r.json()["detail"] == bao_ve.LOI_SOAN_THAO_DANG_NHAP


@pytest.mark.asyncio
async def test_chua_cau_hinh_supabase_khong_dem_khach(client, cai_dat, graph_gia_lap, ghi_lai_rate_limit):
    cai_dat(supabase_url="")
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"})
    assert r.status_code == 200
    assert not any(k.startswith("khach") or k.startswith("ip-ngay") for k, *_ in ghi_lai_rate_limit)


@pytest.mark.integration
def test_kiem_rate_limit_don_theo_KHOA_khong_don_cua_khoa_khac(cai_dat):
    """Giỏ 60 giây KHÔNG được xoá hàng của giỏ 24 giờ (dọn theo khoá).

    Hàng nền CỐ Ý cũ 2 giờ. Bản trước của `_SQL_DON_LUOT` dọn CẢ BẢNG theo cửa
    sổ của lượt gọi hiện tại, nên một khoá bất kỳ chạm giỏ 60 giây là xoá đúng
    hàng này — và giỏ 24 giờ của khách mở lại đúng lúc nó cần đóng. Một test chỉ
    dùng hàng vài mili-giây tuổi KHÔNG hỏng được khi lỗi đó quay lại: câu dọn
    theo 60 giây cũng giữ nguyên chúng.
    """
    from fastapi import HTTPException

    # `tests/conftest.py` TẮT tầng nhịp cho cả suite (`rate_limit_so_luot=0`);
    # test này kiểm chính tầng đó nên phải bật lại tại điểm gọi.
    cai_dat(rate_limit_so_luot=10)
    k, khac = f"test:{uuid.uuid4()}", f"khac:{uuid.uuid4()}"
    with get_engine().begin() as c:
        c.execute(
            text("INSERT INTO rate_limit_luot (ip, ts) VALUES (:k, now() - interval '2 hours')"),
            {"k": k},
        )

    # Giỏ 24 giờ của `k`: hàng 2 giờ tuổi CÒN trong cửa sổ, cộng hàng của lượt này.
    bao_ve.kiem_rate_limit(k, 10, 86400)
    assert bao_ve.dem_cua_so(k, 86400)[0] == 2

    # Một khoá KHÁC chạm giỏ 60 giây — không được động tới hàng nào của `k`.
    bao_ve.kiem_rate_limit(khac, 10, 60)
    assert bao_ve.dem_cua_so(k, 86400)[0] == 2, (
        "giỏ 60 giây của một khoá khác đã dọn mất hàng 2 giờ tuổi của `k` — dọn chung cả bảng"
    )

    # Chiều ngược lại: chính `k` chạm giỏ 60 giây thì hàng 2 giờ tuổi PHẢI đi.
    bao_ve.kiem_rate_limit(k, 10, 60)
    assert bao_ve.dem_cua_so(k, 86400)[0] == 2, (
        "3 hàng = hàng 2 giờ tuổi còn nguyên; chính khoá của nó vừa dọn cửa sổ 60 giây"
    )

    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_rate_limit(k, 2, 86400)  # lượt thứ 3 với trần 2
    assert e.value.status_code == 429 and int(e.value.headers["Retry-After"]) <= 86400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_khach_het_luot_thi_429_va_khach_KHAC_van_hoi_duoc(client, cai_dat, graph_gia_lap):
    """Trần của khách được CƯỠNG CHẾ thật, không chỉ được gọi đúng khoá.

    Test ở trên giả lập `kiem_rate_limit` nên nó khoá HÌNH của lượt gọi (khoá,
    trần, cửa sổ) chứ không khoá HẬU QUẢ. Test này đi qua Postgres thật: hết
    trần là 429, và trần của một `X-Khach-Id` không tràn sang khách khác.

    IP riêng cho mỗi lần chạy qua `X-Forwarded-For` (nên `tin_proxy_header=True`):
    bộ đếm nằm trong Postgres và DB đó DÙNG CHUNG với server dev cùng mọi
    worktree khác, nên giỏ `127.0.0.1` của ASGI transport là nguồn nhiễu thật —
    xem `test_cong_bao_ve.py::test_vuot_rate_limit_chan_TRUOC_khi_graph_chay`.
    """
    cai_dat(supabase_url=SUPABASE, rate_limit_so_luot=10, tin_proxy_header=True)
    tran = int(bao_ve._doc_han_muc()["khach"]["hoi_dap_24h"])
    h = {"X-Khach-Id": str(uuid.uuid4()), "X-Forwarded-For": f"test-{uuid.uuid4()}"}

    for i in range(tran):
        r = await client.post("/api/v1/tra-cuu", json={"query": "x"}, headers=h)
        assert r.status_code == 200, f"lượt {i + 1}/{tran} bị chặn sớm: {r.text}"

    r = await client.post("/api/v1/tra-cuu", json={"query": "x"}, headers=h)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0
    # Câu 429 của khách phải nói việc CẦN LÀM (đăng nhập), không phải một mã lỗi.
    assert "Đăng nhập miễn phí" in r.json()["detail"]

    # Trần của MỘT `X-Khach-Id` không được tràn sang khách khác cùng IP: giỏ
    # `khach-ip:` (30 lượt/24 giờ) còn dư nhiều ở mức 11 lượt.
    khac = {**h, "X-Khach-Id": str(uuid.uuid4())}
    r = await client.post("/api/v1/tra-cuu", json={"query": "x"}, headers=khac)
    assert r.status_code == 200, f"khách thứ hai cùng IP bị chặn oan: {r.text}"
