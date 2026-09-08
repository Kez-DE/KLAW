# CMS quản lý tài khoản KLAW trên Payload — kế hoạch thi công (gói 2B)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một trang quản trị Payload chạy độc lập (mã `cms/`, cổng 3001, database `klaw_cms`, đăng nhập riêng) để tìm, xem, duyệt nâng gói, đặt gói, khoá và mở khoá các tài khoản đã đăng nhập vào KLAW; toàn bộ thay đổi dữ liệu đi qua API `/admin/*` của KLAW, được ghi nhật ký bất biến và báo hai chiều.

**Architecture:** KLAW (FastAPI) giữ quyền sở hữu mọi bảng tài khoản và mở router `/admin/*` sau khoá dịch vụ `KLAW_ADMIN_API_KEY`; ba hàm trong `nang_goi.py` là đường duy nhất đổi `users.plan`. CMS là Payload 3.88 + Next 15 với hai collection riêng (`admins`, `nhat_ky_cms`), một proxy có allowlist chạy phía máy chủ gắn khoá và danh tính admin, và bốn view tuỳ biến gọi proxy đó. Thông báo là bảng `thong_bao` của KLAW, hai người đọc (admin qua CMS, người dùng qua frontend), đẩy nhanh bằng SSE.

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy `text()` · Postgres (docker `klaw-db-1`) · pytest · Payload `3.88.0` · Next 15 · React 19 · pnpm 9 · vitest · TanStack Start (frontend KLAW, npm).

**Spec:** `docs/superpowers/specs/2026-09-08-cms-quan-ly-tai-khoan-design.md` — plan lập luận từ spec; implementer đọc cả hai. Mọi số hiệu `§` dưới đây trỏ vào spec.

## Global Constraints

- **Payload đúng `3.88.0`** cho `payload`, `@payloadcms/next`, `@payloadcms/db-postgres`, `@payloadcms/ui`, `@payloadcms/translations`; không caret, không canary (§0.1, §6.1).
- **CMS dùng database riêng `klaw_cms`**; không đặt `schemaName`; không có chuỗi kết nối nào tới database `klaw` trong `cms/` (§0.2, §4.2).
- **Một đường đổi gói:** ngoài `src/services/nang_goi.py`, không file nào trong `src/` chứa `UPDATE users SET plan` (§4.1). Có test grep.
- **Nhật ký bất biến:** không file nào trong `src/` chứa `UPDATE nhat_ky_quan_tri` hay `DELETE FROM nhat_ky_quan_tri` (§5.1). Có test grep.
- **Fail-closed:** `KLAW_ADMIN_API_KEY` rỗng → mọi request `/admin/*` nhận 503 (§4.1).
- **Không endpoint nào trả nội dung `hoi_thoai`/`luot_hoi_thoai` cho admin** (§5.3).
- **Chữ hiển thị** (cả KLAW và CMS): không "hệ thống", "không diễn giải", "chưa đủ căn cứ", "truy hồi", "database", "để bạn tự đối chiếu", "máy chủ trả về"; xưng "tôi"; gói `pro` hiện "Cá nhân", `free` hiện "Miễn phí" (§6.5).
- **Cổng:** KLAW API 8000, KLAW frontend 3000 (npm), CMS 3001 (pnpm). `cms/` không nằm trong workspace của `frontend/`.
- **Quy ước repo (memory `klaw-harness-frictions`):** không chạy `make check`/`make format`; dùng `ruff check src/ tests/` + `ruff format --check <file đã sửa>` + pytest có mục tiêu. Không stage các file bẩn có sẵn của chủ dự án (`docs/guide/*`, `scripts/log_*.py`, `README_boilerplate.md`, `src/services/checklist.py`, `tests/test_services/test_moi_mau.py`, `config/checklist_don_xin_nghi_viec.yaml`, `eval/datasets/golden_qa_candidates.yaml`, `.impeccable/`, `.tham-dinh-shots/`). Test cần Postgres đánh dấu `pytest.mark.integration`; CI chạy `-m "not integration and not pending_review"`.
- **Bộ test rộng để so trước/sau:** `python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py` (một test đỏ sẵn ở `test_moi_mau.py` không phải hồi quy).
- **Worktree** (§12): giai đoạn 1 và 2 chạy song song ở hai worktree sau Task 1; worktree cần symlink `.venv`, `data/raw`, `frontend/node_modules`; `.env.local` chỉ có ở checkout chính.
- **GateGuard:** câu Bash đầu, file mới và lệnh có chữ phá huỷ cần nêu facts rồi thử lại; heredoc chứa chữ SQL phá huỷ bị chặn — viết file bằng Write rồi `cat`.
- **Commit** conventional commits tiếng Anh; mỗi task một hoặc vài commit nhỏ.

---

## Bản đồ file

**KLAW (giai đoạn 1 và 3)**

| File | Việc | Task |
|---|---|---|
| `migrations/022_quan_tri.sql` (mới) | `thong_bao`, `nhat_ky_quan_tri`, cột mới của `yeu_cau_nang_goi` và `users` | 1 |
| `src/main.py` | `lifespan` áp `"022"`; gắn `router_admin` | 1, 7 |
| `src/config.py` | `admin_api_key` | 1 |
| `src/models/schemas.py` | `ly_do`, `bi_khoa`, các model `/admin` | 1 |
| `src/services/nhat_ky.py` (mới) | `ghi`, `danh_sach`, `csv`, `ket_noi` | 2 |
| `src/services/thong_bao.py` (mới) | `ghi`, `vo_hieu`, `danh_sach`, `dem_chua_doc`, `danh_dau_da_doc` | 3 |
| `src/services/nang_goi.py` | `duyet`, `tu_choi`, `dat_goi`, `thu_hoi`, `ly_do` ở `moi_nhat`, thông báo admin ở `tao_yeu_cau` | 4, 5, 16 |
| `src/services/tai_khoan_qt.py` (mới) | `khoa`, `mo_khoa`, `tim`, `chi_tiet`, `tong_quan`, `danh_sach_goi` | 5, 6 |
| `src/services/bao_ve.py` | `kiem_khoa`, `ghi_nhan_va_kiem_khoa`, `kiem_admin_key`, `LOI_TAI_KHOAN_KHOA` | 5, 7 |
| `src/api/routes_tai_khoan.py` | `bi_khoa` ở `/han-muc`; `/thong-bao*` | 5, 16 |
| `src/api/routes_admin.py` (mới) | router `/admin` | 7, 16 |
| `src/api/luong_thong_bao.py` (mới) | generator SSE hộp thư | 16 |
| `tests/test_services/test_migration_022.py`, `test_nhat_ky.py`, `test_thong_bao.py`, `test_nang_goi_duyet.py`, `test_tai_khoan_qt.py` (mới) | test dịch vụ | 1–6 |
| `tests/test_api/test_tai_khoan_khoa.py`, `test_admin_cong.py`, `test_admin_routes.py`, `test_thong_bao_api.py` (mới) | test endpoint | 5, 7, 16 |

**CMS (giai đoạn 2 và 3)** — toàn bộ dưới `cms/`

| File | Việc | Task |
|---|---|---|
| `package.json`, `payload.config.ts`, `next.config.mjs`, `tsconfig.json`, `vitest.config.ts`, `.env.example`, `.gitignore` | scaffold, ghim 3.88.0 | 8 |
| `src/collections/Admins.ts`, `src/access/vaiTro.ts` | auth, hai vai trò, guard admin cuối | 8 |
| `src/collections/NhatKyCms.ts`, `src/hooks/nhatKyCms.ts`, `src/hooks/exposeErrorReason.ts` | nhật ký CMS, đăng nhập | 9 |
| `src/lib/allowlist.ts`, `src/lib/klaw-client.ts`, `src/endpoints/klaw.ts` | proxy | 10 |
| `src/lib/goi-klaw.ts`, `src/lib/hien-thi.ts`, `src/components/ui/*.tsx`, `src/components/DieuHuong.tsx`, `src/views/TongQuan.tsx` | khung giao diện | 11 |
| `src/views/YeuCau.tsx` + `YeuCauClient.tsx` | duyệt / từ chối | 12 |
| `src/views/TaiKhoan.tsx` + `TaiKhoanClient.tsx` | tìm, chi tiết, hành động | 13 |
| `src/views/NhatKy.tsx` + `NhatKyClient.tsx`, `scripts/start.sh`, `README.md`, `.github/workflows/ci.yml` | nhật ký, vận hành, CI | 14 |
| `src/components/ChuongThongBao/{index.tsx,bell.ts,index.scss}` | chuông | 17 |
| `tests/*.spec.ts`, `tests/helpers/payload.ts` | vitest | 8–14, 17 |

**Frontend KLAW (giai đoạn 2 và 3)** — dưới `frontend/src`

| File | Việc | Task |
|---|---|---|
| `lib/klaw.ts` | `ly_do`, `bi_khoa`, `ThongBao` | 15, 18 |
| `components/tai-khoan/ModalNangGoi.tsx` | hiện lý do từ chối | 15 |
| `components/tai-khoan/TheTaiKhoanKhoa.tsx` (mới), `routes/dung-thu.tsx` | thẻ khoá | 15 |
| `hooks/use-thong-bao.ts`, `lib/thong-bao.ts`, `components/tai-khoan/ChuongThongBao.tsx`, `components/app/AppShell.tsx`, `scripts/kiem-thong-bao.ts` | chuông người dùng | 18 |

---

## Giai đoạn 1 — KLAW backend

### Task 1: Hợp đồng — migration 022, cấu hình, model

**Files:**
- Create: `migrations/022_quan_tri.sql`
- Modify: `src/main.py:75` (`for mig in ("019", "020", "021")`)
- Modify: `src/config.py` (sau khối `supabase_url`, ~dòng 223)
- Modify: `src/models/schemas.py` (`HanMucResponse` ~751, `YeuCauNangGoiOut` ~864, thêm khối `/admin` ở cuối file)
- Test: `tests/test_services/test_migration_022.py`

**Interfaces:**
- Produces: bảng `thong_bao`, `nhat_ky_quan_tri`; cột `yeu_cau_nang_goi.nguon|tham_chieu|ly_do`, `xu_ly_boi TEXT`; cột `users.khoa_luc|khoa_ly_do`. `Settings.admin_api_key: str`. Pydantic: `YeuCauNangGoiOut.ly_do: str | None`, `HanMucResponse.bi_khoa: bool`, và các model admin ở bước 4 — mọi task sau import đúng tên này.

- [ ] **Bước 1: Viết test migration idempotent (đỏ)**

```python
# tests/test_services/test_migration_022.py
"""Migration 022 (spec 2B §5.1): chạy hai lần xanh, đổi kiểu `xu_ly_boi` sang text."""

import pytest
from sqlalchemy import text

from src.services import db
from src.services.db import get_engine

pytestmark = pytest.mark.integration

_KIEU = text(
    "SELECT data_type FROM information_schema.columns"
    " WHERE table_name = 'yeu_cau_nang_goi' AND column_name = 'xu_ly_boi'"
)
_COT = text("SELECT column_name FROM information_schema.columns WHERE table_name = :bang ORDER BY column_name")


def test_022_chay_hai_lan_van_xanh_va_doi_kieu_xu_ly_boi():
    assert db.run_migrations("022") == ["022_quan_tri.sql"]
    assert db.run_migrations("022") == ["022_quan_tri.sql"]  # IF NOT EXISTS + ALTER TYPE cùng kiểu
    with get_engine().connect() as c:
        assert c.execute(_KIEU).scalar_one() == "text"
        cot_users = {r[0] for r in c.execute(_COT, {"bang": "users"})}
        cot_yc = {r[0] for r in c.execute(_COT, {"bang": "yeu_cau_nang_goi"})}
        cot_tb = {r[0] for r in c.execute(_COT, {"bang": "thong_bao"})}
        cot_nk = {r[0] for r in c.execute(_COT, {"bang": "nhat_ky_quan_tri"})}
    assert {"khoa_luc", "khoa_ly_do"} <= cot_users
    assert {"nguon", "tham_chieu", "ly_do"} <= cot_yc
    assert {"nguoi_nhan", "loai", "khoa_gom", "da_doc", "het_hieu_luc"} <= cot_tb
    assert {"hanh_dong", "doi_tuong", "chi_tiet", "boi", "tac_nhan_loai", "ip"} <= cot_nk


def test_thong_bao_khoa_gom_chan_nhan_ban_khi_con_hieu_luc():
    chen = (
        "INSERT INTO thong_bao (nguoi_nhan, loai, tieu_de, noi_dung, duong_dan, khoa_gom)"
        " VALUES (NULL, 'yeu_cau_moi', 't', 'n', '/x', 'test:022')"
        " ON CONFLICT (khoa_gom) WHERE NOT het_hieu_luc DO NOTHING RETURNING id"
    )
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM thong_bao WHERE khoa_gom = 'test:022'"))
        assert c.execute(text(chen)).scalar_one_or_none() is not None
        assert c.execute(text(chen)).scalar_one_or_none() is None, "dòng thứ hai cùng khoa_gom phải bị nuốt"
        c.execute(text("DELETE FROM thong_bao WHERE khoa_gom = 'test:022'"))
```

- [ ] **Bước 2: Chạy test, xác nhận đỏ**

Run: `.venv/bin/python -m pytest tests/test_services/test_migration_022.py -q`
Expected: FAIL — `run_migrations("022")` trả `[]` (chưa có file).

- [ ] **Bước 3: Viết migration**

Viết bằng Write, không heredoc (GateGuard chặn heredoc có chữ `DELETE`/`DROP`):

```sql
-- migrations/022_quan_tri.sql
-- Spec 2026-09-08 cms-quan-ly-tai-khoan §5.1 — đường quản trị: thông báo, nhật ký,
-- idempotent theo tham_chieu, lý do từ chối, khoá tài khoản. Idempotent (IF NOT EXISTS;
-- ALTER TYPE text trên cột đã là text là no-op hợp lệ).

CREATE TABLE IF NOT EXISTS thong_bao (
  id           BIGSERIAL PRIMARY KEY,
  nguoi_nhan   UUID REFERENCES users(sub) ON DELETE CASCADE,   -- NULL = hộp thư admin
  loai         TEXT NOT NULL CHECK (loai IN (
                 'yeu_cau_moi', 'yeu_cau_duyet', 'yeu_cau_tu_choi',
                 'goi_dat_tay', 'goi_thu_hoi', 'tai_khoan_khoa', 'tai_khoan_mo')),
  tieu_de      TEXT NOT NULL,
  noi_dung     TEXT NOT NULL,
  duong_dan    TEXT NOT NULL,
  khoa_gom     TEXT NOT NULL,
  da_doc       BOOLEAN NOT NULL DEFAULT FALSE,
  het_hieu_luc BOOLEAN NOT NULL DEFAULT FALSE,
  tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_thong_bao_gom
  ON thong_bao (khoa_gom) WHERE NOT het_hieu_luc;
CREATE INDEX IF NOT EXISTS ix_thong_bao_nhan
  ON thong_bao (nguoi_nhan, da_doc, tao_luc DESC);

-- CHỈ GHI THÊM. Không đường nào trong src/ UPDATE hay DELETE bảng này (test grep).
CREATE TABLE IF NOT EXISTS nhat_ky_quan_tri (
  id             BIGSERIAL PRIMARY KEY,
  hanh_dong      TEXT NOT NULL,
  doi_tuong      UUID,
  chi_tiet       JSONB NOT NULL DEFAULT '{}'::jsonb,
  boi            TEXT NOT NULL,
  tac_nhan_loai  TEXT NOT NULL DEFAULT 'admin'
                 CHECK (tac_nhan_loai IN ('admin', 'tu_dong', 'thanh_toan')),
  ip             TEXT,
  tao_luc        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_tao_luc ON nhat_ky_quan_tri (tao_luc DESC);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_hanh_dong ON nhat_ky_quan_tri (hanh_dong, tao_luc DESC);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_doi_tuong ON nhat_ky_quan_tri (doi_tuong, tao_luc DESC);

ALTER TABLE yeu_cau_nang_goi
  ADD COLUMN IF NOT EXISTS nguon      TEXT CHECK (nguon IN ('admin', 'thanh_toan')),
  ADD COLUMN IF NOT EXISTS tham_chieu TEXT,
  ADD COLUMN IF NOT EXISTS ly_do      TEXT,
  ALTER COLUMN xu_ly_boi TYPE TEXT USING xu_ly_boi::text;   -- cột luôn NULL tới nay
CREATE UNIQUE INDEX IF NOT EXISTS ux_yeu_cau_tham_chieu
  ON yeu_cau_nang_goi (tham_chieu) WHERE tham_chieu IS NOT NULL;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS khoa_luc   TIMESTAMPTZ,   -- NULL = bình thường
  ADD COLUMN IF NOT EXISTS khoa_ly_do TEXT;
```

- [ ] **Bước 4: `lifespan`, `Settings`, schema**

`src/main.py` dòng 75: `for mig in ("019", "020", "021", "022"):`.

`src/config.py`, ngay sau khối `supabase_url` (giữ kiểu chú thích của file):

