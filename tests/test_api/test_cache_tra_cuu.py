"""Cache câu trả lời `/tra-cuu` — bảng Postgres, KHÔNG Redis.

Cần Postgres (`@pytest.mark.integration`): cache nằm trong DB đúng vì dự án sẽ
scale worker khi deploy thật, và một cache in-process là N cache khác nhau trên
N worker — tức N lần chi phí và N câu trả lời có thể lệch nhau.

Mọi test dọn sạch dòng nó tạo (`don_cache`): một dòng cache còn sót với nội dung
giả lập sẽ được PHỤC VỤ cho request thật kế tiếp cùng câu hỏi.
"""

from datetime import date

import pytest
from sqlalchemy import text

from src.agents.nodes.assemble import ResultType
from src.agents.nodes.verify_tier1 import normalize
from src.config import Settings
from src.services import cache_tra_loi
from src.services.db import get_engine

pytestmark = pytest.mark.integration

_CAU_HOI = "thử việc bao lâu — test cache, không phải câu hỏi thật"


class GraphDem:
    """Đếm số lần graph THẬT SỰ chạy. Đếm, không so nội dung: graph tất định nên
    hai câu trả lời giống nhau KHÔNG chứng minh được lượt hai đã dùng cache."""

    def __init__(self, result_type=ResultType.answer, answer="ba mươi ngày"):
        self.result_type, self.answer, self.goi = result_type, answer, 0

    async def ainvoke(self, *a, **k):
        self.goi += 1
        return {
            "result_type": self.result_type, "answer": self.answer,
            "citations": [], "warnings": [], "coverage_note": None, "nguon": [],
        }


@pytest.fixture
def don_cache():
    """Xoá dòng cache của CÂU HỎI TEST, không phải "mọi dòng mới".

    Xoá theo mốc thời gian (bản đầu của fixture này) cũng dọn luôn dòng do
    server dev đang chạy (`uvicorn --reload`, cùng DATABASE_URL) ghi trong lúc
    test chạy — dọn dữ liệu của người khác để dọn dữ liệu của mình. Khoá theo
    `cau_hoi_chuan` thì phạm vi đúng bằng thứ test này tạo ra.
    """
    yield
    with get_engine().begin() as c:
        c.execute(
            text("DELETE FROM answer_cache WHERE cau_hoi_chuan = :q"),
            {"q": normalize(_CAU_HOI)},
        )


@pytest.fixture
def cache_bat(monkeypatch):
    """Bật cache (TTL 7 ngày) và tắt hai cổng đọc DB — test này kiểm CACHE.
    Suite mặc định TẮT cache; xem `tests/conftest.py`."""
    from src.services import bao_ve

    monkeypatch.setattr(cache_tra_loi, "get_settings", lambda: Settings(_env_file=None, cache_ttl_ngay=7))
    monkeypatch.setattr(
        bao_ve, "get_settings",
        lambda: Settings(_env_file=None, rate_limit_so_luot=0, tran_chi_phi_ngay_usd=0.0),
    )


@pytest.fixture
def graph(monkeypatch):
    """Cài một `GraphDem` cho `/tra-cuu` và trả về nó để test đọc `.goi`."""
    from src.api import routes

    def cai(g):
        monkeypatch.setattr(routes, "_g", lambda: g)
        return g

    return cai


async def test_cache_hit_tra_cung_noi_dung_va_KHONG_goi_LLM(client, graph, don_cache, cache_bat):
    g = graph(GraphDem())

    mot = await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI})
    assert mot.status_code == 200 and g.goi == 1

    hai = await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI})
    assert hai.status_code == 200
    assert g.goi == 1, "cache hit mà graph/LLM vẫn chạy — cache không cắt được lượt gọi nào"
    assert hai.json()["answer"] == mot.json()["answer"]
    assert hai.json()["result_type"] == mot.json()["result_type"]
    assert hai.json()["trace_id"] != mot.json()["trace_id"], (
        "cache hit vẫn là MỘT request — phải có trace_id riêng. Tái dùng trace_id "
        "của lượt đã cache làm bảng traces mất một dòng và số liệu đếm thiếu."
    )


async def test_as_of_date_khac_thi_cache_MISS(client, graph, don_cache, cache_bat):
    """Hiệu lực phụ thuộc `as_of_date` (`expand()` lọc văn bản theo nó). Dùng
    chung câu trả lời cho hai mốc thời gian là trả về HIỆU LỰC SAI — hỏng
    nghiêm trọng hơn hẳn việc chậm thêm 10 giây."""
    g = graph(GraphDem())

    await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI, "as_of_date": "2026-08-31"})
    await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI, "as_of_date": "2020-01-01"})
    assert g.goi == 2, "as_of_date khác mà vẫn cache hit — đang phục vụ hiệu lực của mốc khác"


async def test_bo_nho_KHONG_vao_cache(graph, don_cache, cache_bat):
    """Bộ nhớ phiên (spec 2026-09-09 §6.5): một tóm tắt/hồ sơ khác đi vào state
    của graph cũng làm câu trả lời có thể khác, nên `chay_tra_cuu` không được
    phục vụ cache cho một request mang bộ nhớ — dù cùng `query`, cùng như
    `req.lich_su` đã chặn ở trên."""
    from src.api.routes import chay_tra_cuu
    from src.models.schemas import TraCuuRequest

    g = graph(GraphDem())
    req = TraCuuRequest(query=_CAU_HOI)
    bn = {"tom_tat": "tóm tắt phiên trước", "ho_so": {}}

    await chay_tra_cuu(req, None, "t1", bo_nho=bn)
    await chay_tra_cuu(req, None, "t2", bo_nho=bn)
    assert g.goi == 2, "request mang bộ nhớ mà vẫn cache hit — đang phục vụ câu trả lời của phiên khác"


