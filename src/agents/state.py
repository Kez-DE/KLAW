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
    # Bộ nhớ phiên (spec 2026-09-09 §6): tóm tắt cuộn các lượt cũ hơn K, và hồ sơ tình
    # huống {khoa: {gia_tri, nguon}}. Cả hai là DỮ LIỆU về người hỏi — không chống đỡ khẳng
    # định nào.
    tom_tat: str | None
    ho_so: dict
    ho_so_da_dung: list[dict]
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
    # `list[NguonOut]` đã `model_dump` — văn bản CHI PHỐI câu hỏi, chỉ nhánh
    # `partial_coverage` điền (`assemble._phu_mot_phan`). LỖI CÓ SẴN, KHÔNG PHẢI
    # do T4 gây ra: field này được thêm ở commit 4488cb5 (trước T4), đi qua
    # `**kw` của `assemble._base()` đúng đường `bang` đi, nhưng CHƯA TỪNG được
    # khai ở đây — nên với mọi request HTTP thật, LangGraph loại bỏ khoá này
    # khỏi state trả về của `invoke`/`ainvoke` (cùng cơ chế đã ghi ở `bang` ngay
    # dưới), và `routes.py:111` biến `st.get("nguon")` thành `[]` vô điều kiện.
    # Tính năng "mở văn bản chi phối từ câu trả lời partial_coverage" đã chết
    # câm trong production từ 2026-08-31 tới khi fix round 1 (task-4) sửa dòng
    # này — xem `task-4-fix-round-1.md` finding 1.
    nguon: list[dict]
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
    # Spec 2026-09-06 §3.2 — `list[DocumentOut]` đã `model_dump`. Cùng bẫy với
    # `bang`/`nguon` ngay trên: KHÔNG khai ở đây thì LangGraph loại khoá này khỏi
    # state trả về và `documents[]` rỗng câm trong production.
    documents: list[dict]
    # `rewrite_query.v2` đoán lĩnh vực (`lao_dong`, `dan_su`…). Dùng để cộng
    # điểm mềm sau RRF (`retrieval.cong_diem_linh_vuc`), không loại gì.
    linh_vuc_du_doan: str | None
    # Gợi ý loại văn bản của router (v2) → assemble kiểm và làm đầy → response
    # `soan_thao`. Khai ở đây vì cùng bẫy LangGraph với `bang`/`nguon`/`documents`.
    soan_thao_goi_y: dict | None
