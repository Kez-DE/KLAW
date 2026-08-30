"""Test cho POST /api/v1/tra-cuu (Task 10) — graph + endpoint + cộng dồn traces.

Test đụng graph thật (Postgres + OpenRouter thật) đánh dấu `@pytest.mark.integration`,
theo đúng quy ước đã có trong repo (mọi test cần Postgres đều mang marker này —
xem test_infra/test_migrations.py, test_agents/test_expand.py). Test không
đụng DB/LLM (validation Pydantic thuần, hoặc monkeypatch `_g`/`_ghi_traces`)
không mang marker — chạy trong CI mặc định.
"""

import pytest

from src.agents.nodes.assemble import ResultType
from src.api.routes import _tong_hop_traces

# ══ Pydantic validation thuần — KHÔNG chạm graph/DB ═════════════════════════


@pytest.mark.asyncio
async def test_query_rong_bi_422(client):
    r = await client.post("/api/v1/tra-cuu", json={"query": ""})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_as_of_date_sai_dinh_dang_bi_422(client):
    """`as_of_date` gõ kiểu `date`, không phải `str` (xem schemas.py) — pydantic
    tự chặn chuỗi sai định dạng ở biên, trước khi nó tới được `n_expand` và so
    sánh `date <= str` (TypeError giữa graph thay vì 422 sạch ở biên)."""
    r = await client.post("/api/v1/tra-cuu", json={"query": "x", "as_of_date": "không phải ngày"})
    assert r.status_code == 422


# ══ Lỗi hạ tầng — endpoint không được nuốt lỗi (yêu cầu #1) ═════════════════
# monkeypatch `_g`/`_ghi_traces` để test được KHÔNG cần Postgres/OpenRouter.


@pytest.mark.asyncio
async def test_loi_ha_tang_tra_502_khong_lo_chi_tiet_ngoai_le(client, monkeypatch):
    """Lỗi hạ tầng phải NỔ ra mã lỗi rõ ràng (502), không phải abstain giả.
    Đồng thời khoá constraint #2: response KHÔNG mang `str(e)` — chỉ TÊN loại
    ngoại lệ — để không mở rộng bề mặt rò rỉ nếu một ngoại lệ tương lai vô
    tình mang theo dữ liệu nhạy cảm (vd. OPENROUTER_API_KEY)."""
    from src.api import routes

    class BomGraph:
        async def ainvoke(self, *a, **k):
            raise RuntimeError("giả lập rò rỉ: OPENROUTER_API_KEY=sk-khong-duoc-lo")

    monkeypatch.setattr(routes, "_g", lambda: BomGraph())
    r = await client.post("/api/v1/tra-cuu", json={"query": "thử việc bao lâu"})
    assert r.status_code == 502
    assert "sk-khong-duoc-lo" not in r.text
    assert "RuntimeError" in r.text


@pytest.mark.asyncio
async def test_loi_ghi_traces_KHONG_lam_hong_response_da_tinh_dung(client, monkeypatch):
    """Ghi traces là best-effort (xem docstring `_ghi_traces` trong routes.py):
    một câu trả lời đã tính ĐÚNG không được từ chối người dùng chỉ vì INSERT
    traces trục trặc — đây là lỗi tầng quan sát, không phải lỗi tra cứu."""
    from src.api import routes

    class FakeGraph:
        async def ainvoke(self, *a, **k):
            return {"result_type": ResultType.abstain, "citations": [], "warnings": []}

    def bom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(routes, "_g", lambda: FakeGraph())
    monkeypatch.setattr(routes, "_ghi_traces", bom)
    r = await client.post("/api/v1/tra-cuu", json={"query": "thử việc bao lâu"})
    assert r.status_code == 200
    assert r.json()["result_type"] == "abstain"


# ══ Quy ước cộng dồn traces (yêu cầu #3) — hàm thuần, không cần DB/LLM ══════


