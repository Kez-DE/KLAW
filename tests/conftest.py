import os
from unittest.mock import AsyncMock

# TẮT ba tầng ĐỌC DB của cổng bảo vệ cho toàn bộ suite, TRƯỚC khi `src.main`
# (và qua đó `get_settings()`, một `lru_cache`) được import. Lý do: CI chạy
# `-m "not integration"` KHÔNG có Postgres, còn cổng nằm ở dependency của
# `/tra-cuu` — tức nó chạy TRƯỚC cả validation của pydantic, nên để mặc định
# production (10 lượt/60s, trần $2/ngày, cache 7 ngày) thì cả những test 422
# hiện có cũng cần một Postgres.
#
# Gán thẳng (không `setdefault`): giá trị phải TẤT ĐỊNH bất kể shell của người
# chạy đang export gì. Test nào kiểm chính các cổng này thì tự bật lại bằng cách
# patch `get_settings` TẠI ĐIỂM GỌI (xem `test_api/test_cong_bao_ve.py` và
# `test_api/test_cache_tra_cuu.py`) — cổng vẫn được phủ, chỉ không bật ngầm cho
# hàng trăm test không liên quan.
os.environ["KLAW_RATE_LIMIT_SO_LUOT"] = "0"
os.environ["KLAW_TRAN_CHI_PHI_NGAY_USD"] = "0"
os.environ["KLAW_CACHE_TTL_NGAY"] = "0"
os.environ["KLAW_API_KEY"] = ""

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from src.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock


def pid(duong_dan: str) -> int:
    """`provisions.id` của một neo trích dẫn, tra theo `duong_dan`.

    `id` là BIGSERIAL và `scripts.ingest` XOÁ-RỒI-CHÈN mỗi document có checksum
    đổi, nên số cụ thể KHÔNG bền qua một lần nạp lại: mọi test @integration viết
    id cứng sẽ đỏ sau mỗi lần sửa parser — đỏ vì một lý do KHÔNG liên quan đến
    điều nó muốn khoá, đúng loại nhiễu làm người ta bỏ qua CI.

    `duong_dan` mới là neo canonical của dự án: unique index
    `ux_provisions_neo_trich_dan` (migration 004) bắt nó duy nhất ở cấp trích
    dẫn được, nên phép tra này xác định.
    """
    from sqlalchemy import text

    from src.services.db import get_engine

    with get_engine().connect() as c:
        row = c.execute(text("SELECT id FROM provisions WHERE duong_dan = :d"),
                        {"d": duong_dan}).one_or_none()
    assert row is not None, f"không có provision nào ở {duong_dan!r} — corpus đã nạp chưa?"
    return row[0]
