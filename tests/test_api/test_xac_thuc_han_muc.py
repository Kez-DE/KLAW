"""Auth Supabase + hạn mức theo NGƯỜI DÙNG trên hai endpoint tốn LLM.

Lệch pha mà file này đóng: frontend có đăng ký/đăng nhập/bảng giá, backend chỉ
có MỘT API key dùng chung. Hệ quả đo được của việc đó:
  * rate limit theo IP KHÔNG phân biệt hai người sau cùng một NAT
  * trần chi phí toàn hệ thống KHÔNG tính tiền được cho ai
  * bảng giá bán "50 lượt hỏi AI/tháng" mà không có gì cưỡng chế con số đó

Hai bất biến quan trọng nhất ở đây, cả hai đều dễ vô tình phá:
  1. **Chưa cấu hình Supabase ⇒ hành vi KHÔNG ĐỔI.** `eval/run.py` và mọi test
     hiện có phải chạy được mà không cần đăng nhập. Đây là test bảo vệ số liệu
     của khoá luận, không phải test tiện lợi cho dev.
  2. **Cache hit KHÔNG trừ lượt.** Nó không gọi LLM, không tốn tiền.
"""

import contextlib
import io
import json
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from urllib.error import URLError

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import text

from src.agents.nodes.assemble import ResultType
from src.config import Settings
from src.services import bao_ve, hoi_thoai, xac_thuc
from src.services.db import get_engine
from tests.test_api.test_han_muc_yaml import YAML_OK

_URL = "https://abcdefghijklmnop.supabase.co"
_ISS = f"{_URL}/auth/v1"
_KID = "khoa-thu-nghiem"
_CAU_HOI = {"query": "thử việc bao lâu"}


class _GraphGiaLap:
    async def ainvoke(self, *a, **k):
        return {"result_type": ResultType.answer, "answer": "x", "citations": [], "warnings": []}


@pytest.fixture
def cai_dat(monkeypatch):
    """Bật/tắt auth qua CẤU HÌNH `supabase_url` — đúng cơ chế production.

    Patch `get_settings` ở CẢ HAI module: `bao_ve` (cổng) và `xac_thuc` (auth).
    `get_settings()` là `lru_cache` toàn tiến trình nên đổi env giữa phiên không
    có tác dụng. Mặc định TẮT hai cổng đọc DB cũ để mỗi test bật đúng thứ nó kiểm.
    """

    def dat(**kw):
        mac_dinh = {"rate_limit_so_luot": 0, "tran_chi_phi_ngay_usd": 0.0, "supabase_url": _URL}
        s = Settings(_env_file=None, **{**mac_dinh, **kw})
        monkeypatch.setattr(bao_ve, "get_settings", lambda: s)
        monkeypatch.setattr(xac_thuc, "get_settings", lambda: s)
        return s

    return dat


