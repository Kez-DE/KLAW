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

from src.agents.graph_tra_cuu import _re_sau_route
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


def test_soan_thao_re_qua_gom_du_kien_khong_phai_thang_toi_assemble():
    """`soan_thao` — ý định CHÍNH mà `route` vừa đoán cho LƯỢT NÀY — đi
    `gom_du_kien` trước, không rẽ thẳng như `test_hai_y_dinh...` ở trên."""
    assert _re_sau_route({"intent": Intent.soan_thao}) == "gom_du_kien"


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

    Bất biến: `tra_cuu` (cần đi hết đường) và `soan_thao` (đi qua `gom_du_kien`,
    Task 19) là hai ý định DUY NHẤT không rẽ thẳng tới `assemble`. Mọi ý định
    khác trả lời được mà không cần một điều khoản nào, nên phải rẽ tắt.
    """
    from src.agents.graph_tra_cuu import _RE_TAT

    phai_re_tat = set(Intent) - {Intent.tra_cuu, Intent.soan_thao}
    assert _RE_TAT == phai_re_tat, (
        f"thiếu trong _RE_TAT: {sorted(phai_re_tat - _RE_TAT)}; lạ trong _RE_TAT: {sorted(_RE_TAT - phai_re_tat)}"
    )
    for intent in phai_re_tat:
        assert _re_sau_route({"intent": intent}) == "assemble", f"{intent} phải rẽ tắt"