```python
    # ══ Đường quản trị (spec 2026-09-08 cms-quan-ly-tai-khoan §5.3) ═════════
    # Khoá dịch vụ RIÊNG cho router `/admin/*`, chỉ CMS giữ. RỖNG = router
    # `/admin` TỪ CHỐI TOÀN BỘ (503) — NGƯỢC quy ước của `api_key` (rỗng = mở),
    # và cố ý: một đường quản trị mở khi quên cấu hình hỏng nặng hơn một đường
    # quản trị đóng. Cổng công khai không đọc biến này.
    admin_api_key: str = Field(default="", validation_alias="KLAW_ADMIN_API_KEY")
```

`src/models/schemas.py`: thêm `bi_khoa: bool = False` vào `HanMucResponse` (sau `het_han_luc`); thêm `ly_do: str | None = None` vào `YeuCauNangGoiOut` (sau `xu_ly_luc`); thêm khối cuối file:

```python
# ══ /admin — đường quản trị (spec 2026-09-08 cms-quan-ly-tai-khoan §5.3) ═════════
class LyDoRequest(BaseModel):
    ly_do: str = Field(..., min_length=1, max_length=500)


class DatGoiRequest(BaseModel):
    plan: str = Field(..., min_length=1, max_length=32)
    so_ngay: int | None = Field(default=None, ge=1, le=3650)  # None + gói trả phí = vô thời hạn


class DaDocRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=200)


class KetQuaGoiOut(BaseModel):
    sub: str
    plan: str
    plan_het_han: datetime | None


class YeuCauAdminOut(BaseModel):
    id: int
    user_sub: str
    email: str | None
    loai: str
    goi_hien_tai: str
    goi_muon: str
    trang_thai: str
    tao_luc: datetime
    xu_ly_luc: datetime | None
    xu_ly_boi: str | None
    ly_do: str | None
    plan_hieu_luc: str
    khoa_luc: datetime | None


class DanhSachYeuCauOut(BaseModel):
    tong: int
    items: list[YeuCauAdminOut]


class TaiKhoanTomTatOut(BaseModel):
    sub: str
    email: str | None
    plan: str  # gói HIỆU LỰC
    plan_het_han: datetime | None
    khoa_luc: datetime | None
    tao_luc: datetime
    so_phien: int
    luot_30_ngay: int


class DanhSachTaiKhoanOut(BaseModel):
    tong: int
    items: list[TaiKhoanTomTatOut]


class TaiKhoanChiTietOut(HoSoResponse):
    sub: str
    khoa_luc: datetime | None
    khoa_ly_do: str | None
    yeu_cau: list[YeuCauNangGoiOut]


class NhatKyOut(BaseModel):
    id: int
    hanh_dong: str
    doi_tuong: str | None
    chi_tiet: dict
    boi: str
    tac_nhan_loai: str
    ip: str | None
    tao_luc: datetime


class DanhSachNhatKyOut(BaseModel):
    tong: int
    items: list[NhatKyOut]


class TongQuanOut(BaseModel):
    tong_tai_khoan: int
    dang_ca_nhan: int
    cho_duyet: int
    het_han_7_ngay: int
    moi_7_ngay: int
    dang_khoa: int
    hoi_dap_hom_nay: int


class GoiOut(BaseModel):
    ma: str
    ten: str
    han_muc: dict[str, int]


class DanhSachGoiOut(BaseModel):
    goi: list[GoiOut]
    goi_mac_dinh: str
    chu_ky_pro_ngay: int


class ThongBaoOut(BaseModel):
    id: int
    loai: str
    tieu_de: str
    noi_dung: str
    duong_dan: str
    da_doc: bool
    tao_luc: datetime


class DanhSachThongBaoOut(BaseModel):
    so_chua_doc: int
    items: list[ThongBaoOut]
```

- [ ] **Bước 5: Chạy test, xác nhận xanh; lint**

Run: `.venv/bin/python -m pytest tests/test_services/test_migration_022.py tests/test_api/test_tai_khoan.py tests/test_api/test_ho_so_nang_goi.py -q && .venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check src/config.py src/models/schemas.py tests/test_services/test_migration_022.py`
Expected: PASS; bộ test tài khoản hiện có vẫn xanh (`bi_khoa` và `ly_do` có mặc định nên không phá hình cũ).

- [ ] **Bước 6: Commit**

```bash
git add migrations/022_quan_tri.sql src/main.py src/config.py src/models/schemas.py tests/test_services/test_migration_022.py
git commit -m "feat(db): migration 022 for the admin path, admin API key setting and admin response models"
```

---

### Task 2: `nhat_ky.py` — nhật ký quản trị chỉ ghi thêm

**Files:**
- Create: `src/services/nhat_ky.py`
- Test: `tests/test_services/test_nhat_ky.py`

**Interfaces:**
- Produces:
  - `ket_noi(c: Connection | None)` — contextmanager: dùng transaction ngoài nếu có, không thì mở mới. `thong_bao.py` và `nang_goi.py` dùng chung.
  - `ghi(hanh_dong: str, *, doi_tuong: str | None, chi_tiet: dict, boi: str, tac_nhan_loai: str = "admin", ip: str | None = None, c: Connection | None = None) -> int` — trả `id`.
  - `danh_sach(*, tu: datetime | None, den: datetime | None, hanh_dong: str | None, doi_tuong: str | None, limit: int, offset: int) -> tuple[int, list[dict]]`
  - `csv(rows: list[dict]) -> str` — cột `id,tao_luc,hanh_dong,doi_tuong,boi,tac_nhan_loai,ip,chi_tiet`.

- [ ] **Bước 1: Test (đỏ)**

```python
# tests/test_services/test_nhat_ky.py
"""`nhat_ky` (spec 2B §5.2): ghi thêm, lọc, CSV — và bất biến KHÔNG sửa/xoá trong src/."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

from src.services import nhat_ky
from src.services.db import get_engine

BOI = "test-nhat-ky@klaw.local"


@pytest.fixture
def don():
    yield
    with get_engine().begin() as c:
        # Test là nơi DUY NHẤT được xoá — src/ thì không (test grep bên dưới).
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi = :b"), {"b": BOI})


@pytest.mark.integration
def test_ghi_tra_id_va_doc_lai_duoc(don):
    i = nhat_ky.ghi("thu_nghiem", doi_tuong=None, chi_tiet={"a": 1}, boi=BOI, ip="10.0.0.1")
    tong, rows = nhat_ky.danh_sach(tu=None, den=None, hanh_dong="thu_nghiem", doi_tuong=None, limit=10, offset=0)
    assert tong >= 1 and rows[0]["id"] == i and rows[0]["chi_tiet"] == {"a": 1} and rows[0]["ip"] == "10.0.0.1"


@pytest.mark.integration
def test_loc_theo_khoang_thoi_gian_va_doi_tuong(don):
    sub = str(uuid.uuid4())
    nhat_ky.ghi("thu_nghiem", doi_tuong=sub, chi_tiet={}, boi=BOI)
    tu = datetime.now(UTC) - timedelta(minutes=1)
    tong, rows = nhat_ky.danh_sach(tu=tu, den=None, hanh_dong=None, doi_tuong=sub, limit=10, offset=0)
    assert tong == 1 and rows[0]["doi_tuong"] == sub
    tong0, _ = nhat_ky.danh_sach(tu=None, den=tu, hanh_dong=None, doi_tuong=sub, limit=10, offset=0)
    assert tong0 == 0


@pytest.mark.integration
def test_ghi_trong_transaction_ngoai(don):
    with get_engine().begin() as c:
        nhat_ky.ghi("thu_nghiem", doi_tuong=None, chi_tiet={}, boi=BOI, c=c)
        assert c.execute(text("SELECT count(*) FROM nhat_ky_quan_tri WHERE boi = :b"), {"b": BOI}).scalar_one() == 1


def test_csv_dung_so_dong_va_tieu_de():
    rows = [
        {
            "id": 1, "tao_luc": datetime(2026, 9, 8, tzinfo=UTC), "hanh_dong": "x", "doi_tuong": None,
            "boi": "a", "tac_nhan_loai": "admin", "ip": None, "chi_tiet": {"k": "v, có dấu phẩy"},
        },
    ]
    dong = nhat_ky.csv(rows).strip().splitlines()
    assert dong[0] == "id,tao_luc,hanh_dong,doi_tuong,boi,tac_nhan_loai,ip,chi_tiet"
    assert len(dong) == 2 and '"' in dong[1], "JSON có dấu phẩy phải được bao ngoặc kép"


def test_src_khong_co_UPDATE_hay_DELETE_tren_nhat_ky_quan_tri():
    """Bất biến §5.1: bảng chỉ ghi thêm. Kiểm bằng grep, không bằng mắt."""
    mau = re.compile(r"(UPDATE\s+nhat_ky_quan_tri|DELETE\s+FROM\s+nhat_ky_quan_tri)", re.IGNORECASE)
    vi_pham = [str(p) for p in Path("src").rglob("*.py") if mau.search(p.read_text(encoding="utf-8"))]
    assert vi_pham == [], f"nhat_ky_quan_tri bị sửa/xoá ở: {vi_pham}"
```

- [ ] **Bước 2: Đỏ**

Run: `.venv/bin/python -m pytest tests/test_services/test_nhat_ky.py -q` → FAIL `ModuleNotFoundError: src.services.nhat_ky`.

- [ ] **Bước 3: Dịch vụ**

```python
# src/services/nhat_ky.py
"""Nhật ký quản trị — CHỈ GHI THÊM (spec 2026-09-08 cms-quan-ly-tai-khoan §5.1, §5.2).

Bản pháp lý của mọi thao tác admin. Module này không có hàm sửa hay xoá, và
`tests/test_services/test_nhat_ky.py` grep toàn `src/` để khẳng định không nơi
nào khác làm việc đó. Thông lệ lấy từ Audit Logs của OpenAI: bản ghi kiểm toán
phải bất biến thì mới dùng để điều tra được.
"""

import csv as _csv
import io
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.services.db import get_engine

COT_CSV = ["id", "tao_luc", "hanh_dong", "doi_tuong", "boi", "tac_nhan_loai", "ip", "chi_tiet"]

_SQL_GHI = text(
    "INSERT INTO nhat_ky_quan_tri (hanh_dong, doi_tuong, chi_tiet, boi, tac_nhan_loai, ip)"
    " VALUES (:hd, CAST(:dt AS uuid), CAST(:ct AS jsonb), :boi, :tn, :ip) RETURNING id"
)
_LOC = (
    " WHERE (CAST(:tu AS timestamptz) IS NULL OR tao_luc >= :tu)"
    " AND (CAST(:den AS timestamptz) IS NULL OR tao_luc < :den)"
    " AND (CAST(:hd AS text) IS NULL OR hanh_dong = :hd)"
    " AND (CAST(:dt AS text) IS NULL OR doi_tuong = CAST(:dt AS uuid))"
)
_SQL_DEM = text("SELECT count(*)::int FROM nhat_ky_quan_tri" + _LOC)
_SQL_DANH_SACH = text(
    "SELECT id, hanh_dong, doi_tuong::text AS doi_tuong, chi_tiet, boi, tac_nhan_loai, ip, tao_luc"
    " FROM nhat_ky_quan_tri" + _LOC + " ORDER BY tao_luc DESC, id DESC LIMIT :limit OFFSET :offset"
)


@contextmanager
def ket_noi(c: Connection | None) -> Iterator[Connection]:
    """Dùng transaction ngoài nếu có, không thì mở một transaction mới.

    `nang_goi.duyet` ghi nhật ký TRONG cùng transaction đổi gói: hoặc cả hai
    cùng commit, hoặc không gì cả — một gói được đổi mà không có dòng nhật ký
    là đúng lỗ hổng mà bảng này tồn tại để bịt.
    """
    if c is not None:
        yield c
        return
    with get_engine().begin() as moi:
        yield moi


def ghi(
    hanh_dong: str,
    *,
    doi_tuong: str | None,
    chi_tiet: dict,
    boi: str,
    tac_nhan_loai: str = "admin",
    ip: str | None = None,
    c: Connection | None = None,
) -> int:
    with ket_noi(c) as k:
        r = k.execute(
            _SQL_GHI,
            {
                "hd": hanh_dong,
                "dt": doi_tuong,
                "ct": json.dumps(chi_tiet, ensure_ascii=False),
                "boi": boi,
                "tn": tac_nhan_loai,
                "ip": ip,
            },
        ).scalar_one()
    return int(r)


def danh_sach(
    *,
    tu: datetime | None,
    den: datetime | None,
    hanh_dong: str | None,
    doi_tuong: str | None,
    limit: int,
    offset: int,
) -> tuple[int, list[dict]]:
    p = {"tu": tu, "den": den, "hd": hanh_dong, "dt": doi_tuong}
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_DEM, p).scalar_one())
        rows = [dict(r) for r in c.execute(_SQL_DANH_SACH, {**p, "limit": limit, "offset": offset}).mappings()]
    return tong, rows


def csv(rows: list[dict]) -> str:
    """CSV UTF-8 có tiêu đề; `chi_tiet` là JSON một dòng (csv tự bao ngoặc kép khi cần)."""
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow(COT_CSV)
    for r in rows:
        tl = r["tao_luc"]
        w.writerow(
            [
                r["id"],
                tl.isoformat() if isinstance(tl, datetime) else tl,
                r["hanh_dong"],
                r["doi_tuong"] or "",
                r["boi"],
                r["tac_nhan_loai"],
                r["ip"] or "",
                json.dumps(r["chi_tiet"], ensure_ascii=False),
            ]
        )
    return buf.getvalue()
```

`CAST(:tu AS timestamptz) IS NULL` thay cho `:tu IS NULL`: psycopg cần biết kiểu tham số khi giá trị là `None`, không có `CAST` thì lỗi "could not determine data type of parameter".

- [ ] **Bước 4: Xanh; lint**

Run: `.venv/bin/python -m pytest tests/test_services/test_nhat_ky.py -q && .venv/bin/ruff check src/services/nhat_ky.py tests/test_services/test_nhat_ky.py && .venv/bin/ruff format --check src/services/nhat_ky.py tests/test_services/test_nhat_ky.py`
Expected: 5 passed.

- [ ] **Bước 5: Commit**

```bash
git add src/services/nhat_ky.py tests/test_services/test_nhat_ky.py
git commit -m "feat(admin): append-only admin audit log service with CSV export and immutability test"
```

---

### Task 3: `thong_bao.py` — kho thông báo, hai người đọc

**Files:**
- Create: `src/services/thong_bao.py`
- Test: `tests/test_services/test_thong_bao.py`

**Interfaces:**
- Consumes: `nhat_ky.ket_noi`.
- Produces:
  - `KHOA_YEU_CAU = "yeu_cau:{sub}"`, `KHOA_KET_QUA = "ket_qua:{id}"`, `KHOA_TAI_KHOAN = "tai_khoan:{sub}:{loai}"` — dùng `.format(...)`.
  - `ghi(*, nguoi_nhan: str | None, loai: str, tieu_de: str, noi_dung: str, duong_dan: str, khoa_gom: str, c: Connection | None = None) -> int | None` — `None` khi đụng `khoa_gom` còn hiệu lực.
  - `vo_hieu(khoa_gom: str, c: Connection | None = None) -> int`
  - `danh_sach(nguoi_nhan: str | None, *, chi_chua_doc: bool = False, limit: int = 50) -> list[dict]`
  - `dem_chua_doc(nguoi_nhan: str | None) -> int`
  - `danh_dau_da_doc(ids: list[int], nguoi_nhan: str | None) -> int`
  - `nguoi_nhan is None` = hộp thư admin ở mọi hàm.

- [ ] **Bước 1: Test (đỏ)**

```python
# tests/test_services/test_thong_bao.py
"""`thong_bao` (spec 2B §5.2): gộp theo khoa_gom, hai hộp thư, đánh dấu đúng người."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, thong_bao
from src.services.db import get_engine

pytestmark = pytest.mark.integration


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "tb@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM thong_bao WHERE khoa_gom LIKE :k"), {"k": f"%{sub}%"})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def _ghi(nguoi_nhan, khoa):
    return thong_bao.ghi(
        nguoi_nhan=nguoi_nhan, loai="yeu_cau_moi", tieu_de="t", noi_dung="n", duong_dan="/x", khoa_gom=khoa
    )


def test_cung_khoa_gom_chi_mot_dong_khi_con_hieu_luc(nguoi):
    k = thong_bao.KHOA_YEU_CAU.format(sub=nguoi)
    assert _ghi(None, k) is not None
    assert _ghi(None, k) is None
    assert thong_bao.vo_hieu(k) == 1
    assert _ghi(None, k) is not None, "sau khi vô hiệu, cùng khoá được ghi lại"


def test_hai_hop_thu_khong_tron_va_dem_chua_doc(nguoi):
    _ghi(None, f"admin:{nguoi}")
    _ghi(nguoi, f"user:{nguoi}")
    assert any(r["khoa_gom"] == f"user:{nguoi}" for r in thong_bao.danh_sach(nguoi))
    assert not any(r["khoa_gom"] == f"user:{nguoi}" for r in thong_bao.danh_sach(None))
    assert thong_bao.dem_chua_doc(nguoi) == 1


def test_danh_dau_chi_dong_cua_dung_nguoi_nhan(nguoi):
    i = _ghi(nguoi, f"user:{nguoi}")
    j = _ghi(None, f"admin:{nguoi}")
    assert thong_bao.danh_dau_da_doc([i, j], nguoi) == 1, "id của hộp thư admin không đổi"
    assert thong_bao.dem_chua_doc(nguoi) == 0
    assert thong_bao.danh_sach(nguoi, chi_chua_doc=True) == []
    assert thong_bao.danh_dau_da_doc([], nguoi) == 0
```

- [ ] **Bước 2: Đỏ**

Run: `.venv/bin/python -m pytest tests/test_services/test_thong_bao.py -q` → FAIL `ModuleNotFoundError`.

- [ ] **Bước 3: Dịch vụ**

```python
# src/services/thong_bao.py
"""Thông báo — KLAW sở hữu, hai người đọc (spec 2026-09-08 cms-quan-ly-tai-khoan §5.2).

`nguoi_nhan is None` là hộp thư admin, tường minh ở mọi hàm; không dùng chuỗi
rỗng hay giá trị đặc biệt. `khoa_gom` + chỉ mục duy nhất (WHERE NOT het_hieu_luc)
chặn nhân bản: ghi lặp trong lúc chưa xử lý không tạo thêm dòng.
"""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.services.db import get_engine
from src.services.nhat_ky import ket_noi

KHOA_YEU_CAU = "yeu_cau:{sub}"
KHOA_KET_QUA = "ket_qua:{id}"
KHOA_TAI_KHOAN = "tai_khoan:{sub}:{loai}"

_SQL_GHI = text(
    "INSERT INTO thong_bao (nguoi_nhan, loai, tieu_de, noi_dung, duong_dan, khoa_gom)"
    " VALUES (CAST(:nn AS uuid), :loai, :td, :nd, :dd, :kg)"
    " ON CONFLICT (khoa_gom) WHERE NOT het_hieu_luc DO NOTHING RETURNING id"
)
_SQL_VO_HIEU = text("UPDATE thong_bao SET het_hieu_luc = TRUE WHERE khoa_gom = :kg AND NOT het_hieu_luc")
_NGUOI = " nguoi_nhan IS NOT DISTINCT FROM CAST(:nn AS uuid) AND NOT het_hieu_luc"
_SQL_DANH_SACH = text(
    "SELECT id, loai, tieu_de, noi_dung, duong_dan, khoa_gom, da_doc, tao_luc FROM thong_bao WHERE"
    + _NGUOI
    + " AND (NOT CAST(:chua_doc AS boolean) OR NOT da_doc) ORDER BY tao_luc DESC, id DESC LIMIT :limit"
)
_SQL_DEM = text("SELECT count(*)::int FROM thong_bao WHERE" + _NGUOI + " AND NOT da_doc")
_SQL_DA_DOC = text(
    "UPDATE thong_bao SET da_doc = TRUE WHERE id = ANY(CAST(:ids AS bigint[])) AND NOT da_doc AND" + _NGUOI
)


def ghi(
    *,
    nguoi_nhan: str | None,
    loai: str,
    tieu_de: str,
    noi_dung: str,
    duong_dan: str,
    khoa_gom: str,
    c: Connection | None = None,
) -> int | None:
    with ket_noi(c) as k:
        r = k.execute(
            _SQL_GHI,
            {"nn": nguoi_nhan, "loai": loai, "td": tieu_de, "nd": noi_dung, "dd": duong_dan, "kg": khoa_gom},
        ).scalar_one_or_none()
    return int(r) if r is not None else None


def vo_hieu(khoa_gom: str, c: Connection | None = None) -> int:
    with ket_noi(c) as k:
        return k.execute(_SQL_VO_HIEU, {"kg": khoa_gom}).rowcount


def danh_sach(nguoi_nhan: str | None, *, chi_chua_doc: bool = False, limit: int = 50) -> list[dict]:
    with get_engine().connect() as c:
        rows = c.execute(_SQL_DANH_SACH, {"nn": nguoi_nhan, "chua_doc": chi_chua_doc, "limit": limit}).mappings()
        return [dict(r) for r in rows]


def dem_chua_doc(nguoi_nhan: str | None) -> int:
    with get_engine().connect() as c:
        return int(c.execute(_SQL_DEM, {"nn": nguoi_nhan}).scalar_one())


def danh_dau_da_doc(ids: list[int], nguoi_nhan: str | None) -> int:
    """Chỉ đánh dấu dòng ĐÚNG người nhận; id của người khác không có tác dụng."""
    if not ids:
        return 0
    with get_engine().begin() as c:
        return c.execute(_SQL_DA_DOC, {"ids": ids, "nn": nguoi_nhan}).rowcount
```

- [ ] **Bước 4: Xanh; lint**

Run: `.venv/bin/python -m pytest tests/test_services/test_thong_bao.py -q && .venv/bin/ruff check src/services/thong_bao.py tests/test_services/test_thong_bao.py && .venv/bin/ruff format --check src/services/thong_bao.py`
Expected: 3 passed.

- [ ] **Bước 5: Commit**

```bash
git add src/services/thong_bao.py tests/test_services/test_thong_bao.py
git commit -m "feat(admin): notification store with per-recipient inbox and group-key dedupe"
```

---

### Task 4: `nang_goi.duyet` và `tu_choi` — đường nâng gói idempotent

**Files:**
- Modify: `src/services/nang_goi.py` (giữ `tao_yeu_cau`, `moi_nhat`, bốn ngoại lệ cũ)
- Test: `tests/test_services/test_nang_goi_duyet.py`

**Interfaces:**
- Consumes: `nhat_ky.ghi(..., c=)`, `thong_bao.ghi/vo_hieu(..., c=)`, `bao_ve._doc_han_muc()["chu_ky_pro_ngay"]`, `bao_ve.ten_goi`, `bao_ve.mui_gio`.
- Produces:
  - Ngoại lệ mới: `KhongTonTai(LookupError)`, `DaXuLy(ValueError)`, `TaiKhoanKhoa(ValueError)`, `KhongCoGiDeThuHoi(ValueError)` (Task 5 dùng ngoại lệ cuối).
  - `_han_moi(loai: str, het_han_cu: datetime | None, now: datetime, chu_ky_ngay: int) -> datetime` — thuần.
  - `duyet(yeu_cau_id: int, nguon: str, tham_chieu: str, boi: str, ip: str | None = None) -> dict` → `{"id", "trang_thai", "sub", "plan", "plan_het_han"}`.
  - `tu_choi(yeu_cau_id: int, ly_do: str, boi: str, ip: str | None = None) -> dict` → `{"id", "trang_thai", "ly_do"}`.
  - `moi_nhat(sub)` và `tao_yeu_cau` trả thêm khoá `ly_do`.
  - `_SQL_XU_LY`, `_SQL_DOI_GOI` (Task 5 tái dùng `_SQL_DOI_GOI`).

- [ ] **Bước 1: Test (đỏ)**

```python
# tests/test_services/test_nang_goi_duyet.py
"""`nang_goi.duyet`/`tu_choi` (spec 2B §5.2): idempotent theo tham_chieu, FOR UPDATE,
cộng dồn khi gia hạn, khoá thì không duyệt, lưu lý do từ chối."""

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from src.services import bao_ve, nang_goi, thong_bao
from src.services.db import get_engine

BOI = "admin-test@klaw.local"


def test_han_moi_nang_goi_tinh_tu_now_gia_han_cong_don():
    now = datetime(2026, 9, 8, 12, tzinfo=UTC)
    con = now + timedelta(days=10)
    assert nang_goi._han_moi("nang_goi", con, now, 30) == now + timedelta(days=30)
    assert nang_goi._han_moi("gia_han", con, now, 30) == con + timedelta(days=30)
    assert nang_goi._han_moi("gia_han", now - timedelta(days=1), now, 30) == now + timedelta(days=30)
    assert nang_goi._han_moi("gia_han", None, now, 30) == now + timedelta(days=30)


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "duyet@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(
            text("DELETE FROM thong_bao WHERE khoa_gom LIKE :k OR nguoi_nhan = CAST(:s AS uuid)"),
            {"k": f"%{sub}%", "s": sub},
        )
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi = :b"), {"b": BOI})
        c.execute(text("DELETE FROM yeu_cau_nang_goi WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def _goi(sub):
    with get_engine().connect() as c:
        return c.execute(text("SELECT plan, plan_het_han FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub}).one()


def _ngay_con(het):
    return (het - datetime.now(UTC)).total_seconds() / 86400


@pytest.mark.integration
def test_duyet_hai_lan_cung_tham_chieu_chi_cong_mot_chu_ky(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    r1 = nang_goi.duyet(yc["id"], "admin", f"yeu_cau:{yc['id']}", BOI, "10.0.0.1")
    r2 = nang_goi.duyet(yc["id"], "admin", f"yeu_cau:{yc['id']}", BOI, "10.0.0.1")
    assert r1["trang_thai"] == "da_duyet" and r2["plan_het_han"] == r1["plan_het_han"]
    plan, het = _goi(nguoi)
    assert plan == "pro" and 29 < _ngay_con(het) <= 30
    with get_engine().connect() as c:
        so_nk = c.execute(
            text("SELECT count(*) FROM nhat_ky_quan_tri WHERE boi = :b AND hanh_dong = 'duyet_yeu_cau'"), {"b": BOI}
        ).scalar_one()
    assert so_nk == 1, "lần hai không ghi thêm gì"
    assert thong_bao.dem_chua_doc(nguoi) == 1


@pytest.mark.integration
def test_gia_han_cong_don_tu_han_con_hieu_luc(nguoi):
    with get_engine().begin() as c:
        c.execute(
            text("UPDATE users SET plan='pro', plan_het_han = now() + interval '3 days' WHERE sub = CAST(:s AS uuid)"),
            {"s": nguoi},
        )
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    assert yc["loai"] == "gia_han"
    nang_goi.duyet(yc["id"], "admin", f"yeu_cau:{yc['id']}", BOI)
    assert 32.9 < _ngay_con(_goi(nguoi)[1]) <= 33


@pytest.mark.integration
def test_duyet_yeu_cau_da_xu_ly_bang_tham_chieu_khac_nem_DaXuLy(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    nang_goi.duyet(yc["id"], "admin", f"yeu_cau:{yc['id']}", BOI)
    with pytest.raises(nang_goi.DaXuLy):
        nang_goi.duyet(yc["id"], "thanh_toan", "gd:khac", BOI)
    with pytest.raises(nang_goi.KhongTonTai):
        nang_goi.duyet(10**9, "admin", "x", BOI)


@pytest.mark.integration
def test_hai_duyet_song_song_mot_thang_mot_DaXuLy(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    ket_qua: list[str] = []

    def chay(tc: str) -> None:
        try:
            nang_goi.duyet(yc["id"], "admin", tc, BOI)
            ket_qua.append("ok")
        except nang_goi.DaXuLy:
            ket_qua.append("da_xu_ly")

    luong = [threading.Thread(target=chay, args=(tc,)) for tc in ("a", "b")]
    for t in luong:
        t.start()
    for t in luong:
        t.join()
    assert sorted(ket_qua) == ["da_xu_ly", "ok"]
    assert 29 < _ngay_con(_goi(nguoi)[1]) <= 30, "chỉ một chu kỳ"


@pytest.mark.integration
def test_duyet_cho_nguoi_dang_khoa_nem_TaiKhoanKhoa(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    with get_engine().begin() as c:
        c.execute(text("UPDATE users SET khoa_luc = now(), khoa_ly_do = 'x' WHERE sub = CAST(:s AS uuid)"), {"s": nguoi})
    with pytest.raises(nang_goi.TaiKhoanKhoa):
        nang_goi.duyet(yc["id"], "admin", f"yeu_cau:{yc['id']}", BOI)
    assert _goi(nguoi)[0] == "free"


@pytest.mark.integration
def test_tu_choi_luu_ly_do_va_cho_gui_lai(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    r = nang_goi.tu_choi(yc["id"], "Chưa nhận được chuyển khoản.", BOI)
    assert r["trang_thai"] == "tu_choi" and r["ly_do"].startswith("Chưa")
    assert nang_goi.moi_nhat(nguoi)["ly_do"] == "Chưa nhận được chuyển khoản."
    assert _goi(nguoi)[0] == "free"
    assert nang_goi.tao_yeu_cau(nguoi, "pro")["trang_thai"] == "cho_duyet", "từ chối rồi thì gửi lại được"
    with pytest.raises(nang_goi.DaXuLy):
        nang_goi.tu_choi(yc["id"], "lại", BOI)
```

- [ ] **Bước 2: Đỏ**

Run: `.venv/bin/python -m pytest tests/test_services/test_nang_goi_duyet.py -q` → FAIL `AttributeError: module 'src.services.nang_goi' has no attribute '_han_moi'`.

- [ ] **Bước 3: Viết `duyet`, `tu_choi`, `_han_moi`; thêm `ly_do` vào `_SQL_TAO` và `_SQL_MOI_NHAT`**

Đổi docstring đầu file thành `"""Yêu cầu nâng/gia hạn gói và ĐƯỜNG ĐỔI GÓI DUY NHẤT (spec 2A §6.3, spec 2B §5.2)."""`. Sửa import:

```python
from src.services import nhat_ky, thong_bao
from src.services.bao_ve import _doc_han_muc, mui_gio, plan_hieu_luc_tu, ten_goi
```

Thêm `, ly_do` vào cuối danh sách cột trong `RETURNING` của `_SQL_TAO` và trong `SELECT` của `_SQL_MOI_NHAT`. Thêm sau bốn ngoại lệ cũ:

```python
class KhongTonTai(LookupError):  # noqa: N818
    pass


class DaXuLy(ValueError):  # noqa: N818
    pass


class TaiKhoanKhoa(ValueError):  # noqa: N818
    pass


class KhongCoGiDeThuHoi(ValueError):  # noqa: N818
    pass


NGUON_HOP_LE = ("admin", "thanh_toan")

_SQL_THEO_THAM_CHIEU = text(
    "SELECT y.id, y.trang_thai, y.user_sub::text AS sub, u.plan, u.plan_het_han"
    " FROM yeu_cau_nang_goi y JOIN users u ON u.sub = y.user_sub WHERE y.tham_chieu = :tc"
)
_SQL_KHOA_YEU_CAU = text(
    "SELECT y.id, y.user_sub::text AS sub, y.loai, y.goi_muon, y.trang_thai,"
    " u.plan, u.plan_het_han, u.khoa_luc"
    " FROM yeu_cau_nang_goi y JOIN users u ON u.sub = y.user_sub WHERE y.id = :id FOR UPDATE OF y, u"
)
# Đường ĐỔI GÓI DUY NHẤT trong src/ — test grep ở tests/test_api/test_admin_routes.py.
_SQL_DOI_GOI = text("UPDATE users SET plan = :plan, plan_het_han = :han WHERE sub = CAST(:sub AS uuid)")
_SQL_XU_LY = text(
    "UPDATE yeu_cau_nang_goi SET trang_thai = :tt, xu_ly_luc = now(), xu_ly_boi = :boi,"
    " nguon = :nguon, tham_chieu = :tc, ly_do = :ly_do WHERE id = :id"
)


def _han_moi(loai: str, het_han_cu: datetime | None, now: datetime, chu_ky_ngay: int) -> datetime:
    """`nang_goi` tính từ `now` (ChatGPT/Claude: nâng gói hiệu lực ngay, chu kỳ tính lại);
    `gia_han` nối tiếp hạn còn hiệu lực (Stripe: renewal nối `current_period_end`)."""
    moc = now
    if loai == "gia_han" and het_han_cu is not None and het_han_cu > now:
        moc = het_han_cu
    return moc + timedelta(days=chu_ky_ngay)


def _dinh_dang(han: datetime) -> str:
    return han.astimezone(mui_gio()).strftime("%H:%M ngày %d/%m/%Y")


def duyet(yeu_cau_id: int, nguon: str, tham_chieu: str, boi: str, ip: str | None = None) -> dict:
    """Duyệt một yêu cầu và đổi gói. Idempotent theo `tham_chieu`: gọi lại trả kết quả cũ,
    KHÔNG cộng thêm chu kỳ — điều kiện để webhook thanh toán dùng lại được."""
    if nguon not in NGUON_HOP_LE:
        raise ValueError(f"nguon không hợp lệ: {nguon}")
    chu_ky = int(_doc_han_muc()["chu_ky_pro_ngay"])
    with get_engine().begin() as c:
        cu = c.execute(_SQL_THEO_THAM_CHIEU, {"tc": tham_chieu}).mappings().one_or_none()
        if cu is not None and cu["trang_thai"] == "da_duyet":
            return {
                "id": cu["id"], "trang_thai": "da_duyet", "sub": cu["sub"],
                "plan": cu["plan"], "plan_het_han": cu["plan_het_han"],
            }
        y = c.execute(_SQL_KHOA_YEU_CAU, {"id": yeu_cau_id}).mappings().one_or_none()
        if y is None:
            raise KhongTonTai(yeu_cau_id)
        if y["trang_thai"] != "cho_duyet":
            raise DaXuLy(yeu_cau_id)
        if y["khoa_luc"] is not None:
            raise TaiKhoanKhoa(y["sub"])
        han = _han_moi(y["loai"], y["plan_het_han"], datetime.now(UTC), chu_ky)
        c.execute(_SQL_DOI_GOI, {"plan": y["goi_muon"], "han": han, "sub": y["sub"]})
        c.execute(
            _SQL_XU_LY,
            {"tt": "da_duyet", "boi": boi, "nguon": nguon, "tc": tham_chieu, "ly_do": None, "id": yeu_cau_id},
        )
        nhat_ky.ghi(
            "duyet_yeu_cau",
            doi_tuong=y["sub"],
            chi_tiet={
                "yeu_cau_id": yeu_cau_id, "loai": y["loai"], "goi": y["goi_muon"],
                "plan_het_han": han.isoformat(), "tham_chieu": tham_chieu,
            },
            boi=boi, tac_nhan_loai=nguon, ip=ip, c=c,
        )
        ten = ten_goi(y["goi_muon"])
        thong_bao.ghi(
            nguoi_nhan=y["sub"], loai="yeu_cau_duyet",
            tieu_de=f"Gói {ten} đã được mở",
            noi_dung=f"Tôi đã mở gói {ten} cho bạn tới {_dinh_dang(han)}.",
            duong_dan="/tai-khoan", khoa_gom=thong_bao.KHOA_KET_QUA.format(id=yeu_cau_id), c=c,
        )
        thong_bao.vo_hieu(thong_bao.KHOA_YEU_CAU.format(sub=y["sub"]), c=c)
        return {"id": yeu_cau_id, "trang_thai": "da_duyet", "sub": y["sub"], "plan": y["goi_muon"], "plan_het_han": han}


def tu_choi(yeu_cau_id: int, ly_do: str, boi: str, ip: str | None = None) -> dict:
    """Từ chối và lưu lý do. Không đụng `users`; unique index chỉ chặn `cho_duyet` nên
    người dùng gửi lại được."""
    with get_engine().begin() as c:
        y = c.execute(_SQL_KHOA_YEU_CAU, {"id": yeu_cau_id}).mappings().one_or_none()
        if y is None:
            raise KhongTonTai(yeu_cau_id)
        if y["trang_thai"] != "cho_duyet":
            raise DaXuLy(yeu_cau_id)
        c.execute(
            _SQL_XU_LY, {"tt": "tu_choi", "boi": boi, "nguon": "admin", "tc": None, "ly_do": ly_do, "id": yeu_cau_id}
        )
        nhat_ky.ghi(
            "tu_choi_yeu_cau", doi_tuong=y["sub"], chi_tiet={"yeu_cau_id": yeu_cau_id, "ly_do": ly_do},
            boi=boi, ip=ip, c=c,
        )
        thong_bao.ghi(
            nguoi_nhan=y["sub"], loai="yeu_cau_tu_choi", tieu_de="Yêu cầu nâng gói chưa được duyệt",
            noi_dung=f"Lý do: {ly_do}", duong_dan="/tai-khoan",
            khoa_gom=thong_bao.KHOA_KET_QUA.format(id=yeu_cau_id), c=c,
        )
        thong_bao.vo_hieu(thong_bao.KHOA_YEU_CAU.format(sub=y["sub"]), c=c)
        return {"id": yeu_cau_id, "trang_thai": "tu_choi", "ly_do": ly_do}
```

Vòng import: `bao_ve` không import `nang_goi`, `nhat_ky`, `thong_bao`, nên an toàn.

- [ ] **Bước 4: Xanh; lint; bộ test tài khoản cũ**

Run: `.venv/bin/python -m pytest tests/test_services/test_nang_goi_duyet.py tests/test_api/test_ho_so_nang_goi.py -q && .venv/bin/ruff check src/services/nang_goi.py tests/test_services/test_nang_goi_duyet.py && .venv/bin/ruff format --check src/services/nang_goi.py`
Expected: tất cả xanh.

- [ ] **Bước 5: Commit**

```bash
git add src/services/nang_goi.py tests/test_services/test_nang_goi_duyet.py
git commit -m "feat(admin): idempotent approve and reject for upgrade requests with audit log and notifications"
```

---
### Task 5: Khoá tài khoản, đặt gói tay, thu hồi — và cổng KLAW tôn trọng khoá

**Files:**
- Modify: `src/services/bao_ve.py` (`_SQL_UPSERT_USER` ~115; sau `ghi_nhan_nguoi_dung` ~454; `nguoi_dung_bat_buoc` ~633; thân `cong` trong `_cong` ~752)
- Modify: `src/services/nang_goi.py` (thêm `dat_goi`, `thu_hoi`)
- Create: `src/services/tai_khoan_qt.py` (`khoa`, `mo_khoa`, `TrangThaiKhongDoi`; Task 6 thêm hàm đọc)
- Modify: `src/api/routes_tai_khoan.py` (`han_muc_cua_toi`, nhánh đã đăng nhập)
- Test: `tests/test_services/test_tai_khoan_qt.py`, `tests/test_api/test_tai_khoan_khoa.py`

**Interfaces:**
- Consumes: `nang_goi._SQL_DOI_GOI`, `KhongCoGiDeThuHoi`, `GoiKhongHopLe`, `ChuaCoHoSo`, `_dinh_dang`; `nhat_ky.ghi`; `thong_bao.ghi/vo_hieu`, `KHOA_TAI_KHOAN`.
- Produces:
  - `bao_ve.LOI_TAI_KHOAN_KHOA = "Tài khoản của bạn đang bị tạm khoá. Liên hệ hỗ trợ để được mở lại."`
  - `bao_ve.bi_khoa(sub: str) -> bool`; `bao_ve.kiem_khoa(sub: str) -> None` (403); `bao_ve.ghi_nhan_va_kiem_khoa(sub, email) -> str`.
  - `nang_goi.dat_goi(sub: str, plan: str, so_ngay: int | None, boi: str, ip: str | None = None) -> dict` → `{"sub", "plan", "plan_het_han"}` (`plan` là gói HIỆU LỰC).
  - `nang_goi.thu_hoi(sub: str, ly_do: str, boi: str, ip: str | None = None) -> dict` → cùng hình.
  - `tai_khoan_qt.TrangThaiKhongDoi(ValueError)`; `tai_khoan_qt.khoa(sub, ly_do, boi, ip=None) -> dict` và `mo_khoa(sub, boi, ip=None) -> dict` → `{"sub", "khoa_luc", "khoa_ly_do"}`; `LookupError` khi không có dòng.
  - `HanMucResponse.bi_khoa` có giá trị thật ở `/han-muc`.

- [ ] **Bước 1: Test dịch vụ (đỏ)**

```python
# tests/test_services/test_tai_khoan_qt.py
"""Khoá/mở khoá, đặt gói tay, thu hồi (spec 2B §5.2). Task 6 thêm test đọc vào file này."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from src.services import bao_ve, nang_goi, tai_khoan_qt, thong_bao
from src.services.db import get_engine

pytestmark = pytest.mark.integration
BOI = "admin-qt@klaw.local"


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "qt@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM thong_bao WHERE nguoi_nhan = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi = :b"), {"b": BOI})
        c.execute(text("DELETE FROM yeu_cau_nang_goi WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


def _dong(sub):
    with get_engine().connect() as c:
        return (
            c.execute(
                text("SELECT plan, plan_het_han, khoa_luc, khoa_ly_do FROM users WHERE sub = CAST(:s AS uuid)"),
                {"s": sub},
            )
            .mappings()
            .one()
        )


def test_khoa_roi_mo_khoa_va_trang_thai_khong_doi(nguoi):
    r = tai_khoan_qt.khoa(nguoi, "Gửi câu hỏi tự động hàng loạt.", BOI, "10.0.0.9")
    assert r["khoa_luc"] is not None and bao_ve.bi_khoa(nguoi) is True
    with pytest.raises(tai_khoan_qt.TrangThaiKhongDoi):
        tai_khoan_qt.khoa(nguoi, "lại", BOI)
    assert thong_bao.dem_chua_doc(nguoi) == 1
    r2 = tai_khoan_qt.mo_khoa(nguoi, BOI)
    assert r2["khoa_luc"] is None and bao_ve.bi_khoa(nguoi) is False
    with pytest.raises(tai_khoan_qt.TrangThaiKhongDoi):
        tai_khoan_qt.mo_khoa(nguoi, BOI)
    with pytest.raises(LookupError):
        tai_khoan_qt.khoa(str(uuid.uuid4()), "x", BOI)
    with get_engine().connect() as c:
        hd = {r[0] for r in c.execute(text("SELECT hanh_dong FROM nhat_ky_quan_tri WHERE boi = :b"), {"b": BOI})}
    assert {"khoa_tai_khoan", "mo_khoa_tai_khoan"} <= hd


def test_dat_goi_so_ngay_None_la_vo_thoi_han_va_goi_la(nguoi):
    r = nang_goi.dat_goi(nguoi, "pro", None, BOI)
    assert r["plan"] == "pro" and r["plan_het_han"] is None and _dong(nguoi)["plan_het_han"] is None
    r = nang_goi.dat_goi(nguoi, "pro", 10, BOI)
    assert 9 < (r["plan_het_han"] - datetime.now(UTC)).total_seconds() / 86400 <= 10
    r = nang_goi.dat_goi(nguoi, "free", None, BOI)
    assert r["plan"] == "free" and r["plan_het_han"] is None
    with pytest.raises(nang_goi.GoiKhongHopLe):
        nang_goi.dat_goi(nguoi, "vip", None, BOI)
    with pytest.raises(nang_goi.ChuaCoHoSo):
        nang_goi.dat_goi(str(uuid.uuid4()), "pro", None, BOI)
    assert thong_bao.dem_chua_doc(nguoi) >= 1


def test_thu_hoi_dat_het_han_now_khong_doi_plan_va_tu_choi_khi_dang_free(nguoi):
    with pytest.raises(nang_goi.KhongCoGiDeThuHoi):
        nang_goi.thu_hoi(nguoi, "x", BOI)
    nang_goi.dat_goi(nguoi, "pro", 30, BOI)
    r = nang_goi.thu_hoi(nguoi, "Chia sẻ tài khoản.", BOI)
    d = _dong(nguoi)
    assert d["plan"] == "pro" and d["plan_het_han"] <= datetime.now(UTC)
    assert r["plan"] == "free", "gói HIỆU LỰC trả về là mặc định"
    assert bao_ve.plan_hieu_luc(nguoi) == "free"
```

- [ ] **Bước 2: Test API (đỏ)**

```python
# tests/test_api/test_tai_khoan_khoa.py
"""Tài khoản bị khoá (spec 2B §5.2, §5.4): 403 ở đường tốn LLM và endpoint tài khoản,
`/han-muc` vẫn trả lời kèm `bi_khoa`, endpoint đọc thuần vẫn mở."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, tai_khoan_qt
from src.services.db import get_engine
from tests.test_api.test_tra_cuu_phien import SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration


@pytest.fixture
def nguoi_khoa(cai_dat, khoa_ky):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "khoa@test.local")
    tai_khoan_qt.khoa(sub, "Thử nghiệm.", "qa@klaw.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM thong_bao WHERE nguoi_nhan = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi = 'qa@klaw.local'"))
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


@pytest.mark.asyncio
async def test_khoa_thi_tra_cuu_va_ho_so_403_han_muc_200_pham_vi_200(client, khoa_ky, nguoi_khoa, graph_gia_lap):
    h = _bearer(khoa_ky, nguoi_khoa)
    r = await client.post("/api/v1/tra-cuu", json={"query": "thử việc bao lâu"}, headers=h)
    assert r.status_code == 403 and r.json()["detail"] == bao_ve.LOI_TAI_KHOAN_KHOA
    assert (await client.get("/api/v1/ho-so", headers=h)).status_code == 403
    hm = await client.get("/api/v1/han-muc", headers=h)
    assert hm.status_code == 200 and hm.json()["bi_khoa"] is True
    assert (await client.get("/api/v1/pham-vi")).status_code == 200
    tai_khoan_qt.mo_khoa(nguoi_khoa, "qa@klaw.local")
    assert (await client.get("/api/v1/ho-so", headers=h)).status_code == 200
    assert (await client.get("/api/v1/han-muc", headers=h)).json()["bi_khoa"] is False
```

- [ ] **Bước 3: Đỏ**

Run: `.venv/bin/python -m pytest tests/test_services/test_tai_khoan_qt.py tests/test_api/test_tai_khoan_khoa.py -q` → FAIL `ModuleNotFoundError: src.services.tai_khoan_qt`.

- [ ] **Bước 4: `bao_ve.py`**

Sửa `_SQL_UPSERT_USER`: dòng cuối thành `" RETURNING plan, plan_het_han, khoa_luc"`. Thêm sau `LOI_SOAN_THAO_DANG_NHAP`:

```python
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
```

Trong `nguoi_dung_bat_buoc`, thay `return nguoi` cuối hàm bằng:

```python
    await run_in_threadpool(kiem_khoa, nguoi["sub"])
    return nguoi
```

Trong thân `cong` của `_cong`, thay khối `try: plan = await run_in_threadpool(ghi_nhan_nguoi_dung, …)` bằng:

```python
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
```

- [ ] **Bước 5: `nang_goi.dat_goi`, `thu_hoi`**

```python
_SQL_KHOA_USER = text("SELECT plan, plan_het_han, khoa_luc FROM users WHERE sub = CAST(:sub AS uuid) FOR UPDATE")


def _iso(t: datetime | None) -> str | None:
    return t.isoformat() if t is not None else None


def _ket_qua(sub: str, plan: str, han: datetime | None) -> dict:
    return {"sub": sub, "plan": plan_hieu_luc_tu(plan, han), "plan_het_han": han}


def dat_goi(sub: str, plan: str, so_ngay: int | None, boi: str, ip: str | None = None) -> dict:
    """Đặt gói tay. `so_ngay=None` với gói trả phí = vô thời hạn (`plan_het_han` NULL);
    gói mặc định luôn NULL."""
    d = _doc_han_muc()
    if plan not in d["goi"]:
        raise GoiKhongHopLe(plan)
    han = None
    if plan != d["goi_mac_dinh"] and so_ngay is not None:
        han = datetime.now(UTC) + timedelta(days=so_ngay)
    with get_engine().begin() as c:
        u = c.execute(_SQL_KHOA_USER, {"sub": sub}).mappings().one_or_none()
        if u is None:
            raise ChuaCoHoSo()
        c.execute(_SQL_DOI_GOI, {"plan": plan, "han": han, "sub": sub})
        nhat_ky.ghi(
            "dat_goi",
            doi_tuong=sub,
            chi_tiet={
                "plan": plan, "so_ngay": so_ngay, "plan_het_han": _iso(han),
                "truoc": {"plan": u["plan"], "plan_het_han": _iso(u["plan_het_han"])},
            },
            boi=boi, ip=ip, c=c,
        )
        han_chu = f" tới {_dinh_dang(han)}" if han is not None else ""
        thong_bao.ghi(
            nguoi_nhan=sub, loai="goi_dat_tay", tieu_de="Gói của bạn vừa được cập nhật",
            noi_dung=f"Gói hiện tại của bạn là {ten_goi(plan)}{han_chu}.", duong_dan="/tai-khoan",
            khoa_gom=thong_bao.KHOA_TAI_KHOAN.format(sub=sub, loai="goi_dat_tay"), c=c,
        )
        return _ket_qua(sub, plan, han)


def thu_hoi(sub: str, ly_do: str, boi: str, ip: str | None = None) -> dict:
    """Thu hồi gói trả phí NGAY: `plan_het_han = now()`, KHÔNG đổi `plan` — gói hiệu lực
    tự về mặc định qua `plan_hieu_luc_tu` (hàng "canceled" của bảng trạng thái §2)."""
    d = _doc_han_muc()
    with get_engine().begin() as c:
        u = c.execute(_SQL_KHOA_USER, {"sub": sub}).mappings().one_or_none()
        if u is None:
            raise ChuaCoHoSo()
        if plan_hieu_luc_tu(str(u["plan"]), u["plan_het_han"]) == d["goi_mac_dinh"]:
            raise KhongCoGiDeThuHoi(sub)
        now = datetime.now(UTC)
        c.execute(_SQL_DOI_GOI, {"plan": u["plan"], "han": now, "sub": sub})
        nhat_ky.ghi(
            "thu_hoi_goi", doi_tuong=sub,
            chi_tiet={"ly_do": ly_do, "plan": u["plan"], "plan_het_han_cu": _iso(u["plan_het_han"])},
            boi=boi, ip=ip, c=c,
        )
        thong_bao.ghi(
            nguoi_nhan=sub, loai="goi_thu_hoi", tieu_de=f"Gói {ten_goi(str(u['plan']))} đã bị thu hồi",
            noi_dung=f"Lý do: {ly_do}", duong_dan="/tai-khoan",
            khoa_gom=thong_bao.KHOA_TAI_KHOAN.format(sub=sub, loai="goi_thu_hoi"), c=c,
        )
        return _ket_qua(sub, str(u["plan"]), now)
```

- [ ] **Bước 6: `tai_khoan_qt.py` (phần ghi)**

```python
# src/services/tai_khoan_qt.py
"""Phía admin của tài khoản (spec 2026-09-08 cms-quan-ly-tai-khoan §5.2): khoá/mở khoá,
tìm, chi tiết, tổng quan. Không hàm nào ở đây đổi `plan` — việc đó của `nang_goi`."""

from sqlalchemy import text

from src.services import nhat_ky, thong_bao
from src.services.db import get_engine


class TrangThaiKhongDoi(ValueError):  # noqa: N818
    pass


_SQL_KHOA_USER = text("SELECT khoa_luc FROM users WHERE sub = CAST(:sub AS uuid) FOR UPDATE")
_SQL_KHOA = text(
    "UPDATE users SET khoa_luc = now(), khoa_ly_do = :ly_do WHERE sub = CAST(:sub AS uuid)"
    " RETURNING sub::text AS sub, khoa_luc, khoa_ly_do"
)
_SQL_MO_KHOA = text(
    "UPDATE users SET khoa_luc = NULL, khoa_ly_do = NULL WHERE sub = CAST(:sub AS uuid)"
    " RETURNING sub::text AS sub, khoa_luc, khoa_ly_do"
)


def khoa(sub: str, ly_do: str, boi: str, ip: str | None = None) -> dict:
    with get_engine().begin() as c:
        u = c.execute(_SQL_KHOA_USER, {"sub": sub}).mappings().one_or_none()
        if u is None:
            raise LookupError(sub)
        if u["khoa_luc"] is not None:
            raise TrangThaiKhongDoi("đã khoá")
        r = c.execute(_SQL_KHOA, {"ly_do": ly_do, "sub": sub}).mappings().one()
        nhat_ky.ghi("khoa_tai_khoan", doi_tuong=sub, chi_tiet={"ly_do": ly_do}, boi=boi, ip=ip, c=c)
        thong_bao.ghi(
            nguoi_nhan=sub, loai="tai_khoan_khoa", tieu_de="Tài khoản đã bị tạm khoá",
            noi_dung=f"Lý do: {ly_do}. Liên hệ hỗ trợ để được mở lại.", duong_dan="/tai-khoan",
            khoa_gom=thong_bao.KHOA_TAI_KHOAN.format(sub=sub, loai="tai_khoan_khoa"), c=c,
        )
        return dict(r)


def mo_khoa(sub: str, boi: str, ip: str | None = None) -> dict:
    with get_engine().begin() as c:
        u = c.execute(_SQL_KHOA_USER, {"sub": sub}).mappings().one_or_none()
        if u is None:
            raise LookupError(sub)
        if u["khoa_luc"] is None:
            raise TrangThaiKhongDoi("đang mở")
        r = c.execute(_SQL_MO_KHOA, {"sub": sub}).mappings().one()
        nhat_ky.ghi("mo_khoa_tai_khoan", doi_tuong=sub, chi_tiet={}, boi=boi, ip=ip, c=c)
        thong_bao.vo_hieu(thong_bao.KHOA_TAI_KHOAN.format(sub=sub, loai="tai_khoan_khoa"), c=c)
        thong_bao.ghi(
            nguoi_nhan=sub, loai="tai_khoan_mo", tieu_de="Tài khoản đã được mở lại",
            noi_dung="Bạn hỏi và soạn văn bản lại được rồi.", duong_dan="/tai-khoan",
            khoa_gom=thong_bao.KHOA_TAI_KHOAN.format(sub=sub, loai="tai_khoan_mo"), c=c,
        )
        return dict(r)
```

- [ ] **Bước 7: `/han-muc`**

Trong `han_muc_cua_toi`, nhánh đã đăng nhập, thêm vào khối `try` sau `het_han = …`: `bi_khoa = await run_in_threadpool(bao_ve.bi_khoa, sub)`; thêm `bi_khoa=bi_khoa,` vào `HanMucResponse(...)` cuối hàm. Hai nhánh khách và chưa cấu hình để mặc định `False`.

- [ ] **Bước 8: Xanh; hồi quy cổng; lint**

Run: `.venv/bin/python -m pytest tests/test_services/test_tai_khoan_qt.py tests/test_api/test_tai_khoan_khoa.py tests/test_api/test_cong_bao_ve.py tests/test_api/test_xac_thuc_han_muc.py tests/test_api/test_khach.py tests/test_api/test_tai_khoan.py tests/test_api/test_ho_so_nang_goi.py -q && .venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check src/services/tai_khoan_qt.py src/services/nang_goi.py`
Expected: xanh. Fixture nào monkeypatch `bao_ve.ghi_nhan_nguoi_dung` để né DB (ví dụ `khong_dung_db` ở `test_tai_khoan.py`) thì thêm cùng patch cho `bao_ve.ghi_nhan_va_kiem_khoa` (`lambda sub, email: "free"`) và `bao_ve.bi_khoa` (`lambda sub: False`) — cùng khuôn, không đổi ý test.

- [ ] **Bước 9: Commit**

```bash
git add src/services/bao_ve.py src/services/nang_goi.py src/services/tai_khoan_qt.py src/api/routes_tai_khoan.py tests/test_services/test_tai_khoan_qt.py tests/test_api/test_tai_khoan_khoa.py tests/test_api/test_tai_khoan.py
git commit -m "feat(admin): account suspension enforced at the gates, manual plan set and paid-plan revoke"
```

---

### Task 6: `tai_khoan_qt` — tìm, chi tiết, danh sách yêu cầu, tổng quan, danh mục gói

**Files:**
- Modify: `src/services/tai_khoan_qt.py`
- Test: `tests/test_services/test_tai_khoan_qt.py` (thêm)

**Interfaces:**
- Consumes: `ho_so.tong_hop`, `bao_ve.moc_ngay`, `bao_ve._doc_han_muc`, `bao_ve.ten_goi`.
- Produces:
  - `tim(q: str, limit: int, offset: int) -> tuple[int, list[dict]]` — khoá `sub, email, plan (thô), plan_het_han, khoa_luc, tao_luc, so_phien, luot_30_ngay`.
  - `chi_tiet(sub: str) -> dict | None` — `ho_so.tong_hop(sub)` + `sub`, `khoa_luc`, `khoa_ly_do`, `yeu_cau: list[dict]` (khoá theo `YeuCauNangGoiOut`).
  - `yeu_cau_theo_id(id: int) -> dict | None` — khoá theo `YeuCauNangGoiOut`.
  - `danh_sach_yeu_cau(trang_thai: str | None, q: str | None, limit: int, offset: int) -> tuple[int, list[dict]]` — khoá theo `YeuCauAdminOut` trừ `plan_hieu_luc`, cộng `plan`, `plan_het_han`.
  - `tong_quan() -> dict` — bảy khoá của `TongQuanOut`.
  - `danh_sach_goi() -> dict` — theo `DanhSachGoiOut`.

- [ ] **Bước 1: Test (đỏ) — thêm vào `test_tai_khoan_qt.py`**

```python
def test_tim_theo_email_va_dem_luot_30_ngay(nguoi):
    with get_engine().begin() as c:
        c.execute(
            text(
                "INSERT INTO traces (id, endpoint, config_name, result_type, user_sub, cache_hit) VALUES"
                " (:a, '/api/v1/tra-cuu', 'full', 'answer', :s, false),"
                " (:b, '/api/v1/tra-cuu', 'full', 'answer', :s, true),"
                " (:c, '/api/v1/tra-cuu', 'full', 'loi', :s, false)"
            ),
            {"a": str(uuid.uuid4()), "b": str(uuid.uuid4()), "c": str(uuid.uuid4()), "s": nguoi},
        )
    tong, rows = tai_khoan_qt.tim("qt@test", 20, 0)
    assert tong >= 1
    r = next(x for x in rows if x["sub"] == nguoi)
    assert r["email"] == "qt@test.local" and r["luot_30_ngay"] == 1 and r["so_phien"] == 0
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM traces WHERE user_sub = :s"), {"s": nguoi})


def test_chi_tiet_gom_ho_so_khoa_va_lich_su_yeu_cau(nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    nang_goi.tu_choi(yc["id"], "Thử.", BOI)
    tai_khoan_qt.khoa(nguoi, "Kiểm.", BOI)
    d = tai_khoan_qt.chi_tiet(nguoi)
    assert d is not None and d["sub"] == nguoi and d["khoa_ly_do"] == "Kiểm." and d["email"] == "qt@test.local"
    assert d["yeu_cau"][0]["trang_thai"] == "tu_choi" and d["yeu_cau"][0]["ly_do"] == "Thử."
    assert tai_khoan_qt.chi_tiet(str(uuid.uuid4())) is None
    assert tai_khoan_qt.yeu_cau_theo_id(yc["id"])["ly_do"] == "Thử."
    assert tai_khoan_qt.yeu_cau_theo_id(10**9) is None


def test_danh_sach_yeu_cau_loc_trang_thai_va_email(nguoi):
    nang_goi.tao_yeu_cau(nguoi, "pro")
    tong, rows = tai_khoan_qt.danh_sach_yeu_cau("cho_duyet", "qt@test", 20, 0)
    assert tong == 1 and rows[0]["user_sub"] == nguoi and rows[0]["email"] == "qt@test.local"
    assert rows[0]["plan"] == "free" and rows[0]["khoa_luc"] is None
    tong0, _ = tai_khoan_qt.danh_sach_yeu_cau("da_duyet", "qt@test", 20, 0)
    assert tong0 == 0


def test_tong_quan_dem_du_bay_so(nguoi):
    truoc = tai_khoan_qt.tong_quan()
    nang_goi.dat_goi(nguoi, "pro", 3, BOI)  # Cá nhân hiệu lực, hết hạn trong 7 ngày
    nang_goi.tao_yeu_cau(nguoi, "pro")  # gia_han, cho_duyet
    sau = tai_khoan_qt.tong_quan()
    assert set(sau) == {
        "tong_tai_khoan", "dang_ca_nhan", "cho_duyet", "het_han_7_ngay", "moi_7_ngay", "dang_khoa", "hoi_dap_hom_nay"
    }
    assert sau["dang_ca_nhan"] == truoc["dang_ca_nhan"] + 1
    assert sau["het_han_7_ngay"] == truoc["het_han_7_ngay"] + 1
    assert sau["cho_duyet"] == truoc["cho_duyet"] + 1
    tai_khoan_qt.khoa(nguoi, "x", BOI)
    assert tai_khoan_qt.tong_quan()["dang_khoa"] == truoc["dang_khoa"] + 1


def test_danh_sach_goi_doc_tu_yaml():
    d = tai_khoan_qt.danh_sach_goi()
    ma = {g["ma"]: g for g in d["goi"]}
    assert d["goi_mac_dinh"] == "free" and d["chu_ky_pro_ngay"] == 30
    assert ma["pro"]["ten"] == "Cá nhân" and ma["free"]["han_muc"]["hoi_dap_ngay"] == 200
```

- [ ] **Bước 2: Đỏ**

Run: `.venv/bin/python -m pytest tests/test_services/test_tai_khoan_qt.py -q` → FAIL `AttributeError: tim`.

- [ ] **Bước 3: Viết phần đọc**

Thêm vào `tai_khoan_qt.py` (import thêm `from src.services import ho_so` và `from src.services.bao_ve import _doc_han_muc, moc_ngay, ten_goi`):

```python
_LOC_LUOT = (
    " AND NOT t.cache_hit AND t.endpoint = '/api/v1/tra-cuu'"
    " AND (t.result_type IS NULL OR t.result_type NOT IN ('loi', 'out_of_scope'))"
)
_SQL_TIM_DEM = text("SELECT count(*)::int FROM users WHERE email ILIKE :q")
_SQL_TIM = text(
    "SELECT u.sub::text AS sub, u.email, u.plan, u.plan_het_han, u.khoa_luc, u.created_at AS tao_luc,"
    " (SELECT count(*)::int FROM hoi_thoai h WHERE h.user_sub = u.sub AND h.xoa_luc IS NULL) AS so_phien,"
    " (SELECT count(*)::int FROM traces t WHERE t.user_sub::text = u.sub::text"
    "  AND t.ts >= now() - interval '30 days'" + _LOC_LUOT + ") AS luot_30_ngay"
    " FROM users u WHERE u.email ILIKE :q ORDER BY u.created_at DESC LIMIT :limit OFFSET :offset"
)
_SQL_KHOA_CUA = text("SELECT khoa_luc, khoa_ly_do FROM users WHERE sub = CAST(:sub AS uuid)")
_COT_YC = "id, loai, goi_hien_tai, goi_muon, trang_thai, tao_luc, xu_ly_luc, ly_do"
_SQL_YEU_CAU_CUA = text(
    f"SELECT {_COT_YC} FROM yeu_cau_nang_goi WHERE user_sub = CAST(:sub AS uuid)"
    " ORDER BY tao_luc DESC, id DESC LIMIT 50"
)
_SQL_YEU_CAU_ID = text(f"SELECT {_COT_YC} FROM yeu_cau_nang_goi WHERE id = :id")
_LOC_YC = (
    " FROM yeu_cau_nang_goi y JOIN users u ON u.sub = y.user_sub"
    " WHERE (CAST(:tt AS text) IS NULL OR y.trang_thai = :tt)"
    " AND (CAST(:q AS text) IS NULL OR u.email ILIKE :q)"
)
_SQL_YC_DEM = text("SELECT count(*)::int" + _LOC_YC)
_SQL_YC = text(
    "SELECT y.id, y.user_sub::text AS user_sub, u.email, y.loai, y.goi_hien_tai, y.goi_muon, y.trang_thai,"
    " y.tao_luc, y.xu_ly_luc, y.xu_ly_boi, y.ly_do, u.plan, u.plan_het_han, u.khoa_luc"
    + _LOC_YC
    + " ORDER BY y.tao_luc DESC, y.id DESC LIMIT :limit OFFSET :offset"
)
_SQL_TONG_QUAN = text(
    "SELECT"
    " (SELECT count(*)::int FROM users) AS tong_tai_khoan,"
    " (SELECT count(*)::int FROM users WHERE plan <> :mac_dinh AND khoa_luc IS NULL"
    "   AND (plan_het_han IS NULL OR plan_het_han > now())) AS dang_ca_nhan,"
    " (SELECT count(*)::int FROM yeu_cau_nang_goi WHERE trang_thai = 'cho_duyet') AS cho_duyet,"
    " (SELECT count(*)::int FROM users WHERE plan <> :mac_dinh"
    "   AND plan_het_han > now() AND plan_het_han <= now() + interval '7 days') AS het_han_7_ngay,"
    " (SELECT count(*)::int FROM users WHERE created_at >= now() - interval '7 days') AS moi_7_ngay,"
    " (SELECT count(*)::int FROM users WHERE khoa_luc IS NOT NULL) AS dang_khoa,"
    " (SELECT count(*)::int FROM traces t WHERE t.ts >= :moc" + _LOC_LUOT + ") AS hoi_dap_hom_nay"
)


def tim(q: str, limit: int, offset: int) -> tuple[int, list[dict]]:
    p = {"q": f"%{q.strip()}%"}
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_TIM_DEM, p).scalar_one())
        rows = [dict(r) for r in c.execute(_SQL_TIM, {**p, "limit": limit, "offset": offset}).mappings()]
    return tong, rows


def chi_tiet(sub: str) -> dict | None:
    d = ho_so.tong_hop(sub)
    if d is None:
        return None
    with get_engine().connect() as c:
        k = c.execute(_SQL_KHOA_CUA, {"sub": sub}).mappings().one()
        yc = [dict(r) for r in c.execute(_SQL_YEU_CAU_CUA, {"sub": sub}).mappings()]
    return {**d, "sub": sub, "khoa_luc": k["khoa_luc"], "khoa_ly_do": k["khoa_ly_do"], "yeu_cau": yc}


def yeu_cau_theo_id(id: int) -> dict | None:
    with get_engine().connect() as c:
        r = c.execute(_SQL_YEU_CAU_ID, {"id": id}).mappings().one_or_none()
    return dict(r) if r is not None else None


def danh_sach_yeu_cau(trang_thai: str | None, q: str | None, limit: int, offset: int) -> tuple[int, list[dict]]:
    p = {"tt": trang_thai, "q": f"%{q.strip()}%" if q else None}
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_YC_DEM, p).scalar_one())
        rows = [dict(r) for r in c.execute(_SQL_YC, {**p, "limit": limit, "offset": offset}).mappings()]
    return tong, rows


def tong_quan() -> dict:
    with get_engine().connect() as c:
        r = c.execute(_SQL_TONG_QUAN, {"mac_dinh": _doc_han_muc()["goi_mac_dinh"], "moc": moc_ngay()}).mappings().one()
    return dict(r)


def danh_sach_goi() -> dict:
    d = _doc_han_muc()
    return {
        "goi": [
            {"ma": ma, "ten": ten_goi(ma), "han_muc": {k: int(v) for k, v in hm.items()}} for ma, hm in d["goi"].items()
        ],
        "goi_mac_dinh": str(d["goi_mac_dinh"]),
        "chu_ky_pro_ngay": int(d["chu_ky_pro_ngay"]),
    }
```

Kiểm `traces.ts` là tên cột thời gian (dùng ở `bao_ve._SQL_DEM_LUOT_TU`); `hoi_thoai.xoa_luc` dùng ở `ho_so._SQL_SO_PHIEN`.

- [ ] **Bước 4: Xanh; lint**

Run: `.venv/bin/python -m pytest tests/test_services/test_tai_khoan_qt.py -q && .venv/bin/ruff check src/services/tai_khoan_qt.py tests/test_services/test_tai_khoan_qt.py && .venv/bin/ruff format --check src/services/tai_khoan_qt.py`
Expected: 8 passed.

- [ ] **Bước 5: Commit**

```bash
git add src/services/tai_khoan_qt.py tests/test_services/test_tai_khoan_qt.py
git commit -m "feat(admin): account search, detail, request listing, overview counters and plan catalog"
```

---

### Task 7: Router `/admin` và cổng khoá dịch vụ

**Files:**
- Modify: `src/services/bao_ve.py` (thêm `kiem_admin_key` sau `kiem_api_key`; import `nhat_ky`)
- Create: `src/api/routes_admin.py`
- Modify: `src/main.py` (import + `include_router`, cạnh dòng 162–170)
- Test: `tests/test_api/test_admin_cong.py`, `tests/test_api/test_admin_routes.py`

**Interfaces:**
- Consumes: mọi hàm Task 2–6; model Task 1.
- Produces:
  - `bao_ve.TEN_HEADER_ADMIN_KEY = "X-Admin-Key"`, `bao_ve.TEN_HEADER_ADMIN_BOI = "X-Admin-Boi"`, `bao_ve.LOI_ADMIN_CHUA_CAU_HINH = "Đường quản trị chưa được cấu hình."`.
  - `async bao_ve.kiem_admin_key(request) -> dict` → `{"boi": str, "ip": str}`.
  - Router `/api/v1/admin/*` theo bảng §5.3 (12 endpoint giai đoạn 1–2; ba endpoint thông báo ở Task 16).

- [ ] **Bước 1: Test cổng (đỏ, không cần DB)**

```python
# tests/test_api/test_admin_cong.py
"""Cổng `/admin` (spec 2B §5.3): 503 khi chưa cấu hình, 401 + nhật ký khi sai khoá,
400 khi thiếu danh tính, không liên quan `KLAW_API_KEY`."""

import pytest

from src.services import bao_ve, nhat_ky, tai_khoan_qt

DUNG = {"X-Admin-Key": "khoa-thu", "X-Admin-Boi": "qa@klaw.local"}
BAY_SO = ["tong_tai_khoan", "dang_ca_nhan", "cho_duyet", "het_han_7_ngay", "moi_7_ngay", "dang_khoa", "hoi_dap_hom_nay"]


@pytest.fixture
def ghi_gia(monkeypatch):
    dong: list[dict] = []
    monkeypatch.setattr(nhat_ky, "ghi", lambda hanh_dong, **kw: dong.append({"hanh_dong": hanh_dong, **kw}) or 1)
    monkeypatch.setattr(tai_khoan_qt, "tong_quan", lambda: dict.fromkeys(BAY_SO, 0))
    return dong


async def test_chua_cau_hinh_thi_503_ke_ca_khoa_dung(client, cai_dat, ghi_gia):
    cai_dat(admin_api_key="")
    r = await client.get("/api/v1/admin/tong-quan", headers=DUNG)
    assert r.status_code == 503 and r.json()["detail"] == bao_ve.LOI_ADMIN_CHUA_CAU_HINH


async def test_sai_khoa_401_va_ghi_xac_thuc_that_bai(client, cai_dat, ghi_gia):
    cai_dat(admin_api_key="khoa-thu")
    r = await client.get("/api/v1/admin/tong-quan", headers={**DUNG, "X-Admin-Key": "sai"})
    assert r.status_code == 401 and "khoa-thu" not in r.text
    assert ghi_gia[-1]["hanh_dong"] == "xac_thuc_that_bai" and ghi_gia[-1]["boi"] == "(không rõ)"
    assert (await client.get("/api/v1/admin/tong-quan", headers={"X-Admin-Boi": "qa@klaw.local"})).status_code == 401


async def test_thieu_boi_400_du_khoa_dung(client, cai_dat, ghi_gia):
    cai_dat(admin_api_key="khoa-thu")
    assert (await client.get("/api/v1/admin/tong-quan", headers={"X-Admin-Key": "khoa-thu"})).status_code == 400


async def test_khoa_dung_va_boi_dung_thi_200(client, cai_dat, ghi_gia):
    cai_dat(admin_api_key="khoa-thu")
    assert (await client.get("/api/v1/admin/tong-quan", headers=DUNG)).status_code == 200


async def test_KLAW_API_KEY_khong_lien_quan_toi_admin(client, cai_dat, ghi_gia):
    cai_dat(admin_api_key="khoa-thu", api_key="khoa-cong-khai")
    assert (await client.get("/api/v1/admin/tong-quan", headers=DUNG)).status_code == 200
```

`cai_dat` chỉ patch `bao_ve.get_settings` và `xac_thuc.get_settings` — nên `kiem_admin_key` PHẢI đọc khoá qua `get_settings()` của module `bao_ve` (đúng như viết ở bước 4).

- [ ] **Bước 2: Test endpoint (đỏ, integration)**

```python
# tests/test_api/test_admin_routes.py
"""Router `/admin` (spec 2B §5.3) qua HTTP thật, và hai bất biến grep."""

import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from src.services import bao_ve, nang_goi
from src.services.db import get_engine
from tests.test_api.test_tra_cuu_phien import SUPABASE

H = {"X-Admin-Key": "khoa-thu", "X-Admin-Boi": "qa@klaw.local"}
tich_hop = pytest.mark.integration


@pytest.fixture
def nguoi(cai_dat):
    cai_dat(admin_api_key="khoa-thu", supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "route@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(
            text("DELETE FROM thong_bao WHERE nguoi_nhan = CAST(:s AS uuid) OR khoa_gom LIKE :k"),
            {"s": sub, "k": f"%{sub}%"},
        )
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi IN ('qa@klaw.local', '(không rõ)')"))
        c.execute(text("DELETE FROM yeu_cau_nang_goi WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


@tich_hop
async def test_luong_duyet_tu_api(client, nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    ds = (await client.get("/api/v1/admin/yeu-cau", params={"trang_thai": "cho_duyet", "q": "route@"}, headers=H)).json()
    assert ds["tong"] == 1 and ds["items"][0]["email"] == "route@test.local" and ds["items"][0]["plan_hieu_luc"] == "free"
    r = await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/duyet", headers=H)
    assert r.status_code == 200 and r.json()["plan"] == "pro"
    assert (await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/duyet", headers=H)).status_code == 200, "idempotent"
    assert (await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/tu-choi", json={"ly_do": "x"}, headers=H)).status_code == 409
    assert (await client.post("/api/v1/admin/yeu-cau/999999999/duyet", headers=H)).status_code == 404


@tich_hop
async def test_tu_choi_can_ly_do_va_hien_o_chi_tiet(client, nguoi):
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    assert (await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/tu-choi", json={"ly_do": ""}, headers=H)).status_code == 422
    r = await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/tu-choi", json={"ly_do": "Chưa nhận tiền."}, headers=H)
    assert r.status_code == 200 and r.json()["trang_thai"] == "tu_choi" and r.json()["ly_do"] == "Chưa nhận tiền."
    ct = (await client.get(f"/api/v1/admin/tai-khoan/{nguoi}", headers=H)).json()
    assert ct["sub"] == nguoi and ct["yeu_cau"][0]["ly_do"] == "Chưa nhận tiền." and ct["plan"] == "free"


@tich_hop
async def test_tim_dat_goi_thu_hoi_khoa_mo_khoa(client, nguoi):
    ds = (await client.get("/api/v1/admin/tai-khoan", params={"q": "route@test"}, headers=H)).json()
    assert ds["tong"] == 1 and ds["items"][0]["sub"] == nguoi and ds["items"][0]["plan"] == "free"
    r = await client.patch(f"/api/v1/admin/tai-khoan/{nguoi}/goi", json={"plan": "pro", "so_ngay": 15}, headers=H)
    assert r.status_code == 200 and r.json()["plan"] == "pro"
    assert (await client.patch(f"/api/v1/admin/tai-khoan/{nguoi}/goi", json={"plan": "vip"}, headers=H)).status_code == 422
    r = await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/thu-hoi", json={"ly_do": "Chia sẻ."}, headers=H)
    assert r.status_code == 200 and r.json()["plan"] == "free"
    assert (await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/thu-hoi", json={"ly_do": "Chia sẻ."}, headers=H)).status_code == 409
    assert (await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/khoa", json={"ly_do": "Spam."}, headers=H)).status_code == 200
    assert (await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/khoa", json={"ly_do": "Spam."}, headers=H)).status_code == 409
    yc = nang_goi.tao_yeu_cau(nguoi, "pro")
    assert (await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/duyet", headers=H)).status_code == 423
    assert (await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/mo-khoa", headers=H)).status_code == 200
    assert (await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/mo-khoa", headers=H)).status_code == 409
    assert (await client.get("/api/v1/admin/tai-khoan/khong-phai-uuid", headers=H)).status_code == 422
    assert (await client.get(f"/api/v1/admin/tai-khoan/{uuid.uuid4()}", headers=H)).status_code == 404


@tich_hop
async def test_nhat_ky_json_va_csv_cung_so_dong(client, nguoi):
    await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/khoa", json={"ly_do": "a"}, headers=H)
    await client.post(f"/api/v1/admin/tai-khoan/{nguoi}/mo-khoa", headers=H)
    j = (await client.get("/api/v1/admin/nhat-ky", params={"doi_tuong": nguoi, "limit": 100}, headers=H)).json()
    c = await client.get("/api/v1/admin/nhat-ky", params={"doi_tuong": nguoi, "limit": 100, "dinh_dang": "csv"}, headers=H)
    assert c.status_code == 200 and c.headers["content-type"].startswith("text/csv")
    assert "attachment" in c.headers["content-disposition"]
    assert len(c.text.strip().splitlines()) - 1 == j["tong"] == 2


@tich_hop
async def test_tong_quan_va_goi(client, nguoi):
    assert (await client.get("/api/v1/admin/tong-quan", headers=H)).json()["tong_tai_khoan"] >= 1
    g = (await client.get("/api/v1/admin/goi", headers=H)).json()
    assert g["goi_mac_dinh"] == "free" and any(x["ma"] == "pro" and x["ten"] == "Cá nhân" for x in g["goi"])


@tich_hop
async def test_vuot_la_chan_ip_429(client, cai_dat):
    cai_dat(admin_api_key="khoa-thu", rate_limit_so_luot=10, rate_limit_ip_so_luot=2)
    ma = [(await client.get("/api/v1/admin/goi", headers=H)).status_code for _ in range(4)]
    assert 429 in ma


def test_chi_nang_goi_py_moi_UPDATE_users_SET_plan():
    """Bất biến §4.1: một đường đổi gói."""
    mau = re.compile(r"UPDATE\s+users\s+SET\s+plan", re.IGNORECASE)
    vi_pham = [
        str(p) for p in Path("src").rglob("*.py")
        if p.name != "nang_goi.py" and mau.search(p.read_text(encoding="utf-8"))
    ]
    assert vi_pham == [], vi_pham


def test_khong_endpoint_admin_nao_doc_hoi_thoai():
    """Bất biến §5.3: admin thấy bao nhiêu lượt, không thấy hỏi gì."""
    src = Path("src/api/routes_admin.py").read_text(encoding="utf-8")
    assert "luot_hoi_thoai" not in src and "hoi_thoai.chi_tiet" not in src and "hoi_thoai.luot" not in src
```

- [ ] **Bước 3: Đỏ**

Run: `.venv/bin/python -m pytest tests/test_api/test_admin_cong.py tests/test_api/test_admin_routes.py -q` → FAIL 404 (router chưa gắn) và `FileNotFoundError` ở test grep.

- [ ] **Bước 4: `bao_ve.kiem_admin_key`**

Thêm `from src.services import nhat_ky, xac_thuc` (thay dòng import `xac_thuc` hiện có), và sau `kiem_api_key`:

```python
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
```

- [ ] **Bước 5: `routes_admin.py`**

```python
# src/api/routes_admin.py
"""Router `/admin` — đường quản trị cho CMS (spec 2026-09-08 cms-quan-ly-tai-khoan §5.3).

KHÔNG có endpoint nào đọc `hoi_thoai`/`luot_hoi_thoai`: admin thấy bao nhiêu lượt,
không thấy hỏi gì (test grep). KLAW không biết vai trò admin — proxy ở CMS lọc theo
vai trò; KLAW tin CMS và ghi `boi` để truy vết.
"""

import functools
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from starlette.concurrency import run_in_threadpool

from src.models.schemas import (
    DanhSachGoiOut,
    DanhSachNhatKyOut,
    DanhSachTaiKhoanOut,
    DanhSachYeuCauOut,
    DatGoiRequest,
    HoatDongNgay,
    KetQuaGoiOut,
    LyDoRequest,
    PhanLoai,
    TaiKhoanChiTietOut,
    TongQuanOut,
    YeuCauNangGoiOut,
)
from src.services import bao_ve, nang_goi, nhat_ky, tai_khoan_qt
from src.services.bao_ve import kiem_admin_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin")

_LOI_NGHIEP_VU = (
    nang_goi.KhongTonTai,
    nang_goi.DaXuLy,
    nang_goi.TaiKhoanKhoa,
    nang_goi.KhongCoGiDeThuHoi,
    nang_goi.GoiKhongHopLe,
    nang_goi.ChuaCoHoSo,
    tai_khoan_qt.TrangThaiKhongDoi,
    LookupError,
)


def _http(e: Exception) -> HTTPException:
    if isinstance(e, nang_goi.TaiKhoanKhoa):
        return HTTPException(status_code=423, detail="Tài khoản đang bị khoá, mở khoá trước khi duyệt.")
    if isinstance(e, nang_goi.DaXuLy):
        return HTTPException(status_code=409, detail="Yêu cầu này đã được xử lý.")
    if isinstance(e, tai_khoan_qt.TrangThaiKhongDoi):
        return HTTPException(status_code=409, detail="Tài khoản đã ở trạng thái này.")
    if isinstance(e, nang_goi.KhongCoGiDeThuHoi):
        return HTTPException(status_code=409, detail="Tài khoản đang ở gói Miễn phí, không có gì để thu hồi.")
    if isinstance(e, nang_goi.GoiKhongHopLe):
        return HTTPException(status_code=422, detail="Gói không hợp lệ.")
    return HTTPException(status_code=404, detail="Không tìm thấy.")


async def _thuc_hien(hanh_dong: str, doi_tuong: str | None, ctx: dict, fn, *args):
    """Chạy một thao tác ghi; lỗi nghiệp vụ → nhật ký `<hanh_dong>_that_bai` + mã HTTP đúng (§5.3)."""
    try:
        return await run_in_threadpool(fn, *args)
    except _LOI_NGHIEP_VU as e:
        try:
            await run_in_threadpool(
                functools.partial(
                    nhat_ky.ghi, f"{hanh_dong}_that_bai", doi_tuong=doi_tuong,
                    chi_tiet={"loi": type(e).__name__}, boi=ctx["boi"], ip=ctx["ip"],
                )
            )
        except Exception:
            logger.exception("routes_admin: không ghi được nhật ký thất bại")
        raise _http(e) from e


def _yeu_cau_out(r: dict) -> YeuCauNangGoiOut:
    return YeuCauNangGoiOut(**{k: r[k] for k in YeuCauNangGoiOut.model_fields})


@router.get("/tong-quan", response_model=TongQuanOut)
async def tong_quan(ctx: dict = Depends(kiem_admin_key)) -> TongQuanOut:
    return TongQuanOut(**await run_in_threadpool(tai_khoan_qt.tong_quan))


@router.get("/goi", response_model=DanhSachGoiOut)
async def goi(ctx: dict = Depends(kiem_admin_key)) -> DanhSachGoiOut:
    return DanhSachGoiOut(**tai_khoan_qt.danh_sach_goi())


@router.get("/yeu-cau", response_model=DanhSachYeuCauOut)
async def yeu_cau(
    ctx: dict = Depends(kiem_admin_key),
    trang_thai: str | None = Query(None, pattern="^(cho_duyet|da_duyet|tu_choi)$"),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> DanhSachYeuCauOut:
    tong, rows = await run_in_threadpool(tai_khoan_qt.danh_sach_yeu_cau, trang_thai, q, limit, offset)
    items = [{**r, "plan_hieu_luc": bao_ve.plan_hieu_luc_tu(str(r["plan"]), r["plan_het_han"])} for r in rows]
    return DanhSachYeuCauOut.model_validate({"tong": tong, "items": items})


@router.post("/yeu-cau/{id}/duyet", response_model=KetQuaGoiOut)
async def duyet(id: int, ctx: dict = Depends(kiem_admin_key)) -> KetQuaGoiOut:
    r = await _thuc_hien(
        "duyet_yeu_cau", None, ctx, nang_goi.duyet, id, "admin", f"yeu_cau:{id}", ctx["boi"], ctx["ip"]
    )
    return KetQuaGoiOut(sub=r["sub"], plan=r["plan"], plan_het_han=r["plan_het_han"])


@router.post("/yeu-cau/{id}/tu-choi", response_model=YeuCauNangGoiOut)
async def tu_choi(id: int, body: LyDoRequest, ctx: dict = Depends(kiem_admin_key)) -> YeuCauNangGoiOut:
    await _thuc_hien("tu_choi_yeu_cau", None, ctx, nang_goi.tu_choi, id, body.ly_do, ctx["boi"], ctx["ip"])
    r = await run_in_threadpool(tai_khoan_qt.yeu_cau_theo_id, id)
    if r is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy.")
    return _yeu_cau_out(r)


@router.get("/tai-khoan", response_model=DanhSachTaiKhoanOut)
async def tai_khoan(
    ctx: dict = Depends(kiem_admin_key),
    q: str = Query("", max_length=200),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> DanhSachTaiKhoanOut:
    tong, rows = await run_in_threadpool(tai_khoan_qt.tim, q, limit, offset)
    items = [{**r, "plan": bao_ve.plan_hieu_luc_tu(str(r["plan"]), r["plan_het_han"])} for r in rows]
    return DanhSachTaiKhoanOut.model_validate({"tong": tong, "items": items})


@router.get("/tai-khoan/{sub}", response_model=TaiKhoanChiTietOut)
async def chi_tiet(sub: uuid.UUID, ctx: dict = Depends(kiem_admin_key)) -> TaiKhoanChiTietOut:
    d = await run_in_threadpool(tai_khoan_qt.chi_tiet, str(sub))
    if d is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    plan = bao_ve.plan_hieu_luc_tu(d["plan_tho"], d["plan_het_han"])
    return TaiKhoanChiTietOut(
        sub=str(sub), email=d["email"], plan=plan, ten_goi=bao_ve.ten_goi(plan), tao_luc=d["tao_luc"],
        het_han_luc=d["plan_het_han"], so_phien=d["so_phien"], tong_hoi_dap=d["tong_hoi_dap"],
        tong_ban_thao=d["tong_ban_thao"], hoat_dong=[HoatDongNgay(**h) for h in d["hoat_dong"]],
        phan_loai=[PhanLoai(**p) for p in d["phan_loai"]], khoa_luc=d["khoa_luc"], khoa_ly_do=d["khoa_ly_do"],
        yeu_cau=[_yeu_cau_out(y) for y in d["yeu_cau"]],
    )


@router.patch("/tai-khoan/{sub}/goi", response_model=KetQuaGoiOut)
async def dat_goi(sub: uuid.UUID, body: DatGoiRequest, ctx: dict = Depends(kiem_admin_key)) -> KetQuaGoiOut:
    r = await _thuc_hien(
        "dat_goi", str(sub), ctx, nang_goi.dat_goi, str(sub), body.plan, body.so_ngay, ctx["boi"], ctx["ip"]
    )
    return KetQuaGoiOut(**r)


@router.post("/tai-khoan/{sub}/thu-hoi", response_model=KetQuaGoiOut)
async def thu_hoi(sub: uuid.UUID, body: LyDoRequest, ctx: dict = Depends(kiem_admin_key)) -> KetQuaGoiOut:
    r = await _thuc_hien("thu_hoi_goi", str(sub), ctx, nang_goi.thu_hoi, str(sub), body.ly_do, ctx["boi"], ctx["ip"])
    return KetQuaGoiOut(**r)


@router.post("/tai-khoan/{sub}/khoa")
async def khoa(sub: uuid.UUID, body: LyDoRequest, ctx: dict = Depends(kiem_admin_key)) -> dict:
    return await _thuc_hien(
        "khoa_tai_khoan", str(sub), ctx, tai_khoan_qt.khoa, str(sub), body.ly_do, ctx["boi"], ctx["ip"]
    )


@router.post("/tai-khoan/{sub}/mo-khoa")
async def mo_khoa(sub: uuid.UUID, ctx: dict = Depends(kiem_admin_key)) -> dict:
    return await _thuc_hien("mo_khoa_tai_khoan", str(sub), ctx, tai_khoan_qt.mo_khoa, str(sub), ctx["boi"], ctx["ip"])


@router.get("/nhat-ky", response_model=None)
async def nhat_ky_qt(
    ctx: dict = Depends(kiem_admin_key),
    tu: datetime | None = None,
    den: datetime | None = None,
    hanh_dong: str | None = Query(None, max_length=64),
    doi_tuong: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    dinh_dang: str | None = Query(None, pattern="^csv$"),
) -> DanhSachNhatKyOut | Response:
    tong, rows = await run_in_threadpool(
        functools.partial(
            nhat_ky.danh_sach, tu=tu, den=den, hanh_dong=hanh_dong,
            doi_tuong=str(doi_tuong) if doi_tuong else None, limit=limit, offset=offset,
        )
    )
    if dinh_dang == "csv":
        return Response(
            content=nhat_ky.csv(rows),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="nhat-ky-quan-tri.csv"'},
        )
    return DanhSachNhatKyOut.model_validate({"tong": tong, "items": rows})
```

`src/main.py`: thêm `from src.api.routes_admin import router as router_admin` và `app.include_router(router_admin, prefix="/api/v1")` cạnh các dòng 162–170.

- [ ] **Bước 6: Xanh; lint; bộ test rộng**

Run: `.venv/bin/python -m pytest tests/test_api/test_admin_cong.py tests/test_api/test_admin_routes.py -q && .venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check src/api/routes_admin.py src/services/bao_ve.py && .venv/bin/python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py 2>&1 | tail -3`
Expected: xanh; bộ rộng chỉ đỏ ở `test_moi_mau.py` như trước.

- [ ] **Bước 7: Kiểm bằng `curl` (ghi kết quả vào plan)**

Backend chạy với `KLAW_ADMIN_API_KEY=thu` (đặt tạm trong `.env.local`, gỡ sau):

```bash
curl -s -H 'X-Admin-Key: thu' -H 'X-Admin-Boi: qa@klaw.local' localhost:8000/api/v1/admin/tong-quan
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Admin-Key: sai' -H 'X-Admin-Boi: x' localhost:8000/api/v1/admin/goi   # 401
```

- [ ] **Bước 8: Commit**

```bash
git add src/api/routes_admin.py src/main.py src/services/bao_ve.py tests/test_api/test_admin_cong.py tests/test_api/test_admin_routes.py
git commit -m "feat(api): /admin router behind a fail-closed service key with audit logging and CSV export"
```

**Kết thúc giai đoạn 1:** toàn bộ đường quản trị chạy bằng `curl`. Cổng công khai không đổi (bộ test khách, hạn mức, tài khoản xanh).

---
### Task 7b: Lý do bắt buộc cho mọi thao tác đổi trạng thái (bổ sung theo khảo sát 2026-09-08)

Bổ sung sau khảo sát console quản trị (`docs/superpowers/specs/2026-09-08-khao-sat-console-quan-tri-to-chuc-lon.md`, đề xuất A): GitHub bắt ghi lý do cả khi treo lẫn khi bỏ treo tài khoản. KLAW đã bắt lý do ở từ chối, thu hồi, khoá; task này bổ sung cho **mở khoá** và **đặt gói tay**. Lý do đi vào nhật ký (`chi_tiet.ly_do`), KHÔNG đi vào thông báo cho người dùng (lý do đặt gói là ghi chú nội bộ của admin). Chạy sau Task 9, trước Task 10, để Task 13 dựng giao diện trên hợp đồng cuối.

**Files:**
- Modify: `src/models/schemas.py` (`DatGoiRequest`)
- Modify: `src/services/nang_goi.py` (`dat_goi`)
- Modify: `src/services/tai_khoan_qt.py` (`mo_khoa`)
- Modify: `src/api/routes_admin.py` (`dat_goi`, `mo_khoa` handlers)
- Modify: `tests/test_services/test_tai_khoan_qt.py`, `tests/test_api/test_tai_khoan_khoa.py`, `tests/test_api/test_admin_routes.py`, `tests/test_api/test_admin_cong.py` (mọi lời gọi `mo_khoa`/`dat_goi`)
- Spec `docs/superpowers/specs/2026-09-08-cms-quan-ly-tai-khoan-design.md` đã sửa trước khi dispatch (bảng §5.3, §5.2); không sửa thêm.

**Interfaces:**
- Consumes: mọi thứ Task 5–7 đã dựng.
- Produces (hợp đồng mới; đường dẫn và allowlist của Task 10 không đổi):
  - `DatGoiRequest`: thêm `ly_do: str = Field(..., min_length=1, max_length=500)`.
  - `POST /admin/tai-khoan/{sub}/mo-khoa` nhận body `LyDoRequest` (trước đây không có body).
  - `nang_goi.dat_goi(sub, plan, so_ngay, boi, ip=None, *, ly_do: str)` — keyword-only bắt buộc; `chi_tiet` nhật ký thêm `"ly_do"`.
  - `tai_khoan_qt.mo_khoa(sub, ly_do, boi, ip=None)` — cùng hình với `khoa`; `chi_tiet` nhật ký `{"ly_do": ly_do}`.
  - Thông báo người dùng `goi_dat_tay` và `tai_khoan_mo` KHÔNG đổi nội dung.

- [ ] **Bước 1: Cập nhật test (đỏ)**

`tests/test_services/test_tai_khoan_qt.py`: mọi `tai_khoan_qt.mo_khoa(nguoi, BOI)` → `tai_khoan_qt.mo_khoa(nguoi, "Đã xác minh danh tính.", BOI)`; mọi `nang_goi.dat_goi(nguoi, <plan>, <so_ngay>, BOI)` → thêm `ly_do="Hỗ trợ khách hàng."`. Thêm vào `test_khoa_roi_mo_khoa_va_trang_thai_khong_doi`:

```python
    with get_engine().connect() as c:
        ly_do_mo = c.execute(
            text("SELECT chi_tiet->>'ly_do' FROM nhat_ky_quan_tri WHERE boi = :b AND hanh_dong = 'mo_khoa_tai_khoan'"),
            {"b": BOI},
        ).scalar_one()
    assert ly_do_mo == "Đã xác minh danh tính."
```

và vào `test_dat_goi_so_ngay_None_la_vo_thoi_han_va_goi_la` sau lần `dat_goi` đầu:

```python
    with get_engine().connect() as c:
        ly_do_dat = c.execute(
            text(
                "SELECT chi_tiet->>'ly_do' FROM nhat_ky_quan_tri WHERE boi = :b AND hanh_dong = 'dat_goi'"
                " ORDER BY id LIMIT 1"
            ),
            {"b": BOI},
        ).scalar_one()
    assert ly_do_dat == "Hỗ trợ khách hàng."
```

`tests/test_api/test_tai_khoan_khoa.py`: `tai_khoan_qt.mo_khoa(nguoi_khoa, "qa@klaw.local")` → `tai_khoan_qt.mo_khoa(nguoi_khoa, "Kiểm xong.", "qa@klaw.local")`.

`tests/test_api/test_admin_routes.py`: mọi `client.patch(f"/api/v1/admin/tai-khoan/{nguoi}/goi", json={"plan": "pro", "so_ngay": 15}, …)` → thêm `"ly_do": "Hỗ trợ khách hàng."` vào json (lời gọi `{"plan": "vip"}` → `{"plan": "vip", "ly_do": "x"}` để vẫn nhận 422 vì gói lạ, không vì thiếu lý do); mọi `client.post(f"/api/v1/admin/tai-khoan/{nguoi}/mo-khoa", headers=H)` → thêm `json={"ly_do": "Đã xác minh."}`. Thêm hai assert 422: `PATCH …/goi` với `{"plan": "pro", "so_ngay": 15}` (thiếu lý do) → 422; `POST …/mo-khoa` không body → 422.

`tests/test_api/test_admin_cong.py`: hai test `mo-khoa` (KeyError và KhongTonTai) gửi `json={"ly_do": "x"}`; stub `no(sub, boi, ip=None)` → `no(sub, ly_do, boi, ip=None)`.

- [ ] **Bước 2: Chạy, xác nhận đỏ**

Run: `.venv/bin/python -m pytest tests/test_services/test_tai_khoan_qt.py tests/test_api/test_tai_khoan_khoa.py tests/test_api/test_admin_routes.py tests/test_api/test_admin_cong.py -q`
Expected: FAIL — `TypeError` ở `mo_khoa`/`dat_goi` (tham số thừa) và `mo-khoa` không nhận body.

- [ ] **Bước 3: Sửa mã**

`schemas.py`:

```python
class DatGoiRequest(BaseModel):
    plan: str = Field(..., min_length=1, max_length=32)
    so_ngay: int | None = Field(default=None, ge=1, le=3650)  # None + gói trả phí = vô thời hạn
    ly_do: str = Field(..., min_length=1, max_length=500)  # ghi chú nội bộ, chỉ vào nhật ký
```

`nang_goi.dat_goi`: chữ ký `def dat_goi(sub: str, plan: str, so_ngay: int | None, boi: str, ip: str | None = None, *, ly_do: str) -> dict:`; trong `chi_tiet` của `nhat_ky.ghi("dat_goi", …)` thêm `"ly_do": ly_do`. Docstring thêm: "`ly_do` là ghi chú nội bộ (GitHub bắt lý do cả khi bỏ treo) — chỉ vào nhật ký, không vào thông báo."

`tai_khoan_qt.mo_khoa`: chữ ký `def mo_khoa(sub: str, ly_do: str, boi: str, ip: str | None = None) -> dict:`; `nhat_ky.ghi("mo_khoa_tai_khoan", doi_tuong=sub, chi_tiet={"ly_do": ly_do}, …)`.

`routes_admin.py`:

```python
@router.patch("/tai-khoan/{sub}/goi", response_model=KetQuaGoiOut)
async def dat_goi(sub: uuid.UUID, body: DatGoiRequest, ctx: dict = Depends(kiem_admin_key)) -> KetQuaGoiOut:
    r = await _thuc_hien(
        "dat_goi",
        str(sub),
        ctx,
        functools.partial(nang_goi.dat_goi, str(sub), body.plan, body.so_ngay, ctx["boi"], ctx["ip"], ly_do=body.ly_do),
    )
    return KetQuaGoiOut(**r)


@router.post("/tai-khoan/{sub}/mo-khoa")
async def mo_khoa(sub: uuid.UUID, body: LyDoRequest, ctx: dict = Depends(kiem_admin_key)) -> dict:
    return await _thuc_hien(
        "mo_khoa_tai_khoan", str(sub), ctx, tai_khoan_qt.mo_khoa, str(sub), body.ly_do, ctx["boi"], ctx["ip"]
    )
```

`_thuc_hien(hanh_dong, doi_tuong, ctx, fn, *args)` gọi `run_in_threadpool(fn, *args)` — truyền `functools.partial` làm `fn` với `args` rỗng là hợp lệ.

- [ ] **Bước 4: Xanh; lint; suite rộng**

Run: `.venv/bin/python -m pytest tests/test_services/test_tai_khoan_qt.py tests/test_api/test_tai_khoan_khoa.py tests/test_api/test_admin_routes.py tests/test_api/test_admin_cong.py -q && .venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check src/models/schemas.py src/services/nang_goi.py src/services/tai_khoan_qt.py src/api/routes_admin.py && KLAW_SUPABASE_URL= .venv/bin/python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py --deselect tests/test_services/test_moi_mau.py -p no:cacheprovider 2>&1 | tail -2`
Expected: xanh; suite rộng 0 failed như mốc sau Task 7.

- [ ] **Bước 5: Commit**

```bash
git add src/models/schemas.py src/services/nang_goi.py src/services/tai_khoan_qt.py src/api/routes_admin.py tests/test_services/test_tai_khoan_qt.py tests/test_api/test_tai_khoan_khoa.py tests/test_api/test_admin_routes.py tests/test_api/test_admin_cong.py
git commit -m "feat(admin): require a reason for unlock and manual plan changes, recorded in the audit log"
```

---

## Giai đoạn 2 — CMS Payload (`cms/`)

Chạy song song với giai đoạn 1 ở worktree riêng sau Task 1 (bảng endpoint §5.3 là hợp đồng chung). Task 12–14 cần KLAW của giai đoạn 1 chạy ở `:8000` để kiểm bằng tay; test vitest thì không.

### Task 8: Scaffold `cms/` với Payload 3.88.0, collection `admins`, khung test

**Files:**
- Create: `cms/package.json`, `cms/payload.config.ts`, `cms/next.config.mjs`, `cms/tsconfig.json`, `cms/vitest.config.ts`, `cms/.env.example`, `cms/.gitignore`, `cms/app/(payload)/…` (sinh bởi template), `cms/src/access/vaiTro.ts`, `cms/src/collections/Admins.ts`, `cms/tests/setup.ts`, `cms/tests/helpers/payload.ts`
- Test: `cms/tests/admins.spec.ts`, `cms/tests/config.spec.ts`

**Interfaces:**
- Produces:
  - `src/access/vaiTro.ts`: `type Admin = { id: number | string; email: string; vai_tro: 'doc' | 'quan_tri'; hoat_dong?: boolean | null }`; `dangHoatDong(u: unknown): u is Admin`; `laQuanTri(u: unknown): boolean`; `Access` `adminHoatDong`, `chiQuanTri`, `quanTriHoacChinhMinh`; `FieldAccess` `truongChiQuanTri`.
  - Collection slug `admins`; `payload.config.ts` xuất `default buildConfig(...)`; alias `@payload-config`, `@/*` → `src/*`.
  - `tests/helpers/payload.ts`: `getTestPayload(): Promise<Payload>`; `taoAdmin(payload, {email?, vai_tro, hoat_dong?})` (mật khẩu `MAT_KHAU = 'test1234'`); `stamp()`.

- [ ] **Bước 1: Tạo database và scaffold**

```bash
createdb -h localhost -U postgres klaw_cms
createdb -h localhost -U postgres klaw_cms_test
cd /Users/kenz_de/projects/KLAW
pnpm dlx create-payload-app@latest cms -t blank --db postgres \
  --db-connection-string 'postgres://postgres:postgres@localhost:5432/klaw_cms' --use-pnpm --no-deps
```

Nếu cờ khác (`pnpm dlx create-payload-app@latest --help`), giữ đúng ba ý: tên `cms`, template `blank`, Postgres. Nếu `createdb` cần tài khoản khác, lấy user/host/port từ `DATABASE_URL` trong `.env.local` của KLAW (không lấy tên database).

- [ ] **Bước 2: Ghim phiên bản, gỡ thứ không dùng, script**

`cms/package.json`:

```json
{
  "name": "klaw-cms",
  "private": true,
  "type": "module",
  "packageManager": "pnpm@9.15.9",
  "engines": { "node": ">=20.0.0" },
  "scripts": {
    "dev": "next dev -p 3001",
    "build": "next build",
    "start": "bash scripts/start.sh",
    "payload": "payload",
    "migrate": "payload migrate",
    "migrate:create": "payload migrate:create",
    "lint": "eslint .",
    "type-check": "tsc --noEmit",
    "test": "TZ=Asia/Ho_Chi_Minh vitest run"
  },
  "dependencies": {
    "@payloadcms/db-postgres": "3.88.0",
    "@payloadcms/next": "3.88.0",
    "@payloadcms/translations": "3.88.0",
    "@payloadcms/ui": "3.88.0",
    "payload": "3.88.0",
    "next": "<đúng bản 15.x template ghi, bỏ dấu ^>",
    "react": "<bản template, bỏ ^>",
    "react-dom": "<bản template, bỏ ^>",
    "graphql": "<bản template>"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "eslint": "^9",
    "eslint-config-next": "<khớp next>",
    "typescript": "5.9.3",
    "vitest": "^3"
  }
}
```

Bốn chỗ `<…>` là số template đã ghi — chép đúng số, bỏ `^`. Gỡ `sharp`, `@payloadcms/richtext-lexical`, collection `media` khỏi template. `pnpm install`.

`cms/.gitignore`: `node_modules/`, `.next/`, `.env`, `.env.test`. Commit `src/payload-types.ts` và `app/(payload)/admin/importMap.js` (Payload sinh, cần cho build).

`cms/.env.example`:

```
DATABASE_URI=postgres://postgres:postgres@localhost:5432/klaw_cms
PAYLOAD_SECRET=doi-bang-openssl-rand-hex-32
PAYLOAD_PUBLIC_SERVER_URL=
KLAW_API_URL=http://127.0.0.1:8000/api/v1
KLAW_ADMIN_API_KEY=cung-gia-tri-voi-.env.local-cua-KLAW
```

- [ ] **Bước 3: `payload.config.ts`**

```ts
// cms/payload.config.ts
import path from 'path'
import { fileURLToPath } from 'url'
import { buildConfig } from 'payload'
import { postgresAdapter } from '@payloadcms/db-postgres'
import { en } from '@payloadcms/translations/languages/en'
import { vi } from '@payloadcms/translations/languages/vi'

import { Admins } from './src/collections/Admins'

const dirname = path.dirname(fileURLToPath(import.meta.url))

// Gốc công khai: Railway bơm RAILWAY_PUBLIC_DOMAIN; PAYLOAD_PUBLIC_SERVER_URL ghi đè cho
// host khác. Local để trống → URL tương đối.
const serverURL =
  process.env.PAYLOAD_PUBLIC_SERVER_URL ??
  (process.env.RAILWAY_PUBLIC_DOMAIN ? `https://${process.env.RAILWAY_PUBLIC_DOMAIN}` : '')
const laProd = process.env.NODE_ENV === 'production'
const origins = laProd ? [serverURL].filter(Boolean) : ['http://localhost:3001', 'http://127.0.0.1:3001']

export default buildConfig({
  admin: {
    user: 'admins',
    meta: { titleSuffix: '— KLAW quản trị' },
    components: {},
  },
  i18n: { supportedLanguages: { vi, en }, fallbackLanguage: 'vi' },
  serverURL,
  cors: origins,
  // Dev để RỖNG: allowlist csrf làm rớt phiên trên LAN plain-HTTP (kinh nghiệm dự án
  // tham chiếu). Production phải có allowlist.
  csrf: laProd ? origins : [],
  collections: [Admins],
  graphQL: { disable: true },
  // Database RIÊNG `klaw_cms` (spec §4.2). KHÔNG đặt schemaName. KHÔNG bao giờ trỏ vào
  // database `klaw` — tests/config.spec.ts khẳng định.
  db: postgresAdapter({
    pool: { connectionString: process.env.DATABASE_URI },
    migrationDir: path.resolve(dirname, 'migrations'),
  }),
  secret: process.env.PAYLOAD_SECRET || '',
  typescript: { outputFile: path.resolve(dirname, 'src/payload-types.ts') },
})
```

- [ ] **Bước 4: Khung test và test `admins` (đỏ)**

`cms/vitest.config.ts`:

```ts
import path from 'path'
import { fileURLToPath } from 'url'
import { defineConfig } from 'vitest/config'

const dirname = path.dirname(fileURLToPath(import.meta.url))
export default defineConfig({
  resolve: {
    alias: { '@payload-config': path.resolve(dirname, './payload.config.ts'), '@': path.resolve(dirname, './src') },
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.spec.ts'],
    setupFiles: ['./tests/setup.ts'],
    fileParallelism: false, // Payload mở pool Postgres — song song là tranh chấp
    testTimeout: 60_000,
    hookTimeout: 60_000,
  },
})
```

`cms/tests/setup.ts`:

```ts
process.env.DATABASE_URI ??= 'postgres://postgres:postgres@localhost:5432/klaw_cms_test'
process.env.PAYLOAD_SECRET ??= 'bi-mat-test-khong-dung-o-dau-khac'
process.env.KLAW_API_URL ??= 'http://klaw.test/api/v1'
process.env.KLAW_ADMIN_API_KEY ??= 'khoa-test'
```

`cms/tests/helpers/payload.ts`:

```ts
import { getPayload, type Payload } from 'payload'
import config from '@payload-config'

let cached: Promise<Payload> | undefined
export const getTestPayload = (): Promise<Payload> => (cached ??= getPayload({ config }))

export const MAT_KHAU = 'test1234'
export const stamp = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

export const taoAdmin = async (payload: Payload, d: { email?: string; vai_tro: 'doc' | 'quan_tri'; hoat_dong?: boolean }) =>
  payload.create({
    collection: 'admins',
    data: { email: d.email ?? `${stamp()}@klaw.test`, password: MAT_KHAU, ten: 'Test', vai_tro: d.vai_tro, hoat_dong: d.hoat_dong ?? true },
    overrideAccess: true,
  })
```

`cms/tests/admins.spec.ts`:

```ts
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import type { Payload } from 'payload'
import { MAT_KHAU, getTestPayload, stamp, taoAdmin } from './helpers/payload'

let payload: Payload
const rac: (number | string)[] = []
beforeAll(async () => { payload = await getTestPayload() })
afterAll(async () => {
  for (const id of rac.reverse()) await payload.delete({ collection: 'admins', id, overrideAccess: true }).catch(() => undefined)
})

describe('admins (spec 2B §6.2)', () => {
  it('doc không đổi được vai_tro và hoat_dong của chính mình, đổi được tên', async () => {
    const doc = await taoAdmin(payload, { vai_tro: 'doc' }); rac.push(doc.id)
    const qt = await taoAdmin(payload, { vai_tro: 'quan_tri' }); rac.push(qt.id)
    const sau = await payload.update({ collection: 'admins', id: doc.id, data: { ten: 'Đổi', vai_tro: 'quan_tri', hoat_dong: false }, user: doc, overrideAccess: false })
    expect(sau.ten).toBe('Đổi'); expect(sau.vai_tro).toBe('doc'); expect(sau.hoat_dong).toBe(true)
  })

  it('doc không tạo và không xoá admin khác', async () => {
    const doc = await taoAdmin(payload, { vai_tro: 'doc' }); rac.push(doc.id)
    const qt = await taoAdmin(payload, { vai_tro: 'quan_tri' }); rac.push(qt.id)
    await expect(payload.create({ collection: 'admins', data: { email: `${stamp()}@klaw.test`, password: MAT_KHAU, ten: 'x', vai_tro: 'doc' }, user: doc, overrideAccess: false })).rejects.toThrow()
    await expect(payload.delete({ collection: 'admins', id: qt.id, user: doc, overrideAccess: false })).rejects.toThrow()
  })

  it('không hạ vai trò, vô hiệu hay xoá quản trị viên cuối cùng', async () => {
    const khac = await payload.find({ collection: 'admins', where: { vai_tro: { equals: 'quan_tri' } }, limit: 100, overrideAccess: true })
    const cuoi = await taoAdmin(payload, { vai_tro: 'quan_tri' }); rac.push(cuoi.id)
    for (const a of khac.docs) await payload.update({ collection: 'admins', id: a.id, data: { vai_tro: 'doc' }, overrideAccess: true })
    await expect(payload.update({ collection: 'admins', id: cuoi.id, data: { vai_tro: 'doc' }, overrideAccess: true })).rejects.toThrow(/cuối cùng/)
    await expect(payload.update({ collection: 'admins', id: cuoi.id, data: { hoat_dong: false }, overrideAccess: true })).rejects.toThrow(/cuối cùng/)
    await expect(payload.delete({ collection: 'admins', id: cuoi.id, overrideAccess: true })).rejects.toThrow(/cuối cùng/)
    for (const a of khac.docs) await payload.update({ collection: 'admins', id: a.id, data: { vai_tro: 'quan_tri' }, overrideAccess: true })
  })

  it('hoat_dong=false không đăng nhập được; 5 lần sai thì khoá', async () => {
    const tat = await taoAdmin(payload, { vai_tro: 'doc', hoat_dong: false }); rac.push(tat.id)
    await expect(payload.login({ collection: 'admins', data: { email: tat.email, password: MAT_KHAU } })).rejects.toThrow()
    const a = await taoAdmin(payload, { vai_tro: 'doc' }); rac.push(a.id)
    for (let i = 0; i < 5; i++) await payload.login({ collection: 'admins', data: { email: a.email, password: 'sai' } }).catch(() => undefined)
    await expect(payload.login({ collection: 'admins', data: { email: a.email, password: MAT_KHAU } })).rejects.toThrow()
  })

  it('người đầu tiên luôn là quan_tri (hook ép khi collection rỗng)', async () => {
    // Không xoá dữ liệu thật của DB test; kiểm hook qua Local API với `overrideAccess` trên
    // DB đã có admin thì hook KHÔNG ép — nên chỉ khẳng định nhánh "đã có admin" ở đây, và
    // nhánh "rỗng" được kiểm bằng tay ở bước 8 (create-first-user).
    const a = await taoAdmin(payload, { vai_tro: 'doc' }); rac.push(a.id)
    expect(a.vai_tro).toBe('doc')
  })
})
```

`cms/tests/config.spec.ts`:

```ts
import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

describe('cấu hình (spec §0.1, §0.2)', () => {
  it('không đặt schemaName; không chuỗi kết nối nào tới database klaw', () => {
    const goc = path.resolve(__dirname, '..')
    const tep = ['payload.config.ts', '.env.example', 'tests/setup.ts'].map((t) => fs.readFileSync(path.join(goc, t), 'utf8')).join('\n')
    expect(tep).not.toMatch(/schemaName/)
    expect(tep).not.toMatch(/5432\/klaw(["'\s]|$)/m)
  })
  it('ghim đúng payload 3.88.0', () => {
    const pkg = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../package.json'), 'utf8'))
    for (const k of ['payload', '@payloadcms/next', '@payloadcms/db-postgres', '@payloadcms/ui', '@payloadcms/translations'])
      expect(pkg.dependencies[k]).toBe('3.88.0')
  })
})
```

- [ ] **Bước 5: Đỏ**

Run: `cd cms && pnpm test` → FAIL (collection `admins` chưa có trường `vai_tro`).

- [ ] **Bước 6: `vaiTro.ts` và `Admins.ts`**

```ts
// cms/src/access/vaiTro.ts
import type { Access, FieldAccess } from 'payload'

export type Admin = { id: number | string; email: string; vai_tro: 'doc' | 'quan_tri'; hoat_dong?: boolean | null }

export const dangHoatDong = (u: unknown): u is Admin =>
  typeof u === 'object' && u !== null && typeof (u as Admin).email === 'string' && (u as Admin).hoat_dong !== false
export const laQuanTri = (u: unknown): boolean => dangHoatDong(u) && u.vai_tro === 'quan_tri'

export const adminHoatDong: Access = ({ req }) => dangHoatDong(req.user)
export const chiQuanTri: Access = ({ req }) => laQuanTri(req.user)
export const quanTriHoacChinhMinh: Access = ({ req, id }) =>
  laQuanTri(req.user) || (dangHoatDong(req.user) && id !== undefined && String(req.user.id) === String(id))
export const truongChiQuanTri: FieldAccess = ({ req }) => laQuanTri(req.user)
```

```ts
// cms/src/collections/Admins.ts
import { APIError, type CollectionConfig, type PayloadRequest } from 'payload'
import { adminHoatDong, chiQuanTri, dangHoatDong, quanTriHoacChinhMinh, truongChiQuanTri } from '../access/vaiTro'

const QUAN_TRI_CUOI = 'Không thể hạ vai trò, vô hiệu hay xoá quản trị viên cuối cùng.'

/** Số quản trị viên đang hoạt động KHÁC `truId`. */
const soQuanTriKhac = async (req: PayloadRequest, truId: unknown): Promise<number> => {
  const { totalDocs } = await req.payload.count({
    collection: 'admins',
    where: { and: [{ vai_tro: { equals: 'quan_tri' } }, { hoat_dong: { not_equals: false } }, { id: { not_equals: truId } }] },
    overrideAccess: true,
  })
  return totalDocs
}

