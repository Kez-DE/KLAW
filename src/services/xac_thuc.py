"""Xác minh JWT do Supabase phát. Supabase làm AUTH; dữ liệu ở lại Postgres này.

Không nhân bản dữ liệu người dùng, không thêm một data plane thứ hai: Supabase
phát token, module này xác minh, `bao_ve` gắn nó vào hạn mức. Bảng `users` của
dự án chỉ giữ `sub` + những gì cần để cưỡng chế hạn mức và liên hệ.

## Vì sao chọn khoá BẤT ĐỐI XỨNG (ES256/RS256 qua JWKS), không phải HS256

Đã KIỂM LẠI tài liệu Supabase trước khi viết (cách này đã đổi, không chép từ
trí nhớ). Supabase hỗ trợ cả ba: HS256 (JWT secret dùng chung), ES256 và RS256
(khoá bất đối xứng, khoá công khai phát qua JWKS). Ba lý do chọn bất đối xứng:

1. **Từ 01/10/2025 mọi project MỚI của Supabase mặc định ký bất đối xứng
   (ES256).** Dự án này lập project mới, nên HS256 là đường LEGACY — viết code
   cho nó là viết cho một cấu hình phải đi bật lại bằng tay.
2. **Backend này không cần giữ một bí mật ĐỦ SỨC TỰ PHÁT token.** JWT secret của
   HS256 vừa xác minh vừa KÝ được: ai đọc được biến môi trường của backend
   (log, crash dump, `.env` lọt vào ảnh Docker) là tự phát được token cho bất kỳ
   `sub` nào, kể cả gói `pro`. Khoá công khai thì không ký được gì. Đây là khác
   biệt về BÁN KÍNH THIỆT HẠI, không phải sở thích.
3. **Rotate khoá không cần deploy lại.** JWKS phát nhiều khoá cùng lúc, nên xoay
   khoá ở Supabase là một thao tác ở Supabase — không phải một lần sửa biến môi
   trường trên mọi worker rồi restart.

Hệ quả kèm theo: KHÔNG có bí mật mới nào cần `secrets.compare_digest` trên
đường này (chỗ duy nhất còn so chuỗi bí mật là `bao_ve.kiem_api_key`, vẫn dùng
`compare_digest` trên bytes). Cách tốt nhất để so sánh an toàn một bí mật là
đừng có bí mật nào để so.

## Bốn thứ được xác minh, không thiếu cái nào

`chữ ký` + `exp` + `aud` + `iss`. Bỏ bất kỳ cái nào là mở một đường vòng:

* thiếu **chữ ký** — token là văn bản ai cũng viết được
* thiếu **`exp`** — một token rò rỉ dùng được vĩnh viễn. Chú ý: `verify_exp`
  một mình KHÔNG đủ, vì token không có claim `exp` thì không có gì để kiểm và
  nó lặng lẽ đi qua. Phải `require` nó.
* thiếu **`aud`** — token phát cho một mục đích khác (vd. `anon`) dùng được ở đây
* thiếu **`iss`** — bất kỳ ai mở một project Supabase miễn phí là tự phát được
  token hợp lệ cho hệ thống này. Đây là ca dễ bỏ sót nhất trong bốn ca.
"""

import logging
import uuid
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from src.config import get_settings

logger = logging.getLogger(__name__)

TEN_HEADER = "Authorization"
TIEN_TO_BEARER = "Bearer "

# ALLOWLIST thuật toán. Chỉ khoá bất đối xứng lấy từ JWKS — xem docstring trên.
#
# `HS256` CỐ Ý không có mặt, và đó là thứ chặn ĐÒN NHẦM THUẬT TOÁN: khoá công
# khai trong JWKS ai cũng đọc được, nên nếu HS256 được chấp nhận thì kẻ tấn công
# dùng chính khoá công khai đó làm bí mật HMAC và tự ký token hợp lệ. `none`
# cũng không có mặt: `alg: none` là một đòn tấn công, không phải một lựa chọn.
#
# Danh sách này TRUYỀN VÀO `jwt.decode`, nên header `alg` của token được đối
# chiếu với nó — không bao giờ được tin làm nguồn quyết định thuật toán.
THUAT_TOAN = ("ES256", "RS256")

# Claim BẮT BUỘC phải CÓ MẶT (khác với "được kiểm nếu có").
CLAIM_BAT_BUOC = ("exp", "aud", "iss", "sub")

# JWKS là một round-trip HTTP nằm trên đường request nóng. 5 giây, không phải
# mặc định 30 của PyJWT: một Supabase treo không được giữ một luồng threadpool
# 30 giây cho mỗi request đang chờ.
TIMEOUT_JWKS_GIAY = 5.0


