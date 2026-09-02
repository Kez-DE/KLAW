"""C1 — `ProxyHeadersMiddleware` của uvicorn chạy TRƯỚC code của dự án.

`bao_ve.ip_goi` cố ý không tin `X-Forwarded-For`, nhưng uvicorn 0.52.4 mặc định
`proxy_headers=True` + `forwarded_allow_ips="127.0.0.1"`, nên nó THAY
`scope["client"]` bằng giá trị kẻ gọi gửi trước khi một dòng nào của
`src/` chạy. Chính sách không-tin ở tầng ứng dụng vì vậy vô hiệu, và rate limit
theo IP trở thành trang trí.

Test ở đây không khẳng định một hằng số cấu hình: nó (1) dựng đúng lớp
middleware uvicorn dựng để chứng minh đường tấn công có thật, và (2) NẠP ứng
dụng bằng chính CMD của `Dockerfile` qua bộ phân tích tham số THẬT của uvicorn,
rồi kiểm lớp middleware đó có mặt hay không trong app đã nạp.
"""

import json
import shlex
from pathlib import Path

import pytest
from starlette.requests import Request
from uvicorn.config import Config
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from src.config import Settings
from src.services import bao_ve

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def _cmd_dockerfile() -> list[str]:
    """Tham số của dòng `CMD [...]` trong Dockerfile, KHÔNG kể `uvicorn`.

    Đọc từ chính file sẽ được build, không chép tay: một CMD đổi mà test không
    đổi là đúng loại trôi dạt test này tồn tại để bắt.
    """
    for dong in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        # KHÔNG `strip()` trước: dòng thứ hai của `HEALTHCHECK` cũng bắt đầu
        # bằng `CMD ` sau khi bỏ thụt lề, và bắt nhầm nó thì test kiểm một câu
        # lệnh healthcheck thay vì câu lệnh chạy ứng dụng.
        if dong.startswith("CMD "):
            phan = dong[4:].strip()
            args = json.loads(phan) if phan.startswith("[") else shlex.split(phan)
            assert args[0] == "uvicorn", f"CMD không chạy uvicorn: {args[0]}"
            return args[1:]
    raise AssertionError("Dockerfile không có dòng CMD")


async def test_ProxyHeadersMiddleware_GHI_DE_client_bang_header_ke_goi_gui():
    """Đường tấn công, chứng minh bằng chính lớp uvicorn dùng.

    Không có test này thì `--no-proxy-headers` chỉ là một chuỗi trong Dockerfile
    mà không ai biết nó chặn cái gì.
    """
    thay: dict = {}

    async def app(scope, receive, send):
        thay["ip"] = bao_ve.ip_goi(Request(scope))
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    boc = ProxyHeadersMiddleware(app, trusted_hosts="127.0.0.1")
    await boc(
        {
            "type": "http",
            "scheme": "http",
            "client": ("127.0.0.1", 5555),
            "headers": [(b"x-forwarded-for", b"9.9.9.9"), (b"x-forwarded-proto", b"https")],
        },
        None,
        lambda msg: _nuot(msg),
    )
    # `ip_goi` KHÔNG tin XFF (mặc định `tin_proxy_header=False`) mà vẫn thấy
    # 9.9.9.9: bằng chứng việc thay `client` xảy ra ở tầng dưới nó.
    assert thay["ip"] == "9.9.9.9"


async def _nuot(msg):  # noqa: D103 - send() giả, test chỉ quan tâm scope
    return None


def test_CMD_cua_Dockerfile_nap_app_KHONG_kem_ProxyHeadersMiddleware():
    """Nạp app bằng đúng tham số CMD, qua chính `uvicorn.Config` — không so chuỗi.

    `Config.load()` là nơi uvicorn quyết định bọc `ProxyHeadersMiddleware`; kiểm
    app đã nạp là kiểm ĐÚNG thứ sẽ chạy trong container.
    """
    from uvicorn.main import main as uvicorn_cli

    ctx = uvicorn_cli.make_context("uvicorn", _cmd_dockerfile())
    assert ctx.params["proxy_headers"] is False, (
        "CMD của Dockerfile vẫn để uvicorn tin X-Forwarded-For "
        "(uvicorn mặc định proxy_headers=True, forwarded_allow_ips=127.0.0.1)"
    )

    cfg = Config(
        ctx.params["app"],
        host=ctx.params["host"],
        port=ctx.params["port"],
        proxy_headers=ctx.params["proxy_headers"],
    )
    cfg.load()
    assert not isinstance(cfg.loaded_app, ProxyHeadersMiddleware)


# ══ Lấy XFF từ PHẢI sang, không phải trái ═══════════════════════════════════


def _req(client_ip: str, xff: str | None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "client": (client_ip, 1234), "headers": headers})


@pytest.fixture
def tin_proxy(monkeypatch):
    def dat(**kw):
        s = Settings(_env_file=None, tin_proxy_header=True, **kw)
        monkeypatch.setattr(bao_ve, "get_settings", lambda: s)
        return s

    return dat


def test_mot_hop_tin_cay_thi_lay_phan_tu_CUOI(tin_proxy):
    """Proxy NỐI THÊM vào cuối, nên phần tử cuối là thứ proxy tin cậy tự ghi.

    Phần tử đầu do kẻ gọi tự viết: lấy nó là tin đúng thứ không được tin.
    """
    tin_proxy(so_hop_proxy_tin_cay=1)
    assert bao_ve.ip_goi(_req("10.0.0.1", "1.2.3.4, 203.0.113.9")) == "203.0.113.9"


def test_ke_goi_boi_them_hop_gia_KHONG_day_duoc_IP_that_ra_khoi_vi_tri(tin_proxy):
    tin_proxy(so_hop_proxy_tin_cay=1)
    xff = "evil-1, evil-2, evil-3, 203.0.113.9"
    assert bao_ve.ip_goi(_req("10.0.0.1", xff)) == "203.0.113.9"


def test_hai_hop_tin_cay_thi_lay_phan_tu_thu_hai_tu_phai(tin_proxy):
    """Hai proxy: P2 nối P1, P1 nối client → client ở vị trí thứ 2 từ phải."""
    tin_proxy(so_hop_proxy_tin_cay=2)
    assert bao_ve.ip_goi(_req("10.0.0.1", "1.2.3.4, 203.0.113.9, 10.0.0.2")) == "203.0.113.9"


def test_XFF_ngan_hon_so_hop_khai_bao_thi_ROI_VE_peer(tin_proxy):
    """Hỏng theo hướng CHẶN: header ngắn hơn khai báo nghĩa là chuỗi proxy không
    như cấu hình mô tả, và lúc đó đoán phần tử nào là client là đoán mò."""
    tin_proxy(so_hop_proxy_tin_cay=2)
    assert bao_ve.ip_goi(_req("10.0.0.1", "1.2.3.4")) == "10.0.0.1"


def test_XFF_rong_thi_ROI_VE_peer(tin_proxy):
    tin_proxy(so_hop_proxy_tin_cay=1)
    assert bao_ve.ip_goi(_req("10.0.0.1", "   ")) == "10.0.0.1"
