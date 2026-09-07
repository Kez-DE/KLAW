"""`POST /api/v1/tra-cuu/luong` — SSE phát BƯỚC THẬT (Pha 2, nhóm B).

## Phán quyết: stream BƯỚC, không stream token

Graph chạy `route → tien_de → rewrite → retrieve → expand → generate → tier1 →
tier2 → assemble`, và văn xuôi chỉ sinh ở bước CUỐI. Stream token vì vậy cho
đúng một trải nghiệm: **im lặng ~50 giây rồi chảy chữ ~10 giây** (p95 đo được
50.289ms trên 204 dòng traces) — tệ hơn cả chỉ báo bước hiện có, vì nó thay một
thanh tiến trình bằng một màn hình trắng.

Stream bước biến chỉ báo "ước lượng theo thời gian" mà giao diện đang phải nói
dối thành tiến trình THẬT: mỗi node xong phát một sự kiện, kèm con số đã tính
được ở bước đó (bao nhiêu điều khoản truy hồi, bao nhiêu claim qua tầng 1).

## Hai bất biến khoá ở đây

1. **`POST /tra-cuu` KHÔNG đổi.** `eval/run.py` gọi nó và bảng số liệu khoá luận
   phụ thuộc nó; đường SSE là đường SONG SONG, không phải bản thay thế.
2. **Client rời giữa chừng KHÔNG làm mất dòng `traces`.** LLM đã tiêu tiền rồi.
   Nếu socket đóng huỷ luôn graph thì mọi lượt bị bấm Huỷ là một lượt MIỄN PHÍ —
   và hạn mức ngày/tháng (`bao_ve.dem_luot` đếm chính bảng `traces`) trở thành
   trang trí. Graph chạy trong task riêng, không phải con của request.
"""

import asyncio
import json

import pytest

from src.agents.nodes.assemble import ResultType

_CAU_HOI = {"query": "thử việc tối đa bao nhiêu ngày"}

_TRANG_THAI_CUOI = {
    "result_type": ResultType.answer,
    "answer": "Tối đa 60 ngày.",
    "citations": [],
    "nguon": [],
    "warnings": [],
    "coverage_note": None,
    "traces": {},
}


class GraphGiaLap:
    """Phát đúng hình dạng LangGraph `astream(stream_mode="updates")`:
    `{ten_node: state_sau_node}`. Mọi node thật trong `graph_tra_cuu` trả
    `{**st, ...}` (state ĐẦY ĐỦ), nên bản giả cũng vậy."""

    NODES = ("route", "tien_de", "rewrite", "retrieve", "expand",
             "generate", "tier1", "tier2", "assemble")

    def __init__(self, nodes=None):
        self.nodes = nodes or self.NODES

    async def ainvoke(self, *a, **k):
        return dict(_TRANG_THAI_CUOI)

    async def astream(self, *a, **k):
        st = {}
        for ten in self.nodes:
            st = {**st, "retrieved": [1, 2, 3]} if ten == "retrieve" else st
            if ten == "assemble":
                st = {**st, **_TRANG_THAI_CUOI}
            yield {ten: dict(st)}


async def doc_sse(client, json_body=None, **kw):
    """Đọc cả stream thành `[(event, data_dict), ...]`."""
    ra = []
    ten = None
    async with client.stream(
        "POST", "/api/v1/tra-cuu/luong", json=json_body or _CAU_HOI, **kw
    ) as r:
        if r.status_code != 200:
            await r.aread()
            return r.status_code, []
        async for dong in r.aiter_lines():
            if dong.startswith("event: "):
                ten = dong[7:].strip()
            elif dong.startswith("data: "):
                ra.append((ten, json.loads(dong[6:])))
        return r.status_code, ra


@pytest.fixture
def graph_gia_lap(monkeypatch):
    from src.api import routes

    monkeypatch.setattr(routes, "_g", lambda: GraphGiaLap())
    ghi = []
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: ghi.append(a))
    return ghi


# ══ Ca thường ═══════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_phat_du_chin_buoc_that_theo_dung_thu_tu(client, graph_gia_lap):
    ma, sk = await doc_sse(client)
    assert ma == 200

    assert sk[0][0] == "bat_dau", "client cần trace_id và danh sách bước NGAY, trước 50 giây chờ"
    buoc = [d["buoc"] for e, d in sk if e == "buoc"]
    assert buoc == list(GraphGiaLap.NODES), (
        "phát đúng node THẬT của graph, không phải một danh sách trang trí"
    )
    assert sk[-1][0] == "ket_qua"


@pytest.mark.asyncio
async def test_bat_dau_neu_truoc_toan_bo_danh_sach_buoc(client, graph_gia_lap):
    """Không có danh sách này thì FE lại phải ước lượng — đúng thứ endpoint sinh
    ra để thay thế."""
    _, sk = await doc_sse(client)
    d = sk[0][1]
    assert d["trace_id"]
    assert d["config_name"]
    assert [b["buoc"] for b in d["cac_buoc"]] == list(GraphGiaLap.NODES)
    assert all(b["nhan"] for b in d["cac_buoc"]), "mỗi bước phải có nhãn tiếng Việt"


