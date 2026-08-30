from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class TraCuuRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    # `date`, KHÔNG PHẢI `str`: pydantic tự parse ISO ("2026-08-31") thành
    # `date` VÀ tự trả 422 cho chuỗi sai định dạng — endpoint không được nuốt
    # lỗi (Global Constraint). Nếu field này là `str`, `date` object mà
    # `n_expand`/`danh_gia` cần so sánh (`hl <= as_of`) sẽ nhận một chuỗi và
    # nổ TypeError ở giữa graph thay vì bị chặn sạch ở biên bởi FastAPI.
    as_of_date: date | None = None
    config_name: str | None = None


class CitationOut(BaseModel):
    provision_id: int
    duong_dan: str
    bo_luat: str
    so_ky_hieu: str
    quote: str
    hieu_luc: str | None = None
    tin_cay: str | None = None


class TraCuuResponse(BaseModel):
    result_type: Literal["answer", "partial_coverage", "abstain", "out_of_scope"]
    answer: str | None
    citations: list[CitationOut]
    warnings: list[str]
    coverage_note: str | None
    trace_id: str
    config_name: str
