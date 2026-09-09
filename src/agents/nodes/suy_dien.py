"""Node `suy_dien` — QT-5, 0 token: suy vai của người hỏi từ chính câu hỏi khi hồ sơ chưa có.

Chỉ bắt ngôi thứ nhất rõ ràng ("tôi/em/mình" + việc xảy ra với họ) hoặc vai chủ doanh
nghiệp nói thẳng ("công ty tôi", "nhân viên của tôi", "tôi là giám đốc"). Câu hỏi chung
chung ("thử việc tối đa bao lâu") không được gán vai — thà không đoán còn hơn đoán sai,
và mọi giá trị ở đây mang nguồn `suy_dien` để giao diện in nghiêng kèm "(tôi đoán)" và
người hỏi sửa được một chạm. Nguồn `suy_dien` không bao giờ đè `nguoi_noi`/`tai_khoan`
(xem `bo_nho.gop_ho_so`).
"""

import re

NLD = "người lao động"
NSDLD = "người sử dụng lao động"

_NGOI_1 = r"\b(tôi|em|mình)\b"
_RE_NSDLD = re.compile(
    r"(công ty (tôi|em|mình|chúng tôi)|doanh nghiệp (tôi|chúng tôi)|nhân viên của (tôi|em|công ty)"
    r"|tôi là (giám đốc|chủ|trưởng phòng nhân sự|nhân sự|hr|quản lý|người sử dụng lao động)"
    r"|bên (tôi|em|mình) (tuyển|thuê|sa thải|kỷ luật|cho nghỉ|chấm dứt))",
    re.IGNORECASE,
)
_RE_NLD = re.compile(
    _NGOI_1
    + r".{0,40}?\b(nghỉ việc|thôi việc|xin nghỉ|đang thử việc|bị (sa thải|đuổi|cho nghỉ|trừ lương|kỷ luật|chậm lương)"
    r"|làm (ở|cho|tại) )|(nợ|chậm|trừ) lương " + _NGOI_1 + r"|hợp đồng lao động của " + _NGOI_1,
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