export const Admins: CollectionConfig = {
  slug: 'admins',
  labels: { singular: { vi: 'Quản trị viên', en: 'Admin' }, plural: { vi: 'Quản trị viên', en: 'Admins' } },
  auth: {
    tokenExpiration: 8 * 60 * 60, // một ca làm việc
    maxLoginAttempts: 5,
    lockTime: 10 * 60 * 1000,
    cookies: { secure: process.env.NODE_ENV === 'production', sameSite: 'Lax' },
  },
  versions: false,
  admin: { useAsTitle: 'email', defaultColumns: ['email', 'ten', 'vai_tro', 'hoat_dong'], group: { vi: 'Hệ thống', en: 'System' } },
  access: {
    admin: ({ req }) => dangHoatDong(req.user),
    read: adminHoatDong,
    create: chiQuanTri,
    update: quanTriHoacChinhMinh,
    delete: chiQuanTri,
  },
  hooks: {
    beforeLogin: [
      ({ user }) => {
        if ((user as { hoat_dong?: boolean | null }).hoat_dong === false) throw new APIError('Tài khoản quản trị này đã bị vô hiệu.', 403)
      },
    ],
    beforeChange: [
      async ({ data, operation, originalDoc, req }) => {
        if (operation === 'create') {
          const { totalDocs } = await req.payload.count({ collection: 'admins', overrideAccess: true })
          if (totalDocs === 0) data.vai_tro = 'quan_tri' // create-first-user phải quản trị được
          return data
        }
        const haCap = originalDoc?.vai_tro === 'quan_tri' && (data.vai_tro === 'doc' || data.hoat_dong === false)
        if (haCap && (await soQuanTriKhac(req, originalDoc.id)) === 0) throw new APIError(QUAN_TRI_CUOI, 400)
        return data
      },
    ],
    beforeDelete: [
      async ({ id, req }) => {
        const doc = await req.payload.findByID({ collection: 'admins', id, overrideAccess: true })
        if (doc.vai_tro === 'quan_tri' && (await soQuanTriKhac(req, id)) === 0) throw new APIError(QUAN_TRI_CUOI, 400)
      },
    ],
  },
  fields: [
    { name: 'ten', type: 'text', required: true, label: { vi: 'Tên', en: 'Name' } },
    {
      name: 'vai_tro',
      type: 'select',
      required: true,
      defaultValue: 'doc',
      label: { vi: 'Vai trò', en: 'Role' },
      options: [
        { label: { vi: 'Chỉ xem', en: 'Viewer' }, value: 'doc' },
        { label: { vi: 'Quản trị', en: 'Admin' }, value: 'quan_tri' },
      ],
      access: { update: truongChiQuanTri },
    },
    { name: 'hoat_dong', type: 'checkbox', defaultValue: true, label: { vi: 'Đang hoạt động', en: 'Active' }, access: { update: truongChiQuanTri } },
  ],
}
```

Field-level `access.update` trả `false` làm Payload **bỏ qua** giá trị gửi lên (không ném lỗi) — đúng như test kỳ vọng. Chạy `pnpm payload generate:types`.

- [ ] **Bước 7: Xanh; lint; type-check; dev lên**

Run: `cd cms && pnpm test && pnpm lint && pnpm type-check`. Rồi `pnpm dev` → `http://localhost:3001/admin` → tạo người đầu tiên trên `klaw_cms` trống → list `admins` cho thấy `vai_tro = quan_tri`. Ảnh `.tham-dinh-shots/cms-00-first-user.png`. Dừng dev.

