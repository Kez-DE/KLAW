"""Thông tin nội bộ ở biên HTTP (quyết định 2026-09-30 mục 11): chi tiết lỗi của API
và SSE, nhãn tiến trình, chuỗi cố định, và lượt đã lưu đọc lại từ lịch sử. Không DB,
0 lượt mô hình.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from src.api import routes, routes_luong, routes_tai_khoan
from src.main import app
from src.services import bao_ve, hoi_thoai
from src.services.thong_tin_noi_bo import CAU_NOI_BO, co_noi_bo
from tests.test_api.test_tra_cuu_luong import doc_sse

LOI_RO = "model google/gemini-2.5-flash-lite trả content rỗng sau 3 lần thử (finish_reason=stop)"
PID = "33333333-3333-3333-3333-333333333333"


@pytest.fixture
def dang_nhap():
    app.dependency_overrides[bao_ve.nguoi_dung_bat_buoc] = lambda: {"sub": "u-1", "email": "a@b.c"}
    yield
    app.dependency_overrides.pop(bao_ve.nguoi_dung_bat_buoc, None)


async def test_chi_tiet_loi_http_khong_mang_ten_model(client, dang_nhap, monkeypatch):
    """Mọi `HTTPException(detail=str(e))` đi qua một chỗ: `routes_ban_thao` đặt `str(e)`
    của ValueError vào 429, và `llm.py` viết tên model vào thông điệp đó."""
    monkeypatch.setattr(hoi_thoai, "LOI_KHONG_THAY", LOI_RO)
    r = await client.get("/api/v1/hoi-thoai/khong-phai-uuid")
    assert r.status_code == 404
    assert not co_noi_bo(r.json()["detail"]) and r.json()["detail"]


async def test_chi_tiet_loi_sach_di_qua_nguyen_ven(client, dang_nhap):
    r = await client.get("/api/v1/hoi-thoai/khong-phai-uuid")
    assert r.json()["detail"] == hoi_thoai.LOI_KHONG_THAY


async def test_su_kien_loi_sse_khong_mang_ten_nha_cung_cap(client, monkeypatch):
    async def bom(*a, **k):
        raise HTTPException(status_code=503, detail=f"Lỗi từ OpenRouter: {LOI_RO}")

    monkeypatch.setattr(routes_luong, "chay_tra_cuu", bom)
    _, sk = await doc_sse(client)
    (loi,) = [d for e, d in sk if e == "loi"]
    assert loi["status"] == 503 and loi["detail"] and not co_noi_bo(loi["detail"])


def test_nhan_tien_trinh_khong_noi_mo_hinh():
    for _, nhan in routes.BUOC_TRA_CUU:
        assert "mô hình" not in nhan.lower() and "model" not in nhan.lower(), nhan


async def test_chuoi_co_dinh_khong_ten_ha_tang(client):
    assert not co_noi_bo(routes_tai_khoan.GHI_CHU_TAT)
    assert not co_noi_bo((await client.get("/api/v1/status")).text)


async def test_luot_da_luu_doc_lai_khong_lo_ten_model(client, dang_nhap, monkeypatch):
    """Chính lượt chủ dự án thấy, lưu trong hội thoại TRƯỚC bản vá: mở lại hội thoại
    không được hiện lại nó. Lượt pháp lý giữ tên người hỏi tự nêu."""
    luc = datetime(2026, 9, 30, tzinfo=UTC)
    meta = {
        "result_type": "gioi_thieu",
        "answer": "Tôi chạy trên mô hình ngôn ngữ google/gemini-2.5-flash-lite "
        "và mistralai/mistral-small-3.2-24b-instruct",
    }
    luat = {"result_type": "answer", "answer": "Google Việt Nam phải trả lương đúng hạn. Câu này do GPT-4o viết."}
    monkeypatch.setattr(hoi_thoai, "lay_phien", lambda sub, id: {"id": id})
    monkeypatch.setattr(
        hoi_thoai,
        "chi_tiet",
        lambda sub, id: {
            "id": id,
            "tieu_de": "t",
            "tao_luc": luc,
            "cap_nhat_luc": luc,
            "luot": [
                {"thu_tu": 1, "cau_hoi": "model của bạn là gì", "tra_loi": meta, "trace_id": None, "tao_luc": luc},
                {
                    "thu_tu": 2,
                    "cau_hoi": "Google Việt Nam nợ lương tôi",
                    "tra_loi": luat,
                    "trace_id": None,
                    "tao_luc": luc,
                },
            ],
        },
    )
    r = await client.get(f"/api/v1/hoi-thoai/{PID}")
    assert r.status_code == 200
    a, b = (lu["tra_loi"]["answer"] for lu in r.json()["luot"])
    assert a == CAU_NOI_BO
    assert b == "Google Việt Nam phải trả lương đúng hạn."


async def test_cau_tra_loi_tu_cache_cung_qua_bo_loc(client, monkeypatch):
    """Cache giữ câu trả lời 7 ngày và không đi qua `assemble`: một câu lưu TRƯỚC bản vá
    vẫn phải lọc khi phục vụ lại."""
    from src.services import cache_tra_loi

    payload = {
        "result_type": "answer",
        "answer": "Người lao động được nghỉ phép năm. Câu này do Gemini của Google viết.",
        "citations": [],
        "warnings": [],
        "coverage_note": None,
        "nguon": [],
    }
    monkeypatch.setattr(cache_tra_loi, "tra_cache", lambda *a: ("khoa", "checksum", payload))
    monkeypatch.setattr(routes, "_g", lambda: (_ for _ in ()).throw(AssertionError("cache hit không chạy graph")))
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)
    r = await client.post("/api/v1/tra-cuu", json={"query": "nghỉ phép năm bao nhiêu ngày"})
    assert r.status_code == 200
    assert r.json()["answer"] == "Người lao động được nghỉ phép năm."
