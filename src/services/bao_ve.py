"""Các cổng trước ví tiền, chạy TRƯỚC khi một token nào bị tiêu.

Bối cảnh ĐO ĐƯỢC trên chính DB của dự án (không phải giả thuyết):
  * `/tra-cuu` gọi LLM tối đa 5 lần; p50 10.000ms, p95 50.289ms (204 dòng traces)
  * request đắt nhất đã ghi nhận: $0,00735
  * ngày cao nhất tới nay: 118 request / $0,18329 (2026-08-30)
  * dự án ĐÃ gặp HTTP 429 từ OpenRouter khi nhiều tiến trình chạy song song
Mở 8 endpoint ra công khai nguyên trạng thì một người với một vòng `curl` rút
cạn key trong một buổi.

Các cổng CHỒNG nhau chứ không thay nhau:
  1. **API key** (0 truy vấn) — chặn người không được phép, nếu đã cấu hình.
  2. **Danh tính** (`xac_thuc`, JWT Supabase) — CHỈ khi đã cấu hình Supabase.
  3. **Rate limit** (Postgres) — hãm NHỊP. Khoá đếm là `sub` khi đã đăng nhập,
     IP khi chưa: hai người sau cùng một NAT dùng chung một giỏ IP, nên người
     thứ hai bị hãm vì lưu lượng của người thứ nhất.
  4. **Hạn mức tháng theo NGƯỜI DÙNG** (Postgres, đọc `traces`) — hãm TỔNG. Chỉ
     khi đã đăng nhập; đây là thứ cưỡng chế được con số trên trang bảng giá.
  5. **Trần chi phí ngày** (Postgres, đọc `traces`) — cổng CUỐI trước ví tiền,
     toàn hệ thống, không phân biệt người dùng.

Nhịp và tổng là HAI đại lượng khác nhau, nên (3) không bị bỏ khi (4) bật: hạn
mức tháng không ngăn được một chùm 50 request song song trong ba giây.

Nguyên tắc chung: **hỏng ở tầng đếm là TỪ CHỐI, không phải mở cửa.** Nếu không
đếm được thì không biết còn bao nhiêu tiền (hay còn bao nhiêu suất), và cho qua
là hành xử như thể cổng đó không tồn tại.

Bộ đếm nằm trong Postgres, KHÔNG in-process: in-process chỉ đúng khi có MỘT
worker (`Dockerfile` hiện đúng vậy, nhưng đó là trạng thái tạm), và một rate
limit đúng-cho-đến-khi-scale là một rate limit sai.
"""

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from fastapi import HTTPException, Request
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from src.config import get_settings
from src.services import xac_thuc
from src.services.db import get_engine

logger = logging.getLogger(__name__)

TEN_HEADER_KEY = "X-API-Key"

# Hạn mức là DỮ LIỆU, không phải code — cùng khuôn `config/rules.yaml`. Xem
# chính file đó cho lý do (giá và giới hạn CHƯA CHỐT).
HAN_MUC_PATH = Path("config/han_muc.yaml")

# Hai endpoint TIÊU TIỀN. Liệt kê TƯỜNG MINH thay vì đếm mọi dòng traces: `/soat`
# cũng ghi traces nhưng không gọi LLM một lần nào, và trừ lượt của người dùng cho
# nó là bán cho họ một thứ hệ thống không hề mua. Thêm một endpoint gọi LLM →
# thêm vào đây (cùng kỷ luật với ba danh sách khoá chi phí trong `traces.py`).
ENDPOINT_TON_LLM = ("/api/v1/tra-cuu", "/api/v1/soan-thao")

# Nhãn RIÊNG khi ASGI scope không mang `client`. Không dùng chuỗi rỗng: rỗng gộp
# mọi request không xác định được IP vào MỘT giỏ, và một người dùng làm cạn hạn
# mức của tất cả những người khác trong giỏ đó.
IP_KHONG_XAC_DINH = "khong-xac-dinh"

