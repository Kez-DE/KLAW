"""Ba cổng trước ví tiền: API key, rate limit theo IP, trần chi phí ngày.

Bối cảnh đo được (không phải giả thuyết): một request `/tra-cuu` gọi LLM tối đa
5 lần, p50 10s / p95 50s, request đắt nhất đã ghi nhận $0,00735; ngày cao nhất
tới nay 118 request / $0,18329. Dự án ĐÃ gặp HTTP 429 từ OpenRouter hôm nay khi
nhiều tiến trình chạy song song. Không cổng nào trong ba cái này là phòng xa.

Test cần Postgres mang `@pytest.mark.integration` (quy ước repo — CI chạy
`-m "not integration"` KHÔNG có Postgres). Phần quyết định + thông điệp tách
khỏi phần đọc DB để test được mà không ghi một dòng nào vào `traces`: một test
chèn $999 giả vào bảng đo lường của khoá luận là làm hỏng đúng dữ liệu nó bảo vệ.
"""

import uuid

import pytest
from fastapi import HTTPException

from src.agents.nodes.assemble import ResultType
from src.config import Settings
from src.services import bao_ve

_CAU_HOI = {"query": "thử việc bao lâu"}


class _GraphGiaLap:
    """Trả `answer` cố định — cổng nào cũng phải chặn TRƯỚC khi tới đây."""

    async def ainvoke(self, *a, **k):
        return {"result_type": ResultType.answer, "answer": "x", "citations": [], "warnings": []}


@pytest.fixture
def cai_dat(monkeypatch):
    """Ghi đè settings CHỈ cho tầng cổng. `get_settings()` là `lru_cache` toàn
    tiến trình nên không thể đổi env giữa phiên — patch điểm gọi thay vì cache.

    Mặc định TẮT hai cổng đọc DB (rate limit, trần chi phí) để mỗi test bật
    ĐÚNG một cổng nó đang kiểm — không thì một test API key cũng lặng lẽ cần
    Postgres và fail ở CI (`-m "not integration"`, không có DB).
    """

    def dat(**kw):
        mac_dinh = {"rate_limit_so_luot": 0, "tran_chi_phi_ngay_usd": 0.0}
        s = Settings(_env_file=None, **{**mac_dinh, **kw})
        monkeypatch.setattr(bao_ve, "get_settings", lambda: s)
        return s

    return dat


@pytest.fixture
def graph_gia_lap(monkeypatch):
    from src.api import routes

    monkeypatch.setattr(routes, "_g", lambda: _GraphGiaLap())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)


# ══ API key — tuỳ chọn, nhưng BẮT BUỘC khi đã cấu hình ══════════════════════


async def test_khong_dat_KLAW_API_KEY_thi_mo_cho_dev(client, cai_dat, graph_gia_lap):
    cai_dat(api_key="")
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI)
    assert r.status_code == 200


async def test_dat_KLAW_API_KEY_ma_thieu_header_thi_401(client, cai_dat, graph_gia_lap):
    cai_dat(api_key="khoa-that")
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI)
    assert r.status_code == 401


async def test_dat_KLAW_API_KEY_ma_sai_header_thi_401(client, cai_dat, graph_gia_lap):
    cai_dat(api_key="khoa-that")
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers={"X-API-Key": "khoa-sai"})
    assert r.status_code == 401


async def test_dat_KLAW_API_KEY_va_dung_header_thi_qua(client, cai_dat, graph_gia_lap):
    cai_dat(api_key="khoa-that")
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers={"X-API-Key": "khoa-that"})
    assert r.status_code == 200


async def test_401_khong_lo_gia_tri_khoa(client, cai_dat, graph_gia_lap):
    """Thông điệp lỗi KHÔNG được mang khoá thật (dù chỉ một phần) — phản hồi của
    một endpoint không xác thực là bề mặt rò rỉ."""
    cai_dat(api_key="khoa-that-sk-bi-mat")
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers={"X-API-Key": "sai"})
    assert r.status_code == 401
    assert "khoa-that" not in r.text and "bi-mat" not in r.text


async def test_soan_thao_cung_bi_cong_api_key(client, cai_dat):
    """`/soan-thao` cũng tốn một lượt LLM — cùng cổng, không phải chỉ /tra-cuu."""
    cai_dat(api_key="khoa-that")
    r = await client.post(
        "/api/v1/soan-thao", json={"loai_van_ban": "hdld", "facts": {}}
    )
    assert r.status_code == 401


async def test_endpoint_doc_thuan_KHONG_can_key(client, cai_dat):
    """`/health` không tốn LLM — bắt key ở đó chỉ làm healthcheck của Docker
    hỏng mà không bảo vệ đồng nào."""
    cai_dat(api_key="khoa-that")
    assert (await client.get("/health")).status_code == 200


