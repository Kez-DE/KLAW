"""Ý định không cần tra cứu phải RẼ TẮT ở `route`, không đi hết graph.

ĐO ĐƯỢC 2026-09-02 (vòng thẩm định câu trả lời): `gioi_thieu` — nhánh có chú
thích "0 TOKEN" trong `assemble` — thực tế tiêu **8.975 token vào và dựng 15
luận điểm qua cả hai tầng kiểm** rồi vứt sạch. Đắt hơn `out_of_scope` **65
lần**.

Chú thích "0 TOKEN" không sai về `assemble`: khâu đó thật sự không gọi LLM.
Nó sai về thứ người đọc hiểu — vì `assemble` là node CUỐI, nên truy hồi, mở
rộng, sinh luận điểm và hai tầng kiểm chứng đã chạy xong hết trước khi tới
được nhánh ấy.

`ngoai_pham_vi` làm đúng từ đầu: nó rẽ tắt ở `add_conditional_edges("route",…)`.
Hai ý định không-cần-tra-cứu còn lại (`gioi_thieu`, `hoi_ve_kho`) phải đi cùng
đường đó.

`soan_thao` KHÔNG còn nằm trong nhóm rẽ tắt thẳng-tới-assemble (Task 19,
bo-nho-tinh-cach-soan-thao): trước đó soạn thảo chỉ có MỘT câu trả lời cố định
(gợi ý mở biểu mẫu), nên rẽ thẳng như ba ý định kia là đủ. Nay một lượt soạn
thảo cần GOM DỮ KIỆN qua nhiều lượt và có thể DỰNG một bản thảo thật ngay
trong hội thoại, nên nó có đường riêng qua `gom_du_kien`/`dung_ban_thao`.

Rẽ này gác CHỈ trên `intent` mà `route` VỪA đoán cho lượt này (state review,
sau khi lượt đầu triển khai đã tự xét thêm `soan_thao_dang_mo` — một hội
thoại đang soạn dở — như một điều kiện OR thứ hai). Bản đó bị bỏ có chủ đích:
`route.v3.md` đã có `{dang_soan}` để tự phân biệt câu trả lời dữ kiện/yêu cầu
sửa với một câu hỏi luật thật *dựa trên chính nội dung câu hỏi*; xét thêm
`soan_thao_dang_mo` sẽ ném phán đoán đó đi và ép MỌI lượt sau khi mở một
draft — kể cả một câu hỏi luật thật, kể cả `gioi_thieu`/`hoi_ve_kho`/
`ngoai_pham_vi` — đi qua `gom_du_kien`. `route` (đoán đúng) là nguồn sự thật
DUY NHẤT cho quyết định rẽ này.

Test khoá TOPO của graph chứ không khoá số token: đo token thật cần một lượt
gọi LLM 100–180 giây. Đường đi là thứ quyết định chi phí, và nó kiểm được
trong một phần nghìn giây.
"""

from src.agents.graph_tra_cuu import _re_sau_route, _vao_graph
from src.agents.nodes.route import Intent


def test_hai_y_dinh_khong_can_tra_cuu_deu_re_tat():
    for intent in (Intent.ngoai_pham_vi, Intent.gioi_thieu, Intent.hoi_ve_kho):
        assert _re_sau_route({"intent": intent}) == "assemble", f"{intent} phải rẽ tắt"


def test_hai_y_dinh_khong_can_tra_cuu_van_re_tat_du_dang_co_draft_mo():
    """Cùng test trên, nhưng với `soan_thao_dang_mo` còn ở phiên — MỘT hội
    thoại đang soạn dở KHÔNG được phép ép ba ý định rẽ tắt này đi chệch
    hướng: `route` đoán `gioi_thieu`/`hoi_ve_kho`/`ngoai_pham_vi` thì vẫn phải
    rẽ tắt y hệt, không bị kéo vào `gom_du_kien` chỉ vì có draft."""
    draft = {"loai": "hdld", "facts": {"x": "1"}, "ban_thao_id": None, "so_lan_sua": 0}
    for intent in (Intent.ngoai_pham_vi, Intent.gioi_thieu, Intent.hoi_ve_kho):
        assert _re_sau_route({"intent": intent, "soan_thao_dang_mo": draft}) == "assemble", (
            f"{intent} phải rẽ tắt dù đang có draft mở"
        )