_SQL_CHI_PHI_HOM_NAY = text(
    "SELECT COALESCE(SUM(cost_usd), 0) FROM traces WHERE ts >= :bat_dau"
)
# `pg_advisory_xact_lock` khoá theo IP trong phạm vi transaction, tự nhả khi
# commit/rollback. Không có nó, một chùm request song song cùng IP đều đọc số
# đếm TRƯỚC chùm (READ COMMITTED không thấy INSERT chưa commit của nhau) và
# đều đi qua — tức rate limit thất bại đúng lúc nó cần hoạt động nhất.
# `hashtext` cho bigint từ TEXT; va chạm hash chỉ khiến hai IP chờ nhau một
# chút, không gây kết quả sai.
_SQL_KHOA_IP = text("SELECT pg_advisory_xact_lock(hashtext(:ip))")
_SQL_DON_LUOT = text("DELETE FROM rate_limit_luot WHERE ts < now() - make_interval(secs => :cua_so)")
_SQL_GHI_LUOT = text("INSERT INTO rate_limit_luot (ip) VALUES (:ip)")
_SQL_DEM_LUOT = text(
    "SELECT count(*) FROM rate_limit_luot"
    " WHERE ip = :ip AND ts >= now() - make_interval(secs => :cua_so)"
)

# JIT provisioning: dòng `users` sinh ra ở lần đăng nhập ĐẦU, không cần một
# webhook từ Supabase (một đường đồng bộ nữa là một đường nữa để lệch pha).
# MỘT câu lệnh làm cả ba việc — tạo nếu chưa có, cập nhật `last_seen_at`, và
# TRẢ VỀ `plan` — thay vì SELECT rồi INSERT: hai câu thì hai request song song
# của cùng người dùng mới đều thấy "chưa có" và đều INSERT, một cái nổ.
#
# `COALESCE(EXCLUDED.email, users.email)` chứ không `EXCLUDED.email`: đăng nhập
# lần sau bằng phương thức không mang email (số điện thoại) sẽ ghi NULL lên
# email đã biết — mất dữ liệu liên hệ, im lặng.
_SQL_UPSERT_USER = text(
    "INSERT INTO users (sub, email) VALUES (:sub, :email)"
    " ON CONFLICT (sub) DO UPDATE SET last_seen_at = now(),"
    " email = COALESCE(EXCLUDED.email, users.email)"
    " RETURNING plan, plan_het_han"
)

# Đếm SỐ LƯỢT gọi LLM thật của một `sub` trong tháng.
#
# `NOT cache_hit` — cache hit không gọi LLM và không tốn một xu (đo được ở vòng
# hardening: $0 và 3ms, so với ~$0,0004 và ~6,9s một lượt thật).
#
# Đếm `count(*)`, KHÔNG `cost_usd > 0`: chi phí là một đại lượng ĐO ĐƯỢC và có
# thể bằng 0 vì một lỗi ghi nhận — đã xảy ra thật, 32/32 dòng `/soan-thao` từng
# ghi $0 dù mỗi request tốn một lượt LLM. "Đã gọi hay chưa" không phụ thuộc việc
# cột chi phí có được cộng đúng, nên hạn mức của người dùng cũng không được.
_SQL_DEM_LUOT_THANG = text(
    "SELECT count(*) FROM traces"
    " WHERE user_sub = :sub AND ts >= :bat_dau"
    " AND NOT cache_hit AND endpoint = ANY(:endpoints)"
)


# ── IP thật ─────────────────────────────────────────────────────────────────


def ip_goi(request: Request) -> str:
    """IP để đếm rate limit.

    `X-Forwarded-For` CHỈ được tin khi `KLAW_TIN_PROXY_HEADER=true`. Mặc định
    KHÔNG tin, vì nếu tin mà thực tế không có reverse proxy đặt header đó thì
    bất kỳ ai cũng gửi một IP giả khác nhau mỗi request và rate limit theo IP
    trở thành trang trí.

    Khi tin thì lấy từ PHẢI sang, KHÔNG phải phần tử đầu. Mỗi proxy NỐI THÊM
    địa chỉ nó thấy vào cuối, nên phần tử đầu là phần kẻ gọi tự viết — lấy nó
    là tin đúng thứ duy nhất trong header mà không ai trong chuỗi tin cậy đã
    ghi. Với `so_hop_proxy_tin_cay = N`, client thật ở vị trí thứ N từ phải:
    hop cuối do proxy sát ứng dụng ghi, và cứ lùi một hop là lùi một proxy.

    Header NGẮN hơn N phần tử ⇒ chuỗi proxy không như cấu hình mô tả; rơi về
    địa chỉ peer thay vì đoán, cùng hướng hỏng-thì-CHẶN với cả module này.

    Lưu ý tầng dưới: uvicorn mặc định `proxy_headers=True` và tự thay
    `scope["client"]` bằng chính header này TRƯỚC khi hàm này chạy, nên chính
    sách ở đây chỉ có hiệu lực khi tiến trình chạy kèm `--no-proxy-headers`
    (xem `Dockerfile` và `tests/test_infra/test_uvicorn_proxy_headers.py`).
    """
    if get_settings().tin_proxy_header:
        phan = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",")]
        phan = [p for p in phan if p]
        n = get_settings().so_hop_proxy_tin_cay
        if len(phan) >= n:
            return phan[-n]
    return request.client.host if request.client else IP_KHONG_XAC_DINH