class XacMinhError(Exception):
    """Token không dùng được — vì BẤT KỲ lý do gì.

    Một loại ngoại lệ duy nhất cho mọi nguyên nhân là CÓ CHỦ Ý: caller không
    được có cách nào phân biệt "hết hạn" với "sai chữ ký" với "sai `aud`" để
    rồi vô tình nói ra sự khác biệt đó cho client. Lý do cụ thể đi vào LOG.

    Thông điệp chỉ mang TÊN loại ngoại lệ gốc, không mang token: token là bí mật
    của phiên (bearer), và log không phải nơi chứa token còn dùng được.
    """


def _goc(url: str) -> str:
    return url.rstrip("/")


def issuer(url: str) -> str:
    """`iss` mà Supabase đặt vào token: `<url dự án>/auth/v1`.

    Suy ra TỪ `supabase_url` chứ không phải một biến môi trường riêng: hai biến
    phải khớp nhau mới đúng, và hai biến phải-khớp-nhau là một biến cộng một
    cách để cấu hình sai (pin `iss` sang một project khác project đang phát khoá
    thì mọi token đều bị từ chối, hoặc tệ hơn, ngược lại).
    """
    return f"{_goc(url)}/auth/v1"


def jwks_url(url: str) -> str:
    return f"{issuer(url)}/.well-known/jwks.json"


@lru_cache(maxsize=4)
def _client(url: str, ttl_giay: int) -> PyJWKClient:
    """PyJWKClient tự cache JWKS với TTL (`lifespan`) — KHÔNG viết cache thứ hai.

    `lru_cache` ở đây giữ cho CLIENT sống qua các request; nếu dựng client mới
    mỗi request thì cache TTL bên trong nó rỗng mỗi lần và mỗi request thành một
    lượt gọi mạng tới Supabase.
    """
    return PyJWKClient(
        jwks_url(url), cache_jwk_set=True, lifespan=ttl_giay, timeout=TIMEOUT_JWKS_GIAY
    )


def da_cau_hinh() -> bool:
    """Auth chỉ BẬT khi `KLAW_SUPABASE_URL` có giá trị.

    Chưa cấu hình ⇒ hệ thống hoạt động ĐÚNG NHƯ TRƯỚC. Đây không phải sự tiện
    lợi cho dev: `eval/run.py` chạy hàng trăm lượt để dựng bảng số liệu của khoá
    luận, và bảng đó không được phụ thuộc một tài khoản Supabase.
    """
    return bool(get_settings().supabase_url)


def token_tu_header(gia_tri: str | None) -> str | None:
    """Tách token khỏi `Authorization: Bearer <token>`. Không đúng khuôn → None."""
    if not gia_tri or not gia_tri.startswith(TIEN_TO_BEARER):
        return None
    return gia_tri[len(TIEN_TO_BEARER) :].strip() or None


def xac_minh(token: str) -> dict:
    """Trả `{"sub", "email"}` nếu token hợp lệ, ngược lại raise `XacMinhError`.

    FAIL CLOSED ở mọi nhánh, kể cả nhánh không phải lỗi của người dùng: JWKS
    không lấy được (Supabase sập, DNS hỏng, timeout) là TỪ CHỐI. Cho qua khi
    không lấy được khoá là biến một sự cố mạng của nhà cung cấp thành một cửa
    mở cho mọi token bịa — đúng lúc không ai đang xem log.

    I/O ĐỒNG BỘ (`urllib` bên trong PyJWKClient): caller PHẢI bọc
    `run_in_threadpool`. Xem `bao_ve.cong_bao_ve`.
    """
    s = get_settings()
    try:
        khoa = _client(s.supabase_url, s.supabase_jwks_ttl_giay).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            khoa.key,
            algorithms=list(THUAT_TOAN),
            audience=s.supabase_jwt_aud,
            issuer=issuer(s.supabase_url),
            options={"require": list(CLAIM_BAT_BUOC)},
        )
    except Exception as e:
        # KHÔNG `str(e)`: giữ bề mặt rò rỉ ở mức tên loại lỗi.
        logger.info("xac_minh: token bị từ chối (%s)", type(e).__name__)
        raise XacMinhError(f"token bị từ chối: {type(e).__name__}") from e

    sub = claims.get("sub")
    try:
        # `users.sub` là cột UUID. Chặn ở BIÊN để một `sub` dị dạng là 401 (vấn
        # đề của token) chứ không rơi xuống tầng DB rồi nổi lên thành 503.
        uuid.UUID(str(sub))
    except (ValueError, AttributeError, TypeError):
        logger.warning("xac_minh: `sub` không phải uuid — từ chối")
        raise XacMinhError("sub không phải uuid") from None

    # `email` để LIÊN HỆ, không để định danh — định danh là `sub`. Đăng nhập
    # bằng số điện thoại không có email, và đó không phải lý do từ chối.
    return {"sub": str(sub), "email": claims.get("email") or None}
