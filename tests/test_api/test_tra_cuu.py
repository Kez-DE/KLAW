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
async def test_documents_va_k_song_qua_graph_that_khi_answer():
    """Bẫy đã sập bốn lần: khoá không khai trong KLawState bị `ainvoke` loại âm
    thầm. Chạy graph thật với câu hỏi lao động có căn cứ chắc; nếu ra `answer`
    thì `documents` phải khác rỗng và mọi `k` hợp lệ. Ra `abstain` vì hạ tầng
    (429) thì bỏ qua — test này canh hình dạng, không canh độ phủ."""
    from src.agents.graph_tra_cuu import build_graph_tra_cuu

    st = await build_graph_tra_cuu().ainvoke(
        {"query": "Thời gian thử việc tối đa với công việc cần trình độ cao đẳng là bao lâu?", "lich_su": []}
    )
    rt = st["result_type"].value if hasattr(st["result_type"], "value") else st["result_type"]
    if rt != "answer":
        pytest.skip(f"graph ra {rt} — không đo được hình dạng answer lượt này")
    assert st["documents"], "documents rỗng sau ainvoke — kiểm KLawState.documents"
    k = [c["k"] for c in st["citations"] if c.get("k")]
    assert k == list(range(1, len(k) + 1))
    assert {d["doc_id"] for d in st["documents"]} <= {c["doc_id"] for c in st["citations"]}


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


@pytest.mark.asyncio
async def test_truong_trich_dan_day_du_khong_bi_loc_o_bien_HTTP(client, monkeypatch):
    """Quyết định 2026-09-28 — cùng kiểu hỏng với `khop_tai_id`/`doc_id`: trường
    nào CitationOut/NguonOut không khai thì pydantic vứt câm ở biên HTTP."""
    from src.agents.nodes.assemble import ResultType
    from src.api import routes

    day_du = {
        "ten_van_ban": "Bộ Luật lao động",
        "loai_van_ban": "Bộ luật",
        "co_quan_ban_hanh": "Quốc hội",
        "ngay_ban_hanh": "2019-11-20",
        "ngay_hieu_luc": "2021-01-01",
        "lien_ket": "https://vbpl.vn/van-ban/chi-tiet/139264",
        "cach_trich": "khoản 2 Điều 127 Bộ luật Lao động số 45/2019/QH14 ngày 20/11/2019 của Quốc hội",
    }

    class FakeGraph:
        async def ainvoke(self, *a, **k):
            return {
                "result_type": ResultType.answer,
                "answer": "x",
                "citations": [
                    {
                        **day_du,
                        "provision_id": 141418,
                        "khop_tai_id": 141420,
                        "doc_id": "139264",
                        "duong_dan": "45/2019/QH14 > Điều 127 > Khoản 2",
                        "bo_luat": "Bộ Luật lao động",
                        "so_ky_hieu": "45/2019/QH14",
                        "quote": "Phạt tiền...",
                        "hieu_luc": "mot_phan_khong_xac_dinh",
                        "tin_cay": "thap",
                        "canh_bao": "45/2019/QH14 hết hiệu lực một phần: bị 71/2025/QH15 sửa",
                    }
                ],
                "warnings": ["45/2019/QH14 hết hiệu lực một phần: bị 71/2025/QH15 sửa"],
                "documents": [
                    {
                        **day_du,
                        "doc_id": "139264",
                        "ten": "Bộ Luật lao động",
                        "so_ky_hieu": "45/2019/QH14",
                        "loai_van_ban": "Bộ luật",
                    }
                ],
            }

    monkeypatch.setattr(routes, "_g", lambda: FakeGraph())
    r = await client.post("/api/v1/tra-cuu", json={"query": "x"})
    assert r.status_code == 200
    j = r.json()
    c, d = j["citations"][0], j["documents"][0]
    assert {k: c[k] for k in day_du} == day_du and {k: d[k] for k in day_du} == day_du
    assert c["canh_bao"] == j["warnings"][0]


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


