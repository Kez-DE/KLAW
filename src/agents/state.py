from __future__ import annotations

from typing import TypedDict


class KLawState(TypedDict, total=False):
    """State schema cho graph tra cứu (spec mục 6) — LangGraph node nào cũng đọc
    và ghi vào đây. `total=False`: mọi field optional, node chạy sau phải tự
    `.get()` với mặc định, không được giả định field trước đã set.
    """

    # vào
    query: str
    # Lịch sử hội thoại do CLIENT gửi (`list[LuotTruoc]` đã `model_dump`), tối đa
    # 3 lượt gần nhất. Rỗng ở lượt đầu, và khi rỗng thì `giai_nghia` không chạy.
    # An toàn dù client bịa: lịch sử chỉ làm câu hỏi tự đứng được, nó không chống
    # đỡ khẳng định nào — xem docstring `nodes/giai_nghia.py`.
    lich_su: list[dict]
    as_of_date: object            # date | None
    config_name: str
    abstain_threshold: float
    # trung gian
    # Câu người dùng THẬT SỰ gõ, giữ lại vì `giai_nghia` THAY `query` bằng câu đã
    # giải nghĩa để cả pipeline chạy trên nó.
    cau_hoi_goc: str
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
    # `None` = lượt đầu, hoặc không giải nghĩa được. Giao diện chỉ hiện dòng
    # "Mình hiểu câu hỏi của bạn là: …" khi nó KHÁC `cau_hoi_goc` — giải nghĩa
    # sai là chế độ hỏng chắc chắn xảy ra, và không có dòng đó thì người dùng
    # nhận câu trả lời cho một câu họ không hỏi mà không có cách nào biết.
    cau_hoi_day_du: str | None
    result_type: object
    answer: str | None
    citations: list[dict]
    warnings: list[str]
    coverage_note: str | None
    trace_id: str
    # T4 — bảng dữ liệu (`services/kho.dung_bang`, `list[Bang]` đã `model_dump`)
    # cho lượt `hoi_ve_kho` xin trình bày dạng bảng. KHÔNG khai báo ở đây thì
    # LangGraph loại bỏ khoá này khỏi state trả về của `invoke`/`ainvoke` — nó
    # chỉ CARRY những khoá có tên trong `KLawState` qua khỏi node cuối, và
    # `n_assemble`/`assemble()` đã set khoá này ĐÚNG nhưng biến mất câm trước
    # khi tới `_payload_cache` (ĐO ĐƯỢC: test graph-thật báo `KeyError: 'bang'`
    # ở `st["bang"]` dù `assemble()` gọi riêng đã trả đúng khoá).
    bang: list[dict]
