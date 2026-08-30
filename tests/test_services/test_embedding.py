import httpx
import pytest

from src.services.embedding import EmbeddingClient


def _c(handler, dim=4) -> EmbeddingClient:
    c = EmbeddingClient(api_key="k", base_url="https://x/api/v1", model="baai/bge-m3", dim=dim)
    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_embed_giu_dung_thu_tu_theo_index_tra_ve():
    def h(req):
        # OpenRouter có thể trả không đúng thứ tự — phải sort theo index
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [9, 9, 9, 9]},
            {"index": 0, "embedding": [1, 1, 1, 1]},
        ]})

    out = _c(h).embed(["a", "b"])
    assert out[0] == [1, 1, 1, 1] and out[1] == [9, 9, 9, 9]


def test_dim_khong_khop_thi_nem_khong_im_lang():
    def h(req):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 2]}]})

    with pytest.raises(ValueError, match="chiều vector"):
        _c(h, dim=4).embed(["a"])


def test_chia_lo_khi_nhieu_text():
    lots = []

    def h(req):
        import json
        body = json.loads(req.content)
        lots.append(len(body["input"]))
        return httpx.Response(200, json={"data": [
            {"index": i, "embedding": [0, 0, 0, 0]} for i in range(len(body["input"]))
        ]})

    c = _c(h)
    c.batch = 32
    c.embed(["x"] * 70)
    assert lots == [32, 32, 6]


def test_http_loi_nem_ra():
    def h(req):
        return httpx.Response(429, text="rate limited")

    with pytest.raises(httpx.HTTPStatusError):
        _c(h).embed(["a"])


def test_text_rong_bi_tu_choi_truoc_khi_goi_api():
    def h(req):
        raise AssertionError("không được gọi API với text rỗng")

    with pytest.raises(ValueError, match="rỗng"):
        _c(h).embed(["a", ""])


def test_retry_thanh_cong_sau_loi_tam_thoi():
    # lỗi 503 hai lần đầu (mạng/server chập chờn) rồi mới thành công — retry
    # phải tự phục hồi thay vì fail ngay ở lần thử đầu tiên
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, text="server error")
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 1, 1, 1]}]})

    c = _c(h)
    c.retry_backoff_base = 0
    out = c.embed(["a"])
    assert out == [[1, 1, 1, 1]]
    assert calls["n"] == 3


def test_can_retry_thi_nem_loi_cuoi_khong_im_lang():
    # cạn retry KHÔNG được nuốt lỗi — phải raise, và phải thực sự thử lại
    # (không phải raise ngay ở lần đầu)
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        return httpx.Response(503, text="server error")

    c = _c(h)
    c.retry_backoff_base = 0
    with pytest.raises(httpx.HTTPStatusError):
        c.embed(["a"])
    assert calls["n"] == c.max_retries + 1