# ── Cổng 1: API key ─────────────────────────────────────────────────────────


def kiem_api_key(request: Request) -> None:
    """Bắt buộc header `X-API-Key` khớp, NẾU `KLAW_API_KEY` được cấu hình.

    Rỗng = mở (dev local). CỐ Ý chưa phải user/session: ai là người dùng, đăng
    ký thế nào, phân quyền ra sao là quyết định SẢN PHẨM chưa chốt — nhưng
    deploy mà mở toang thì không được, nên đây là cổng tối thiểu đóng được
    ngay mà không cần chốt trước những câu hỏi đó.

    `secrets.compare_digest` chứ không `==`: `==` thoát sớm ở byte đầu lệch,
    nên thời gian so sánh rò rỉ độ dài tiền tố đúng. Encode sang bytes trước
    khi so — `compare_digest` trên `str` NỔ TypeError với ký tự ngoài ASCII, và
    một header do người ngoài gửi hoàn toàn có thể chứa ký tự đó (biến một cổng
    xác thực thành 500).
    """
    khoa_that = get_settings().api_key
    if not khoa_that:
        return
    khoa_gui = request.headers.get(TEN_HEADER_KEY.lower(), "")
    if not secrets.compare_digest(khoa_gui.encode("utf-8"), khoa_that.encode("utf-8")):
        # Thông điệp KHÔNG mang khoá thật, kể cả một phần: phản hồi của một
        # endpoint chưa xác thực là bề mặt rò rỉ. Cũng KHÔNG phân biệt
        # "thiếu header" với "sai khoá" — phân biệt là nói cho người thăm dò
        # biết họ đã đi được nửa đường.
        raise HTTPException(
            status_code=401,
            detail=f"Thiếu hoặc sai header {TEN_HEADER_KEY}.",
            headers={"WWW-Authenticate": TEN_HEADER_KEY},
        )


# ── Cổng 2: rate limit theo IP ──────────────────────────────────────────────


def kiem_rate_limit(ip: str, so_luot: int | None = None) -> None:
    """Cửa sổ TRƯỢT trong Postgres. Vượt → 429.

    `so_luot` None = dùng `rate_limit_so_luot` (hạn mức NHỊP của một người).
    Truyền tường minh cho giỏ có mục đích khác — lá chắn trước xác thực dùng
    `rate_limit_ip_so_luot`, rộng hơn nhiều; xem `cong_bao_ve`.

    Cửa sổ trượt, không phải cửa sổ cố định theo phút: cửa sổ cố định cho phép
    gấp đôi hạn mức quanh mốc chuyển phút (10 lượt cuối phút này + 10 lượt đầu
    phút sau).

    Đếm SAU khi ghi lượt của chính request này, nên `> hạn mức` từ chối đúng
    request thứ (hạn mức + 1). Lỗi DB ở đây là TỪ CHỐI (503), không phải mở cửa.
    """
    s = get_settings()
    if s.rate_limit_so_luot <= 0:  # 0 = TẮT cả tầng nhịp (eval sweep qua HTTP)
        return
    if so_luot is None:
        so_luot = s.rate_limit_so_luot
    if so_luot <= 0:
        return
    cua_so = s.rate_limit_cua_so_giay
    try:
        with get_engine().begin() as c:
            c.execute(_SQL_KHOA_IP, {"ip": ip})
            c.execute(_SQL_DON_LUOT, {"cua_so": cua_so})
            c.execute(_SQL_GHI_LUOT, {"ip": ip})
            da_dung = c.execute(_SQL_DEM_LUOT, {"ip": ip, "cua_so": cua_so}).scalar_one()
    except Exception as e:
        logger.exception("kiem_rate_limit: không đếm được lượt gọi (ip=%s) — TỪ CHỐI", ip)
        raise HTTPException(
            status_code=503,
            detail="Không kiểm được giới hạn tần suất, tạm thời từ chối yêu cầu. Vui lòng thử lại.",
        ) from e

    if da_dung > so_luot:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Vượt giới hạn tần suất: tối đa {so_luot} lượt "
                f"trong {cua_so} giây cho mỗi địa chỉ IP. Vui lòng thử lại sau {cua_so} giây."
            ),
            headers={"Retry-After": str(cua_so)},
        )


