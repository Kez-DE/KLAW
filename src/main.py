from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException

from src.agents import graph_soan_thao as soan_thao_graph
from src.api.routes import router
from src.api.routes_luong import router as router_luong
from src.api.routes_tai_khoan import router as router_tai_khoan
from src.api.routes_tim_kiem import router as router_tim_kiem
from src.api.routes_van_ban import router as router_van_ban
from src.config import get_settings
from src.services import checklist as checklist_svc
from src.services import rules as rules_svc


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
    # Task 5, ràng buộc #2: kiểm can_cu LÚC KHỞI ĐỘNG, không phải lúc người
    # dùng gọi /soan-thao hay /soat. Một can_cu chết (rule hoặc mục checklist
    # trích dẫn điều luật không tồn tại) phải làm app fail nhanh ngay đây —
    # không nổ giữa lúc người dùng đang chờ. `kiem_tra_can_cu_ton_tai` (rules.py
    # và checklist.py, Task 2/3) tự đối chiếu với `provisions.duong_dan` thật.
    rules, checklist, _ = soan_thao_graph.requirements()
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
        # `chunked` là cách DUY NHẤT gửi thân mà không khai `Content-Length`
        # trong HTTP/1.1 — tức cách duy nhất đi vòng qua phép kiểm dưới đây.
        # 411 là mã đúng cho "khai độ dài đi rồi hẵng gửi"; không client hợp lệ
        # nào của dự án dùng chunked (FE gửi JSON qua `fetch`, luôn có độ dài).
        if "chunked" in h.get("transfer-encoding", "").lower():
            return await self._tu_choi(
                scope, receive, send, 411,
                f"Cần khai Content-Length; tối đa {self.toi_da // (1024 * 1024)} MB.",
            )
        cl = h.get("content-length")
        if cl and cl.isdigit() and int(cl) > self.toi_da:
            return await self._tu_choi(
                scope, receive, send, 413,
                f"Thân yêu cầu vượt {self.toi_da // (1024 * 1024)} MB.",
            )
        return await self.app(scope, receive, send)

    async def _tu_choi(self, scope, receive, send, ma: int, ly_do: str):
        # KHÔNG đọc thân trước khi trả lời: đọc nó là làm đúng việc mà lớp này
        # tồn tại để tránh.
        await JSONResponse({"detail": ly_do}, status_code=ma)(scope, receive, send)


app.add_middleware(GioiHanKichThuoc)

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


# Static frontend (Vite build output). Mounted LAST — a StaticFiles mount at
# "/" is a catch-all; every /api/* and /health route above must already be
# registered or this would shadow them.
STATIC = Path(__file__).parent / "static"

# Tuyến do router phía client giữ. Chúng không tương ứng file nào trên đĩa, nên
# `StaticFiles` trần ném 404 thật — bấm F5, mở bookmark, hay bấm link được chia
# sẻ đều ra trang lỗi. Danh sách chép từ `frontend/src/App.tsx`; thêm tuyến mới
# ở đó thì thêm ở đây.
TUYEN_CLIENT = frozenset(
    {"/", "/tra-cuu", "/soan-thao", "/soat", "/huong-dan", "/pham-vi", "/mien-tru"}
)
TIEN_TO_CLIENT = ("/van-ban/",)


class StaticSPA(StaticFiles):
    """Trả `index.html` cho tuyến phía client, nhưng KHÔNG nói dối mã trạng thái.

    Tuyến có thật → 200. Đường dẫn không tồn tại → **404 kèm HTML**, để React
    dựng được trang 404 tử tế mà máy tìm kiếm vẫn đọc đúng tín hiệu. Trả 200 cho
    mọi thứ là nói dối với crawler; trả 404 rỗng là nói dối với người dùng.

    Asset thiếu vẫn hỏng RÕ RÀNG: trả `index.html` cho một file `.js` không tồn
    tại làm trình duyệt nuốt HTML như JavaScript và báo lỗi cú pháp khó hiểu.
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            if e.status_code != 404:
                raise
            duong_dan = "/" + path.lstrip("/")
            if "." in Path(path).name:  # trông như một tệp — để nó hỏng rõ ràng
                raise
            la_tuyen = duong_dan in TUYEN_CLIENT or duong_dan.startswith(TIEN_TO_CLIENT)
            return FileResponse(
                STATIC / "index.html", status_code=200 if la_tuyen else 404
            )


if STATIC.exists():
    app.mount("/", StaticSPA(directory=STATIC, html=True), name="static")