- [ ] **Bước 8: Commit**

```bash
git add cms
git commit -m "feat(cms): scaffold Payload 3.88 admin app on its own database with a two-role admins collection"
```

---

### Task 9: `nhat_ky_cms` và hook đăng nhập

**Files:**
- Create: `cms/src/collections/NhatKyCms.ts`, `cms/src/hooks/nhatKyCms.ts`, `cms/src/hooks/exposeErrorReason.ts`
- Modify: `cms/payload.config.ts` (`collections`, `hooks.afterError`), `cms/src/collections/Admins.ts` (`hooks.afterLogin`, `afterLogout`)
- Test: `cms/tests/nhat-ky-cms.spec.ts`

**Interfaces:**
- Produces:
  - Collection `nhat_ky_cms`: `hanh_dong: text`, `boi: text`, `ip: text?`, `chi_tiet: json`; thời điểm = `createdAt`.
  - `ghiNhatKyCms(payload: Payload, d: { hanh_dong: string; boi: string; ip?: string | null; chi_tiet?: Record<string, unknown> }): Promise<void>` — không ném.
  - `ipCua(req: Pick<PayloadRequest, 'headers'>): string | null` — phần tử cuối `x-forwarded-for` hoặc null.
  - `ghiDangNhapThatBai` — hook `afterError` cấp config.

