"""Lịch sử hội thoại lên dây: biên HTTP, đường đi trong graph, và cái được ghi
vào `traces`.

Ràng buộc quan trọng nhất ở đây KHÔNG phải một tính năng — nó là `traces.query`.
Cột đó là dữ liệu của chương đánh giá; ghi câu ĐÃ GIẢI NGHĨA vào nó thì người
đọc lại bảng sau này thấy những câu hỏi người dùng chưa từng gõ, và không có
cách nào tách hai loại ra.
"""

import pytest

from src.agents.graph_tra_cuu import _re_sau_giai_nghia, _vao_graph
from src.agents.nodes.assemble import ResultType
from src.api.routes import BUOC_TRA_CUU
from src.models.schemas import LuotTruoc, TraCuuRequest

LICH_SU_JSON = [{
    "cau_hoi": "tôi đang chuẩn bị nghỉ việc",
    "tra_loi": "Thời hạn báo trước phụ thuộc loại hợp đồng. Bảng dưới đây tóm lại.",
    "duong_dan": ["45/2019/QH14 > Điều 35 > Khoản 1"],
}]

DA_GIAI_NGHIA = "liệt kê bảng thời hạn báo trước khi nghỉ việc"


# ══ Đường đi trong graph — khoá TOPO, không cần LLM ═════════════════════════


def test_luot_dau_KHONG_di_qua_giai_nghia():
    """Lượt đầu (lịch sử rỗng) vào thẳng `route`: không một token nào thêm."""
    assert _vao_graph({"query": "x"}) == "route"
    assert _vao_graph({"query": "x", "lich_su": []}) == "route"


def test_luot_noi_tiep_di_qua_giai_nghia_TRUOC_route():
    """Phải TRƯỚC `route`: routing dựa trên câu ĐÃ giải nghĩa — "còn model nào
    khác" sau một lượt `gioi_thieu` là câu hỏi về trợ lý, không phải tra cứu."""
    assert _vao_graph({"query": "liệt kê bảng cho tôi", "lich_su": LICH_SU_JSON}) == "giai_nghia"


def test_giai_nghia_that_bai_di_DUONG_NGO_CUT_da_co():
    """Không dựng đường thứ hai: `cau_hoi_day_du is None` rẽ thẳng sang
    `assemble`, nơi `_ngo_cut` đã ghép sẵn hai nửa (nói cái đã biết + hỏi lại).
    Và nó bỏ qua truy hồi, nên một câu rỗng nội dung không còn khớp nhiễu."""
    assert _re_sau_giai_nghia({"cau_hoi_day_du": None}) == "assemble"
    assert _re_sau_giai_nghia({}) == "assemble", "thiếu khoá thì đi đường an toàn"
    assert _re_sau_giai_nghia({"cau_hoi_day_du": ""}) == "assemble"


def test_giai_nghia_thanh_cong_di_DU_duong_route_va_hai_tang():
    """Nguyên tắc ràng buộc của spec mục 2: lịch sử chỉ làm câu hỏi tự đứng
    được, nó KHÔNG chống đỡ khẳng định nào — nên câu đã giải nghĩa vào `route`
    rồi đi hết truy hồi, tầng 1, tầng 2 như một câu hỏi mới."""
    assert _re_sau_giai_nghia({"cau_hoi_day_du": DA_GIAI_NGHIA}) == "route"


def test_giai_nghia_co_mat_trong_thanh_tien_trinh():
    """`BUOC_TRA_CUU` phải bám graph thật — một bước THẬT vắng ở đây là một bước
    biến mất khỏi thanh tiến trình SSE (test integration khoá hai tập khớp nhau,
    test này khoá phần chạy được không cần Postgres)."""
    ten = [t for t, _ in BUOC_TRA_CUU]
    assert ten[0] == "giai_nghia", f"node đầu vào phải đứng đầu danh sách: {ten}"


# ══ Biên HTTP ═══════════════════════════════════════════════════════════════


def test_lich_su_mac_dinh_rong_nen_client_cu_KHONG_hong():
    assert TraCuuRequest(query="x").lich_su == []


