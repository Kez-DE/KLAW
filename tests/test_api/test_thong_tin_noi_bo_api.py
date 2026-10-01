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


async def _goi_thu(duong: str, loi: HTTPException) -> dict:
    """Gọi một route thử gắn tạm vào app thật, ném đúng `loi`."""
    from httpx import ASGITransport, AsyncClient

    async def _thu():
        raise loi

    app.add_api_route(duong, _thu)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get(duong)
    finally:
        app.router.routes.pop()
    return {"status": r.status_code, **r.json()}


async def test_chi_tiet_loi_5xx_khong_mang_ten_model():
    """Lưới cuối của handler HTTP: một 5xx lặp lại chữ của ngoại lệ."""
    r = await _goi_thu("/__thu_5xx", HTTPException(status_code=503, detail=f"Lỗi hạ tầng. {LOI_RO}"))
    assert r["status"] == 503 and r["detail"] == "Lỗi hạ tầng."


async def test_loi_4xx_lap_lai_ten_tep_cua_nguoi_dung_di_qua_nguyen_ven():
    """api-sse-r1-04, dung-sai-r1-06: tên tệp người dùng đặt có "Google"; lỗi trần trang
    vĩnh viễn không được thành "thử lại sau"."""
    from src.api.routes_tai_lieu import _loi_http
    from src.services.tai_lieu import VuotTran

    loi = _loi_http(VuotTran("so_trang", 20, 35), "HĐLĐ Công ty TNHH Google Việt Nam.pdf")
    r = await _goi_thu("/__thu_ten_tep", loi)
    assert r["status"] == 422
    assert r["detail"] == "«HĐLĐ Công ty TNHH Google Việt Nam.pdf» có 35 trang, vượt giới hạn 20 trang."


async def test_dung_lai_ban_thao_loi_mo_hinh_khong_mang_ten_model(client, dang_nhap, monkeypatch):
    """`routes_ban_thao.dung` đặt `str(e)` của ValueError vào 429, và `llm.py` viết tên model
    vào thông điệp đó — chỗ đó tự lọc."""
    from src.api import routes_ban_thao as rbt
    from src.services import ban_thao

    monkeypatch.setattr(ban_thao, "chi_tiet", lambda sub, id: {"id": id, "loai": "hdld", "facts": {}})
    monkeypatch.setattr(rbt, "con_thieu", lambda *a: [])
    monkeypatch.setattr(rbt, "lua_chon_sai", lambda *a: [])
    monkeypatch.setattr(rbt, "_validate_facts", lambda *a: None)
    monkeypatch.setattr(rbt, "rules_cho", lambda *a: None)
    monkeypatch.setattr(bao_ve, "kiem_tran_chi_phi", lambda: None)

    async def hong(*a, **k):
        raise ValueError(LOI_RO)

    monkeypatch.setattr(ban_thao, "dung_lai", hong)
    r = await client.post(f"/api/v1/ban-thao/{PID}/dung", json={"facts": {}})
    assert r.status_code == 429
    assert r.json()["detail"] and not co_noi_bo(r.json()["detail"])


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


# ══ Vòng kiểm 1 (2026-10-01) — đọc lại bản thảo, lượt đã lưu, tài liệu API, chi phí ═══

LO = "Văn bản do google/gemini-2.5-flash-lite soạn qua OpenRouter."
BEN = "Bên B: Công ty TNHH Google Việt Nam."
DOC = f"# HỢP ĐỒNG DỊCH VỤ\n\n## Điều 1. Các bên\n\n{BEN}\n\n## Điều 9. Ghi chú\n\n{LO}\n"
BT = {
    "id": PID,
    "loai": "tong_quat",
    "phien_ban": 2,
    "document": DOC,
    "clauses": [{"key": "ghi_chu", "ten": "Ghi chú", "noi_dung": f"{BEN} {LO}"}],
    "audit": {},
    "facts": {"ben_b": "Công ty TNHH Google Việt Nam"},
    "khuon": None,
}