def test_moi_field_TraCuuResponse_deu_duoc_KLawState_khai():
    """Phép canh CHUNG (fix round 1, finding 1) — cùng tinh thần test ngay
    trên, nhưng cho lớp lỗi RỘNG hơn: `KLawState` là `TypedDict` làm SCHEMA
    KÊNH của LangGraph, nên một field `TraCuuResponse` cần đọc từ state mà
    quên khai ở đây sẽ bị `.invoke()`/`.ainvoke()` LOẠI ÂM THẦM — dự án đã bị
    cắn bởi đúng lớp lỗi này BỐN lần trên bốn field khác nhau (`khop_tai_id`,
    `doc_id`, `bang`, và `nguon` — round 1 này sửa `nguon`).

    So HAI TẬP, không liệt kê tay: mọi field của `TraCuuResponse` phải nằm
    trong tập khoá `KLawState` khai (rẻ — chỉ introspect hai class, không cần
    Postgres/LLM) — thêm field mới vào response mà quên khai ở state sẽ làm
    test này đỏ ngay, thay vì im lặng cho tới khi ai đó đo được trên HTTP thật.
    """
    from src.agents.state import KLawState
    from src.models.schemas import TraCuuResponse

    can = set(TraCuuResponse.model_fields)
    khai = set(KLawState.__annotations__)
    # Trường response đổi tên so với khoá state: nêu ĐÍCH DANH ở đây, và khoá
    # state tương ứng vẫn phải được KLawState khai — LangGraph vẫn rơi nó nếu không.
    alias = {"soan_thao": "soan_thao_goi_y"}
    thieu = {f for f in can if alias.get(f, f) not in khai}
    assert not thieu, (
        f"TraCuuResponse cần field {thieu} nhưng KLawState chưa khai — "
        "LangGraph sẽ loại âm thầm khỏi state trả về của invoke()/ainvoke()"
    )


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

    monkeypatch.setattr(g, "route", lambda st, llm, model, prompt_path=None: {
        **st, "intent": Intent.hoi_ve_kho, "traces": {"route_token_in": 0}})

    st = g.build_graph_tra_cuu().invoke(
        {"query": "hiện tại có bao nhiêu bộ luật?", "as_of_date": None})

    assert st["result_type"] is ResultType.hoi_ve_kho
    assert "Bộ luật: 6" in st["answer"], st["answer"]
    assert CAU_GIOI_HAN in st["answer"]
    assert st["traces"]["assemble_token_in"] == 0

    res = tra_cuu_response(_payload_cache(st, st["result_type"].value), "t", "c")
    assert res.result_type == "hoi_ve_kho" and res.answer == st["answer"]


@pytest.mark.integration
def test_hoi_ve_kho_xin_bang_di_het_duong_graph_ra_HTTP_khong_ton_mot_token(monkeypatch):
    """T4 — cùng khuôn test ngay trên, cho nhánh XIN BẢNG: `bang` phải KHÔNG
    rỗng và `answer` phải là câu dẫn ngắn, không phải bài văn xuôi đầy đủ như
    nhánh không xin bảng (test ngay trên, `answer` chứa "Bộ luật: 6")."""
    import src.agents.graph_tra_cuu as g
    from src.agents.nodes.route import Intent
    from src.api.routes import _payload_cache, tra_cuu_response
    from src.services.kho import CAU_GIOI_HAN

    monkeypatch.setattr(g, "route", lambda st, llm, model, prompt_path=None: {
        **st, "intent": Intent.hoi_ve_kho, "traces": {"route_token_in": 0}})

    st = g.build_graph_tra_cuu().invoke(
        {"query": "cho tôi bảng hiển thị các văn bản trong kho", "as_of_date": None})

    assert st["result_type"] is ResultType.hoi_ve_kho
    assert CAU_GIOI_HAN in st["answer"]
    assert st["traces"]["assemble_token_in"] == 0
    assert len(st["bang"]) == 2, st["bang"]
    assert [b["tieu_de"] for b in st["bang"]] == [
        "Phân theo loại văn bản", "Phân theo lĩnh vực"]

    res = tra_cuu_response(_payload_cache(st, st["result_type"].value), "t", "c")
    assert len(res.bang) == 2
    assert res.bang[0].cot == ["Loại văn bản", "Tổng", "Có toàn văn", "Chỉ có số hiệu và tên"]
    assert res.bang[1].cot == ["Lĩnh vực", "Số văn bản", "Độ sâu"]


