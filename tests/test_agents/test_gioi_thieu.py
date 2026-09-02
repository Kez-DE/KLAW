"""Câu hỏi VỀ CHÍNH TRỢ LÝ không phải câu hỏi pháp luật ngoài phạm vi.

Chủ dự án hỏi "bạn làm được những gì" và nhận về "Câu hỏi này nằm ngoài phạm vi
của hệ thống." Thông tin đúng nằm ngay bên dưới lời từ chối đó — nên hệ thống
BIẾT câu trả lời và vẫn chọn từ chối. Đó là hỏng ở khâu định tuyến, không phải
thiếu dữ liệu.

Hai câu này khác hẳn nhau và trước bản này dùng chung một lời đáp:

  "Thuế thu nhập cá nhân tính thế nào?"  → ngoài phạm vi THẬT, từ chối là đúng
  "bạn làm được những gì"                → hỏi về chính trợ lý, phải trả lời

`gioi_thieu` tách hai thứ đó. Nó KHÔNG gọi LLM để dựng câu trả lời — nội dung
là sự thật về hệ thống, đọc từ DB, nên 0 token cho khâu hành văn.
"""

from src.agents.nodes.assemble import ResultType, assemble
from src.agents.nodes.route import Intent


def test_intent_co_nhanh_gioi_thieu():
    assert Intent.gioi_thieu == "gioi_thieu"


def test_hoi_ve_tro_ly_KHONG_ra_out_of_scope():
    """Lỗi chủ dự án chỉ ra: câu hỏi về trợ lý bị đối xử như câu hỏi về thuế."""
    st = assemble({"query": "bạn làm được những gì", "intent": "gioi_thieu"}, {}, None, "")
    assert st["result_type"] != ResultType.out_of_scope, (
        "hỏi trợ lý làm được gì KHÔNG phải câu hỏi ngoài phạm vi — "
        "hệ thống biết câu trả lời và phải nói ra"
    )
    assert st["result_type"] == ResultType.gioi_thieu


def test_gioi_thieu_tra_loi_thay_vi_tu_choi():
    st = assemble({"query": "bạn là ai", "intent": "gioi_thieu"}, {}, None, "")
    ans = st["answer"] or ""
    assert ans, "phải CÓ câu trả lời, không được để rỗng như abstain"
    assert "ngoài phạm vi" not in ans, "không được mở bằng lời từ chối"
    # Nêu được cả hai việc nó làm, và nêu ra ranh giới — nói được mình làm gì
    # mà không nói được mình KHÔNG làm gì thì vẫn là quảng cáo, không phải
    # câu trả lời trung thực.
    assert "tra cứu" in ans.lower()
    assert "soạn thảo" in ans.lower()
    assert "thuế" in ans.lower(), "phải nêu thứ KHÔNG phủ, không chỉ khoe thứ phủ"


def test_gioi_thieu_khong_ton_token():
    """0 token: `llm=None` ở trên đã chứng minh — gọi LLM sẽ nổ AttributeError."""
    st = assemble({"query": "klaw là gì", "intent": "gioi_thieu"}, {}, None, "")
    assert st["traces"]["assemble_token_in"] == 0
    assert st["traces"]["assemble_token_out"] == 0


def test_ngoai_pham_vi_van_tu_choi_nhu_cu():
    """Mặt còn lại: câu hỏi pháp luật ngoài phạm vi VẪN phải bị từ chối."""
    st = assemble({"query": "thuế TNCN tính sao", "intent": "ngoai_pham_vi"}, {}, None, "")
    assert st["result_type"] == ResultType.out_of_scope
    assert st["answer"] is None