async def test_drawer_doc_lai_ban_thao_cu_bo_cau_tac_gia_mo_hinh_giu_ben_hop_dong(client, dang_nhap, monkeypatch):
    """tai-lieu-soan-r1-4: bản thảo lưu trước bản vá — drawer, phiên bản cũ, bản thảo của việc."""
    from src.services import ban_thao

    monkeypatch.setattr(ban_thao, "chi_tiet", lambda sub, id: dict(BT))
    monkeypatch.setattr(ban_thao, "phien_ban_chi_tiet", lambda sub, id, so: {**BT, "luc": None, "doi": []})
    monkeypatch.setattr(ban_thao, "moi_nhat_tren_khuon", lambda sub, viec_id=None, hoi_thoai_id=None: dict(BT))
    for duong in (f"/api/v1/ban-thao/{PID}", f"/api/v1/ban-thao/{PID}/phien-ban/1", f"/api/v1/tai-lieu/{PID}/ban-thao"):
        j = (await client.get(duong)).json()
        assert BEN in j["document"] and "OpenRouter" not in j["document"], duong
        assert j["clauses"][0]["noi_dung"] == BEN, duong


async def test_mo_lai_hoi_thoai_loc_tai_lieu_ban_thao_va_giu_ben_tu_tai_lieu(client, dang_nhap, monkeypatch):
    """api-sse-r1-03, dung-sai-r1-03: phần tài liệu và bản thảo của lượt cũ được lọc; một bên
    hợp đồng người dùng nêu trong TÀI LIỆU (không trong câu hỏi) không mất khi mở lại; câu
    hỏi của một lượt SAU không cấp phép câu tự xưng của lượt trước."""
    luc = datetime(2026, 9, 29, tzinfo=UTC)
    tu_xung = "Tôi là Gemini của Google, chạy qua OpenRouter."
    tai_lieu = {
        "result_type": "tai_lieu",
        "answer": "Bên B trong hợp đồng là Công ty TNHH Google Việt Nam. Điều 5 chưa ghi thời hạn thanh toán.",
        "tai_lieu": {"muc_dich": "tom_tat", "mo_ta": tu_xung, "quan_sat": [], "suy_luan": [tu_xung, "Thiếu thời hạn."]},
        "ban_thao": {
            "id": PID,
            "loai": "tong_quat",
            "ten": "Bản thảo",
            "phien_ban": 1,
            "document": DOC,
            "clauses": [],
            "audit_report": {},
            "facts": {},
        },
    }
    luat = {"result_type": "answer", "answer": "Thử việc tối đa 60 ngày. Tôi là Gemini."}
    luot = [
        {
            "thu_tu": 1,
            "cau_hoi": "Rà soát giúp tôi hợp đồng này",
            "tra_loi": tai_lieu,
            "trace_id": None,
            "tao_luc": luc,
        },
        {"thu_tu": 2, "cau_hoi": "thử việc tối đa bao lâu", "tra_loi": luat, "trace_id": None, "tao_luc": luc},
        {
            "thu_tu": 3,
            "cau_hoi": "bạn có phải gemini không",
            "tra_loi": {"result_type": "gioi_thieu", "answer": "x"},
            "trace_id": None,
            "tao_luc": luc,
        },
    ]
    monkeypatch.setattr(hoi_thoai, "lay_phien", lambda sub, id: {"id": id})
    monkeypatch.setattr(
        hoi_thoai,
        "chi_tiet",
        lambda sub, id: {"id": id, "tieu_de": "t", "tao_luc": luc, "cap_nhat_luc": luc, "luot": luot},
    )
    a, b, _ = (lu["tra_loi"] for lu in (await client.get(f"/api/v1/hoi-thoai/{PID}")).json()["luot"])
    assert a["answer"] == tai_lieu["answer"]
    assert a["tai_lieu"]["mo_ta"] == "" and a["tai_lieu"]["suy_luan"] == ["", "Thiếu thời hạn."]
    assert BEN in a["ban_thao"]["document"] and "OpenRouter" not in a["ban_thao"]["document"]
    assert b["answer"] == "Thử việc tối đa 60 ngày."


def test_tai_lieu_api_cong_khai_tat_ngoai_may_dev():
    """api-sse-r1-02: /docs, /redoc, /openapi.json in docstring nội bộ ("gọi LLM…", "Supabase")."""
    import os
    import subprocess
    import sys

    ma = "from src.main import app; print(app.openapi_url, app.docs_url, app.redoc_url, app.description)"
    for env in ("production", "test"):
        ra = subprocess.run(
            [sys.executable, "-c", ma], capture_output=True, text=True, check=True, env={**os.environ, "APP_ENV": env}
        ).stdout.strip()
        assert ra.startswith("None None None") and "LangGraph" not in ra, (env, ra)
