"""LLM qua OpenRouter — ba vai, một key.

route/rewrite : OPENROUTER_MODEL_NAME
generate      : OPENROUTER_GENERATE_MODEL_NAME  (bắt buộc structured output)
judge         : OPENROUTER_JUDGE_MODEL_NAME     (nên khác họ với generate — spec 7b.2)

Mọi request gửi `usage: {include: true}` để OpenRouter luôn trả `cost` thật
trong `usage` — đã xác nhận bằng gọi API thật (xem task-3-report.md). Không có
trường này thì `Usage` sẽ phải bịa số, việc `chat()` cấm làm (raise thay vì đoán).
"""

import json
import logging
import math
import time
from dataclasses import dataclass

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class _ContentRongError(Exception):
    """Nội bộ: HTTP 200 nhưng `message.content` rỗng.

    Tầng HTTP thấy 200 và không có gì để bắt, nên retry cũ (chỉ phủ
    HTTPStatusError/TransportError) bỏ qua hẳn ca này. Đo được 2026-09-02:
    `mistralai/mistral-nemo` rỗng 2/5 lần trên prompt `route` — mỗi lần là một
    HTTP 500 ở node ĐẦU TIÊN của graph, trong khi lần gọi ngay sau thành công.
    """


class _JsonDoDangError(Exception):
    """Nội bộ: content KHÔNG rỗng nhưng bị CẮT GIỮA CHỪNG khi caller đã xin
    structured output (`finish_reason=length` + `response_format`).

    TÁCH RIÊNG khỏi `_ContentRongError` (review round 1, 2026-09-02) vì ngân
    sách thử lại phải khác: nếu cắt là CẤU TRÚC (schema + ngữ cảnh cần nhiều
    token hơn provider chịu phát cho request đó — khác content rỗng, vốn
    thường là chập chờn provider) thì MỌI lần thử lại đều cắt y hệt. Thử tới
    `max_retries` trên node ĐẮT NHẤT của graph (`generate_claims`, schema
    nhiều claim + quote dài) chỉ nhân chi phí và độ trễ trên đường chờ người
    dùng rồi vẫn thất bại. MỘT lần thử lại đủ bắt ca TẠM THỜI; quá đó là lãng
    phí đã đo được (review round 1).
    """


class _JsonHongError(Exception):
    """Content là JSON HỎNG dù `finish_reason=stop` — đã phát hết, chỉ là phát
    sai. KHÁC `_JsonDoDangError` (bị cắt vì `length`): ở đây không thiếu token,
    model chỉ đẻ ra một chuỗi không đóng. Đo được hai lần: Phase 16 trên
    `rewrite_query`, và 2026-09-18 trên `hieu_tai_lieu`
    (`Unterminated string starting at` vị trí 4248) — lần sau người dùng bấm
    lại thì lành, nên đây là lỗi KHÔNG TẤT ĐỊNH, đúng lớp đáng thử lại.

    Bắt ở ĐÂY chứ không ở từng node: mười node gọi `json.loads` trên content,
    nên vá ở node là vá một nhánh và để chín nhánh kia nguyên lỗi.

    Mang theo `JSONDecodeError` gốc để lần cạn ngân sách raise lại đúng lỗi đó
    — mọi caller đang bắt `json.JSONDecodeError` vẫn chạy y như cũ.
    """

    def __init__(self, goc: json.JSONDecodeError):
        super().__init__(str(goc))
        self.goc = goc


