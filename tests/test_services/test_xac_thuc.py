"""Xác minh JWT do Supabase phát — phần THUẦN, không DB, không mạng.

Test tự sinh khoá EC P-256 và tự ký token bằng CHÍNH thuật toán production
(ES256), nên toàn bộ file này chạy được mà KHÔNG cần một tài khoản Supabase nào.

Điểm patch là `urllib.request.urlopen` — tức lớp SOCKET, thấp nhất có thể. Mọi
thứ trên nó là đường thật của PyJWT: tra `kid`, khớp thuật toán, và ĐẶC BIỆT là
cache TTL. Đây không phải chi tiết vụn: PyJWT ghi cache BÊN TRONG
`PyJWKClient.fetch_data`, nên patch `fetch_data` (điểm patch hiển nhiên hơn) sẽ
thay thế đúng cái hàm ghi cache và test "JWKS có được cache không" trở thành một
test không bao giờ đo được thứ nó khẳng định — nó xanh vì mock, hoặc đỏ vì mock.

Bốn claim BẮT BUỘC được kiểm: chữ ký, `exp`, `aud`, `iss`. Mỗi cái một test —
bỏ bất kỳ cái nào là mở một đường vòng, nên mỗi cái phải có một test đỏ khi
người sau vô tình gỡ nó.
"""

import contextlib
import io
import json
import urllib.request
from datetime import UTC, datetime, timedelta
from urllib.error import URLError

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from src.config import Settings
from src.services import xac_thuc

_URL = "https://abcdefghijklmnop.supabase.co"
_ISS = f"{_URL}/auth/v1"
_AUD = "authenticated"
_SUB = "123e4567-e89b-12d3-a456-426614174000"
_KID = "khoa-thu-nghiem"


def _cap_khoa_ec(kid: str = _KID):
    """Khoá riêng để KÝ trong test + JWKS công khai tương ứng để XÁC MINH."""
    khoa = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(khoa.public_key()))
    jwk.update({"kid": kid, "use": "sig", "alg": "ES256"})
    return khoa, {"keys": [jwk]}


def _token(khoa, alg="ES256", kid=_KID, **ghi_de) -> str:
    claims = {
        "sub": _SUB,
        "email": "nguoi.dung@example.com",
        "aud": _AUD,
        "iss": _ISS,
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
        "role": "authenticated",
    }
    claims.update(ghi_de)
    return jwt.encode(claims, khoa, algorithm=alg, headers={"kid": kid})


@pytest.fixture
def cai_dat(monkeypatch):
    """Bật auth bằng cách CẤU HÌNH `supabase_url` — đúng cơ chế production."""

    def dat(**kw):
        mac_dinh = {"supabase_url": _URL}
        s = Settings(_env_file=None, **{**mac_dinh, **kw})
        monkeypatch.setattr(xac_thuc, "get_settings", lambda: s)
        return s

    return dat


@pytest.fixture(autouse=True)
def _don_cache_client():
    """`_client` là `lru_cache` nên một client (kèm JWKS đã cache trong nó) sẽ
    sống qua nhiều test và test sau xác minh bằng khoá của test trước.
    """
    xac_thuc._client.cache_clear()
    yield
    xac_thuc._client.cache_clear()


@pytest.fixture
def jwks(monkeypatch):
    """Nạp một JWKS cho endpoint giả, hoặc làm nó KHÔNG lấy được.

    Trả về bộ đếm số lượt gọi MẠNG thật (để test cache đo được thứ nó khẳng
    định). `bo_khoa=None` ⇒ `URLError`, đúng thứ `urllib` ném khi Supabase
    không kết nối được, và PyJWT bọc nó thành `PyJWKClientConnectionError`.
    """

    def nap(bo_khoa: dict | None) -> dict:
        dem = {"n": 0}

        if bo_khoa is None:

            def mo(req, timeout=None, context=None):
                dem["n"] += 1
                raise URLError("Supabase không kết nối được")

        else:

            @contextlib.contextmanager
            def mo(req, timeout=None, context=None):
                dem["n"] += 1
                yield io.BytesIO(json.dumps(bo_khoa).encode("utf-8"))

        monkeypatch.setattr(urllib.request, "urlopen", mo)
        return dem

    return nap


# ══ Chưa cấu hình Supabase = auth TẮT (bảo vệ eval của khoá luận) ═══════════


def test_chua_cau_hinh_thi_auth_TAT(cai_dat):
    cai_dat(supabase_url="")
    assert xac_thuc.da_cau_hinh() is False


def test_cau_hinh_roi_thi_auth_BAT(cai_dat):
    cai_dat()
    assert xac_thuc.da_cau_hinh() is True


def test_url_dan_ra_dung_issuer_va_jwks(cai_dat):
    # Chấp nhận cả URL có dấu `/` cuối — người cấu hình dán từ dashboard.
    assert xac_thuc.issuer(_URL + "/") == _ISS
    assert xac_thuc.jwks_url(_URL) == f"{_ISS}/.well-known/jwks.json"


