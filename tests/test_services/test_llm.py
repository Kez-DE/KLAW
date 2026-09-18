import httpx
import pytest

from src.services.llm import LlmClient, TruncatedOutputError, Usage, _provider, generate_model, judge_model

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


# ══ Task 1 (2026-09-02) — structured output bị CẮT GIỮA CHỪNG ═══════════════
# Đo được trong 45-trap run: `rewrite_query` (json_schema=QUERIES_SCHEMA) ăn
# JSONDecodeError "Unterminated string" 2/45 lần. Content KHÔNG rỗng (nhánh
# `_ContentRongError` cũ không bắt được ca này) nhưng cũng KHÔNG PHẢI JSON đầy
# đủ — `finish_reason=length` nghĩa là provider cắt response giữa chừng.
# Không có `max_tokens` nào được đặt ở tầng này (đọc `chat()` — xác nhận), nên
# ngân sách output hoàn toàn phụ thuộc mặc định phía provider; "length" khi
# caller đã xin `response_format=json_schema` LUÔN nghĩa là JSON dở dang — decision
# xác định (không có ca "length nhưng vẫn đủ" ở structured mode), nên phải thử
# lại, cùng khuôn với content rỗng.


def test_json_schema_bi_cat_giua_chung_length_duoc_thu_lai():
    """`finish_reason=length` + đã xin structured output ⇒ JSON chắc chắn dở
    dang dù content không rỗng — phải thử lại, không được trả thẳng cho caller
    tự vỡ ở JSONDecodeError. Review round 1 (2026-09-02): phục hồi phải xảy ra
    trong ĐÚNG MỘT lần thử lại (2 lần gọi tổng) — không phải "thử tới khi nào
    max_retries cho phép"."""
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{"queries": ["a'}, "finish_reason": "length"}],
                    "usage": _USAGE_OK,
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"queries": ["a", "b"]}'}, "finish_reason": "stop"}],
                "usage": _USAGE_OK,
            },
        )

    c = _c(h)
    c.retry_backoff_base = 0
    content, _ = c.chat("m", [{"role": "user", "content": "x"}], json_schema={"type": "object"})
    assert content == '{"queries": ["a", "b"]}'
    assert calls["n"] == 2, f"phải phục hồi trong ĐÚNG 1 lần thử lại (2 lần gọi): {calls['n']}"


def test_json_schema_do_dang_chi_thu_lai_MOT_lan_khong_an_het_max_retries():
    """Review round 1 [Important] (2026-09-02): nếu cắt là CẤU TRÚC (schema +
    ngữ cảnh cần nhiều token hơn provider chịu phát cho request đó) thì MỌI
    lần thử lại đều cắt y hệt. `generate_claims` là node ĐẮT NHẤT của graph
    (nhiều claim, mỗi claim kèm quote dài) — ăn hết max_retries=3 (4 lần gọi)
    ở đây là 4x chi phí + 4x độ trễ trên đường chờ người dùng rồi vẫn thất
    bại. Ngân sách RIÊNG cho ca này: MỘT lần thử lại (2 lần gọi tổng), không
    ăn hết max_retries như content rỗng/429/5xx."""
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"queries": ["a'}, "finish_reason": "length"}],
                "usage": _USAGE_OK,
            },
        )

    c = _c(h)
    c.retry_backoff_base = 0
    with pytest.raises(ValueError, match="length"):
        c.chat("m", [{"role": "user", "content": "x"}], json_schema={"type": "object"})
    assert calls["n"] == 2, f"phải dừng sau 2 lần gọi (1 lần thử lại), không ăn hết max_retries: {calls['n']}"


def test_json_schema_can_retry_van_cat_thi_nem_khong_tra_JSON_do_dang():
    """Cạn NGÂN SÁCH RIÊNG (1 lần thử lại) vẫn phải nổ — không được trả JSON
    dở dang để caller tự JSONDecodeError ở một tầng không biết gì về
    finish_reason, cùng lý do content rỗng cạn retry phải nổ."""

    def h(req):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"queries": ["a'}, "finish_reason": "length"}],
                "usage": _USAGE_OK,
            },
        )

    c = _c(h)
    c.retry_backoff_base = 0
    with pytest.raises(ValueError, match="length"):
        c.chat("m", [{"role": "user", "content": "x"}], json_schema={"type": "object"})