class TruncatedOutputError(ValueError):
    """CÔNG KHAI (không tiền tố `_`) — Phase 16 R2/R3: cắt CẤU TRÚC đã cạn ngân
    sách một-lần-thử-lại của `_JsonDoDangError` (xem docstring lớp đó, không
    đổi). Trước bản vá này chỗ `raise` bên dưới ném thẳng `ValueError`, buộc
    caller muốn phản ứng riêng cho "đầu ra không vừa một lượt" phải so khớp
    CHUỖI tiếng Việt của thông điệp lỗi — giòn, gãy theo câu chữ. Là lớp con
    của `ValueError` nên MỌI `except ValueError`/`except Exception` đang có
    (cả trong file này lẫn mọi node gọi `llm.chat`) vẫn bắt được y hệt, không
    hành vi nào đổi; chỉ thêm một cửa để `hieu_tai_lieu` (chia tài liệu thành
    nhiều lượt) phân biệt được ca này với lỗi hạ tầng khác, trả lời đúng người
    dùng thay vì "chưa đọc được, thử lại" chung chung."""

    def __init__(self, *args, usage: "Usage | None" = None) -> None:
        # Chi phí đã trả THẬT cho OpenRouter dù lượt hỏng — mang theo trong
        # lỗi để caller ghi đúng vào traces thay vì 0 (Phase 16, Concern 3).
        super().__init__(*args)
        self.usage = usage


@dataclass(frozen=True)
class Usage:
    token_in: int
    token_out: int
    cost_usd: float


