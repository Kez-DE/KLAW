"""`GET /api/v1/han-muc` và `POST /api/v1/nguoi-dung` (Pha 2, nhóm B).

Trang bảng giá bán "50 lượt hỏi AI/tháng" và `bao_ve.kiem_han_muc_thang` đã
cưỡng chế con số đó từ Plan 4b — nhưng người dùng KHÔNG có cách nào biết mình
còn bao nhiêu lượt cho tới khi bị 429 giữa một câu hỏi. Hai endpoint này lấp
đúng khoảng đó, và cả hai chỉ ĐỌC lại thứ cổng bảo vệ đã đếm; không có bộ đếm
thứ hai nào được dựng (hai bộ đếm sẽ lệch và không cách nào biết bên nào đúng).

Bất biến quan trọng nhất, dễ vô tình phá nhất: **`/han-muc` KHÔNG đi qua
`cong_bao_ve`.** Cổng đó ném 429 khi hết hạn mức — tức đúng endpoint sinh ra để
nói "bạn hết lượt rồi" sẽ tự khoá mình lại đúng lúc người dùng cần nó nhất.

Fixture auth tái dùng nguyên từ `test_xac_thuc_han_muc.py`: khoá EC tự sinh +
JWKS giả lập, KHÔNG cần tài khoản Supabase nào.
"""

import uuid

import pytest

from src.services import bao_ve

# `cai_dat` / `khoa_ky` là fixture, lấy qua tests/test_api/conftest.py.
from tests.test_api.test_tra_cuu_phien import SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer


@pytest.fixture
def khong_dung_db(monkeypatch):
    """Tách QUYẾT ĐỊNH hạn mức khỏi phần ĐỌC DB — chạy được ở CI không Postgres."""
    monkeypatch.setattr(bao_ve, "ghi_nhan_nguoi_dung", lambda sub, email: "free")
    monkeypatch.setattr(bao_ve, "dem_luot", lambda sub, ep, moc: 7)


# ══ /han-muc ════════════════════════════════════════════════════════════════


async def test_han_muc_tra_so_con_lai_that_cua_nguoi_dang_dang_nhap(client, cai_dat, khoa_ky, khong_dung_db):
    cai_dat()
    r = await client.get("/api/v1/han-muc", headers=_bearer(khoa_ky))
    assert r.status_code == 200
    d = r.json()

    assert d["ap_dung"] is True
    assert d["plan"] == "free"
    assert d["ten_goi"] == "Miễn phí"
    assert d["het_han_luc"] is None
    assert d["muc"][0]["khoa"] == "hoi_dap_ngay"
    assert d["muc"][0]["han_muc"] == 200, "đọc từ config/han_muc.yaml, không viết cứng trong Python"
    assert d["muc"][0]["da_dung"] == 7
    assert d["phien"]["luot_toi_da"] == 20
    assert "bộ đệm" in d["ghi_chu"], "phải nói ra rằng cache hit không tính"


async def test_han_muc_KHONG_di_qua_cong_bao_ve_nen_khong_tu_khoa_khi_het_luot(client, cai_dat, khoa_ky, monkeypatch):
    """Nếu endpoint này nằm sau `cong_bao_ve`, nó trả 429 đúng lúc người dùng
    hết lượt — tức im lặng đúng lúc cần nói nhất. Đã dùng >= hạn mức vẫn phải 200.
    """
    cai_dat()
    monkeypatch.setattr(bao_ve, "ghi_nhan_nguoi_dung", lambda sub, email: "free")
    monkeypatch.setattr(bao_ve, "dem_luot", lambda sub, ep, moc: 999)

    r = await client.get("/api/v1/han-muc", headers=_bearer(khoa_ky))
    assert r.status_code == 200
    d = r.json()
    assert d["muc"][0]["da_dung"] == 999
    assert d["muc"][0]["da_dung"] >= d["muc"][0]["han_muc"], "hết lượt vẫn phải 200, không tự khoá"