# ══ Đường HỢP LỆ ════════════════════════════════════════════════════════════


def test_token_hop_le_thi_qua_va_tra_sub_email(cai_dat, jwks):
    cai_dat()
    khoa, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    ra = xac_thuc.xac_minh(_token(khoa))
    assert ra["sub"] == _SUB
    assert ra["email"] == "nguoi.dung@example.com"


def test_token_khong_co_email_van_qua(cai_dat, jwks):
    """Đăng nhập bằng số điện thoại không có `email`. `email` là để LIÊN HỆ,
    không phải để định danh — định danh là `sub`. Thiếu nó không được là 401.
    """
    cai_dat()
    khoa, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    ra = xac_thuc.xac_minh(_token(khoa, email=None))
    assert ra["sub"] == _SUB
    assert ra["email"] is None


def test_RS256_cung_duoc_chap_nhan(cai_dat, jwks):
    """Dự án Supabase chọn RSA 2048 thay P-256 vẫn phải chạy: cả hai đều là
    khoá BẤT ĐỐI XỨNG lấy từ JWKS, cùng một đường xác minh.
    """
    cai_dat()
    khoa = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(khoa.public_key()))
    jwk.update({"kid": _KID, "use": "sig", "alg": "RS256"})
    jwks({"keys": [jwk]})
    assert xac_thuc.xac_minh(_token(khoa, alg="RS256"))["sub"] == _SUB


# ══ Bốn claim bắt buộc — mỗi cái một test ═══════════════════════════════════


def test_het_han_thi_TU_CHOI(cai_dat, jwks):
    cai_dat()
    khoa, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    qua_han = _token(khoa, exp=datetime.now(UTC) - timedelta(seconds=1))
    with pytest.raises(xac_thuc.XacMinhError):
        xac_thuc.xac_minh(qua_han)


def test_thieu_exp_thi_TU_CHOI(cai_dat, jwks):
    """Không có `exp` = token VĨNH VIỄN. `verify_exp` một mình không chặn được
    ca này (không có gì để kiểm thì không có gì fail) — phải `require` nó.
    """
    cai_dat()
    khoa, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    claims = {"sub": _SUB, "aud": _AUD, "iss": _ISS}
    khong_exp = jwt.encode(claims, khoa, algorithm="ES256", headers={"kid": _KID})
    with pytest.raises(xac_thuc.XacMinhError):
        xac_thuc.xac_minh(khong_exp)


def test_sai_chu_ky_thi_TU_CHOI(cai_dat, jwks):
    """Ký bằng một khoá KHÁC khoá trong JWKS — đúng thứ kẻ tấn công làm."""
    cai_dat()
    _, bo_khoa = _cap_khoa_ec()
    khoa_khac, _ = _cap_khoa_ec()
    jwks(bo_khoa)
    with pytest.raises(xac_thuc.XacMinhError):
        xac_thuc.xac_minh(_token(khoa_khac))


def test_sai_aud_thi_TU_CHOI(cai_dat, jwks):
    cai_dat()
    khoa, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    with pytest.raises(xac_thuc.XacMinhError):
        xac_thuc.xac_minh(_token(khoa, aud="mot-du-an-khac"))


def test_sai_iss_thi_TU_CHOI(cai_dat, jwks):
    """Token thật, ký thật, nhưng do DỰ ÁN SUPABASE KHÁC phát. Không pin `iss`
    thì bất kỳ ai mở một project Supabase miễn phí cũng tự phát được token cho
    hệ thống này.
    """
    cai_dat()
    khoa, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    with pytest.raises(xac_thuc.XacMinhError):
        xac_thuc.xac_minh(_token(khoa, iss="https://ke-tan-cong.supabase.co/auth/v1"))