def test_soan_thao_tuoi_di_hieu_tai_lieu_de_mo_hinh_tu_soan():
    """Phase 14 (R1/R2) — một yêu cầu soạn thảo MỚI của người đã đăng nhập đi
    thẳng `hieu_tai_lieu` (mô hình soạn, `muc_dich = tao_van_ban`), KHÔNG còn
    qua `gom_du_kien`: checklist không còn là cổng bắt buộc của đường chat, và
    một loại văn bản ngoài 29 mẫu không được rơi vào ngõ cụt "chưa có loại này".
    Đúng cả khi router đoán ĐƯỢC một loại checklist — khớp mẫu là một lời mời,
    không phải điều kiện (R3)."""
    assert _re_sau_route({"intent": Intent.soan_thao, "user_sub": "u"}) == "hieu_tai_lieu"
    goi_y = {"loai": "don_xin_nghi_viec", "ly_do": "", "thay_the": []}
    assert _re_sau_route({"intent": Intent.soan_thao, "user_sub": "u", "soan_thao_goi_y": goi_y}) == "hieu_tai_lieu"


def test_soan_thao_dang_gom_du_kien_van_di_gom_du_kien():
    """Phiên ĐANG có một checklist mở dở (`soan_thao_dang_mo`, vào từ
    `/sang-soan-thao` hoặc từ trước Phase 14) thì câu trả lời dữ kiện của
    người dùng vẫn về `gom_du_kien` — nhánh này chỉ xét SAU KHI `intent` đã là
    `soan_thao`, cùng khuôn hẹp Phase 3 đã dùng, không phải một phép xét
    trạng thái phiên đè lên ý định."""
    draft = {"loai": "hdld", "facts": {"x": "1"}, "ban_thao_id": None, "so_lan_sua": 0}
    assert _re_sau_route({"intent": Intent.soan_thao, "user_sub": "u", "soan_thao_dang_mo": draft}) == "gom_du_kien"


def test_soan_thao_khach_re_thang_assemble_khong_ton_token():
    """Khách chưa đăng nhập không có chỗ lưu bản thảo: rẽ thẳng `assemble` (0
    token, lời mời đăng nhập) thay vì trả tiền một lượt soạn rồi mới nói không
    lưu được."""
    assert _re_sau_route({"intent": Intent.soan_thao}) == "assemble"
    assert _re_sau_route({"intent": Intent.soan_thao, "user_sub": None}) == "assemble"


def test_soan_thao_re_sang_hieu_tai_lieu_khi_co_ban_thao_tong_quat_dang_mo():
    """Phase 3 Half B (R5), giữ nguyên dưới Phase 14: hội thoại đã có một bản
    thảo TỔNG QUÁT (`ban_thao_tong_quat_dang_mo`) thì ý định `soan_thao` đi
    `hieu_tai_lieu` (sửa bản thảo đang mở, `muc_dich = "sua_ban_thao"`)."""
    draft = {"id": "bt1", "loai": "tong_quat", "clauses": []}
    assert _re_sau_route({"intent": Intent.soan_thao, "user_sub": "u", "ban_thao_tong_quat_dang_mo": draft}) == "hieu_tai_lieu"


def test_ban_thao_tong_quat_dang_mo_khong_tu_no_doi_y_dinh_khac():
    """Cùng bất biến `test_draft_mo_KHONG_tu_no_re_qua_gom_du_kien...` ở dưới,
    áp cho trường state MỚI: có bản thảo tổng quát đang mở KHÔNG được ép một
    ý định KHÁC `soan_thao` đi chệch hướng — nó chỉ có tác dụng SAU KHI
    `intent` đã là `soan_thao`."""
    draft = {"id": "bt1", "loai": "tong_quat", "clauses": []}
    assert _re_sau_route({"intent": Intent.tra_cuu, "ban_thao_tong_quat_dang_mo": draft}) == "tien_de"
    assert _re_sau_route({"intent": Intent.tai_lieu, "ban_thao_tong_quat_dang_mo": draft}) == "hieu_tai_lieu"
    for intent in (Intent.ngoai_pham_vi, Intent.gioi_thieu, Intent.hoi_ve_kho):
        assert _re_sau_route({"intent": intent, "ban_thao_tong_quat_dang_mo": draft}) == "assemble"


def test_draft_mo_KHONG_tu_no_re_qua_gom_du_kien_khi_intent_la_tra_cuu():
    """Bug đã sửa: `soan_thao_dang_mo` một mình (không kèm `intent == soan_thao`)
    không còn ép lượt này qua `gom_du_kien` — một câu hỏi luật thật giữa lúc
    đang soạn phải đi hết đường tra cứu bình thường (`tien_de`), không bị hỏi
    lại dữ kiện. `route` đoán sai vẫn là rủi ro của `route`, không phải thứ
    graph tự sửa bằng cách nhìn vào trạng thái phiên."""
    draft = {"loai": "hdld", "facts": {"x": "1"}, "ban_thao_id": None, "so_lan_sua": 0}
    assert _re_sau_route({"intent": Intent.tra_cuu, "soan_thao_dang_mo": draft}) == "tien_de"


def test_tra_cuu_van_di_het_duong():
    assert _re_sau_route({"intent": Intent.tra_cuu}) == "tien_de"
    assert _re_sau_route({}) == "tien_de", "thiếu intent thì đi đường an toàn"
    assert _re_sau_route({"intent": "gia_tri_la"}) == "tien_de", "giá trị lạ đi đường an toàn"