# ── Cổng 3: trần chi phí ngày ───────────────────────────────────────────────


def _dau_ngay_utc() -> datetime:
    """Nửa đêm UTC của hôm nay.

    UTC tường minh, KHÔNG `date_trunc('day', now())`: hàm đó dùng TimeZone của
    session Postgres, nên cùng một dòng code cho hai mốc reset khác nhau trên
    hai deployment cấu hình khác nhau — một trần chi phí không được phụ thuộc
    một biến môi trường không ai nhớ là mình đã đặt. Container hiện chạy
    `Etc/UTC` nên hôm nay hai cách trùng nhau; sự trùng đó là ngẫu nhiên.
    """
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def chi_phi_hom_nay() -> float:
    """Tổng `traces.cost_usd` từ nửa đêm UTC. CÓ THỂ RAISE (caller từ chối).

    Đọc từ `traces` — bảng đã ghi chi phí THẬT từng request — thay vì dựng một
    bộ đếm thứ hai: hai bộ đếm sẽ lệch nhau và không cách nào biết bên nào
    đúng. Chỉ ĐỌC, không ghi: bảng này là dữ liệu đo lường của khoá luận.
    """
    with get_engine().connect() as c:
        return float(c.execute(_SQL_CHI_PHI_HOM_NAY, {"bat_dau": _dau_ngay_utc()}).scalar_one())


def kiem_tran_chi_phi() -> None:
    """Vượt trần → 429 kèm lý do CỤ THỂ. Không đếm được → 503.

    429 chung chung ("thử lại sau") làm cả người dùng và người vận hành đoán sai
    nguyên nhân: người dùng thử lại vô ích cả ngày, người vận hành đi tìm lỗi
    mạng. Thông điệp nói rõ đây là trần chi phí NGÀY và mốc mở lại.
    """
    s = get_settings()
    if s.tran_chi_phi_ngay_usd <= 0:  # 0 = TẮT (đặt tay, không phải mặc định)
        return
    try:
        da_dung = chi_phi_hom_nay()
    except Exception as e:
        # Cổng CUỐI trước ví tiền: không biết đã tiêu bao nhiêu thì không được
        # cho tiêu thêm. Đây là chỗ duy nhất trong repo mà một lỗi DB ở tầng
        # quan sát KHÔNG được best-effort — vì ở đây nó không phải quan sát.
        logger.exception("kiem_tran_chi_phi: không đọc được chi phí hôm nay — TỪ CHỐI")
        raise HTTPException(
            status_code=503,
            detail="Không kiểm được trần chi phí ngày, tạm thời từ chối yêu cầu. Vui lòng thử lại.",
        ) from e

    if da_dung >= s.tran_chi_phi_ngay_usd:
        mo_lai = _dau_ngay_utc() + timedelta(days=1)
        raise HTTPException(
            status_code=429,
            detail=(
                f"Đã đạt trần chi phí ngày ({s.tran_chi_phi_ngay_usd} USD; "
                f"đã dùng {da_dung:.5f} USD). Hạn mức mở lại lúc "
                f"{mo_lai.strftime('%Y-%m-%d %H:%M')} UTC."
            ),
            headers={"Retry-After": str(int((mo_lai - datetime.now(UTC)).total_seconds()))},
        )


# ── Cổng 4: danh tính + hạn mức THÁNG theo NGƯỜI DÙNG ───────────────────────


