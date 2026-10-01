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
  4. **Hạn mức NGÀY/THÁNG theo NGƯỜI DÙNG** (Postgres, đọc `traces`) — hãm TỔNG.
     Chỉ khi đã đăng nhập; đây là thứ cưỡng chế được con số trên trang bảng giá.
     Khách (chưa đăng nhập, chỉ khi Supabase đã cấu hình) không có dòng `traces`
     nào để đếm, nên cửa sổ 24 giờ của họ nằm ở tầng (3).
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
from src.services import nhat_ky, xac_thuc
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
EP_TRA_CUU, EP_SOAN_THAO = "/api/v1/tra-cuu", "/api/v1/soan-thao"
ENDPOINT_TON_LLM = (EP_TRA_CUU, EP_SOAN_THAO)

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
#
# Cột `ip` nay chứa một KHOÁ bất kỳ, không chỉ địa chỉ IP: `chan-ip:{ip}`,
# `ip-ngay:{ip}`, `user:{sub}`, `khach:{id}`, `khach-ip:{ip}`. Tên cột giữ
# nguyên (đổi tên cột là một migration cho đúng một nhãn), tên tham số `:ip`
# cũng vậy — chỉ Ý NGHĨA rộng ra.
_SQL_KHOA_IP = text("SELECT pg_advisory_xact_lock(hashtext(:ip))")
# Dọn THEO KHOÁ, không dọn cả bảng: bảng nay chứa nhiều cửa sổ khác nhau cạnh
# nhau (60 giây cho giỏ nhịp, 86400 giây cho giỏ khách), nên một câu dọn chung
# theo cửa sổ 60 giây sẽ xoá sạch lịch sử 24 giờ của giỏ khách — tức mở lại
# đúng cái cổng vừa đóng.
_SQL_DON_LUOT = text(
    "DELETE FROM rate_limit_luot WHERE ip = :khoa AND ts < now() - make_interval(secs => :cua_so)"
)
_SQL_GHI_LUOT = text("INSERT INTO rate_limit_luot (ip) VALUES (:ip)")
_SQL_DEM_LUOT = text(
    "SELECT count(*) FROM rate_limit_luot"
    " WHERE ip = :ip AND ts >= now() - make_interval(secs => :cua_so)"
)
# Lượt CŨ NHẤT còn trong cửa sổ — mốc để nói `Retry-After` thật thay vì "cả cửa
# sổ": với giỏ 24 giờ, "thử lại sau 86400 giây" gần như luôn sai và luôn bi quan.
_SQL_LUOT_CU_NHAT = text(
    "SELECT min(ts) FROM rate_limit_luot WHERE ip = :khoa AND ts >= now() - make_interval(secs => :cua_so)"
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
    " RETURNING plan, plan_het_han, khoa_luc"
)

# Đếm SỐ LƯỢT gọi LLM thật của một `sub` trên MỘT endpoint, từ một mốc.
#
# `NOT cache_hit` — cache hit không gọi LLM và không tốn một xu (đo được ở vòng
# hardening: $0 và 3ms, so với ~$0,0004 và ~6,9s một lượt thật).
#
# `result_type NOT IN ('loi', 'out_of_scope')` — một lượt hỏng và một câu ngoài
# phạm vi không phải thứ người dùng mua; trừ lượt cho chúng là bắt họ trả cho
# lỗi của hệ thống. `IS NULL` VẪN đếm: `/soan-thao` thành công ghi NULL ở cột này.
#
# Đếm `count(*)`, KHÔNG `cost_usd > 0`: chi phí là một đại lượng ĐO ĐƯỢC và có
# thể bằng 0 vì một lỗi ghi nhận — đã xảy ra thật, 32/32 dòng `/soan-thao` từng
# ghi $0 dù mỗi request tốn một lượt LLM. "Đã gọi hay chưa" không phụ thuộc việc
# cột chi phí có được cộng đúng, nên hạn mức của người dùng cũng không được.
_SQL_DEM_LUOT_TU = text(
    "SELECT count(*) FROM traces WHERE user_sub = :sub AND ts >= :moc AND NOT cache_hit"
    " AND endpoint = :ep AND (result_type IS NULL OR result_type NOT IN ('loi', 'out_of_scope'))"
)
_SQL_HET_HAN = text("SELECT plan_het_han FROM users WHERE sub = :sub")


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