@pytest.fixture
def khoa_ky(monkeypatch):
    """Khoá EC P-256 tự sinh + JWKS tương ứng. KHÔNG cần tài khoản Supabase.

    Patch ở `urllib.request.urlopen` (lớp socket), không ở `PyJWKClient.fetch_data`:
    PyJWT ghi cache JWKS bên TRONG `fetch_data`, nên patch hàm đó là thay đúng
    cái hàm ghi cache. Xem `tests/test_services/test_xac_thuc.py`.
    """
    khoa = ec.generate_private_key(ec.SECP256R1())
    jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(khoa.public_key()))
    jwk.update({"kid": _KID, "use": "sig", "alg": "ES256"})
    xac_thuc._client.cache_clear()

    @contextlib.contextmanager
    def mo(req, timeout=None, context=None):
        yield io.BytesIO(json.dumps({"keys": [jwk]}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", mo)
    yield khoa
    xac_thuc._client.cache_clear()


def _bearer(khoa, sub: str | None = None, **ghi_de) -> dict[str, str]:
    claims = {
        "sub": sub or str(uuid.uuid4()),
        "email": "nguoi.dung@example.com",
        "aud": "authenticated",
        "iss": _ISS,
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    claims.update(ghi_de)
    token = jwt.encode(claims, khoa, algorithm="ES256", headers={"kid": _KID})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def graph_gia_lap(monkeypatch):
    """Chặn mọi lượt LLM thật + mọi lượt ghi DB không thuộc phần đang kiểm."""
    from src.api import routes

    monkeypatch.setattr(routes, "_g", lambda: _GraphGiaLap())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)


@pytest.fixture
def khong_dung_db(monkeypatch):
    """Tách QUYẾT ĐỊNH hạn mức khỏi phần ĐỌC DB, để test wiring/thông điệp chạy
    được ở CI (`-m "not integration"`, không có Postgres). Phần SQL thật có test
    integration riêng ở cuối file.

    `ghi_nhan_nguoi_dung` giả không ghi dòng `users` thật, nhưng `/tra-cuu` (Task 3)
    giờ LUÔN gọi `hoi_thoai.tao_phien` cho request có danh tính không mang
    `hoi_thoai_id` — insert đó có FK vào `users`. Giả luôn `tao_phien`/`ghi_luot`
    ở đây để mọi test dùng fixture này không chạm Postgres cho bảng `hoi_thoai`.
    """
    monkeypatch.setattr(bao_ve, "ghi_nhan_nguoi_dung", lambda sub, email: "free")
    monkeypatch.setattr(bao_ve, "dem_luot", lambda sub, ep, moc: 0)
    monkeypatch.setattr(hoi_thoai, "tao_phien", lambda *a, **k: "00000000-0000-0000-0000-000000000000")
    monkeypatch.setattr(hoi_thoai, "ghi_luot", lambda *a, **k: 1)


# ══ 1. Chưa cấu hình Supabase ⇒ hành vi KHÔNG ĐỔI (bảo vệ eval) ═════════════


async def test_chua_cau_hinh_supabase_thi_KHONG_can_dang_nhap(client, cai_dat, graph_gia_lap):
    """Bất biến quan trọng nhất của lượt này. `eval/run.py` chạy hàng trăm lượt
    và bảng số liệu khoá luận không được phụ thuộc một tài khoản Supabase.
    """
    cai_dat(supabase_url="")
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI)
    assert r.status_code == 200


async def test_chua_cau_hinh_thi_token_rac_cung_KHONG_lam_hong(client, cai_dat, graph_gia_lap):
    """Auth tắt = header bị BỎ QUA, không phải "được kiểm rồi cho qua"."""
    cai_dat(supabase_url="")
    r = await client.post(
        "/api/v1/tra-cuu", json=_CAU_HOI, headers={"Authorization": "Bearer rac"}
    )
    assert r.status_code == 200


async def test_chua_cau_hinh_thi_KHONG_ap_han_muc(client, cai_dat, graph_gia_lap, monkeypatch):
    """Không có người dùng thì không có ai để tính hạn mức. Hàm đếm không được
    gọi lần nào — gọi nó là một round-trip Postgres vô nghĩa trên mỗi request.
    """
    cai_dat(supabase_url="")

    def no(*a, **k):
        raise AssertionError("KHÔNG được đếm hạn mức khi Supabase chưa cấu hình")

    monkeypatch.setattr(bao_ve, "dem_luot", no)
    monkeypatch.setattr(bao_ve, "ghi_nhan_nguoi_dung", no)
    assert (await client.post("/api/v1/tra-cuu", json=_CAU_HOI)).status_code == 200


# ══ 2. Đã cấu hình ⇒ BẮT BUỘC token hợp lệ ══════════════════════════════════


async def test_thieu_header_thi_401(client, cai_dat, graph_gia_lap, khong_dung_db):
    cai_dat()
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI)
    assert r.status_code == 401


async def test_token_hop_le_thi_qua(client, cai_dat, khoa_ky, graph_gia_lap, khong_dung_db):
    cai_dat()
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=_bearer(khoa_ky))
    assert r.status_code == 200


async def test_token_het_han_thi_401(client, cai_dat, khoa_ky, graph_gia_lap, khong_dung_db):
    cai_dat()
    h = _bearer(khoa_ky, exp=datetime.now(UTC) - timedelta(seconds=1))
    assert (await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=h)).status_code == 401


async def test_sai_chu_ky_thi_401(client, cai_dat, khoa_ky, graph_gia_lap, khong_dung_db):
    cai_dat()
    khoa_khac = ec.generate_private_key(ec.SECP256R1())
    h = _bearer(khoa_khac)
    assert (await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=h)).status_code == 401


