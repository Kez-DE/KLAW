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

    c = _c(h)
    c.retry_backoff_base = 0  # content rỗng nay ĐƯỢC thử lại (Pha 0a) — đừng ngủ thật trong suite
    with pytest.raises(ValueError, match="rỗng"):
        c.chat("m", [{"role": "user", "content": "x"}])


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


# ══ Pha 0a/0b — content rỗng và 429 (spec 2026-09-02, mục 4) ═══════════════


def test_content_rong_duoc_thu_lai_roi_phuc_hoi():
    """HTTP 200 + content rỗng là lỗi TẠM THỜI, không phải câu trả lời.

    Đo được 2026-09-02: `mistralai/mistral-nemo` trả rỗng 2/5 lần trên prompt
    `route`. Trước bản này mỗi lần như vậy là một HTTP 500 ném vào mặt người
    dùng ngay node ĐẦU TIÊN của graph — trong khi lần gọi ngay sau đó thành
    công. Retry đã có sẵn cho 503 nhưng không phủ ca này, vì tầng HTTP thấy 200
    và không có gì để bắt.
    """
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        noi_dung = "" if calls["n"] < 3 else "ok"
        return httpx.Response(200, json={"choices": [{"message": {"content": noi_dung}}], "usage": _USAGE_OK})

    c = _c(h)
    c.retry_backoff_base = 0
    content, _ = c.chat("m", [{"role": "user", "content": "x"}])
    assert content == "ok"
    assert calls["n"] == 3


def test_content_rong_can_retry_van_nem_khong_tra_rong():
    """Cạn retry vẫn phải nổ. Trả về chuỗi rỗng sẽ khiến node gọi nó
    (`route`, `generate_claims`) nhận một câu trả lời hợp lệ-về-hình-dạng mà
    trống nội dung — đúng lớp lỗi im lặng cả dự án chống."""
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "  "}}], "usage": _USAGE_OK})

    c = _c(h)
    c.retry_backoff_base = 0
    with pytest.raises(ValueError, match="rỗng"):
        c.chat("m", [{"role": "user", "content": "x"}])
    assert calls["n"] == c.max_retries + 1


def test_429_cho_lau_hon_loi_may_chu_thuong(monkeypatch):
    """Backoff 0,2s cho 429 là gần như không thử lại: 0,2 + 0,4 + 0,8 = 1,4
    giây rồi bỏ cuộc, trong khi rate limit cần vài giây. Đo được một 429 xuyên
    thủng cả bốn lần thử khi chạy hai câu hỏi liên tiếp."""
    da_cho: list[float] = []
    monkeypatch.setattr("src.services.llm.time.sleep", da_cho.append)

    def h(req):
        return httpx.Response(429, text="rate limited")

    with pytest.raises(httpx.HTTPStatusError):
        _c(h).chat("m", [{"role": "user", "content": "x"}])
    assert da_cho, "429 phải chờ giữa các lần thử"
    assert sum(da_cho) >= 10, f"429 chờ tổng {sum(da_cho)}s — quá ngắn cho rate limit"