- [ ] **Bước 1: Test (đỏ)**

```ts
// cms/tests/nhat-ky-cms.spec.ts
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import type { Payload } from 'payload'
import { getTestPayload, taoAdmin } from './helpers/payload'
import { ghiDangNhapThatBai, ghiNhatKyCms, ipCua } from '../src/hooks/nhatKyCms'

let payload: Payload
const rac: (number | string)[] = []
beforeAll(async () => { payload = await getTestPayload() })
afterAll(async () => { for (const id of rac) await payload.delete({ collection: 'admins', id, overrideAccess: true }).catch(() => undefined) })

describe('nhat_ky_cms (spec §6.3)', () => {
  it('không ai tạo/sửa/xoá qua access; admin hoạt động đọc được', async () => {
    const doc = await taoAdmin(payload, { vai_tro: 'doc' }); rac.push(doc.id)
    await expect(payload.create({ collection: 'nhat_ky_cms', data: { hanh_dong: 'x', boi: 'a' }, user: doc, overrideAccess: false })).rejects.toThrow()
    await ghiNhatKyCms(payload, { hanh_dong: 'thu', boi: 'qa@klaw.test' })
    const r = await payload.find({ collection: 'nhat_ky_cms', where: { hanh_dong: { equals: 'thu' } }, user: doc, overrideAccess: false })
    expect(r.totalDocs).toBeGreaterThan(0)
    await expect(payload.update({ collection: 'nhat_ky_cms', id: r.docs[0].id, data: { boi: 'khac' }, user: doc, overrideAccess: false })).rejects.toThrow()
    await expect(payload.delete({ collection: 'nhat_ky_cms', id: r.docs[0].id, user: doc, overrideAccess: false })).rejects.toThrow()
  })

  it('afterError trên /api/admins/login với 401 ghi dang_nhap_that_bai kèm email và IP', async () => {
    const req = { payload, url: 'http://cms.local/api/admins/login', headers: new Headers({ 'x-forwarded-for': '1.2.3.4' }), data: { email: 'sai@klaw.test' } }
    await ghiDangNhapThatBai({ error: Object.assign(new Error('x'), { status: 401 }), req } as never)
    const r = await payload.find({ collection: 'nhat_ky_cms', where: { and: [{ hanh_dong: { equals: 'dang_nhap_that_bai' } }, { boi: { equals: 'sai@klaw.test' } }] }, sort: '-createdAt', overrideAccess: true })
    expect(r.totalDocs).toBeGreaterThan(0); expect(r.docs[0].ip).toBe('1.2.3.4')
    expect(ipCua({ headers: new Headers() } as never)).toBeNull()
  })

  it('afterError trên đường khác không ghi gì', async () => {
    const truoc = (await payload.count({ collection: 'nhat_ky_cms', overrideAccess: true })).totalDocs
    await ghiDangNhapThatBai({ error: Object.assign(new Error('x'), { status: 401 }), req: { payload, url: 'http://cms.local/api/admins/me', headers: new Headers() } } as never)
    expect((await payload.count({ collection: 'nhat_ky_cms', overrideAccess: true })).totalDocs).toBe(truoc)
  })
})
```

- [ ] **Bước 2: Đỏ** — `pnpm test` → FAIL (module chưa có).

- [ ] **Bước 3: Collection và hook**

```ts
// cms/src/collections/NhatKyCms.ts
import type { CollectionConfig } from 'payload'
import { adminHoatDong } from '../access/vaiTro'

/** Nhật ký PHÍA CMS (spec §6.3): đăng nhập, đăng nhập sai, bản sao thao tác ghi qua proxy.
 *  Bản pháp lý nằm ở KLAW (`nhat_ky_quan_tri`); bảng này để tra trên giao diện. Chỉ hook ghi
 *  (`overrideAccess: true`); mọi đường access ghi đều đóng. */
export const NhatKyCms: CollectionConfig = {
  slug: 'nhat_ky_cms',
  labels: { singular: { vi: 'Nhật ký CMS', en: 'CMS log' }, plural: { vi: 'Nhật ký CMS', en: 'CMS logs' } },
  versions: false,
  admin: { hidden: true, useAsTitle: 'hanh_dong', defaultColumns: ['createdAt', 'hanh_dong', 'boi', 'ip'] },
  access: { read: adminHoatDong, create: () => false, update: () => false, delete: () => false },
  fields: [
    { name: 'hanh_dong', type: 'text', required: true, index: true },
    { name: 'boi', type: 'text', required: true, index: true },
    { name: 'ip', type: 'text' },
    { name: 'chi_tiet', type: 'json' },
  ],
}
```

```ts
// cms/src/hooks/nhatKyCms.ts
import type { Config, Payload, PayloadRequest } from 'payload'

type AfterErrorHook = NonNullable<NonNullable<Config['hooks']>['afterError']>[number]

export const ipCua = (req: Pick<PayloadRequest, 'headers'>): string | null => {
  const xff = req.headers?.get?.('x-forwarded-for') ?? ''
  const phan = xff.split(',').map((s) => s.trim()).filter(Boolean)
  return phan.length > 0 ? phan[phan.length - 1] : null
}

/** Ghi một dòng; KHÔNG ném — một dòng nhật ký hỏng không được làm hỏng thao tác chính. */
export const ghiNhatKyCms = async (
  payload: Payload,
  d: { hanh_dong: string; boi: string; ip?: string | null; chi_tiet?: Record<string, unknown> },
): Promise<void> => {
  try {
    await payload.create({
      collection: 'nhat_ky_cms',
      data: { hanh_dong: d.hanh_dong, boi: d.boi, ip: d.ip ?? null, chi_tiet: d.chi_tiet ?? {} },
      overrideAccess: true,
    })
  } catch (error) {
    payload.logger.warn({ err: error }, 'nhat_ky_cms: không ghi được')
  }
}

/** `afterError` cấp config: lỗi 401/423 trên `/api/admins/login` = đăng nhập sai hoặc bị khoá
 *  (spec §6.3). Chuỗi thất bại liên tiếp là tín hiệu dò mật khẩu — thông lệ audit log của OpenAI. */
export const ghiDangNhapThatBai: AfterErrorHook = async ({ error, req }) => {
  const url = (req as { url?: string }).url ?? ''
  const status = (error as { status?: number }).status
  if (!url.includes('/api/admins/login') || (status !== 401 && status !== 423)) return
  const data = (req as { data?: { email?: unknown } }).data
  const email = typeof data?.email === 'string' ? data.email : '(không rõ)'
  await ghiNhatKyCms(req.payload, { hanh_dong: 'dang_nhap_that_bai', boi: email, ip: ipCua(req), chi_tiet: { status } })
}
```

`exposeErrorReason.ts`: chép từ `~/VF_TTS/vsf-cms-multiple-sites-backend/src/payload/hooks/exposeErrorReason.ts` nguyên văn; nếu kiểu khác giữa 4-canary và 3.88, `pnpm type-check` chỉ chỗ sửa.

`payload.config.ts`: `collections: [Admins, NhatKyCms]`, `hooks: { afterError: [exposeErrorReason, ghiDangNhapThatBai] }`.

`Admins.ts` thêm vào `hooks`:

```ts
    afterLogin: [async ({ req, user }) => { await ghiNhatKyCms(req.payload, { hanh_dong: 'dang_nhap', boi: user.email, ip: ipCua(req) }) }],
    afterLogout: [async ({ req }) => { if (req.user) await ghiNhatKyCms(req.payload, { hanh_dong: 'dang_xuat', boi: req.user.email, ip: ipCua(req) }) }],
```

- [ ] **Bước 4: Xanh; lint; type-check**

Run: `cd cms && pnpm test && pnpm lint && pnpm type-check`.

- [ ] **Bước 5: Commit**

```bash
git add cms
git commit -m "feat(cms): hook-written CMS log with login, logout and failed-login entries"
```

---

### Task 10: Allowlist và proxy `/api/klaw/*`

**Files:**
- Create: `cms/src/lib/allowlist.ts`, `cms/src/lib/klaw-client.ts`, `cms/src/endpoints/klaw.ts`
- Modify: `cms/payload.config.ts` (`endpoints: klawEndpoints`)
- Test: `cms/tests/allowlist.spec.ts`, `cms/tests/proxy.spec.ts`

**Interfaces:**
- Produces:
  - `allowlist.ts`: `type VaiTro = 'doc' | 'quan_tri'`; `type Hang = { method: 'get' | 'post' | 'patch'; duong: string; vaiTro: VaiTro; sse?: boolean; hanhDong?: string }`; `ALLOWLIST: readonly Hang[]` (15 hàng §5.3); `UUID_RE`; `dienDuong(mau, params) -> string`.
  - `klaw-client.ts`: `goiKlaw(y: { method: string; duong: string; body?: string; boi: string; ip?: string | null; sse?: boolean }, fetchFn = fetch): Promise<Response>` — 503 khi thiếu env, 502 khi không nối được.
  - `endpoints/klaw.ts`: `quyetDinh(user, hang, params) -> 401 | 403 | 404 | null`; `taoEndpoint(hang) -> Endpoint`; `klawEndpoints: Endpoint[]`.
  - Client (Task 11) gọi `/api/klaw/<duong>` cùng gốc; SSE ở `/api/klaw/thong-bao/luong`.