async def test_sai_aud_thi_401(client, cai_dat, khoa_ky, graph_gia_lap, khong_dung_db):
    cai_dat()
    h = _bearer(khoa_ky, aud="du-an-khac")
    assert (await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=h)).status_code == 401


async def test_sai_iss_thi_401(client, cai_dat, khoa_ky, graph_gia_lap, khong_dung_db):
    cai_dat()
    h = _bearer(khoa_ky, iss="https://ke-tan-cong.supabase.co/auth/v1")
    assert (await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=h)).status_code == 401


async def test_header_sai_dinh_dang_thi_401(client, cai_dat, khoa_ky, graph_gia_lap, khong_dung_db):
    """Thiếu tiền tố `Bearer`, hoặc dùng scheme khác."""
    cai_dat()
    for h in ({"Authorization": "abc.def.ghi"}, {"Authorization": "Basic abc"}):
        r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=h)
        assert r.status_code == 401, h


async def test_401_KHONG_ro_ly_do_noi_bo(client, cai_dat, khoa_ky, graph_gia_lap, khong_dung_db):
    """Client nhận "phiên không hợp lệ", KHÔNG nhận "thiếu claim aud". Nói cho
    người thăm dò biết claim nào sai là chỉ cho họ đường đi tiếp.
    """
    cai_dat()
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=_bearer(khoa_ky, aud="x"))
    body = r.text.lower()
    for ro_ri in ("aud", "iss", "jwks", "signature", "claim", "audience", "issuer"):
        assert ro_ri not in body, f"401 rò rỉ chi tiết nội bộ: {ro_ri}"


async def test_soan_thao_cung_can_token(client, cai_dat, graph_gia_lap, khong_dung_db):
    """`/soan-thao` cũng tốn một lượt LLM thật (`draft_generate`)."""
    cai_dat()
    r = await client.post(
        "/api/v1/soan-thao", json={"loai_van_ban": "hdld", "facts": {}}
    )
    assert r.status_code == 401


async def test_endpoint_doc_thuan_KHONG_can_token(client, cai_dat):
    """`/health` không gọi LLM, không tốn tiền — bắt đăng nhập là một từ chối
    oan, và làm health check của hạ tầng cần một tài khoản.
    """
    cai_dat()
    assert (await client.get("/health")).status_code == 200


async def test_JWKS_khong_lay_duoc_thi_401_khong_cho_qua(
    client, cai_dat, graph_gia_lap, khong_dung_db, monkeypatch
):
    """Fail closed ở tầng HTTP: Supabase sập ⇒ từ chối, KHÔNG mở cửa."""
    cai_dat()
    khoa = ec.generate_private_key(ec.SECP256R1())
    xac_thuc._client.cache_clear()

    def no(req, timeout=None, context=None):
        raise URLError("Supabase không kết nối được")

    monkeypatch.setattr(urllib.request, "urlopen", no)
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=_bearer(khoa))
    assert r.status_code == 401
    xac_thuc._client.cache_clear()


# ══ 3. Hạn mức THÁNG theo `sub` — đọc từ config, không hardcode ═════════════


def test_han_muc_doc_tu_CONFIG_khong_hardcode(monkeypatch, tmp_path):
    """Giá và giới hạn CHƯA CHỐT. Viết cứng một con số vào Python là biến một số
    nháp của trang bảng giá thành hành vi hệ thống — sửa nó phải là sửa YAML.
    """
    f = tmp_path / "han_muc.yaml"
    f.write_text(YAML_OK, encoding="utf-8")
    monkeypatch.setattr(bao_ve, "HAN_MUC_PATH", f)
    bao_ve._doc_han_muc.cache_clear()
    assert bao_ve.han_muc("free", "hoi_dap_ngay") == 200
    assert bao_ve.han_muc("pro", "soan_thao_ngay") == 20
    bao_ve._doc_han_muc.cache_clear()


def test_goi_la_khong_roi_ve_muc_THAP_NHAT_khong_phai_vo_han(monkeypatch, tmp_path):
    """Một `users.plan` không có trong YAML (gói bị đổi tên, dữ liệu tay) phải
    rơi về gói mặc định, KHÔNG phải "không giới hạn" — hỏng theo hướng an toàn.
    """
    f = tmp_path / "han_muc.yaml"
    f.write_text(YAML_OK, encoding="utf-8")
    monkeypatch.setattr(bao_ve, "HAN_MUC_PATH", f)
    bao_ve._doc_han_muc.cache_clear()
    assert bao_ve.han_muc("goi-khong-ton-tai", "hoi_dap_ngay") == 200
    bao_ve._doc_han_muc.cache_clear()