class LlmClient:
    """Client HTTP dùng chung cho cả ba vai (router/generate/judge) — cùng một
    OPENROUTER_API_KEY, khác nhau ở `model` truyền vào `chat()`. `temperature` cố
    định tại constructor và không có tham số ghi đè per-call, nên không vai nào
    tự chọn temperature khác được (spec 8.1: mọi vai temperature=0.0).
    """

    def __init__(self, api_key: str, base_url: str, temperature: float) -> None:
        self.temperature = temperature
        self.max_retries = 3
        self.retry_backoff_base = 0.2  # giây; cạn retry vẫn raise, không swallow (cùng khuôn EmbeddingClient)
        # 429 cần chờ lâu hơn lỗi máy chủ thường: 0,2 + 0,4 + 0,8 = 1,4 giây rồi
        # bỏ cuộc là gần như không thử lại, và đã đo được một 429 xuyên thủng cả
        # bốn lần thử. Là HỆ SỐ NHÂN chứ không phải hằng số riêng, để test nào
        # đặt `retry_backoff_base = 0` vẫn chạy tức thì.
        self.retry_429_nhan = 10
        self.retry_cho_toi_da = 30.0  # trần; `Retry-After: 3600` sẽ treo request một tiếng
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=180,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )

    def _cho_bao_lau(self, resp: httpx.Response, thuong: float) -> float:
        """Bao lâu trước lần thử kế. 429 chờ lâu hơn, và nếu máy chủ nói rõ
        chờ bấy lâu thì tin nó — đoán một con số khác chỉ tạo thêm 429 hoặc chờ
        vô ích.

        `Retry-After` do máy chủ ngoài gửi nên KHÔNG tin hình dạng, và
        `float()` một mình KHÔNG đủ để kiểm: nó nhận "-5", "nan", "-inf" mà
        không raise gì cả. Ba giá trị đó lọt qua `min()` (`min(nan, 30.0)` trả
        về `nan` — mọi so sánh với NaN đều False nên `min` giữ tham số đầu, trần
        không chặn được) rồi tới `time.sleep()`, chỗ nằm NGOÀI mọi try/except
        của vòng lặp: `time.sleep(-5.0)` nổ "sleep length must be non-negative",
        `time.sleep(nan)` nổ "Invalid value NaN". Kết quả là một lỗi không liên
        quan gì tới nguyên nhân thật (header xấu), đẩy chẩn đoán đi sai hướng.

        Nên: parse xong còn phải hữu hạn và không âm. Không đạt thì rơi về
        backoff thường — cùng đường với dạng HTTP-date hợp-lệ-theo-RFC
        ("Wed, 21 Oct 2026 07:28:00 GMT") mà `float()` không đọc được.

        Có trần vì `Retry-After: 3600` sẽ treo request một tiếng.

        `thuong` (backoff thường) NHẬN VÀO chứ không tính lại: vòng lặp đã tính
        đúng giá trị đó ở đầu mỗi lượt, và hai bản sao của cùng một công thức sẽ
        lệch nhau ngay khi ai đó thêm jitter vào một bên.
        """
        if resp.status_code != 429:
            return thuong
        # MỌI đường ra đều qua trần. Trước bản này chỉ nhánh đọc được header bị
        # chặn, nhánh dự phòng thì không — nên bất biến "chờ 429 luôn ≤ trần" chỉ
        # đúng nhờ trùng hợp số hiện tại (0,2 × 10 × 2² = 8s < 30s), không nhờ cấu
        # trúc. Ai tăng `retry_backoff_base` hay `max_retries` vì một lý do khác là
        # nhánh này tự phình qua trần mà không ai chủ ý.
        du_phong = min(thuong * self.retry_429_nhan, self.retry_cho_toi_da)
        # Chỉ `ValueError`: `headers.get(k, "")` luôn trả `str`, nên `TypeError`
        # từ `float()` là nhánh không tới được — bỏ đi thay vì để lại một cái
        # bắt-cho-chắc gợi ý sai về hình dạng dữ liệu thật.
        try:
            giay = float(resp.headers.get("Retry-After", ""))
        except ValueError:
            return du_phong
        if not math.isfinite(giay) or giay < 0:
            logger.warning("Retry-After vô nghĩa (%r) — dùng backoff thường", giay)
            return du_phong
        return min(giay, self.retry_cho_toi_da)

    @staticmethod
    def _boc_content(data: dict) -> tuple[str, str]:
        """Trả (content, finish_reason).

        `message` có thể là `null` (có khoá, giá trị None) chứ không chỉ thiếu
        khoá, và `.get("message", {})` KHÔNG áp default cho ca đó — `.get()` kế
        tiếp sẽ chạy trên `None` và nổ `AttributeError` không mang tên model,
        lệch hẳn khuôn raise của cả file. `or {}` phủ cả hai hình dạng.

        `finish_reason` được bóc ra vì nó phân biệt bốn nguyên nhân rất khác
        nhau của content rỗng: bộ lọc nội dung, hết token (`length`), model gọi
        tool thay vì trả nội dung, và lỗi provider ngẫu nhiên (ca đã đo với
        mistral-nemo). Thiếu nó thì cả bốn trông giống nhau trong log.
        """
        choice = (data.get("choices") or [{}])[0] or {}
        content = (choice.get("message") or {}).get("content") or ""
        return content, str(choice.get("finish_reason") or "?")

    def _goi_va_lay_content(self, body: dict, model: str) -> tuple[str, dict]:
        """Gọi + bóc content TRONG CÙNG vòng retry.

        Bóc content ở đây chứ không ở `chat()` là điều kiện để content rỗng được
        thử lại: nếu vòng lặp chỉ trả `Response` thì lúc phát hiện rỗng đã ra
        ngoài vòng, không còn lần thử nào.

        URL tuyệt đối: test thay `_http` bằng client chỉ có MockTransport (không
        set base_url) sẽ vỡ trên httpx>=0.28 nếu POST bằng path tương đối — cùng
        lý do EmbeddingClient._post_with_retry đã né bằng URL tuyệt đối.
        """
        url = f"{self._base_url}/chat/completions"
        # Ngân sách RIÊNG cho JSON cắt giữa chừng (structural truncation, xem
        # `_JsonDoDangError`) — ĐỘC LẬP với `attempt`/`max_retries`: một request
        # có thể ăn vài lần 503 rồi một lần length-cắt, và lần length đó vẫn
        # chỉ được đúng MỘT cơ hội thử lại, không phải phần ngân sách còn lại
        # của max_retries.
        so_lan_length_cat = 0
        # Ngân sách RIÊNG cho JSON hỏng ở `stop` — cùng khuôn một-lần-thử-lại.
        so_lan_json_hong = 0
        # Cộng dồn usage qua MỌI lần thử — kể cả lần bị loại (content rỗng/JSON
        # cắt giữa chừng vẫn tốn token thật, `usage.include=true` ở `chat()`).
        # Không cộng dồn thì `cost_usd` chỉ phản ánh lần cuối, hiểu thấp chi phí
        # thật mỗi khi có thử lại — số này lên thẳng một khoá luận (review
        # round 1, Minor, 2026-09-02). Chỉ GHI ĐÈ khoá đã có trong `usage` của
        # lần cuối, KHÔNG thêm khoá mới: một khoá vắng mặt (vd. thiếu 'cost')
        # vẫn phải vắng mặt, để `_usage_from` còn raise đúng chỗ thay vì nhận
        # một số 0 bịa ra.
        tong: dict[str, int | float] = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
        for attempt in range(self.max_retries + 1):
            cho = self.retry_backoff_base * (2**attempt)
            try:
                r = self._http.post(url, json=body)
                r.raise_for_status()
                data = r.json()
                u = data.get("usage") or {}
                for k in tong:
                    tong[k] += u.get(k) or 0
                content, ly_do_dung = self._boc_content(data)
                # Task 1 (2026-09-02): `length` + ĐÃ xin `response_format`
                # (structured output) ⇒ JSON chắc chắn dở dang, dù `content`
                # không rỗng — không có "length nhưng vẫn đủ JSON" ở chế độ
                # này. Đo được trong 45-trap run: `rewrite_query` ăn
                # JSONDecodeError "Unterminated string" 2/45 lần theo đúng
                # hình dạng này. Không ép caller KHÔNG xin schema (hành văn tự
                # do có thể cố ý bị cắt dài) — chỉ structured output mới coi
                # `length` là lỗi tạm thời cần thử lại, cùng khuôn content rỗng.
                #
                # PHẢI đứng TRƯỚC nhánh content rỗng ngay dưới: cắt TOÀN BỘ
                # (model tiêu hết ngân sách cho suy luận + schema lớn, phát ra
                # 0 ký tự) vẫn có finish_reason=length + response_format, và đó
                # là ca CẤU TRÚC nhất — review round 2 (2026-09-02): nếu nhánh
                # content rỗng bắt trước, ca này ăn hẳn max_retries (4 lần gọi
                # HTTP trên `generate_claims`, node đắt nhất graph) thay vì
                # ngân sách RIÊNG một-lần-thử-lại mà lớp lỗi CẤU TRÚC này được
                # thiết kế để dùng (2 lần gọi).
                if ly_do_dung == "length" and "response_format" in body:
                    raise _JsonDoDangError(ly_do_dung)
                if not content.strip():
                    raise _ContentRongError(ly_do_dung)
                # Caller đã xin schema ⇒ content PHẢI là JSON. Kiểm ngay trong
                # vòng lặp: ra khỏi đây là hết lần thử, và một chuỗi không đóng
                # ở `finish_reason=stop` là lỗi không tất định — chính nó đã đẩy
                # `hieu_tai_lieu` xuống "Chưa đọc được tài liệu lúc này" trong
                # khi bấm lại thì lành (2026-09-18).
                if "response_format" in body:
                    try:
                        json.loads(content)
                    except json.JSONDecodeError as e:
                        raise _JsonHongError(e) from None
                if u:
                    data = {**data, "usage": {**u, **{k: v for k, v in tong.items() if k in u}}}
                return content, data
            except _ContentRongError as e:
                # Cạn retry vẫn NỔ, không trả chuỗi rỗng: node gọi nó (`route`,
                # `generate_claims`) sẽ nhận một câu trả lời hợp lệ-về-hình-dạng mà
                # trống nội dung — đúng lớp lỗi im lặng cả dự án chống.
                if attempt == self.max_retries:
                    raise ValueError(
                        f"model {model} trả content rỗng sau {attempt + 1} lần thử "
                        f"(finish_reason={e})"
                    ) from None
                logger.warning(
                    "model %s trả content rỗng (finish_reason=%s), thử lại (lần %d)",
                    model, e, attempt + 2,
                )
            except _JsonDoDangError as e:
                so_lan_length_cat += 1
                if so_lan_length_cat > 1 or attempt == self.max_retries:
                    # `tong` đã cộng dồn MỌI lần HTTP 200 của request này (lần cắt
                    # đầu lẫn lần thử lại) — đúng số tiền thật, không chỉ lần cuối.
                    raise TruncatedOutputError(
                        f"model {model}: JSON bị cắt giữa chừng (finish_reason={e}) sau "
                        f"{so_lan_length_cat} lần thử — có vẻ CẤU TRÚC (schema + ngữ cảnh cần "
                        f"nhiều token hơn provider chịu phát), không thử thêm",
                        usage=self._usage_from(model, {"usage": tong}),
                    ) from None
                logger.warning(
                    "model %s: JSON bị cắt giữa chừng (finish_reason=%s), thử lại 1 lần (lần %d)",
                    model, e, attempt + 2,
                )
            except _JsonHongError as e:
                so_lan_json_hong += 1
                if so_lan_json_hong > 1 or attempt == self.max_retries:
                    # Raise lại CHÍNH `JSONDecodeError` gốc, kèm `usage` cộng dồn
                    # của mọi lần thử: node bắt lỗi này (`hieu_tai_lieu`) đọc
                    # `getattr(e, "usage", ...)` để tính đúng tiền đã tiêu.
                    e.goc.usage = self._usage_from(model, {"usage": tong})
                    raise e.goc from None
                logger.warning(
                    "model %s: content là JSON hỏng dù finish_reason=%s, thử lại 1 lần (lần %d)",
                    model, ly_do_dung, attempt + 2,
                )
            except json.JSONDecodeError:
                # HTTP 200 kèm body không phải JSON là cùng lớp lỗi tạm thời với
                # content rỗng — gateway/proxy trả một trang HTML lỗi kèm mã 200.
                # Cạn retry vẫn để nó nổ nguyên trạng.
                if attempt == self.max_retries:
                    raise
                logger.warning(
                    "model %s: HTTP 200 nhưng body không phải JSON, thử lại (lần %d)",
                    model, attempt + 2,
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in _RETRYABLE_STATUS or attempt == self.max_retries:
                    raise
                cho = self._cho_bao_lau(e.response, cho)
                # Log ở CẢ hai nhánh này, đối xứng với nhánh content rỗng: thiếu nó,
                # một request có thể chờ tới ~90 giây (ba lần `Retry-After: 30` bị
                # chặn trần) mà không để lại một dấu vết nào.
                logger.warning(
                    "model %s: HTTP %d, chờ %.1fs rồi thử lại (lần %d)",
                    model, e.response.status_code, cho, attempt + 2,
                )
            except httpx.TransportError as e:
                if attempt == self.max_retries:
                    raise
                logger.warning(
                    "model %s: lỗi mạng %s, chờ %.1fs rồi thử lại (lần %d)",
                    model, type(e).__name__, cho, attempt + 2,
                )
            time.sleep(cho)
        raise AssertionError("unreachable")  # vòng lặp luôn raise hoặc return ở trên

    def chat(
        self, model: str, messages: list[dict], json_schema: dict | None = None, max_tokens: int | None = None,
    ) -> tuple[str, Usage]:
        """`max_tokens=None` (mặc định, mọi caller trước Phase 16) giữ hành vi
        CŨ Y HỆT: không gửi trường này, để provider tự quyết trần — đúng thứ
        brief Phase 16 R1 chỉ ra là "không ai biết là bao nhiêu". Caller nào
        biết trần THẬT của model mình gọi (đo được, không đoán — xem
        `hieu_tai_lieu.TOI_DA_TOKEN_RA`) thì truyền số đó vào, thay vì im lặng
        phó mặc một mặc định vô hình.

        Đã THỬ và BỎ (Phase 16, xem `.sdd/phase-16-report.md`): tắt hẳn suy
        luận (`reasoning: {max_tokens: 0}`) làm MỘT tài liệu dày bảng ổn định
        hơn trong ba lần gọi thô liên tiếp (luôn 8.133 token, `finish_reason=
        stop`), nhưng qua ĐỦ đường thật (kèm retry) lại một lần đẻ ra JSON DỞ
        DANG ở `finish_reason=stop` — hỏng NẶNG hơn `TruncatedOutputError` cũ
        vì `finish_reason` không còn là `length` nữa nên llm.py không bắt
        được, rơi thẳng xuống lỗi hạ tầng chung chung. Không đủ bằng chứng để
        khẳng định tắt suy luận AN TOÀN hơn — không thêm tham số đó ở đây."""
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "usage": {"include": True},  # bắt OpenRouter trả cost thật, xem docstring module
        }
        if json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "klaw", "strict": True, "schema": json_schema},
            }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        content, data = self._goi_va_lay_content(body, model)
        return content, self._usage_from(model, data)

    @staticmethod
    def _usage_from(model: str, data: dict) -> Usage:
        raw = data.get("usage")
        if not raw:
            raise ValueError(f"model {model}: response thiếu 'usage' — không thể lấy cost thật, không bịa số")
        missing = [k for k in ("prompt_tokens", "completion_tokens", "cost") if k not in raw]
        if missing:
            raise ValueError(f"model {model}: 'usage' thiếu trường {missing} — không bịa số: {raw}")
        return Usage(token_in=raw["prompt_tokens"], token_out=raw["completion_tokens"], cost_usd=float(raw["cost"]))