def test_429_ton_trong_header_retry_after(monkeypatch):
    """Máy chủ nói chờ bao lâu thì chờ đúng bấy lâu — đoán một con số khác là
    tự tạo thêm 429 hoặc chờ vô ích."""
    da_cho: list[float] = []
    monkeypatch.setattr("src.services.llm.time.sleep", da_cho.append)
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="slow down", headers={"Retry-After": "7"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": _USAGE_OK})

    content, _ = _c(h).chat("m", [{"role": "user", "content": "x"}])
    assert content == "ok"
    assert da_cho == [7.0], f"phải chờ đúng 7s theo Retry-After, đã chờ {da_cho}"


def test_retry_after_rac_roi_ve_backoff_thuong(monkeypatch):
    """Header do máy chủ ngoài gửi — không tin. 'Wed, 21 Oct 2026 07:28:00 GMT'
    (dạng HTTP-date, hợp lệ theo RFC) không parse được thành số.

    Kiểm CẢ HAI nửa của lời hứa: không nổ, VÀ rơi về đúng backoff 429 thường
    (`retry_backoff_base × retry_429_nhan`). Bản trước chỉ assert `content ==
    "ok"`, nên nếu công thức dự phòng bị đổi thành một con số vô lý khác — miễn
    còn hữu hạn và không âm để không crash — test vẫn xanh.
    """
    da_cho: list[float] = []
    monkeypatch.setattr("src.services.llm.time.sleep", da_cho.append)
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="x", headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": _USAGE_OK})

    c = _c(h)
    content, _ = c.chat("m", [{"role": "user", "content": "x"}])
    assert content == "ok"
    assert da_cho == [pytest.approx(c.retry_backoff_base * c.retry_429_nhan)]


def test_retry_after_qua_lon_bi_chan_tran(monkeypatch):
    """Một `Retry-After: 3600` sẽ treo request một tiếng. Chặn bằng trần."""
    da_cho: list[float] = []
    monkeypatch.setattr("src.services.llm.time.sleep", da_cho.append)

    def h(req):
        return httpx.Response(429, text="x", headers={"Retry-After": "3600"})

    c = _c(h)
    with pytest.raises(httpx.HTTPStatusError):
        c.chat("m", [{"role": "user", "content": "x"}])
    assert da_cho and max(da_cho) <= c.retry_cho_toi_da


def test_du_phong_429_cung_bi_chan_tran(monkeypatch):
    """Không có `Retry-After` thì dùng backoff dự phòng — và nó PHẢI qua cùng
    trần. Trước bản này chỉ nhánh đọc được header bị chặn, nên bất biến "chờ 429
    luôn ≤ trần" chỉ đúng nhờ trùng hợp số mặc định."""
    da_cho: list[float] = []
    monkeypatch.setattr("src.services.llm.time.sleep", da_cho.append)

    def h(req):
        return httpx.Response(429, text="rate limited")  # không có Retry-After

    c = _c(h)
    c.retry_backoff_base = 100.0  # 100 × 10 × 2^n — vượt xa trần nếu không chặn
    with pytest.raises(httpx.HTTPStatusError):
        c.chat("m", [{"role": "user", "content": "x"}])
    assert da_cho and max(da_cho) <= c.retry_cho_toi_da, f"vượt trần: {da_cho}"


# ══ Vòng review 1 (silent-failure-hunter, 2026-09-02) ══════════════════════


@pytest.mark.parametrize("header", ["-5", "nan", "-inf"])
def test_retry_after_so_vo_nghia_khong_lam_no_o_time_sleep(header):
    """`float()` KHÔNG raise với "-5" / "nan" / "-inf".

    Ba giá trị này lọt qua `min()` rồi tới `time.sleep()` — chỗ nằm NGOÀI mọi
    try/except của vòng lặp — và `time.sleep(-5.0)` nổ
    `ValueError: sleep length must be non-negative`, `time.sleep(nan)` nổ
    `Invalid value NaN`. Một header xấu từ proxy trung gian sẽ tạo ra một lỗi
    không liên quan gì tới nguyên nhân thật, đẩy chẩn đoán đi sai hướng.

    (`min(nan, 30.0)` trả về `nan`: mọi so sánh với NaN đều False nên `min` giữ
    tham số đầu — trần `retry_cho_toi_da` không chặn được ca này.)
    """
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="x", headers={"Retry-After": header})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": _USAGE_OK})

    c = _c(h)
    c.retry_backoff_base = 0
    content, _ = c.chat("m", [{"role": "user", "content": "x"}])
    assert content == "ok"


def test_429_va_loi_may_chu_co_log_khong_cho_cam(caplog):
    """Nhánh content rỗng có log mỗi lần thử lại; nhánh 429/5xx/mạng thì không.
    Bất đối xứng đó nghĩa là một request có thể chờ tới ~90 giây (ba lần
    `Retry-After: 30` bị chặn trần) mà không để lại một dấu vết nào."""
    import logging

    def h(req):
        return httpx.Response(503, text="server error")

    c = _c(h)
    c.retry_backoff_base = 0
    with caplog.at_level(logging.WARNING, logger="src.services.llm"), pytest.raises(httpx.HTTPStatusError):
        c.chat("m", [{"role": "user", "content": "x"}])
    assert "503" in caplog.text, f"không có log nào cho 503: {caplog.text!r}"


def test_content_rong_neu_ly_do_dung_vao_thong_bao_loi():
    """`finish_reason` phân biệt bốn nguyên nhân rất khác nhau của content rỗng:
    bộ lọc nội dung, hết token (`length`), model gọi tool thay vì trả nội dung,
    và lỗi provider ngẫu nhiên (ca đã đo với mistral-nemo). Thiếu nó thì cả bốn
    trông giống nhau trong log."""

    def h(req):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}],
                "usage": _USAGE_OK,
            },
        )

    c = _c(h)
    c.retry_backoff_base = 0
    with pytest.raises(ValueError, match="content_filter"):
        c.chat("m", [{"role": "user", "content": "x"}])


def test_message_null_khong_nem_AttributeError():
    """`message` có KHOÁ nhưng giá trị `null` khác hẳn `message` thiếu khoá:
    `.get("message", {})` không áp default cho ca đầu, nên `.get("content")`
    chạy trên `None`. Lỗi ra sẽ là `AttributeError` không mang tên model —
    không khớp khuôn raise nào khác trong file này."""

    def h(req):
        return httpx.Response(200, json={"choices": [{"message": None}], "usage": _USAGE_OK})

    c = _c(h)
    c.retry_backoff_base = 0
    with pytest.raises(ValueError, match="rỗng"):
        c.chat("m", [{"role": "user", "content": "x"}])


def test_body_khong_phai_json_duoc_thu_lai():
    """HTTP 200 kèm body không phải JSON là cùng lớp lỗi tạm thời với content
    rỗng — gateway glitch. Trước bản này nó thoát ngay, không được thử lại."""
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, text="<html>502 Bad Gateway</html>")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": _USAGE_OK})

    c = _c(h)
    c.retry_backoff_base = 0
    content, _ = c.chat("m", [{"role": "user", "content": "x"}])
    assert content == "ok"
    assert calls["n"] == 2