KHOA_GOI = ("hoi_dap_ngay", "soan_thao_ngay", "soan_thao_thang", "luot_moi_phien")
KHOA_LA_CHAN = ("free_hoi_dap_thang", "pro_hoi_dap_ngay", "ip_ngay")
KHOA_KHACH = ("hoi_dap_24h", "ip_24h")
KHACH_HEADER = "x-khach-id"


@lru_cache
def _doc_han_muc() -> dict:
    """Đọc `config/han_muc.yaml` (hình v3). Fail loud — một hạn mức không đọc được
    KHÔNG được lặng lẽ thành một mặc định trong Python."""
    d = yaml.safe_load(HAN_MUC_PATH.read_text(encoding="utf-8"))
    if not isinstance(d, dict) or not isinstance(d.get("goi"), dict) or not d["goi"]:
        raise ValueError(f"{HAN_MUC_PATH}: cần khoá 'goi' kiểu mapping (không rỗng) ở gốc file")
    if d.get("goi_mac_dinh") not in d["goi"]:
        raise ValueError(f"{HAN_MUC_PATH}: 'goi_mac_dinh' phải là một khoá trong 'goi'")
    if "phien_luu" in d:
        raise ValueError(f"{HAN_MUC_PATH}: khoá 'phien_luu' không còn dùng (cơ chế ẩn phiên đã gỡ)")
    try:
        ZoneInfo(str(d.get("mui_gio")))
    except (ZoneInfoNotFoundError, TypeError, ValueError) as e:
        raise ValueError(f"{HAN_MUC_PATH}: 'mui_gio' không phải tên vùng hợp lệ") from e
    for ten, khoi in d["goi"].items():
        thieu = [k for k in KHOA_GOI if not isinstance(khoi, dict) or k not in khoi]
        if thieu:
            raise ValueError(f"{HAN_MUC_PATH}: gói '{ten}' thiếu khoá {thieu}")
    for nhom, khoa in (("la_chan", KHOA_LA_CHAN), ("khach", KHOA_KHACH)):
        khoi = d.get(nhom)
        thieu = [k for k in khoa if not isinstance(khoi, dict) or k not in khoi]
        if thieu:
            raise ValueError(f"{HAN_MUC_PATH}: '{nhom}' thiếu khoá {thieu}")
    if not isinstance(d.get("chu_ky_pro_ngay"), int) or d["chu_ky_pro_ngay"] <= 0:
        raise ValueError(f"{HAN_MUC_PATH}: cần 'chu_ky_pro_ngay' là số nguyên dương")
    return d


def han_muc(plan: str, khoa: str) -> int:
    """Trần `khoa` của `plan`. Gói lạ → gói mặc định (hỏng theo hướng CHẶT); khoá lạ → KeyError."""
    d = _doc_han_muc()
    if khoa not in KHOA_GOI:
        raise KeyError(khoa)
    if plan not in d["goi"]:
        logger.warning("han_muc: gói %r không có trong YAML — dùng gói mặc định", plan)
        plan = d["goi_mac_dinh"]
    return int(d["goi"][plan][khoa])


def la_chan(khoa: str) -> int:
    return int(_doc_han_muc()["la_chan"][khoa])


def mui_gio() -> ZoneInfo:
    return ZoneInfo(str(_doc_han_muc()["mui_gio"]))


def moc_ngay(now: datetime | None = None) -> datetime:
    t = (now or datetime.now(UTC)).astimezone(mui_gio())
    return t.replace(hour=0, minute=0, second=0, microsecond=0)


def moc_ngay_sau(now: datetime | None = None) -> datetime:
    return moc_ngay(now) + timedelta(days=1)


def moc_thang(now: datetime | None = None) -> datetime:
    return moc_ngay(now).replace(day=1)


def moc_thang_sau(now: datetime | None = None) -> datetime:
    d = moc_thang(now)
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def plan_hieu_luc_tu(plan: str, het_han: datetime | None) -> str:
    """Gói HIỆU LỰC: `plan` khi chưa hết hạn, ngược lại gói mặc định. NULL = không hết hạn."""
    if het_han is not None and het_han <= datetime.now(UTC):
        return str(_doc_han_muc()["goi_mac_dinh"])
    return plan


_SQL_PLAN_HIEU_LUC = text("SELECT plan, plan_het_han FROM users WHERE sub = :sub")


