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
async def test_loi_khong_xac_dinh_tra_500_khong_lo_chi_tiet_ngoai_le(client, monkeypatch):
    """Lỗi hạ tầng phải NỔ ra mã lỗi rõ ràng, không phải abstain giả. Một
    RuntimeError không thuộc (httpx lỗi, OperationalError) → 500 (bug thật,
    không ngụ ý nên thử lại) — xem hai test 503 riêng cho hai loại NHẤT THỜI.
    Đồng thời khoá constraint #2: response KHÔNG mang `str(e)` — chỉ TÊN loại
    ngoại lệ — để không mở rộng bề mặt rò rỉ nếu một ngoại lệ tương lai vô
    tình mang theo dữ liệu nhạy cảm (vd. OPENROUTER_API_KEY)."""
    from src.api import routes

    class BomGraph:
        async def ainvoke(self, *a, **k):
            raise RuntimeError("giả lập rò rỉ: OPENROUTER_API_KEY=sk-khong-duoc-lo")

    monkeypatch.setattr(routes, "_g", lambda: BomGraph())
    r = await client.post("/api/v1/tra-cuu", json={"query": "thử việc bao lâu"})
    assert r.status_code == 500
    assert "sk-khong-duoc-lo" not in r.text
    assert "RuntimeError" in r.text