def test_qua_ba_luot_bi_422_o_bien():
    """Trần BA lượt (spec mục 3). Chặn ở biên chứ không cắt im lặng: một client
    gửi 20 lượt đang hiểu sai hợp đồng, và một lỗi 422 nói ra điều đó ngay."""
    with pytest.raises(ValueError):
        TraCuuRequest(query="x", lich_su=[LuotTruoc(**LICH_SU_JSON[0])] * 4)


@pytest.mark.asyncio
async def test_lich_su_duoc_truyen_VAO_graph(client, monkeypatch):
    from src.api import routes

    da_nhan: dict = {}

    class GraphGhiLai:
        async def ainvoke(self, st, *a, **k):
            da_nhan.update(st)
            return {"result_type": ResultType.answer, "answer": "x", "citations": [],
                    "warnings": [], "cau_hoi_day_du": DA_GIAI_NGHIA}

    monkeypatch.setattr(routes, "_g", lambda: GraphGhiLai())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)
    r = await client.post("/api/v1/tra-cuu",
                          json={"query": "liệt kê bảng cho tôi", "lich_su": LICH_SU_JSON})

    assert r.status_code == 200
    assert da_nhan["lich_su"][0]["cau_hoi"] == "tôi đang chuẩn bị nghỉ việc"
    assert da_nhan["query"] == "liệt kê bảng cho tôi", "graph nhận câu GỐC, tự nó giải nghĩa"
    assert r.json()["cau_hoi_day_du"] == DA_GIAI_NGHIA


@pytest.mark.asyncio
async def test_cau_hoi_day_du_mac_dinh_None_khi_graph_khong_dat(client, monkeypatch):
    """Lượt đầu không chạy `giai_nghia` nên khoá này vắng trong state — và một
    dòng cache cũ (ghi trước bản này) cũng vắng nó. Cả hai phải ra `None`, không
    phải KeyError ở khâu tuần tự hoá."""
    from src.api import routes

    class GraphCu:
        async def ainvoke(self, *a, **k):
            return {"result_type": ResultType.answer, "answer": "x", "citations": [],
                    "warnings": []}

    monkeypatch.setattr(routes, "_g", lambda: GraphCu())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)
    r = await client.post("/api/v1/tra-cuu", json={"query": "thử việc bao lâu"})
    assert r.status_code == 200
    assert r.json()["cau_hoi_day_du"] is None


# ══ `traces.query` — câu GỐC, không bao giờ câu đã giải nghĩa ═══════════════


@pytest.mark.asyncio
async def test_traces_ghi_cau_GOC_khong_ghi_cau_da_giai_nghia(client, monkeypatch):
    from src.api import routes

    da_ghi: dict = {}

    class GraphDaGiaiNghia:
        async def ainvoke(self, *a, **k):
            # Đúng thứ node `giai_nghia` làm: THAY `query` để pipeline chạy trên
            # câu đã giải nghĩa, và giữ câu gốc ở `cau_hoi_goc`.
            return {"result_type": ResultType.answer, "answer": "x", "citations": [],
                    "warnings": [], "query": DA_GIAI_NGHIA,
                    "cau_hoi_goc": "liệt kê bảng cho tôi",
                    "cau_hoi_day_du": DA_GIAI_NGHIA}

    def ghi(trace_id, endpoint, query, *a, **k):
        da_ghi["query"] = query

    monkeypatch.setattr(routes, "_g", lambda: GraphDaGiaiNghia())
    monkeypatch.setattr(routes, "_ghi_traces", ghi)
    r = await client.post("/api/v1/tra-cuu",
                          json={"query": "liệt kê bảng cho tôi", "lich_su": LICH_SU_JSON})

    assert r.status_code == 200
    assert da_ghi["query"] == "liệt kê bảng cho tôi", (
        "traces.query phải là câu người dùng THẬT SỰ gõ — ghi câu đã giải nghĩa "
        "làm chương đánh giá đọc thấy những câu hỏi chưa từng tồn tại"
    )


# ══ Cache: khoá dựng từ câu GỐC, nên lượt nối tiếp không được dùng nó ═══════


