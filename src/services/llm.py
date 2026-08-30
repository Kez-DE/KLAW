"""LLM qua OpenRouter — ba vai, một key.

route/rewrite : OPENROUTER_MODEL_NAME
generate      : OPENROUTER_GENERATE_MODEL_NAME  (bắt buộc structured output)
judge         : OPENROUTER_JUDGE_MODEL_NAME     (nên khác họ với generate — spec 7b.2)

Mọi request gửi `usage: {include: true}` để OpenRouter luôn trả `cost` thật
trong `usage` — đã xác nhận bằng gọi API thật (xem task-3-report.md). Không có
trường này thì `Usage` sẽ phải bịa số, việc `chat()` cấm làm (raise thay vì đoán).
"""

import logging
import time
from dataclasses import dataclass

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


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
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=180,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )

    def _post_with_retry(self, body: dict) -> httpx.Response:
        # URL tuyệt đối: test thay `_http` bằng client chỉ có MockTransport (không
        # set base_url) sẽ vỡ trên httpx>=0.28 nếu POST bằng path tương đối — cùng
        # lý do EmbeddingClient._post_with_retry đã né bằng URL tuyệt đối.
        url = f"{self._base_url}/chat/completions"
        for attempt in range(self.max_retries + 1):
            try:
                r = self._http.post(url, json=body)
                r.raise_for_status()
                return r
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in _RETRYABLE_STATUS or attempt == self.max_retries:
                    raise
            except httpx.TransportError:
                if attempt == self.max_retries:
                    raise
            time.sleep(self.retry_backoff_base * (2**attempt))
        raise AssertionError("unreachable")  # vòng lặp luôn raise hoặc return ở trên

    def chat(self, model: str, messages: list[dict], json_schema: dict | None = None) -> tuple[str, Usage]:
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
        r = self._post_with_retry(body)
        data = r.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        if not content.strip():
            raise ValueError(f"model {model} trả content rỗng")
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
