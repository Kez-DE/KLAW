"""Tiêm SOUL — linh hồn dùng chung cho các node có hành văn hoặc phán đoán
(spec 2026-09-06 §5.1).

Tiêm ở: `assemble`, `hoi_lai`, `giai_nghia`, `draft_generate`, `generate_claims`.
KHÔNG tiêm ở `route`/`rewrite_query` (việc cơ học, tiết kiệm ~1.500–2.000
token/lượt) và TUYỆT ĐỐI không ở `verify_tier2`: đó là người thẩm định độc lập,
cùng một "linh hồn" với người viết làm mất tính độc lập mà `judge_model` khác họ
với `generate_model` đang cố giữ.

`lru_cache` vì file đọc một lần mỗi tiến trình là đủ; đổi SOUL thì khởi động lại.
"""

from functools import lru_cache
from pathlib import Path

SOUL_PATH = Path("prompts/soul.v2.md")


@lru_cache(maxsize=1)
def soul() -> str:
    return SOUL_PATH.read_text(encoding="utf-8")


def messages(user_prompt: str, *, co_soul: bool = True) -> list[dict]:
    """`[system(SOUL), user(prompt)]` — hoặc chỉ `user` khi `co_soul=False`."""
    he = [{"role": "system", "content": soul()}] if co_soul else []
    return [*he, {"role": "user", "content": user_prompt}]