- [ ] **Bước 1: Test (đỏ)**

```ts
// cms/tests/allowlist.spec.ts
import { describe, expect, it } from 'vitest'
import { ALLOWLIST, UUID_RE, dienDuong } from '../src/lib/allowlist'

describe('allowlist (spec §5.3, §6.4)', () => {
  it('có đủ 15 hàng đúng method/đường; mọi thao tác ghi ngoài thông báo cần quan_tri', () => {
    expect(ALLOWLIST.map((h) => `${h.method} ${h.duong}`).sort()).toEqual([
      'get /goi', 'get /nhat-ky', 'get /tai-khoan', 'get /tai-khoan/:sub', 'get /thong-bao', 'get /thong-bao/luong', 'get /tong-quan', 'get /yeu-cau',
      'patch /tai-khoan/:sub/goi',
      'post /tai-khoan/:sub/khoa', 'post /tai-khoan/:sub/mo-khoa', 'post /tai-khoan/:sub/thu-hoi', 'post /thong-bao/da-doc', 'post /yeu-cau/:id/duyet', 'post /yeu-cau/:id/tu-choi',
    ])
    expect(ALLOWLIST.filter((h) => h.method !== 'get' && !h.duong.startsWith('/thong-bao')).every((h) => h.vaiTro === 'quan_tri')).toBe(true)
    expect(ALLOWLIST.find((h) => h.duong === '/thong-bao/luong')?.sse).toBe(true)
  })
  it('dienDuong thay tham số và mã hoá; UUID_RE', () => {
    expect(dienDuong('/tai-khoan/:sub/khoa', { sub: 'abc' })).toBe('/tai-khoan/abc/khoa')
    expect(dienDuong('/yeu-cau/:id/duyet', { id: '5 6' })).toBe('/yeu-cau/5%206/duyet')
    expect(UUID_RE.test('7c9e6679-7425-40de-944b-e07fc1f90ae7')).toBe(true)
    expect(UUID_RE.test('khong-phai')).toBe(false)
  })
})
```

```ts
// cms/tests/proxy.spec.ts
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import type { Payload } from 'payload'
import { ALLOWLIST } from '../src/lib/allowlist'
import { quyetDinh, taoEndpoint } from '../src/endpoints/klaw'
import { getTestPayload } from './helpers/payload'

const DOC = { id: 1, email: 'doc@klaw.test', vai_tro: 'doc', hoat_dong: true }
const QT = { id: 2, email: 'qt@klaw.test', vai_tro: 'quan_tri', hoat_dong: true }
const SUB = '7c9e6679-7425-40de-944b-e07fc1f90ae7'
const hang = (d: string) => ALLOWLIST.find((h) => h.duong === d)!
let payload: Payload
beforeAll(async () => { payload = await getTestPayload() })
afterEach(() => vi.unstubAllGlobals())

const req = (user: unknown, url: string, params: Record<string, string>, body = '') =>
  ({ user, url, routeParams: params, headers: new Headers({ 'x-forwarded-for': '9.9.9.9' }), text: async () => body, payload }) as never

describe('proxy (spec §6.4)', () => {
  it('quyetDinh: 401 không phiên, 403 doc ghi, 404 sub sai, null khi hợp lệ', () => {
    expect(quyetDinh(null, hang('/tong-quan'), {})).toBe(401)
    expect(quyetDinh({ ...DOC, hoat_dong: false }, hang('/tong-quan'), {})).toBe(401)
    expect(quyetDinh(DOC, hang('/yeu-cau/:id/duyet'), { id: '1' })).toBe(403)
    expect(quyetDinh(QT, hang('/tai-khoan/:sub'), { sub: 'x' })).toBe(404)
    expect(quyetDinh(DOC, hang('/tai-khoan/:sub'), { sub: SUB })).toBeNull()
    expect(quyetDinh(QT, hang('/yeu-cau/:id/duyet'), { id: '1' })).toBeNull()
  })

  it('không phiên → 401 và KHÔNG gọi KLAW; doc POST → 403 và KHÔNG gọi KLAW', async () => {
    const f = vi.fn(); vi.stubGlobal('fetch', f)
    const ep = taoEndpoint(hang('/yeu-cau/:id/duyet'))
    expect((await ep.handler(req(null, 'http://cms.local/api/klaw/yeu-cau/1/duyet', { id: '1' }))).status).toBe(401)
    expect((await ep.handler(req(DOC, 'http://cms.local/api/klaw/yeu-cau/1/duyet', { id: '1' }))).status).toBe(403)
    expect(f).not.toHaveBeenCalled()
  })

  it('quan_tri → chuyển tiếp đúng URL, hai header, body, query; ghi nhat_ky_cms khi 2xx', async () => {
    const f = vi.fn(async () => new Response(JSON.stringify({ sub: SUB, plan: 'pro' }), { status: 200, headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', f)
    const r = await taoEndpoint(hang('/tai-khoan/:sub/goi')).handler(req(QT, `http://cms.local/api/klaw/tai-khoan/${SUB}/goi?x=1`, { sub: SUB }, '{"plan":"pro"}'))
    expect(r.status).toBe(200); expect(await r.json()).toEqual({ sub: SUB, plan: 'pro' })
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(`http://klaw.test/api/v1/admin/tai-khoan/${SUB}/goi?x=1`)
    expect(init.method).toBe('PATCH'); expect(init.body).toBe('{"plan":"pro"}')
    const h = new Headers(init.headers)
    expect(h.get('x-admin-key')).toBe('khoa-test'); expect(h.get('x-admin-boi')).toBe('qt@klaw.test'); expect(h.get('x-forwarded-for')).toBe('9.9.9.9')
    const nk = await payload.find({ collection: 'nhat_ky_cms', where: { and: [{ hanh_dong: { equals: 'dat_goi' } }, { boi: { equals: 'qt@klaw.test' } }] }, overrideAccess: true })
    expect(nk.totalDocs).toBeGreaterThan(0)
  })

  it('KLAW 503 giữ nguyên mã và thân; fetch ném → 502', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'Đường quản trị chưa được cấu hình.' }), { status: 503, headers: { 'content-type': 'application/json' } })))
    let r = await taoEndpoint(hang('/tong-quan')).handler(req(DOC, 'http://cms.local/api/klaw/tong-quan', {}))
    expect(r.status).toBe(503); expect((await r.json()).detail).toMatch(/chưa được cấu hình/)
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('ECONNREFUSED') }))
    r = await taoEndpoint(hang('/tong-quan')).handler(req(DOC, 'http://cms.local/api/klaw/tong-quan', {}))
    expect(r.status).toBe(502)
  })

  it('SSE trả thẳng body với text/event-stream', async () => {
    const body = new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode('event: so_chua_doc\ndata: 1\n\n')); c.close() } })
    vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status: 200, headers: { 'content-type': 'text/event-stream' } })))
    const r = await taoEndpoint(hang('/thong-bao/luong')).handler(req(DOC, 'http://cms.local/api/klaw/thong-bao/luong', {}))
    expect(r.headers.get('content-type')).toBe('text/event-stream'); expect(await r.text()).toContain('so_chua_doc')
  })
})
```

- [ ] **Bước 2: Đỏ** — `pnpm test` → FAIL module chưa có.

- [ ] **Bước 3: Viết ba file**

```ts
// cms/src/lib/allowlist.ts
/** Bảng §5.3 của spec chuyển sang mã. Mỗi hàng sinh MỘT endpoint Payload (endpoints/klaw.ts),
 *  nên không có đường ký tự đại diện: đường lạ tự 404 do không có route. */
export type VaiTro = 'doc' | 'quan_tri'
export type Hang = { method: 'get' | 'post' | 'patch'; duong: string; vaiTro: VaiTro; sse?: boolean; hanhDong?: string }

export const ALLOWLIST: readonly Hang[] = [
  { method: 'get', duong: '/tong-quan', vaiTro: 'doc' },
  { method: 'get', duong: '/goi', vaiTro: 'doc' },
  { method: 'get', duong: '/yeu-cau', vaiTro: 'doc' },
  { method: 'post', duong: '/yeu-cau/:id/duyet', vaiTro: 'quan_tri', hanhDong: 'duyet_yeu_cau' },
  { method: 'post', duong: '/yeu-cau/:id/tu-choi', vaiTro: 'quan_tri', hanhDong: 'tu_choi_yeu_cau' },
  { method: 'get', duong: '/tai-khoan', vaiTro: 'doc' },
  { method: 'get', duong: '/tai-khoan/:sub', vaiTro: 'doc' },
  { method: 'patch', duong: '/tai-khoan/:sub/goi', vaiTro: 'quan_tri', hanhDong: 'dat_goi' },
  { method: 'post', duong: '/tai-khoan/:sub/thu-hoi', vaiTro: 'quan_tri', hanhDong: 'thu_hoi_goi' },
  { method: 'post', duong: '/tai-khoan/:sub/khoa', vaiTro: 'quan_tri', hanhDong: 'khoa_tai_khoan' },
  { method: 'post', duong: '/tai-khoan/:sub/mo-khoa', vaiTro: 'quan_tri', hanhDong: 'mo_khoa_tai_khoan' },
  { method: 'get', duong: '/nhat-ky', vaiTro: 'doc' },
  { method: 'get', duong: '/thong-bao', vaiTro: 'doc' },
  { method: 'post', duong: '/thong-bao/da-doc', vaiTro: 'doc', hanhDong: 'da_doc_thong_bao' },
  { method: 'get', duong: '/thong-bao/luong', vaiTro: 'doc', sse: true },
]

export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export const dienDuong = (mau: string, params: Record<string, string>): string =>
  mau.replace(/:(\w+)/g, (_, k: string) => encodeURIComponent(params[k] ?? ''))
```

```ts
// cms/src/lib/klaw-client.ts
/** Gọi KLAW `/admin/*` — CHỈ chạy phía máy chủ. `KLAW_ADMIN_API_KEY` không có tiền tố
 *  NEXT_PUBLIC_ nên không bao giờ vào bundle trình duyệt (tests/bundle.spec.ts). */
export type YeuCauKlaw = { method: string; duong: string; body?: string; boi: string; ip?: string | null; sse?: boolean }

export const goiKlaw = async (y: YeuCauKlaw, fetchFn: typeof fetch = fetch): Promise<Response> => {
  const goc = process.env.KLAW_API_URL
  const khoa = process.env.KLAW_ADMIN_API_KEY
  if (!goc || !khoa) return Response.json({ detail: 'CMS chưa cấu hình KLAW_API_URL hoặc KLAW_ADMIN_API_KEY.' }, { status: 503 })
  const headers: Record<string, string> = { 'X-Admin-Key': khoa, 'X-Admin-Boi': y.boi }
  if (y.ip) headers['X-Forwarded-For'] = y.ip
  if (y.body) headers['Content-Type'] = 'application/json'
  if (y.sse) headers.Accept = 'text/event-stream'
  try {
    return await fetchFn(`${goc}/admin${y.duong}`, {
      method: y.method.toUpperCase(),
      headers,
      body: y.body,
      signal: y.sse ? undefined : AbortSignal.timeout(30_000),
    })
  } catch {
    return Response.json({ detail: 'Không nối được tới KLAW.' }, { status: 502 })
  }
}
```

```ts
// cms/src/endpoints/klaw.ts
import type { Endpoint, PayloadRequest } from 'payload'
import { dangHoatDong, laQuanTri } from '../access/vaiTro'
import { ghiNhatKyCms, ipCua } from '../hooks/nhatKyCms'
import { ALLOWLIST, UUID_RE, dienDuong, type Hang } from '../lib/allowlist'
import { goiKlaw } from '../lib/klaw-client'

const THONG_DIEP: Record<number, string> = {
  401: 'Bạn cần đăng nhập vào trang quản trị.',
  403: 'Vai trò của bạn chỉ được xem, không thực hiện được thao tác này.',
  404: 'Không tìm thấy.',
}

/** Thứ tự kiểm §6.4: phiên → tham số → vai trò. Thuần, test riêng. */
export const quyetDinh = (user: unknown, hang: Hang, params: Record<string, string>): 401 | 403 | 404 | null => {
  if (!dangHoatDong(user)) return 401
  if ('sub' in params && !UUID_RE.test(params.sub ?? '')) return 404
  if (hang.vaiTro === 'quan_tri' && !laQuanTri(user)) return 403
  return null
}

