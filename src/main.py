from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from src.agents import graph_soan_thao as soan_thao_graph
from src.api.routes import router
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