@pytest.mark.integration
def test_hoi_ve_kho_xin_bang_luot_noi_tiep_doc_cau_da_giai_nghia(monkeypatch):
    """Fix round 1, finding 2 — test T4 ngay trên gọi graph với `lich_su` RỖNG
    (lượt đầu): `giai_nghia` không chạy, `cau_hoi_day_du` giữ `None`, và
    `n_assemble` chỉ đi qua NỬA biểu thức
    `cau_hoi = st.get("cau_hoi_day_du") or st["query"]` (`graph_tra_cuu.py`,
    trong `n_assemble`) — nửa `st["query"]`. Đúng ca brief mở đầu (câu NỐI TIẾP,
    ý "bảng" chỉ lộ ra sau khi giải nghĩa) chưa hề được đi qua graph thật.

    Ép lượt NỐI TIẾP bằng cách khống chế `giai_nghia` trả `cau_hoi_day_du` mang
    ý "bảng" trong khi CỐ Ý giữ nguyên `query` KHÔNG khớp cụm kích hoạt nào —
    khác chính hành vi `giai_nghia` thật (nó đồng bộ `query` = `cau_hoi_day_du`
    khi giải nghĩa thành công). Tách hai giá trị ra để pin đúng dòng mã đọc
    `cau_hoi_day_du` TRƯỚC — nếu test dựa vào bất biến đồng bộ đó (để `query`
    tự nhiên bằng `cau_hoi_day_du`), một bug xoá mất ưu tiên đọc
    `cau_hoi_day_du` vẫn có thể lọt qua vì `query` tình cờ đúng."""
    import src.agents.graph_tra_cuu as g
    from src.agents.nodes.route import Intent
    from src.api.routes import _payload_cache, tra_cuu_response

    cau_da_giai_nghia = ("Đưa cho tôi bảng hiển thị 130 văn bản pháp lý trong kho "
                        "của KLAW để xem dễ hơn")

    def fake_giai_nghia(st, llm, model):
        return {**st, "cau_hoi_goc": st["query"], "cau_hoi_day_du": cau_da_giai_nghia,
                "traces": {**(st.get("traces") or {}), "giai_nghia_token_in": 0}}

    monkeypatch.setattr(g, "giai_nghia", fake_giai_nghia)
    monkeypatch.setattr(g, "route", lambda st, llm, model, prompt_path=None: {
        **st, "intent": Intent.hoi_ve_kho, "traces": {"route_token_in": 0}})

    st = g.build_graph_tra_cuu().invoke({
        # KHÔNG khớp cụm kích hoạt nào — chỉ câu ĐÃ giải nghĩa mới khớp
        # ("bảng hiển thị"/"xem dễ hơn"); xem `xin_dang_bang` (services/kho.py).
        "query": "cho tôi xem cho dễ",
        "lich_su": [{"cau_hoi": "kho có bao nhiêu văn bản?",
                     "tra_loi": "Kho hiện có 130 văn bản.", "duong_dan": []}],
        "as_of_date": None,
    })

    assert st["result_type"] is ResultType.hoi_ve_kho
    assert st["query"] == "cho tôi xem cho dễ", "test tự kiểm: fake giai_nghia không sửa query"
    assert len(st["bang"]) == 2, (
        f"bang rỗng — n_assemble đang đọc st['query'] (không khớp cụm nào) thay vì "
        f"st['cau_hoi_day_du'] (khớp 'bảng hiển thị'/'xem dễ hơn'): {st['bang']}"
    )

    res = tra_cuu_response(_payload_cache(st, st["result_type"].value), "t", "c")
    assert len(res.bang) == 2