def from_settings() -> LlmClient:
    s = get_settings()
    return LlmClient(s.openrouter_api_key, s.openrouter_base_url, s.llm_temperature)


def router_model() -> str:
    return get_settings().openrouter_model_name


def generate_model() -> str:
    return get_settings().openrouter_generate_model_name


def _provider(model_id: str) -> str:
    """Phần trước dấu '/' — xấp xỉ THÔ của "họ model", KHÔNG phải bảo đảm:
    `gemini-2.5-flash-lite` và `gemini-2.5-flash` là hai chuỗi model khác nhau
    nhưng cùng provider "google" (đây chính là cặp nguy hiểm nhất — một validator
    so chuỗi đầy đủ `judge != generate` sẽ cho qua). Ngược lại, hai provider khác
    nhau vẫn có thể cùng lineage nếu một bên là fine-tune/rebrand — nên đây chỉ
    là tín hiệu để CẢNH BÁO, không phải bảo đảm để tự động chặn.
    """
    return model_id.split("/", 1)[0]


def judge_model() -> str:
    """Model cho vai judge (spec 7b.2): PHẢI khác họ với generate, nếu không judge
    thiên vị chính đầu ra của họ mình (self-preference bias) và tầng 2 verifier
    trở thành một sự yên tâm giả.

    Chỉ CẢNH BÁO qua log khi trùng provider — KHÔNG raise — vì hai lý do: (a)
    `_provider()` chỉ là xấp xỉ thô, hard-raise trên nó tạo cảm giác an toàn sai
    y hệt thứ ràng buộc này muốn tránh; (b) ablation Task 9 có thể cần cố ý phá
    ràng buộc để ĐO self-preference bias bằng thực nghiệm — hard-raise sẽ chặn
    đúng thực nghiệm đó.
    """
    g, j = generate_model(), get_settings().openrouter_judge_model_name
    if _provider(g) == _provider(j):
        logger.warning(
            "judge model '%s' cùng provider với generate model '%s' — rủi ro self-preference bias (spec 7b.2)", j, g
        )
    return j