def test_TruncatedOutputError_mang_usage_cong_don_ca_hai_lan_cat():
    """Phase 16 fix round (Concern 3): cả hai lần gọi bị cắt đều tốn tiền thật —
    lỗi phải mang `usage` CỘNG DỒN của cả hai, để node gọi ghi đúng vào traces
    thay vì 0."""

    def h(req):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"queries": ["a'}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 5, "cost": 0.01},
            },
        )

    c = _c(h)
    c.retry_backoff_base = 0
    with pytest.raises(TruncatedOutputError) as ex:
        c.chat("m", [{"role": "user", "content": "x"}], json_schema={"type": "object"})
    assert isinstance(ex.value.usage, Usage)
    assert (ex.value.usage.token_in, ex.value.usage.token_out) == (6, 10)
    assert ex.value.usage.cost_usd == pytest.approx(0.02)


def test_content_rong_VA_length_VA_schema_dung_ngan_sach_length_khong_phai_content_rong():
    """Review round 2 [Important] (2026-09-02): cắt TOÀN BỘ — model tiêu hết
    ngân sách output cho suy luận + schema lớn, phát ra 0 ký tự — vẫn có
    `finish_reason=length` + `response_format`, tức content RỖNG. Trước bản
    này nhánh content rỗng (`_ContentRongError`, ngân sách ĐẦY ĐỦ
    `max_retries`) bắt ca này TRƯỚC khi nhánh length-cắt (`_JsonDoDangError`,
    ngân sách MỘT lần thử lại) kịp thấy — nên đúng ca CẤU TRÚC nhất trong hai
    lớp lại ăn 4 lần gọi thay vì 2, trên `generate_claims`, node đắt nhất của
    graph, trên đường người dùng đang chờ."""
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                "usage": _USAGE_OK,
            },
        )

    c = _c(h)
    c.retry_backoff_base = 0
    with pytest.raises(ValueError, match="length"):
        c.chat("m", [{"role": "user", "content": "x"}], json_schema={"type": "object"})
    assert calls["n"] == 2, (
        f"phải dừng sau 2 lần gọi (ngân sách RIÊNG của length-cắt), không ăn hết "
        f"max_retries=4 lần gọi như nhánh content rỗng thường: {calls['n']}"
    )


def test_length_KHONG_xin_structured_output_thi_KHONG_bi_ep_thu_lai():
    """Không xin `json_schema` thì `length` có thể là một câu trả lời dài hợp
    lệ bị cắt theo đúng ý caller (vd. hành văn tự do) — không được ép thử lại
    một hành vi caller không xin, tự thêm round-trip vô ích."""

    def h(req):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "một câu trả lời dài bị cắt"}, "finish_reason": "length"}],
                "usage": _USAGE_OK,
            },
        )

    c = _c(h)
    c.retry_backoff_base = 0
    content, _ = c.chat("m", [{"role": "user", "content": "x"}])  # KHÔNG có json_schema
    assert content == "một câu trả lời dài bị cắt"


def test_usage_cong_don_qua_cac_lan_thu_lai():
    """Review round 1 [Minor, folded in] (2026-09-02): `_usage_from` dựng
    `Usage` từ response THÀNH CÔNG cuối cùng — token của các lần thử TRƯỚC
    (rỗng, length-cắt...) bị mất, dù OpenRouter đã tính phí cho chúng
    (`usage.include=true`). Áp dụng cho MỌI lý do thử lại, không riêng
    length+schema — số `cost_usd` lên thẳng một khoá luận, không được hiểu
    thấp chi phí thật."""
    calls = {"n": 0}

    def h(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": ""}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 0, "cost": 0.00001},
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3, "cost": 0.00002},
            },
        )

    c = _c(h)
    c.retry_backoff_base = 0
    _, usage = c.chat("m", [{"role": "user", "content": "x"}])
    assert usage.token_in == 10, f"phải cộng dồn 5+5=10, không chỉ lấy lần cuối: {usage.token_in}"
    assert usage.token_out == 3, f"lần đầu completion_tokens=0 nên tổng vẫn 0+3=3: {usage.token_out}"
    assert usage.cost_usd == pytest.approx(0.00003), f"phải cộng dồn 0.00001+0.00002: {usage.cost_usd}"


def test_usage_thieu_truong_van_KHONG_bi_bia_sau_khi_cong_don():
    """Cộng dồn KHÔNG được biến một khoá 'usage' vắng mặt (hoặc thiếu trường)
    thành một số 0 giả — bất biến "không bịa số" của `_usage_from` phải sống
    sót qua bản cộng dồn (round 1 review)."""

    def h(req):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},  # thiếu 'cost'
            },
        )

    c = _c(h)
    c.retry_backoff_base = 0
    with pytest.raises(ValueError, match="cost"):
        c.chat("m", [{"role": "user", "content": "x"}])