@pytest.mark.asyncio
async def test_moi_buoc_mang_thu_tu_va_tong_de_ve_thanh_tien_trinh(client, graph_gia_lap):
    _, sk = await doc_sse(client)
    cac_buoc = [d for e, d in sk if e == "buoc"]
    assert [b["thu_tu"] for b in cac_buoc] == list(range(1, len(GraphGiaLap.NODES) + 1))
    assert {b["tong"] for b in cac_buoc} == {len(GraphGiaLap.NODES)}


@pytest.mark.asyncio
async def test_buoc_mang_con_so_da_tinh_duoc_khong_chi_ten(client, graph_gia_lap):
    """"Truy hồi điều khoản — 3 điều khoản" là tiến trình; "Truy hồi điều khoản"
    một mình vẫn là một cái tên không nói gì về việc đã xong tới đâu."""
    _, sk = await doc_sse(client)
    retrieve = next(d for e, d in sk if e == "buoc" and d["buoc"] == "retrieve")
    assert retrieve["chi_tiet"] == {"so_dieu_khoan": 3}


@pytest.mark.asyncio
async def test_ket_qua_dung_shape_TraCuuResponse(client, graph_gia_lap):
    _, sk = await doc_sse(client)
    d = sk[-1][1]
    for t in ("result_type", "answer", "citations", "nguon", "warnings",
              "coverage_note", "trace_id", "config_name"):
        assert t in d, f"thiếu {t} — FE không dùng lại được bộ xử lý của POST /tra-cuu"
    assert d["result_type"] == "answer"
    assert d["answer"] == "Tối đa 60 ngày."


@pytest.mark.asyncio
async def test_content_type_la_text_event_stream(client, graph_gia_lap):
    async with client.stream("POST", "/api/v1/tra-cuu/luong", json=_CAU_HOI) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        # Proxy đệm cả stream là biến SSE thành một response bình thường đến
        # muộn — mất trắng lý do endpoint này tồn tại.
        assert r.headers.get("cache-control") == "no-cache"
        assert r.headers.get("x-accel-buffering") == "no"
        await r.aread()


@pytest.mark.asyncio
async def test_ghi_dung_MOT_dong_traces(client, graph_gia_lap):
    await doc_sse(client)
    assert len(graph_gia_lap) == 1
    assert graph_gia_lap[0][1] == "/api/v1/tra-cuu"


# ══ POST /tra-cuu KHÔNG đổi ═════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_duong_POST_cu_van_dung_ainvoke_va_tra_cung_payload(client, monkeypatch):
    """Đường SSE là SONG SONG, không phải bản thay thế. `eval/run.py` gọi POST."""
    from src.api import routes

    g = GraphGiaLap()
    da_stream = []
    goc = g.astream

    def astream_ghi(*a, **k):
        da_stream.append(1)
        return goc(*a, **k)

    g.astream = astream_ghi
    monkeypatch.setattr(routes, "_g", lambda: g)
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)

    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI)
    assert r.status_code == 200
    assert r.json()["answer"] == "Tối đa 60 ngày."
    assert not da_stream, "POST phải dùng ainvoke — đường eval không được đổi cơ chế"


# ══ Ca rẽ nhánh: cache hit ══════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_cache_hit_phat_mot_buoc_cache_khong_gia_vo_chay_chin_node(
    client, graph_gia_lap, monkeypatch
):
    """Giả vờ chạy 9 node cho một lượt 3ms là dựng một thanh tiến trình bịa."""
    from src.api import routes
    from src.services import cache_tra_loi

    payload = {"result_type": "answer", "answer": "từ bộ đệm", "citations": [],
               "warnings": [], "coverage_note": None, "nguon": []}
    monkeypatch.setattr(
        cache_tra_loi, "tra_cache", lambda *a, **k: ("khoa", "checksum", payload))
    monkeypatch.setattr(routes, "_g", lambda: None)  # nổ nếu graph bị gọi

    _, sk = await doc_sse(client)
    buoc = [d["buoc"] for e, d in sk if e == "buoc"]
    assert buoc == ["cache"]
    assert sk[-1][1]["answer"] == "từ bộ đệm"


# ══ Ca lỗi ══════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_graph_no_thi_phat_su_kien_loi_KHONG_dong_stream_im_lang(client, monkeypatch):
    """Stream chết im lặng đọc y hệt một câu trả lời rất chậm. Client phải nhận
    một sự kiện có KIỂU để phân biệt và hiện đúng thông báo."""
    from src.api import routes

    class Bom:
        async def astream(self, *a, **k):
            raise RuntimeError("rò rỉ: OPENROUTER_API_KEY=sk-khong-duoc-lo")
            yield  # pragma: no cover  (biến hàm thành async generator)

    monkeypatch.setattr(routes, "_g", lambda: Bom())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)

    ma, sk = await doc_sse(client)
    assert ma == 200, "lỗi giữa stream không đổi được mã HTTP đã gửi"
    loi = [d for e, d in sk if e == "loi"]
    assert loi and loi[0]["status"] == 500
    assert "RuntimeError" in loi[0]["detail"]
    assert "sk-khong-duoc-lo" not in json.dumps(sk), "response chỉ mang TÊN loại lỗi"