def test_thieu_sub_thi_TU_CHOI(cai_dat, jwks):
    """`sub` là khoá của bảng `users` và của hạn mức. Không có nó thì không có
    ai để tính hạn mức cho.
    """
    cai_dat()
    khoa, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    claims = {
        "aud": _AUD, "iss": _ISS, "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    with pytest.raises(xac_thuc.XacMinhError):
        xac_thuc.xac_minh(jwt.encode(claims, khoa, algorithm="ES256", headers={"kid": _KID}))


def test_sub_khong_phai_uuid_thi_TU_CHOI(cai_dat, jwks):
    """`users.sub` là cột UUID. Một `sub` không phải uuid phải bị chặn ở BIÊN
    (401 — vấn đề của token), không rơi xuống tầng DB rồi thành 503.
    """
    cai_dat()
    khoa, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    with pytest.raises(xac_thuc.XacMinhError):
        xac_thuc.xac_minh(_token(khoa, sub="'; DROP TABLE users; --"))


# ══ Thuật toán — allowlist, không tin header ════════════════════════════════


def test_alg_none_thi_TU_CHOI(cai_dat, jwks):
    """`alg: none` là một ĐÒN TẤN CÔNG, không phải một lựa chọn."""
    cai_dat()
    _, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    khong_ky = jwt.encode(
        {"sub": _SUB, "aud": _AUD, "iss": _ISS, "exp": datetime.now(UTC) + timedelta(hours=1)},
        key="", algorithm="none", headers={"kid": _KID},
    )
    with pytest.raises(xac_thuc.XacMinhError):
        xac_thuc.xac_minh(khong_ky)


def test_HS256_thi_TU_CHOI(cai_dat, jwks):
    """Nhầm thuật toán (alg confusion): kẻ tấn công lấy khoá CÔNG KHAI trong
    JWKS — ai cũng đọc được — dùng nó làm bí mật HMAC và tự ký một token.

    Token dưới đây ký bằng một bí mật BẤT KỲ, không phải bằng chính khoá công
    khai, vì PyJWT tự chặn biến thể đó ngay ở `encode` ("looks like a JWK and
    should not be used directly as an HMAC secret") — tức không dựng được token
    tấn công đúng khuôn bằng thư viện này. Điều đó KHÔNG làm bài test yếu đi:
    thứ đang được kiểm là allowlist thuật toán, và allowlist từ chối HS256 bất
    kể khoá là gì. Chặn vì `alg` không được phép, không vì đoán đúng ý định.
    """
    cai_dat()
    _, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    tu_ky = jwt.encode(
        {"sub": _SUB, "aud": _AUD, "iss": _ISS, "exp": datetime.now(UTC) + timedelta(hours=1)},
        key="bi-mat-ke-tan-cong-tu-chon-du-dai-32-byte", algorithm="HS256", headers={"kid": _KID},
    )
    with pytest.raises(xac_thuc.XacMinhError):
        xac_thuc.xac_minh(tu_ky)


# ══ JWKS không lấy được = TỪ CHỐI (fail closed) ═════════════════════════════


def test_JWKS_khong_lay_duoc_thi_TU_CHOI_khong_cho_qua(cai_dat, jwks):
    """Điểm quan trọng nhất của file này. Không lấy được khoá thì KHÔNG xác
    minh được, và không xác minh được thì từ chối — cho qua là biến một sự cố
    mạng của Supabase thành một cửa mở cho mọi token bịa.
    """
    cai_dat()
    khoa, _ = _cap_khoa_ec()
    jwks(None)
    with pytest.raises(xac_thuc.XacMinhError):
        xac_thuc.xac_minh(_token(khoa))


def test_kid_khong_co_trong_JWKS_thi_TU_CHOI(cai_dat, jwks):
    """Khoá đã bị rotate/thu hồi: JWKS lấy được nhưng không chứa `kid` này."""
    cai_dat()
    khoa, bo_khoa = _cap_khoa_ec(kid="khoa-cu-da-thu-hoi")
    jwks(bo_khoa)
    with pytest.raises(xac_thuc.XacMinhError):
        xac_thuc.xac_minh(_token(khoa, kid="khoa-khong-ton-tai"))


def test_rac_khong_phai_JWT_thi_TU_CHOI(cai_dat, jwks):
    cai_dat()
    _, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    for rac in ("", "khong-phai-jwt", "a.b.c"):
        with pytest.raises(xac_thuc.XacMinhError):
            xac_thuc.xac_minh(rac)


def test_JWKS_duoc_CACHE_khong_goi_lai_moi_request(cai_dat, jwks):
    """TTL cache: 5 lượt xác minh không được thành 5 lượt gọi mạng tới Supabase
    (mỗi lượt là một round-trip HTTP nằm trên đường request nóng).

    Test này phụ thuộc việc `_client` được `lru_cache`: cache TTL nằm BÊN TRONG
    client, nên dựng client mới mỗi request làm cache rỗng mỗi lần và mỗi request
    thành một lượt gọi mạng — hỏng theo hướng chậm và im lặng.
    """
    cai_dat()
    khoa, bo_khoa = _cap_khoa_ec()
    dem = jwks(bo_khoa)
    for _ in range(5):
        xac_thuc.xac_minh(_token(khoa))
    assert dem["n"] == 1


def test_ngoai_le_KHONG_mang_theo_token(cai_dat, jwks):
    """Token là bí mật của phiên (bearer). Nó không được nằm trong thông điệp
    ngoại lệ — thông điệp đó đi vào log, và log không phải nơi chứa token dùng
    được.
    """
    cai_dat()
    khoa_khac, _ = _cap_khoa_ec()
    _, bo_khoa = _cap_khoa_ec()
    jwks(bo_khoa)
    token = _token(khoa_khac)
    with pytest.raises(xac_thuc.XacMinhError) as e:
        xac_thuc.xac_minh(token)
    assert token not in str(e.value)
