"""Embedding qua OpenRouter /embeddings.

OpenRouter CÓ embedding — 36 model, chỉ hiện qua ?output_modalities=embeddings,
không hiện trong danh sách /models mặc định. baai/bge-m3: $0.010/1M, dim 1024,
VN-MTEB retrieval 39.84 (cao nhất nhóm ≤1B).
"""

import time

import httpx

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class EmbeddingClient:
    def __init__(self, api_key: str, base_url: str, model: str, dim: int) -> None:
        self.model = model
        self.dim = dim
        self.batch = 32
        self.max_retries = 3
        self.retry_backoff_base = 0.2  # giây; cạn retry vẫn raise, không swallow
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=120,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )

    def _post_with_retry(self, payload: dict) -> httpx.Response:
        # URL tuyệt đối: client thay thế trong test (không set base_url) sẽ vỡ
        # trên httpx>=0.28 nếu POST bằng path tương đối ("/embeddings").
        url = f"{self._base_url}/embeddings"
        for attempt in range(self.max_retries + 1):
            try:
                r = self._http.post(url, json=payload)
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

    def embed(self, texts: list[str]) -> list[list[float]]:
        if any(not t or not t.strip() for t in texts):
            raise ValueError("có text rỗng — không gọi API, sửa chunker")

        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch):
            lo = texts[i : i + self.batch]
            r = self._post_with_retry({"model": self.model, "input": lo})
            data = r.json().get("data") or []
            if len(data) != len(lo):
                raise ValueError(f"API trả {len(data)} vector cho {len(lo)} text")
            for item in sorted(data, key=lambda x: x["index"]):
                v = item["embedding"]
                if len(v) != self.dim:
                    raise ValueError(f"chiều vector {len(v)} ≠ cấu hình {self.dim}")
                out.append(v)
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


def from_settings() -> EmbeddingClient:
    from src.config import get_settings

    s = get_settings()
    return EmbeddingClient(
        api_key=s.openrouter_api_key,
        base_url=s.openrouter_base_url,
        model=s.openrouter_embedding_model_name,
        dim=s.openrouter_embedding_dim,
    )