def plan_hieu_luc(sub: str) -> str:
    """Gói hiệu lực của `sub`; chưa có dòng `users` → gói mặc định (đọc không được tạo)."""
    with get_engine().connect() as c:
        r = c.execute(_SQL_PLAN_HIEU_LUC, {"sub": sub}).mappings().one_or_none()
    if r is None:
        return str(_doc_han_muc()["goi_mac_dinh"])
    return plan_hieu_luc_tu(str(r["plan"]), r["plan_het_han"])


def khach_id_tu_request(request: Request) -> str | None:
    """`X-Khach-Id` hợp lệ (UUID) hoặc None. Không phải danh tính — chỉ là khoá đếm."""
    tho = request.headers.get(KHACH_HEADER)
    if tho is None:
        return None
    try:
        return str(uuid.UUID(tho))
    except ValueError:
        return None


def han_muc_thang(plan: str) -> int:
    """Tương thích tạm cho Task 2–3: lá chắn tháng của free; "không giới hạn" của pro."""
    return la_chan("free_hoi_dap_thang") if plan == "free" else 100_000


def _dau_thang_utc() -> datetime:
    """Nửa đêm ngày 1 tháng này, UTC tường minh — cùng lý lẽ `_dau_ngay_utc`."""
    return datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _dau_thang_sau_utc() -> datetime:
    """Mốc hạn mức mở lại. `day=28 + 4 ngày` rồi ép về ngày 1: đúng cho cả tháng
    28/29/30/31 ngày mà không cần `calendar.monthrange`.
    """
    d = _dau_thang_utc()
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def ghi_nhan_nguoi_dung(sub: str, email: str | None) -> str:
    """Upsert dòng `users` và trả gói HIỆU LỰC (đã xét `plan_het_han`). CÓ THỂ RAISE.

    Chỉ ghi `sub`/`email`/`last_seen_at` — xem `migrations/012` cho lý do từng
    cột và lý do KHÔNG có `ho_ten`/`avatar_url`/`provider`.
    """
    with get_engine().begin() as c:
        r = c.execute(_SQL_UPSERT_USER, {"sub": sub, "email": email}).mappings().one()
    return plan_hieu_luc_tu(str(r["plan"]), r["plan_het_han"])


def dem_luot_thang(sub: str) -> int:
    """Số lượt LLM thật của `sub` trong tháng này. CÓ THỂ RAISE (caller từ chối)."""
    with get_engine().connect() as c:
        return int(
            c.execute(
                _SQL_DEM_LUOT_THANG,
                {
                    "sub": sub,
                    "bat_dau": _dau_thang_utc(),
                    "endpoints": list(ENDPOINT_TON_LLM),
                },
            ).scalar_one()
        )


def kiem_han_muc_thang(sub: str, plan: str) -> None:
    """Vượt hạn mức tháng → 429 nêu đúng GÓI và MỐC RESET. Không đếm được → 503.

    Cùng nguyên tắc với trần chi phí: không đếm được thì không biết còn bao nhiêu
    suất, và cho qua là hành xử như thể hạn mức không tồn tại.
    """
    han_muc = han_muc_thang(plan)
    try:
        da_dung = dem_luot_thang(sub)
    except Exception as e:
        logger.exception("kiem_han_muc_thang: không đếm được lượt trong tháng — TỪ CHỐI")
        raise HTTPException(
            status_code=503,
            detail="Không kiểm được hạn mức của tài khoản, tạm thời từ chối yêu cầu. Vui lòng thử lại.",
        ) from e

    if da_dung >= han_muc:
        mo_lai = _dau_thang_sau_utc()
        raise HTTPException(
            status_code=429,
            detail=(
                f"Đã dùng hết hạn mức tháng của gói {plan}: {da_dung}/{han_muc} lượt hỏi AI. "
                f"Hạn mức đặt lại vào {mo_lai.strftime('%d/%m/%Y')} (00:00 UTC). "
                "Lượt trả lời lấy từ bộ đệm không tính vào hạn mức."
            ),
            headers={"Retry-After": str(int((mo_lai - datetime.now(UTC)).total_seconds()))},
        )