def test_config_that_trong_repo_doc_duoc():
    """`config/han_muc.yaml` thật phải parse được và có gói mặc định."""
    bao_ve._doc_han_muc.cache_clear()
    d = bao_ve._doc_han_muc()
    assert d["goi_mac_dinh"] in d["goi"]
    assert all(isinstance(v, int) and v >= 0 for khoi in d["goi"].values() for v in khoi.values())


def test_luot_thu_N_cong_1_thi_TU_CHOI(monkeypatch):
    """Ranh giới: đúng hạn mức thì QUA, hơn một lượt thì chặn."""
    monkeypatch.setattr(bao_ve, "han_muc", lambda plan, khoa: 50)
    monkeypatch.setattr(bao_ve, "la_chan", lambda khoa: 100_000)
    monkeypatch.setattr(bao_ve, "dem_luot", lambda sub, ep, moc: 49)
    bao_ve.kiem_han_muc("s", "free", "/api/v1/tra-cuu")  # lượt thứ 50 — còn suất
    monkeypatch.setattr(bao_ve, "dem_luot", lambda sub, ep, moc: 50)
    with pytest.raises(Exception) as e:
        bao_ve.kiem_han_muc("s", "free", "/api/v1/tra-cuu")  # lượt thứ 51
    assert e.value.status_code == 429


def test_thong_diep_429_neu_ro_GOI_va_MOC_RESET(monkeypatch):
    """429 chung chung làm người dùng thử lại vô ích và người vận hành đi tìm lỗi
    mạng. Phải nói: của GÓI nào, đã dùng bao nhiêu, mở lại KHI NÀO.
    """
    monkeypatch.setattr(bao_ve, "han_muc", lambda plan, khoa: 50)
    monkeypatch.setattr(bao_ve, "dem_luot", lambda sub, ep, moc: 50)
    with pytest.raises(Exception) as e:
        bao_ve.kiem_han_muc("s", "free", "/api/v1/tra-cuu")
    d = e.value.detail
    assert e.value.status_code == 429
    # Tên NGƯỜI ĐỌC của gói, không phải mã `free`: câu này người dùng Việt Nam đọc.
    assert "Miễn phí" in d
    assert "50/50" in d
    assert "Mở lại lúc" in d
    assert int(e.value.headers["Retry-After"]) > 0


def test_tang_dem_HONG_thi_TU_CHOI_khong_mo_cua(monkeypatch):
    """Cùng nguyên tắc với trần chi phí: không đếm được thì không biết còn bao
    nhiêu suất, và cho qua là hành xử như thể hạn mức không tồn tại.
    """

    def no(sub, ep, moc):
        raise RuntimeError("Postgres chết")

    monkeypatch.setattr(bao_ve, "han_muc", lambda plan, khoa: 50)
    monkeypatch.setattr(bao_ve, "dem_luot", no)
    with pytest.raises(Exception) as e:
        bao_ve.kiem_han_muc("s", "free", "/api/v1/tra-cuu")
    assert e.value.status_code == 503


async def test_vuot_han_muc_chan_TRUOC_khi_graph_chay(client, cai_dat, khoa_ky, monkeypatch):
    """Hạn mức phải chặn trước khi tiêu token, không phải sau."""
    cai_dat()
    from src.api import routes

    goi = {"n": 0}

    class _Dem:
        async def ainvoke(self, *a, **k):
            goi["n"] += 1
            return {"result_type": ResultType.answer, "answer": "x", "citations": [], "warnings": []}

    monkeypatch.setattr(routes, "_g", lambda: _Dem())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)
    monkeypatch.setattr(bao_ve, "ghi_nhan_nguoi_dung", lambda sub, email: "free")
    monkeypatch.setattr(bao_ve, "han_muc", lambda plan, khoa: 3)
    monkeypatch.setattr(bao_ve, "dem_luot", lambda sub, ep, moc: 3)
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=_bearer(khoa_ky))
    assert r.status_code == 429
    assert goi["n"] == 0


# ══ 4. Phần đọc/ghi DB thật ═════════════════════════════════════════════════


