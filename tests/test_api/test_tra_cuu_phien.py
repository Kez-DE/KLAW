"""Ghi lượt vào phiên qua stream và POST (spec 2026-09-07 §5.2)."""

import json
import uuid

import pytest
from sqlalchemy import text

from src.api import routes
from src.services import bao_ve, bo_nho, hoi_thoai
from src.services.db import get_engine
from tests.test_api.test_xac_thuc_han_muc import _URL as SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer


class _GraphGiaLapStream:
    """`_GraphGiaLap` của `test_xac_thuc_han_muc.py` chỉ có `ainvoke` — đủ cho
    `/tra-cuu`, KHÔNG đủ cho `/tra-cuu/luong` (đường SSE gọi `astream`, xem
    `routes.chay_tra_cuu`). Fixture `graph_gia_lap` cục bộ dưới đây thay bản đó
    CHO FILE NÀY (cùng khuôn `test_tra_cuu_luong.py`), thêm `astream` mà không
    đụng tới fixture dùng chung ở các file khác."""

    _KET_QUA = {
        "result_type": "answer",
        "answer": "x",
        "citations": [],
        "warnings": [],
        "coverage_note": None,
        "nguon": [],
    }

    async def ainvoke(self, *a, **k):
        return dict(self._KET_QUA)

    async def astream(self, *a, **k):
        yield {"assemble": dict(self._KET_QUA)}


@pytest.fixture
def graph_gia_lap(monkeypatch):
    monkeypatch.setattr(routes, "_g", lambda: _GraphGiaLapStream())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)


@pytest.fixture
def don_dep():
    subs: list[str] = []
    yield subs
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = ANY(CAST(:s AS uuid[]))"), {"s": subs})
        c.execute(text("DELETE FROM traces WHERE user_sub = ANY(CAST(:s AS uuid[]))"), {"s": subs})
        c.execute(text("DELETE FROM users WHERE sub = ANY(CAST(:s AS uuid[]))"), {"s": subs})


