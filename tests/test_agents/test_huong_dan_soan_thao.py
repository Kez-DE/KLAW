"""Xin soạn văn bản ở ô chat không được rơi vào ngõ cụt.

ĐO ĐƯỢC 2026-09-02, trên máy chủ thật:

  "Soạn cho tôi một hợp đồng lao động xác định thời hạn 12 tháng"
  → answer · 4 trích dẫn · "Hợp đồng lao động xác định thời hạn bạn soạn có
    thể kéo dài từ 12 đến 36 tháng (Điều 20, Khoản 1, Điểm b)…"

Đúng luật, và không phải thứ người hỏi xin. Nguyên nhân: `intent == soan_thao`
không có nhánh riêng trong graph nên rơi thẳng vào đường tra cứu.

Cách chữa KHÔNG phải để chat tự soạn. Một bản thảo dựng từ văn xuôi tự do sẽ có
những điều khoản không neo được vào căn cứ nào — đúng thứ dự án tồn tại để
không làm. `POST /soan-thao` đòi `loai_van_ban` (để chọn checklist) và `facts`
(để điền và chạy rule) chính vì thế.

Cách chữa là BÀN GIAO: nói rằng việc này soạn được, nói vì sao cần biểu mẫu, và
chỉ đường. 0 token — đây là sự thật về hệ thống, không phải thứ cần suy luận.
"""

from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.route import Intent


def test_intent_soan_thao_khong_con_roi_vao_duong_tra_cuu():
    st = assemble({"query": "Soạn cho tôi hợp đồng lao động", "intent": Intent.soan_thao},
                  {}, None, "")
    assert st["result_type"] == ResultType.huong_dan_soan_thao


def test_noi_duoc_viec_nay_soan_duoc_va_chi_duong():
    st = assemble({"query": "Viết giúp tôi quyết định kỷ luật", "intent": "soan_thao"},
                  {}, None, "")
    ans = (st["answer"] or "").lower()
    assert ans, "phải CÓ câu trả lời, không để rỗng như abstain"
    assert "soạn thảo" in ans, "phải chỉ đường sang màn soạn thảo"
    # Nói VÌ SAO cần biểu mẫu. Thiếu câu này thì việc chuyển hướng đọc như một
    # lời từ chối có trang trí.
    assert any(t in ans for t in ("biểu mẫu", "dữ kiện")), "phải nói vì sao cần biểu mẫu"
    assert st["citations"] == [], "không trích dẫn: đây không phải câu trả lời pháp luật"


def test_khong_ton_token():
    """`llm=None` chứng minh: gọi LLM sẽ nổ AttributeError."""
    st = assemble({"query": "soạn hợp đồng", "intent": "soan_thao"}, {}, None, "")
    assert st["traces"]["assemble_token_in"] == 0
    assert st["traces"]["assemble_token_out"] == 0