export const taoEndpoint = (hang: Hang): Endpoint => ({
  path: `/klaw${hang.duong}`,
  method: hang.method,
  handler: async (req: PayloadRequest) => {
    const params = (req.routeParams ?? {}) as Record<string, string>
    const ma = quyetDinh(req.user, hang, params)
    if (ma !== null) return Response.json({ detail: THONG_DIEP[ma] }, { status: ma })
    const user = req.user as { email: string }
    const url = new URL(req.url ?? 'http://cms.local/')
    const body = hang.method === 'get' || typeof req.text !== 'function' ? undefined : await req.text()
    const duong = dienDuong(hang.duong, params)
    const res = await goiKlaw({ method: hang.method, duong: duong + url.search, body: body || undefined, boi: user.email, ip: ipCua(req), sse: hang.sse })
    if (hang.sse && res.ok) {
      return new Response(res.body, { status: 200, headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store', Connection: 'keep-alive' } })
    }
    const than = await res.text()
    if (res.ok && hang.method !== 'get' && hang.hanhDong) {
      await ghiNhatKyCms(req.payload, { hanh_dong: hang.hanhDong, boi: user.email, ip: ipCua(req), chi_tiet: { duong } })
    }
    const headers: Record<string, string> = { 'Content-Type': res.headers.get('content-type') ?? 'application/json' }
    const cd = res.headers.get('content-disposition')
    if (cd) headers['Content-Disposition'] = cd
    return new Response(than, { status: res.status, headers })
  },
})

export const klawEndpoints: Endpoint[] = ALLOWLIST.map(taoEndpoint)
```

`payload.config.ts`: `import { klawEndpoints } from './src/endpoints/klaw'` và `endpoints: klawEndpoints`.

- [ ] **Bước 4: Xanh; lint; type-check**

Run: `cd cms && pnpm test && pnpm lint && pnpm type-check`. Nếu `req.routeParams` không có trong kiểu `PayloadRequest` 3.88, đọc `node_modules/payload/dist/types/index.d.ts` để lấy đúng tên.

- [ ] **Bước 5: Commit**

```bash
git add cms
git commit -m "feat(cms): allowlisted server-side proxy to KLAW /admin with role gate and SSE passthrough"
```

---

### Task 11: Khung giao diện — client helper, hiển thị, điều hướng, Tổng quan

**Files:**
- Create: `cms/src/lib/goi-klaw.ts`, `cms/src/lib/hien-thi.ts`, `cms/src/components/ui/Bang.tsx`, `cms/src/components/ui/HopXacNhan.tsx`, `cms/src/components/ui/ThongBaoLoi.tsx`, `cms/src/components/DieuHuong.tsx`, `cms/src/views/khung.tsx`, `cms/src/views/TongQuan.tsx`, `cms/src/views/TongQuanClient.tsx`
- Modify: `cms/payload.config.ts` (`admin.components.views.dashboard`, `afterNavLinks`)
- Test: `cms/tests/hien-thi.spec.ts`

**Interfaces:**
- Produces:
  - `goi-klaw.ts` (client): `goiQuanTri<T>(duong: string, tuyChon?: { method?: 'GET' | 'POST' | 'PATCH'; body?: unknown }): Promise<KetQua<T>>` với `type KetQua<T> = { ok: true; data: T } | { ok: false; status: number; message: string }`.
  - `hien-thi.ts` (thuần): `tenGoi(ma, goi?)`, `dinhDangLuc(iso)`, `soNgayCon(iso)`, `nhanTrangThaiYeuCau(t)`, `nhanLoai(l)`, `nhanHanhDong(hd)`, `HANH_DONG`.
  - `khung.tsx`: `KhungQuanTri({ props: AdminViewServerProps; tieuDe: string; children })` — bọc `DefaultTemplate`; không phiên → "Bạn cần đăng nhập vào trang quản trị."
  - `Bang({ cot: { khoa: string; nhan: string }[]; hang: Record<string, React.ReactNode>[]; rong: string; onChonHang?(i) })`; `ThongBaoLoi({ message, onThuLai? })`; `HopXacNhan({ mo, tieuDe, moTa, nhanXacNhan, canLyDo?, onXacNhan(lyDo?: string), onDong })`.
  - `DieuHuong`: bốn liên kết `/admin`, `/admin/yeu-cau`, `/admin/tai-khoan`, `/admin/nhat-ky`.

- [ ] **Bước 1: Test helper thuần (đỏ)**

```ts
// cms/tests/hien-thi.spec.ts
import { describe, expect, it } from 'vitest'
import { dinhDangLuc, nhanHanhDong, nhanLoai, nhanTrangThaiYeuCau, soNgayCon, tenGoi } from '../src/lib/hien-thi'

describe('hien-thi (spec §6.5)', () => {
  it('tên gói ưu tiên danh mục KLAW, rơi về bảng cứng, mã lạ giữ mã', () => {
    expect(tenGoi('pro', [{ ma: 'pro', ten: 'Cá nhân' }])).toBe('Cá nhân')
    expect(tenGoi('free')).toBe('Miễn phí'); expect(tenGoi('vip')).toBe('vip')
  })
  it('nhãn tiếng Việt', () => {
    expect(nhanTrangThaiYeuCau('cho_duyet')).toBe('Chờ duyệt'); expect(nhanLoai('gia_han')).toBe('Gia hạn')
    expect(nhanHanhDong('duyet_yeu_cau')).toBe('Duyệt yêu cầu'); expect(nhanHanhDong('duyet_yeu_cau_that_bai')).toBe('Duyệt yêu cầu (thất bại)')
    expect(nhanHanhDong('la')).toBe('la')
  })
  it('thời gian theo Asia/Ho_Chi_Minh, null an toàn', () => {
    expect(dinhDangLuc('2026-09-08T17:00:00Z')).toBe('00:00 09/09/2026'); expect(dinhDangLuc(null)).toBe('')
    expect(soNgayCon(null)).toBeNull(); expect(soNgayCon(new Date(Date.now() + 2.5 * 86_400_000).toISOString())).toBe(3)
  })
})
```

- [ ] **Bước 2: Đỏ** — `pnpm test tests/hien-thi.spec.ts`.

- [ ] **Bước 3: Helper và khung**

```ts
// cms/src/lib/hien-thi.ts
const GOI_CUNG: Record<string, string> = { free: 'Miễn phí', pro: 'Cá nhân' }
export const tenGoi = (ma: string, goi?: { ma: string; ten: string }[]): string => goi?.find((g) => g.ma === ma)?.ten ?? GOI_CUNG[ma] ?? ma

export const nhanTrangThaiYeuCau = (t: string): string => ({ cho_duyet: 'Chờ duyệt', da_duyet: 'Đã duyệt', tu_choi: 'Từ chối' } as Record<string, string>)[t] ?? t
export const nhanLoai = (l: string): string => ({ nang_goi: 'Nâng gói', gia_han: 'Gia hạn' } as Record<string, string>)[l] ?? l

export const HANH_DONG: Record<string, string> = {
  duyet_yeu_cau: 'Duyệt yêu cầu', tu_choi_yeu_cau: 'Từ chối yêu cầu', dat_goi: 'Đặt gói', thu_hoi_goi: 'Thu hồi gói',
  khoa_tai_khoan: 'Khoá tài khoản', mo_khoa_tai_khoan: 'Mở khoá tài khoản', xac_thuc_that_bai: 'Xác thực thất bại',
  dang_nhap: 'Đăng nhập', dang_xuat: 'Đăng xuất', dang_nhap_that_bai: 'Đăng nhập thất bại', da_doc_thong_bao: 'Đánh dấu đã đọc',
}
const HAU_TO = '_that_bai'
export const nhanHanhDong = (hd: string): string => {
  if (HANH_DONG[hd]) return HANH_DONG[hd]
  const goc = hd.endsWith(HAU_TO) ? hd.slice(0, -HAU_TO.length) : ''
  return goc && HANH_DONG[goc] ? `${HANH_DONG[goc]} (thất bại)` : hd
}

const FMT = new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric', hour12: false, timeZone: 'Asia/Ho_Chi_Minh' })
export const dinhDangLuc = (iso: string | null): string => {
  if (!iso) return ''
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return ''
  const p = Object.fromEntries(FMT.formatToParts(t).map((x) => [x.type, x.value]))
  return `${p.hour}:${p.minute} ${p.day}/${p.month}/${p.year}`
}
export const soNgayCon = (iso: string | null): number | null => {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : Math.max(0, Math.ceil((t - Date.now()) / 86_400_000))
}
```

```ts
// cms/src/lib/goi-klaw.ts
'use client'
export type KetQua<T> = { ok: true; data: T } | { ok: false; status: number; message: string }

export async function goiQuanTri<T>(duong: string, tuyChon: { method?: 'GET' | 'POST' | 'PATCH'; body?: unknown } = {}): Promise<KetQua<T>> {
  let res: Response
  try {
    res = await fetch(`/api/klaw${duong}`, {
      method: tuyChon.method ?? 'GET',
      credentials: 'same-origin',
      headers: tuyChon.body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: tuyChon.body === undefined ? undefined : JSON.stringify(tuyChon.body),
    })
  } catch {
    return { ok: false, status: 0, message: 'Không nối được tới trang quản trị. Kiểm tra mạng rồi thử lại.' }
  }
  if (!res.ok) {
    let message = `Lỗi ${res.status}.`
    try { const j = await res.json(); if (typeof j.detail === 'string') message = j.detail } catch { /* thân không phải JSON */ }
    return { ok: false, status: res.status, message }
  }
  return { ok: true, data: (await res.json()) as T }
}
```

```tsx
// cms/src/views/khung.tsx
import type { AdminViewServerProps } from 'payload'
import { DefaultTemplate } from '@payloadcms/next/templates'
import { Gutter } from '@payloadcms/ui'
import React from 'react'

/** Mọi view tuỳ biến của Payload là CÔNG KHAI mặc định — khung này là chỗ duy nhất kiểm phiên. */
export function KhungQuanTri({ props, tieuDe, children }: { props: AdminViewServerProps; tieuDe: string; children: React.ReactNode }) {
  const { initPageResult, params, searchParams } = props
  if (!initPageResult.req.user) return <Gutter><p>Bạn cần đăng nhập vào trang quản trị.</p></Gutter>
  return (
    <DefaultTemplate
      i18n={initPageResult.req.i18n} locale={initPageResult.locale} params={params} payload={initPageResult.req.payload}
      permissions={initPageResult.permissions} searchParams={searchParams} user={initPageResult.req.user} visibleEntities={initPageResult.visibleEntities}
    >
      <Gutter><h1 style={{ marginBottom: 24 }}>{tieuDe}</h1>{children}</Gutter>
    </DefaultTemplate>
  )
}
```

```tsx
// cms/src/components/DieuHuong.tsx
'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import React from 'react'

const MUC = [['/admin', 'Tổng quan'], ['/admin/yeu-cau', 'Yêu cầu nâng gói'], ['/admin/tai-khoan', 'Tài khoản'], ['/admin/nhat-ky', 'Nhật ký']] as const
export function DieuHuong() {
  const path = usePathname()
  return (
    <nav aria-label="Quản lý tài khoản" style={{ display: 'grid', gap: 4, padding: '8px 0' }}>
      {MUC.map(([href, nhan]) => (
        <Link key={href} href={href} className="nav__link" aria-current={path === href ? 'page' : undefined} style={{ fontWeight: path === href ? 700 : 400 }}>{nhan}</Link>
      ))}
    </nav>
  )
}
```

`Bang.tsx`: `<table className="table">` với `<thead>` từ `cot`, `<tbody>` từ `hang` (mỗi ô `hang[i][cot.khoa]`), dòng "`rong`" khi không có hàng, `onChonHang` gắn `onClick` và `tabIndex=0` + Enter. `ThongBaoLoi.tsx`: `<div role="alert">` + `<Button>` của `@payloadcms/ui` "Thử lại" khi có `onThuLai`. `HopXacNhan.tsx`: `<dialog>` điều khiển bằng `useEffect` (`mo ? ref.showModal() : ref.close()`), `<textarea>` bắt buộc khi `canLyDo` (1–500 ký tự, nút Xác nhận vô hiệu khi rỗng), nút Huỷ và `onCancel` (Escape) gọi `onDong`.

```tsx
// cms/src/views/TongQuanClient.tsx
'use client'
import Link from 'next/link'
import React, { useCallback, useEffect, useState } from 'react'
import { ThongBaoLoi } from '../components/ui/ThongBaoLoi'
import { goiQuanTri, type KetQua } from '../lib/goi-klaw'

type TongQuan = { tong_tai_khoan: number; dang_ca_nhan: number; cho_duyet: number; het_han_7_ngay: number; moi_7_ngay: number; dang_khoa: number; hoi_dap_hom_nay: number }
const O: [keyof TongQuan, string, string?][] = [
  ['tong_tai_khoan', 'Tài khoản'], ['dang_ca_nhan', 'Đang dùng gói Cá nhân'], ['cho_duyet', 'Yêu cầu chờ duyệt', '/admin/yeu-cau?trang_thai=cho_duyet'],
  ['het_han_7_ngay', 'Hết hạn trong 7 ngày', '/admin/tai-khoan?loc=het_han'], ['moi_7_ngay', 'Tài khoản mới 7 ngày'], ['dang_khoa', 'Đang khoá'], ['hoi_dap_hom_nay', 'Lượt hỏi hôm nay'],
]
export function TongQuanClient() {
  const [kq, setKq] = useState<KetQua<TongQuan> | null>(null)
  const tai = useCallback(() => { setKq(null); void goiQuanTri<TongQuan>('/tong-quan').then(setKq) }, [])
  useEffect(() => { tai() }, [tai])
  if (kq === null) return <p>Đang tải…</p>
  if (!kq.ok) return <ThongBaoLoi message={kq.message} onThuLai={tai} />
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
      {O.map(([k, nhan, href]) => {
        const so = <strong style={{ fontSize: 32 }}>{kq.data[k].toLocaleString('vi-VN')}</strong>
        return <div key={k} className="card" style={{ padding: 16 }}>{href ? <Link href={href}>{so}</Link> : so}<div>{nhan}</div></div>
      })}
    </div>
  )
}
```

```tsx
// cms/src/views/TongQuan.tsx
import type { AdminViewServerProps } from 'payload'
import React from 'react'
import { KhungQuanTri } from './khung'
import { TongQuanClient } from './TongQuanClient'
export function TongQuan(props: AdminViewServerProps) {
  return <KhungQuanTri props={props} tieuDe="Tổng quan"><TongQuanClient /></KhungQuanTri>
}
```

`payload.config.ts`:

```ts
  admin: {
    user: 'admins',
    meta: { titleSuffix: '— KLAW quản trị' },
    components: {
      views: { dashboard: { Component: '@/views/TongQuan#TongQuan' } },
      afterNavLinks: ['@/components/DieuHuong#DieuHuong'],
    },
  },
```

Chạy `pnpm payload generate:importmap` sau mỗi lần thêm component path.

- [ ] **Bước 4: Xanh; build; xem bằng mắt**

Run: `cd cms && pnpm test && pnpm lint && pnpm type-check && pnpm build`. Rồi `pnpm dev` với KLAW chạy (`KLAW_ADMIN_API_KEY` khớp hai bên): `/admin` hiện bảy ô số; tắt KLAW → "Không nối được tới KLAW." và nút Thử lại. Ảnh `.tham-dinh-shots/cms-01-tong-quan.png`.

- [ ] **Bước 5: Commit**

```bash
git add cms
git commit -m "feat(cms): admin shell with navigation, shared client helper and the overview dashboard"
```

---

### Task 12: View Yêu cầu — duyệt và từ chối

**Files:**
- Create: `cms/src/views/YeuCau.tsx`, `cms/src/views/YeuCauClient.tsx`, `cms/src/views/yeu-cau-logic.ts`
- Modify: `cms/payload.config.ts` (`views.yeuCau`)
- Test: `cms/tests/yeu-cau-logic.spec.ts`

**Interfaces:**
- Consumes: `/api/klaw/yeu-cau?trang_thai=&q=&limit=&offset=`, `POST /api/klaw/yeu-cau/:id/duyet`, `POST …/tu-choi {ly_do}`, `/api/klaw/goi`; `HopXacNhan`, `Bang`, `hien-thi`.
- Produces: `thongDiepSauThaoTac(status: number, loai: 'duyet' | 'tu_choi', chuMayChu: string): { kieu: 'ok' | 'canh_bao' | 'loi'; chu: string; taiLai: boolean }`.

- [ ] **Bước 1: Test logic (đỏ)**

```ts
// cms/tests/yeu-cau-logic.spec.ts
import { describe, expect, it } from 'vitest'
import { thongDiepSauThaoTac } from '../src/views/yeu-cau-logic'
describe('thông điệp sau duyệt/từ chối (spec §6.5)', () => {
  it('409 là cảnh báo + tải lại, 423 là lỗi có hướng dẫn, 200 là ok', () => {
    expect(thongDiepSauThaoTac(200, 'duyet', '')).toEqual({ kieu: 'ok', chu: 'Đã duyệt. Gói của người dùng đã đổi.', taiLai: true })
    expect(thongDiepSauThaoTac(409, 'duyet', 'x')).toMatchObject({ kieu: 'canh_bao', taiLai: true, chu: expect.stringContaining('người khác') })
    expect(thongDiepSauThaoTac(423, 'duyet', 'x')).toMatchObject({ kieu: 'loi', chu: expect.stringContaining('mở khoá') })
    expect(thongDiepSauThaoTac(500, 'tu_choi', 'Máy bận')).toEqual({ kieu: 'loi', chu: 'Máy bận', taiLai: false })
  })
})
```

- [ ] **Bước 2: Đỏ**, rồi viết:

```ts
// cms/src/views/yeu-cau-logic.ts
export type ThongDiep = { kieu: 'ok' | 'canh_bao' | 'loi'; chu: string; taiLai: boolean }
export const thongDiepSauThaoTac = (status: number, loai: 'duyet' | 'tu_choi', chuMayChu: string): ThongDiep => {
  if (status >= 200 && status < 300) return { kieu: 'ok', chu: loai === 'duyet' ? 'Đã duyệt. Gói của người dùng đã đổi.' : 'Đã từ chối. Người dùng sẽ thấy lý do.', taiLai: true }
  if (status === 409) return { kieu: 'canh_bao', chu: 'Yêu cầu này vừa được người khác xử lý.', taiLai: true }
  if (status === 423) return { kieu: 'loi', chu: 'Tài khoản đang bị khoá, mở khoá trước khi duyệt.', taiLai: false }
  if (status === 403) return { kieu: 'loi', chu: 'Vai trò của bạn chỉ được xem, không duyệt được.', taiLai: false }
  return { kieu: 'loi', chu: chuMayChu || `Lỗi ${status}.`, taiLai: false }
}
```

`YeuCauClient.tsx` (`'use client'`, prop `vaiTro: 'doc' | 'quan_tri'`): state `tab` (`cho_duyet | da_duyet | tu_choi`, khởi từ `useSearchParams().get('trang_thai')`), `q`, `trang`, `ds: KetQua<{ tong: number; items: YeuCauAdmin[] }> | null`, `goi` (từ `/goi`, tải một lần), `hopTuChoi: number | null`, `thongDiep: ThongDiep | null`, `subKhoa: string | null` (để liên kết Mở khoá sau 423). Ba tab là `<button role="tab">`. Bảng cột: Email · Gói hiện tại (`tenGoi(plan_hieu_luc, goi)`) · Loại (`nhanLoai`) · Tạo lúc (`dinhDangLuc`) · Trạng thái (`nhanTrangThaiYeuCau` + huy hiệu "Đang khoá" khi `khoa_luc`) · Hành động (chỉ khi `vaiTro === 'quan_tri' && tab === 'cho_duyet'`: nút Duyệt gọi `goiQuanTri(`/yeu-cau/${id}/duyet`, { method: 'POST' })`; nút Từ chối mở `HopXacNhan canLyDo` rồi `goiQuanTri(…/tu-choi, { method: 'POST', body: { ly_do } })`). Sau thao tác: `setThongDiep(thongDiepSauThaoTac(status, loai, message))`; nếu `taiLai` gọi lại danh sách; nếu 423 hiện thêm `<Link href={`/admin/tai-khoan?sub=${user_sub}`}>Mở khoá tài khoản</Link>`. Phân trang 50/trang: Trước/Sau + "x–y trong tổng". Kiểu `YeuCauAdmin` chép từ `YeuCauAdminOut` (Task 1).

`YeuCau.tsx`: `KhungQuanTri` + `<YeuCauClient vaiTro={(props.initPageResult.req.user as { vai_tro: 'doc' | 'quan_tri' }).vai_tro} />`.

`payload.config.ts`: `views.yeuCau = { Component: '@/views/YeuCau#YeuCau', path: '/yeu-cau', exact: true }`.

- [ ] **Bước 3: Xanh; build; kiểm bằng tay**

Run: `cd cms && pnpm test && pnpm lint && pnpm type-check && pnpm build`. Tay (KLAW chạy): từ KLAW FE gửi yêu cầu nâng gói bằng tài khoản thử → CMS tab Chờ duyệt thấy dòng → Duyệt → KLAW FE `/tai-khoan` hiện "Cá nhân · còn 30 ngày"; bấm Duyệt hai lần nhanh → cảnh báo 409; tạo yêu cầu khác rồi Từ chối với lý do. Ảnh `.tham-dinh-shots/cms-02-yeu-cau.png`, `cms-03-tu-choi.png`.

- [ ] **Bước 4: Commit**

```bash
git add cms
git commit -m "feat(cms): upgrade-request view with approve, reject-with-reason and conflict handling"
```

---

### Task 13: View Tài khoản — tìm, chi tiết, ba hành động

**Files:**
- Create: `cms/src/views/TaiKhoan.tsx`, `cms/src/views/TaiKhoanClient.tsx`, `cms/src/views/ChiTietTaiKhoan.tsx`, `cms/src/views/tai-khoan-logic.ts`
- Modify: `cms/payload.config.ts` (`views.taiKhoan`)
- Test: `cms/tests/tai-khoan-logic.spec.ts`

**Interfaces:**
- Consumes: `/api/klaw/tai-khoan?q=&limit=&offset=`, `/api/klaw/tai-khoan/:sub`, `PATCH …/goi {plan, so_ngay, ly_do}`, `POST …/thu-hoi {ly_do}`, `…/khoa {ly_do}`, `…/mo-khoa {ly_do}`, `/api/klaw/goi`.
- Produces: `cauXacNhan(hd: 'dat_goi' | 'thu_hoi' | 'khoa' | 'mo_khoa', ctx: { email: string; tenGoi?: string; soNgay?: number | null }): { tieuDe: string; moTa: string; canLyDo: boolean }`.

- [ ] **Bước 1: Test (đỏ)**

```ts
// cms/tests/tai-khoan-logic.spec.ts
import { describe, expect, it } from 'vitest'
import { cauXacNhan } from '../src/views/tai-khoan-logic'
describe('câu xác nhận nêu hậu quả (spec §6.5)', () => {
  it('cả bốn hành động bắt buộc lý do; khoá nêu hậu quả; đặt gói nêu số ngày hoặc vô thời hạn', () => {
    expect(cauXacNhan('khoa', { email: 'a@b.c' })).toEqual({ tieuDe: 'Khoá tài khoản a@b.c?', moTa: 'Người dùng sẽ không hỏi và soạn được cho tới khi mở khoá. Tra cứu và soát văn bản vẫn mở.', canLyDo: true })
    expect(cauXacNhan('mo_khoa', { email: 'a@b.c' }).canLyDo).toBe(true)
    expect(cauXacNhan('dat_goi', { email: 'a@b.c', tenGoi: 'Cá nhân', soNgay: 30 }).canLyDo).toBe(true)
    expect(cauXacNhan('dat_goi', { email: 'a@b.c', tenGoi: 'Cá nhân', soNgay: 30 }).moTa).toContain('30 ngày')
    expect(cauXacNhan('dat_goi', { email: 'a@b.c', tenGoi: 'Cá nhân', soNgay: null }).moTa).toContain('vô thời hạn')
    expect(cauXacNhan('thu_hoi', { email: 'a@b.c' })).toMatchObject({ canLyDo: true, moTa: expect.stringContaining('ngay lập tức') })
  })
})
```

- [ ] **Bước 2: Đỏ**, rồi viết:

```ts
// cms/src/views/tai-khoan-logic.ts
export type HanhDongTK = 'dat_goi' | 'thu_hoi' | 'khoa' | 'mo_khoa'
export const cauXacNhan = (hd: HanhDongTK, ctx: { email: string; tenGoi?: string; soNgay?: number | null }): { tieuDe: string; moTa: string; canLyDo: boolean } => {
  switch (hd) {
    case 'khoa':
      return { tieuDe: `Khoá tài khoản ${ctx.email}?`, moTa: 'Người dùng sẽ không hỏi và soạn được cho tới khi mở khoá. Tra cứu và soát văn bản vẫn mở.', canLyDo: true }
    case 'mo_khoa':
      return { tieuDe: `Mở khoá tài khoản ${ctx.email}?`, moTa: 'Người dùng hỏi và soạn văn bản lại được ngay. Lý do chỉ ghi vào nhật ký, người dùng không thấy.', canLyDo: true }
    case 'thu_hoi':
      return { tieuDe: `Thu hồi gói trả phí của ${ctx.email}?`, moTa: 'Gói về Miễn phí ngay lập tức; người dùng nhận thông báo kèm lý do. Dùng cho lạm dụng, không dùng thay cho việc để gói hết hạn.', canLyDo: true }
    case 'dat_goi':
      return {
        tieuDe: `Đặt gói ${ctx.tenGoi ?? ''} cho ${ctx.email}?`,
        moTa: `${ctx.soNgay == null ? `Gói ${ctx.tenGoi ?? ''} vô thời hạn (không có ngày hết hạn).` : `Gói ${ctx.tenGoi ?? ''} trong ${ctx.soNgay} ngày tính từ bây giờ.`} Lý do chỉ ghi vào nhật ký, người dùng không thấy.`,
        canLyDo: true,
      }
  }
}
```

`TaiKhoanClient.tsx` (prop `vaiTro`): ô tìm `<input type="search">` (gửi khi Enter hoặc sau 400 ms), bảng cột Email · Gói (`tenGoi`) · Hạn (`dinhDangLuc(plan_het_han)` hoặc "—") · Trạng thái ("Bình thường" / "Đang khoá") · Tham gia · Số phiên · Lượt 30 ngày; bấm dòng → `router.push('/admin/tai-khoan?sub=' + sub)`. Khi `?sub=` có → render `<ChiTietTaiKhoan sub vaiTro />` với nút "← Danh sách". `?loc=het_han` (từ Tổng quan): lọc phía client các dòng có `plan_het_han` trong 7 ngày (đủ cho quy mô khoá luận; ghi rõ trong mã bằng chú thích `// ponytail: lọc client, chuyển sang query KLAW khi > 500 tài khoản`).

`ChiTietTaiKhoan.tsx`: tải `/tai-khoan/:sub` (kiểu `TaiKhoanChiTietOut`) và `/goi`; thẻ định danh (email, `tenGoi(plan)` + "hết hạn `dinhDangLuc(het_han_luc)`" hoặc "vô thời hạn", "Đang khoá từ `dinhDangLuc(khoa_luc)` · Lý do: `khoa_ly_do`" khi khoá); ba ô số `tong_hoi_dap`, `tong_ban_thao`, `so_phien` (KLAW không trả `muc` cho admin — không bịa thanh đo); bảng `yeu_cau` (Loại · Gói · Trạng thái · Tạo lúc · Xử lý lúc · Lý do); khối hành động chỉ khi `vaiTro === 'quan_tri'`: form Đặt gói (`<select>` từ `/goi`, `<input type="number" min=1 max=3650>` để trống = vô thời hạn, vô hiệu khi gói = `goi_mac_dinh`) → `HopXacNhan(cauXacNhan('dat_goi', …))` → `PATCH` với body `{ plan, so_ngay, ly_do }`; nút Thu hồi gói (ẩn khi `plan === goi_mac_dinh`) → `HopXacNhan canLyDo` → `POST`; nút Khoá / Mở khoá theo `khoa_luc`, mở khoá gửi `POST …/mo-khoa` với body `{ ly_do }`. **Cả bốn hành động đều bắt buộc lý do** (Task 7b đổi hợp đồng; spec §5.3). Sau 2xx tải lại chi tiết; lỗi → `ThongBaoLoi` với `message` máy chủ (409 "Tài khoản đã ở trạng thái này." nguyên văn). **Không có** phần tử nào hiện nội dung hội thoại.

`payload.config.ts`: `views.taiKhoan = { Component: '@/views/TaiKhoan#TaiKhoan', path: '/tai-khoan', exact: true }`.

- [ ] **Bước 3: Xanh; build; tay**

Run: `cd cms && pnpm test && pnpm lint && pnpm type-check && pnpm build`. Tay: tìm email thử → chi tiết → Đặt gói Cá nhân 7 ngày → KLAW FE "còn 7 ngày"; Khoá → KLAW FE thẻ khoá (Task 15) và `/tra-cuu` 403; Mở khoá; Thu hồi → Miễn phí. Ảnh `cms-04-tai-khoan.png`, `cms-05-chi-tiet-khoa.png`.

- [ ] **Bước 4: Commit**

```bash
git add cms
git commit -m "feat(cms): account search and detail with manual plan, revoke, suspend and unsuspend actions"
```

---

### Task 14: View Nhật ký, `start.sh`, CI, README, kiểm bí mật

**Files:**
- Create: `cms/src/views/NhatKy.tsx`, `cms/src/views/NhatKyClient.tsx`, `cms/src/views/nhat-ky-logic.ts`, `cms/scripts/start.sh`, `cms/README.md`, `cms/migrations/*` (sinh)
- Modify: `cms/payload.config.ts` (`views.nhatKy`), `.github/workflows/ci.yml` (job `cms`), `docs/README.md` (một dòng)
- Test: `cms/tests/nhat-ky-logic.spec.ts`, `cms/tests/bundle.spec.ts`

**Interfaces:**
- Consumes: `/api/klaw/nhat-ky?tu=&den=&hanh_dong=&doi_tuong=&limit=&offset=[&dinh_dang=csv]`; `/api/nhat_ky_cms?sort=-createdAt&limit=&page=` (REST Payload, cookie).
- Produces: `queryNhatKy(loc: { tu?: string; den?: string; hanhDong?: string; doiTuong?: string; trang: number; kichCo: number; csv?: boolean }): string`.

- [ ] **Bước 1: Test (đỏ)**

```ts
// cms/tests/nhat-ky-logic.spec.ts
import { describe, expect, it } from 'vitest'
import { queryNhatKy } from '../src/views/nhat-ky-logic'
describe('query nhật ký', () => {
  it('bỏ trống, phân trang, csv lấy tối đa 5000', () => {
    expect(queryNhatKy({ trang: 2, kichCo: 50 })).toBe('?limit=50&offset=50')
    expect(queryNhatKy({ hanhDong: 'dat_goi', doiTuong: 'abc', trang: 1, kichCo: 50 })).toBe('?hanh_dong=dat_goi&doi_tuong=abc&limit=50&offset=0')
    expect(queryNhatKy({ tu: '2026-09-08T00:00', trang: 1, kichCo: 50, csv: true })).toBe('?tu=2026-09-07T17%3A00%3A00.000Z&limit=5000&offset=0&dinh_dang=csv')
  })
})
```

(`TZ=Asia/Ho_Chi_Minh` trong script `test` làm `tu` tất định.)

```ts
// cms/tests/bundle.spec.ts
import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
describe('bí mật không lọt bundle (spec §4.1, §9)', () => {
  it('.next/static không chứa KLAW_ADMIN_API_KEY', () => {
    const goc = path.resolve(__dirname, '../.next/static')
    if (!fs.existsSync(goc)) { console.warn('chưa build — bỏ qua'); return }
    const tep: string[] = []
    const duyet = (d: string) => { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); if (fs.statSync(p).isDirectory()) duyet(p); else tep.push(p) } }
    duyet(goc)
    for (const f of tep) expect(fs.readFileSync(f, 'utf8')).not.toContain('KLAW_ADMIN_API_KEY')
  })
})
```

- [ ] **Bước 2: Đỏ**, rồi viết:

```ts
// cms/src/views/nhat-ky-logic.ts
export type LocNhatKy = { tu?: string; den?: string; hanhDong?: string; doiTuong?: string; trang: number; kichCo: number; csv?: boolean }
const iso = (local?: string): string | undefined => (local ? new Date(local).toISOString() : undefined)
export const queryNhatKy = (l: LocNhatKy): string => {
  const p = new URLSearchParams()
  const tu = iso(l.tu)
  const den = iso(l.den)
  if (tu) p.set('tu', tu)
  if (den) p.set('den', den)
  if (l.hanhDong) p.set('hanh_dong', l.hanhDong)
  if (l.doiTuong) p.set('doi_tuong', l.doiTuong)
  if (l.csv) { p.set('limit', '5000'); p.set('offset', '0'); p.set('dinh_dang', 'csv') }
  else { p.set('limit', String(l.kichCo)); p.set('offset', String((l.trang - 1) * l.kichCo)) }
  return `?${p.toString()}`
}
```

`NhatKyClient.tsx`: hai tab "Nhật ký KLAW" (mặc định) và "Nhật ký CMS". Tab KLAW: bộ lọc (`datetime-local` từ/đến; `<select>` hành động từ `HANH_DONG`; `sub` đối tượng), bảng Thời điểm (`dinhDangLuc`) · Hành động (`nhanHanhDong`) · Người thực hiện · Loại tác nhân · IP · Đối tượng · Chi tiết (`<details>` JSON), dòng chữ tĩnh "IP là địa chỉ qua CMS khi KLAW không tin proxy." dưới bảng; phân trang; cạnh nút xuất, dòng chữ tĩnh "Xuất tối đa 5.000 dòng mỗi lần theo bộ lọc đang chọn; thu hẹp khoảng thời gian nếu cần đủ." (đề xuất B của khảo sát); chân màn hình: "Nhật ký được giữ vô thời hạn và chưa có bản sao tự động — xuất CSV định kỳ để giữ bằng chứng." (đề xuất C); nút "Xuất CSV": `fetch('/api/klaw/nhat-ky' + queryNhatKy({ ...loc, csv: true }), { credentials: 'same-origin' })` → `Blob` → `<a download="nhat-ky-quan-tri.csv">` bấm tự động rồi `URL.revokeObjectURL`. Tab CMS: `fetch('/api/nhat_ky_cms?sort=-createdAt&limit=50&page=n', { credentials: 'same-origin' })` → bảng Thời điểm · Hành động · Bởi · IP.

`payload.config.ts`: `views.nhatKy = { Component: '@/views/NhatKy#NhatKy', path: '/nhat-ky', exact: true }`.

- [ ] **Bước 3: `start.sh`**

Chép `~/VF_TTS/vsf-cms-multiple-sites-backend/scripts/start.sh` sang `cms/scripts/start.sh` nguyên văn, đổi hai chỗ: dòng gợi ý `railway ssh --service klaw-cms`, và `exec next start -p "${PORT:-3001}"`. `chmod +x cms/scripts/start.sh`.

- [ ] **Bước 4: CI**

Thêm job vào `.github/workflows/ci.yml` (không đụng job Python):

```yaml
  cms:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: postgres, POSTGRES_DB: klaw_cms_test }
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 5s --health-timeout 5s --health-retries 10
    defaults: { run: { working-directory: cms } }
    env:
      DATABASE_URI: postgres://postgres:postgres@localhost:5432/klaw_cms_test
      PAYLOAD_SECRET: ci-secret-not-used-elsewhere
      KLAW_API_URL: http://klaw.test/api/v1
      KLAW_ADMIN_API_KEY: ci-key
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with: { version: 9.15.9 }
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: pnpm, cache-dependency-path: cms/pnpm-lock.yaml }
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm type-check
      - run: pnpm build
      - run: pnpm test
```

`pnpm build` trước `pnpm test` để `bundle.spec.ts` có `.next/static`. Không cài hook git, không đổi branch protection (§8.3).

- [ ] **Bước 5: `cms/README.md`** — runbook §8.1 và §8.2 của spec: tạo database, năm biến, `pnpm dev`, người đầu tiên, `pnpm migrate:create` khi đổi collection, Railway (root dir `cms`, `pnpm start`, healthcheck `/api/admins/me` trả 200 `user: null`), ghi chú "`frontend/` npm, `cms/` pnpm, gốc Python", và mục **Lưu trữ nhật ký** (đề xuất C của khảo sát): KLAW giữ `nhat_ky_quan_tri` và `nhat_ky_cms` vô thời hạn, không có job dọn; bản sao giữ được duy nhất là CSV admin tự xuất (trần 5.000 dòng mỗi lần, theo bộ lọc), khuyến nghị mỗi tháng một lần; stream ra kho ngoài nằm ngoài phạm vi. Thêm một dòng vào `docs/README.md` trỏ tới `cms/README.md`.

- [ ] **Bước 6: Migration đầu tiên**

`cd cms && pnpm migrate:create khoi_tao` → commit `migrations/`. Trên `klaw_cms` sạch: `pnpm migrate`; `psql -d klaw -c '\dt'` trước và sau phải cùng số bảng (§9).

- [ ] **Bước 7: Xanh; build; tay**

Run: `cd cms && pnpm lint && pnpm type-check && pnpm build && pnpm test`. Tay: Nhật ký hiện các dòng đã tạo ở Task 12–13; Xuất CSV đúng số dòng như bảng; tab Nhật ký CMS có `dang_nhap` và một `dang_nhap_that_bai` (thử đăng nhập sai một lần). Ảnh `cms-06-nhat-ky.png`.

- [ ] **Bước 8: Commit**

```bash
git add cms .github/workflows/ci.yml docs/README.md
git commit -m "feat(cms): audit log view with CSV export, verified start script, CI job and runbook"
```

**Kết thúc giai đoạn 2:** duyệt một yêu cầu thật từ giao diện; bí mật không lọt bundle; CI xanh.

---
### Task 15: Frontend KLAW — lý do từ chối và thẻ tài khoản bị khoá

**Files:**
- Modify: `frontend/src/lib/klaw.ts` (`YeuCauNangGoi` ~724, `HanMuc` ~514, `laHanMuc` ~988)
- Modify: `frontend/src/lib/han-muc.ts` (thêm `laBiKhoa`)
- Modify: `frontend/src/components/tai-khoan/ModalNangGoi.tsx` (dưới `nutCaNhan` của card Cá nhân)
- Create: `frontend/src/components/tai-khoan/TheTaiKhoanKhoa.tsx`
- Modify: `frontend/src/routes/dung-thu.tsx` (~399 `plan`, ~418 `khoaOHoi`, khối render trên dòng chat), `frontend/src/routes/soan-thao.index.tsx` (nút bắt đầu soạn)
- Modify: `frontend/scripts/kiem-han-muc.ts`

**Interfaces:**
- Consumes: `HanMucResponse.bi_khoa`, `YeuCauNangGoiOut.ly_do` (Task 1, 4, 5); `useTaiKhoan().hanMuc`.
- Produces: `laBiKhoa(hm: HanMuc | null): boolean`; `TheTaiKhoanKhoa()`.

- [ ] **Bước 1: Kiểu và guard**

`klaw.ts`: thêm `ly_do: string | null;` vào `YeuCauNangGoi`; thêm `bi_khoa: boolean;` vào `HanMuc`; trong `laHanMuc` thêm điều kiện `typeof x["bi_khoa"] === "boolean"`. `han-muc.ts`:

```ts
/** Tài khoản bị admin khoá (spec 2B §5.2). Chỉ người đã đăng nhập mới có cờ này; khách luôn false. */
export const laBiKhoa = (hm: HanMuc | null): boolean => hm?.bi_khoa === true;
```

- [ ] **Bước 2: Script kiểm (đỏ)** — thêm vào `kiem-han-muc.ts`:

```ts
import { laBiKhoa } from "../src/lib/han-muc.ts";
{
  const hm = { ap_dung: true, plan: "free", ten_goi: "Miễn phí", mui_gio: "Asia/Ho_Chi_Minh", muc: [], phien: { luot_toi_da: 20 }, het_han_luc: null, ghi_chu: "", bi_khoa: true };
  assert.equal(laBiKhoa(hm), true);
  assert.equal(laBiKhoa({ ...hm, bi_khoa: false }), false);
  assert.equal(laBiKhoa(null), false);
}
```

Run: `cd frontend && npm run kiem-han-muc` → FAIL (`laBiKhoa` chưa export) → thêm hàm → PASS.

- [ ] **Bước 3: `ModalNangGoi`**

Dưới dòng chữ "Chưa có thanh toán trực tuyến…" của card Cá nhân, thêm:

```tsx
{yeuCau?.trang_thai === "tu_choi" && yeuCau.ly_do !== null && (
  <p role="status" className="mt-2 mb-0 text-[13px] leading-5 text-muted-foreground">
    Yêu cầu trước chưa được duyệt: {yeuCau.ly_do}. Bạn gửi lại được ngay.
  </p>
)}
```

Nút "Yêu cầu nâng lên Cá nhân" vẫn bật khi `trang_thai === "tu_choi"` (chỉ `cho_duyet` mới khoá — `dangCho` hiện có đã đúng).

- [ ] **Bước 4: `TheTaiKhoanKhoa`**

```tsx
// frontend/src/components/tai-khoan/TheTaiKhoanKhoa.tsx
import { Link } from "@tanstack/react-router";

/**
 * Tài khoản bị admin khoá (spec 2B §7). Câu đầu là câu của máy chủ; câu sau nói việc còn làm
 * được: tra cứu luật và soát văn bản không tốn LLM nên vẫn mở. Không dùng màu hiệu lực
 * (đỏ dành cho luật hết hiệu lực — xem BaoLoi).
 */
export function TheTaiKhoanKhoa() {
  return (
    <div
      role="alert"
      className="mt-4 rounded-xl border border-border border-l-2 bg-[var(--color-paper-50)] p-4"
      style={{ borderLeftColor: "var(--color-status-neutral)" }}
    >
      <p className="doc-prose m-0 text-foreground">Tài khoản của bạn đang bị tạm khoá. Liên hệ hỗ trợ để được mở lại.</p>
      <p className="mt-2 mb-0 text-[14px] leading-6 text-muted-foreground">
        Tra cứu luật và soát văn bản vẫn dùng được; hỏi đáp và soạn văn bản mở lại sau khi tài khoản được mở.
      </p>
      <Link
        to="/huong-dan"
        className="focus-brass mt-3 inline-flex min-h-11 items-center rounded-lg border border-border px-4 text-[15px] font-medium text-primary hover:bg-[var(--color-paper-100)]"
      >
        Trợ giúp và liên hệ
      </Link>
    </div>
  );
}
```

Nếu `bang-gia.tsx` hoặc `huong-dan.tsx` đã có liên kết `mailto:` hỗ trợ (grep `mailto:`), dùng cùng địa chỉ đó làm nút thứ hai "Gửi email hỗ trợ"; không có thì chỉ giữ liên kết Trợ giúp — không bịa địa chỉ.

- [ ] **Bước 5: `dung-thu.tsx` và `soan-thao.index.tsx`**

`dung-thu.tsx`: sau `const plan = …` (≈399) thêm `const biKhoa = laBiKhoa(hanMuc.hanMuc);`; đổi dòng 418 thành `const khoaOHoi = biKhoa || traCuu.dangChay || hoiThoai.loiChiTiet !== null || phienDay || khachHetLuot;`; trong khối render trên dòng chat (ngay trước `{traCuu.loi !== null && (…)}`), thêm `{biKhoa && <TheTaiKhoanKhoa />}`. Import `laBiKhoa` và `TheTaiKhoanKhoa`.

`soan-thao.index.tsx`: nơi nút "Soạn bản thảo" hiện `TheDangNhap` cho khách, thêm nhánh: `laBiKhoa(hanMuc)` (lấy `hanMuc` từ `useTaiKhoan()`) → render `<TheTaiKhoanKhoa />` thay nút. Xem biểu mẫu vẫn mở.

- [ ] **Bước 6: Kiểm**

Run: `cd frontend && npm run typecheck && npm run lint && npm run kiem-han-muc && npm run build`. Tay (KLAW + FE chạy, `KLAW_SUPABASE_URL` đặt để xác thực JWT thật): khoá tài khoản thử từ CMS → tải lại `/dung-thu` thấy thẻ khoá, ô hỏi khoá, `/tra-cuu` vẫn mở; mở khoá → bình thường; từ chối một yêu cầu với lý do → `ModalNangGoi` hiện lý do và nút gửi lại bật. Ảnh `.tham-dinh-shots/fe-01-khoa.png`, `fe-02-ly-do-tu-choi.png`.

- [ ] **Bước 7: Commit**

```bash
git add frontend/src/lib/klaw.ts frontend/src/lib/han-muc.ts frontend/src/components/tai-khoan/ModalNangGoi.tsx frontend/src/components/tai-khoan/TheTaiKhoanKhoa.tsx frontend/src/routes/dung-thu.tsx frontend/src/routes/soan-thao.index.tsx frontend/scripts/kiem-han-muc.ts
git commit -m "feat(frontend): show rejection reason in the upgrade modal and a suspended-account card"
```

---

## Giai đoạn 3 — Thông báo hai chiều (cắt được)

### Task 16: KLAW — thông báo admin khi có yêu cầu, sáu endpoint, SSE

**Files:**
- Modify: `src/services/nang_goi.py` (`_SQL_USER`, `tao_yeu_cau`)
- Modify: `src/services/thong_bao.py` (thêm `hop_thu`)
- Create: `src/api/luong_thong_bao.py`
- Modify: `src/api/routes_admin.py` (ba endpoint), `src/api/routes_tai_khoan.py` (ba endpoint)
- Test: `tests/test_api/test_luong_thong_bao.py`, `tests/test_api/test_thong_bao_api.py`

**Interfaces:**
- Consumes: `thong_bao.*`, `DaDocRequest`, `DanhSachThongBaoOut`, `kiem_admin_key`, `nguoi_dung_bat_buoc`.
- Produces:
  - `thong_bao.hop_thu(nguoi_nhan: str | None, chi_chua_doc: bool) -> dict` → `{"so_chua_doc", "items"}`.
  - `luong_thong_bao.sse(ten: str, du_lieu: dict) -> str`; `luong_thong_bao.phat(nguoi_nhan: str | None, *, chu_ky_giay=5.0, nhip_giay=15.0, toi_da_giay=1800.0) -> AsyncIterator[str]` — khung `event: so_chua_doc\ndata: {"so": n}\n\n`, `event: thong_bao_moi\ndata: {…ThongBaoOut}\n\n`, `: ping\n\n`.
  - `GET /admin/thong-bao?chi_chua_doc=`, `POST /admin/thong-bao/da-doc` → `{"da_danh_dau": int}`, `GET /admin/thong-bao/luong`; `GET /thong-bao`, `POST /thong-bao/da-doc`, `GET /thong-bao/luong` (bearer).

- [ ] **Bước 1: Test (đỏ)**

```python
# tests/test_api/test_luong_thong_bao.py
"""Generator SSE hộp thư (spec 2B §5.5): phát khi số đếm đổi, nhịp tim, dừng đúng hạn."""

import asyncio

import pytest

from src.api import luong_thong_bao
from src.services import thong_bao


def test_sse_dung_khung():
    assert luong_thong_bao.sse("so_chua_doc", {"so": 2}) == 'event: so_chua_doc\ndata: {"so": 2}\n\n'


@pytest.mark.asyncio
async def test_phat_khi_so_doi_va_ping(monkeypatch):
    dem = iter([0, 1])
    monkeypatch.setattr(thong_bao, "dem_chua_doc", lambda nn: next(dem, 1))
    monkeypatch.setattr(
        thong_bao,
        "danh_sach",
        lambda nn, chi_chua_doc=False, limit=50: [
            {"id": 9, "loai": "yeu_cau_moi", "tieu_de": "t", "noi_dung": "n", "duong_dan": "/x", "da_doc": False,
             "tao_luc": "2026-09-08T00:00:00+00:00"}
        ],
    )
    khung = [k async for k in luong_thong_bao.phat(None, chu_ky_giay=0.01, nhip_giay=0.03, toi_da_giay=0.15)]
    chuoi = "".join(khung)
    assert 'event: so_chua_doc\ndata: {"so": 0}' in chuoi and 'event: so_chua_doc\ndata: {"so": 1}' in chuoi
    assert chuoi.count("event: thong_bao_moi") == 1 and '"id": 9' in chuoi, "phát một lần khi số tăng, không lặp"
    assert ": ping\n\n" in chuoi


@pytest.mark.asyncio
async def test_phat_dung_sau_toi_da(monkeypatch):
    monkeypatch.setattr(thong_bao, "dem_chua_doc", lambda nn: 0)
    t0 = asyncio.get_running_loop().time()
    async for _ in luong_thong_bao.phat("00000000-0000-0000-0000-000000000001", chu_ky_giay=0.01, nhip_giay=1, toi_da_giay=0.05):
        pass
    assert asyncio.get_running_loop().time() - t0 < 1
```

```python
# tests/test_api/test_thong_bao_api.py
"""Sáu endpoint thông báo (spec 2B §5.3, §5.4) và thông báo admin sinh từ `tao_yeu_cau`."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, nang_goi, thong_bao
from src.services.db import get_engine
from tests.test_api.test_tra_cuu_phien import SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration
H = {"X-Admin-Key": "khoa-thu", "X-Admin-Boi": "qa@klaw.local"}


@pytest.fixture
def nguoi(cai_dat, khoa_ky):
    cai_dat(admin_api_key="khoa-thu", supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "tb-api@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(
            text("DELETE FROM thong_bao WHERE nguoi_nhan = CAST(:s AS uuid) OR khoa_gom LIKE :k"),
            {"s": sub, "k": f"%{sub}%"},
        )
        c.execute(text("DELETE FROM nhat_ky_quan_tri WHERE boi = 'qa@klaw.local'"))
        c.execute(text("DELETE FROM yeu_cau_nang_goi WHERE user_sub = CAST(:s AS uuid)"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = CAST(:s AS uuid)"), {"s": sub})


async def test_tao_yeu_cau_sinh_mot_thong_bao_admin_va_duyet_vo_hieu_no(client, nguoi, khoa_ky):
    h = _bearer(khoa_ky, nguoi)
    truoc = thong_bao.dem_chua_doc(None)
    assert (await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)).status_code == 201
    assert (await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)).status_code == 409
    assert thong_bao.dem_chua_doc(None) == truoc + 1, "hai lần gửi, một thông báo"
    hop = (await client.get("/api/v1/admin/thong-bao", params={"chi_chua_doc": "true"}, headers=H)).json()
    dong = next(x for x in hop["items"] if "tb-api@test.local" in x["noi_dung"])
    assert dong["loai"] == "yeu_cau_moi" and dong["duong_dan"].startswith("/admin/yeu-cau")
    yc = nang_goi.moi_nhat(nguoi)
    assert (await client.post(f"/api/v1/admin/yeu-cau/{yc['id']}/duyet", headers=H)).status_code == 200
    assert thong_bao.dem_chua_doc(None) == truoc, "duyệt xong thì thông báo admin hết hiệu lực"
    tb = (await client.get("/api/v1/thong-bao", headers=h)).json()
    assert tb["so_chua_doc"] == 1 and tb["items"][0]["loai"] == "yeu_cau_duyet"
    r = await client.post("/api/v1/thong-bao/da-doc", json={"ids": [tb["items"][0]["id"]]}, headers=h)
    assert r.status_code == 200 and r.json()["da_danh_dau"] == 1
    assert (await client.get("/api/v1/thong-bao", headers=h)).json()["so_chua_doc"] == 0


async def test_da_doc_khong_dong_toi_hop_thu_nguoi_khac(client, nguoi, khoa_ky):
    i = thong_bao.ghi(nguoi_nhan=None, loai="yeu_cau_moi", tieu_de="t", noi_dung="n", duong_dan="/x", khoa_gom=f"test:{nguoi}")
    r = await client.post("/api/v1/thong-bao/da-doc", json={"ids": [i]}, headers=_bearer(khoa_ky, nguoi))
    assert r.status_code == 200 and r.json()["da_danh_dau"] == 0


async def test_luong_tra_event_stream(client, nguoi, khoa_ky, monkeypatch):
    from src.api import luong_thong_bao

    async def ngan(nn, **kw):
        yield luong_thong_bao.sse("so_chua_doc", {"so": 0})

    monkeypatch.setattr(luong_thong_bao, "phat", ngan)
    r = await client.get("/api/v1/admin/thong-bao/luong", headers=H)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream") and "so_chua_doc" in r.text
    r = await client.get("/api/v1/thong-bao/luong", headers=_bearer(khoa_ky, nguoi))
    assert r.status_code == 200 and "so_chua_doc" in r.text
```

Router phải gọi `luong_thong_bao.phat(...)` qua thuộc tính module (không `from … import phat`) để `monkeypatch` có tác dụng — cùng quy ước `bao_ve.<tên>` của repo.

- [ ] **Bước 2: Đỏ** — `.venv/bin/python -m pytest tests/test_api/test_luong_thong_bao.py tests/test_api/test_thong_bao_api.py -q`.

- [ ] **Bước 3: `tao_yeu_cau` ghi thông báo admin; `hop_thu`**

`nang_goi._SQL_USER`: `"SELECT plan, plan_het_han, email FROM users WHERE sub = :sub"`. Trong khối `with get_engine().begin() as c:` của `tao_yeu_cau`, sau `r = c.execute(_SQL_TAO …)`:

```python
            viec = "gia hạn" if loai == "gia_han" else "nâng lên"
            thong_bao.ghi(
                nguoi_nhan=None, loai="yeu_cau_moi", tieu_de="Yêu cầu nâng gói mới",
                noi_dung=f"{u['email'] or sub} muốn {viec} gói {ten_goi(goi_muon)}.",
                duong_dan="/admin/yeu-cau?trang_thai=cho_duyet",
                khoa_gom=thong_bao.KHOA_YEU_CAU.format(sub=sub), c=c,
            )
```

`thong_bao.ghi` trả `None` khi đụng khoá gộp — không lỗi. `IntegrityError` của unique index `cho_duyet` vẫn được bắt ở ngoài như cũ.

`thong_bao.py` thêm:

```python
def hop_thu(nguoi_nhan: str | None, chi_chua_doc: bool = False) -> dict:
    """Hình `DanhSachThongBaoOut` — dùng chung cho router admin và router người dùng."""
    return {"so_chua_doc": dem_chua_doc(nguoi_nhan), "items": danh_sach(nguoi_nhan, chi_chua_doc=chi_chua_doc)}
```

- [ ] **Bước 4: `luong_thong_bao.py`**

```python
# src/api/luong_thong_bao.py
"""SSE hộp thư thông báo (spec 2026-09-08 cms-quan-ly-tai-khoan §5.5).

Polling PHÍA MÁY CHỦ: hỏi DB mỗi `chu_ky_giay`, chỉ phát khi số chưa đọc đổi; `: ping`
khi im lặng quá `nhip_giay`; đóng sau `toi_da_giay` để không giữ tài nguyên vô hạn —
client tự nối lại. Nguồn sự thật là `GET …/thong-bao`; luồng này chỉ đẩy nhanh.
"""

import asyncio
import functools
import json
from collections.abc import AsyncIterator

from fastapi.encoders import jsonable_encoder
from starlette.concurrency import run_in_threadpool

from src.services import thong_bao


def sse(ten: str, du_lieu: dict) -> str:
    return f"event: {ten}\ndata: {json.dumps(jsonable_encoder(du_lieu), ensure_ascii=False)}\n\n"


async def phat(
    nguoi_nhan: str | None,
    *,
    chu_ky_giay: float = 5.0,
    nhip_giay: float = 15.0,
    toi_da_giay: float = 1800.0,
) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    bat_dau = loop.time()
    lan_phat = bat_dau
    truoc: int | None = None
    while loop.time() - bat_dau < toi_da_giay:
        so = await run_in_threadpool(thong_bao.dem_chua_doc, nguoi_nhan)
        if so != truoc:
            yield sse("so_chua_doc", {"so": so})
            if truoc is not None and so > truoc:
                moi = await run_in_threadpool(functools.partial(thong_bao.danh_sach, nguoi_nhan, chi_chua_doc=True, limit=1))
                if moi:
                    yield sse("thong_bao_moi", moi[0])
            truoc = so
            lan_phat = loop.time()
        elif loop.time() - lan_phat >= nhip_giay:
            yield ": ping\n\n"
            lan_phat = loop.time()
        await asyncio.sleep(chu_ky_giay)
```

- [ ] **Bước 5: Sáu endpoint**

`routes_admin.py` (import `from fastapi.responses import StreamingResponse`, `from src.api import luong_thong_bao`, `from src.services import thong_bao`, model `DaDocRequest`, `DanhSachThongBaoOut`):

```python
_HEADER_SSE = {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}


@router.get("/thong-bao", response_model=DanhSachThongBaoOut)
async def hop_thu_admin(ctx: dict = Depends(kiem_admin_key), chi_chua_doc: bool = False) -> DanhSachThongBaoOut:
    return DanhSachThongBaoOut.model_validate(await run_in_threadpool(thong_bao.hop_thu, None, chi_chua_doc))


@router.post("/thong-bao/da-doc")
async def da_doc_admin(body: DaDocRequest, ctx: dict = Depends(kiem_admin_key)) -> dict:
    return {"da_danh_dau": await run_in_threadpool(thong_bao.danh_dau_da_doc, body.ids, None)}


@router.get("/thong-bao/luong")
async def luong_admin(ctx: dict = Depends(kiem_admin_key)) -> StreamingResponse:
    return StreamingResponse(luong_thong_bao.phat(None), media_type="text/event-stream", headers=_HEADER_SSE)
```

`routes_tai_khoan.py` — cùng khuôn với `nguoi: dict = Depends(nguoi_dung_bat_buoc)` và `nguoi["sub"]`, đường `/thong-bao`, `/thong-bao/da-doc`, `/thong-bao/luong`.

- [ ] **Bước 6: Xanh; lint; bộ rộng**

Run: `.venv/bin/python -m pytest tests/test_api/test_luong_thong_bao.py tests/test_api/test_thong_bao_api.py tests/test_services/test_thong_bao.py tests/test_api/test_ho_so_nang_goi.py -q && .venv/bin/ruff check src/ tests/ && .venv/bin/python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py 2>&1 | tail -3`

- [ ] **Bước 7: Commit**

```bash
git add src/services/nang_goi.py src/services/thong_bao.py src/api/luong_thong_bao.py src/api/routes_admin.py src/api/routes_tai_khoan.py tests/test_api/test_luong_thong_bao.py tests/test_api/test_thong_bao_api.py
git commit -m "feat(api): two-way notifications with admin and user inboxes and server-polled SSE"
```

---

### Task 17: CMS — chuông thông báo

**Files:**
- Create: `cms/src/components/ChuongThongBao/index.tsx`, `cms/src/components/ChuongThongBao/bell.ts`, `cms/src/components/ChuongThongBao/index.scss`
- Modify: `cms/payload.config.ts` (`admin.components.actions`)
- Test: `cms/tests/bell.spec.ts`

**Interfaces:**
- Consumes: `/api/klaw/thong-bao?chi_chua_doc=`, `POST /api/klaw/thong-bao/da-doc {ids}`, `EventSource('/api/klaw/thong-bao/luong')`.
- Produces (`bell.ts`, thuần): `type ThongBao = { id: number; loai: string; tieu_de: string; noi_dung: string; duong_dan: string; da_doc: boolean; tao_luc: string }`; `BADGE_CAP = 99`; `formatBadge(n: number): string | null`; `bucketFor(iso: string, now: Date): 'today' | 'yesterday' | 'older'`; `nhomTheoNgay(items, now): { nhan: string; items: ThongBao[] }[]`; `duongDanCms(duong: string): string`.

- [ ] **Bước 1: Test (đỏ)**

```ts
// cms/tests/bell.spec.ts
import { describe, expect, it } from 'vitest'
import { bucketFor, duongDanCms, formatBadge, nhomTheoNgay } from '../src/components/ChuongThongBao/bell'

const tb = (id: number, iso: string) => ({ id, loai: 'yeu_cau_moi', tieu_de: 't', noi_dung: 'n', duong_dan: '/admin/yeu-cau', da_doc: false, tao_luc: iso })

describe('bell.ts', () => {
  it('badge: 0 → null, 99+ khi vượt trần', () => {
    expect(formatBadge(0)).toBeNull(); expect(formatBadge(7)).toBe('7'); expect(formatBadge(150)).toBe('99+')
  })
  it('bucket theo NGÀY lịch, không theo giờ trôi', () => {
    const now = new Date(2026, 8, 9, 0, 10)
    expect(bucketFor(new Date(2026, 8, 8, 23, 50).toISOString(), now)).toBe('yesterday')
    expect(bucketFor(new Date(2026, 8, 9, 0, 5).toISOString(), now)).toBe('today')
    expect(bucketFor('rác', now)).toBe('older')
  })
  it('nhóm bỏ nhóm rỗng, giữ thứ tự Hôm nay → Hôm qua → Trước đó', () => {
    const now = new Date(2026, 8, 9, 12)
    const nhom = nhomTheoNgay([tb(1, new Date(2026, 8, 1).toISOString()), tb(2, new Date(2026, 8, 9, 8).toISOString())], now)
    expect(nhom.map((n) => n.nhan)).toEqual(['Hôm nay', 'Trước đó'])
  })
  it('đường dẫn ngoài /admin bị đưa về /admin', () => {
    expect(duongDanCms('/admin/yeu-cau?trang_thai=cho_duyet')).toBe('/admin/yeu-cau?trang_thai=cho_duyet')
    expect(duongDanCms('https://x.y/z')).toBe('/admin')
  })
})
```

- [ ] **Bước 2: Đỏ**, rồi viết `bell.ts`:

```ts
// cms/src/components/ChuongThongBao/bell.ts
export type ThongBao = { id: number; loai: string; tieu_de: string; noi_dung: string; duong_dan: string; da_doc: boolean; tao_luc: string }
export const BADGE_CAP = 99
export const formatBadge = (n: number): string | null => (n <= 0 ? null : n > BADGE_CAP ? `${BADGE_CAP}+` : String(n))

export type DayBucket = 'today' | 'yesterday' | 'older'
const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
export const bucketFor = (iso: string, now: Date): DayBucket => {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return 'older'
  const today = startOfDay(now)
  const yesterday = startOfDay(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1))
  const day = startOfDay(then)
  return day >= today ? 'today' : day >= yesterday ? 'yesterday' : 'older'
}
const NHAN: Record<DayBucket, string> = { today: 'Hôm nay', yesterday: 'Hôm qua', older: 'Trước đó' }
export const nhomTheoNgay = (items: ThongBao[], now: Date) =>
  (['today', 'yesterday', 'older'] as DayBucket[])
    .map((b) => ({ nhan: NHAN[b], items: items.filter((t) => bucketFor(t.tao_luc, now) === b) }))
    .filter((n) => n.items.length > 0)

/** Chỉ điều hướng trong admin: một `duong_dan` lạ từ dữ liệu không được kéo trình duyệt đi đâu khác. */
export const duongDanCms = (duong: string): string => (duong === '/admin' || duong.startsWith('/admin/') ? duong : '/admin')
```

`index.tsx` (`'use client'`): chuyển từ `~/VF_TTS/vsf-cms-multiple-sites-backend/src/payload/components/NotificationBell/index.tsx`, đổi: nguồn `goiQuanTri<{ so_chua_doc: number; items: ThongBao[] }>('/thong-bao')`; `new EventSource('/api/klaw/thong-bao/luong')` với `addEventListener('so_chua_doc', () => tai())` (không đọc payload, chỉ tải lại — nguồn sự thật là GET); `onerror` để trình duyệt tự nối lại, không viết retry; tải lại khi `document.visibilitychange` về visible; nút chuông `aria-label={`Thông báo${so > 0 ? `, ${so} chưa đọc` : ''}`}`, badge `formatBadge`, popover `role="menu"` liệt kê `nhomTheoNgay`, bấm một dòng → `goiQuanTri('/thong-bao/da-doc', { method: 'POST', body: { ids: [id] } })` rồi `router.push(duongDanCms(duong_dan))`; nút "Đánh dấu tất cả đã đọc". Badge trên tiêu đề tab: `document.title = so > 0 ? `(${so}) ${goc}` : goc`. `index.scss` chép nguyên, đổi class gốc `notification-bell` → `chuong-thong-bao`.

`payload.config.ts`: `components.actions: ['@/components/ChuongThongBao#ChuongThongBao']`. `pnpm payload generate:importmap`.

- [ ] **Bước 3: Xanh; build; tay**

Run: `cd cms && pnpm test && pnpm lint && pnpm type-check && pnpm build`. Tay (KLAW giai đoạn 3 chạy): mở CMS; từ KLAW FE gửi một yêu cầu → badge tăng trong ≤ 10 giây không tải lại; bấm dòng → sang `/admin/yeu-cau`, badge giảm. Ảnh `cms-07-chuong.png`.

- [ ] **Bước 4: Commit**

```bash
git add cms
git commit -m "feat(cms): notification bell fed by the KLAW admin inbox over SSE"
```

---

### Task 18: Frontend KLAW — chuông người dùng

**Files:**
- Create: `frontend/src/lib/thong-bao.ts`, `frontend/src/hooks/use-thong-bao.ts`, `frontend/src/components/tai-khoan/ChuongThongBao.tsx`, `frontend/scripts/kiem-thong-bao.ts`
- Modify: `frontend/src/lib/klaw.ts` (kiểu + guard), `frontend/src/lib/api.ts` (export `tieuDeXacThuc` nếu chưa), `frontend/src/components/app/AppShell.tsx` (~236, cạnh `TheTaiKhoan`), `frontend/package.json` (script `kiem-thong-bao`, nối vào `kiem`)

**Interfaces:**
- Consumes: `GET /thong-bao`, `POST /thong-bao/da-doc`, `GET /thong-bao/luong` (bearer); `goi()`, `apiGoc()`, `tieuDeXacThuc()`, `catCacKhung` từ `lib/sse-khung.ts`.
- Produces:
  - `klaw.ts`: `interface ThongBao { id: number; loai: string; tieu_de: string; noi_dung: string; duong_dan: string; da_doc: boolean; tao_luc: string }`, `interface HopThu { so_chua_doc: number; items: ThongBao[] }`, `laHopThu(x): x is HopThu`, `laDaDanhDau(x): x is { da_danh_dau: number }`.
  - `lib/thong-bao.ts` (thuần): `formatBadge(n)`, `nhomTheoNgay(items, now)` (cùng logic Task 17, viết lại — hai gói không chia sẻ mã), `duongDanTrongApp(duong): string` (chỉ cho đường bắt đầu `/tai-khoan` hoặc `/dung-thu`; khác → `/tai-khoan`).
  - `useThongBao(kichHoat: boolean): { soChuaDoc: number; items: ThongBao[]; dangTai: boolean; taiLai(): void; danhDauDaDoc(ids: number[]): Promise<void> }`.
  - `ChuongThongBao()`.

- [ ] **Bước 1: Script kiểm (đỏ)**

```ts
// frontend/scripts/kiem-thong-bao.ts
/** Chuông người dùng (spec 2B §7): badge, nhóm theo ngày, đường dẫn an toàn. Chạy: `npm run kiem-thong-bao`. */
import assert from "node:assert/strict";
import { duongDanTrongApp, formatBadge, nhomTheoNgay } from "../src/lib/thong-bao.ts";

const tb = (id: number, tao_luc: string) => ({ id, loai: "yeu_cau_duyet", tieu_de: "t", noi_dung: "n", duong_dan: "/tai-khoan", da_doc: false, tao_luc });
assert.equal(formatBadge(0), null);
assert.equal(formatBadge(3), "3");
assert.equal(formatBadge(120), "99+");
const now = new Date(2026, 8, 9, 12);
assert.deepEqual(
  nhomTheoNgay([tb(1, new Date(2026, 8, 1).toISOString()), tb(2, new Date(2026, 8, 9, 8).toISOString())], now).map((n) => n.nhan),
  ["Hôm nay", "Trước đó"],
);
assert.equal(duongDanTrongApp("/tai-khoan"), "/tai-khoan");
assert.equal(duongDanTrongApp("https://x/y"), "/tai-khoan");
console.log("kiem-thong-bao: 6/6");
```

`package.json`: `"kiem-thong-bao": "node scripts/kiem-thong-bao.ts"` và nối `&& npm run kiem-thong-bao` vào chuỗi `kiem` (trước `python3 scripts/do-tuong-phan.py`).

- [ ] **Bước 2: Đỏ** — `npm run kiem-thong-bao` → FAIL. Viết `lib/thong-bao.ts` (cùng logic `bell.ts` Task 17 + `duongDanTrongApp`), kiểu và guard trong `klaw.ts` (`laHopThu`: `laBanGhi(x) && typeof x["so_chua_doc"] === "number" && Array.isArray(x["items"])`; `laDaDanhDau`: `laBanGhi(x) && typeof x["da_danh_dau"] === "number"`). → PASS.

- [ ] **Bước 3: `use-thong-bao.ts`**

```ts
import { useCallback, useEffect, useRef, useState } from "react";
import { apiGoc, goi, tieuDeXacThuc } from "@/lib/api";
import { laDaDanhDau, laHopThu, type ThongBao } from "@/lib/klaw";
import { catCacKhung } from "@/lib/sse-khung";

const NOI_LAI_MS = 5_000;

/** Hộp thư của chính người gọi. Nguồn sự thật là GET; SSE chỉ báo "tải lại". Dùng `fetch` +
 *  `ReadableStream` như `traCuuLuong` vì `EventSource` không gửi được `Authorization`. */
export function useThongBao(kichHoat: boolean) {
  const [items, setItems] = useState<ThongBao[]>([]);
  const [soChuaDoc, setSo] = useState(0);
  const [dangTai, setDangTai] = useState(false);
  const huy = useRef<AbortController | null>(null);

  const taiLai = useCallback(() => {
    if (!kichHoat) return;
    setDangTai(true);
    void goi("/thong-bao", laHopThu).then((r) => {
      setDangTai(false);
      if (r.ok) {
        setItems(r.data.items);
        setSo(r.data.so_chua_doc);
      }
    });
  }, [kichHoat]);

  const danhDauDaDoc = useCallback(
    async (ids: number[]) => {
      if (ids.length === 0) return;
      const r = await goi("/thong-bao/da-doc", laDaDanhDau, { method: "POST", body: { ids } });
      if (r.ok) taiLai();
    },
    [taiLai],
  );

  useEffect(() => {
    taiLai();
  }, [taiLai]);

  useEffect(() => {
    if (!kichHoat) return;
    let dung = false;
    const noi = async () => {
      while (!dung) {
        const ac = new AbortController();
        huy.current = ac;
        try {
          const res = await fetch(`${apiGoc()}/thong-bao/luong`, {
            headers: { ...(await tieuDeXacThuc()), Accept: "text/event-stream" },
            signal: ac.signal,
          });
          if (!res.ok || res.body === null) throw new Error(String(res.status));
          const doc = res.body.getReader();
          const giaiMa = new TextDecoder();
          let dem = "";
          for (;;) {
            const { done, value } = await doc.read();
            if (done) break;
            const cat = catCacKhung(`${dem}${giaiMa.decode(value, { stream: true })}`);
            dem = cat.con;
            if (cat.khung.some((k) => k.event === "so_chua_doc")) taiLai();
          }
        } catch {
          /* mất kết nối hoặc hết 30 phút: nối lại bên dưới */
        }
        if (!dung) await new Promise((r) => setTimeout(r, NOI_LAI_MS));
      }
    };
    void noi();
    return () => {
      dung = true;
      huy.current?.abort();
    };
  }, [kichHoat, taiLai]);

  return { soChuaDoc, items, dangTai, taiLai, danhDauDaDoc };
}
```

Kiểm tên trường của `KhungSSE` trong `sse-khung.ts` (`event` hay `ten`) và chỉnh `k.event` cho khớp. `tieuDeXacThuc` (`api.ts` ~73) phải được `export`.

- [ ] **Bước 4: `ChuongThongBao.tsx` và gắn vào `AppShell`**

Cùng khuôn `MenuTaiKhoan`: nút với icon `Bell` (lucide) và badge `formatBadge`, `aria-label` như CMS; popover `role="menu"` mở/đóng bằng state, đóng khi Escape hoặc click ngoài, trả tiêu điểm về nút; danh sách `nhomTheoNgay(items, new Date())`, mỗi dòng `role="menuitem"`: `tieu_de` (đậm nếu chưa đọc), `noi_dung`, thời gian; bấm → `danhDauDaDoc([id])` rồi `navigate({ to: duongDanTrongApp(duong_dan) })`; dòng rỗng "Chưa có thông báo nào."; nút "Đã đọc tất cả" khi `so > 0`.

`AppShell.tsx` ~236: `{daDangNhap ? (<div className="flex items-center gap-2"><ChuongThongBao /><TheTaiKhoan gon={!rong} /></div>) : …}` — giữ nguyên hai nhánh còn lại. Ở `<768px` (sheet Tài khoản), thêm `<ChuongThongBao />` ngay trên `MenuTaiKhoan`.

- [ ] **Bước 5: Kiểm**

Run: `cd frontend && npm run typecheck && npm run lint && npm run kiem-thong-bao && npm run kiem-sse && npm run build`. Tay: đăng nhập FE; từ CMS duyệt yêu cầu của tài khoản đó → badge FE tăng trong ≤ 10 giây; bấm → `/tai-khoan`, badge về 0; tắt KLAW 10 giây rồi bật lại → luồng tự nối (đếm request `/thong-bao/luong` trong Network). Ảnh `fe-03-chuong.png`.

- [ ] **Bước 6: Commit**

```bash
git add frontend/src/lib/thong-bao.ts frontend/src/lib/klaw.ts frontend/src/lib/api.ts frontend/src/hooks/use-thong-bao.ts frontend/src/components/tai-khoan/ChuongThongBao.tsx frontend/src/components/app/AppShell.tsx frontend/scripts/kiem-thong-bao.ts frontend/package.json
git commit -m "feat(frontend): notification bell for signed-in users with bearer-authenticated SSE"
```

**Kết thúc giai đoạn 3:** badge hai phía tăng trong vài giây; `tao_yeu_cau` hai lần → một thông báo admin; `danh_dau_da_doc` không đụng hộp thư người khác.

---

## Đóng gói

- [ ] **Gộp hai worktree** vào `feat/tro-ly-phap-luat` (giai đoạn 1 trước, giai đoạn 2 sau; xung đột chỉ có thể ở `src/main.py` và `.github/workflows/ci.yml`).
- [ ] **Bộ kiểm toàn nhánh:** `.venv/bin/ruff check src/ tests/`; `.venv/bin/python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py` (đỏ duy nhất được phép: `test_moi_mau.py`); `cd frontend && npm run kiem`; `cd cms && pnpm lint && pnpm type-check && pnpm build && pnpm test`.
- [ ] **Bằng chứng theo §9 của spec** ghi vào `docs/plans/active/cms-quan-ly-tai-khoan.md` (template `docs/templates/exec-plan.md`), kèm đường dẫn ảnh trong `.tham-dinh-shots/`; sau khi chủ dự án xem, chuyển sang `docs/plans/completed/`.
- [ ] **Review toàn nhánh** bằng `ecc:code-reviewer` và `ecc:security-reviewer` (đường `/admin`, proxy, cookie, khoá tài khoản), sửa Critical/Important, re-review.
- [ ] **Gỡ `KLAW_ADMIN_API_KEY` tạm** khỏi `.env.local` nếu đã đặt để thử; hướng dẫn đặt biến này khi cần CMS ghi ở `cms/README.md` (không sửa `docs/guide/*` — file bẩn của chủ dự án).