def test_moi_y_dinh_KHONG_PHAI_tra_cuu_va_soan_thao_deu_phai_re_tat():
    """So HAI TẬP, không liệt kê tay — `test_hai_y_dinh_khong_can_tra_cuu_deu_re_tat`
    ở trên đếm hai tên cụ thể, nên một `Intent` thứ sáu thêm vào mà quên `_RE_TAT`
    vẫn để nó xanh. Đúng cách lỗi 8.975-token đã lọt lần đầu.

    Bất biến: `tra_cuu` (cần đi hết đường), `soan_thao` (đi qua `hieu_tai_lieu`
    hoặc `gom_du_kien`, Phase 14) và `tai_lieu` (đi qua `hieu_tai_lieu`, plan tài-liệu-tổng-quát) là
    những ý định DUY NHẤT không rẽ thẳng tới `assemble`. Mọi ý định khác trả lời
    được mà không cần một điều khoản nào, nên phải rẽ tắt.
    """
    from src.agents.graph_tra_cuu import _RE_TAT

    phai_re_tat = set(Intent) - {Intent.tra_cuu, Intent.soan_thao, Intent.tai_lieu}
    assert _RE_TAT == phai_re_tat, (
        f"thiếu trong _RE_TAT: {sorted(phai_re_tat - _RE_TAT)}; lạ trong _RE_TAT: {sorted(_RE_TAT - phai_re_tat)}"
    )
    for intent in phai_re_tat:
        assert _re_sau_route({"intent": intent}) == "assemble", f"{intent} phải rẽ tắt"


# ══════ Phase 3 Half B — fix round 1: _vao_graph không còn xét tai_lieu_phien


def test_vao_graph_khong_re_theo_tai_lieu_phien_mot_minh():
    """Fix round 1 (Q-C3) — bản mở rộng đầu tiên ("mọi lượt của một hội thoại
    có tài liệu vào thẳng hieu_tai_lieu, bất kể ý định") đã bị RÚT LẠI: nó vô
    hiệu hoá `route`/`giai_nghia`/`_RE_TAT` cho toàn bộ phần đời còn lại của
    một hội thoại từng nhận một tài liệu — một câu hỏi luật thật trong hội
    thoại đó không còn tới được đường truy hồi nữa. `tai_lieu_phien` MỘT MÌNH
    (không kèm `tai_lieu_ids` của chính lượt này) không còn rẽ tất định ở
    đây; đường đúng cho một câu hỏi VỀ tài liệu là `route.v4` tự chào
    `Intent.tai_lieu` rồi `_re_sau_route` đưa nó vào `hieu_tai_lieu` — xem
    `test_re_sau_route_dua_tai_lieu_vao_hieu_tai_lieu` bên dưới."""
    tep = [{"id": "x", "ten_tep": "form.docx"}]
    assert _vao_graph({"tai_lieu_phien": tep}) == "suy_dien"
    assert _vao_graph({"tai_lieu_phien": tep, "lich_su": [{"cau_hoi": "a", "tra_loi": "b"}]}) == "giai_nghia"


def test_vao_graph_khong_tai_lieu_di_duong_cu():
    """Không có tài liệu nào (mọi hội thoại KHÔNG liên quan tài liệu) — đường
    cũ giữ nguyên."""
    assert _vao_graph({}) == "suy_dien"
    assert _vao_graph({"lich_su": [{"cau_hoi": "a", "tra_loi": "b"}]}) == "giai_nghia"
    assert _vao_graph({"tom_tat": "x"}) == "giai_nghia"


def test_vao_graph_dinh_kem_tuoi_van_re_that_nhu_cu():
    """Đường CŨ, không đổi: một lượt VỪA đính kèm (`tai_lieu_ids` của chính
    lượt này) vẫn rẽ tất định 0 token, không phải qua `tai_lieu_phien`."""
    assert _vao_graph({"tai_lieu_ids": ["x"]}) == "hieu_tai_lieu"


def test_re_sau_route_dua_tai_lieu_vao_hieu_tai_lieu():
    """Cơ chế THẬT đứng sau một câu hỏi VỀ tài liệu ở lượt nối tiếp — có SẴN
    từ trước Phase 3 (`route.v4`/`Intent.tai_lieu`, quyết định chủ sở hữu
    Q4), không phải thứ lát cắt này dựng: một khi `route` đã gán đúng
    `Intent.tai_lieu`, `_re_sau_route` đưa THẲNG vào `hieu_tai_lieu`, không
    đụng gì tới `gom_du_kien` hay tới các ý định khác."""
    assert _re_sau_route({"intent": Intent.tai_lieu}) == "hieu_tai_lieu"
