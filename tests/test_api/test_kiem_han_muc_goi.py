"""`_kiem_han_muc` (routes_tai_lieu.py) phải đo đúng gói HIỆU LỰC — Phase 10.

Trước bản vá, hàm đọc `nguoi.get("goi")` từ dict xác thực — dict đó chỉ có
`sub`/`email` (`bao_ve.nguoi_dung_bat_buoc`) — nên luôn rơi về "free" bất kể
`users.plan`. Ba test dưới khoá đúng ba chiều: gói trả phí được tính đúng hạn
mức, gói đã hết hạn rơi về gói mặc định (chiều bảo mật), và không có dòng
`users` không phải là lỗi mà cũng rơi về gói mặc định.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from src.api import routes_tai_lieu as rtl
from src.services import bao_ve, hoi_thoai, nang_goi
from src.services.db import get_engine

pytestmark = pytest.mark.integration


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    ht = hoi_thoai.tao_phien(sub, "hợp đồng")
    yield sub, ht
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM viec_doc_tai_lieu WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def _ghi_viec(sub: str, ht: str, n: int) -> None:
    """Chèn `n` việc đọc ĐÃ XONG cho `sub` hôm nay — mô phỏng đã dùng `n` lượt."""
    with get_engine().begin() as c:
        for i in range(n):
            c.execute(
                text(
                    "INSERT INTO viec_doc_tai_lieu"
                    " (user_sub, hoi_thoai_id, ten_tep, dau_van_ban, so_byte, trang_thai)"
                    " VALUES (:u, :h, :t, :d, 1, 'xong')"
                ),
                {"u": sub, "h": ht, "t": f"hd{i}.docx", "d": f"sha:{sub}:{i}"},
            )


@pytest.mark.asyncio
async def test_nguoi_dung_pro_duoc_do_theo_han_muc_tra_phi(nguoi):
    """Bằng chứng gốc rễ: 6 việc đã dùng vượt trần free (5) nhưng KHÔNG vượt
    trần pro (100000 — config/han_muc.yaml). Trên code HÔM NAY, hàm luôn đọc
    "free" nên test này ĐỎ (xem báo cáo cho log chạy thật)."""
    sub, ht = nguoi
    nang_goi.dat_goi(sub, "pro", None, "test-phase10", ly_do="kiểm hạn mức trả phí")
    _ghi_viec(sub, ht, 6)

    await rtl._kiem_han_muc({"sub": sub, "email": None})  # không raise nghĩa là ĐÃ dùng trần pro


@pytest.mark.asyncio
async def test_goi_het_han_roi_ve_mac_dinh(nguoi):
    """Chiều bảo mật: `plan_het_han` đã QUA thì không còn giữ hạn mức trả phí,
    và thông điệp 429 phải nêu đúng gói mặc định vừa áp dụng, không phải "pro"."""
    sub, ht = nguoi
    nang_goi.dat_goi(sub, "pro", 30, "test-phase10", ly_do="kiểm hết hạn")
    with get_engine().begin() as c:
        c.execute(
            text("UPDATE users SET plan_het_han = :h WHERE sub = CAST(:s AS uuid)"),
            {"h": datetime.now(UTC) - timedelta(days=1), "s": sub},
        )
    _ghi_viec(sub, ht, 5)

    with pytest.raises(rtl.HTTPException) as e:
        await rtl._kiem_han_muc({"sub": sub, "email": None})
    assert e.value.status_code == 429
    assert "gói free" in e.value.detail
    assert "gói pro" not in e.value.detail


@pytest.mark.asyncio
async def test_khong_co_dong_users_van_ra_mac_dinh_khong_loi():
    """Đọc không tạo dòng `users` (`plan_hieu_luc` docstring): một `sub` chưa
    từng ghi nhận vẫn phải chạy được — rơi về gói mặc định, không phải lỗi."""
    la = str(uuid.uuid4())
    await rtl._kiem_han_muc({"sub": la, "email": None})  # không raise (0 việc < trần mặc định)
