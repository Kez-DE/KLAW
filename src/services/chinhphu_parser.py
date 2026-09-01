"""Adapter: HTML `vanban.chinhphu.vn` → HTML mang class `prov-*` của MOJ.

Đây KHÔNG phải parser thứ hai. Nó chỉ gắn NHÃN CẤP cho từng thẻ rồi giao lại
cho `prov_parser.parse_provisions` — parser duy nhất của repo — nên toàn bộ bất
biến đã có (`_kiem_bat_bien`, `parse_anomalies`, quy tắc gộp tiêu đề bị tách,
bảng tách riêng, CITABLE không rỗng) chạy y nguyên trên nguồn mới. Đường nạp
MOJ không bị chạm một dòng nào.

**Vì sao phải có lớp này.** `prov_parser` mở đầu bằng "Đọc class `prov-*`,
KHÔNG regex tiếng Việt để nhận cấp" — đúng, VÌ MOJ đã gắn sẵn class. Trang
Chính phủ là bản xuất từ Word: 469 thẻ `<p class="MsoNormal">` phẳng, cấp bậc
chỉ còn nằm ở NHÃN mở đầu ("Điều 8.", "2.", "a)"). Không có class để đọc, nên
regex là đường DUY NHẤT. Lớp này nhốt toàn bộ phần regex vào một chỗ thay vì
rải nó vào parser chung.

**Vì sao cần nguồn này.** Bản MOJ của `02/2011/QH13` (doc_id 27325) bị tường
phí: 86 chỗ trong toàn văn bị thay bằng `<a class="clsBookmark
clsopentLogin">`, câu cụt giữa chừng — xem `KHONG_NAP` trong
`scripts/fetch_moj.py`. Bản Chính phủ đầy đủ, và nó còn ĐÚNG hơn ở một chỗ đã
đo được: Điều 31 Khoản 2 bản MOJ có HAI Điểm cùng nhãn `i)`, bản Chính phủ ghi
`i)` rồi `k)` — đúng bảng chữ cái pháp lý Việt Nam (a…h, i, k, không có j).

`robots.txt` của `vanban.chinhphu.vn` là `User-agent: * / Allow: /` (đã kiểm
2026-09-02), và Điều 15(2) Luật Sở hữu trí tuệ loại văn bản QPPL khỏi đối tượng
bảo hộ quyền tác giả — tải và trích dẫn hợp lệ, miễn ghi nguồn. `nguon_url` của
document làm việc đó. Cùng lý lẽ đã dùng cho `congbao_client.py`.
"""

import html as _html
import re

from bs4 import BeautifulSoup

from src.models.domain import Cap
from src.services.prov_parser import RE_SO, _text

CAP_TO_CLASS = {
    Cap.phan: "prov-part",
    Cap.chuong: "prov-chapter",
    Cap.muc: "prov-section",
    Cap.tieu_muc: "prov-subsection",
    Cap.dieu: "prov-article",
    Cap.khoan: "prov-clause",
    Cap.diem: "prov-item",
}

# Thứ tự thử KHÔNG tuỳ tiện: `Tiểu mục` phải đứng trước `Mục`, nếu không
# "Tiểu mục 1" khớp nhầm thành Mục. `RE_SO` của prov_parser đã lo việc đó bằng
# hai regex không chồng nhau (`^Tiểu\s+mục` vs `^Mục`), ở đây chỉ giữ đúng thứ
# tự cho chắc. Dùng LẠI `RE_SO` chứ không chép: một ngày nào đó sửa quy ước số
# hiệu ở prov_parser thì lớp này đi theo, không lệch âm thầm.
_THU_TU_CAU_TRUC = (Cap.phan, Cap.chuong, Cap.tieu_muc, Cap.muc, Cap.dieu)

# Khoản/Điểm dùng regex RIÊNG, CHẶT HƠN `RE_SO`, và đây là khác biệt có chủ ý.
# `RE_SO[Cap.khoan]` cho phép số rồi khoảng trắng ("1 Trường hợp…") vì ở MOJ nó
# chỉ chạy trên thẻ ĐÃ có class prov-clause — cái class đó là bằng chứng độc
# lập rằng đây là một Khoản. Ở đây không có bằng chứng nào ngoài chính cái
# nhãn, nên nới lỏng như vậy sẽ biến mọi câu văn mở đầu bằng một con số ("15
# ngày kể từ…") thành một Khoản giả. Buộc phải có dấu `.` hoặc `)`.
_RE_KHOAN = re.compile(r"^(\d+[a-zA-ZđĐ]*)\s*[.)]")
_RE_DIEM = re.compile(r"^([a-zăâđêôơư])\s*\)", re.IGNORECASE)

# Công thức BAN HÀNH chuẩn của văn bản QPPL Việt Nam — mốc bắt đầu KHỐI ĐUÔI
# (lời chứng thông qua + khối chữ ký). Xem `_khoi_duoi_tu` để biết vì sao phải
# nhận nó bằng chữ chứ không bằng vị trí.
_RE_KHOI_DUOI = re.compile(
    r"^(?:Luật|Bộ\s+luật|Pháp\s+lệnh|Nghị\s+quyết|Nghị\s+định|Thông\s+tư|Quyết\s+định)"
    r"\s+này\s+đã\s+được\b", re.IGNORECASE)


