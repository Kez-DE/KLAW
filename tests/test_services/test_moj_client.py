import httpx
import pytest

from src.services.moj_client import MojClient


def _client(handler) -> MojClient:
    c = MojClient(base="https://x/api", sleep=0.0)
    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_fetch_doc_boc_lop_data():
    def h(req):
        return httpx.Response(200, json={"data": {"id": "139264", "docNum": "45/2019/QH14"}})

    assert _client(h).fetch_doc("139264")["docNum"] == "45/2019/QH14"


def test_rate_limit_sleep_duoc_goi_giua_cac_request(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr("src.services.moj_client.time.sleep", lambda s: calls.append(s))

    def h(req):
        return httpx.Response(200, json={"data": {"id": "1"}})

    c = _client(h)
    c.sleep = 1.5
    c.fetch_doc("1")
    c.fetch_doc("2")
    assert calls == [1.5, 1.5], "phải nghỉ giữa các request — HTTP 400 sau ~35 request liên tiếp"


def test_http_loi_nem_ra_khong_tra_dict_rong():
    def h(req):
        return httpx.Response(400, text="bad")

    with pytest.raises(httpx.HTTPStatusError):
        _client(h).fetch_doc("1")


def test_response_thieu_data_nem_ValueError_khong_tra_None():
    def h(req):
        return httpx.Response(200, json={"success": False})

    with pytest.raises(ValueError, match="thiếu 'data'"):
        _client(h).fetch_doc("1")