@pytest.mark.asyncio
async def test_luot_noi_tiep_KHONG_doc_ghi_cache(client, monkeypatch):
    """`khoa_cache` dựng từ `query` gốc, không có lịch sử trong đó. Hai hội thoại
    khác nhau cùng gõ "liệt kê bảng cho tôi" sẽ tra CÙNG một khoá — và người thứ
    hai nhận câu trả lời cho cuộc hội thoại của người thứ nhất."""
    from src.api import routes
    from src.services import cache_tra_loi

    goi: list[str] = []

    def tra_cache(cau_hoi, config_name, as_of):
        goi.append(cau_hoi)
        return "khoa-gia", "checksum", None

    class G:
        async def ainvoke(self, *a, **k):
            return {"result_type": ResultType.answer, "answer": "x", "citations": [],
                    "warnings": []}

    monkeypatch.setattr(cache_tra_loi, "tra_cache", tra_cache)
    monkeypatch.setattr(cache_tra_loi, "ghi_cache",
                        lambda *a, **k: goi.append("GHI"))
    monkeypatch.setattr(routes, "_g", lambda: G())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)

    r = await client.post("/api/v1/tra-cuu",
                          json={"query": "liệt kê bảng cho tôi", "lich_su": LICH_SU_JSON})
    assert r.status_code == 200
    assert goi == [], f"lượt nối tiếp không được chạm cache: {goi}"

    r = await client.post("/api/v1/tra-cuu", json={"query": "liệt kê bảng cho tôi"})
    assert r.status_code == 200
    assert goi[:1] == ["liệt kê bảng cho tôi"], "lượt đầu vẫn phải dùng cache như trước"


# ══ Thanh tiến trình SSE phải đếm bước của LƯỢT NÀY ═════════════════════════


def test_buoc_cua_luot_bo_giai_nghia_o_luot_dau():
    """Lượt đầu là phần lớn lượt. Đếm `giai_nghia` vào tổng của nó cho một thanh
    tiến trình mở màn ở "bước 2/10" với một bước 1 không bao giờ tới — đúng thứ
    thanh tiến trình bịa mà endpoint SSE sinh ra để thay thế."""
    from src.api.routes import BUOC_TRA_CUU, buoc_cua_luot

    dau = buoc_cua_luot(TraCuuRequest(query="x"))
    assert [t for t, _ in dau] == [t for t, _ in BUOC_TRA_CUU if t != "giai_nghia"]

    noi_tiep = buoc_cua_luot(TraCuuRequest(query="x", lich_su=LICH_SU_JSON))
    assert noi_tiep == BUOC_TRA_CUU
    assert [t for t, _ in noi_tiep][0] == "giai_nghia"


@pytest.mark.asyncio
async def test_sse_luot_noi_tiep_phat_giai_nghia_la_buoc_MOT(client, monkeypatch):
    import json as _json

    from src.api import routes

    class G:
        async def astream(self, *a, **k):
            for ten in ("giai_nghia", "route", "assemble"):
                yield {ten: {"result_type": ResultType.answer, "answer": "x",
                             "citations": [], "nguon": [], "warnings": [],
                             "coverage_note": None, "traces": {}}}

    monkeypatch.setattr(routes, "_g", lambda: G())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)

    sk = []
    ten_sk = None
    async with client.stream("POST", "/api/v1/tra-cuu/luong",
                             json={"query": "liệt kê bảng cho tôi",
                                   "lich_su": LICH_SU_JSON}) as r:
        assert r.status_code == 200
        async for dong in r.aiter_lines():
            if dong.startswith("event: "):
                ten_sk = dong[7:].strip()
            elif dong.startswith("data: "):
                sk.append((ten_sk, _json.loads(dong[6:])))

    bat_dau = next(d for e, d in sk if e == "bat_dau")
    assert bat_dau["cac_buoc"][0] == {"buoc": "giai_nghia",
                                      "nhan": "Giải nghĩa câu hỏi nối tiếp", "thu_tu": 1}
    gn = next(d for e, d in sk if e == "buoc" and d["buoc"] == "giai_nghia")
    assert (gn["thu_tu"], gn["tong"]) == (1, len(bat_dau["cac_buoc"]))