def _cap_cua(text: str) -> Cap | None:
    """Cấp suy từ NHÃN mở đầu. `None` = phần thân của node đang mở.

    `None` KHÔNG phải "bỏ qua": bên gọi gắn nhãn `prov-content`, và nguyên tắc
    1 của prov_parser ("KHÔNG WHITELIST") nối nó vào `noi_dung` của node đỉnh
    stack. Nhờ vậy phần mở đầu (quốc hiệu, căn cứ ban hành, "Quốc hội ban hành
    Luật khiếu nại.") và các đoạn tiêu đề bị tách rời không rơi mất.
    """
    for cap in _THU_TU_CAU_TRUC:
        if RE_SO[cap].match(text):
            return cap
    if _RE_DIEM.match(text):
        return Cap.diem
    if _RE_KHOAN.match(text):
        return Cap.khoan
    return None


def sang_html_prov(html: str, khoi_id: str = "block_detail") -> str:
    """Trang chi tiết → HTML phẳng mang class `prov-*`, ăn khớp `parse_provisions`.

    Chỉ lấy trong `div#<khoi_id>` — phần còn lại của trang là menu, breadcrumb
    và khối "văn bản liên quan"; nuốt chúng vào sẽ đẩy rác vào `noi_dung` của
    Điều cuối cùng, và bất biến CITABLE không bắt được vì nó chỉ kiểm RỖNG.
    """
    khoi = BeautifulSoup(html, "html.parser").find("div", id=khoi_id)
    if khoi is None:
        raise ValueError(
            f"không tìm thấy div#{khoi_id} — trang đổi cấu trúc; DỪNG thay vì "
            "parse cả trang, vì parse cả trang vẫn 'thành công' và cho ra một "
            "văn bản lẫn menu mà không phép kiểm nào bắt được")

    # `_text` của prov_parser, KHÔNG phải `get_text(" ")`. Nguồn này là bản xuất
    # từ Word và nó CẮT NGANG TỪ bằng thẻ inline: Điều 2 Khoản 1 có
    # `<i>Khiếu nạ</i>i`. Lấy text với dấu phân cách " " chèn khoảng trắng vào
    # giữa, cho ra "Khiếu nạ i" — sai chính tả ngay trong định nghĩa trung tâm
    # của cả đạo luật, và không phép kiểm nào bắt được vì chuỗi vẫn không rỗng.
    # `_text` nối liền và thay <br> bằng khoảng trắng trước — đúng bẫy #3 mà
    # module kia đã xử lý.
    doan = [t for p in khoi.find_all("p") if (t := _text(p))]
    bat_dau_duoi = _khoi_duoi_tu(doan)

    the: list[str] = []
    for i, text in enumerate(doan):
        if i >= bat_dau_duoi:
            # KHÔNG class. `_don_vi` trả dạng "text mồ côi" (cap None, tag None)
            # cho thẻ không mang class prov-*, và mốc `cuoi` của parse_provisions
            # bỏ qua chúng — nên cả khối rơi vào MỘT bản ghi `phu_luc`, cấp
            # KHÔNG trích dẫn được. Gắn `prov-content` như phần thân sẽ nhét lời
            # chứng thông qua và tên người ký vào Điều CUỐI của văn bản, biến
            # một câu trích lấy từ khối chữ ký thành "kiểm chứng thành công"
            # trên một neo Điều — đúng véc-tơ mà ruling chữ-đuôi đã đóng cho
            # nguồn MOJ. Đã đo trước khi sửa: Điều 70 của 02/2011/QH13 nuốt trọn
            # "…thông qua ngày 11 tháng 11 năm 2011. CHỦ TỊCH QUỐC HỘI (Đã ký)
            # Nguyễn Sinh Hùng".
            the.append(f"<p>{_html.escape(text)}</p>")
            continue
        cls = CAP_TO_CLASS.get(_cap_cua(text), "prov-content")
        the.append(f'<p class="{cls}">{_html.escape(text)}</p>')

    if not the:
        raise ValueError(f"div#{khoi_id} không có thẻ <p> nào có chữ")
    # `div.WordSection1` là khung mà prov_parser mong đợi (xem docstring của nó).
    return '<html><body><div class="WordSection1">' + "".join(the) + "</div></body></html>"


def _khoi_duoi_tu(doan: list[str]) -> int:
    """Chỉ số đoạn mở đầu KHỐI ĐUÔI; `len(doan)` nếu văn bản không có khối đuôi.

    Nguồn MOJ tách khối đuôi bằng CẤU TRÚC (nó nằm ngoài mọi thẻ `prov-*`), nên
    `parse_provisions` nhận ra bằng VỊ TRÍ và không cần đọc một chữ tiếng Việt
    nào. Trang Chính phủ KHÔNG cho tín hiệu cấu trúc đó: lời chứng thông qua và
    thân của Điều cuối cùng đều là `<p class="MsoNormal">`, khác nhau mỗi chỗ
    một bên nằm trong `<i>` — quá mỏng để dựa vào.

    Nên ở đây phải nhận bằng CHỮ, và chỗ đúng để làm việc đó là module này:
    adapter vốn đã là lớp đọc nhãn tiếng Việt ("Điều", "1.", "a)") vì nguồn
    không có class. `prov_parser` vẫn không phải học thêm một regex nào.

    Chỉ nhận công thức ban hành CHUẨN và chỉ khi nó xuất hiện SAU một thẻ cấu
    trúc — một Điều dẫn chiếu "Luật này đã được sửa đổi…" ở giữa thân văn bản
    thì `_RE_KHOI_DUOI` không khớp (nó đòi "đã được" ngay sau "này"), và nếu có
    khớp nhầm ở đoạn mở đầu thì điều kiện `da_co_cau_truc` chặn lại.
    """
    da_co_cau_truc = False
    for i, text in enumerate(doan):
        if _cap_cua(text) is not None:
            da_co_cau_truc = True
        elif da_co_cau_truc and _RE_KHOI_DUOI.match(text):
            return i
    return len(doan)
