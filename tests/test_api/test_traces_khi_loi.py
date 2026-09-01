"""H2 — một request HỎNG không được là một request MIỄN PHÍ.

`chay_tra_cuu` raise trước khi tới `_ghi_traces`, nên mọi request thất bại biến
mất khỏi sổ. Đường `/tra-cuu` gọi LLM tối đa 5 lần: hỏng ở lần thứ 5 nghĩa là 4
lượt ĐÃ TRẢ TIỀN không để lại một dòng nào.

Chế độ hỏng này kích hoạt đúng lúc OpenRouter trả 429/5xx — tức đúng lúc trần
chi phí ngày và hạn mức tháng cần chính xác nhất, vì cả hai ĐỌC bảng `traces`.
Càng hỏng nhiều thì hai cổng đó càng đếm thiếu, theo đúng hướng nguy hiểm.

`_tong_hop_traces` dùng `.get(k) or 0` nên một dòng `loi` thiếu khoá không nổ;
và `dem_luot_thang` đếm `count(*)`, nên dòng đó TRỪ đúng một lượt hạn mức tháng
— chính là điều làm request hỏng thôi miễn phí.
"""

import httpx
import pytest

from src.agents.nodes.assemble import ResultType
from src.api import routes

_CAU_HOI = {"query": "thử việc bao lâu"}

FACTS = {"nhom_chuc_danh": "cong_viec_khac", "thoi_gian_thu_viec_ngay": 30,
         "luong_thang": 10_000_000, "vung": "I",
         "luong_thu_viec": 9_000_000, "luong_chinh_thuc": 10_000_000,
         "co_dieu_khoan_phat_tien": False, "co_dieu_khoan_giu_giay_to": False,
         "co_dieu_khoan_dat_coc": False}


@pytest.fixture
def so_sach(monkeypatch):
    """Bắt mọi lượt `_ghi_traces` thay vì ghi Postgres."""
    dong: list[dict] = []

    def ghi(trace_id, endpoint, query, config_name, st, latency_ms,
            cache_hit=False, user_sub=None):
        dong.append({
            "endpoint": endpoint, "st": st, "latency_ms": latency_ms,
            "cache_hit": cache_hit, "user_sub": user_sub,
        })

    monkeypatch.setattr(routes, "_ghi_traces", ghi)
    return dong


class _GraphNo:
    """Graph nổ ở giữa chừng, sau khi vài node đã tiêu tiền."""

    def __init__(self, loi: Exception, truoc_khi_no: list | None = None):
        self._loi = loi
        self._truoc = truoc_khi_no or []

    async def ainvoke(self, *a, **k):
        raise self._loi

    async def astream(self, *a, **k):
        for chunk in self._truoc:
            yield chunk
        raise self._loi


# ══ /tra-cuu ════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("loi", "ma"),
    [
        (httpx.TransportError("OpenRouter không với tới"), 503),
        (RuntimeError("bug thật"), 500),
    ],
)
async def test_tra_cuu_hong_van_GHI_mot_dong_traces(client, so_sach, monkeypatch, loi, ma):
    monkeypatch.setattr(routes, "_g", lambda: _GraphNo(loi))
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI)

    assert r.status_code == ma
    assert len(so_sach) == 1, "request hỏng không để lại dòng traces nào"
    assert so_sach[0]["endpoint"] == "/api/v1/tra-cuu"
    assert so_sach[0]["st"]["result_type"] == "loi"
    # `cache_hit=False` là điều kiện để `dem_luot_thang` ĐẾM dòng này.
    assert so_sach[0]["cache_hit"] is False


