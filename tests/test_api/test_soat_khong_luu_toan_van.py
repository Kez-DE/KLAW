"""`/soat` KHÔNG được lưu toàn văn tài liệu người dùng dán vào.

Vì sao đây là lỗi chứ không phải một lựa chọn lưu trữ: trong `/tra-cuu`, `query`
là CÂU NGƯỜI DÙNG HỎI — dữ liệu của chính họ, ngắn (max 96 ký tự đo trên DB), và
eval cần thật. Trong `/soat`, `text` là TÀI LIỆU của người dùng, và dữ liệu cá
nhân trong đó thường thuộc về NGƯỜI THỨ BA: người lao động có tên trong hợp
đồng, số CCCD của họ, mức lương của họ. Người đó chưa từng dùng KLAW và chưa
đồng ý bất cứ điều gì — không ô checkbox nào trên giao diện xin phép thay cho họ.

Đo được trước khi sửa: 30 dòng `/api/v1/soat`, `max(length(query))` =
**2.000.000**, trung bình 66.793 ký tự.

Test này là loại bắt được hồi quy khi ai đó "tiện tay" ghi lại `text` để debug.
"""

import uuid

import pytest
from sqlalchemy import text as sql_text

from src.services.db import get_engine
from src.services.traces import dau_van_ban

pytestmark = pytest.mark.integration

_FACTS = {
    "thoi_gian_thu_viec_ngay": 30, "nhom_chuc_danh": "cong_viec_khac",
    "luong_thu_viec": 6_000_000, "luong_chinh_thuc": 7_000_000, "luong_thang": 7_000_000,
    "vung": "I", "co_dieu_khoan_phat_tien": False,
    "co_dieu_khoan_giu_giay_to": False, "co_dieu_khoan_dat_coc": False,
}


async def test_traces_KHONG_chua_noi_dung_van_ban_da_soat(client):
    """Chuỗi đặc trưng dưới đây đóng vai dữ liệu cá nhân của người thứ ba (tên +
    số giấy tờ + lương). Nó KHÔNG được xuất hiện ở bất kỳ cột nào của dòng traces.
    """
    bi_mat = f"NGUYEN VAN A CCCD 001199{uuid.uuid4().hex[:6]} luong 42000000"
    van_ban = (
        f"Điều 1. Công việc và địa điểm làm việc\nBên B: {bi_mat}, làm việc tại Hà Nội.\n\n"
        f"Điều 2. Thời hạn hợp đồng\nHợp đồng có thời hạn 12 tháng.\n"
    )

    r = await client.post(
        "/api/v1/soat",
        json={"loai_van_ban": "hdld", "facts": _FACTS, "text": van_ban},
    )
    assert r.status_code == 200
    trace_id = r.json()["trace_id"]

    with get_engine().connect() as c:
        dong = c.execute(
            sql_text("SELECT * FROM traces WHERE id = :id"), {"id": trace_id}
        ).mappings().one()

    # Quét MỌI cột, không chỉ `query`: nếu một cột khác được thêm sau này và ai
    # đó nhét text vào đó, test này vẫn phải đỏ.
    for ten_cot, gia_tri in dong.items():
        assert bi_mat not in str(gia_tri), f"dữ liệu cá nhân bị lưu ở cột `{ten_cot}`"
        assert "NGUYEN VAN A" not in str(gia_tri), f"tên người bị lưu ở cột `{ten_cot}`"


async def test_traces_van_giu_du_so_lieu_de_do_luong(client):
    """Xoá nội dung, KHÔNG xoá số liệu: `cost_usd`/`latency_ms`/`result_type` và
    các cột claim vẫn phải nguyên — nếu không thì bảng đo của khoá luận mất dòng.
    """
    van_ban = "Điều 1. Công việc\nLàm việc tại Hà Nội.\n\nĐiều 2. Tiền lương\nLương 7.000.000 đồng.\n"

    r = await client.post(
        "/api/v1/soat", json={"loai_van_ban": "hdld", "facts": _FACTS, "text": van_ban}
    )
    assert r.status_code == 200

    with get_engine().connect() as c:
        dong = c.execute(
            sql_text(
                "SELECT query, endpoint, config_name, latency_ms, cost_usd, claims_raw, cache_hit"
                " FROM traces WHERE id = :id"
            ),
            {"id": r.json()["trace_id"]},
        ).mappings().one()

    assert dong["endpoint"] == "/api/v1/soat"
    assert dong["config_name"]
    assert dong["latency_ms"] is not None and dong["latency_ms"] >= 0
    assert dong["cost_usd"] is not None  # /soat không gọi LLM → 0, nhưng phải CÓ mặt
    assert dong["cache_hit"] is False
    # Dấu thay cho nội dung: đủ nhận ra hai lần soát cùng một văn bản.
    assert dong["query"].startswith("soat sha256=")
    assert f"len={len(van_ban)}" in dong["query"]
    assert "clauses=2" in dong["query"], f"tách được 2 Điều, dấu ghi: {dong['query']}"


async def test_cung_van_ban_cho_cung_dau_khac_van_ban_cho_dau_khac():
    """`sha256` của dạng đã chuẩn hoá — đủ để đếm trùng lặp mà không giữ nội dung.
    Chuẩn hoá bằng CHÍNH `verify_tier1.normalize`, không viết hàm thứ hai."""
    a = "Điều 1. Công việc\nHà Nội"
    assert dau_van_ban(a, 1) == dau_van_ban(a, 1)
    # khoảng trắng khác nhau → CÙNG hash (chuẩn hoá), nhưng `len` là độ dài THÔ
    b = "Điều 1.   Công việc\nHà Nội"
    ha, hb = dau_van_ban(a, 1).split()[1], dau_van_ban(b, 1).split()[1]
    assert ha == hb, "chuẩn hoá phải khử khác biệt khoảng trắng"
    assert dau_van_ban(a, 1) != dau_van_ban(b, 1), "`len` thô phải phản ánh văn bản người dùng dán"
    # nội dung khác → hash khác
    assert dau_van_ban("Điều 1. Tiền lương\nHà Nội", 1).split()[1] != ha


def test_dau_van_ban_khong_mang_theo_mot_manh_noi_dung_nao():
    """Chốt hình dạng: chỉ hash, độ dài, số clause — không một ký tự nội dung."""
    bi_mat = "NGUYEN VAN A CCCD 001199123456"
    dau = dau_van_ban(f"Điều 1. Bên B: {bi_mat}", 1)
    assert bi_mat not in dau and "NGUYEN" not in dau and "Điều" not in dau
    assert dau.startswith("soat sha256=")
