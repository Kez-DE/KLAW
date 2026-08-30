from __future__ import annotations

from typing import TypedDict


class KLawState(TypedDict, total=False):
    """State schema cho graph tra cứu (spec mục 6) — LangGraph node nào cũng đọc
    và ghi vào đây. `total=False`: mọi field optional, node chạy sau phải tự
    `.get()` với mặc định, không được giả định field trước đã set.
    """

    # vào
    query: str
    as_of_date: object            # date | None
    config_name: str
    abstain_threshold: float
    # trung gian
    intent: object
    tien_de_sai: str | None    # phép kiểm thứ sáu — lý do nếu câu hỏi tự nêu Điều không tồn tại
    queries: list[str]
    retrieved: list[int]
    expanded: list[dict]
    hits_shallow: list[dict]
    draft_claims: list
    insufficient_evidence: bool
    schema_error: bool
    tier1: list
    tier2: list
    traces: dict
    # ra
    result_type: object
    answer: str | None
    citations: list[dict]
    warnings: list[str]
    coverage_note: str | None
    trace_id: str
