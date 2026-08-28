import json
import time
from pathlib import Path

import httpx


class MojClient:
    """Client cho API công khai của CSDL quốc gia về VBPL (Bộ Tư pháp).

    Không auth. Quan sát thực: HTTP 400 thoáng qua sau ~35 request liên tiếp,
    nên nghỉ `sleep` giây trước MỖI request.
    """

    def __init__(self, base: str, sleep: float) -> None:
        self.base = base.rstrip("/")
        self.sleep = sleep
        self._http = httpx.Client(timeout=60, headers={"User-Agent": "klaw-thesis/1.0"})

    def _get(self, path: str) -> dict:
        time.sleep(self.sleep)
        r = self._http.get(f"{self.base}{path}")
        r.raise_for_status()
        return r.json()

    def fetch_doc(self, doc_id: str) -> dict:
        payload = self._get(f"/doc/{doc_id}")
        if "data" not in payload or payload["data"] is None:
            raise ValueError(f"response cho doc {doc_id} thiếu 'data'")
        return payload["data"]

    def fetch_related(self, doc_id: str) -> list[dict]:
        payload = self._get(f"/doc/{doc_id}/related?pageNumber=0&pageSize=200")
        return (payload.get("data") or {}).get("items") or []

    def fetch_many(self, doc_ids: list[str], dest: Path) -> dict[str, Path]:
        dest.mkdir(parents=True, exist_ok=True)
        out: dict[str, Path] = {}
        for did in doc_ids:
            p = dest / f"{did}.json"
            if p.exists():
                out[did] = p
                continue
            p.write_text(json.dumps(self.fetch_doc(did), ensure_ascii=False), encoding="utf-8")
            print(f"[ok] {did} → {p.name}")
            out[did] = p
        return out
