"""Client Công báo điện tử (`congbao.chinhphu.vn`) — tải văn bản hợp nhất `.docx`.

`robots.txt` của congbao là `User-agent: * / Allow: /`, và điều khoản công bố
chỉ yêu cầu *"ghi rõ nguồn 'congbao.chinhphu.vn' khi phát hành lại thông tin"*.
Cộng với Điều 15(2) Luật Sở hữu trí tuệ (văn bản QPPL không là đối tượng bảo hộ
quyền tác giả), việc tải và trích dẫn là hợp lệ, miễn ghi nguồn — `nguon` của
mỗi dòng `sua_doi_dieu_khoan` làm việc đó.

**KHÔNG chạm `thuvienphapluat.vn`** dưới bất kỳ hình thức nào: `Disallow: /` cho
ClaudeBot, `ai-train=no`, HTTP 403. Không đường vòng, không mirror, không dùng
mã văn bản của họ.

Congbao không có API JSON và không có sitemap; đường dẫn suy được là đủ:

    Chi tiết:  /van-ban/<slug>-<id>.htm
    Tải file:  https://g7.cdnchinhphu.vn/api/download/stream?Url=<token>&file_name=…

Token nằm sẵn trong HTML trang chi tiết, không cần ký. Tìm kiếm KHÔNG địa chỉ
hoá được bằng GET (`/tim-kiem?keyword=…` trả nguyên homepage) — muốn quét diện
rộng phải đi qua trang liệt kê `l7/trang-N`.
"""

import html
import re
import ssl
import time
from pathlib import Path

import certifi
import httpx

# Chứng chỉ trung gian mà CDN của congbao gửi thiếu. Xem đầu file PEM cho lý do
# đầy đủ; tóm tắt: cấp bù mắt xích thiếu để GIỮ xác thực, không phải tắt nó.
CHUNG_CHI_TRUNG_GIAN = (
    Path(__file__).resolve().parents[2] / "config" / "certs"
    / "globalsign-rsa-ov-ssl-ca-2018.pem"
)

# Quan sát thực trong khảo sát: không rate-limit nào chạm phải trong 21 lượt.
# 1,5 s là nhịp TỰ ĐẶT cho một máy chủ nhà nước không có API — không phải giới
# hạn đo được, mà là mức lịch sự. Đừng hạ.
NHIP_TOI_THIEU = 1.5

_RE_TAI = re.compile(r'https://[\w.-]*cdnchinhphu\.vn/api/download/stream\?[^"\'<>\s]+')


def lien_ket_docx(trang: str) -> str:
    """Link `.docx` trong HTML trang chi tiết.

    `html.unescape` là bắt buộc: HTML ghi `&amp;file_name=…`, giữ nguyên thì
    CDN đọc thành MỘT tham số `Url` mang cả phần `amp;file_name=…` dính vào và
    trả về file khác — hỏng âm thầm, vẫn HTTP 200.
    """
    for u in _RE_TAI.findall(trang):
        u = html.unescape(u)
        if ".docx" in u:
            return u
    raise ValueError(
        "không tìm thấy link .docx trong trang — văn bản cũ (trước ~2020) phát "
        "hành `.doc` (OLE nhị phân), parser OOXML không đọc được")


class CongBaoClient:
    """Chỉ GET, không auth, không CAPTCHA. User-Agent trung thực."""

    def __init__(self, sleep: float = NHIP_TOI_THIEU) -> None:
        self.sleep = max(sleep, 0.0)
        self._ssl = ssl.create_default_context(cafile=certifi.where())
        self._ssl.load_verify_locations(cafile=str(CHUNG_CHI_TRUNG_GIAN))
        self._http = httpx.Client(
            timeout=120,
            follow_redirects=True,
            verify=self._ssl,
            headers={"User-Agent": "klaw-thesis/1.0"},
        )

    def tai(self, url: str) -> httpx.Response:
        time.sleep(self.sleep)
        r = self._http.get(url)
        r.raise_for_status()
        return r

    def tai_vbhn(self, url_chi_tiet: str) -> bytes:
        """Trang chi tiết → bytes `.docx`. Hai lượt GET, mỗi lượt nghỉ `sleep`."""
        return self.tai(lien_ket_docx(self.tai(url_chi_tiet).text)).content