# ══ IP thật — X-Forwarded-For chỉ được tin khi CẤU HÌNH nói có proxy ════════


def _request_gia_lap(client_ip: str, headers: dict):
    from starlette.requests import Request

    return Request(
        {
            "type": "http",
            "client": (client_ip, 1234),
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        }
    )


def test_X_Forwarded_For_KHONG_duoc_tin_khi_khong_co_proxy(cai_dat):
    """Mặc định KHÔNG tin: nếu tin, bất kỳ ai cũng gửi `X-Forwarded-For: <ip
    ngẫu nhiên>` mỗi request và rate limit theo IP trở thành trang trí."""
    cai_dat(tin_proxy_header=False)
    ip = bao_ve.ip_goi(_request_gia_lap("203.0.113.9", {"X-Forwarded-For": "1.2.3.4"}))
    assert ip == "203.0.113.9"


def test_X_Forwarded_For_duoc_tin_khi_cau_hinh_noi_co_proxy(cai_dat):
    """Lấy từ PHẢI sang: proxy nối thêm vào cuối, nên phần tử cuối là phần do
    proxy tin cậy ghi. Phần tử ĐẦU do kẻ gọi tự viết — tin nó là đưa cho kẻ gọi
    quyền tự chọn giỏ đếm rate limit của mình.

    Chi tiết đầy đủ (nhiều hop, header ngắn hơn khai báo, và tầng
    `ProxyHeadersMiddleware` của uvicorn ở dưới) ở
    `tests/test_infra/test_uvicorn_proxy_headers.py`.
    """
    cai_dat(tin_proxy_header=True, so_hop_proxy_tin_cay=1)
    ip = bao_ve.ip_goi(_request_gia_lap("10.0.0.1", {"X-Forwarded-For": "1.2.3.4, 203.0.113.9"}))
    assert ip == "203.0.113.9"


def test_khong_co_client_thi_KHONG_gop_moi_nguoi_vao_mot_gio(cai_dat):
    """`scope["client"]` vắng mặt (một số ASGI server/transport) — trả một nhãn
    RIÊNG, không phải chuỗi rỗng gộp chung: gộp lại thì một người dùng làm cạn
    hạn mức của tất cả những người khác."""
    cai_dat(tin_proxy_header=False)
    from starlette.requests import Request

    ip = bao_ve.ip_goi(Request({"type": "http", "client": None, "headers": []}))
    assert ip == bao_ve.IP_KHONG_XAC_DINH


# ══ Trần chi phí ngày — quyết định + thông điệp (KHÔNG ghi traces) ══════════


def test_vuot_tran_thi_429_va_thong_diep_neu_DUNG_ly_do(cai_dat, monkeypatch):
    """429 chung chung ("thử lại sau") làm người dùng và người vận hành đều đoán
    sai nguyên nhân. Thông điệp phải nói rõ đây là TRẦN CHI PHÍ NGÀY và khi nào
    mở lại."""
    cai_dat(tran_chi_phi_ngay_usd=2.0)
    monkeypatch.setattr(bao_ve, "chi_phi_hom_nay", lambda: 2.5)

    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_tran_chi_phi()
    assert e.value.status_code == 429
    assert "trần chi phí ngày" in e.value.detail.lower()
    assert "2.0" in e.value.detail or "2,0" in e.value.detail
    assert e.value.headers and "Retry-After" in e.value.headers


def test_duoi_tran_thi_qua(cai_dat, monkeypatch):
    cai_dat(tran_chi_phi_ngay_usd=2.0)
    monkeypatch.setattr(bao_ve, "chi_phi_hom_nay", lambda: 1.99)
    bao_ve.kiem_tran_chi_phi()  # không raise


def test_tran_bang_0_la_TAT_han_khong_phai_chan_het(cai_dat, monkeypatch):
    """0 = TẮT (cần cho eval sweep chạy hàng trăm request qua HTTP). Một trần
    $0 "chặn mọi thứ" sẽ vô dụng ở production, nên 0 không mơ hồ."""
    cai_dat(tran_chi_phi_ngay_usd=0.0)

    def khong_duoc_goi():
        raise AssertionError("trần đã TẮT mà vẫn truy vấn DB")

    monkeypatch.setattr(bao_ve, "chi_phi_hom_nay", khong_duoc_goi)
    bao_ve.kiem_tran_chi_phi()