@pytest.mark.integration
def test_partial_coverage_giu_duoc_nguon_di_het_duong_graph_ra_HTTP(monkeypatch):
    """Fix round 1, finding 1 — `nguon` mang ĐÚNG lỗi mất khoá ở biên LangGraph
    như `bang` (T4) đã đo: `KLawState` không khai `nguon` nên `.invoke()` loại
    âm thầm khỏi state trả về, dù `assemble()` gọi riêng (test đơn vị
    `test_partial_coverage_mang_nguon_co_doc_id_de_mo_duoc_van_ban` ở
    test_assemble.py) đã set đúng khoá này — test đó gọi `assemble()` TRỰC
    TIẾP, hàm thuần, nên không thể thấy chỗ mất ở biên `.invoke()`.

    Cùng khuôn hai test `hoi_ve_kho` ngay trên: khống chế `route`/`rewrite_query`
    /`Retriever` để ép nhánh `partial_coverage` một cách XÁC ĐỊNH (không phụ
    thuộc nội dung corpus đang nạp song song) — `expand` bị thay để trả đúng
    `expanded=[]`, `hits_shallow=[...]`, tái hiện chính điều kiện
    `not deep and shallow` mà `assemble._phu_mot_phan` xét. `hoi_lai` (nửa sau
    của mọi ngõ cụt) vẫn gọi LLM thật theo thiết kế (partial_coverage không còn
    0 token từ Pha 2) — khống chế luôn `llm_from_settings` để test không phụ
    thuộc mạng/API key, cùng lý do khống chế `route` ở hai test trên."""
    import json

    import src.agents.graph_tra_cuu as g
    from src.agents.nodes.route import Intent
    from src.api.routes import _payload_cache, tra_cuu_response
    from src.services.llm import Usage

    class FakeLlmHoiLai:
        def chat(self, model, messages, json_schema=None):
            return json.dumps({"chieu": [{"ma": "chu_the", "cau": "Bạn ở phía nào?"}]}), Usage(1, 1, 0.0)

    monkeypatch.setattr(g, "llm_from_settings", lambda: FakeLlmHoiLai())
    monkeypatch.setattr(g, "route", lambda st, llm, model, prompt_path=None: {
        **st, "intent": Intent.tra_cuu, "traces": {"route_token_in": 0}})
    monkeypatch.setattr(g, "rewrite_query", lambda st, llm, model, prompt_path=None: {**st, "queries": [st["query"]]})
    monkeypatch.setattr(g.Retriever, "hybrid", lambda self, q: [])
    monkeypatch.setattr(g.Retriever, "provision_ids", lambda self, hits: [])
    monkeypatch.setattr(g, "expand", lambda before, engine, as_of, hops: (
        [], [{"id": 5, "document_id": "84265", "duong_dan": "84/2015/QH13 > Điều 3",
              "so_ky_hieu": "84/2015/QH13", "ten": "Luật An toàn, vệ sinh lao động"}]))

    st = g.build_graph_tra_cuu().invoke(
        {"query": "an toàn lao động quy định thế nào", "as_of_date": None})

    assert st["result_type"] is ResultType.partial_coverage
    # Trường trích dẫn đầy đủ (quyết định 2026-09-28) là THÊM; ba khoá cũ giữ nguyên.
    assert [{k: n[k] for k in ("doc_id", "so_ky_hieu", "bo_luat")} for n in st["nguon"]] == [
        {"doc_id": "84265", "so_ky_hieu": "84/2015/QH13", "bo_luat": "Luật An toàn, vệ sinh lao động"}
    ], st["nguon"]

    res = tra_cuu_response(_payload_cache(st, st["result_type"].value), "t", "c")
    assert len(res.nguon) == 1
    assert res.nguon[0].doc_id == "84265"


def test_tra_cuu_response_bang_mac_dinh_rong_khi_payload_cu_thieu_khoa():
    """T4 — một dòng `answer_cache` ghi TRƯỚC khi `bang` tồn tại không có khoá
    này trong JSON (cùng lớp với `cau_hoi_day_du` ngay dưới nó ở
    `tra_cuu_response`). Phải dựng được response mà không `KeyError` — `bang`
    mặc định rỗng, không phải một cache hit hoá thành HTTP 500."""
    from src.api.routes import tra_cuu_response

    payload_cu = {
        "result_type": "hoi_ve_kho", "answer": "Trong kho của mình…",
        "citations": [], "warnings": [], "coverage_note": None, "nguon": [],
    }
    res = tra_cuu_response(payload_cu, "t", "c")
    assert res.bang == []