@pytest.mark.asyncio
async def test_loi_httpx_tra_503_nen_thu_lai(client, monkeypatch):
    """OpenRouter 429/5xx cạn retry (httpx.HTTPStatusError/TransportError) →
    503 Service Unavailable — client NÊN thử lại, khác 500 (bug thật)."""
    import httpx

    from src.api import routes

    class BomHttpx:
        async def ainvoke(self, *a, **k):
            raise httpx.TransportError("connection refused")

    monkeypatch.setattr(routes, "_g", lambda: BomHttpx())
    r = await client.post("/api/v1/tra-cuu", json={"query": "x"})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_loi_postgres_tra_503_nen_thu_lai(client, monkeypatch):
    """Postgres không kết nối được (sqlalchemy.exc.OperationalError) → 503,
    cùng lý do với lỗi httpx: NHẤT THỜI, client nên thử lại."""
    from sqlalchemy.exc import OperationalError

    from src.api import routes

    class BomDb:
        async def ainvoke(self, *a, **k):
            raise OperationalError("statement", {}, Exception("connection refused"))

    monkeypatch.setattr(routes, "_g", lambda: BomDb())
    r = await client.post("/api/v1/tra-cuu", json={"query": "x"})
    assert r.status_code == 503


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
    Mức 2 không bao giờ kích hoạt và nhóm bẫy 'văn bản đã bị thay' fail im lặng.

    Sửa sau silent-failure review round 2: bản cũ chỉ assert TRONG nhánh
    `if result_type == "answer"`, không nhánh else — từ khi phép kiểm thứ bảy
    khiến câu hỏi này (không neo văn bản, mọi nguồn đều bi_thay_the) thường ra
    `abstain`, nhánh `if` không chạy và test PASS mà KHÔNG kiểm gì. Giờ khoá
    cả hai nhánh: `answer` phải có cảnh báo/toàn con_hieu_luc; `abstain` phải
    nêu lý do (không phải từ chối trống rỗng)."""
    from src.agents.graph_tra_cuu import build_graph_tra_cuu

    st = await build_graph_tra_cuu().ainvoke(
        {"query": "mức lương tối thiểu vùng một hiện nay là bao nhiêu"})
    rt = st["result_type"].value
    assert rt in ("answer", "abstain"), f"kỳ vọng answer hoặc abstain cho câu hỏi này, được {rt}"
    if rt == "answer":
        assert any("thay thế" in w or "hết hiệu lực" in w for w in st["warnings"]) or \
            all(c["hieu_luc"] == "con_hieu_luc" for c in st["citations"]), \
            "citation từ văn bản đã bị thay mà không có cảnh báo"
    else:
        assert st["coverage_note"], "abstain phải nêu lý do, không phải từ chối trống rỗng"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_citation_khong_bao_gio_thieu_duong_dan(client):
    d = (await client.post("/api/v1/tra-cuu", json={"query": "thử việc lương bao nhiêu"})).json()
    assert all(c["duong_dan"] and c["so_ky_hieu"] for c in d["citations"])


# ══ H1 (silent-failure review round 2) — khop_tai_id không bị lọc ở biên HTTP ═


@pytest.mark.asyncio
async def test_khop_tai_id_khong_bi_loc_o_bien_HTTP(client, monkeypatch):
    """`CitationOut` từng THIẾU `khop_tai_id` — pydantic (`extra="ignore"` mặc
    định) âm thầm vứt field này ở biên HTTP: response ghép `provision_id` với
    `duong_dan`/`so_ky_hieu` của DÒNG KHÁC (`khop_tai`) mà không trường nào
    nói ra. Ca THƯỜNG, không phải ca biên — 73,6% số Điều chỉ có tiêu đề, xem
    `verify_tier1._cay_con`."""
    from src.agents.nodes.assemble import ResultType
    from src.api import routes

    class FakeGraph:
        async def ainvoke(self, *a, **k):
            return {
                "result_type": ResultType.answer,
                "answer": "x",
                "citations": [{
                    "provision_id": 141418, "khop_tai_id": 141420,
                    "doc_id": "139264",
                    "duong_dan": "45/2019/QH14 > Điều 127 > Khoản 2",
                    "bo_luat": "Bộ Luật lao động", "so_ky_hieu": "45/2019/QH14",
                    "quote": "Phạt tiền...", "hieu_luc": "con_hieu_luc", "tin_cay": "cao",
                }],
                "warnings": [],
            }

    monkeypatch.setattr(routes, "_g", lambda: FakeGraph())
    r = await client.post("/api/v1/tra-cuu", json={"query": "x"})
    assert r.status_code == 200
    c = r.json()["citations"][0]
    assert c["provision_id"] == 141418
    assert c["khop_tai_id"] == 141420
    assert c["doc_id"] == "139264", (
        "cùng một lỗi, cùng một chỗ: thiếu `doc_id` trong CitationOut thì pydantic vứt nó ở "
        "biên HTTP và FE mất khoá DUY NHẤT dựng được URL /van-ban/{doc_id}?around= — "
        "click-to-verify chết mà không lỗi nào nổ"
    )
    assert "Khoản 2" in c["duong_dan"], "duong_dan phải khớp khop_tai_id (dòng THẬT), không phải provision_id"


# ══ HIGH (FastAPI review) — _ghi_traces() không được chặn event loop ═══════


@pytest.mark.asyncio
async def test_ghi_traces_khong_chan_event_loop(client, monkeypatch):
    """`_ghi_traces()` chạy SQLAlchemy ĐỒNG BỘ ngay trong `async def tra_cuu()`,
    NGOÀI graph nên KHÔNG được LangGraph tự offload sang thread (khác các
    node trong graph — LangGraph coerce mỗi `def` đồng bộ thành chạy trong
    threadpool). Dưới tải cao hoặc Postgres chậm, nó chặn TẤT CẢ request khác.
    Ép `_ghi_traces` chậm (giả lập Postgres chậm bằng `time.sleep` — hàm ĐỒNG
    BỘ, blocking thật) rồi đo hai request đồng thời: tổng thời gian phải xấp
    xỉ MỘT lần sleep, không phải hai lần cộng dồn."""
    import asyncio
    import time as time_mod

    from src.agents.nodes.assemble import ResultType
    from src.api import routes

    class FakeGraph:
        async def ainvoke(self, *a, **k):
            return {"result_type": ResultType.abstain, "citations": [], "warnings": []}

    sleep_s = 0.3

    def cham(*a, **k):
        time_mod.sleep(sleep_s)

    monkeypatch.setattr(routes, "_g", lambda: FakeGraph())
    monkeypatch.setattr(routes, "_ghi_traces", cham)

    bat_dau = time_mod.monotonic()
    await asyncio.gather(
        client.post("/api/v1/tra-cuu", json={"query": "a"}),
        client.post("/api/v1/tra-cuu", json={"query": "b"}),
    )
    tong = time_mod.monotonic() - bat_dau
    assert tong < sleep_s * 1.7, (
        f"hai request đồng thời mất {tong:.2f}s — nghi _ghi_traces chặn tuần tự (≈{2 * sleep_s:.2f}s nếu vậy)"
    )


def test_response_model_biet_moi_gia_tri_cua_ResultType():
    """Biên API phải biết MỌI loại kết quả — nếu không, một nhánh đúng ở graph
    thành 500 ở HTTP.

    ĐO ĐƯỢC 2026-09-01: `gioi_thieu` được thêm vào `ResultType` nhưng không
    thêm vào `Literal` của `TraCuuResponse`, nên `/tra-cuu` cho câu "bạn làm
    được những gì" dựng đúng kết quả rồi chết ở khâu tuần tự hoá. Nó lọt vì
    tôi xác minh bằng bảng `traces` — mà traces ghi TRƯỚC response, nên nó
    xanh trong khi HTTP đỏ.

    Test này so hai tập, không liệt kê tay: thêm một loại mới mà quên biên API
    sẽ làm nó đỏ ngay.
    """
    import typing

    from src.agents.nodes.assemble import ResultType
    from src.models.schemas import TraCuuResponse

    o_model = set(typing.get_args(TraCuuResponse.model_fields["result_type"].annotation))
    o_enum = {r.value for r in ResultType}
    assert o_model == o_enum, f"lệch: enum có {o_enum - o_model}, model có {o_model - o_enum}"


@pytest.mark.integration
def test_hoi_ve_kho_di_het_duong_graph_ra_HTTP_khong_ton_mot_token(monkeypatch):
    """Bốn chỗ sync của một `result_type` mới đã sập HAI LẦN vì mỗi test chỉ
    canh được một chỗ. Test này chạy GRAPH THẬT rồi tuần tự hoá bằng ĐÚNG hai
    hàm mà endpoint dùng (`_payload_cache` → `tra_cuu_response`), nên nó bắt cả
    năm chỗ trong một lượt — kể cả chế độ hỏng đặc trưng: traces ghi xanh còn
    HTTP trả 500, vì traces được ghi TRƯỚC khi response được serialize.

    0 token: `route` bị thay bằng một hàm thuần, và `hoi_ve_kho` rẽ tắt ngay sau
    đó nên không node nào gọi LLM. Cái duy nhất thật ở đây là Postgres — đúng
    thứ câu trả lời về kho được dựng từ.
    """
    import src.agents.graph_tra_cuu as g
    from src.agents.nodes.route import Intent
    from src.api.routes import _payload_cache, tra_cuu_response
    from src.services.kho import CAU_GIOI_HAN

    monkeypatch.setattr(g, "route", lambda st, llm, model: {
        **st, "intent": Intent.hoi_ve_kho, "traces": {"route_token_in": 0}})

    st = g.build_graph_tra_cuu().invoke(
        {"query": "hiện tại có bao nhiêu bộ luật?", "as_of_date": None})

    assert st["result_type"] is ResultType.hoi_ve_kho
    assert "Bộ luật: 6" in st["answer"], st["answer"]
    assert CAU_GIOI_HAN in st["answer"]
    assert st["traces"]["assemble_token_in"] == 0

    res = tra_cuu_response(_payload_cache(st, st["result_type"].value), "t", "c")
    assert res.result_type == "hoi_ve_kho" and res.answer == st["answer"]