async def test_abstain_KHONG_vao_cache(client, graph, don_cache, cache_bat):
    """`abstain` là hành vi ĐÚNG, được tính điểm. Nhưng một lần abstain do lỗi
    TẠM (OpenRouter 429, DB chậm) mà bị cache 7 ngày sẽ hoá đá thành "không tìm
    thấy căn cứ" vĩnh viễn cho câu hỏi đó."""
    g = graph(GraphDem(ResultType.abstain, answer=None))

    await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI})
    await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI})
    assert g.goi == 2, "abstain đã bị cache — lượt hai phải chạy lại graph"


async def test_partial_coverage_CO_vao_cache(client, graph, don_cache, cache_bat):
    g = graph(GraphDem(ResultType.partial_coverage))

    await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI})
    r = await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI})
    assert g.goi == 1
    assert r.status_code == 200 and r.json()["result_type"] == "partial_coverage"


async def test_corpus_checksum_doi_thi_cache_MISS(client, graph, monkeypatch, don_cache, cache_bat):
    """Seed lại corpus → cache TỰ hết hiệu lực, không phụ thuộc việc ai đó nhớ
    xoá tay: một câu trả lời trích dẫn điều luật của corpus CŨ là trích dẫn
    không kiểm lại được nữa."""
    g = graph(GraphDem())

    monkeypatch.setattr(cache_tra_loi, "corpus_checksum", lambda as_of=None: "19135:cu")
    await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI})

    monkeypatch.setattr(cache_tra_loi, "corpus_checksum", lambda as_of=None: "19200:moi")
    await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI})
    assert g.goi == 2, "corpus đã đổi mà vẫn cache hit — đang phục vụ câu trả lời của corpus cũ"


async def test_cache_hit_ghi_traces_co_co_phan_biet(client, graph, don_cache, cache_bat):
    """Số liệu đánh giá của khoá luận KHÔNG được lẫn lượt cache vào lượt gọi LLM
    thật: một cache hit có latency ~10ms và cost $0 — trộn vào cùng cột sẽ kéo
    p50 latency và chi phí trung bình xuống một cách vô nghĩa."""
    graph(GraphDem())

    mot = await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI})
    hai = await client.post("/api/v1/tra-cuu", json={"query": _CAU_HOI})

    with get_engine().connect() as c:
        co = dict(c.execute(
            text("SELECT id, cache_hit FROM traces WHERE id = ANY(:ids)"),
            {"ids": [mot.json()["trace_id"], hai.json()["trace_id"]]},
        ).all())
    assert co[mot.json()["trace_id"]] is False
    assert co[hai.json()["trace_id"]] is True


def test_corpus_checksum_doc_duoc_tu_DB_that():
    """Suy từ `count(*)` của `provisions` + `max(crawled_at)` của `documents` —
    hai đại lượng đổi khi và chỉ khi corpus được nạp lại."""
    cs = cache_tra_loi.corpus_checksum()
    assert cs and ":" in cs
    assert cs == cache_tra_loi.corpus_checksum(), "checksum phải tất định trên cùng một corpus"


def test_cache_TAT_thi_KHONG_MOT_truy_van_DB_nao(monkeypatch):
    """TTL 0 = TẮT, và tắt nghĩa là **không chạm DB**, không phải "vẫn hỏi DB
    rồi bỏ kết quả".

    Regression: bản đầu tính `corpus_checksum()` TRƯỚC khi kiểm TTL, nên mỗi
    request vẫn trả một `count(*)` trên 19.135 dòng dù cache đã tắt. Hai hệ quả
    thật: `eval/run.py` (chạy không-cache, đúng cấu hình để đo) phải trả
    round-trip đó mỗi lượt, và MỌI test không-DB của `/tra-cuu` bỗng cần
    Postgres — CI chạy `-m "not integration"` không có Postgres nên đỏ 6 test,
    4 trong đó là test đã tồn tại từ trước. `corpus_checksum` nằm trong danh
    sách chặn dưới đây chính vì nó là hàm đã lọt lần đó.
    """
    monkeypatch.setattr(cache_tra_loi, "get_settings", lambda: Settings(_env_file=None, cache_ttl_ngay=0))

    def khong_duoc_goi(*a, **k):
        raise AssertionError("cache đã TẮT mà vẫn chạm DB")

    monkeypatch.setattr(cache_tra_loi, "_doc_dong", khong_duoc_goi)
    monkeypatch.setattr(cache_tra_loi, "_ghi_dong", khong_duoc_goi)
    monkeypatch.setattr(cache_tra_loi, "corpus_checksum", khong_duoc_goi)

    assert cache_tra_loi.tra_cache("q", "full", date(2026, 8, 31)) == (None, None, None)
    cache_tra_loi.ghi_cache("khoa-bat-ky", "q", "full", date(2026, 8, 31), "cs", {})
