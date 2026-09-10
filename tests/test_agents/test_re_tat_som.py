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

Test khoá TOPO của graph chứ không khoá số token: đo token thật cần một lượt
gọi LLM 100–180 giây. Đường đi là thứ quyết định chi phí, và nó kiểm được
trong một phần nghìn giây.
"""

from src.agents.graph_tra_cuu import _re_sau_route
from src.agents.nodes.route import Intent


def test_hai_y_dinh_khong_can_tra_cuu_deu_re_tat():
    for intent in (Intent.ngoai_pham_vi, Intent.gioi_thieu, Intent.hoi_ve_kho):
        assert _re_sau_route({"intent": intent}) == "assemble", f"{intent} phải rẽ tắt"


def test_soan_thao_re_qua_gom_du_kien_khong_phai_thang_toi_assemble():
    """`soan_thao` — ý định CHÍNH của lượt này, HOẶC một hội thoại đang soạn dở
    (`soan_thao_dang_mo` còn ở phiên, dù ý định lượt này đoán là gì) — đi
    `gom_du_kien` trước, không rẽ thẳng như `test_hai_y_dinh...` ở trên."""
    assert _re_sau_route({"intent": Intent.soan_thao}) == "gom_du_kien"
    assert _re_sau_route({"intent": Intent.tra_cuu, "soan_thao_dang_mo": {"loai": "hdld"}}) == "gom_du_kien"


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