@pytest.fixture
def don_users():
    """Xoá theo CHÍNH `sub` của test, không theo mốc thời gian: một fixture dọn
    theo thời gian sẽ xoá luôn dòng do server dev ghi trong lúc test chạy (lỗi
    đã xảy ra thật ở vòng hardening với `answer_cache`).
    """
    subs: list[str] = []
    yield subs
    if subs:
        with get_engine().begin() as c:
            c.execute(text("DELETE FROM traces WHERE user_sub = ANY(:s)"), {"s": subs})
            c.execute(text("DELETE FROM users WHERE sub = ANY(:s)"), {"s": subs})


def _ghi_traces_gia(c, sub: str, endpoint: str, cache_hit: bool, ts_offset_days: int = 0):
    c.execute(
        text(
            "INSERT INTO traces (id, endpoint, query, config_name, result_type, retrieved_ids,"
            " claims_raw, claims_after_tier1, claims_after_tier2, latency_ms, cache_hit, user_sub,"
            " ts) VALUES (:id, :ep, 'x', 'full', 'answer', '{}', 0, 0, 0, 1, :ch, :sub,"
            " now() - make_interval(days => :d))"
        ),
        {"id": str(uuid.uuid4()), "ep": endpoint, "ch": cache_hit, "sub": sub, "d": ts_offset_days},
    )


@pytest.mark.integration
def test_ghi_nhan_nguoi_dung_tao_dong_users_lan_dau(don_users):
    """JIT provisioning: dòng `users` sinh ra ở lần đăng nhập đầu, gói mặc định."""
    sub = str(uuid.uuid4())
    don_users.append(sub)
    plan = bao_ve.ghi_nhan_nguoi_dung(sub, "a@example.com")
    assert plan == bao_ve._doc_han_muc()["goi_mac_dinh"]
    with get_engine().connect() as c:
        r = c.execute(
            text("SELECT email, plan, created_at, last_seen_at FROM users WHERE sub = :s"),
            {"s": sub},
        ).one()
    assert r.email == "a@example.com"


@pytest.mark.integration
def test_ghi_nhan_lan_hai_cap_nhat_last_seen_KHONG_tao_dong_moi(don_users):
    sub = str(uuid.uuid4())
    don_users.append(sub)
    bao_ve.ghi_nhan_nguoi_dung(sub, "a@example.com")
    bao_ve.ghi_nhan_nguoi_dung(sub, "a@example.com")
    with get_engine().connect() as c:
        assert c.execute(
            text("SELECT count(*) FROM users WHERE sub = :s"), {"s": sub}
        ).scalar_one() == 1


@pytest.mark.integration
def test_dang_nhap_khong_email_KHONG_xoa_email_da_biet(don_users):
    """Đăng nhập lần sau bằng phương thức không mang `email` không được ghi NULL
    lên email đã biết — đó là mất dữ liệu liên hệ, im lặng.
    """
    sub = str(uuid.uuid4())
    don_users.append(sub)
    bao_ve.ghi_nhan_nguoi_dung(sub, "a@example.com")
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    with get_engine().connect() as c:
        assert c.execute(
            text("SELECT email FROM users WHERE sub = :s"), {"s": sub}
        ).scalar_one() == "a@example.com"


@pytest.mark.integration
def test_CACHE_HIT_khong_tinh_vao_han_muc(don_users):
    """Cache hit không gọi LLM và không tốn một xu — trừ lượt của người dùng cho
    nó là bán cho họ một thứ hệ thống không hề mua.
    """
    sub = str(uuid.uuid4())
    don_users.append(sub)
    with get_engine().begin() as c:
        _ghi_traces_gia(c, sub, "/api/v1/tra-cuu", cache_hit=False)
        _ghi_traces_gia(c, sub, "/api/v1/tra-cuu", cache_hit=True)
        _ghi_traces_gia(c, sub, "/api/v1/tra-cuu", cache_hit=True)
    assert bao_ve.dem_luot(sub, "/api/v1/tra-cuu", bao_ve.moc_ngay()) == 1


