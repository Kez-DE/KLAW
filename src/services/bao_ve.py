"""Ba cổng trước ví tiền, chạy TRƯỚC khi một token nào bị tiêu.

Bối cảnh ĐO ĐƯỢC trên chính DB của dự án (không phải giả thuyết):
  * `/tra-cuu` gọi LLM tối đa 5 lần; p50 10.000ms, p95 50.289ms (204 dòng traces)
  * request đắt nhất đã ghi nhận: $0,00735
  * ngày cao nhất tới nay: 118 request / $0,18329 (2026-08-30)
  * dự án ĐÃ gặp HTTP 429 từ OpenRouter khi nhiều tiến trình chạy song song
Mở 8 endpoint ra công khai nguyên trạng thì một người với một vòng `curl` rút
cạn key trong một buổi.

Ba cổng CHỒNG nhau chứ không thay nhau:
  1. **API key** (0 truy vấn) — chặn người không được phép, nếu đã cấu hình.
  2. **Rate limit theo IP** (Postgres) — hãm nhịp, giữ tải trong ngưỡng các
     mặc định của threadpool/connection pool còn chịu được.
  3. **Trần chi phí ngày** (Postgres, đọc `traces`) — cổng CUỐI trước ví tiền.

Nguyên tắc chung: **hỏng ở tầng đếm là TỪ CHỐI, không phải mở cửa.** Nếu không
đếm được thì không biết còn bao nhiêu tiền, và cho qua là hành xử như thể trần
chi phí không tồn tại.

Bộ đếm nằm trong Postgres, KHÔNG in-process: in-process chỉ đúng khi có MỘT
worker (`Dockerfile` hiện đúng vậy, nhưng đó là trạng thái tạm), và một rate
limit đúng-cho-đến-khi-scale là một rate limit sai.
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from src.config import get_settings
from src.services.db import get_engine

logger = logging.getLogger(__name__)

TEN_HEADER_KEY = "X-API-Key"

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


# ── IP thật ─────────────────────────────────────────────────────────────────


def ip_goi(request: Request) -> str:
    """IP để đếm rate limit.

    `X-Forwarded-For` CHỈ được tin khi `KLAW_TIN_PROXY_HEADER=true`. Mặc định
    KHÔNG tin, vì nếu tin mà thực tế không có reverse proxy đặt header đó thì
    bất kỳ ai cũng gửi một IP giả khác nhau mỗi request và rate limit theo IP
    trở thành trang trí. Khi tin thì lấy phần tử ĐẦU (client gốc) — các phần tử
    sau là chuỗi proxy.
    """
    if get_settings().tin_proxy_header:
        xff = request.headers.get("x-forwarded-for")
        if xff and xff.split(",")[0].strip():
            return xff.split(",")[0].strip()
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


def kiem_rate_limit(ip: str) -> None:
    """Cửa sổ TRƯỢT trong Postgres. Vượt → 429.

    Cửa sổ trượt, không phải cửa sổ cố định theo phút: cửa sổ cố định cho phép
    gấp đôi hạn mức quanh mốc chuyển phút (10 lượt cuối phút này + 10 lượt đầu
    phút sau).

    Đếm SAU khi ghi lượt của chính request này, nên `> hạn mức` từ chối đúng
    request thứ (hạn mức + 1). Lỗi DB ở đây là TỪ CHỐI (503), không phải mở cửa.
    """
    s = get_settings()
    if s.rate_limit_so_luot <= 0:  # 0 = TẮT (eval sweep qua HTTP)
        return
    cua_so = s.rate_limit_cua_so_giay
    try:
        with get_engine().begin() as c:
            c.execute(_SQL_KHOA_IP, {"ip": ip})
            c.execute(_SQL_DON_LUOT, {"cua_so": cua_so})
            c.execute(_SQL_GHI_LUOT, {"ip": ip})
            so_luot = c.execute(_SQL_DEM_LUOT, {"ip": ip, "cua_so": cua_so}).scalar_one()
    except Exception as e:
        logger.exception("kiem_rate_limit: không đếm được lượt gọi (ip=%s) — TỪ CHỐI", ip)
        raise HTTPException(
            status_code=503,
            detail="Không kiểm được giới hạn tần suất, tạm thời từ chối yêu cầu. Vui lòng thử lại.",
        ) from e

    if so_luot > s.rate_limit_so_luot:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Vượt giới hạn tần suất: tối đa {s.rate_limit_so_luot} lượt "
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


# ── Dependency dùng ở các endpoint tốn LLM ──────────────────────────────────


async def cong_bao_ve(request: Request) -> None:
    """Thứ tự: API key (0 truy vấn) → rate limit → trần chi phí.

    API key trước vì nó không tốn truy vấn nào: một request không có quyền không
    nên được phép làm hệ thống ghi một dòng DB.

    Trần chi phí kiểm TRƯỚC cache (cache nằm trong handler): cache hit tốn $0
    nên chặn nó khi đã cạn trần là một từ chối OAN — nhưng đó là hướng hỏng CÓ
    CHỦ Ý. Đạt trần $2/ngày trong khi ngày cao nhất đo được là $0,18 nghĩa là
    có điều bất thường đang xảy ra, và lúc đó đóng hẳn endpoint đúng hơn là
    phục vụ chọn lọc. Nghi ngờ giữa "chặn" và "cho qua" thì chặn.

    Hai kiểm tra sau đọc/ghi Postgres ĐỒNG BỘ (SQLAlchemy) trong một `async def`
    → phải qua `run_in_threadpool`, nếu không chúng chặn event loop cho MỌI
    request khác. Dự án đã dính đúng lỗi này hai lần (`_ghi_traces`, `/soat`).
    """
    kiem_api_key(request)
    await run_in_threadpool(kiem_rate_limit, ip_goi(request))
    await run_in_threadpool(kiem_tran_chi_phi)