TEN_HEADER_ADMIN_KEY = "X-Admin-Key"
TEN_HEADER_ADMIN_BOI = "X-Admin-Boi"
LOI_ADMIN_CHUA_CAU_HINH = "Đường quản trị chưa được cấu hình."


async def kiem_admin_key(request: Request) -> dict:
    """Cổng của router `/admin` (spec 2B §5.3), dừng ở bước đầu hỏng: lá chắn IP →
    khoá phải được cấu hình (503, fail-closed) → khoá khớp (401 + nhật ký) → danh
    tính admin (400). Trả `{"boi", "ip"}` cho handler ghi `xu_ly_boi`."""
    ip = ip_goi(request)
    await run_in_threadpool(kiem_rate_limit, f"chan-ip:{ip}", get_settings().rate_limit_ip_so_luot)
    khoa_that = get_settings().admin_api_key
    if not khoa_that:
        raise HTTPException(status_code=503, detail=LOI_ADMIN_CHUA_CAU_HINH)
    khoa_gui = request.headers.get(TEN_HEADER_ADMIN_KEY.lower(), "")
    if not secrets.compare_digest(khoa_gui.encode("utf-8"), khoa_that.encode("utf-8")):
        try:
            await run_in_threadpool(
                nhat_ky.ghi, "xac_thuc_that_bai", doi_tuong=None, chi_tiet={}, boi="(không rõ)", ip=ip
            )
        except Exception:
            logger.exception("kiem_admin_key: không ghi được nhật ký xác thực thất bại")
        raise HTTPException(
            status_code=401,
            detail=f"Thiếu hoặc sai header {TEN_HEADER_ADMIN_KEY}.",
            headers={"WWW-Authenticate": TEN_HEADER_ADMIN_KEY},
        )
    boi = request.headers.get(TEN_HEADER_ADMIN_BOI.lower(), "").strip()
    if not boi:
        raise HTTPException(status_code=400, detail=f"Thiếu header {TEN_HEADER_ADMIN_BOI}.")
    return {"boi": boi, "ip": ip}


# ── Cổng 2: rate limit theo IP ──────────────────────────────────────────────


def _cau_429_nhip(khoa: str, so_luot: int, cua_so: int, con: int) -> str:
    """Câu 429 của tầng NHỊP, nói đúng thứ người đọc nó cần làm tiếp.

    Ba giỏ, ba việc khác nhau: khách hết lượt thử thì việc cần làm là ĐĂNG NHẬP
    (miễn phí, và giữ được đoạn chat), còn một giỏ theo địa chỉ mạng thì người
    đọc không đăng nhập được ra khỏi nó — nói "đăng nhập đi" ở đó là gửi họ đi
    làm một việc không giải quyết gì.
    """
    mo_lai = (datetime.now(UTC) + timedelta(seconds=con)).astimezone(mui_gio()).strftime("%H:%M ngày %d/%m")
    if khoa.startswith("khach:"):
        return (
            f"Bạn đã dùng {so_luot} lượt thử trong 24 giờ. Đăng nhập miễn phí để tiếp tục và lưu đoạn"
            f" chat này, hoặc quay lại lúc {mo_lai}."
        )
    if khoa.startswith(("ip-ngay:", "khach-ip:")):
        return f"Đã vượt giới hạn {so_luot} lượt trong 24 giờ cho địa chỉ mạng này. Mở lại lúc {mo_lai}."
    return f"Vượt giới hạn tần suất: tối đa {so_luot} lượt trong {cua_so} giây. Vui lòng thử lại sau {con} giây."


