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
Ba ý định không-cần-tra-cứu phải đi cùng đường đó.

Test khoá TOPO của graph chứ không khoá số token: đo token thật cần một lượt
gọi LLM 100–180 giây. Đường đi là thứ quyết định chi phí, và nó kiểm được
trong một phần nghìn giây.
"""

from src.agents.graph_tra_cuu import _re_sau_route
from src.agents.nodes.route import Intent


def test_ba_y_dinh_khong_can_tra_cuu_deu_re_tat():
    """`soan_thao` nay cũng rẽ: từ 2026-09-02 nó trả về BÀN GIAO sang màn soạn
    thảo, không còn trả lời tra cứu, nên mọi thứ graph dựng cho nó đều bị vứt."""
    for intent in (Intent.ngoai_pham_vi, Intent.gioi_thieu, Intent.soan_thao):
        assert _re_sau_route({"intent": intent}) == "assemble", f"{intent} phải rẽ tắt"


def test_tra_cuu_van_di_het_duong():
    assert _re_sau_route({"intent": Intent.tra_cuu}) == "tien_de"
    assert _re_sau_route({}) == "tien_de", "thiếu intent thì đi đường an toàn"
    assert _re_sau_route({"intent": "gia_tri_la"}) == "tien_de", "giá trị lạ đi đường an toàn"


def test_moi_y_dinh_KHONG_PHAI_tra_cuu_deu_phai_re_tat():
    """So HAI TẬP, không liệt kê tay — `test_ba_y_dinh_khong_can_tra_cuu_deu_re_tat`
    ở trên đếm ba tên cụ thể, nên một `Intent` thứ năm thêm vào mà quên `_RE_TAT`
    vẫn để nó xanh. Đúng cách lỗi 8.975-token đã lọt lần đầu.

    Bất biến: `tra_cuu` là ý định DUY NHẤT cần truy hồi. Mọi ý định khác trả lời
    được mà không cần một điều khoản nào, nên phải rẽ tắt. Nếu tương lai có một ý
    định thật sự cần đi hết đường, test này buộc người thêm nó phải nói ra điều
    đó ở đây thay vì để chi phí lặng lẽ nhân lên trong hoá đơn.
    """
    from src.agents.graph_tra_cuu import _RE_TAT

    phai_re_tat = set(Intent) - {Intent.tra_cuu}
    assert _RE_TAT == phai_re_tat, (
        f"thiếu trong _RE_TAT: {sorted(phai_re_tat - _RE_TAT)}; "
        f"lạ trong _RE_TAT: {sorted(_RE_TAT - phai_re_tat)}"
    )
    for intent in phai_re_tat:
        assert _re_sau_route({"intent": intent}) == "assemble", f"{intent} phải rẽ tắt"
