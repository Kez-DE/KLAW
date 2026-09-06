"""C2 — production KHÔNG được khởi động khi không có cách nào biết người gọi là ai.

`cong_bao_ve` coi `nguoi is None` là hợp lệ ở cả ba endpoint tiêu tiền
(`POST /tra-cuu`, `POST /tra-cuu/luong`, `POST /soan-thao`): `xac_thuc_nguoi_goi`
trả None khi Supabase chưa cấu hình, và hàm trả None đó là một đường ĐI TIẾP,
không phải một đường từ chối. Cả `KLAW_API_KEY` lẫn `KLAW_SUPABASE_URL` đều mặc
định RỖNG = MỞ, nên quên đặt một biến không phát ra tín hiệu nào.

Đo được trước khi vá: 768/768 dòng `traces` của `/tra-cuu` có `user_sub` NULL, và
bảng `users` có 0 dòng — tức hạn mức tháng (đếm chính cột `user_sub`) chưa từng
trừ của ai một lượt nào.

Guard nằm ở `lifespan`, KHÔNG phải một dòng runbook: một dòng runbook là thứ
người ta đọc sau khi sự cố đã xảy ra.
"""

import pytest

from src.config import Settings
from src.main import app, lifespan


@pytest.fixture
def cai_dat(monkeypatch):
    def dat(**kw):
        import src.main as main

        s = Settings(_env_file=None, **kw)
        monkeypatch.setattr(main, "get_settings", lambda: s)
        return s

    return dat


@pytest.fixture
def bo_qua_can_cu(monkeypatch):
    """Vô hiệu phần lifespan CẦN POSTGRES, để test chạy được ở CI không có DB.

    KHÔNG dùng cho ca production-thiếu-danh-tính: ca đó phải nổ TRƯỚC khi chạm
    Postgres, và việc nó nổ mà không cần fixture này chính là bằng chứng guard
    đứng đúng chỗ — trước, chứ không phải sau, phần khởi động đắt tiền.
    """
    import src.main as main

    monkeypatch.setattr(main.db_svc, "run_migrations", lambda *a, **kw: [])
    monkeypatch.setattr(main.soan_thao_graph, "requirements", lambda loai: ([], [], []))
    monkeypatch.setattr(main.rules_svc, "kiem_tra_can_cu_ton_tai", lambda *a: None)
    monkeypatch.setattr(main.checklist_svc, "kiem_tra_can_cu_ton_tai", lambda *a: None)


async def test_production_KHONG_co_api_key_lan_supabase_thi_TU_CHOI_khoi_dong(cai_dat):
    """Không fixture `bo_qua_can_cu`: nếu guard nằm sau phần đọc Postgres thì
    test này đỏ vì `OperationalError`, không phải `RuntimeError` — tức nó cũng
    khoá luôn VỊ TRÍ của guard, không chỉ sự tồn tại của nó."""
    cai_dat(app_env="production", api_key="", supabase_url="")
    with pytest.raises(RuntimeError, match="KLAW_API_KEY|KLAW_SUPABASE_URL"):
        async with lifespan(app):
            pass


async def test_production_co_api_key_thi_khoi_dong_duoc(cai_dat, bo_qua_can_cu):
    cai_dat(app_env="production", api_key="khoa-that", supabase_url="")
    async with lifespan(app):
        pass


async def test_production_co_supabase_thi_khoi_dong_duoc(cai_dat, bo_qua_can_cu):
    cai_dat(app_env="production", api_key="", supabase_url="https://abc.supabase.co")
    async with lifespan(app):
        pass


async def test_development_van_mo_toang_duoc(cai_dat, bo_qua_can_cu):
    """Dev local và `eval/run.py` chạy hàng trăm lượt không có tài khoản nào —
    guard chỉ chặn `production`, đúng phạm vi mà biến `app_env` tồn tại để phân."""
    cai_dat(app_env="development", api_key="", supabase_url="")
    async with lifespan(app):
        pass


async def test_lifespan_ap_migration_019_truoc_khi_kiem_can_cu(cai_dat, bo_qua_can_cu, monkeypatch):
    """Migration 019 (`link_vbpl`/`link_chinhphu`/`link_tvpl`) phải chạy ở
    lifespan: `graph_tra_cuu.py` SELECT ba cột này VÔ ĐIỀU KIỆN trên đường
    nóng của mọi câu trả lời có trích dẫn, và trước bản vá này không caller
    nào trong `src/` gọi `run_migrations` — một DB chưa áp 019 làm mọi lượt
    `/tra-cuu` có căn cứ nổ `UndefinedColumn` (Important A, final review
    2026-09-06)."""
    import src.main as main

    cai_dat(app_env="development", api_key="", supabase_url="")
    goi: list[str | None] = []
    monkeypatch.setattr(main.db_svc, "run_migrations", lambda chi=None: goi.append(chi) or [])
    async with lifespan(app):
        pass
    assert goi == ["019"]