async def test_han_muc_khong_ton_han_mot_luot_rate_limit_nao(client, cai_dat, khoa_ky, khong_dung_db, monkeypatch):
    """Xem hạn mức không phải là dùng hạn mức. Ghi một lượt vào
    `rate_limit_luot` cho mỗi lần mở trang tài khoản là tự hãm mình.
    """
    cai_dat(rate_limit_so_luot=1)

    def no(*a, **k):
        raise AssertionError("/han-muc không được đếm vào rate limit")

    monkeypatch.setattr(bao_ve, "kiem_rate_limit", no)
    assert (await client.get("/api/v1/han-muc", headers=_bearer(khoa_ky))).status_code == 200


async def test_han_muc_chua_cau_hinh_auth_tra_ap_dung_false_KHONG_bia_so(client, cai_dat):
    """Ca rỗng. Auth tắt ⇒ không có người dùng ⇒ không có hạn mức nào để báo.

    Trả 200 kèm `ap_dung=false` chứ không bịa `da_dung=0`: 0 đọc thành "bạn
    chưa dùng lượt nào", trong khi sự thật là hệ thống không đếm theo người.
    """
    cai_dat(supabase_url="")
    r = await client.get("/api/v1/han-muc")
    assert r.status_code == 200
    d = r.json()
    assert d["ap_dung"] is False
    assert d["plan"] is None
    assert d["muc"] == []
    assert d["ghi_chu"]


async def test_han_muc_da_cau_hinh_nhung_thieu_token_tra_401(client, cai_dat):
    cai_dat()
    assert (await client.get("/api/v1/han-muc")).status_code == 401


async def test_han_muc_token_rac_tra_401(client, cai_dat):
    cai_dat()
    r = await client.get("/api/v1/han-muc", headers={"Authorization": "Bearer rac"})
    assert r.status_code == 401


# ══ /han-muc — khách (chưa đăng nhập, spec 2A §8.3) ═════════════════════════


async def test_han_muc_khach_dung_header_dem_dung_cua_so(client, cai_dat, monkeypatch):
    cai_dat(supabase_url=SUPABASE)
    monkeypatch.setattr(bao_ve, "dem_cua_so", lambda khoa, cua_so_giay: (3, None))

    kid = str(uuid.uuid4())
    r = await client.get("/api/v1/han-muc", headers={"X-Khach-Id": kid})
    assert r.status_code == 200
    d = r.json()
    assert d["plan"] == "khach"
    assert d["muc"][0]["khoa"] == "khach_24h"
    assert d["muc"][0]["han_muc"] == 10
    assert d["muc"][0]["da_dung"] == 3
    assert d["phien"]["luot_toi_da"] == 10


async def test_han_muc_khach_khong_header_401(client, cai_dat):
    cai_dat(supabase_url=SUPABASE)
    assert (await client.get("/api/v1/han-muc")).status_code == 401


async def test_han_muc_khach_khong_dem_duoc_thi_TU_CHOI_503_khong_mo_cua(client, cai_dat, monkeypatch):
    """Cùng bất biến với nhánh đã đăng nhập: hỏng ở tầng đếm là TỪ CHỐI, không phải 500 rơi tự do."""
    cai_dat(supabase_url=SUPABASE)

    def no(khoa, cua_so_giay):
        raise RuntimeError("Postgres ngã")

    monkeypatch.setattr(bao_ve, "dem_cua_so", no)
    kid = str(uuid.uuid4())
    r = await client.get("/api/v1/han-muc", headers={"X-Khach-Id": kid})
    assert r.status_code == 503