def test_payload_cache_va_tra_cuu_response_giu_nguyen_bang():
    """T4 — vòng tròn `_payload_cache` → `tra_cuu_response` (đúng hai hàm
    endpoint dùng) giữ nguyên `bang`, và pydantic tự dựng lại `list[Bang]` từ
    `list[dict]` — cùng cách `citations` đã làm."""
    from src.api.routes import _payload_cache, tra_cuu_response

    st = {
        "result_type": "hoi_ve_kho", "answer": "Mình dựng hai bảng…",
        "citations": [], "warnings": [], "coverage_note": None, "nguon": [],
        "bang": [{"tieu_de": "Phân theo loại văn bản",
                  "cot": ["Loại văn bản", "Tổng"], "dong": [["Luật", "1"]]}],
    }
    payload = _payload_cache(st, "hoi_ve_kho")
    res = tra_cuu_response(payload, "t", "c")
    assert len(res.bang) == 1
    assert res.bang[0].tieu_de == "Phân theo loại văn bản"
    assert res.bang[0].dong == [["Luật", "1"]]


def test_FE_biet_moi_gia_tri_ResultType_cua_backend():
    """Điểm đồng bộ thứ BẢY, và nó ở phía FE.

    ĐO ĐƯỢC 2026-09-02 trên UI thật: câu "các bộ luật hiện có là" cho backend trả
    `hoi_ve_kho` THÀNH CÔNG — trace 8e32221d, 6.490ms, ghi đủ vào bảng `traces` —
    nhưng người hỏi nhận "Máy chủ trả về dữ liệu không đúng hình dạng đã thoả
    thuận nên không hiển thị được". Nguyên nhân: `LOAI_KET_QUA` trong
    `frontend/src/lib/klaw.ts` chỉ có năm giá trị, nên `laTraCuuKetQua` từ chối cả
    response.

    `huong_dan_soan_thao` cũng thiếu ở đó — đường bàn giao sang soạn thảo đã hỏng
    trên FE từ TRƯỚC đợt này, không ai biết.

    Đúng chế độ hỏng đã xảy ra ba lần trong dự án: traces xanh, HTTP xanh, FE đỏ.
    Spec đợt này ghi "FE không cần nhánh mới vì `hoi_ve_kho` mang `answer` nên rơi
    đúng nhánh mặc định" — đúng về RENDER, sai về KIỂM HÌNH DẠNG. Hai test so-hai-
    tập đã có (`ResultType` vs `Literal`, `Intent` vs `INTENT_SCHEMA`) đều nằm
    trong Python nên không cái nào thấy được biên này.

    Test đọc thẳng file `.ts`, KHÔNG nhân bản danh sách sang một fixture thứ hai —
    một bản sao thứ ba sẽ lệch pha đúng vào ngày ai đó thêm loại thứ tám.
    """
    import re
    from pathlib import Path

    from src.agents.nodes.assemble import ResultType

    ts = Path(__file__).resolve().parents[2] / "frontend/src/lib/klaw.ts"
    assert ts.exists(), f"không thấy {ts} — thư mục frontend đã đổi tên?"
    noi_dung = ts.read_text(encoding="utf-8")

    khoi = re.search(r"const LOAI_KET_QUA: readonly string\[\] = \[(.*?)\];", noi_dung, re.S)
    assert khoi, "không tìm thấy LOAI_KET_QUA trong klaw.ts — đổi tên biến?"
    o_fe = set(re.findall(r'"([a-z_]+)"', khoi.group(1)))
    o_be = {r.value for r in ResultType}

    assert o_be == o_fe, (
        f"thiếu ở FE: {sorted(o_be - o_fe)}; lạ ở FE: {sorted(o_fe - o_be)}"
    )

    # Union `ResultType` của TypeScript cũng phải biết, không chỉ danh sách runtime:
    # thiếu ở union thì `tsc` không cảnh báo chỗ nào quên xử lý loại mới.
    thieu_union = [v for v in o_be if f'"{v}"' not in noi_dung.split("const LOAI_KET_QUA")[0]]
    assert not thieu_union, f"thiếu trong union ResultType của TS: {sorted(thieu_union)}"