def xac_thuc_nguoi_goi(request: Request) -> dict | None:
    """Trả `{"sub", "email"}` của người gọi, hoặc None khi auth CHƯA cấu hình.

    Trả cả `email` chứ không chỉ `sub`: `email` là cột LIÊN HỆ của `users` và
    nguồn duy nhất của nó là token này. Bỏ nó ở đây thì cột kia vĩnh viễn NULL.

    Chưa cấu hình Supabase ⇒ None và không một truy vấn nào: hệ thống hoạt động
    đúng như trước, và `eval/run.py` không cần tài khoản nào.

    401 nói MỘT câu duy nhất cho mọi nguyên nhân. Client không được biết token
    của họ sai ở `aud`, ở `iss`, ở chữ ký, hay đã hết hạn — mỗi sự phân biệt là
    một mũi chỉ đường cho người đang thăm dò. Lý do thật nằm trong log.
    """
    if not xac_thuc.da_cau_hinh():
        return None
    token = xac_thuc.token_tu_header(request.headers.get(xac_thuc.TEN_HEADER.lower()))
    if token is None:
        raise HTTPException(
            status_code=401,
            detail="Cần đăng nhập để dùng tính năng này.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return xac_thuc.xac_minh(token)
    except xac_thuc.XacMinhError as e:
        raise HTTPException(
            status_code=401,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# ── Dependency cho endpoint tốn CPU nhưng KHÔNG gọi LLM ─────────────────────


async def cong_nhe(request: Request) -> None:
    """API key + nhịp. KHÔNG danh tính, KHÔNG hạn mức tháng, KHÔNG trần chi phí.

    Dành cho `/soat`: nó không gọi LLM một lần nào (nên `ENDPOINT_TON_LLM` cố ý
    loại nó, và trừ lượt của người dùng cho nó là bán thứ hệ thống không hề
    mua), nhưng nó tách clause + chạy cả rule engine ĐỒNG BỘ trên văn bản người
    dùng dán vào, và ghi một dòng `traces`. Không cổng nào thì một vòng `curl`
    làm treo tiến trình một-worker cho mọi người dùng khác — không tốn của kẻ
    gọi một xu, cũng không để lại một hạn mức nào chặn được họ.

    Nhịp đếm theo IP: endpoint này không yêu cầu danh tính nên không có khoá
    nào khác. Xem `cong_bao_ve` cho đường đầy đủ của endpoint tiêu tiền.
    """
    kiem_api_key(request)
    await run_in_threadpool(kiem_rate_limit, ip_goi(request))


async def nguoi_dung_bat_buoc(request: Request) -> dict:
    """Danh tính BẮT BUỘC cho dữ liệu theo người (phiên hội thoại). Khác `cong_bao_ve`
    ở một điểm: không có `sub` thì 401 kể cả khi Supabase chưa cấu hình — không có
    ai để gán phiên. Trả `{"sub", "email"}`."""
    kiem_api_key(request)
    await run_in_threadpool(kiem_rate_limit, ip_goi(request))
    nguoi = await run_in_threadpool(xac_thuc_nguoi_goi, request)
    if nguoi is None:
        raise HTTPException(
            status_code=401,
            detail="Cần đăng nhập để dùng tính năng này.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return nguoi


# ── Dependency dùng ở các endpoint tốn LLM ──────────────────────────────────


async def cong_bao_ve(request: Request) -> str | None:
    """Trả `sub` người gọi (None khi auth chưa cấu hình) — handler cần nó để ghi
    `traces.user_sub`, và không ghi được thì lượt đó không đếm vào hạn mức của ai.

    Thứ tự: API key (0 truy vấn) → LÁ CHẮN theo IP → danh tính → nhịp theo `sub`
    (hoặc theo IP khi chưa cấu hình auth) → hạn mức tháng → trần chi phí. Cổng
    RẺ đứng trước cổng ĐẮT, không có ngoại lệ.

    API key trước vì nó không tốn truy vấn nào: một request không có quyền không
    nên được phép làm hệ thống ghi một dòng DB.

    **Nhịp theo IP chạy TRƯỚC xác thực.** Xác thực là cổng ĐẮT NHẤT trên đường
    này: PyJWT bỏ qua TTL cache khi `kid` không khớp khoá đang cache
    (`get_signing_key` → `get_signing_keys(refresh=True)`), nên mỗi token mang
    một `kid` bịa ép MỘT round-trip HTTPS ra Supabase và giữ một luồng
    threadpool tới `TIMEOUT_JWKS_GIAY` = 5 giây. Anyio mặc định 40 luồng, nên
    40 request/giây với `kid` ngẫu nhiên làm cạn threadpool và treo mọi endpoint
    khác — bằng một token không ai ký, khi cổng nhịp còn chưa được chạy.

    **HAI giỏ, HAI mục đích — và hai hạn mức khác nhau.** Đây là chỗ dễ làm sai
    nhất, vì gộp chúng lại thì một trong hai tính chất luôn gãy:

    * `chan-ip:{ip}` (`rate_limit_ip_so_luot`, mặc định 60/60s) — LÁ CHẮN. Việc
      duy nhất của nó là chặn lụt trước khi tới `xac_thuc_nguoi_goi`. Nó RỘNG,
      vì nó đếm theo IP mà một văn phòng sau NAT là nhiều người trên một IP.
    * `user:{sub}` (`rate_limit_so_luot`, mặc định 10/60s) — HẠN MỨC NHỊP THẬT
      của một người, chạy sau khi đã biết người đó là ai.

    Siết lá chắn bằng hạn mức cá nhân là để người thứ hai sau cùng một NAT bị
    hãm vì lưu lượng của người thứ nhất — dự án có test khoá đúng tính chất này
    (`test_hai_nguoi_dung_sau_CUNG_mot_IP_khong_lam_can_han_muc_cua_nhau`), và
    nó đỏ ngay khi hai giỏ dùng chung một con số.

    Chưa cấu hình auth ⇒ không có `sub` nào để đếm, nên giỏ chặt quay về đếm
    theo IP, đúng như trước.

    Rate limit KHÔNG bị bỏ khi đã đăng nhập — nó hãm NHỊP (một chùm song song),
    còn hạn mức tháng hãm TỔNG; hai đại lượng khác nhau.

    Ba cổng cuối đọc/ghi Postgres ĐỒNG BỘ (SQLAlchemy) trong một `async def` →
    phải qua `run_in_threadpool`, nếu không chúng chặn event loop cho MỌI request
    khác. Dự án đã dính đúng lỗi này hai lần (`_ghi_traces`, `/soat`).
    `xac_minh` cũng vào threadpool: nó có thể gọi mạng (nạp JWKS khi TTL hết).
    """
    kiem_api_key(request)
    # Lá chắn, TRƯỚC `xac_thuc_nguoi_goi`: xem docstring — một `kid` bịa mua
    # được một round-trip HTTPS và 5 giây của một luồng threadpool, và một cổng
    # đứng SAU thứ nó bảo vệ thì không bảo vệ gì. Tiền tố `chan-ip:` để giỏ này
    # không bao giờ trộn số đếm với giỏ chặt bên dưới.
    ip = ip_goi(request)
    await run_in_threadpool(
        kiem_rate_limit, f"chan-ip:{ip}", get_settings().rate_limit_ip_so_luot
    )
    nguoi = await run_in_threadpool(xac_thuc_nguoi_goi, request)

    if nguoi is None:
        # Chưa cấu hình auth: không có danh tính để đếm, giỏ chặt quay về IP.
        await run_in_threadpool(kiem_rate_limit, ip)
        await run_in_threadpool(kiem_tran_chi_phi)
        return None

    sub = nguoi["sub"]
    # Tiền tố `user:` để một `sub` không bao giờ trùng giỏ với một IP dạng chuỗi.
    await run_in_threadpool(kiem_rate_limit, f"user:{sub}")
    # `plan` đọc trong CÙNG câu upsert đã ghi `last_seen_at` — một round-trip.
    # Lỗi ở đây là TỪ CHỐI (503), không phải "cho qua với gói mặc định": gói
    # quyết định hạn mức, và đoán nó là tự phát hạn mức cho một người mà hệ
    # thống vừa mất khả năng tra cứu.
    try:
        plan = await run_in_threadpool(ghi_nhan_nguoi_dung, sub, nguoi["email"])
    except Exception as e:
        logger.exception("cong_bao_ve: không đọc/ghi được dòng users — TỪ CHỐI")
        raise HTTPException(
            status_code=503,
            detail="Không đọc được thông tin tài khoản, tạm thời từ chối yêu cầu. Vui lòng thử lại.",
        ) from e

    await run_in_threadpool(kiem_han_muc_thang, sub, plan)
    await run_in_threadpool(kiem_tran_chi_phi)
    return sub
