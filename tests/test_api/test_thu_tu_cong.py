"""H5 — cổng NHỊP phải chạy TRƯỚC cổng XÁC THỰC.

`cong_bao_ve` gọi `xac_thuc_nguoi_goi` trước `kiem_rate_limit`. PyJWT bỏ qua
TTL cache khi `kid` của token không khớp khoá nào đang cache
(`get_signing_key` → `get_signing_keys(refresh=True)`), nên MỖI token mang một
`kid` lạ ép một lượt HTTPS ra Supabase và giữ một luồng threadpool tới 5 giây
(`TIMEOUT_JWKS_GIAY`). Anyio mặc định 40 luồng.

Nghĩa là: 40 request/giây với `kid` ngẫu nhiên làm cạn threadpool và treo MỌI
endpoint khác — trong khi cổng nhịp, thứ tồn tại để chặn đúng loại lưu lượng
này, còn chưa được chạy. Cổng rẻ nhất phải đứng trước cổng đắt nhất.

Test đếm lượt gọi mạng THẬT qua đúng chỗ `khoa_ky` đã chọn để can thiệp
(`urllib.request.urlopen`, tầng socket), không đếm một hàm giả lập ở tầng trên.
"""

import contextlib
import io
import json
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from src.services import bao_ve, xac_thuc

_URL = "https://abcdefghijklmnop.supabase.co"
_ISS = f"{_URL}/auth/v1"
_CAU_HOI = {"query": "thử việc bao lâu"}


@pytest.fixture
def dem_jwks(monkeypatch):
    """Như `khoa_ky`, nhưng ĐẾM số lượt nạp JWKS thật sự rời khỏi tiến trình."""
    khoa = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(khoa.public_key()))
    jwk.update({"kid": "khoa-that", "use": "sig", "alg": "ES256"})
    dem = {"lan": 0}
    xac_thuc._client.cache_clear()

    @contextlib.contextmanager
    def mo(req, timeout=None, context=None):
        dem["lan"] += 1
        yield io.BytesIO(json.dumps({"keys": [jwk]}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", mo)
    yield khoa, dem
    xac_thuc._client.cache_clear()


def _token(khoa, kid: str) -> dict[str, str]:
    t = jwt.encode(
        {
            "sub": str(uuid.uuid4()), "email": "a@b.c", "aud": "authenticated",
            "iss": _ISS, "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        khoa, algorithm="ES256", headers={"kid": kid},
    )
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture
def chan_nhip(monkeypatch):
    """Cổng nhịp đã ĐẦY: mọi lượt gọi đều 429."""
    khoa_da_dem = []

    def chan(khoa, so_luot=None):
        khoa_da_dem.append(khoa)
        raise bao_ve.HTTPException(status_code=429, detail="quá nhịp")

    monkeypatch.setattr(bao_ve, "kiem_rate_limit", chan)
    return khoa_da_dem


async def test_bi_ham_nhip_thi_KHONG_nap_JWKS_lan_nao(client, cai_dat, dem_jwks, chan_nhip):
    """Đường tấn công: `kid` lạ ⇒ PyJWT refresh JWKS bất kể TTL.

    Cổng nhịp đứng trước nghĩa là kẻ gọi bị hãm KHÔNG mua được một round-trip
    HTTPS nào bằng một token họ tự bịa.
    """
    cai_dat(supabase_url=_URL)
    khoa, dem = dem_jwks

    r = await client.post(
        "/api/v1/tra-cuu", json=_CAU_HOI, headers=_token(khoa, f"kid-la-{uuid.uuid4()}")
    )

    assert r.status_code == 429
    assert dem["lan"] == 0, f"đã nạp JWKS {dem['lan']} lần cho một request bị hãm nhịp"


async def test_kid_la_THAT_SU_ep_mot_luot_nap_JWKS(client, cai_dat, dem_jwks, khong_dung_db,
                                                   graph_gia_lap, monkeypatch):
    """Chứng minh đường tấn công có thật, không phải giả thuyết: khi cổng nhịp
    KHÔNG chặn, mỗi `kid` lạ đúng là một lượt ra mạng."""
    cai_dat(supabase_url=_URL)
    monkeypatch.setattr(bao_ve, "kiem_rate_limit", lambda khoa, so_luot=None: None)
    khoa, dem = dem_jwks

    for _ in range(3):
        await client.post(
            "/api/v1/tra-cuu", json=_CAU_HOI, headers=_token(khoa, f"kid-la-{uuid.uuid4()}")
        )

    assert dem["lan"] >= 3, "TTL cache lẽ ra phải bị bỏ qua với kid lạ"


async def test_nguoi_da_dang_nhap_van_bi_dem_theo_ca_IP_va_sub(
    client, cai_dat, dem_jwks, khong_dung_db, graph_gia_lap, monkeypatch
):
    """Sau khi biết danh tính thì ĐẾM LẠI theo `user:{sub}`.

    Hai giỏ, hai mục đích: giỏ IP là lá chắn chạy được TRƯỚC khi biết ai đang
    gọi, giỏ `sub` là hạn mức thật của người đó. Bỏ giỏ thứ hai là để hai người
    sau cùng một NAT dùng chung một hạn mức.
    """
    cai_dat(supabase_url=_URL)
    khoa, _ = dem_jwks
    khoa_dem: list[str] = []
    monkeypatch.setattr(
        bao_ve, "kiem_rate_limit", lambda k, so_luot=None: khoa_dem.append(k)
    )

    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=_token(khoa, "khoa-that"))

    assert r.status_code == 200
    assert len(khoa_dem) == 2, f"đếm nhịp {len(khoa_dem)} lượt: {khoa_dem}"
    assert khoa_dem[0].startswith("chan-ip:"), "lượt ĐẦU phải là lá chắn theo IP"
    assert khoa_dem[1].startswith("user:"), "lượt SAU phải theo sub"


async def test_chua_cau_hinh_auth_van_ham_nhip_theo_IP_truoc(client, cai_dat, chan_nhip,
                                                             graph_gia_lap):
    cai_dat(supabase_url="")
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI)
    assert r.status_code == 429
    assert chan_nhip and chan_nhip[0].startswith("chan-ip:")


async def test_API_key_sai_van_dung_TRUOC_ca_cong_nhip(client, cai_dat, chan_nhip):
    """API key không tốn một truy vấn nào, nên nó giữ nguyên vị trí đầu tiên:
    một request không có quyền không nên làm hệ thống ghi một dòng DB."""
    cai_dat(api_key="khoa-that", supabase_url="")
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI)
    assert r.status_code == 401
    assert chan_nhip == [], "cổng nhịp chạy trước cả API key — thừa một lượt ghi DB"