def kiem_rate_limit(khoa: str, so_luot: int | None = None, cua_so_giay: int | None = None) -> None:
    """Cửa sổ TRƯỢT trong Postgres theo `khoa` (IP, `user:{sub}`, `khach:{id}`…). Vượt → 429.

    `so_luot` None = dùng `rate_limit_so_luot` (hạn mức NHỊP của một người).
    Truyền tường minh cho giỏ có mục đích khác — lá chắn trước xác thực dùng
    `rate_limit_ip_so_luot`, rộng hơn nhiều; xem `cong_bao_ve`.

    Cửa sổ trượt, không phải cửa sổ cố định theo phút: cửa sổ cố định cho phép
    gấp đôi hạn mức quanh mốc chuyển phút (10 lượt cuối phút này + 10 lượt đầu
    phút sau).

    Dọn hàng cũ THEO KHOÁ: bảng nay chứa nhiều cửa sổ khác nhau, một câu dọn
    chung theo 60 giây sẽ xoá dữ liệu của giỏ 24 giờ. `Retry-After` = giây tới
    khi lượt cũ nhất rời cửa sổ.

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
    cua_so = cua_so_giay if cua_so_giay is not None else s.rate_limit_cua_so_giay
    try:
        with get_engine().begin() as c:
            c.execute(_SQL_KHOA_IP, {"ip": khoa})
            c.execute(_SQL_DON_LUOT, {"khoa": khoa, "cua_so": cua_so})
            c.execute(_SQL_GHI_LUOT, {"ip": khoa})
            da_dung = c.execute(_SQL_DEM_LUOT, {"ip": khoa, "cua_so": cua_so}).scalar_one()
            cu_nhat = c.execute(_SQL_LUOT_CU_NHAT, {"khoa": khoa, "cua_so": cua_so}).scalar_one()
    except Exception as e:
        logger.exception("kiem_rate_limit: không đếm được lượt gọi (khoa=%s) — TỪ CHỐI", khoa)
        raise HTTPException(
            status_code=503,
            detail="Không kiểm được giới hạn tần suất, tạm thời từ chối yêu cầu. Vui lòng thử lại.",
        ) from e

    if da_dung > so_luot:
        con = cua_so
        if cu_nhat is not None:
            con = max(1, int(cua_so - (datetime.now(UTC) - cu_nhat).total_seconds()))
        raise HTTPException(
            status_code=429, detail=_cau_429_nhip(khoa, so_luot, cua_so, con), headers={"Retry-After": str(con)}
        )


def dem_cua_so(khoa: str, cua_so_giay: int) -> tuple[int, datetime | None]:
    """Đếm KHÔNG ghi lượt (cho `/han-muc` của khách): (đã dùng, lúc lượt cũ nhất rời cửa sổ)."""
    with get_engine().connect() as c:
        n = int(c.execute(_SQL_DEM_LUOT, {"ip": khoa, "cua_so": cua_so_giay}).scalar_one())
        cu_nhat = c.execute(_SQL_LUOT_CU_NHAT, {"khoa": khoa, "cua_so": cua_so_giay}).scalar_one()
    return n, (cu_nhat + timedelta(seconds=cua_so_giay)) if cu_nhat is not None else None


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
            detail="KLAW tạm thời chưa nhận yêu cầu mới. Vui lòng thử lại sau ít phút.",
        ) from e

    if da_dung >= s.tran_chi_phi_ngay_usd:
        mo_lai = _dau_ngay_utc() + timedelta(days=1)
        # Quyết định 2026-09-30 mục 11: chi phí là thông tin nội bộ — trần và số đã tiêu chỉ
        # vào log; người dùng biết KLAW hết lượt hôm nay và khi nào mở lại.
        logger.warning("kiem_tran_chi_phi: chạm trần ngày %s USD (đã dùng %.5f USD)", s.tran_chi_phi_ngay_usd, da_dung)
        raise HTTPException(
            status_code=429,
            detail=(
                f"KLAW đã nhận đủ lượt hỏi cho hôm nay. Hạn mức mở lại lúc {mo_lai.strftime('%H:%M %d/%m/%Y')} UTC."
            ),
            headers={"Retry-After": str(int((mo_lai - datetime.now(UTC)).total_seconds()))},
        )


# ── Cổng 4: danh tính + hạn mức THÁNG theo NGƯỜI DÙNG ───────────────────────


KHOA_GOI = ("hoi_dap_ngay", "soan_thao_ngay", "soan_thao_thang", "luot_moi_phien")
KHOA_LA_CHAN = ("free_hoi_dap_thang", "ip_ngay")
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


def ghi_nhan_nguoi_dung(sub: str, email: str | None) -> str:
    """Upsert dòng `users` và trả gói HIỆU LỰC (đã xét `plan_het_han`). CÓ THỂ RAISE.

    Chỉ ghi `sub`/`email`/`last_seen_at` — xem `migrations/012` cho lý do từng
    cột và lý do KHÔNG có `ho_ten`/`avatar_url`/`provider`.
    """
    with get_engine().begin() as c:
        r = c.execute(_SQL_UPSERT_USER, {"sub": sub, "email": email}).mappings().one()
    return plan_hieu_luc_tu(str(r["plan"]), r["plan_het_han"])


# Nhãn của ba thanh đo trên trang tài khoản. Chỉ ba khoá trong `goi`: lá chắn
# CỐ Ý không có mặt — nó là biện pháp chống lạm dụng, không phải một lời hứa bán
# hàng, và vẽ nó thành một thanh đo là biến nó thành lời hứa.
NHAN_MUC = {
    "hoi_dap_ngay": "Hỏi đáp hôm nay",
    "soan_thao_ngay": "Bản thảo hôm nay",
    "soan_thao_thang": "Bản thảo tháng này",
}
LOI_KHACH_DANG_NHAP = "Cần đăng nhập để dùng tính năng này."
LOI_SOAN_THAO_DANG_NHAP = "Cần đăng nhập để soạn văn bản."
LOI_TAI_KHOAN_KHOA = "Tài khoản của bạn đang bị tạm khoá. Liên hệ hỗ trợ để được mở lại."
_SQL_KHOA = text("SELECT khoa_luc FROM users WHERE sub = :sub")


def bi_khoa(sub: str) -> bool:
    """`users.khoa_luc IS NOT NULL`; chưa có dòng → False."""
    with get_engine().connect() as c:
        return c.execute(_SQL_KHOA, {"sub": sub}).scalar_one_or_none() is not None


def kiem_khoa(sub: str) -> None:
    """403 khi tài khoản bị khoá (spec 2B §5.2). Một truy vấn khoá chính; dùng ở
    `nguoi_dung_bat_buoc` — không phải đường tốn LLM."""
    if bi_khoa(sub):
        raise HTTPException(status_code=403, detail=LOI_TAI_KHOAN_KHOA)


def ghi_nhan_va_kiem_khoa(sub: str, email: str | None) -> str:
    """Như `ghi_nhan_nguoi_dung` nhưng ném 403 khi khoá — cùng MỘT round-trip, cho
    đường tốn LLM. Tách hàm thay vì đổi `ghi_nhan_nguoi_dung`: `/han-muc` và
    `/nguoi-dung` phải vẫn trả lời người bị khoá để giao diện vẽ được thẻ khoá."""
    with get_engine().begin() as c:
        r = c.execute(_SQL_UPSERT_USER, {"sub": sub, "email": email}).mappings().one()
    if r["khoa_luc"] is not None:
        raise HTTPException(status_code=403, detail=LOI_TAI_KHOAN_KHOA)
    return plan_hieu_luc_tu(str(r["plan"]), r["plan_het_han"])


def ten_goi(plan: str) -> str:
    """Tên NGƯỜI ĐỌC của gói. Gói lạ → chính mã của nó (thà lộ một mã kỹ thuật
    còn hơn gọi một gói trả phí là "Miễn phí" trong câu từ chối)."""
    return {"free": "Miễn phí", "pro": "Cá nhân"}.get(plan, plan)


def dem_luot(sub: str, endpoint: str, tu_luc: datetime) -> int:
    """Số lượt LLM thật của `sub` trên `endpoint` từ `tu_luc`. CÓ THỂ RAISE (caller từ chối)."""
    with get_engine().connect() as c:
        return int(c.execute(_SQL_DEM_LUOT_TU, {"sub": sub, "moc": tu_luc, "ep": endpoint}).scalar_one())


def het_han_cua(sub: str) -> datetime | None:
    """`users.plan_het_han` của `sub` (NULL = không hết hạn, hoặc chưa có dòng)."""
    with get_engine().connect() as c:
        return c.execute(_SQL_HET_HAN, {"sub": sub}).scalar_one_or_none()


def _cau_429(plan: str, da_dung: int, tran: int, loai: str, ky: str, mo_lai: datetime) -> str:
    luc = mo_lai.astimezone(mui_gio()).strftime("%H:%M ngày %d/%m")
    return f"{ky} bạn đã dùng {da_dung}/{tran} lượt {loai} của gói {ten_goi(plan)}. Mở lại lúc {luc}."


def _kiem_mot(
    sub: str, plan: str, endpoint: str, tran: int, moc: datetime, mo_lai: datetime, loai: str, ky: str
) -> None:
    """Một trần, một cửa sổ. Không đếm được là TỪ CHỐI (503), cùng nguyên tắc với
    trần chi phí: không đếm được thì không biết còn bao nhiêu suất."""
    if tran >= 100_000:  # quy ước của `config/han_muc.yaml`: không giới hạn
        return
    try:
        da_dung = dem_luot(sub, endpoint, moc)
    except Exception as e:
        logger.exception("kiem_han_muc: không đếm được lượt — TỪ CHỐI")
        raise HTTPException(
            status_code=503,
            detail="Không kiểm được hạn mức của tài khoản, tạm thời từ chối yêu cầu. Vui lòng thử lại.",
        ) from e
    if da_dung >= tran:
        raise HTTPException(
            status_code=429,
            detail=_cau_429(plan, da_dung, tran, loai, ky, mo_lai),
            headers={"Retry-After": str(max(1, int((mo_lai - datetime.now(UTC)).total_seconds())))},
        )


def kiem_han_muc(sub: str, plan: str, endpoint: str) -> None:
    """Spec 2A §4.2. `/tra-cuu*` (cả `/luong`) kiểm ngày rồi lá chắn tháng free; Pro chỉ có
    hạn mức ngày. `/soan-thao` kiểm ngày rồi tháng. Trần >= 100000 = không giới hạn.

    Trần của GÓI đứng trước lá chắn: khi cả hai đã cạn, câu người dùng đọc phải
    là con số họ mua, không phải con số chống lạm dụng mà họ chưa từng nghe tới.
    """
    if endpoint.startswith(EP_TRA_CUU):
        ep, loai = EP_TRA_CUU, "hỏi đáp"
        cac_muc = [(han_muc(plan, "hoi_dap_ngay"), moc_ngay(), moc_ngay_sau(), "Hôm nay")]
        if plan == "free":
            cac_muc.append((la_chan("free_hoi_dap_thang"), moc_thang(), moc_thang_sau(), "Tháng này"))
    elif endpoint.startswith(EP_SOAN_THAO):
        ep, loai = EP_SOAN_THAO, "bản thảo"
        cac_muc = [
            (han_muc(plan, "soan_thao_ngay"), moc_ngay(), moc_ngay_sau(), "Hôm nay"),
            (han_muc(plan, "soan_thao_thang"), moc_thang(), moc_thang_sau(), "Tháng này"),
        ]
    else:  # endpoint không tốn LLM (`/soat`, `/tim-kiem`…) — không giỏ nào của nó ở đây
        return
    for tran, moc, sau, ky in cac_muc:
        _kiem_mot(sub, plan, ep, tran, moc, sau, loai, ky)


def mo_ta_muc(sub: str, plan: str) -> list[dict]:
    """Các thanh đo của `/han-muc` (chỉ khoá trong `goi`, không gồm lá chắn)."""
    return [
        {
            "khoa": khoa,
            "nhan": NHAN_MUC[khoa],
            "da_dung": dem_luot(sub, ep, moc),
            "han_muc": han_muc(plan, khoa),
            "dat_lai_luc": sau,
        }
        for khoa, ep, moc, sau in (
            ("hoi_dap_ngay", EP_TRA_CUU, moc_ngay(), moc_ngay_sau()),
            ("soan_thao_ngay", EP_SOAN_THAO, moc_ngay(), moc_ngay_sau()),
            ("soan_thao_thang", EP_SOAN_THAO, moc_thang(), moc_thang_sau()),
        )
    ]


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


def xac_thuc_nguoi_goi_hoac_none(request: Request) -> dict | None:
    """Như `xac_thuc_nguoi_goi`, nhưng KHÔNG có header Authorization → None (đường khách).

    Token có mà sai/hết hạn vẫn 401 — không để một token hỏng rơi xuống đường
    khách: nếu nó rơi, một phiên hết hạn im lặng biến thành một phiên khách và
    người dùng mất lịch sử của mình mà không một thông báo nào nói vì sao.
    """
    if not xac_thuc.da_cau_hinh():
        return None
    if request.headers.get(xac_thuc.TEN_HEADER.lower()) is None:
        return None
    return xac_thuc_nguoi_goi(request)


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
    await run_in_threadpool(kiem_khoa, nguoi["sub"])
    return nguoi


async def nguoi_dung_ke_ca_khoa(request: Request) -> dict:
    """Như `nguoi_dung_bat_buoc` nhưng KHÔNG chặn tài khoản bị khoá: dùng cho hộp thư
    thông báo — người bị khoá phải đọc được chính thông báo "tài khoản bị khoá"
    (cùng lý do `/han-muc` và `/nguoi-dung` vẫn trả lời người bị khoá). Không phải
    đường tốn LLM."""
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


def _cong(cho_khach: bool):
    """Trả `sub` người gọi (None khi auth chưa cấu hình HOẶC người gọi là khách) —
    handler cần nó để ghi
    `traces.user_sub`, và không ghi được thì lượt đó không đếm vào hạn mức của ai.

    Thứ tự: API key (0 truy vấn) → LÁ CHẮN theo IP → lá chắn ngày theo IP →
    danh tính → nhịp theo `sub` (hoặc theo IP khi chưa cấu hình auth) → hạn mức
    ngày/tháng → trần chi phí. Cổng RẺ đứng trước cổng ĐẮT, không có ngoại lệ.

    **Hai biến thể, một thân.** `cong_bao_ve_khach` cho `/tra-cuu*`: không có
    token thì `X-Khach-Id` mở một cửa sổ 10 lượt/24 giờ — đó là cách người chưa
    có tài khoản thử được sản phẩm. `cong_bao_ve` cho `/soan-thao`: không có
    token là 401, vì một bản thảo phải thuộc về một tài khoản để người ta còn
    mở lại được nó. Viết hai bản chép tay là để hai đường lệch pha ở lần sửa
    thứ ba; `cho_khach` là DUY NHẤT chỗ chúng khác nhau.

    Khách KHÔNG được ghi `traces.user_sub` (không có tài khoản để gán) nên
    hàm trả None, và không một dòng `users`/phiên hội thoại nào được tạo cho họ:
    một dòng `users` với `sub` bịa ra là dữ liệu rác vĩnh viễn trong đúng bảng
    mà hạn mức đếm theo. Nhịp của khách vì thế đếm ở tầng `rate_limit_luot`,
    không ở tầng `traces`.

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

    async def cong(request: Request) -> str | None:
        kiem_api_key(request)
        # Lá chắn, TRƯỚC `xac_thuc_nguoi_goi`: xem docstring — một `kid` bịa mua
        # được một round-trip HTTPS và 5 giây của một luồng threadpool, và một cổng
        # đứng SAU thứ nó bảo vệ thì không bảo vệ gì. Tiền tố `chan-ip:` để giỏ này
        # không bao giờ trộn số đếm với giỏ chặt bên dưới.
        ip = ip_goi(request)
        await run_in_threadpool(kiem_rate_limit, f"chan-ip:{ip}", get_settings().rate_limit_ip_so_luot)
        da_cau_hinh = xac_thuc.da_cau_hinh()
        # Lá chắn NGÀY theo IP, chỉ khi auth đã bật: nó tồn tại để chặn một người
        # thay `X-Khach-Id` mỗi request và mua vô hạn lượt khách. Khi auth chưa
        # cấu hình thì không có đường khách nào để chặn, và giỏ này sẽ chỉ hãm
        # `eval/run.py` — đúng thứ bất biến "chưa cấu hình ⇒ hành vi KHÔNG ĐỔI" cấm.
        if da_cau_hinh:
            await run_in_threadpool(kiem_rate_limit, f"ip-ngay:{ip}", la_chan("ip_ngay"), 86400)
        nguoi = await run_in_threadpool(xac_thuc_nguoi_goi_hoac_none, request)

        if nguoi is None and not da_cau_hinh:
            # Chưa cấu hình auth: không có danh tính để đếm, giỏ chặt quay về IP.
            await run_in_threadpool(kiem_rate_limit, ip)
            await run_in_threadpool(kiem_tran_chi_phi)
            return None

        if nguoi is None:
            if not cho_khach:
                raise HTTPException(
                    status_code=401, detail=LOI_SOAN_THAO_DANG_NHAP, headers={"WWW-Authenticate": "Bearer"}
                )
            kid = khach_id_tu_request(request)
            if kid is None:
                raise HTTPException(status_code=401, detail=LOI_KHACH_DANG_NHAP, headers={"WWW-Authenticate": "Bearer"})
            # Hai giỏ cho khách, cùng lý lẽ hai giỏ của người đã đăng nhập: `khach:{id}`
            # là hạn mức của một trình duyệt, `khach-ip:{ip}` chặn một người sinh
            # ra một nghìn `X-Khach-Id` — header đó là khoá ĐẾM, không phải danh tính.
            k = _doc_han_muc()["khach"]
            await run_in_threadpool(kiem_rate_limit, f"khach:{kid}", int(k["hoi_dap_24h"]), 86400)
            await run_in_threadpool(kiem_rate_limit, f"khach-ip:{ip}", int(k["ip_24h"]), 86400)
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
            plan = await run_in_threadpool(ghi_nhan_va_kiem_khoa, sub, nguoi["email"])
        except HTTPException:
            raise  # 403 khoá — KHÔNG được nuốt thành 503 bởi nhánh dưới
        except Exception as e:
            logger.exception("cong_bao_ve: không đọc/ghi được dòng users — TỪ CHỐI")
            raise HTTPException(
                status_code=503,
                detail="Không đọc được thông tin tài khoản, tạm thời từ chối yêu cầu. Vui lòng thử lại.",
            ) from e

        await run_in_threadpool(kiem_han_muc, sub, plan, request.url.path)
        await run_in_threadpool(kiem_tran_chi_phi)
        return sub

    cong.__name__ = "cong_bao_ve_khach" if cho_khach else "cong_bao_ve"
    return cong


cong_bao_ve = _cong(cho_khach=False)
cong_bao_ve_khach = _cong(cho_khach=True)
