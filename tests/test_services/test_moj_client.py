import httpx
import pytest

from src.services.moj_client import MojClient


def _client(handler) -> MojClient:
    c = MojClient(base="https://x/api", sleep=0.0)
    c.backoff_base = 0.0
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


@pytest.mark.parametrize("ma", [400, 429, 500, 503])
def test_loi_thoang_qua_thi_thu_lai_voi_backoff_luy_thua(monkeypatch, ma):
    """HTTP 400 thoáng qua sau ~35 request liên tiếp (đo 2026-08-27) — một lần
    nạp 35 văn bản không được chết giữa chừng vì nó. Nghỉ tăng gấp đôi mỗi lần."""
    nghi: list[float] = []
    monkeypatch.setattr("src.services.moj_client.time.sleep", lambda s: nghi.append(s))
    lan = iter([httpx.Response(ma, text="tam"), httpx.Response(ma, text="tam"),
                httpx.Response(200, json={"data": {"id": "1"}})])
    c = _client(lambda req: next(lan))
    c.backoff_base = 2.0
    assert c.fetch_doc("1") == {"id": "1"}
    assert nghi == [0.0, 2.0, 0.0, 4.0, 0.0], "nghỉ nhịp trước MỖI request, cộng 2 s rồi 4 s backoff"


def test_het_luot_thu_thi_van_nem_loi():
    goi: list[int] = []

    def h(req):
        goi.append(1)
        return httpx.Response(503, text="bận")

    with pytest.raises(httpx.HTTPStatusError):
        _client(h).fetch_doc("1")
    assert len(goi) == 1 + MojClient.max_retries


def test_loi_khong_thoang_qua_khong_thu_lai():
    goi: list[int] = []

    def h(req):
        goi.append(1)
        return httpx.Response(404, text="không có")

    with pytest.raises(httpx.HTTPStatusError):
        _client(h).fetch_doc("1")
    assert len(goi) == 1


def test_response_thieu_data_nem_ValueError_khong_tra_None():
    def h(req):
        return httpx.Response(200, json={"success": False})

    with pytest.raises(ValueError, match="thiếu 'data'"):
        _client(h).fetch_doc("1")
