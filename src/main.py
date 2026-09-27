import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers

from src.agents import graph_soan_thao as soan_thao_graph
from src.api.routes import router
from src.api.routes_admin import router as router_admin
from src.api.routes_ban_thao import router as router_ban_thao
from src.api.routes_hoi_thoai import router as router_hoi_thoai
from src.api.routes_luong import router as router_luong
from src.api.routes_tai_khoan import router as router_tai_khoan
from src.api.routes_tai_lieu import router as router_tai_lieu
from src.api.routes_tim_kiem import router as router_tim_kiem
from src.api.routes_van_ban import router as router_van_ban
from src.config import get_settings
from src.services import checklist as checklist_svc
from src.services import db as db_svc
from src.services import rules as rules_svc
from src.services.tai_lieu import TRAN_BYTE

logger = logging.getLogger(__name__)

# Migration prefixes lifespan re-applies on every start (fail-fast guards for
# columns a hot path reads unconditionally). `tests/test_api/test_guard_khoi_dong.py`
# asserts every migrations/*.sql from "019" onward has its prefix here, so a new
# migration in that range can't be silently skipped at startup.
MIGRATIONS_KHOI_DONG = (
    "019",
    "020",
    "021",
    "022",
    "023",
    "024",
    "025",
    "026",
    "027",
    "028",
    "029",
    "030",
    "031",
    "032",
    "033",
    "034",
    "035",
    "036",
    "037",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    # Production PHẢI có ít nhất MỘT cách biết người gọi là ai. `cong_bao_ve`
    # coi `nguoi is None` (Supabase chưa cấu hình) là một đường ĐI TIẾP, và cả
    # `KLAW_API_KEY` lẫn `KLAW_SUPABASE_URL` đều mặc định RỖNG = MỞ — nên quên
    # đặt cả hai không phát ra một tín hiệu nào, và ba endpoint tiêu tiền chạy
    # công khai. Đo được trước khi có guard này: 768/768 dòng traces của
    # `/tra-cuu` có `user_sub` NULL, bảng `users` 0 dòng — hạn mức tháng chưa
    # từng trừ của ai một lượt nào.
    #
    # Đặt TRƯỚC phần kiểm can_cu bên dưới: đây là lỗi CẤU HÌNH, biết được mà
    # không cần một truy vấn nào, và một deployment sai cấu hình không nên chạy
    # xa tới mức mở kết nối Postgres. Cùng khuôn fail-fast với
    # `kiem_tra_can_cu_ton_tai` — hỏng lúc khởi động, không hỏng giữa lúc người
    # dùng đang chờ.
    if settings.app_env == "production" and not (settings.api_key or settings.supabase_url):
        raise RuntimeError(
            "production mà KHÔNG đặt KLAW_API_KEY lẫn KLAW_SUPABASE_URL: ba endpoint "
            "tiêu tiền (/tra-cuu, /tra-cuu/luong, /soan-thao) sẽ mở công khai và hạn "
            "mức tháng không trừ được của ai. Đặt ít nhất một trong hai rồi khởi động lại."
        )
    # Supabase đã cấu hình MÀ `KLAW_RATE_LIMIT_SO_LUOT=0` ⇒ hạn mức khách FAIL
    # OPEN. `bao_ve.kiem_rate_limit` mở đầu bằng `if s.rate_limit_so_luot <= 0:
    # return` — công tắc CỐ Ý cho `eval/run.py`, chạy hàng trăm lượt qua HTTP —
    # nhưng nó tắt cả những giỏ được truyền trần TƯỜNG MINH: `khach:{id}` (10
    # lượt/24 giờ), `khach-ip:` và `ip-ngay:`. Tức đúng tổ hợp này cho người
    # CHƯA đăng nhập gọi LLM không giới hạn, im lặng.
    #
    # KHÔNG vá ở `kiem_rate_limit`: escape hatch đó là thứ giữ cho eval chạy
    # được, và eval chạy KHÔNG có Supabase nên hai điều kiện dưới đây không bao
    # giờ đúng cùng lúc ở đó. Vá ở đây, cùng khuôn fail-fast với guard ngay
    # trên: một tổ hợp cấu hình không dùng được thì không được khởi động.
    #
    # Đọc `settings.supabase_url` chứ không gọi `xac_thuc.da_cau_hinh()`: hàm
    # đó chính là `bool(get_settings().supabase_url)`, nhưng đọc qua `settings`
    # giữ cả lifespan trên MỘT đối tượng cấu hình.
    if settings.supabase_url and settings.rate_limit_so_luot <= 0:
        raise RuntimeError(
            "KLAW_SUPABASE_URL đã đặt mà KLAW_RATE_LIMIT_SO_LUOT=0: công tắc đó tắt CẢ "
            "hạn mức khách (10 lượt/24 giờ), giỏ khach-ip và ip-ngay, nên người chưa "
            "đăng nhập gọi LLM không giới hạn. Đặt KLAW_RATE_LIMIT_SO_LUOT > 0 (mặc "
            "định 10) rồi khởi động lại; số 0 chỉ dành cho eval chạy KHÔNG có Supabase."
        )
    # Cùng bệnh, cổng khác: `KLAW_ADMIN_API_KEY` đã đặt mà `KLAW_RATE_LIMIT_SO_LUOT=0`
    # ⇒ lá chắn IP (`chan-ip:{ip}`) mà `kiem_admin_key` gọi trước tiên tắt theo, vì
    # `kiem_rate_limit` mở đầu bằng CÙNG công tắc toàn cục. Không có lá chắn đó thì
    # mọi request CHƯA xác thực chạm thẳng nhánh 401 — dò khoá quản trị không giới
    # hạn, và mỗi lần sai còn ghi một dòng `nhat_ky_quan_tri`.
    if settings.admin_api_key and settings.rate_limit_so_luot <= 0:
        raise RuntimeError(
            "KLAW_ADMIN_API_KEY đã đặt mà KLAW_RATE_LIMIT_SO_LUOT=0: công tắc đó tắt cả lá chắn "
            "IP trước cổng /admin, nên ai cũng dò khoá quản trị không giới hạn và mỗi lần sai ghi "
            "một dòng nhật ký. Đặt KLAW_RATE_LIMIT_SO_LUOT > 0 rồi khởi động lại; số 0 chỉ dành cho eval."
        )
    # Migration 019 (link_vbpl/link_chinhphu/link_tvpl) PHẢI áp trước khi
    # `graph_tra_cuu.py` SELECT ba cột này — SELECT đó vô điều kiện, trên đường
    # nóng của MỌI câu trả lời có trích dẫn (Important A, final review
    # 2026-09-06): một DB chưa áp 019 làm `_db_provisions` nổ
    # `UndefinedColumn`, tức HTTP 500 cho mọi answer có căn cứ. File .sql dùng
    # `ADD COLUMN IF NOT EXISTS` nên idempotent — an toàn chạy lại mỗi lần
    # khởi động, cùng khuôn fail-fast với hai guard bên dưới. Migration 023
    # (bo_nho: cột tom_tat/ho_so/khong_ghi_nho và bảng ho_so_tai_khoan) is
    # included for the same reason: Phase 2 memory reads must not hit
    # UndefinedColumn on a fresh deploy.
    for mig in MIGRATIONS_KHOI_DONG:
        db_svc.run_migrations(mig)
    # Task 5, ràng buộc #2: kiểm can_cu LÚC KHỞI ĐỘNG, không phải lúc người
    # dùng gọi /soan-thao hay /soat. Một can_cu chết (rule hoặc mục checklist
    # trích dẫn điều luật không tồn tại) phải làm app fail nhanh ngay đây —
    # không nổ giữa lúc người dùng đang chờ. `kiem_tra_can_cu_ton_tai` (rules.py
    # và checklist.py, Task 2/3) tự đối chiếu với `provisions.duong_dan` thật.
    # MỌI loại văn bản có checklist, không riêng hdld: một mẫu mới bịa can_cu
    # phải chết ở đây, lúc khởi động, chứ không lọt tới người dùng.
    for loai in sorted(soan_thao_graph.cac_loai()):
        rules, checklist, _ = soan_thao_graph.requirements(loai)
        rules_svc.kiem_tra_can_cu_ton_tai(rules)
        checklist_svc.kiem_tra_can_cu_ton_tai(checklist)
    yield
    print("Shutting down...")


app = FastAPI(
    title="KLAW API",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

# 2 MB. Mọi payload HỢP LỆ nhỏ hơn thế rất nhiều: `SoatRequest.text` tối đa
# 500k ký tự, còn `/tra-cuu.query` và `facts` của `/soan-thao` thì bé.
BODY_TOI_DA = 2 * 1024 * 1024
# Ngoại lệ DUY NHẤT: `POST /tai-lieu` mang chính tệp, nên trần của nó là trần của
# tệp (`tai_lieu.TRAN_BYTE`, 20 MB — quyết định 2026-09-26). Khớp đúng phương
# thức + đường, không theo tiền tố: `/tai-lieu/{id}/huy` vẫn 2 MB.
TRAN_RIENG = {("POST", "/api/v1/tai-lieu"): TRAN_BYTE}


class GioiHanKichThuoc:
    """Từ chối request quá lớn TRƯỚC khi đọc một byte thân nào.

    Đo được trước khi có lớp này: gửi 50 MB tới `POST /api/v1/soat` nhận **422
    kèm phản hồi 50,00 MB** — handler mặc định cho `RequestValidationError` trả
    nguyên `input`. Kẻ gọi biến mỗi byte upload thành một byte download, không
    tốn một lượt LLM nào và không để lại một dòng `traces` nào để đếm.

    Middleware ASGI thuần, KHÔNG `BaseHTTPMiddleware`: cái sau đệm response và
    đã biết là làm hỏng SSE — mà `/tra-cuu/luong` chính là SSE.

    Thêm TRƯỚC `CORSMiddleware` để CORS bọc NGOÀI (Starlette dựng ngăn xếp theo
    thứ tự ngược: cái thêm sau nằm ngoài cùng). Nếu không, 413 trả về không
    mang header CORS và trình duyệt không đọc nổi lý do bị từ chối.
    """

    def __init__(self, app, toi_da: int = BODY_TOI_DA) -> None:
        self.app = app
        self.toi_da = toi_da

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        h = Headers(scope=scope)
        toi_da = TRAN_RIENG.get((scope["method"], scope["path"]), self.toi_da)
        # `chunked` là cách DUY NHẤT gửi thân mà không khai `Content-Length`
        # trong HTTP/1.1 — tức cách duy nhất đi vòng qua phép kiểm dưới đây.
        # 411 là mã đúng cho "khai độ dài đi rồi hẵng gửi"; không client hợp lệ
        # nào của dự án dùng chunked (FE gửi JSON qua `fetch`, luôn có độ dài).
        if "chunked" in h.get("transfer-encoding", "").lower():
            return await self._tu_choi(
                scope, receive, send, 411,
                f"Cần khai Content-Length; tối đa {toi_da // (1024 * 1024)} MB.",
            )
        cl = h.get("content-length")
        if cl and cl.isdigit() and int(cl) > toi_da:
            return await self._tu_choi(
                scope, receive, send, 413,
                f"Thân yêu cầu vượt {toi_da // (1024 * 1024)} MB.",
            )
        return await self.app(scope, receive, send)

    async def _tu_choi(self, scope, receive, send, ma: int, ly_do: str):
        # KHÔNG đọc thân trước khi trả lời: đọc nó là làm đúng việc mà lớp này
        # tồn tại để tránh.
        await JSONResponse({"detail": ly_do}, status_code=ma)(scope, receive, send)


LOI_MAY_CHU_KHONG_XU_LY_DUOC = "Có lỗi ở máy chủ, vui lòng thử lại sau."


class BatLoiMayChu:
    """Bắt MỌI exception chưa handler nào xử lý, trả JSON 500 KÈM header CORS.

    `ServerErrorMiddleware` của Starlette luôn là middleware NGOÀI CÙNG
    (`Starlette.build_middleware_stack`: bất cứ handler đăng ký cho
    `Exception`/500 nào — kể cả qua `@app.exception_handler(Exception)` —
    đều bị gộp thành `error_handler` của CHÍNH lớp đó, không đi vào
    `ExceptionMiddleware` như mọi handler khác). Vì lớp đó nằm NGOÀI
    `CORSMiddleware`, response nó tự dựng đi qua `send` GỐC (chưa bọc CORS)
    — nên cú pháp FastAPI hay dùng, `@app.exception_handler(Exception)`,
    KHÔNG sửa được lỗi thiếu header CORS mà bug này mô tả. Middleware NÀY,
    thêm bằng `app.add_middleware` NẰM TRONG CORS (như `GioiHanKichThuoc`),
    là cách duy nhất bắt exception TRƯỚC khi nó thoát ra tới lớp đó.

    `HTTPException`/`RequestValidationError` KHÔNG bao giờ tới được đây:
    `ExceptionMiddleware` (nằm trong cùng, sát router) đã tự giải quyết
    chúng thành response bình thường trước khi có dịp lan ra ngoài — nên lớp
    này không cần, và không được, tự phân biệt loại exception.

    CHỈ nuốt exception (không `raise` lại) khi response CHƯA bắt đầu gửi
    (`da_gui` còn `False`) — lúc đó đổi hẳn sang một 500 JSON là an toàn, vì
    chưa byte nào rời khỏi server. Nếu response ĐÃ bắt đầu (`da_gui` là
    `True`, ca `/tra-cuu/luong` SSE giữa chừng), header/status đã gửi rồi —
    không còn cách nào "sửa" thành 500 nữa, và im lặng trả về coi như thành
    công còn tệ hơn: response bị bỏ dở, không frame `more_body=False` cuối
    cùng nào được gửi, client treo chờ một luồng không bao giờ đóng. Vẫn phải
    `raise` lại ở ca đó, ĐÚNG hành vi `ServerErrorMiddleware` (nó luôn ném lại
    exception để server ASGI đóng kết nối) — middleware này chỉ đứng vào
    GIỮA để phần response CHƯA gửi có cơ hội mang header CORS, không phải để
    đổi cách một luồng ĐÃ gửi dở kết thúc. Log thủ công dưới đây giữ traceback
    ở mức ERROR, cùng độ ồn hôm nay, ở CẢ hai nhánh.

    `detail` là MỘT câu cố định, không mang `str(exc)`/traceback: khác 500 của
    `/tra-cuu` (routes.py, cố ý lộ TÊN loại lỗi cho một endpoint đã biết rõ
    những loại lỗi có thể tới), lớp NÀY bắt exception BẤT KỲ ở BẤT KỲ route
    nào — không có cách nào đảm bảo một ngoại lệ tương lai không mang dữ liệu
    nhạy cảm trong message của nó.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        da_gui = False

        async def _send(message):
            nonlocal da_gui
            if message["type"] == "http.response.start":
                da_gui = True
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception:
            logger.exception("Lỗi máy chủ không xử lý được")
            if da_gui:
                # Response đã gửi dở (vd SSE giữa chừng) — không còn cách nào
                # đổi thành 500 nữa. Ném lại để server ASGI đóng kết nối, đúng
                # hành vi `ServerErrorMiddleware`, thay vì trả về "thành công"
                # với một luồng không bao giờ đóng.
                raise
            await JSONResponse(
                {"detail": LOI_MAY_CHU_KHONG_XU_LY_DUOC}, status_code=500
            )(scope, receive, send)


app.add_middleware(GioiHanKichThuoc)

# TRƯỚC CORSMiddleware (như GioiHanKichThuoc ở trên) để CORS bọc NGOÀI cả hai —
# xem docstring BatLoiMayChu.
app.add_middleware(BatLoiMayChu)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
# Router tách theo nhóm chức năng (Pha 2): `routes.py` đã ở ngưỡng độ dài
# tối đa của dự án, và tìm kiếm / hiệu lực / tài khoản là ba mối bận tâm
# khác nhau. Cùng prefix nên hợp đồng URL không đổi.
app.include_router(router_tim_kiem, prefix="/api/v1")
app.include_router(router_van_ban, prefix="/api/v1")
app.include_router(router_tai_khoan, prefix="/api/v1")
app.include_router(router_luong, prefix="/api/v1")
app.include_router(router_hoi_thoai, prefix="/api/v1")
app.include_router(router_ban_thao, prefix="/api/v1")
app.include_router(router_tai_lieu, prefix="/api/v1")
app.include_router(router_admin, prefix="/api/v1")


@app.exception_handler(RequestValidationError)
async def loi_xac_thuc_khong_phan_chieu(request, exc: RequestValidationError):
    """422 nói SAI Ở ĐÂU, không đọc lại thứ người dùng vừa gửi.

    Handler mặc định của FastAPI đưa nguyên khoá `input` của mỗi lỗi vào phản
    hồi. Hai hệ quả: một request 50 MB bị từ chối vẫn tốn 50 MB băng thông ra
    (đo được), và ở mọi kích thước, dữ liệu người dùng đi vòng lại qua log của
    mọi proxy trên đường. `loc`/`msg`/`type` là đủ để sửa một request sai.
    """
    return JSONResponse(
        status_code=422,
        content={
            "detail": jsonable_encoder(
                [{k: v for k, v in e.items() if k != "input"} for e in exc.errors()]
            )
        },
    )


@app.get("/health")
async def health():
    # KHÔNG trả `app_env` (FastAPI review, MEDIUM): một endpoint không xác
    # thực không nên tiết lộ deployment đang chạy môi trường nào trước khi
    # Plan 4 deploy thật.
    return {"status": "ok"}
