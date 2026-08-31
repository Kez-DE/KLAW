"""Client Công báo điện tử. Cùng khuôn `test_moj_client.py` — MockTransport,
không chạm mạng."""

import httpx
import pytest

from src.services.congbao_client import CongBaoClient, lien_ket_docx

TRANG = '''<html><body>
<a href="https://g7.cdnchinhphu.vn/api/download/stream?Url=TOKEN&amp;file_name=2026_131_18%2fVBHN-VPQH.pdf">PDF</a>
<a href="https://g7.cdnchinhphu.vn/api/download/stream?Url=TOKEN&amp;file_name=2026_131_18%2fVBHN-VPQH.docx">Word</a>
</body></html>'''


def _client(handler) -> CongBaoClient:
    c = CongBaoClient(sleep=0.0)
    c._http = httpx.Client(transport=httpx.MockTransport(handler))
    return c


def test_lien_ket_docx_bo_qua_pdf_va_giai_ma_entity():
    """`&amp;` trong HTML phải thành `&`; không giải mã thì CDN nhận một query
    param duy nhất tên `Url` mang cả `amp;file_name=…` và trả về sai file."""
    u = lien_ket_docx(TRANG)
    assert u.endswith(".docx") and "&file_name=" in u and "&amp;" not in u


def test_lien_ket_docx_khong_co_thi_nem_chu_khong_tra_None():
    """Congbao phát hành `.doc` (OLE) cho văn bản cũ. Trả `None` ở đây biến
    "trang này không có Word" thành một `TypeError` ở tận tầng tải."""
    with pytest.raises(ValueError, match="không tìm thấy"):
        lien_ket_docx("<html>không có link nào</html>")


def test_rate_limit_sleep_it_nhat_1_5_giay_giua_cac_request(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr("src.services.congbao_client.time.sleep", lambda s: calls.append(s))
    c = _client(lambda req: httpx.Response(200, text="ok"))
    c.sleep = 1.5
    c.tai("https://congbao.chinhphu.vn/a.htm")
    c.tai("https://congbao.chinhphu.vn/b.htm")
    assert calls == [1.5, 1.5]


def test_user_agent_trung_thuc_khong_gia_trinh_duyet():
    assert CongBaoClient(sleep=0.0)._http.headers["User-Agent"] == "klaw-thesis/1.0"


def test_mac_dinh_nhip_khong_duoi_1_5_giay():
    assert CongBaoClient().sleep >= 1.5


def test_http_loi_nem_ra():
    with pytest.raises(httpx.HTTPStatusError):
        _client(lambda req: httpx.Response(404, text="no")).tai("https://x/a.htm")


def test_chung_chi_trung_gian_duoc_nap_va_van_xac_thuc_day_du():
    """`g7.cdnchinhphu.vn` gửi THIẾU chứng chỉ trung gian GlobalSign, nên
    `httpx` mặc định ném CERTIFICATE_VERIFY_FAILED. Cách sửa là CẤP BÙ mắt
    xích thiếu — không phải `verify=False`: chuỗi vẫn phải chốt vào một root
    mà certifi tin, nên vẫn bắt được MITM."""
    ctx = CongBaoClient(sleep=0.0)._ssl
    assert ctx.verify_mode.name == "CERT_REQUIRED" and ctx.check_hostname is True
    chu_de = {c["subject"][-1][0][1] for c in ctx.get_ca_certs()}
    assert "GlobalSign RSA OV SSL CA 2018" in chu_de