@pytest.mark.asyncio
async def test_loi_ha_tang_nhat_thoi_phat_status_503(client, monkeypatch):
    import httpx

    from src.api import routes

    class Bom:
        async def astream(self, *a, **k):
            raise httpx.TransportError("connection refused")
            yield  # pragma: no cover

    monkeypatch.setattr(routes, "_g", lambda: Bom())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)

    _, sk = await doc_sse(client)
    assert [d for e, d in sk if e == "loi"][0]["status"] == 503


# ══ Tham số sai ═════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_query_rong_tra_422_truoc_khi_mo_stream(client):
    ma, sk = await doc_sse(client, json_body={"query": ""})
    assert ma == 422
    assert sk == []


@pytest.mark.asyncio
async def test_as_of_date_sai_dinh_dang_tra_422(client):
    ma, _ = await doc_sse(client, json_body={"query": "x", "as_of_date": "31-12-2026"})
    assert ma == 422


# ══ Bất biến đắt nhất: client rời giữa chừng vẫn bị tính tiền ═══════════════


@pytest.mark.asyncio
async def test_client_roi_giua_chung_VAN_ghi_traces(monkeypatch):
    """LLM đã tiêu tiền trước khi người dùng bấm Huỷ.

    Nếu socket đóng huỷ luôn graph thì mọi lượt bị huỷ là một lượt MIỄN PHÍ, và
    hạn mức tháng — thứ đếm chính bảng `traces` — trở thành trang trí. Graph
    chạy trong task riêng, không phải con của request.

    Gọi thẳng handler thay vì qua `client.stream`: bất biến cần khoá là "đóng
    body_iterator KHÔNG dừng graph", còn `ASGITransport` của httpx chạy app
    nội tuyến nên nó mô phỏng ngắt kết nối theo cách riêng của nó — test sẽ đo
    hành vi của transport chứ không đo hành vi của endpoint.
    """
    from src.api import routes, routes_luong
    from src.models.schemas import TraCuuRequest

    da_ghi = asyncio.Event()
    cho_client_roi = asyncio.Event()

    class GraphCham(GraphGiaLap):
        async def astream(self, *a, **k):
            yield {"route": {}}
            await cho_client_roi.wait()
            yield {"assemble": dict(_TRANG_THAI_CUOI)}

    monkeypatch.setattr(routes, "_g", lambda: GraphCham())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: da_ghi.set())

    r = await routes_luong.tra_cuu_luong(TraCuuRequest(**_CAU_HOI), None)
    it = r.body_iterator
    assert "bat_dau" in await it.__anext__()
    await it.aclose()                       # client rời ngay sau sự kiện đầu

    cho_client_roi.set()
    await asyncio.wait_for(da_ghi.wait(), timeout=5)


@pytest.mark.asyncio
async def test_task_nen_duoc_giu_tham_chieu_manh(monkeypatch):
    """`asyncio.create_task` chỉ giữ tham chiếu YẾU: một task không được ai giữ
    có thể bị thu gom giữa chừng, và lượt LLM đó biến mất khỏi `traces` đúng
    như thể client đã rời đi."""
    from src.api import routes, routes_luong
    from src.models.schemas import TraCuuRequest

    cho = asyncio.Event()

    class GraphCham(GraphGiaLap):
        async def astream(self, *a, **k):
            await cho.wait()
            yield {"assemble": dict(_TRANG_THAI_CUOI)}

    monkeypatch.setattr(routes, "_g", lambda: GraphCham())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)

    r = await routes_luong.tra_cuu_luong(TraCuuRequest(**_CAU_HOI), None)
    assert len(routes_luong._DANG_CHAY) == 1
    cho.set()
    await r.body_iterator.aclose()
    for t in list(routes_luong._DANG_CHAY):
        await t
    assert routes_luong._DANG_CHAY == set(), "done_callback phải dọn tham chiếu"


# ══ Danh sách bước phải BÁM graph thật, không trôi ══════════════════════════


@pytest.mark.integration
def test_BUOC_TRA_CUU_khop_dung_node_cua_graph_da_compile():
    """Thêm một node vào `build_graph_tra_cuu` mà quên khai ở `BUOC_TRA_CUU` là
    một bước THẬT biến mất khỏi thanh tiến trình — và thanh đó lại thành ước
    lượng, đúng thứ endpoint SSE sinh ra để thay thế. Đổi thứ tự cũng bị bắt:
    `thu_tu` của mỗi sự kiện lấy từ chính danh sách này.
    """
    from src.agents.graph_tra_cuu import build_graph_tra_cuu
    from src.api.routes import BUOC_TRA_CUU

    that = [n for n in build_graph_tra_cuu().get_graph().nodes
            if not n.startswith("__")]
    assert [ten for ten, _ in BUOC_TRA_CUU] == that