def test_tong_hop_traces_cong_dung_5_diem_goi_LLM():
    traces = {
        "route_token_in": 10, "route_token_out": 1, "route_cost_usd": 0.001,
        "rewrite_query_token_in": 20, "rewrite_query_token_out": 2, "rewrite_query_cost_usd": 0.002,
        "token_in": 30, "token_out": 3, "cost_usd": 0.003,  # generate_claims — khoá TRẦN
        "tier2_token_in": 40, "tier2_token_out": 4, "tier2_cost_usd": 0.004,
        "assemble_token_in": 50, "assemble_token_out": 5, "assemble_cost_usd": 0.005,
    }
    tong = _tong_hop_traces(traces)
    assert tong["token_in"] == 10 + 20 + 30 + 40 + 50
    assert tong["token_out"] == 1 + 2 + 3 + 4 + 5
    assert abs(tong["cost_usd"] - (0.001 + 0.002 + 0.003 + 0.004 + 0.005)) < 1e-9


def test_tong_hop_traces_khoa_thieu_tinh_la_0_khong_sap():
    assert _tong_hop_traces({}) == {
        "token_in": 0, "token_out": 0, "cost_usd": 0.0,
        "generate_model": None, "judge_model": None,
        "expand_before": None, "expand_after": None,
    }


def test_tong_hop_traces_model_va_expand_lay_dung_khoa():
    traces = {
        "tier2_generate_model": "google/gemini-2.5-flash-lite",
        "tier2_judge_model": "mistralai/mistral-small-3.2-24b-instruct",
        "expand_before": 10, "expand_after": 101,
    }
    tong = _tong_hop_traces(traces)
    assert tong["generate_model"] == "google/gemini-2.5-flash-lite"
    assert tong["judge_model"] == "mistralai/mistral-small-3.2-24b-instruct"
    assert tong["expand_before"] == 10
    assert tong["expand_after"] == 101


def test_tong_hop_traces_tier2_khong_chay_thi_model_la_None():
    """tier2 tắt (`VERIFY_TIER2_ENABLED=false`) hoặc không có claim nào qua
    tầng 1 → `n_tier2` trả sớm `{'tier2': []}` KHÔNG qua
    `verify_tier2_and_trace`, nên `state['traces']` không có
    `tier2_generate_model`/`tier2_judge_model` — cột DB phải là NULL, không
    phải tên model 'lẽ ra' dùng (xem docstring `_tong_hop_traces`)."""
    traces = {"route_token_in": 5}  # không có khoá tier2_*
    tong = _tong_hop_traces(traces)
    assert tong["generate_model"] is None
    assert tong["judge_model"] is None


# ══ Hợp đồng brief (task-10-brief.md Step 2) — đụng graph thật ══════════════


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tra_cuu_tra_ve_result_type_khong_phai_bool_abstained(client):
    r = await client.post("/api/v1/tra-cuu", json={"query": "thử việc bao lâu"})
    assert r.status_code == 200
    d = r.json()
    assert "result_type" in d and "abstained" not in d
    assert d["result_type"] in {"answer", "partial_coverage", "abstain", "out_of_scope"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_response_luon_co_trace_id_va_config_name(client):
    d = (await client.post("/api/v1/tra-cuu", json={"query": "x"})).json()
    assert d["trace_id"] and d["config_name"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_effectivity_tu_expand_duoc_dung_KHONG_tinh_lai_voi_canh_rong():
    """Regression: n_tier1 từng tính lại effectivity với cạnh đi vào rỗng, làm
    Mức 2 không bao giờ kích hoạt và nhóm bẫy 'văn bản đã bị thay' fail im lặng."""
    from src.agents.graph_tra_cuu import build_graph_tra_cuu

    st = await build_graph_tra_cuu().ainvoke(
        {"query": "mức lương tối thiểu vùng một hiện nay là bao nhiêu"})
    if st["result_type"].value == "answer":
        assert any("thay thế" in w or "hết hiệu lực" in w for w in st["warnings"]) or \
            all(c["hieu_luc"] == "con_hieu_luc" for c in st["citations"]), \
            "citation từ văn bản đã bị thay mà không có cảnh báo"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_citation_khong_bao_gio_thieu_duong_dan(client):
    d = (await client.post("/api/v1/tra-cuu", json={"query": "thử việc lương bao nhiêu"})).json()
    assert all(c["duong_dan"] and c["so_ky_hieu"] for c in d["citations"])