@pytest.mark.integration
def test_dem_RIENG_tung_endpoint_va_khong_dem_endpoint_khong_ton_LLM(don_users):
    """Hạn mức nay theo TỪNG endpoint (hỏi đáp và bản thảo là hai con số khác
    nhau trên trang bảng giá), nên `/soat` không chỉ bị loại — nó không nằm
    trong bất kỳ giỏ nào."""
    sub = str(uuid.uuid4())
    don_users.append(sub)
    with get_engine().begin() as c:
        _ghi_traces_gia(c, sub, "/api/v1/tra-cuu", cache_hit=False)
        _ghi_traces_gia(c, sub, "/api/v1/soan-thao", cache_hit=False)
        _ghi_traces_gia(c, sub, "/api/v1/soat", cache_hit=False)
    moc = bao_ve.moc_ngay()
    assert bao_ve.dem_luot(sub, "/api/v1/tra-cuu", moc) == 1
    assert bao_ve.dem_luot(sub, "/api/v1/soan-thao", moc) == 1
    # `/soat` không nằm trong giỏ nào: `kiem_han_muc` chỉ nhìn hai endpoint tốn LLM.
    assert "/api/v1/soat" not in bao_ve.ENDPOINT_TON_LLM


@pytest.mark.integration
def test_han_muc_dem_theo_CUA_SO_THANG_khong_phai_moi_thoi_dai(don_users):
    """Lượt của tháng trước không được trừ hạn mức tháng này."""
    sub = str(uuid.uuid4())
    don_users.append(sub)
    with get_engine().begin() as c:
        _ghi_traces_gia(c, sub, "/api/v1/tra-cuu", cache_hit=False)
        _ghi_traces_gia(c, sub, "/api/v1/tra-cuu", cache_hit=False, ts_offset_days=40)
    assert bao_ve.dem_luot(sub, "/api/v1/tra-cuu", bao_ve.moc_thang()) == 1


@pytest.mark.integration
def test_HAI_SUB_khac_nhau_dem_RIENG(don_users):
    """Đúng lỗ hổng của rate limit theo IP: hai người sau cùng một NAT."""
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    don_users.extend([a, b])
    with get_engine().begin() as c:
        for _ in range(3):
            _ghi_traces_gia(c, a, "/api/v1/tra-cuu", cache_hit=False)
        _ghi_traces_gia(c, b, "/api/v1/tra-cuu", cache_hit=False)
    moc = bao_ve.moc_ngay()
    assert bao_ve.dem_luot(a, "/api/v1/tra-cuu", moc) == 3
    assert bao_ve.dem_luot(b, "/api/v1/tra-cuu", moc) == 1


@pytest.mark.integration
async def test_hai_nguoi_dung_sau_CUNG_mot_IP_khong_lam_can_han_muc_cua_nhau(
    client, cai_dat, khoa_ky, graph_gia_lap, don_users, monkeypatch
):
    """Test end-to-end của chính lỗ hổng brief nêu: rate limit 1 lượt/60s, hai
    `sub` khác nhau, CÙNG một địa chỉ IP (test client dùng một IP duy nhất).
    Đếm theo IP thì người thứ hai bị 429; đếm theo `sub` thì cả hai đi qua.
    """
    cai_dat(rate_limit_so_luot=1, rate_limit_cua_so_giay=60)
    monkeypatch.setattr(bao_ve, "dem_luot", lambda sub, ep, moc: 0)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    don_users.extend([a, b])
    r1 = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=_bearer(khoa_ky, sub=a))
    r2 = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=_bearer(khoa_ky, sub=b))
    assert (r1.status_code, r2.status_code) == (200, 200)
    r3 = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=_bearer(khoa_ky, sub=a))
    assert r3.status_code == 429  # cùng `sub` thì VẪN bị hãm nhịp


@pytest.mark.integration
async def test_traces_ghi_user_sub_de_dem_duoc(client, cai_dat, khoa_ky, don_users, monkeypatch):
    """Không gán được request cho người dùng thì không đếm được hạn mức của họ."""
    cai_dat()
    from src.api import routes

    monkeypatch.setattr(routes, "_g", lambda: _GraphGiaLap())
    monkeypatch.setattr(bao_ve, "dem_luot", lambda sub, ep, moc: 0)
    sub = str(uuid.uuid4())
    don_users.append(sub)
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=_bearer(khoa_ky, sub=sub))
    assert r.status_code == 200
    with get_engine().connect() as c:
        assert c.execute(
            text("SELECT count(*) FROM traces WHERE user_sub = :s"), {"s": sub}
        ).scalar_one() == 1