def _su_kien(body: str) -> list[tuple[str, dict]]:
    ra = []
    for khung in body.strip().split("\n\n"):
        dong = khung.splitlines()
        ten = next((d[7:] for d in dong if d.startswith("event: ")), None)
        if ten is None:
            continue  # nhịp tim/comment SSE (vd. `: ping`) — không phải sự kiện thật.
        du = next(d[6:] for d in dong if d.startswith("data: "))
        ra.append((ten, json.loads(du)))
    return ra


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_tao_phien_va_ghi_luot(client, cai_dat, khoa_ky, graph_gia_lap, don_dep):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "Thử việc tối đa?"}, headers=_bearer(khoa_ky, sub))
    assert r.status_code == 200
    sk = dict(_su_kien(r.text))
    pid = sk["bat_dau"]["hoi_thoai_id"]
    assert pid and "ket_qua" in sk and "loi_luu" not in sk
    ct = hoi_thoai.chi_tiet(sub, pid)
    assert ct["tieu_de"] == "Thử việc tối đa?"
    assert ct["luot"][0]["cau_hoi"] == "Thử việc tối đa?"
    assert ct["luot"][0]["tra_loi"] == sk["ket_qua"]
    assert ct["luot"][0]["trace_id"] == sk["bat_dau"]["trace_id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hoi_tiep_trong_phien_nap_lich_su_may_chu(client, cai_dat, khoa_ky, graph_gia_lap, don_dep, monkeypatch):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    pid = hoi_thoai.tao_phien(sub, "Câu đầu")
    hoi_thoai.ghi_luot(pid, "Câu đầu", {"result_type": "answer", "answer": "Trả lời đầu", "citations": []}, "t0")
    thay: dict = {}
    goc = routes._state_vao

    def ghi_lai(req, as_of, trace_id, bo_nho=None, user_sub=None, hoi_thoai_id=None, soan_thao=None):
        st = goc(
            req,
            as_of,
            trace_id,
            bo_nho=bo_nho,
            user_sub=user_sub,
            hoi_thoai_id=hoi_thoai_id,
            soan_thao=soan_thao,
        )
        thay["lich_su"] = st["lich_su"]
        return st

    monkeypatch.setattr(routes, "_state_vao", ghi_lai)
    r = await client.post(
        "/api/v1/tra-cuu/luong",
        json={
            "query": "Còn khoản mấy?",
            "hoi_thoai_id": pid,
            "lich_su": [{"cau_hoi": "client gửi", "tra_loi": "bị bỏ qua"}],
        },
        headers=_bearer(khoa_ky, sub),
    )
    assert r.status_code == 200
    assert thay["lich_su"] == [{"cau_hoi": "Câu đầu", "tra_loi": "Trả lời đầu", "duong_dan": []}]
    assert dict(_su_kien(r.text))["bat_dau"]["hoi_thoai_id"] == pid
    assert [luot["cau_hoi"] for luot in hoi_thoai.chi_tiet(sub, pid)["luot"]] == ["Câu đầu", "Còn khoản mấy?"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_phien_nguoi_khac_404_va_phien_day_403(client, cai_dat, khoa_ky, graph_gia_lap, don_dep, monkeypatch):
    cai_dat(supabase_url=SUPABASE)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    don_dep.extend([a, b])
    bao_ve.ghi_nhan_nguoi_dung(a, None)
    pid = hoi_thoai.tao_phien(a, "của A")
    r = await client.post(
        "/api/v1/tra-cuu/luong", json={"query": "x", "hoi_thoai_id": pid}, headers=_bearer(khoa_ky, b)
    )
    assert r.status_code == 404
    monkeypatch.setattr(bao_ve, "han_muc", lambda plan, khoa: 2 if khoa == "luot_moi_phien" else 100_000)
    for i in range(2):
        hoi_thoai.ghi_luot(pid, f"q{i}", {"result_type": "answer", "answer": "", "citations": []}, None)
    r = await client.post(
        "/api/v1/tra-cuu/luong", json={"query": "x", "hoi_thoai_id": pid}, headers=_bearer(khoa_ky, a)
    )
    assert r.status_code == 403 and "đã đủ 2 lượt" in r.json()["detail"]


@pytest.mark.asyncio
async def test_an_danh_khong_ghi_va_bat_dau_null(client, cai_dat, graph_gia_lap, monkeypatch):
    cai_dat(supabase_url="")
    # "Không ghi" phải chứng minh được: mọi đường ghi phiên đều nổ nếu bị gọi.
    monkeypatch.setattr(hoi_thoai, "tao_phien", lambda *a, **k: pytest.fail("ẩn danh không được tạo phiên"))
    monkeypatch.setattr(hoi_thoai, "ghi_luot", lambda *a, **k: pytest.fail("ẩn danh không được ghi lượt"))
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x", "hoi_thoai_id": str(uuid.uuid4())})
    assert r.status_code == 200
    assert dict(_su_kien(r.text))["bat_dau"]["hoi_thoai_id"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ghi_loi_thi_van_ket_qua_kem_loi_luu(client, cai_dat, khoa_ky, graph_gia_lap, don_dep, monkeypatch):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)

    def no(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(hoi_thoai, "ghi_luot", no)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"}, headers=_bearer(khoa_ky, sub))
    ten = [t for t, _ in _su_kien(r.text)]
    assert "ket_qua" in ten and "loi_luu" in ten and ten.index("loi_luu") > ten.index("ket_qua")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_tra_cuu_tra_header_phien(client, cai_dat, khoa_ky, graph_gia_lap, don_dep):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    r = await client.post("/api/v1/tra-cuu", json={"query": "x"}, headers=_bearer(khoa_ky, sub))
    assert r.status_code == 200
    pid = r.headers["x-hoi-thoai-id"]
    assert hoi_thoai.chi_tiet(sub, pid)["luot"][0]["cau_hoi"] == "x"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_tra_cuu_xep_lich_cap_nhat_bo_nho(client, cai_dat, khoa_ky, graph_gia_lap, don_dep, monkeypatch):
    """Sau khi lượt được ghi thành công, `/tra-cuu` phải xếp `bo_nho.cap_nhat_phien`
    chạy nền (spec 2026-09-09 §6.7) — cùng phép kiểm áp cho đường SSE ngay dưới."""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    goi: list[tuple[str, str]] = []
    monkeypatch.setattr(bo_nho, "len_lich_cap_nhat", lambda pid, s, rt=None: goi.append((pid, s)))
    r = await client.post("/api/v1/tra-cuu", json={"query": "x"}, headers=_bearer(khoa_ky, sub))
    assert r.status_code == 200
    assert goi == [(r.headers["x-hoi-thoai-id"], sub)]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stream_xep_lich_cap_nhat_bo_nho(client, cai_dat, khoa_ky, graph_gia_lap, don_dep, monkeypatch):
    """Đường SSE — classic defect ở đây là sửa POST mà quên `_chay_nen` (spec
    2026-09-09 §6.7), nên phép kiểm này KHÔNG được gộp chung với test ở trên."""
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    don_dep.append(sub)
    goi: list[tuple[str, str]] = []
    monkeypatch.setattr(bo_nho, "len_lich_cap_nhat", lambda pid, s, rt=None: goi.append((pid, s)))
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"}, headers=_bearer(khoa_ky, sub))
    assert r.status_code == 200
    pid = dict(_su_kien(r.text))["bat_dau"]["hoi_thoai_id"]
    assert goi == [(pid, sub)]
