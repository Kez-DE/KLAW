"""`services/prompts.py` — tiêm SOUL (spec 2026-09-06 §5.1)."""

from src.services.prompts import SOUL_PATH, messages, soul


def test_messages_co_soul_dat_system_truoc_user():
    m = messages("câu hỏi")
    assert [x["role"] for x in m] == ["system", "user"]
    assert m[0]["content"] == soul()
    assert m[1]["content"] == "câu hỏi"


def test_messages_khong_soul_chi_co_user():
    assert messages("x", co_soul=False) == [{"role": "user", "content": "x"}]


def test_soul_la_file_that_va_khong_co_ngoac_nhon():
    """SOUL nối vào prompt rồi `.format()` — một `{` lạc sẽ nổ KeyError ở
    runtime, không phải lúc import."""
    assert SOUL_PATH.exists()
    s = soul()
    assert len(s) > 1000
    assert "{" not in s and "}" not in s
    # Q1: SOUL phải NÊU quy tắc xưng "tôi" cho câu trả lời. Không cấm chữ "mình"
    # nói chung — trong chỉ dẫn gọi mô hình là "bạn", "mình" là phản thân
    # ("tự nhắc mình"), không phải cách xưng hô với người đọc.
    assert 'tự xưng "tôi"' in s, "Q1: SOUL thiếu quy tắc tự xưng 'tôi'"
