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
    # Request frame from `rewrite_query` v3 (cai_thien GĐ2): {muc_tieu,
    # cau_hoi_phap_ly, du_kien_quyet_dinh_con_thieu[]} or None. A reading of the
    # question, never căn cứ. Declared here or LangGraph drops it silently.
    khung_yeu_cau: dict | None
    # Gợi ý loại văn bản của router (v2) → assemble kiểm và làm đầy → response
    # `soan_thao`. Khai ở đây vì cùng bẫy LangGraph với `bang`/`nguon`/`documents`.
    soan_thao_goi_y: dict | None
    # Router v3 (spec 2026-09-09 §7.4). `dang_tra_loi` là dạng câu trả lời mô
    # hình chọn ("van_xuoi"/"bang") — T15 dùng để rẽ nhánh bảng ở assemble.
    # `y_dinh_phu` là ý định PHỤ khi câu hỏi vừa hỏi luật vừa nhờ soạn thảo
    # ("soan_thao" hoặc None); `assemble` đọc nó để điền `soan_thao_goi_y`
    # trên nhánh `answer` mà không hijack `answer` (khác `Intent.soan_thao` —
    # ý định CHÍNH — nay đi qua `gom_du_kien`/`dung_ban_thao`, Task 19, xem
    # `graph_tra_cuu._re_sau_route`, KHÔNG còn nằm trong `_RE_TAT`).
    dang_tra_loi: str
    y_dinh_phu: str | None
    # Soạn thảo hội thoại (spec 2026-09-09 §8.2, Task 18). Trạng thái gom dữ kiện của
    # phiên đang mở: `loai`, `facts`, `ban_thao_id`, `so_lan_sua` (Task 17) cộng
    # `con_thieu`, `du`, `cu_soan` mà `nodes/gom_du_kien.py` tính mỗi lượt. `None` = chưa
    # mở phiên soạn thảo nào. Khai ở đây vì cùng bẫy LangGraph với `bang`/`nguon`/
    # `documents`/`soan_thao_goi_y`: thiếu dòng này thì khoá bị loại khỏi state trả về.
    soan_thao_dang_mo: dict | None
    # Chủ phiên hội thoại hiện tại — `gom_du_kien` (và các node sau nó) cần để tra/ghi
    # `ban_thao` đúng người, không đọc lại từ request HTTP.
    user_sub: str | None
    # Phiên hội thoại hiện tại (Task 19) — `dung_ban_thao` cần để gắn bản thảo
    # MỚI vào đúng cuộc hội thoại lúc `ban_thao.tao`. `None` khi ẩn danh (nhánh
    # đó không tới được vì `assemble` đã chặn ở `user_sub is None` trước).
    hoi_thoai_id: str | None
    # Bản thảo vừa dựng/sửa xong trong LƯỢT NÀY (Task 19, node `dung_ban_thao`)
    # — cùng bẫy LangGraph với `bang`/`soan_thao_dang_mo`: thiếu dòng này thì
    # khoá bị loại khỏi state trả về và `assemble` không bao giờ thấy nó.
    # `None` ở mọi lượt khác (kể cả lượt đang hỏi thêm dữ kiện, chưa dựng gì).
    ban_thao_ket: dict | None
    # Hai kết quả `assemble` đặt cho `TraCuuResponse.soan_thao_hoi`/`.ban_thao`
    # (Task 19) — PHẢI khai ở đây (`test_moi_field_TraCuuResponse_deu_duoc_KLawState_khai`):
    # cùng lớp lỗi đã cắn bốn lần trên `khop_tai_id`/`doc_id`/`bang`/`nguon`, LangGraph
    # loại ÂM THẦM một khoá `assemble()` đã set đúng nếu `KLawState` không khai nó.
    soan_thao_hoi: dict | None
    ban_thao: dict | None
    # Tài liệu người hỏi gửi (plan `tai-lieu-tong-quat.md` §Graph S2). `tai_lieu_ids`
    # là tài liệu ĐÍNH KÈM chính lượt này (đã kiểm chủ ở `routes._chuan_bi_phien`)
    # — khác rỗng thì graph rẽ TẤT ĐỊNH sang `hieu_tai_lieu`, 0 token.
    # `tai_lieu_phien` là mọi tài liệu hội thoại đang giữ (dòng của
    # `tai_lieu.tai_lieu_cua_hoi_thoai`), để `route.v4` biết có nên chào ý định
    # `tai_lieu` hay không và để lượt nối tiếp tìm lại tài liệu đã gửi.
    tai_lieu_ids: list[str]
    tai_lieu_phien: list[dict]
    # Phase 3 Half B (R5) — bản thảo TỔNG QUÁT mới nhất của hội thoại này, nếu
    # có, tính MỘT lần ở `routes._chuan_bi_phien`, khác `None` chỉ khi có danh
    # tính VÀ hội thoại này từng dựng một bản thảo tổng quát. Fix round 2 (N4)
    # — giá trị nay đến từ `ban_thao.ban_thao_tong_quat_dang_mo_nhe` (fix round
    # 1, PostgreSQL review), CHỈ mang `document`/`audit`, không phải bản đầy đủ
    # của `moi_nhat_cua_hoi_thoai` — không có `id`/`clauses`/`phien_ban`/…; xem
    # docstring hàm đó cho ba nơi đã kiểm là không cần cột nào khác.
    # Nơi đọc: `hieu_tai_lieu` cho mô hình thấy bản thảo ĐANG CÓ khi sửa (R4)
    # thay vì coi mọi lượt sửa là soạn lại từ đầu, và (Phase 14) chọn
    # `sua_ban_thao` thay vì mở bản thứ hai khi mô hình gán nhầm mục đích.
    # `_re_sau_route` không còn đọc nó từ Phase 14: mọi lượt `soan_thao` không
    # có checklist mở dở đều đi `hieu_tai_lieu`. KHÔNG phải `soan_thao_dang_mo`
    # (đó là dữ kiện checklist đang gom dở, một khái niệm khác), và không tự nó
    # ép một ý định khác (xem docstring `_re_sau_route`).
    ban_thao_tong_quat_dang_mo: dict | None
    # Việc người hỏi muốn làm với tài liệu trong lượt này (CONTEXT.md "mục đích").
    # Ghi lại KỂ CẢ khi lát cắt này chưa làm được nó — S4–S6 rẽ nhánh trên nó.
    muc_dich_tai_lieu: str | None
    # Kết quả đọc tài liệu (`TaiLieuKetQuaOut`) và neo điều khoản đưa sang đường
    # pháp lý. Cùng bẫy LangGraph với `bang`/`nguon`/`ban_thao`: không khai ở đây
    # thì khoá bị loại ÂM THẦM khỏi state trả về của `invoke`/`ainvoke`.
    tai_lieu_ket: dict | None
    # `TraCuuResponse.tai_lieu` — cái `assemble._base` phát hành, KHÁC
    # `tai_lieu_ket` (bản node vừa dựng) đúng như `ban_thao` khác `ban_thao_ket`.
    # Thiếu dòng này thì LangGraph loại khoá khỏi state trả về và `_payload_cache`
    # đọc ra `None`: lần thứ NĂM của lớp lỗi `khop_tai_id`/`doc_id`/`bang`/`nguon`.
    tai_lieu: dict | None
    tai_lieu_neo: list[dict]
    # Dữ kiện MỚI rút từ tài liệu trong lượt này (S4) — chờ ghi qua `tl.luu_du_kien`.
    tai_lieu_du_kien_moi: list[dict]
    # Văn bản MỚI mô hình soạn từ tài liệu ở lượt `tao_van_ban`/`sua_ban_thao`
    # (S6): `{tieu_de, muc: [{ten, noi_dung}]}`, ĐÃ qua phép làm sạch 0 token của
    # `hieu_tai_lieu.lam_sach_van_ban` — mọi con số trong nó đều tra ngược được
    # về tài liệu hay lời người hỏi. `None` ở mọi lượt khác. Cùng bẫy LangGraph
    # với `bang`/`nguon`/`ban_thao_ket`: không khai ở đây thì khoá bị loại ÂM
    # THẦM khỏi state trả về và node dựng bản thảo nhận `None` mãi mãi.
    van_ban_tong_quat: dict | None
    # Tài liệu có KHUÔN GỐC (P4b): thay cho `van_ban_tong_quat`, phép sửa ĐÃ KIỂM
    # của lượt `{viec_id, ten_tep, dinh_dang, phep_sua, bo_qua, cho_trong}` —
    # `phep_sua` là THAY ĐỔI của lượt (gộp vào phiên bản đang có ở
    # `dung_ban_thao_tong_quat`), `bo_qua` chỉ mang đơn vị/chỗ trống/lý do, không
    # mang giá trị. `None` ở mọi lượt khác. Cùng bẫy LangGraph với `van_ban_tong_quat`.
    khuon_tong_quat: dict | None
    # Lý do KHÔNG dựng được bản thảo tổng quát ở lượt này (hết trần sửa, chưa có
    # bản thảo nào để sửa, mô hình không soạn được mục nào). `assemble` biến nó
    # thành một lượt hỏi lại — một lượt soạn hỏng mà im lặng là tệ nhất.
    ban_thao_tong_quat_loi: str | None
    # Phase 12 part B — ký ức TÀI KHOẢN trong lượt này. `bo_nho_tai_khoan` là
    # những gì `bo_nho_tai_khoan.liet_ke(sub)` trả về: NGỮ CẢNH cho prompt, KHÔNG
    # phải nguồn để điền (chỉ khoá lượt này hỏi tới mới thành nguồn — xem
    # `hieu_tai_lieu._nguon_soan`). `bo_nho_moi` là điều người hỏi vừa tự khai,
    # chờ `graph_tra_cuu._ghi_bo_nho` ghi; `bo_nho_da_nho` là NHÃN của cái thật
    # sự mới hay đổi, để `assemble` nói "đã nhớ" đúng một lần và không nói gì
    # khi người ta nhắc lại y hệt. Cùng bẫy LangGraph với `bang`/`nguon`: không
    # khai ở đây thì khoá bị loại ÂM THẦM khỏi state trả về của `ainvoke`.
    bo_nho_tai_khoan: list[dict]
    bo_nho_moi: list[dict]
    bo_nho_da_nho: list[str]
