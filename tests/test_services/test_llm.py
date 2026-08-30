import httpx
import pytest

from src.services.llm import LlmClient, _provider, generate_model, judge_model

_USAGE_OK = {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0}


def _c(handler) -> LlmClient:
    c = LlmClient(api_key="k", base_url="https://x/api/v1", temperature=0.0)
    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_temperature_0_duoc_gui_di():
    got = {}

    def h(req):
        import json

        got.update(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": _USAGE_OK})

    _c(h).chat("m", [{"role": "user", "content": "x"}])
    assert got["temperature"] == 0.0


def test_json_schema_bien_thanh_response_format():
    got = {}

    def h(req):
        import json

        got.update(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}], "usage": _USAGE_OK})

    _c(h).chat("m", [{"role": "user", "content": "x"}], json_schema={"type": "object"})
    assert got["response_format"]["type"] == "json_schema"


def test_usage_va_cost_duoc_boc_ra():
    def h(req):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.00012},
            },
        )

    _, u = _c(h).chat("m", [{"role": "user", "content": "x"}])
    assert u.token_in == 100 and u.token_out == 20 and u.cost_usd == 0.00012


def test_content_rong_nem_khong_tra_chuoi_rong():
    def h(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}], "usage": {}})

    with pytest.raises(ValueError, match="rỗng"):
        _c(h).chat("m", [{"role": "user", "content": "x"}])


def test_generate_va_judge_la_hai_model_khac_nhau():
    assert generate_model() != judge_model()


def test_usage_thieu_hoan_toan_nem_khong_bia_so():
    def h(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})  # không có 'usage'

    with pytest.raises(ValueError, match="usage"):
        _c(h).chat("m", [{"role": "user", "content": "x"}])


def test_usage_thieu_truong_cost_nem_khong_bia_so():
    def h(req):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},  # thiếu 'cost'
            },
        )

    with pytest.raises(ValueError, match="cost"):
        _c(h).chat("m", [{"role": "user", "content": "x"}])


def test_retry_thanh_cong_sau_loi_tam_thoi():
    # 503 hai lần đầu (server chập chờn) rồi mới thành công — retry phải tự
    # phục hồi thay vì fail ngay ở lần thử đầu, và không được nuốt thành rỗng.
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, text="server error")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": _USAGE_OK})

    c = _c(h)
    c.retry_backoff_base = 0
    content, usage = c.chat("m", [{"role": "user", "content": "x"}])
    assert content == "ok"
    assert calls["n"] == 3
    assert usage.cost_usd == 0.0


def test_retry_can_van_nem_khong_nuot_thanh_ket_qua_rong():
    # OpenRouter đang trả 429 thật cho project này — cạn retry PHẢI nổ, không
    # được lặng lẽ trả về nội dung rỗng hay Usage bịa.
    def h(req):
        return httpx.Response(429, text="rate limited")

    c = _c(h)
    c.retry_backoff_base = 0
    with pytest.raises(httpx.HTTPStatusError):
        c.chat("m", [{"role": "user", "content": "x"}])


def test_provider_la_phan_truoc_dau_slash():
    assert _provider("google/gemini-2.5-flash-lite") == "google"
    assert _provider("google/gemini-2.5-flash-lite") == _provider("google/gemini-2.5-flash")
    assert _provider("mistralai/mistral-nemo") == "mistralai"


def test_judge_cung_provider_thi_canh_bao_khong_chan(monkeypatch, caplog):
    import logging

    class FakeSettings:
        openrouter_generate_model_name = "google/gemini-2.5-flash-lite"
        openrouter_judge_model_name = "google/gemini-2.5-flash"

    monkeypatch.setattr("src.services.llm.get_settings", lambda: FakeSettings())
    with caplog.at_level(logging.WARNING, logger="src.services.llm"):
        result = judge_model()
    assert result == "google/gemini-2.5-flash"  # vẫn trả về — cảnh báo, không chặn
    assert "google" in caplog.text