async def test_k_va_documents_khong_bi_loc_o_bien_HTTP(client, monkeypatch):
    """Spec 2026-09-06 §3.2: hai trường mới của thẻ bấm được phải sống qua
    pydantic ở biên HTTP — cùng lớp lỗi `khop_tai_id`/`doc_id`/`bang`/`nguon`."""
    from src.agents.nodes.assemble import ResultType
    from src.api import routes

    class FakeGraph:
        async def ainvoke(self, *a, **k):
            return {
                "result_type": ResultType.answer,
                "answer": "x [Điều 127](cite:1)",
                "citations": [{
                    "provision_id": 141418, "khop_tai_id": 141420, "doc_id": "139264",
                    "duong_dan": "45/2019/QH14 > Điều 127 > Khoản 2",
                    "bo_luat": "Bộ Luật lao động", "so_ky_hieu": "45/2019/QH14",
                    "quote": "Phạt tiền...", "hieu_luc": "con_hieu_luc", "tin_cay": "cao",
                    "k": 1,
                }],
                "warnings": [],
                "documents": [{
                    "doc_id": "139264", "ten": "Bộ Luật lao động",
                    "so_ky_hieu": "45/2019/QH14", "loai_van_ban": "Bộ luật",
                    "links": {"vbpl": "https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=139264",
                              "chinhphu": None, "tvpl": None},
                }],
            }

    monkeypatch.setattr(routes, "_g", lambda: FakeGraph())
    r = await client.post("/api/v1/tra-cuu", json={"query": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body["citations"][0]["k"] == 1
    assert body["documents"][0]["doc_id"] == "139264"
    assert body["documents"][0]["links"]["vbpl"].startswith("https://vbpl.vn/")
    assert body["documents"][0]["links"]["tvpl"] is None


def test_tra_cuu_response_chap_nhan_payload_cache_cu_khong_co_k_va_documents():
    """Một dòng `answer_cache` ghi TRƯỚC bản này không có `documents` và
    citation không có `k` — phải dựng được, không 500 cho tới hết TTL."""
    from src.api.routes import tra_cuu_response

    payload = {
        "result_type": "answer", "answer": "x", "warnings": [], "coverage_note": None,
        "nguon": [],
        "citations": [{
            "provision_id": 1, "khop_tai_id": 1, "doc_id": "139264",
            "duong_dan": "45/2019/QH14 > Điều 1", "bo_luat": "B", "so_ky_hieu": "45/2019/QH14",
            "quote": "q",
        }],
    }
    r = tra_cuu_response(payload, "trace", "full")
    assert r.documents == []
    assert r.citations[0].k is None


async def test_soan_thao_goi_y_khong_bi_loc_o_bien_HTTP(client, monkeypatch):
    """Spec 2026-09-06 (soạn thảo trong chat) §4.3: gợi ý loại văn bản phải
    sống qua pydantic ở biên — cùng lớp lỗi khop_tai_id/doc_id/bang/nguon/documents."""
    from src.agents.nodes.assemble import ResultType
    from src.api import routes

    class FakeGraph:
        async def ainvoke(self, *a, **k):
            return {
                "result_type": ResultType.huong_dan_soan_thao, "answer": "Tôi hiểu bạn cần đơn xin nghỉ việc.",
                "citations": [], "warnings": [],
                "soan_thao_goi_y": {
                    "loai": "don_xin_nghi_viec", "ten": "đơn xin nghỉ việc", "ly_do": "bạn là người lao động muốn nghỉ",
                    "thay_the": [{"loai": "thoa_thuan_cham_dut_hdld", "ten": "thoả thuận chấm dứt hợp đồng lao động"}],
                    "ho_tro": True,
                },
            }

    monkeypatch.setattr(routes, "_g", lambda: FakeGraph())
    r = await client.post("/api/v1/tra-cuu", json={"query": "soạn cho tôi đơn nghỉ việc"})
    assert r.status_code == 200
    gy = r.json()["soan_thao"]
    assert gy["loai"] == "don_xin_nghi_viec" and gy["ho_tro"] is True
    assert gy["thay_the"][0]["loai"] == "thoa_thuan_cham_dut_hdld"


def test_tra_cuu_response_chap_nhan_payload_cache_cu_khong_co_soan_thao():
    from src.api.routes import tra_cuu_response

    payload = {"result_type": "huong_dan_soan_thao", "answer": "x", "warnings": [],
               "coverage_note": None, "nguon": [], "citations": []}
    assert tra_cuu_response(payload, "t", "full").soan_thao is None