async def test_han_muc_khong_dem_duoc_thi_TU_CHOI_503_khong_mo_cua(client, cai_dat, khoa_ky, monkeypatch):
    """Hỏng ở tầng đếm là TỪ CHỐI, không phải trả một con số đoán.

    Một `con_lai` bịa ra khi DB hỏng tệ hơn một lỗi: người dùng tin nó.
    """
    cai_dat()
    monkeypatch.setattr(bao_ve, "ghi_nhan_nguoi_dung", lambda sub, email: "free")

    def no(sub, ep, moc):
        raise RuntimeError("Postgres ngã")

    monkeypatch.setattr(bao_ve, "dem_luot", no)
    assert (await client.get("/api/v1/han-muc", headers=_bearer(khoa_ky))).status_code == 503


# ══ POST /nguoi-dung ════════════════════════════════════════════════════════


async def test_nguoi_dung_ghi_nhan_va_tra_ve_goi(client, cai_dat, khoa_ky, monkeypatch):
    cai_dat()
    da_goi = {}

    def ghi(sub, email):
        da_goi["sub"], da_goi["email"] = sub, email
        return "pro"

    monkeypatch.setattr(bao_ve, "ghi_nhan_nguoi_dung", ghi)

    sub = str(uuid.uuid4())
    r = await client.post("/api/v1/nguoi-dung", headers=_bearer(khoa_ky, sub=sub))
    assert r.status_code == 200
    d = r.json()
    assert d == {"sub": sub, "email": "nguoi.dung@example.com", "plan": "pro"}
    assert da_goi == {"sub": sub, "email": "nguoi.dung@example.com"}


async def test_nguoi_dung_goi_hai_lan_khong_no_idempotent(client, cai_dat, khoa_ky, monkeypatch):
    """JIT provisioning: dòng `users` sinh ở lần đăng nhập ĐẦU. Lần thứ hai chỉ
    cập nhật `last_seen_at` — `ON CONFLICT DO UPDATE`, không phải INSERT thứ hai.
    """
    cai_dat()
    monkeypatch.setattr(bao_ve, "ghi_nhan_nguoi_dung", lambda sub, email: "free")
    h = _bearer(khoa_ky)
    assert (await client.post("/api/v1/nguoi-dung", headers=h)).status_code == 200
    assert (await client.post("/api/v1/nguoi-dung", headers=h)).status_code == 200


async def test_nguoi_dung_thieu_token_tra_401(client, cai_dat):
    cai_dat()
    assert (await client.post("/api/v1/nguoi-dung")).status_code == 401


async def test_nguoi_dung_chua_cau_hinh_auth_tra_501_khong_bia_danh_tinh(client, cai_dat):
    """Ca 'không tồn tại'. Không có Supabase thì không có `sub` nào để ghi.

    KHÔNG trả 200: một dòng `users` với `sub` bịa ra là dữ liệu rác vĩnh viễn
    trong đúng bảng mà hạn mức tháng đếm theo.
    """
    cai_dat(supabase_url="")
    r = await client.post("/api/v1/nguoi-dung")
    assert r.status_code == 501


@pytest.mark.integration
async def test_nguoi_dung_ghi_that_vao_bang_users(client, cai_dat, khoa_ky):
    """Ca tích hợp: bảng `users` hiện 0 dòng; sau lượt này phải có đúng 1 dòng
    cho `sub` đó, `plan` mặc định `free`, và gọi lại KHÔNG sinh dòng thứ hai."""
    from sqlalchemy import text

    from src.services.db import get_engine

    cai_dat()
    sub = str(uuid.uuid4())
    h = _bearer(khoa_ky, sub=sub)
    try:
        assert (await client.post("/api/v1/nguoi-dung", headers=h)).json()["plan"] == "free"
        assert (await client.post("/api/v1/nguoi-dung", headers=h)).status_code == 200
        with get_engine().connect() as c:
            rows = c.execute(text("SELECT plan, email FROM users WHERE sub = :s"), {"s": sub}).all()
        assert len(rows) == 1
        assert rows[0] == ("free", "nguoi.dung@example.com")
    finally:
        with get_engine().begin() as c:
            c.execute(text("DELETE FROM users WHERE sub = :s"), {"s": sub})
