"""Node `suy_dien` — QT-5, 0 token: suy vai của người hỏi từ chính câu hỏi khi hồ sơ chưa có.

Chỉ bắt ngôi thứ nhất rõ ràng ("tôi/em/mình" + việc xảy ra với họ) hoặc vai chủ doanh
nghiệp nói thẳng ("công ty tôi", "nhân viên của tôi", "tôi là giám đốc"). Câu hỏi chung
chung ("thử việc tối đa bao lâu") không được gán vai — thà không đoán còn hơn đoán sai,
và mọi giá trị ở đây mang nguồn `suy_dien` để giao diện in nghiêng kèm "(tôi đoán)" và
người hỏi sửa được một chạm. Nguồn `suy_dien` không bao giờ đè `nguoi_noi`/`tai_khoan`
(xem `bo_nho.gop_ho_so`).

Hai quyết định CỐ Ý sau khi review round 1 chỉ ra dương tính giả (finding 1, 2) và bảng
mẫu quá dễ (finding 3):

* "nhân viên của công ty" KHÔNG suy ra `NSDLD` — chỉ "nhân viên của tôi/em" (sở hữu cách
  thật) mới suy ra chủ doanh nghiệp. "Tôi là nhân viên của công ty ABC" là cách một nhân
  viên tự giới thiệu phổ biến nhất, và trước bản sửa này nó bị suy nhầm thành `NSDLD` vì
  `_RE_NSDLD` chạy trước và khớp ngay cụm "nhân viên của công ty". Câu tự giới thiệu này
  giờ khớp một mẫu riêng ở `_RE_NLD` ("tôi là nhân viên").
* "chủ" trong nhóm `tôi là (...)` có phủ định nhìn trước loại "chủ tịch": "chủ tịch công
  đoàn" (chủ tịch = chairman, đại diện NGƯỜI LAO ĐỘNG) không phải "chủ" (chủ = ông chủ,
  người SỬ DỤNG lao động) dù chuỗi "chủ" nằm trong đó — ranh giới từ (`\b`) không giúp gì
  ở đây vì hai âm tiết đã cách nhau bằng dấu cách sẵn, phải loại đích danh từ ghép đó.
  Không mở rộng cho các từ ghép khác bắt đầu bằng "chủ" (chủ nhật, chủ đề…) — chưa có ca
  thật nào cho thấy chúng gây dương tính giả trong miền câu hỏi lao động.
* "Tôi bị công ty cho nghỉ việc" (bị động chêm tác nhân) ĐÃ suy đúng `NLD` từ trước —
  không phải nhờ một mẫu dành riêng cho "bị <tác nhân> <động từ>", mà nhờ mẫu chung
  "nghỉ việc" khớp trùng ở cuối câu. Xác minh và GHIM lại bằng ca kiểm thử, không mở
  rộng thêm mẫu cho dạng câu này: một câu tương tự nhưng không có "nghỉ việc"/"thôi
  việc" ở cuối (vd. "tôi bị công ty sa thải") vẫn suy ra `None` — chấp nhận được, vì
  liệt kê hết các danh từ tác nhân ("công ty", "doanh nghiệp", "sếp"…) chỉ để bắt thêm
  một dạng câu là mở rộng bề mặt cho lợi ích nhỏ, ngược với "thà không đoán còn hơn đoán
  sai".
"""

import re

NLD = "người lao động"
NSDLD = "người sử dụng lao động"

_NGOI_1 = r"\b(tôi|em|mình)\b"
_RE_NSDLD = re.compile(
    # "nhân viên của (tôi|em)\b" — CHỈ sở hữu cách thật (finding 1: bỏ "công ty" khỏi
    # đây, "nhân viên của công ty ABC" không còn suy ra chủ doanh nghiệp).
    # "chủ(?!\s*tịch)\b" — loại từ ghép "chủ tịch" (finding 2), và `\b` chặn ở cuối mỗi
    # từ/cụm rời trong nhóm "tôi là (...)" dù ở đây phần lớn là chặn thừa (âm tiết tiếng
    # Việt vốn đã cách nhau bằng dấu cách) — thêm cho đúng ý kiểm review.
    r"(công ty (tôi|em|mình|chúng tôi)|doanh nghiệp (tôi|chúng tôi)|nhân viên của (tôi|em)\b"
    r"|tôi là (giám đốc|chủ(?!\s*tịch)|trưởng phòng nhân sự|nhân sự|hr|quản lý|người sử dụng lao động)\b"
    r"|bên (tôi|em|mình) (tuyển|thuê|sa thải|kỷ luật|cho nghỉ|chấm dứt))",
    re.IGNORECASE,
)
_RE_NLD = re.compile(
    # "tôi là nhân viên" — tự giới thiệu (finding 1), khớp trước để không phụ thuộc mẫu
    # "việc xảy ra với tôi" ở nhánh dưới.
    r"(" + _NGOI_1 + r"\s+là\s+nhân\s+viên\b"
    r"|"
    + _NGOI_1
    + r".{0,40}?\b(nghỉ việc|thôi việc|xin nghỉ|đang thử việc|bị (sa thải|đuổi|cho nghỉ|trừ lương|kỷ luật|chậm lương)"
    r"|làm (ở|cho|tại) )"
    r"|(nợ|chậm|trừ) lương " + _NGOI_1 + r"|hợp đồng lao động của " + _NGOI_1 + r")",
    re.IGNORECASE,
)


def suy_vai(cau: str) -> str | None:
    c = " ".join((cau or "").split())
    if _RE_NSDLD.search(c):
        return NSDLD
    if _RE_NLD.search(c):
        return NLD
    return None


def suy_dien(state: dict) -> dict:
    ho_so = {k: dict(v) for k, v in (state.get("ho_so") or {}).items() if isinstance(v, dict)}
    vai: str | None = None
    if not (ho_so.get("chu_the") or {}).get("gia_tri"):
        vai = suy_vai(state.get("cau_hoi_day_du") or state.get("query") or "")
        if vai:
            ho_so["chu_the"] = {"gia_tri": vai, "nguon": "suy_dien"}
    return {**state, "ho_so": ho_so, "traces": {**(state.get("traces") or {}), "suy_dien_chu_the": vai}}