def test_tang_dem_HONG_thi_TU_CHOI_khong_mo_cua(cai_dat, monkeypatch):
    """Cổng cuối trước ví tiền: nếu không đếm được chi phí hôm nay thì không
    biết còn bao nhiêu tiền — cho qua là mở cửa như thể trần không tồn tại."""
    cai_dat(tran_chi_phi_ngay_usd=2.0)

    def no(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(bao_ve, "chi_phi_hom_nay", no)
    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_tran_chi_phi()
    assert e.value.status_code == 503


async def test_vuot_tran_chan_TRUOC_khi_graph_chay(client, cai_dat, monkeypatch):
    """Cổng phải chặn trước khi tốn token, không phải sau."""
    cai_dat(tran_chi_phi_ngay_usd=2.0)
    monkeypatch.setattr(bao_ve, "chi_phi_hom_nay", lambda: 99.0)

    from src.api import routes

    class GraphBom:
        async def ainvoke(self, *a, **k):
            raise AssertionError("graph đã chạy dù trần chi phí đã vượt")

    monkeypatch.setattr(routes, "_g", lambda: GraphBom())
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI)
    assert r.status_code == 429
    assert "trần chi phí ngày" in r.text.lower()


# ══ Rate limit — bộ đếm trong Postgres (KHÔNG in-process) ═══════════════════


def test_rate_limit_bang_0_la_TAT(cai_dat):
    cai_dat(rate_limit_so_luot=0)
    for _ in range(50):
        bao_ve.kiem_rate_limit("1.2.3.4")  # không raise, không chạm DB


@pytest.mark.integration
def test_vuot_rate_limit_thi_429(cai_dat):
    """Bộ đếm nằm trong Postgres, KHÔNG in-process: in-process chỉ đúng khi có
    MỘT worker, và một rate limit đúng-cho-đến-khi-scale là một rate limit sai.
    """
    cai_dat(rate_limit_so_luot=3, rate_limit_cua_so_giay=60)
    ip = f"test-{uuid.uuid4()}"

    for _ in range(3):
        bao_ve.kiem_rate_limit(ip)

    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_rate_limit(ip)
    assert e.value.status_code == 429
    assert "lượt" in e.value.detail.lower()
    assert e.value.headers and "Retry-After" in e.value.headers


@pytest.mark.integration
def test_rate_limit_dem_RIENG_tung_IP(cai_dat):
    """Một IP cạn hạn mức không được làm cạn hạn mức của IP khác."""
    cai_dat(rate_limit_so_luot=2, rate_limit_cua_so_giay=60)
    a, b = f"test-{uuid.uuid4()}", f"test-{uuid.uuid4()}"

    bao_ve.kiem_rate_limit(a)
    bao_ve.kiem_rate_limit(a)
    with pytest.raises(HTTPException):
        bao_ve.kiem_rate_limit(a)

    bao_ve.kiem_rate_limit(b)  # IP khác vẫn còn hạn mức


@pytest.mark.integration
async def test_vuot_rate_limit_chan_TRUOC_khi_graph_chay(client, cai_dat, monkeypatch):
    """Cổng chặn ở tầng HTTP, không chỉ ở hàm.

    Dùng một IP DUY NHẤT qua `X-Forwarded-For` (nên `tin_proxy_header=True`)
    thay vì để test dùng `127.0.0.1` của ASGI transport: bộ đếm nằm trong
    Postgres — đúng như thiết kế yêu cầu — và DB đó DÙNG CHUNG với server dev
    đang chạy (`uvicorn --reload`) cùng mọi worktree khác. Bản trước của test
    này đỏ vì đúng lý do đó: một request thật của server dev đã chiếm một suất
    trong giỏ `127.0.0.1` giữa lúc test chạy. Giỏ riêng cho mỗi lần chạy vừa
    khử được nguồn nhiễu đó, vừa đi qua luôn nhánh proxy tin cậy.
    """
    cai_dat(rate_limit_so_luot=1, rate_limit_cua_so_giay=60, tin_proxy_header=True)
    from src.api import routes

    monkeypatch.setattr(routes, "_g", lambda: _GraphGiaLap())
    monkeypatch.setattr(routes, "_ghi_traces", lambda *a, **k: None)
    h = {"X-Forwarded-For": f"test-{uuid.uuid4()}"}

    assert (await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=h)).status_code == 200
    r = await client.post("/api/v1/tra-cuu", json=_CAU_HOI, headers=h)
    assert r.status_code == 429
    assert r.headers.get("Retry-After") == "60"


@pytest.mark.integration
def test_chi_phi_hom_nay_doc_duoc_tu_bang_traces_that(cai_dat):
    """`traces` ĐÃ ghi chi phí thật từng request — không dựng bộ đếm thứ hai.
    Chỉ ĐỌC ở đây (không ghi): dữ liệu này là bảng đo của khoá luận."""
    cai_dat()
    gia_tri = bao_ve.chi_phi_hom_nay()
    assert isinstance(gia_tri, float)
    assert gia_tri >= 0.0