async def test_dong_loi_giu_lai_chi_phi_cac_node_DA_chay(client, so_sach, monkeypatch):
    """Giá trị thật của vết vá: hỏng ở lượt LLM thứ 5 vẫn giữ chi phí 4 lượt đầu.

    Đường SSE gom state theo từng node nên phần đã tiêu CÒN ĐÓ lúc nổ; ghi nó
    lại là khác biệt giữa "biết đã tiêu bao nhiêu" và "mất trắng khỏi sổ".
    """
    da_chay = [
        {"route": {"traces": {"route_cost_usd": 0.0011, "route_token_in": 700}}},
        {"generate_claims": {"traces": {"route_cost_usd": 0.0011, "route_token_in": 700,
                                        "cost_usd": 0.0042, "token_in": 3100}}},
    ]
    monkeypatch.setattr(
        routes, "_g", lambda: _GraphNo(httpx.TransportError("429 từ OpenRouter"), da_chay)
    )

    r = await client.post("/api/v1/tra-cuu/luong", json=_CAU_HOI)
    assert r.status_code == 200  # SSE: lỗi đi qua `event: loi`, mã HTTP đã gửi rồi
    assert "event: loi" in r.text

    assert len(so_sach) == 1
    tr = so_sach[0]["st"]["traces"]
    assert routes._tong_hop_traces(tr)["cost_usd"] == pytest.approx(0.0053)
    assert so_sach[0]["st"]["result_type"] == "loi"


async def test_duong_SSE_khong_ghi_HAI_dong_cho_mot_request(client, so_sach, monkeypatch):
    """`_chay_nen` gọi `chay_tra_cuu`, nên vết vá nằm ở hàm dùng chung — không
    được vá lần nữa ở caller và thành ghi đôi."""

    class _Xong:
        async def astream(self, *a, **k):
            yield {"assemble": {"result_type": ResultType.answer, "answer": "x",
                                "citations": [], "warnings": [], "nguon": []}}

    monkeypatch.setattr(routes, "_g", lambda: _Xong())
    r = await client.post("/api/v1/tra-cuu/luong", json=_CAU_HOI)
    assert r.status_code == 200
    assert len(so_sach) == 1, f"ghi {len(so_sach)} dòng cho một request"
    assert so_sach[0]["st"]["result_type"] != "loi"


async def test_tra_cuu_thanh_cong_van_ghi_dung_MOT_dong(client, so_sach, monkeypatch):
    class _Xong:
        async def ainvoke(self, *a, **k):
            return {"result_type": ResultType.answer, "answer": "x",
                    "citations": [], "warnings": [], "nguon": []}

    monkeypatch.setattr(routes, "_g", lambda: _Xong())
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI)
    assert r.status_code == 200
    assert len(so_sach) == 1
    assert so_sach[0]["st"]["result_type"] != "loi"


# ══ /soan-thao ══════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("loi", "ma"),
    [
        (httpx.TransportError("OpenRouter không với tới"), 503),
        (RuntimeError("bug thật"), 500),
    ],
)
async def test_soan_thao_hong_van_GHI_mot_dong_traces(client, so_sach, monkeypatch, loi, ma):
    monkeypatch.setattr(routes, "_g_soan_thao", lambda: _GraphNo(loi))
    r = await client.post(
        "/api/v1/soan-thao", json={"loai_van_ban": "hdld", "facts": FACTS, "nganh": "thuong_mai"}
    )

    assert r.status_code == ma
    assert len(so_sach) == 1, "request /soan-thao hỏng không để lại dòng traces nào"
    assert so_sach[0]["endpoint"] == "/api/v1/soan-thao"
    assert so_sach[0]["st"]["result_type"] == "loi"


# ══ Chứng minh dòng `loi` thật sự chạm Postgres ═════════════════════════════


@pytest.mark.integration
async def test_dong_loi_that_su_nam_trong_bang_traces(client, monkeypatch):
    """Không giả lập `_ghi_traces`: ghi thật, rồi ĐỌC LẠI từ Postgres.

    Test spy ở trên chứng minh đường gọi; test này chứng minh cột `result_type`
    nhận được giá trị mới và dòng đó đếm được — tức hạn mức tháng
    (`dem_luot_thang`, `count(*)`) thật sự trừ một lượt cho request hỏng.
    """
    from sqlalchemy import text

    from src.services.db import get_engine

    monkeypatch.setattr(routes, "_g", lambda: _GraphNo(httpx.TransportError("429")))
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI)
    assert r.status_code == 503

    with get_engine().connect() as c:
        dong = c.execute(
            text("SELECT endpoint, result_type, cache_hit FROM traces"
                 " WHERE endpoint = '/api/v1/tra-cuu' AND result_type = 'loi'"
                 " ORDER BY ts DESC LIMIT 1")
        ).mappings().one_or_none()

    assert dong is not None, "request hỏng không để lại dòng nào trong Postgres"
    assert dong["cache_hit"] is False
