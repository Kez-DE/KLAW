"""Bốn phép tính trên số của tài liệu — chạy BẰNG MÃ, không bằng mô hình
(plan `tai-lieu-tong-quat.md` S4, FR-013).

Lý do tồn tại: "tổng điểm có khớp không" là câu hỏi mà một mô hình ngôn ngữ trả
lời sai một cách TỰ TIN. Ở đây mô hình chỉ được viết biểu thức bằng những con số
nó chép từ tài liệu; con số kết quả do `tinh` sinh ra, và `so_bang_nhau` đặt nó
cạnh con số tài liệu tự ghi. Mô hình không bao giờ là nguồn của `ket_qua_code`.

Hai ràng buộc định hình file:

**Không `eval`.** Biểu thức đến từ một mô hình đọc tài liệu của người lạ —
`eval` ở đây là một lỗ thực thi mã có thật, không phải một rủi ro lý thuyết.
`ast.parse(mode="eval")` rồi đi trên một DANH SÁCH CHO PHÉP các loại nút: mọi
thứ ngoài số, `+ - * /`, dấu âm và ngoặc đều trả `None`. Danh sách cho phép chứ
không phải danh sách cấm: thứ chưa nghĩ tới bị từ chối theo mặc định.

**`Decimal`, không `float`.** Đây là điểm số và tiền. `0,1 + 0,2 != 0,3` trong
nhị phân, và một phép so "khớp/không khớp" hiện thẳng ra giao diện thì không
được sai vì lý do biểu diễn.
"""

import ast
import operator
import re
from decimal import Decimal

__all__ = ["SAI_SO", "so_bang_nhau", "tinh", "viet_so"]

# Chênh lệch bỏ qua được khi so hai số. Không phải 0: hai đường tới cùng một
# con số (chuỗi tài liệu và phép chia của `tinh`) có thể lệch ở chữ số cuối.
SAI_SO = Decimal("1e-9")

# Bốn phép, không hơn. `**` không nằm ở đây vì `2**10**10` treo tiến trình bằng
# một biểu thức dài 9 ký tự.
_PHEP = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}

# Số quá 6 chữ số thập phân là kết quả của một phép chia lẻ; 28 chữ số của
# `Decimal` hiện ra màn hình chỉ làm người đọc mất tin vào con số.
_LAM_TRON = Decimal("1.000000")

_RE_SO = re.compile(r"\d[\d.,]*\d|\d")
_HONG = "!"  # ký tự không parse được — ép `ast.parse` ném SyntaxError


def _so_viet_sang_python(m: re.Match) -> str:
    """`2,0` → `2.0`; `20.000.000` → `20000000`; `1.234,56` → `1234.56`.

    Quy ước Việt: dấu phẩy là dấu thập phân, dấu chấm phân nhóm nghìn. Nhóm
    phải ĐÚNG ba chữ số mới được coi là phân nhóm — nếu không thì `10.0` (mười)
    biến thành `100`, và một phiếu điểm đọc sai gấp mười lần.
    """
    s = m.group(0)
    if "," in s:
        nguyen, _, thap_phan = s.partition(",")
        if "," in thap_phan:
            return _HONG
        return nguyen.replace(".", "") + "." + thap_phan
    phan = s.split(".")
    if len(phan) > 1 and all(len(p) == 3 for p in phan[1:]):
        return "".join(phan)
    return s


def _tinh_nut(n: ast.AST) -> Decimal | None:
    """Đi trên cây theo danh sách cho phép. `None` nghĩa là "không tính được",
    không bao giờ là một kết quả đoán."""
    if isinstance(n, ast.Constant) and isinstance(n.value, int | float) and not isinstance(n.value, bool):
        return Decimal(str(n.value))
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.UAdd | ast.USub):
        v = _tinh_nut(n.operand)
        return None if v is None else (-v if isinstance(n.op, ast.USub) else v)
    if isinstance(n, ast.BinOp) and type(n.op) in _PHEP:
        a, b = _tinh_nut(n.left), _tinh_nut(n.right)
        if a is None or b is None:
            return None
        try:
            return _PHEP[type(n.op)](a, b)
        except ArithmeticError:
            # Chia cho 0 (và mọi lỗi số học khác) là "không tính được", không
            # phải một ngoại lệ làm hỏng cả lượt trả lời.
            return None
    return None


def tinh(bieu_thuc: str) -> Decimal | None:
    """Giá trị của `bieu_thuc`, hoặc `None` khi nó không phải bốn phép trên số.

    `%` bị từ chối thẳng: "5 %" trong một tài liệu là một ĐƠN VỊ, không phải
    phép chia cho trăm, và đoán xem người viết định nói gì là đúng thứ file này
    tồn tại để không làm.
    """
    s = (bieu_thuc or "").strip()
    if not s or "%" in s:
        return None
    try:
        cay = ast.parse(_RE_SO.sub(_so_viet_sang_python, s), mode="eval")
    except (SyntaxError, ValueError):
        return None
    return _tinh_nut(cay.body)


def so_bang_nhau(a: str, b: str) -> bool:
    """Hai chuỗi số có cùng giá trị không, sau khi đọc theo cùng một quy ước.

    Đuôi `%` được bỏ ở CẢ HAI phía: "50%" và "50" là cùng một con số viết hai
    kiểu, và báo "không khớp" vì một ký tự đơn vị là một báo động giả.
    """
    x, y = tinh(_bo_phan_tram(a)), tinh(_bo_phan_tram(b))
    return x is not None and y is not None and abs(x - y) <= SAI_SO


def _bo_phan_tram(s: str) -> str:
    return (s or "").strip().removesuffix("%").strip()


def viet_so(d: Decimal) -> str:
    """`Decimal` → chuỗi kiểu Việt: dấu phẩy thập phân, không số 0 thừa."""
    if -d.as_tuple().exponent > 6:
        d = d.quantize(_LAM_TRON)
    return format(d.normalize(), "f").replace(".", ",")
