# Lịch sử hội thoại theo tài khoản — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Người đã đăng nhập có phiên hội thoại lưu ở máy chủ, mở lại và hỏi tiếp được; free giữ 10 phiên gần nhất (cũ hơn ẩn), pro không giới hạn.

**Architecture:** Hai bảng mới (`hoi_thoai`, `luot_hoi_thoai`, migration 020) lưu nguyên payload `TraCuuResponse` từng lượt. Endpoint stream nhận `hoi_thoai_id`: tự tạo phiên, tự nạp ba lượt gần nhất làm `lich_su`, ghi lượt sau khi trả lời (báo `loi_luu` nếu ghi hỏng). Router `/hoi-thoai` liệt kê/mở/đổi tên/xoá mềm, lọc theo `user_sub`, ẩn phiên vượt hạn gói (`config/han_muc.yaml: phien_luu`). Frontend thay cột "Lịch sử phiên" trong bộ nhớ bằng danh sách phiên thật, URL `?phien=`. Bước 0 khoá hợp đồng trên checkout chính; Bước 1 hai worktree BE/FE song song; Bước 2 gộp và kiểm.

**Tech Stack:** FastAPI + SQLAlchemy `text()` + pydantic v2 + pytest (integration với fixture `client`, `cai_dat`, `khoa_ky`, `_bearer`, `graph_gia_lap`); React 19 + TanStack Router + Tailwind 4, TS `exactOptionalPropertyTypes: true`, check scripts `frontend/scripts/kiem-*.ts`.

**Spec:** `docs/superpowers/specs/2026-09-07-lich-su-hoi-thoai-design.md`

## Global Constraints

- Mọi truy vấn phiên/lượt lọc theo `user_sub`; phiên của người khác → 404; phiên ẩn theo gói → 403 với `detail` chuỗi; ẩn danh → 401 ở `/hoi-thoai/*`, còn `/tra-cuu*` bỏ qua `hoi_thoai_id` và không ghi.
- `lich_su` khi có `hoi_thoai_id` do MÁY CHỦ nạp (3 lượt gần nhất, hình `LuotTruoc`: `cau_hoi`, `tra_loi` ≤2000, `duong_dan` list ≤50 phần tử duy nhất); `lich_su` client gửi bị bỏ qua. Câu nối tiếp không đi qua cache (giữ `(None, None, None) if req.lich_su`).
- Ghi lượt lỗi không làm mất câu trả lời: phát `event: loi_luu {hoi_thoai_id, detail}` sau `ket_qua`, log exception.
- `TraCuuResponse` không đổi; `TraCuuRequest.hoi_thoai_id: UUID | None = None` additive; `bat_dau` thêm `hoi_thoai_id: str | null`; `/tra-cuu` trả header `X-Hoi-Thoai-Id` khi có.
- `config/han_muc.yaml` thêm `phien_luu: {free: 10, pro: 100000}` — cùng quy ước: 0 = không hiện phiên nào, "không giới hạn" = số lớn; `_doc_han_muc` fail loud nếu thiếu gói.
- `lifespan` áp migration bằng danh sách `("019", "020")`.
- Frontend: không thêm dependency; chữ hiển thị mới không chứa "hệ thống", "không diễn giải", "chưa đủ căn cứ", "truy hồi", "database", "để bạn tự đối chiếu", "máy chủ trả về"; xưng "tôi".
- Không đụng: `Luot` (`<div className="mt-4 rounded-xl …">{children}</div>`), `chonTrichDan`, khối `KhungDoiChieu`, khối khung soạn thảo, `TheKetQua.tsx`, `KhongGianSoanThao.tsx`.
- Không chạy `make check`/`make format`. Python: `make lint` + pytest có đích + `ruff format --check <file đã sửa>` (drift dòng cũ là baseline). Pytest FOREGROUND, `timeout` 600000. Test tích hợp cần DB: chạy `python -c "from src.services.db import run_migrations; print(run_migrations('020'))"` một lần trước; `ASGITransport` không chạy `lifespan`.
- Worktree: symlink `.venv`, `data/raw`, `.env.local` (chứa DB URL và khoá LLM; gitignored), và `frontend/node_modules`. Không stage file bẩn có từ trước (docs/guide/*, scripts/log_*.py, README_boilerplate.md, src/services/checklist.py, tests/test_services/test_moi_mau.py, qh3.html, .impeccable/, eval/results/lexical_only-*.json, config/checklist_don_xin_nghi_viec.yaml, eval/datasets/golden_qa_candidates.yaml, .agents/, presentation/README.md).
- Commit tiếng Anh, conventional, kèm `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File Structure

| File | Trách nhiệm | Task |
|---|---|---|
| `migrations/020_hoi_thoai.sql` | hai bảng + chỉ mục | 1 |
| `config/han_muc.yaml` | `phien_luu` | 1 |
| `src/services/bao_ve.py` | kiểm `phien_luu` trong `_doc_han_muc`; `phien_luu_toi_da`; `plan_cua`; `nguoi_dung_bat_buoc` | 1 |
| `src/models/schemas.py` | `TraCuuRequest.hoi_thoai_id`; `PhienTomTatOut`, `DanhSachPhienResponse`, `LuotDaLuuOut`, `ChiTietPhienResponse`, `DoiTenPhienRequest` | 1 |
| `src/main.py` | migrations tuple; include `router_hoi_thoai` (Task 4) | 1, 4 |
| `frontend/src/lib/klaw.ts` | `PhienTomTat`, `DanhSachPhien`, `LuotDaLuu`, `ChiTietPhien`, `SuKienBatDau.hoi_thoai_id`, predicates, `chuanHoaLuot` | 1 |
| `frontend/src/lib/api.ts` | `YeuCauTraCuu.hoi_thoai_id`, `XuLyLuong.onLoiLuu`, sự kiện `loi_luu` | 1 |
| `docs/plans/active/lich-su-hoi-thoai.md` | plan bền | 1, 8 |
| `src/services/hoi_thoai.py` (mới) | SQL + quy tắc ẩn | 2 |
| `tests/test_services/test_hoi_thoai.py` (mới) | test dịch vụ trên DB thật | 2 |
| `src/api/routes.py`, `src/api/routes_luong.py` | `_chuan_bi_phien`, `_ghi_luot_nhe`, `bat_dau.hoi_thoai_id`, `loi_luu`, header | 3 |
| `tests/test_api/test_tra_cuu_phien.py` (mới) | stream/POST với danh tính giả | 3 |
| `src/api/routes_hoi_thoai.py` (mới), `tests/test_api/test_hoi_thoai.py` (mới) | CRUD phiên | 4 |
| `frontend/src/lib/phien.ts` (mới), `frontend/scripts/kiem-phien.ts` (mới), `frontend/package.json` | helper thuần + kiểm | 5 |
| `frontend/src/hooks/use-hoi-thoai.ts` (mới) | danh sách/chi tiết/đổi tên/xoá | 5 |
| `frontend/src/hooks/use-tra-cuu.ts` | `hoi(cauHoi, tuyChon)`, `hoiThoaiId`, `loiLuu` | 6 |
| `frontend/src/routes/dung-thu.tsx` | `?phien=`, tải phiên, phiên mới, không gửi `lich_su` khi đăng nhập | 6, 7 |
| `frontend/src/components/klaw/DanhSachPhien.tsx` (mới) | cột phiên + sheet | 7 |

Thứ tự: Task 1 (main) → BE worktree `../KLAW-be3` (`wt-be-phien`): 2 → 3 → 4; FE worktree `../KLAW-fe3` (`wt-fe-phien`): 5 → 6 → 7 (song song với BE) → Task 8 (main) gộp.

---

# BƯỚC 0 — HỢP ĐỒNG (checkout chính)

### Task 1: Migration, cấu hình hạn phiên, cổng danh tính, schema hai phía, worktree

**Files:**
- Create: `migrations/020_hoi_thoai.sql`, `docs/plans/active/lich-su-hoi-thoai.md`
- Modify: `config/han_muc.yaml`, `src/services/bao_ve.py`, `src/models/schemas.py` (sau `lich_su` của `TraCuuRequest`; và sau `NguoiDungResponse`), `src/main.py:52`, `frontend/src/lib/klaw.ts` (sau `SuKienBuoc`), `frontend/src/lib/api.ts` (`YeuCauTraCuu`, `XuLyLuong`, vòng đọc khung)
- Test: `tests/test_api/test_han_muc_phien.py` (mới)

**Interfaces:**
- Produces (BE): `bao_ve.phien_luu_toi_da(plan: str) -> int`; `bao_ve.plan_cua(sub: str) -> str` (SELECT `users.plan`, rơi về `goi_mac_dinh` khi chưa có dòng); `bao_ve.nguoi_dung_bat_buoc(request) -> dict` (`{"sub","email"}` hoặc 401); `TraCuuRequest.hoi_thoai_id: UUID | None`; models `PhienTomTatOut{id: str, tieu_de: str, so_luot: int, tao_luc: datetime, cap_nhat_luc: datetime}`, `DanhSachPhienResponse{plan: str, gioi_han: int, tong_hien: int, tong_an: int, items: list[PhienTomTatOut]}`, `LuotDaLuuOut{thu_tu: int, cau_hoi: str, tra_loi: dict, trace_id: str | None, tao_luc: datetime}`, `ChiTietPhienResponse{id, tieu_de, tao_luc, cap_nhat_luc, luot: list[LuotDaLuuOut]}`, `DoiTenPhienRequest{tieu_de: str}` (1–120, strip).
- Produces (FE): `PhienTomTat`, `DanhSachPhien`, `LuotDaLuu`, `ChiTietPhien`, `laDanhSachPhien`, `laChiTietPhien`, `chuanHoaLuot(l: LuotDaLuu): { thuTu: number; cauHoi: string; ketQua: TraCuuKetQua | null; traceId: string | null }`; `SuKienBatDau.hoi_thoai_id: string | null`; `YeuCauTraCuu.hoi_thoai_id?: string`; `XuLyLuong.onLoiLuu?: (su: SuKienLoiLuu) => void` với `SuKienLoiLuu{hoi_thoai_id: string; detail: string}`.

- [x] **Step 1: Plan bền** `docs/plans/active/lich-su-hoi-thoai.md`

```markdown
# Execution Plan: Lịch sử hội thoại theo tài khoản

Date: 2026-09-07

## Status

Active

## Spec / Plan

- docs/superpowers/specs/2026-09-07-lich-su-hoi-thoai-design.md
- docs/superpowers/plans/2026-09-07-lich-su-hoi-thoai.md

## Progress

- [x] Task 1 hợp đồng + migration 020 + phien_luu
- [x] Task 2 dịch vụ hoi_thoai
- [x] Task 3 stream/POST ghi lượt
- [x] Task 4 router /hoi-thoai
- [x] Task 5 helper + hook FE
- [x] Task 6 use-tra-cuu + ?phien=
- [x] Task 7 DanhSachPhien
- [x] Task 8 gộp, kiểm, Chrome, đóng

## Decisions

(ghi khi có)

## Result

(điền ở Task 8)
```

- [x] **Step 2: Test đỏ** `tests/test_api/test_han_muc_phien.py`

```python
"""`phien_luu` trong `config/han_muc.yaml` + `nguoi_dung_bat_buoc` (spec 2026-09-07 §4.2, §5.3)."""

import pytest
from fastapi import HTTPException

from src.services import bao_ve


def test_phien_luu_toi_da_theo_goi_that():
    bao_ve._doc_han_muc.cache_clear()
    assert bao_ve.phien_luu_toi_da("free") == 10
    assert bao_ve.phien_luu_toi_da("pro") >= 10_000
    # Gói lạ rơi về gói mặc định (hỏng theo hướng CHẶT), như `han_muc_thang`.
    assert bao_ve.phien_luu_toi_da("goi-la") == bao_ve.phien_luu_toi_da("free")


def test_yaml_thieu_phien_luu_thi_fail_loud(tmp_path, monkeypatch):
    f = tmp_path / "han_muc.yaml"
    f.write_text("goi_mac_dinh: free\ngoi:\n  free: 50\n  pro: 500\n", encoding="utf-8")
    monkeypatch.setattr(bao_ve, "HAN_MUC_PATH", f)
    bao_ve._doc_han_muc.cache_clear()
    with pytest.raises(ValueError, match="phien_luu"):
        bao_ve._doc_han_muc()
    bao_ve._doc_han_muc.cache_clear()


def test_yaml_phien_luu_thieu_mot_goi_thi_fail_loud(tmp_path, monkeypatch):
    f = tmp_path / "han_muc.yaml"
    f.write_text(
        "goi_mac_dinh: free\ngoi:\n  free: 50\n  pro: 500\nphien_luu:\n  free: 10\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bao_ve, "HAN_MUC_PATH", f)
    bao_ve._doc_han_muc.cache_clear()
    with pytest.raises(ValueError, match="phien_luu"):
        bao_ve._doc_han_muc()
    bao_ve._doc_han_muc.cache_clear()


@pytest.mark.asyncio
async def test_nguoi_dung_bat_buoc_401_khi_khong_co_danh_tinh(cai_dat, monkeypatch):
    """Kể cả khi Supabase CHƯA cấu hình: không có ai để gán phiên → 401, không phải None."""
    cai_dat(supabase_url="")
    monkeypatch.setattr(bao_ve, "kiem_api_key", lambda request: None)
    monkeypatch.setattr(bao_ve, "kiem_rate_limit", lambda ip, so_luot=None: None)

    class Req:
        headers: dict = {}
        client = type("C", (), {"host": "127.0.0.1"})()

    with pytest.raises(HTTPException) as e:
        await bao_ve.nguoi_dung_bat_buoc(Req())
    assert e.value.status_code == 401
```

(`cai_dat` đến từ `tests/test_api/conftest.py`. Nếu `ip_goi` cần thuộc tính khác của request, đọc `bao_ve.ip_goi` và bổ sung vào `Req` cho đủ — không nới điều kiện assert.)

- [x] **Step 3: Đỏ** — `python -m pytest tests/test_api/test_han_muc_phien.py -q` → AttributeError/ValueError không khớp.

- [x] **Step 4: `config/han_muc.yaml`** — thêm cuối file:

```yaml

# Số phiên hội thoại gần nhất được HIỆN cho mỗi gói (spec 2026-09-07 §4.2). Phiên
# cũ hơn không bị xoá — chỉ ẩn khỏi danh sách và không mở/hỏi tiếp được; nâng
# gói thì hiện lại. Cùng quy ước với `goi`: 0 = không hiện phiên nào; "không
# giới hạn" cố ý không biểu đạt được — cần thì đặt một số lớn.
phien_luu:
  free: 10
  pro: 100000
```

- [x] **Step 5: `src/services/bao_ve.py`**

Trong `_doc_han_muc`, sau kiểm `goi_mac_dinh`:

```python
    pl = d.get("phien_luu")
    if not isinstance(pl, dict) or set(pl) != set(d["goi"]):
        raise ValueError(
            f"{HAN_MUC_PATH}: cần khoá 'phien_luu' kiểu mapping với ĐÚNG các gói của 'goi' "
            f"(thiếu/lạ: {sorted(set(d['goi']) ^ set(pl or {}))})"
        )
```

Sau `han_muc_thang`:

```python
def phien_luu_toi_da(plan: str) -> int:
    """Số phiên hội thoại gần nhất được hiện cho `plan` (`han_muc.yaml: phien_luu`).
    Gói lạ rơi về gói mặc định — hỏng theo hướng CHẶT, như `han_muc_thang`."""
    d = _doc_han_muc()
    if plan not in d["phien_luu"]:
        logger.warning("phien_luu_toi_da: gói %r không có trong YAML — dùng gói mặc định", plan)
        return int(d["phien_luu"][d["goi_mac_dinh"]])
    return int(d["phien_luu"][plan])


_SQL_PLAN_CUA = text("SELECT plan FROM users WHERE sub = :sub")


def plan_cua(sub: str) -> str:
    """Gói hiện tại của `sub`; chưa có dòng `users` thì gói mặc định (JIT provisioning
    xảy ra ở `ghi_nhan_nguoi_dung`, không ở đây — đọc không được tạo)."""
    with get_engine().connect() as c:
        r = c.execute(_SQL_PLAN_CUA, {"sub": sub}).scalar_one_or_none()
    return str(r) if r is not None else str(_doc_han_muc()["goi_mac_dinh"])
```

(`text` và `get_engine` đã được import trong module — kiểm; nếu chưa, thêm.) Sau `cong_nhe`:

```python
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
```

- [x] **Step 6: Migration** `migrations/020_hoi_thoai.sql`

```sql
-- Spec 2026-09-07 §4 — phiên hội thoại theo tài khoản. `tra_loi` là NGUYÊN payload
-- `TraCuuResponse` để mở lại phiên render y hệt (thẻ trích dẫn vẫn bấm được).
-- Xoá mềm bằng `xoa_luc`; hạn mức hiện theo gói nằm ở config/han_muc.yaml, không ở DB.
CREATE TABLE IF NOT EXISTS hoi_thoai (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_sub     UUID NOT NULL REFERENCES users(sub) ON DELETE CASCADE,
    tieu_de      TEXT NOT NULL,
    tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    cap_nhat_luc TIMESTAMPTZ NOT NULL DEFAULT now(),
    xoa_luc      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_hoi_thoai_user_cap_nhat
    ON hoi_thoai(user_sub, cap_nhat_luc DESC) WHERE xoa_luc IS NULL;

CREATE TABLE IF NOT EXISTS luot_hoi_thoai (
    id           BIGSERIAL PRIMARY KEY,
    hoi_thoai_id UUID NOT NULL REFERENCES hoi_thoai(id) ON DELETE CASCADE,
    thu_tu       INTEGER NOT NULL,
    cau_hoi      TEXT NOT NULL,
    tra_loi      JSONB NOT NULL,
    trace_id     TEXT,
    tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (hoi_thoai_id, thu_tu)
);
```

Áp lên DB local: `python -c "from src.services.db import run_migrations; print(run_migrations('020'))"`.

- [x] **Step 7: `src/main.py:52`** — `db_svc.run_migrations("019")` thành:

```python
    for mig in ("019", "020"):
        db_svc.run_migrations(mig)
```

Chạy `python -m pytest tests/test_api/test_guard_khoi_dong.py -q`: test hiện có khẳng định gọi với `"019"` — đọc và đổi kỳ vọng thành danh sách `["019", "020"]` (spy ghi mọi lời gọi), giữ ý nghĩa "áp migration trước guard".

- [x] **Step 8: `src/models/schemas.py`** — trong `TraCuuRequest`, ngay sau `lich_su`:

```python
    # Spec 2026-09-07 §5.2: phiên hội thoại để máy chủ nạp `lich_su` và ghi lượt. Chỉ
    # có ý nghĩa khi có danh tính; ẩn danh thì bị bỏ qua.
    hoi_thoai_id: UUID | None = None
```

(`from uuid import UUID` nếu chưa có.) Sau `NguoiDungResponse`:

```python
# ══ /hoi-thoai — phiên hội thoại theo tài khoản (spec 2026-09-07 §5.3) ═════════
class PhienTomTatOut(BaseModel):
    id: str
    tieu_de: str
    so_luot: int
    tao_luc: datetime
    cap_nhat_luc: datetime


class DanhSachPhienResponse(BaseModel):
    plan: str
    gioi_han: int
    tong_hien: int
    tong_an: int
    items: list[PhienTomTatOut]


class LuotDaLuuOut(BaseModel):
    thu_tu: int
    cau_hoi: str
    tra_loi: dict  # nguyên payload TraCuuResponse lúc trả lời
    trace_id: str | None
    tao_luc: datetime


class ChiTietPhienResponse(BaseModel):
    id: str
    tieu_de: str
    tao_luc: datetime
    cap_nhat_luc: datetime
    luot: list[LuotDaLuuOut]


class DoiTenPhienRequest(BaseModel):
    tieu_de: str = Field(..., min_length=1, max_length=120)
```

(`from datetime import datetime` nếu chưa có.)

- [x] **Step 9: Frontend kiểu** — `frontend/src/lib/klaw.ts`, sau `SuKienBuoc`:

```ts
/* ── /hoi-thoai — phiên hội thoại theo tài khoản (spec 2026-09-07) ─────────── */
export interface PhienTomTat {
  id: string;
  tieu_de: string;
  so_luot: number;
  tao_luc: string;
  cap_nhat_luc: string;
}

export interface DanhSachPhien {
  plan: string;
  gioi_han: number;
  tong_hien: number;
  tong_an: number;
  items: PhienTomTat[];
}

export interface LuotDaLuu {
  thu_tu: number;
  cau_hoi: string;
  tra_loi: unknown;
  trace_id: string | null;
  tao_luc: string;
}

export interface ChiTietPhien {
  id: string;
  tieu_de: string;
  tao_luc: string;
  cap_nhat_luc: string;
  luot: LuotDaLuu[];
}

export interface SuKienLoiLuu {
  hoi_thoai_id: string;
  detail: string;
}
```

Trong `SuKienBatDau` thêm `hoi_thoai_id: string | null;`. Cạnh `laTimKiem`:

```ts
export function laDanhSachPhien(x: unknown): x is DanhSachPhien {
  return laBanGhi(x) && Array.isArray(x["items"]) && typeof x["tong_hien"] === "number";
}

export function laChiTietPhien(x: unknown): x is ChiTietPhien {
  return laBanGhi(x) && typeof x["id"] === "string" && Array.isArray(x["luot"]);
}

/** Một lượt đã lưu → lượt render được. `tra_loi` đi đúng đường chuẩn hoá của stream
 *  (`chuanHoaBang` → `chuanHoaDocuments` → `laTraCuuKetQua`); payload cũ thiếu trường
 *  thì `ketQua: null` và card không render — không bịa. */
export function chuanHoaLuot(l: LuotDaLuu): {
  thuTu: number;
  cauHoi: string;
  ketQua: TraCuuKetQua | null;
  traceId: string | null;
} {
  const du = chuanHoaDocuments(chuanHoaBang(l.tra_loi));
  return {
    thuTu: l.thu_tu,
    cauHoi: l.cau_hoi,
    ketQua: laTraCuuKetQua(du) ? du : null,
    traceId: l.trace_id,
  };
}
```

`frontend/src/lib/api.ts`: `YeuCauTraCuu` thêm `hoi_thoai_id?: string;`; `XuLyLuong` thêm `onLoiLuu?: (su: SuKienLoiLuu) => void;` (import kiểu); trong `traCuuLuong`, nhánh `bat_dau`: truyền `hoi_thoai_id: typeof du["hoi_thoai_id"] === "string" ? du["hoi_thoai_id"] : null` vào đối tượng gửi `onBatDau` (thay `du as unknown as SuKienBatDau` bằng object có đủ ba trường cũ + trường mới); thêm nhánh:

```ts
        } else if (khung.ten === "loi_luu" && laBanGhiTho(du)) {
          if (typeof du["hoi_thoai_id"] === "string" && typeof du["detail"] === "string")
            xuLy.onLoiLuu?.({ hoi_thoai_id: du["hoi_thoai_id"], detail: du["detail"] });
```

- [x] **Step 10: Xanh**

```bash
make lint && ruff format --check src/services/bao_ve.py src/models/schemas.py src/main.py tests/test_api/test_han_muc_phien.py && python -m pytest tests/test_api/test_han_muc_phien.py tests/test_api/test_guard_khoi_dong.py tests/test_api/test_tra_cuu.py tests/test_config.py -q
cd frontend && npm run typecheck && npm run lint && node scripts/kiem-sse.ts
```

- [x] **Step 11: Commit**

```bash
git add migrations/020_hoi_thoai.sql config/han_muc.yaml src/services/bao_ve.py src/models/schemas.py src/main.py tests/test_api/test_han_muc_phien.py tests/test_api/test_guard_khoi_dong.py frontend/src/lib/klaw.ts frontend/src/lib/api.ts docs/plans/active/lich-su-hoi-thoai.md
git commit -m "feat(api): conversation tables, per-plan session cap, identity gate and response contract

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [x] **Step 12: Worktree**

```bash
git worktree add ../KLAW-be3 -b wt-be-phien && git worktree add ../KLAW-fe3 -b wt-fe-phien
for w in ../KLAW-be3 ../KLAW-fe3; do ln -s "$PWD/.venv" "$w/.venv"; ln -s "$PWD/.env.local" "$w/.env.local"; mkdir -p "$w/data" && ln -s "$PWD/data/raw" "$w/data/raw"; done
ln -s "$PWD/frontend/node_modules" ../KLAW-fe3/frontend/node_modules
(cd ../KLAW-be3 && .venv/bin/python -c "import src.config; print('be3 ok')") && (cd ../KLAW-fe3/frontend && npm run typecheck && echo fe3 ok)
```

---

# BƯỚC 1 — BACKEND (worktree `../KLAW-be3`, nhánh `wt-be-phien`)

Mọi lệnh chạy từ gốc worktree với `.venv/bin/python` / `.venv/bin/ruff`. DB local đã có bảng 020 (Task 1 Step 6).

### Task 2: Dịch vụ `src/services/hoi_thoai.py`

**Files:**
- Create: `src/services/hoi_thoai.py`
- Test: `tests/test_services/test_hoi_thoai.py` (mới, integration trên DB thật)

**Interfaces:**
- Consumes: `bao_ve.phien_luu_toi_da(plan)`, `bao_ve.ghi_nhan_nguoi_dung(sub, email) -> plan` (tạo dòng `users` cho FK), `get_engine()`.
- Produces: `tao_phien(sub: str, cau_hoi: str) -> str`; `lay_phien(sub, id) -> dict | None` (`{id, tieu_de, tao_luc, cap_nhat_luc}`); `phien_bi_an(sub, plan, id) -> bool`; `lich_su_gan_nhat(id, n=3) -> list[dict]` (hình `LuotTruoc`, theo thứ tự thời gian); `ghi_luot(id, cau_hoi, tra_loi: dict, trace_id: str | None) -> int`; `danh_sach(sub, plan, limit, offset) -> tuple[list[dict], int, int]` (items, tong_hien, tong_an); `chi_tiet(sub, id) -> dict | None` (phiên + `luot: list[dict]`); `doi_ten(sub, id, tieu_de) -> dict | None`; `xoa_mem(sub, id) -> bool`; `tieu_de_mac_dinh(cau_hoi) -> str`. Task 3, 4 gọi đúng các tên này.

- [x] **Step 1: Test đỏ** `tests/test_services/test_hoi_thoai.py`

```python
"""Dịch vụ phiên hội thoại (spec 2026-09-07 §4, §5.1) — chạy trên DB thật, dọn theo `sub`."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, hoi_thoai
from src.services.db import get_engine

pytestmark = pytest.mark.integration

PAYLOAD = {
    "result_type": "answer", "answer": "Thử việc tối đa 180 ngày.", "warnings": [],
    "coverage_note": None, "nguon": [], "bang": [], "documents": [], "soan_thao": None,
    "citations": [{"provision_id": 1, "khop_tai_id": 1, "doc_id": "d", "duong_dan": "45/2019/QH14 > Điều 25 > Khoản 1",
                   "bo_luat": "BLLĐ", "so_ky_hieu": "45/2019/QH14", "quote": "…", "hieu_luc": "con_hieu_luc",
                   "tin_cay": None, "k": 1}],
}


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, f"{sub[:8]}@test.local")
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = :s"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = :s"), {"s": sub})


def test_tieu_de_mac_dinh_cat_80_tai_ranh_gioi_tu():
    ngan = "Thử việc tối đa bao lâu?"
    assert hoi_thoai.tieu_de_mac_dinh(ngan) == ngan
    dai = " ".join(["từ"] * 60)
    t = hoi_thoai.tieu_de_mac_dinh(dai)
    assert len(t) <= 81 and t.endswith("…") and not t[:-1].endswith(" ")


def test_tao_ghi_va_lich_su_theo_thu_tu(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "Câu một?")
    assert hoi_thoai.lay_phien(nguoi, pid)["tieu_de"] == "Câu một?"
    assert hoi_thoai.ghi_luot(pid, "Câu một?", PAYLOAD, "t1") == 1
    assert hoi_thoai.ghi_luot(pid, "Câu hai?", PAYLOAD, "t2") == 2
    ls = hoi_thoai.lich_su_gan_nhat(pid, 3)
    assert [l["cau_hoi"] for l in ls] == ["Câu một?", "Câu hai?"]
    assert ls[0]["tra_loi"] == "Thử việc tối đa 180 ngày."
    assert ls[0]["duong_dan"] == ["45/2019/QH14 > Điều 25 > Khoản 1"]
    ct = hoi_thoai.chi_tiet(nguoi, pid)
    assert [l["thu_tu"] for l in ct["luot"]] == [1, 2] and ct["luot"][1]["trace_id"] == "t2"


def test_phien_cua_nguoi_khac_la_None(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "x")
    assert hoi_thoai.lay_phien(str(uuid.uuid4()), pid) is None
    assert hoi_thoai.chi_tiet(str(uuid.uuid4()), pid) is None
    assert hoi_thoai.xoa_mem(str(uuid.uuid4()), pid) is False


def test_free_giu_N_phien_gan_nhat_va_xoa_thi_hien_lai(nguoi, monkeypatch):
    monkeypatch.setattr(hoi_thoai, "phien_luu_toi_da", lambda plan: 3)  # gói thu nhỏ để test nhanh
    ids = [hoi_thoai.tao_phien(nguoi, f"câu {i}") for i in range(5)]
    for pid in ids:  # cập nhật cap_nhat_luc tăng dần theo thứ tự tạo
        hoi_thoai.ghi_luot(pid, "q", PAYLOAD, None)
    items, tong_hien, tong_an = hoi_thoai.danh_sach(nguoi, "free", limit=20, offset=0)
    assert (tong_hien, tong_an) == (3, 2)
    assert [i["id"] for i in items] == list(reversed(ids[2:]))
    assert hoi_thoai.phien_bi_an(nguoi, "free", ids[0]) is True
    assert hoi_thoai.phien_bi_an(nguoi, "free", ids[4]) is False
    assert hoi_thoai.xoa_mem(nguoi, ids[4]) is True
    items, tong_hien, tong_an = hoi_thoai.danh_sach(nguoi, "free", limit=20, offset=0)
    assert (tong_hien, tong_an) == (3, 1) and hoi_thoai.phien_bi_an(nguoi, "free", ids[1]) is False


def test_doi_ten_va_xoa_mem(nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "x")
    assert hoi_thoai.doi_ten(nguoi, pid, "Tên mới")["tieu_de"] == "Tên mới"
    assert hoi_thoai.xoa_mem(nguoi, pid) is True
    assert hoi_thoai.lay_phien(nguoi, pid) is None
    assert hoi_thoai.danh_sach(nguoi, "free", 20, 0)[1] == 0
```

- [x] **Step 2: Đỏ** — `.venv/bin/python -m pytest tests/test_services/test_hoi_thoai.py -q` → ModuleNotFoundError.

- [x] **Step 3: Dịch vụ** `src/services/hoi_thoai.py`

```python
"""Phiên hội thoại theo tài khoản (spec 2026-09-07 §4, §5.1).

Mọi hàm đọc/ghi nhận `sub` và lọc theo `user_sub` — không có đường nào đọc phiên
mà không có chủ. "Ẩn" là quy tắc HIỆN theo gói (`han_muc.yaml: phien_luu`), tính
lúc đọc chứ không ghi vào DB: nâng gói thì phiên cũ hiện lại mà không cần sửa dòng nào.
"""

import json
import logging

from sqlalchemy import text

from src.services.bao_ve import phien_luu_toi_da
from src.services.db import get_engine

logger = logging.getLogger(__name__)

TIEU_DE_TOI_DA = 80
LUOT_LICH_SU = 3
TRA_LOI_TOI_DA = 2000
DUONG_DAN_TOI_DA = 50

_SQL_TAO = text("INSERT INTO hoi_thoai (user_sub, tieu_de) VALUES (:sub, :tieu_de) RETURNING id")
_SQL_LAY = text(
    "SELECT id::text AS id, tieu_de, tao_luc, cap_nhat_luc FROM hoi_thoai"
    " WHERE id = :id AND user_sub = :sub AND xoa_luc IS NULL"
)
# Số phiên còn sống MỚI HƠN phiên này (theo cặp (cap_nhat_luc, id) để tất định).
_SQL_HANG = text(
    "SELECT count(*)::int FROM hoi_thoai h"
    " WHERE h.user_sub = :sub AND h.xoa_luc IS NULL"
    "   AND (h.cap_nhat_luc, h.id) > (SELECT cap_nhat_luc, id FROM hoi_thoai WHERE id = :id)"
)
_SQL_LICH_SU = text(
    "SELECT cau_hoi, tra_loi FROM luot_hoi_thoai WHERE hoi_thoai_id = :id"
    " ORDER BY thu_tu DESC LIMIT :n"
)
_SQL_GHI = text(
    "INSERT INTO luot_hoi_thoai (hoi_thoai_id, thu_tu, cau_hoi, tra_loi, trace_id)"
    " VALUES (:id, (SELECT coalesce(max(thu_tu), 0) + 1 FROM luot_hoi_thoai WHERE hoi_thoai_id = :id),"
    "         :cau_hoi, CAST(:tra_loi AS jsonb), :trace_id) RETURNING thu_tu"
)
_SQL_CHAM = text("UPDATE hoi_thoai SET cap_nhat_luc = now() WHERE id = :id")
_SQL_DEM = text("SELECT count(*)::int FROM hoi_thoai WHERE user_sub = :sub AND xoa_luc IS NULL")
_SQL_DANH_SACH = text(
    "SELECT h.id::text AS id, h.tieu_de, h.tao_luc, h.cap_nhat_luc,"
    "       (SELECT count(*)::int FROM luot_hoi_thoai l WHERE l.hoi_thoai_id = h.id) AS so_luot"
    " FROM hoi_thoai h WHERE h.user_sub = :sub AND h.xoa_luc IS NULL"
    " ORDER BY h.cap_nhat_luc DESC, h.id DESC LIMIT :limit OFFSET :offset"
)
_SQL_LUOT = text(
    "SELECT thu_tu, cau_hoi, tra_loi, trace_id, tao_luc FROM luot_hoi_thoai"
    " WHERE hoi_thoai_id = :id ORDER BY thu_tu"
)
_SQL_DOI_TEN = text(
    "UPDATE hoi_thoai SET tieu_de = :tieu_de WHERE id = :id AND user_sub = :sub AND xoa_luc IS NULL"
)
_SQL_XOA_MEM = text(
    "UPDATE hoi_thoai SET xoa_luc = now() WHERE id = :id AND user_sub = :sub AND xoa_luc IS NULL"
)


def tieu_de_mac_dinh(cau_hoi: str) -> str:
    """Câu hỏi đầu, cắt còn ≤80 ký tự tại ranh giới từ, thêm "…" nếu cắt."""
    gon = " ".join(cau_hoi.split())
    if len(gon) <= TIEU_DE_TOI_DA:
        return gon
    cat = gon[:TIEU_DE_TOI_DA].rsplit(" ", 1)[0].rstrip()
    return f"{cat}…"


def tao_phien(sub: str, cau_hoi: str) -> str:
    with get_engine().begin() as c:
        return str(c.execute(_SQL_TAO, {"sub": sub, "tieu_de": tieu_de_mac_dinh(cau_hoi)}).scalar_one())


def lay_phien(sub: str, id: str) -> dict | None:
    with get_engine().connect() as c:
        r = c.execute(_SQL_LAY, {"sub": sub, "id": id}).mappings().one_or_none()
    return dict(r) if r is not None else None


def phien_bi_an(sub: str, plan: str, id: str) -> bool:
    """Phiên nằm ngoài N phiên mới nhất của gói. Gọi SAU `lay_phien` (phiên phải của `sub`)."""
    with get_engine().connect() as c:
        moi_hon = c.execute(_SQL_HANG, {"sub": sub, "id": id}).scalar_one()
    return int(moi_hon) >= phien_luu_toi_da(plan)


def _luot_thanh_lich_su(cau_hoi: str, tra_loi: dict) -> dict:
    # Cùng khuôn với `dungLichSu` phía FE: answer cắt 2000, đường dẫn duy nhất, ≤50.
    duong_dan: list[str] = []
    for c in tra_loi.get("citations") or []:
        d = c.get("duong_dan") if isinstance(c, dict) else None
        if isinstance(d, str) and d and d not in duong_dan:
            duong_dan.append(d[:500])
    return {
        "cau_hoi": cau_hoi,
        "tra_loi": str(tra_loi.get("answer") or "")[:TRA_LOI_TOI_DA],
        "duong_dan": duong_dan[:DUONG_DAN_TOI_DA],
    }


def lich_su_gan_nhat(id: str, n: int = LUOT_LICH_SU) -> list[dict]:
    with get_engine().connect() as c:
        rows = c.execute(_SQL_LICH_SU, {"id": id, "n": n}).mappings().all()
    return [_luot_thanh_lich_su(r["cau_hoi"], r["tra_loi"] or {}) for r in reversed(rows)]


def ghi_luot(id: str, cau_hoi: str, tra_loi: dict, trace_id: str | None) -> int:
    """Một transaction: thêm lượt (thu_tu = max+1) và chạm `cap_nhat_luc`. Có thể raise —
    caller (`_ghi_luot_nhe`) quyết định phát `loi_luu`."""
    with get_engine().begin() as c:
        thu_tu = c.execute(_SQL_GHI, {
            "id": id, "cau_hoi": cau_hoi,
            "tra_loi": json.dumps(tra_loi, ensure_ascii=False), "trace_id": trace_id,
        }).scalar_one()
        c.execute(_SQL_CHAM, {"id": id})
    return int(thu_tu)


def danh_sach(sub: str, plan: str, limit: int, offset: int) -> tuple[list[dict], int, int]:
    toi_da = phien_luu_toi_da(plan)
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_DEM, {"sub": sub}).scalar_one())
        tong_hien = min(tong, toi_da)
        con = max(0, min(limit, tong_hien - offset))
        items = (
            [dict(r) for r in c.execute(_SQL_DANH_SACH, {"sub": sub, "limit": con, "offset": offset}).mappings().all()]
            if con > 0 else []
        )
    return items, tong_hien, tong - tong_hien


def chi_tiet(sub: str, id: str) -> dict | None:
    phien = lay_phien(sub, id)
    if phien is None:
        return None
    with get_engine().connect() as c:
        luot = [dict(r) for r in c.execute(_SQL_LUOT, {"id": id}).mappings().all()]
    return {**phien, "luot": luot}


def doi_ten(sub: str, id: str, tieu_de: str) -> dict | None:
    with get_engine().begin() as c:
        n = c.execute(_SQL_DOI_TEN, {"sub": sub, "id": id, "tieu_de": tieu_de.strip()}).rowcount
    return lay_phien(sub, id) if n else None


def xoa_mem(sub: str, id: str) -> bool:
    with get_engine().begin() as c:
        return c.execute(_SQL_XOA_MEM, {"sub": sub, "id": id}).rowcount > 0
```

- [x] **Step 4: Xanh**

```bash
.venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check src/services/hoi_thoai.py tests/test_services/test_hoi_thoai.py && .venv/bin/python -m pytest tests/test_services/test_hoi_thoai.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/services/hoi_thoai.py tests/test_services/test_hoi_thoai.py
git commit -m "feat(hoi-thoai): conversation service with plan-based visibility and server-side history

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Stream và POST ghi lượt vào phiên

**Files:**
- Modify: `src/api/routes.py` (import; `_chuan_bi_phien`, `_ghi_luot_nhe`; handler `tra_cuu`), `src/api/routes_luong.py` (handler + `_chay_nen`)
- Test: `tests/test_api/test_tra_cuu_phien.py` (mới)

**Interfaces:**
- Consumes: Task 2 hàm dịch vụ; `bao_ve.plan_cua(sub)`; fixture `cai_dat`, `khoa_ky`, `graph_gia_lap`, `_bearer` (`tests/test_api/test_xac_thuc_han_muc.py`).
- Produces: `routes._chuan_bi_phien(req, user_sub) -> tuple[TraCuuRequest, str | None]` (raise 404/403; trả req đã gắn `lich_su` máy chủ + id phiên); `routes._ghi_luot_nhe(hoi_thoai_id, cau_hoi, payload_json, trace_id) -> str | None` (None khi ghi được, chuỗi lỗi khi không); `bat_dau.hoi_thoai_id`; sự kiện `loi_luu`; header `X-Hoi-Thoai-Id` ở `/tra-cuu`.

- [x] **Step 1: Test đỏ** `tests/test_api/test_tra_cuu_phien.py`

```python
"""Ghi lượt vào phiên qua stream và POST (spec 2026-09-07 §5.2)."""

import json
import uuid

import pytest
from sqlalchemy import text

from src.api import routes
from src.services import bao_ve, hoi_thoai
from src.services.db import get_engine
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration
SUPABASE = "https://x.supabase.co"


@pytest.fixture
def don_dep():
    subs: list[str] = []
    yield subs
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = ANY(CAST(:s AS uuid[]))"), {"s": subs})
        c.execute(text("DELETE FROM traces WHERE user_sub = ANY(CAST(:s AS uuid[]))"), {"s": subs})
        c.execute(text("DELETE FROM users WHERE sub = ANY(CAST(:s AS uuid[]))"), {"s": subs})


def _su_kien(body: str) -> list[tuple[str, dict]]:
    ra = []
    for khung in body.strip().split("\n\n"):
        dong = khung.splitlines()
        ten = next(d[7:] for d in dong if d.startswith("event: "))
        du = next(d[6:] for d in dong if d.startswith("data: "))
        ra.append((ten, json.loads(du)))
    return ra


@pytest.mark.asyncio
async def test_stream_tao_phien_va_ghi_luot(client, cai_dat, khoa_ky, graph_gia_lap, don_dep):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4()); don_dep.append(sub)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "Thử việc tối đa?"}, headers=_bearer(khoa_ky, sub))
    assert r.status_code == 200
    sk = dict(_su_kien(r.text))
    pid = sk["bat_dau"]["hoi_thoai_id"]
    assert pid and "ket_qua" in sk and "loi_luu" not in sk
    ct = hoi_thoai.chi_tiet(sub, pid)
    assert ct["tieu_de"] == "Thử việc tối đa?"
    assert ct["luot"][0]["cau_hoi"] == "Thử việc tối đa?"
    assert ct["luot"][0]["tra_loi"]["result_type"] == sk["ket_qua"]["result_type"]
    assert ct["luot"][0]["trace_id"] == sk["bat_dau"]["trace_id"]


@pytest.mark.asyncio
async def test_hoi_tiep_trong_phien_nap_lich_su_may_chu(client, cai_dat, khoa_ky, graph_gia_lap, don_dep, monkeypatch):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4()); don_dep.append(sub)
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    pid = hoi_thoai.tao_phien(sub, "Câu đầu")
    hoi_thoai.ghi_luot(pid, "Câu đầu", {"result_type": "answer", "answer": "Trả lời đầu", "citations": []}, "t0")
    thay: dict = {}
    goc = routes._state_vao

    def ghi_lai(req, as_of, trace_id):
        st = goc(req, as_of, trace_id)
        thay["lich_su"] = st["lich_su"]
        return st

    monkeypatch.setattr(routes, "_state_vao", ghi_lai)
    r = await client.post(
        "/api/v1/tra-cuu/luong",
        json={"query": "Còn khoản mấy?", "hoi_thoai_id": pid,
              "lich_su": [{"cau_hoi": "client gửi", "tra_loi": "bị bỏ qua"}]},
        headers=_bearer(khoa_ky, sub),
    )
    assert r.status_code == 200
    assert thay["lich_su"] == [{"cau_hoi": "Câu đầu", "tra_loi": "Trả lời đầu", "duong_dan": []}]
    assert dict(_su_kien(r.text))["bat_dau"]["hoi_thoai_id"] == pid
    assert [l["cau_hoi"] for l in hoi_thoai.chi_tiet(sub, pid)["luot"]] == ["Câu đầu", "Còn khoản mấy?"]


@pytest.mark.asyncio
async def test_phien_nguoi_khac_404_va_phien_an_403(client, cai_dat, khoa_ky, graph_gia_lap, don_dep, monkeypatch):
    cai_dat(supabase_url=SUPABASE)
    a, b = str(uuid.uuid4()), str(uuid.uuid4()); don_dep.extend([a, b])
    bao_ve.ghi_nhan_nguoi_dung(a, None)
    pid = hoi_thoai.tao_phien(a, "của A")
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x", "hoi_thoai_id": pid}, headers=_bearer(khoa_ky, b))
    assert r.status_code == 404
    monkeypatch.setattr(hoi_thoai, "phien_luu_toi_da", lambda plan: 1)
    pid2 = hoi_thoai.tao_phien(a, "mới hơn")
    hoi_thoai.ghi_luot(pid2, "q", {"result_type": "answer", "answer": "", "citations": []}, None)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x", "hoi_thoai_id": pid}, headers=_bearer(khoa_ky, a))
    assert r.status_code == 403 and "phiên" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_an_danh_khong_ghi_va_bat_dau_null(client, cai_dat, graph_gia_lap):
    cai_dat(supabase_url="")
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x", "hoi_thoai_id": str(uuid.uuid4())})
    assert r.status_code == 200
    assert dict(_su_kien(r.text))["bat_dau"]["hoi_thoai_id"] is None


@pytest.mark.asyncio
async def test_ghi_loi_thi_van_ket_qua_kem_loi_luu(client, cai_dat, khoa_ky, graph_gia_lap, don_dep, monkeypatch):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4()); don_dep.append(sub)

    def no(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(hoi_thoai, "ghi_luot", no)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"}, headers=_bearer(khoa_ky, sub))
    ten = [t for t, _ in _su_kien(r.text)]
    assert "ket_qua" in ten and "loi_luu" in ten and ten.index("loi_luu") > ten.index("ket_qua")


@pytest.mark.asyncio
async def test_post_tra_cuu_tra_header_phien(client, cai_dat, khoa_ky, graph_gia_lap, don_dep):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4()); don_dep.append(sub)
    r = await client.post("/api/v1/tra-cuu", json={"query": "x"}, headers=_bearer(khoa_ky, sub))
    assert r.status_code == 200
    pid = r.headers["x-hoi-thoai-id"]
    assert hoi_thoai.chi_tiet(sub, pid)["luot"][0]["cau_hoi"] == "x"
```

(Đọc `_GraphGiaLap.ainvoke` và cách các test hiện có gọi `cai_dat(...)` để dùng đúng tham số; `graph_gia_lap` đã vô hiệu `_ghi_traces`. Không dùng `khong_dung_db`: hạn mức đọc DB thật với người vừa tạo là 0 lượt — hợp lệ.)

- [x] **Step 2: Đỏ** — `.venv/bin/python -m pytest tests/test_api/test_tra_cuu_phien.py -q`.

- [x] **Step 3: `src/api/routes.py`** — import `LuotTruoc` (gộp vào import schemas), `Response` từ fastapi, `from src.services import hoi_thoai as hoi_thoai_svc`, và `plan_cua` từ `src.services.bao_ve`. Thêm sau `_state_vao`:

```python
async def _chuan_bi_phien(req: TraCuuRequest, user_sub: str | None) -> tuple[TraCuuRequest, str | None]:
    """Gắn lượt hỏi vào một phiên (spec 2026-09-07 §5.2). Ẩn danh → bỏ qua `hoi_thoai_id`.
    Có danh tính: chưa có id → tạo phiên; có id → kiểm chủ (404), kiểm ẩn theo gói
    (403), nạp `lich_su` từ máy chủ và BỎ `lich_su` client gửi."""
    if user_sub is None:
        return req, None
    if req.hoi_thoai_id is None:
        return req, await run_in_threadpool(hoi_thoai_svc.tao_phien, user_sub, req.query)
    pid = str(req.hoi_thoai_id)
    if await run_in_threadpool(hoi_thoai_svc.lay_phien, user_sub, pid) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên này.")
    plan = await run_in_threadpool(plan_cua, user_sub)
    if await run_in_threadpool(hoi_thoai_svc.phien_bi_an, user_sub, plan, pid):
        raise HTTPException(
            status_code=403,
            detail="Gói hiện tại chỉ giữ các phiên gần nhất; phiên này đang ẩn. Nâng gói để mở lại.",
        )
    lich_su = await run_in_threadpool(hoi_thoai_svc.lich_su_gan_nhat, pid)
    return req.model_copy(update={"lich_su": [LuotTruoc(**l) for l in lich_su]}), pid


async def _ghi_luot_nhe(hoi_thoai_id: str, cau_hoi: str, payload: dict, trace_id: str) -> str | None:
    """Ghi lượt vào phiên; lỗi → log + trả thông điệp cho `loi_luu`. KHÔNG nuốt im lặng,
    KHÔNG làm mất câu trả lời đã tính."""
    try:
        await run_in_threadpool(hoi_thoai_svc.ghi_luot, hoi_thoai_id, cau_hoi, payload, trace_id)
        return None
    except Exception:
        logger.exception("hoi_thoai: không ghi được lượt (phien=%s, trace=%s)", hoi_thoai_id, trace_id)
        return "Lượt này chưa lưu được vào phiên."
```

Handler `tra_cuu` (giữ docstring):

```python
@router.post("/tra-cuu", response_model=TraCuuResponse)
async def tra_cuu(
    req: TraCuuRequest, response: Response, user_sub: str | None = Depends(cong_bao_ve)
) -> TraCuuResponse:
    trace_id = str(uuid.uuid4())
    req, hoi_thoai_id = await _chuan_bi_phien(req, user_sub)
    payload, config_name = await chay_tra_cuu(req, user_sub, trace_id)
    resp = tra_cuu_response(payload, trace_id, config_name)
    if hoi_thoai_id is not None:
        response.headers["X-Hoi-Thoai-Id"] = hoi_thoai_id
        await _ghi_luot_nhe(hoi_thoai_id, req.query, resp.model_dump(mode="json"), trace_id)
    return resp
```

- [x] **Step 4: `src/api/routes_luong.py`** — import `_chuan_bi_phien, _ghi_luot_nhe` từ `src.api.routes`. Trong `tra_cuu_luong`, TRƯỚC khi tạo `hang`: `req, hoi_thoai_id = await _chuan_bi_phien(req, user_sub)` (404/403 nổ ở đây, trước khi stream mở). Thêm `"hoi_thoai_id": hoi_thoai_id,` vào dict `bat_dau`. `_chay_nen(req, user_sub, trace_id, hang, hoi_thoai_id)` — sau `await hang.put(("ket_qua", …))`:

```python
        if hoi_thoai_id is not None:
            loi_luu = await _ghi_luot_nhe(hoi_thoai_id, req.query, resp.model_dump(mode="json"), trace_id)
            if loi_luu is not None:
                await hang.put(("loi_luu", {"hoi_thoai_id": hoi_thoai_id, "detail": loi_luu}))
```

Docstring "Ba loại sự kiện" → bốn: thêm `loi_luu` và `hoi_thoai_id` trong `bat_dau`.

- [x] **Step 5: Xanh**

```bash
.venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check src/api/routes.py src/api/routes_luong.py tests/test_api/test_tra_cuu_phien.py && .venv/bin/python -m pytest tests/test_api/test_tra_cuu_phien.py tests/test_api/test_tra_cuu.py tests/test_api/test_sse_nhip_tim.py tests/test_api/test_xac_thuc_han_muc.py -q
```

- [x] **Step 6: Commit**

```bash
git add src/api/routes.py src/api/routes_luong.py tests/test_api/test_tra_cuu_phien.py
git commit -m "feat(api): attach each answer to a conversation; server-side history; loi_luu event

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Router `/hoi-thoai`

**Files:**
- Create: `src/api/routes_hoi_thoai.py`, `tests/test_api/test_hoi_thoai.py`
- Modify: `src/main.py` (import + `include_router`)

**Interfaces:**
- Consumes: Task 1 models + `nguoi_dung_bat_buoc`, `plan_cua`; Task 2 dịch vụ.
- Produces: `GET /hoi-thoai`, `GET /hoi-thoai/{id}`, `PATCH /hoi-thoai/{id}`, `DELETE /hoi-thoai/{id}` như spec §5.3.

- [x] **Step 1: Test đỏ** `tests/test_api/test_hoi_thoai.py`

```python
"""CRUD phiên hội thoại (spec 2026-09-07 §5.3)."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, hoi_thoai
from src.services.db import get_engine
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration
P = {"result_type": "answer", "answer": "a", "citations": []}
SUPABASE = "https://x.supabase.co"


@pytest.fixture
def hai_nguoi(cai_dat, khoa_ky):
    cai_dat(supabase_url=SUPABASE)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    for s in (a, b):
        bao_ve.ghi_nhan_nguoi_dung(s, None)
    yield a, b
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM hoi_thoai WHERE user_sub = ANY(CAST(:s AS uuid[]))"), {"s": [a, b]})
        c.execute(text("DELETE FROM users WHERE sub = ANY(CAST(:s AS uuid[]))"), {"s": [a, b]})


@pytest.mark.asyncio
async def test_khong_dang_nhap_401(client, cai_dat):
    cai_dat(supabase_url="")
    assert (await client.get("/api/v1/hoi-thoai")).status_code == 401


@pytest.mark.asyncio
async def test_danh_sach_chi_tiet_doi_ten_xoa(client, khoa_ky, hai_nguoi):
    a, _ = hai_nguoi
    pid = hoi_thoai.tao_phien(a, "Câu hỏi đầu tiên của A")
    hoi_thoai.ghi_luot(pid, "Câu hỏi đầu tiên của A", P, "t")
    r = await client.get("/api/v1/hoi-thoai", headers=_bearer(khoa_ky, a))
    assert r.status_code == 200
    d = r.json()
    assert d["plan"] == "free" and d["gioi_han"] == 10 and d["tong_hien"] == 1 and d["tong_an"] == 0
    assert d["items"][0]["id"] == pid and d["items"][0]["so_luot"] == 1
    r = await client.get(f"/api/v1/hoi-thoai/{pid}", headers=_bearer(khoa_ky, a))
    assert r.json()["luot"][0]["tra_loi"]["answer"] == "a"
    r = await client.patch(f"/api/v1/hoi-thoai/{pid}", json={"tieu_de": "  Tên mới  "}, headers=_bearer(khoa_ky, a))
    assert r.status_code == 200 and r.json()["tieu_de"] == "Tên mới"
    assert (await client.patch(f"/api/v1/hoi-thoai/{pid}", json={"tieu_de": "   "}, headers=_bearer(khoa_ky, a))).status_code == 422
    assert (await client.delete(f"/api/v1/hoi-thoai/{pid}", headers=_bearer(khoa_ky, a))).status_code == 204
    assert (await client.get(f"/api/v1/hoi-thoai/{pid}", headers=_bearer(khoa_ky, a))).status_code == 404


@pytest.mark.asyncio
async def test_nguoi_khac_404_va_id_sai_dinh_dang_404(client, khoa_ky, hai_nguoi):
    a, b = hai_nguoi
    pid = hoi_thoai.tao_phien(a, "của A")
    assert (await client.get(f"/api/v1/hoi-thoai/{pid}", headers=_bearer(khoa_ky, b))).status_code == 404
    assert (await client.delete(f"/api/v1/hoi-thoai/{pid}", headers=_bearer(khoa_ky, b))).status_code == 404
    assert (await client.patch(f"/api/v1/hoi-thoai/{pid}", json={"tieu_de": "x"}, headers=_bearer(khoa_ky, b))).status_code == 404
    assert (await client.get("/api/v1/hoi-thoai/khong-phai-uuid", headers=_bearer(khoa_ky, a))).status_code == 404


@pytest.mark.asyncio
async def test_phien_an_theo_goi_403_va_tong_an(client, khoa_ky, hai_nguoi, monkeypatch):
    a, _ = hai_nguoi
    monkeypatch.setattr(hoi_thoai, "phien_luu_toi_da", lambda plan: 2)
    ids = [hoi_thoai.tao_phien(a, f"c{i}") for i in range(3)]
    for pid in ids:
        hoi_thoai.ghi_luot(pid, "q", P, None)
    d = (await client.get("/api/v1/hoi-thoai", headers=_bearer(khoa_ky, a))).json()
    assert d["tong_hien"] == 2 and d["tong_an"] == 1 and [i["id"] for i in d["items"]] == [ids[2], ids[1]]
    assert (await client.get(f"/api/v1/hoi-thoai/{ids[0]}", headers=_bearer(khoa_ky, a))).status_code == 403
    assert (await client.patch(f"/api/v1/hoi-thoai/{ids[0]}", json={"tieu_de": "x"}, headers=_bearer(khoa_ky, a))).status_code == 403
```

(Router lấy `gioi_han` bằng `hoi_thoai.phien_luu_toi_da(plan)` — cùng tên module với `danh_sach`/`phien_bi_an` — để `monkeypatch.setattr(hoi_thoai, "phien_luu_toi_da", …)` tác động nhất quán.)

- [x] **Step 2: Đỏ** — 404 cho mọi route.

- [x] **Step 3: Router** `src/api/routes_hoi_thoai.py`

```python
"""`/hoi-thoai` — phiên hội thoại theo tài khoản (spec 2026-09-07 §5.3).

Không LLM ⇒ không `cong_bao_ve`; nhưng dữ liệu THEO NGƯỜI ⇒ `nguoi_dung_bat_buoc`
(401 kể cả khi Supabase chưa cấu hình). Mọi truy vấn lọc theo `sub`; phiên của
người khác là 404 (không tiết lộ tồn tại); phiên ẩn theo gói là 403.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from starlette.concurrency import run_in_threadpool

from src.models.schemas import (
    ChiTietPhienResponse,
    DanhSachPhienResponse,
    DoiTenPhienRequest,
    LuotDaLuuOut,
    PhienTomTatOut,
)
from src.services import hoi_thoai
from src.services.bao_ve import nguoi_dung_bat_buoc, plan_cua

logger = logging.getLogger(__name__)
router = APIRouter()

_KHONG_THAY = "Không tìm thấy phiên này."
_AN = "Gói hiện tại chỉ giữ các phiên gần nhất; phiên này đang ẩn. Nâng gói để mở lại."


def _uuid_hop_le(id: str) -> str:
    # Chuỗi không phải UUID → 404 như phiên không tồn tại; không để Postgres nổ lỗi kiểu.
    try:
        return str(uuid.UUID(id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=_KHONG_THAY) from e


async def _phien_mo_duoc(sub: str, id: str) -> dict:
    phien = await run_in_threadpool(hoi_thoai.lay_phien, sub, id)
    if phien is None:
        raise HTTPException(status_code=404, detail=_KHONG_THAY)
    plan = await run_in_threadpool(plan_cua, sub)
    if await run_in_threadpool(hoi_thoai.phien_bi_an, sub, plan, id):
        raise HTTPException(status_code=403, detail=_AN)
    return phien


@router.get("/hoi-thoai", response_model=DanhSachPhienResponse)
async def danh_sach(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    nguoi: dict = Depends(nguoi_dung_bat_buoc),
) -> DanhSachPhienResponse:
    sub = nguoi["sub"]
    plan = await run_in_threadpool(plan_cua, sub)
    items, tong_hien, tong_an = await run_in_threadpool(hoi_thoai.danh_sach, sub, plan, limit, offset)
    return DanhSachPhienResponse(
        plan=plan, gioi_han=hoi_thoai.phien_luu_toi_da(plan), tong_hien=tong_hien, tong_an=tong_an,
        items=[PhienTomTatOut(**i) for i in items],
    )


@router.get("/hoi-thoai/{id}", response_model=ChiTietPhienResponse)
async def chi_tiet(id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> ChiTietPhienResponse:
    id = _uuid_hop_le(id)
    await _phien_mo_duoc(nguoi["sub"], id)
    ct = await run_in_threadpool(hoi_thoai.chi_tiet, nguoi["sub"], id)
    return ChiTietPhienResponse(**{**ct, "luot": [LuotDaLuuOut(**l) for l in ct["luot"]]})


@router.patch("/hoi-thoai/{id}", response_model=PhienTomTatOut)
async def doi_ten(
    id: str, body: DoiTenPhienRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)
) -> PhienTomTatOut:
    id = _uuid_hop_le(id)
    if not body.tieu_de.strip():
        raise HTTPException(status_code=422, detail="Tiêu đề không được để trống.")
    await _phien_mo_duoc(nguoi["sub"], id)
    phien = await run_in_threadpool(hoi_thoai.doi_ten, nguoi["sub"], id, body.tieu_de)
    ct = await run_in_threadpool(hoi_thoai.chi_tiet, nguoi["sub"], id)
    return PhienTomTatOut(**{**phien, "so_luot": len(ct["luot"])})


@router.delete("/hoi-thoai/{id}", status_code=204)
async def xoa(id: str, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> Response:
    id = _uuid_hop_le(id)
    if not await run_in_threadpool(hoi_thoai.xoa_mem, nguoi["sub"], id):
        raise HTTPException(status_code=404, detail=_KHONG_THAY)
    return Response(status_code=204)
```

`src/main.py`: `from src.api.routes_hoi_thoai import router as router_hoi_thoai` + `app.include_router(router_hoi_thoai, prefix="/api/v1")` cạnh các router khác.

- [x] **Step 4: Xanh**

```bash
.venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check src/api/routes_hoi_thoai.py tests/test_api/test_hoi_thoai.py && .venv/bin/python -m pytest tests/test_api/test_hoi_thoai.py tests/test_api/test_han_muc_phien.py -q
```

- [x] **Step 5: Commit**

```bash
git add src/api/routes_hoi_thoai.py src/main.py tests/test_api/test_hoi_thoai.py
git commit -m "feat(api): list, open, rename and soft-delete conversations per account

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

# BƯỚC 2 — FRONTEND (worktree `../KLAW-fe3`, nhánh `wt-fe-phien`; lệnh chạy trong `frontend/`)

Chạy song song với BƯỚC 1 — hai stream không đụng file nhau (BE chỉ sửa `src/`, `tests/`, `migrations/`; FE chỉ sửa `frontend/`). Hợp đồng hai phía đã chốt ở Task 1 (`lib/klaw.ts`, `lib/api.ts`).

### Task 5: Vận chuyển `/hoi-thoai` — `lib/phien.ts`, `hooks/use-hoi-thoai.ts`, kiểm

**Files:**
- Create: `frontend/src/lib/phien.ts`, `frontend/src/hooks/use-hoi-thoai.ts`, `frontend/scripts/kiem-phien.ts`
- Modify: `frontend/src/lib/api.ts` (`TuyChonGoi.method`, 204), `frontend/src/lib/klaw.ts` (`laPhienTomTat`), `frontend/package.json` (script `kiem-phien` + nối vào `kiem`)

**Interfaces:**
- Consumes: `goi(duongDan, kiem, {signal, method, body})`, `useGoiApi<T>()` (`hooks/use-goi-api.ts`), kiểu Task 1: `DanhSachPhien`, `ChiTietPhien`, `PhienTomTat`, `laDanhSachPhien`, `laChiTietPhien`, `chuanHoaLuot`.
- Produces: `tenGoi(plan: string): string`; `cauPhienAn(plan: string, gioiHan: number, tongAn: number): string`; `thoiGianTuongDoi(iso: string, bayGio?: number): string`; `laPhienTomTat(x): x is PhienTomTat`; `laKhongThan(x): x is null` (export từ `lib/api.ts`); hook `useHoiThoai(daDangNhap: boolean): TrangThaiHoiThoai` với `{ danhSach: DanhSachPhien | null; dangTai: boolean; loi: ApiError | null; taiLai(): void; chiTiet: ChiTietPhien | null; dangTaiChiTiet: boolean; loiChiTiet: ApiError | null; taiChiTiet(id: string): void; xoaChiTiet(): void; doiTen(id, tieuDe): Promise<ApiResult<PhienTomTat>>; xoa(id): Promise<ApiResult<null>> }`. Task 6, 7 dùng đúng các tên này.

- [x] **Step 1: Kiểm đỏ** `frontend/scripts/kiem-phien.ts`

```ts
/**
 * Kiểm chạy được cho phần phiên hội thoại (spec 2026-09-07 §8): câu "đang ẩn"
 * theo số, thời gian tương đối tất định, và hai predicate hình dạng với payload
 * thiếu trường — 2xx sai hình dạng phải rơi về `invalid_response`, không hiển
 * thị một danh sách rỗng trông như thật. Chạy: `npm run kiem-phien`.
 */
import assert from "node:assert/strict";
import { chuanHoaLuot, laChiTietPhien, laDanhSachPhien } from "../src/lib/klaw.ts";
import { cauPhienAn, tenGoi, thoiGianTuongDoi } from "../src/lib/phien.ts";

// 1. Tên gói và câu ẩn.
{
  assert.equal(tenGoi("free"), "Miễn phí");
  assert.equal(tenGoi("pro"), "Pro");
  assert.equal(tenGoi("la"), "la");
  assert.equal(
    cauPhienAn("free", 10, 3),
    "Gói Miễn phí giữ 10 phiên gần nhất. 3 phiên cũ hơn đang ẩn.",
  );
}

// 2. Thời gian tương đối — mốc cố định để kiểm không lệch theo giờ chạy.
{
  const moc = Date.parse("2026-09-07T10:00:00Z");
  const luc = (giay: number) => new Date(moc - giay * 1000).toISOString();
  assert.equal(thoiGianTuongDoi(luc(20), moc), "vừa xong");
  assert.equal(thoiGianTuongDoi(luc(5 * 60), moc), "5 phút trước");
  assert.equal(thoiGianTuongDoi(luc(3 * 3600), moc), "3 giờ trước");
  assert.equal(thoiGianTuongDoi(luc(26 * 3600), moc), "hôm qua");
  assert.equal(thoiGianTuongDoi(luc(4 * 86400), moc), "4 ngày trước");
  assert.equal(thoiGianTuongDoi(luc(40 * 86400), moc), "29/07/2026");
  assert.equal(thoiGianTuongDoi("không phải ngày", moc), "");
}

// 3. Predicate: đủ trường thì qua, thiếu `items`/`luot` thì chặn.
{
  const phien = { id: "a", tieu_de: "t", so_luot: 1, tao_luc: "x", cap_nhat_luc: "y" };
  assert.ok(laDanhSachPhien({ plan: "free", gioi_han: 10, tong_hien: 1, tong_an: 0, items: [phien] }));
  assert.equal(laDanhSachPhien({ plan: "free", tong_hien: 1 }), false);
  assert.equal(laDanhSachPhien(null), false);
  assert.ok(laChiTietPhien({ id: "a", tieu_de: "t", tao_luc: "x", cap_nhat_luc: "y", luot: [] }));
  assert.equal(laChiTietPhien({ id: "a" }), false);
}

// 4. `chuanHoaLuot`: payload thiếu trường → `ketQua: null`, câu hỏi vẫn giữ.
{
  const l = chuanHoaLuot({ thu_tu: 1, cau_hoi: "Hỏi?", tra_loi: { answer: "x" }, trace_id: null, tao_luc: "z" });
  assert.equal(l.ketQua, null);
  assert.equal(l.cauHoi, "Hỏi?");
  assert.equal(l.thuTu, 1);
}
console.info("kiem-phien: 4/4 đạt");
```

`package.json`: thêm `"kiem-phien": "node scripts/kiem-phien.ts"` và nối `&& npm run kiem-phien` vào chuỗi `kiem` ngay sau `npm run kiem-quay-lai`.

- [x] **Step 2: Đỏ** — `npm run kiem-phien` → ERR_MODULE_NOT_FOUND `lib/phien.ts`.

- [x] **Step 3: `lib/phien.ts`**

```ts
/**
 * Chữ và số cho cột phiên hội thoại (spec 2026-09-07 §6). Thuần — kiểm bằng
 * `scripts/kiem-phien.ts` không cần dựng trang.
 */

/** Tên gói hiện cho người dùng; gói lạ trả nguyên mã để không bịa tên. */
export function tenGoi(plan: string): string {
  if (plan === "free") return "Miễn phí";
  if (plan === "pro") return "Pro";
  return plan;
}

/** Dòng cuối cột phiên khi có phiên bị ẩn theo gói. */
export function cauPhienAn(plan: string, gioiHan: number, tongAn: number): string {
  return `Gói ${tenGoi(plan)} giữ ${gioiHan} phiên gần nhất. ${tongAn} phiên cũ hơn đang ẩn.`;
}

const PHUT = 60_000;
const GIO = 60 * PHUT;
const NGAY = 24 * GIO;

/** "vừa xong" / "5 phút trước" / "3 giờ trước" / "hôm qua" / "4 ngày trước" / "29/07/2026".
 *  `bayGio` truyền vào được để kiểm tất định. Chuỗi ngày sai → "" (không đoán). */
export function thoiGianTuongDoi(iso: string, bayGio: number = Date.now()): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const cach = Math.max(0, bayGio - t);
  if (cach < PHUT) return "vừa xong";
  if (cach < GIO) return `${Math.floor(cach / PHUT)} phút trước`;
  if (cach < NGAY) return `${Math.floor(cach / GIO)} giờ trước`;
  const ngay = Math.floor(cach / NGAY);
  if (ngay === 1) return "hôm qua";
  if (ngay < 30) return `${ngay} ngày trước`;
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" }).format(t);
}
```

- [x] **Step 4: `lib/api.ts`** — `TuyChonGoi.method?: "GET" | "POST" | "PATCH" | "DELETE"`. Trong `goi`, thay khối đọc body:

```ts
  let than: unknown;
  if (phanHoi.status === 204) {
    than = null; // DELETE /hoi-thoai/{id} — không có thân, `laKhongThan` là guard
  } else {
    try {
      than = await phanHoi.json();
    } catch (loi) {
      return { ok: false, error: { kind: "invalid_response", message: LOI_HINH_DANG, status: phanHoi.status, detail: loi } };
    }
  }
```

và export `export const laKhongThan = (x: unknown): x is null => x === null;`. `lib/klaw.ts`, cạnh `laDanhSachPhien`:

```ts
export function laPhienTomTat(x: unknown): x is PhienTomTat {
  return laBanGhi(x) && typeof x["id"] === "string" && typeof x["tieu_de"] === "string" && typeof x["so_luot"] === "number";
}
```

- [x] **Step 5: `hooks/use-hoi-thoai.ts`**

```ts
import { useCallback, useEffect } from "react";
import { goi, laKhongThan } from "@/lib/api";
import type { ApiError, ApiResult, ChiTietPhien, DanhSachPhien, PhienTomTat } from "@/lib/klaw";
import { laChiTietPhien, laDanhSachPhien, laPhienTomTat } from "@/lib/klaw";
import { useGoiApi } from "./use-goi-api";

/**
 * Phiên hội thoại của tài khoản (spec 2026-09-07 §6). Hai máy trạng thái
 * `useGoiApi` — danh sách và chi tiết — vì chúng sống độc lập: đổi tên một
 * phiên không được xoá các lượt đang hiện, và mở một phiên không được nhấp
 * nháy cả cột. Đổi tên/xoá xong thì tải lại danh sách từ máy chủ thay vì
 * sửa tay mảng ở client: `tong_an`/thứ tự do máy chủ tính, tự tính lại là
 * chép logic ẩn theo gói sang FE.
 */
export interface TrangThaiHoiThoai {
  danhSach: DanhSachPhien | null;
  dangTai: boolean;
  loi: ApiError | null;
  taiLai: () => void;
  chiTiet: ChiTietPhien | null;
  dangTaiChiTiet: boolean;
  loiChiTiet: ApiError | null;
  taiChiTiet: (id: string) => void;
  xoaChiTiet: () => void;
  doiTen: (id: string, tieuDe: string) => Promise<ApiResult<PhienTomTat>>;
  xoa: (id: string) => Promise<ApiResult<null>>;
}

const DUONG_DAN = "/hoi-thoai";

export function useHoiThoai(daDangNhap: boolean): TrangThaiHoiThoai {
  const ds = useGoiApi<DanhSachPhien>();
  const ct = useGoiApi<ChiTietPhien>();
  const { chay: chayDs } = ds;
  const { chay: chayCt, datLai: datLaiCt } = ct;

  const taiLai = useCallback(() => {
    void chayDs((signal) => goi(`${DUONG_DAN}?limit=50`, laDanhSachPhien, { signal }));
  }, [chayDs]);

  useEffect(() => {
    if (daDangNhap) taiLai();
  }, [daDangNhap, taiLai]);

  const taiChiTiet = useCallback(
    (id: string) => {
      void chayCt((signal) => goi(`${DUONG_DAN}/${encodeURIComponent(id)}`, laChiTietPhien, { signal }));
    },
    [chayCt],
  );

  const doiTen = useCallback(
    async (id: string, tieuDe: string) => {
      const kq = await goi(`${DUONG_DAN}/${encodeURIComponent(id)}`, laPhienTomTat, {
        method: "PATCH",
        body: { tieu_de: tieuDe },
      });
      if (kq.ok) taiLai();
      return kq;
    },
    [taiLai],
  );

  const xoa = useCallback(
    async (id: string) => {
      const kq = await goi(`${DUONG_DAN}/${encodeURIComponent(id)}`, laKhongThan, { method: "DELETE" });
      if (kq.ok) taiLai();
      return kq;
    },
    [taiLai],
  );

  return {
    danhSach: ds.ketQua,
    dangTai: ds.dangChay,
    loi: ds.loi,
    taiLai,
    chiTiet: ct.ketQua,
    dangTaiChiTiet: ct.dangChay,
    loiChiTiet: ct.loi,
    taiChiTiet,
    xoaChiTiet: datLaiCt,
    doiTen,
    xoa,
  };
}
```

- [x] **Step 6: Xanh**

```bash
npm run typecheck && npm run lint && npm run kiem-phien && npm run kiem-sse && npx prettier --check src/lib/phien.ts src/hooks/use-hoi-thoai.ts scripts/kiem-phien.ts src/lib/api.ts src/lib/klaw.ts
```

- [x] **Step 7: Commit**

```bash
git add frontend/src/lib/phien.ts frontend/src/hooks/use-hoi-thoai.ts frontend/scripts/kiem-phien.ts frontend/src/lib/api.ts frontend/src/lib/klaw.ts frontend/package.json
git commit -m "feat(frontend): conversation transport hook, plan copy helpers and checks

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: `useTraCuu` mang `hoi_thoai_id`; `/dung-thu` mở, tiếp và tạo phiên

**Files:**
- Modify: `frontend/src/hooks/use-tra-cuu.ts`, `frontend/src/routes/dung-thu.tsx`

**Interfaces:**
- Consumes: Task 1 `SuKienBatDau.hoi_thoai_id`, `XuLyLuong.onLoiLuu`, `YeuCauTraCuu.hoi_thoai_id`, `chuanHoaLuot`; Task 5 `useHoiThoai`.
- Produces: `hoi(cauHoi: string, tuyChon?: { lichSu?: LuotTruoc[]; hoiThoaiId?: string })`; `TrangThaiTraCuu.hoiThoaiId: string | null` (từ `bat_dau`), `TrangThaiTraCuu.loiLuu: string | null`; `Route.validateSearch → { q?: string; phien?: string }`; trong `dung-thu.tsx` một chỗ đánh dấu `{/* CỘT PHIÊN — Task 7 */}` nơi Task 7 gắn `CotPhien`, và các callback Task 7 cần: `chonPhien(id)`, `phienMoi()`, `hoiThoai` (kết quả `useHoiThoai`).

- [x] **Step 1: `use-tra-cuu.ts`** — đổi chữ ký và thêm hai trạng thái:

```ts
export interface TuyChonHoi {
  /** Lịch sử client — chỉ khi ẨN DANH; có danh tính thì máy chủ tự nạp từ phiên. */
  lichSu?: LuotTruoc[];
  /** Phiên đang mở; vắng ⇒ máy chủ tạo phiên mới (có danh tính) hoặc bỏ qua (ẩn danh). */
  hoiThoaiId?: string;
}
```

Trong `TrangThaiTraCuu`: `hoi: (cauHoi: string, tuyChon?: TuyChonHoi) => void;` + `/** Phiên máy chủ gắn lượt này vào — từ `bat_dau`; null khi ẩn danh hoặc chưa tới. */ hoiThoaiId: string | null;` + `/** Thông điệp `loi_luu`: câu trả lời có nhưng chưa lưu vào phiên. */ loiLuu: string | null;`.

Thân hook: `const [hoiThoaiId, datHoiThoaiId] = useState<string | null>(null); const [loiLuu, datLoiLuu] = useState<string | null>(null);` `lichSuGanNhat` → `tuyChonGanNhat = useRef<TuyChonHoi | undefined>(undefined)`. Trong `hoi(noiDungTho, tuyChon)`: `tuyChonGanNhat.current = tuyChon; datLoiLuu(null);` (KHÔNG xoá `hoiThoaiId` ở đầu lượt — giữ để lượt hai của phiên vừa tạo còn id khi URL chưa kịp đổi); body:

```ts
          {
            query: noiDung,
            ...(tuyChon?.lichSu !== undefined && tuyChon.lichSu.length > 0 ? { lich_su: tuyChon.lichSu } : {}),
            ...(tuyChon?.hoiThoaiId !== undefined ? { hoi_thoai_id: tuyChon.hoiThoaiId } : {}),
          },
          {
            onBatDau: (su) => {
              if (luotNay !== luot.current) return;
              datCacBuoc(su.cac_buoc);
              datTraceId(su.trace_id);
              datHoiThoaiId(su.hoi_thoai_id);
            },
            onBuoc: …,
            onLoiLuu: (su) => {
              if (luotNay !== luot.current) return;
              datLoiLuu(su.detail);
            },
          },
```

`thuLai`: `hoi(cauHoi, tuyChonGanNhat.current)`. `datLai`: thêm `datHoiThoaiId(null); datLoiLuu(null);`. Trả thêm `hoiThoaiId, loiLuu`.

- [x] **Step 2: `dung-thu.tsx` — search và trạng thái**

`validateSearch`:

```ts
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  validateSearch: (tho: Record<string, unknown>): { q?: string; phien?: string } => {
    const q = tho["q"];
    const phien = tho["phien"];
    return {
      ...(typeof q === "string" && q.trim() !== "" ? { q } : {}),
      ...(typeof phien === "string" && UUID.test(phien) ? { phien } : {}),
    };
  },
```

Trong `ManHoiKlaw`: `const { q: cauHoiTrenUrl, phien: phienId } = Route.useSearch();` `const daDangNhap = !chuaCauHinh && !dangKiemPhien && user !== null;` `const hoiThoai = useHoiThoai(daDangNhap);`.

Đồng bộ với `?phien=` — một effect, ref nhớ phiên đang hiện để chỉ chạy khi URL THẬT SỰ đổi:

```ts
  // `?phien=` là nguồn sự thật về phiên đang mở (tải lại trang giữ được, chia sẻ
  // được). Đổi phiên ⇒ xoá dòng hội thoại, đóng khung, tải lượt đã lưu. Trường
  // hợp đặc biệt: sau `bat_dau` của phiên MỚI ta tự `replace` URL sang id đó —
  // lúc ấy `traCuu.hoiThoaiId === phienId` và dòng hội thoại đang chạy PHẢI giữ.
  const { datLai: datLaiTraCuu } = traCuu;
  const { dong: dongDoiChieu } = doiChieu; // `useDoiChieu` trả object mới mỗi render; `dong` là useCallback ổn định
  const { taiChiTiet, xoaChiTiet } = hoiThoai;
  const phienDangHien = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (dangKiemPhien || phienDangHien.current === phienId) return;
    phienDangHien.current = phienId;
    if (phienId !== undefined && phienId === traCuu.hoiThoaiId) return;
    datLuuTru([]);
    datDangMo(null);
    dongDoiChieu();
    datSoanThao(null);
    datLaiTraCuu();
    if (phienId !== undefined && daDangNhap) taiChiTiet(phienId);
    else xoaChiTiet();
  }, [phienId, dangKiemPhien, daDangNhap, traCuu.hoiThoaiId, datLaiTraCuu, taiChiTiet, xoaChiTiet, dongDoiChieu]);
```

(Đã kiểm: `useDoiChieu` trả object mới mỗi render, nên deps dùng `dongDoiChieu` chứ không dùng `doiChieu`; kiểm `dong` là `useCallback` trong `hooks/use-doi-chieu.ts`.)

Sau `bat_dau` của phiên mới → ghim id lên URL; hết stream → tải lại danh sách (máy chủ ghi lượt TRƯỚC khi đóng stream, nên lúc `dangChay` về false danh sách đã có lượt mới):

```ts
  useEffect(() => {
    if (!daDangNhap || traCuu.hoiThoaiId === null || phienId !== undefined) return;
    phienDangHien.current = traCuu.hoiThoaiId; // để effect trên không xoá dòng đang chạy
    void navigate({ to: "/dung-thu", search: { phien: traCuu.hoiThoaiId }, replace: true });
  }, [daDangNhap, traCuu.hoiThoaiId, phienId, navigate]);

  const { taiLai } = hoiThoai;
  useEffect(() => {
    if (daDangNhap && !traCuu.dangChay && traCuu.cauHoi !== null) taiLai();
  }, [daDangNhap, traCuu.dangChay, traCuu.cauHoi, taiLai]);
```

`gui()`: giữ phần xếp lượt đang hiện vào `luuTru`; dòng gọi cuối:

```ts
    if (daDangNhap) {
      const id = phienId ?? traCuu.hoiThoaiId ?? undefined;
      traCuu.hoi(noiDung, id === undefined ? {} : { hoiThoaiId: id });
    } else {
      traCuu.hoi(noiDung, { lichSu: dungLichSu(luotTruoc) });
    }
```

(`exactOptionalPropertyTypes`: không gán `hoiThoaiId: undefined`.) Effect `?q=`: giữ `hoi(cauHoiTrenUrl)` — phiên mới.

Hai callback cho Task 7:

```ts
  const chonPhien = (id: string) => void navigate({ to: "/dung-thu", search: { phien: id } });
  const phienMoi = () => void navigate({ to: "/dung-thu", search: {} });
```

- [x] **Step 3: `dung-thu.tsx` — render lượt đã lưu, lỗi phiên, `loi_luu`**

Trên `luuTru.map(...)` thêm các lượt đã tải (chỉ khi chi tiết đúng phiên đang mở):

```tsx
  const daTai =
    phienId !== undefined && hoiThoai.chiTiet !== null && hoiThoai.chiTiet.id === phienId
      ? hoiThoai.chiTiet.luot.map(chuanHoaLuot)
      : [];
  const chuaHoiGiCa = daTai.length === 0 && luuTru.length === 0 && traCuu.cauHoi === null && hoiThoai.loiChiTiet === null && !hoiThoai.dangTaiChiTiet;
```

Trong `<div className="flex flex-col gap-8">`, TRƯỚC `luuTru.map`:

```tsx
                  {daTai.map((l) => (
                    <Luot key={`da-luu-${l.thuTu}`} cauHoi={l.cauHoi} traceId={l.traceId}>
                      {l.ketQua === null ? (
                        <p className="m-0 text-[14px] leading-6 text-muted-foreground">
                          Lượt này được lưu ở định dạng cũ nên tôi không hiển thị lại được.
                        </p>
                      ) : (
                        <TheKetQua
                          ketQua={l.ketQua}
                          cauHoiGoc={l.cauHoi}
                          chiSoDangMo={chiSoDangMoCua(l.ketQua)}
                          onChonTrichDan={(chiSo) => { const kq = l.ketQua; if (kq !== null) chonTrichDan(kq, chiSo); }}
                          onSoanThao={moSoanThao}
                        />
                      )}
                    </Luot>
                  ))}
```

Khối trạng thái phiên, đặt ngay trên `<div className="flex flex-col gap-8">` (trong vùng hội thoại — `chuaHoiGiCa` đã tính cả hai trạng thái này nên `ManChao` không che):

```tsx
                {hoiThoai.dangTaiChiTiet && (
                  <p className="m-0 mb-6 text-[13px] text-muted-foreground" aria-live="polite">Đang mở phiên…</p>
                )}
                {hoiThoai.loiChiTiet !== null && (
                  <div className="mb-6 rounded-xl border border-dashed border-border px-4 py-3">
                    <p className="m-0 text-[14px] leading-6 text-foreground">{hoiThoai.loiChiTiet.message}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {hoiThoai.loiChiTiet.status === 403 && (
                        <Link to="/bang-gia" className="focus-brass inline-flex min-h-9 items-center rounded-lg border border-border px-3 text-[13px] font-medium text-primary hover:bg-[var(--color-paper-100)]">
                          Xem bảng giá
                        </Link>
                      )}
                      <button type="button" onClick={phienMoi} className="focus-brass inline-flex min-h-9 cursor-pointer items-center rounded-lg border border-border px-3 text-[13px] font-medium text-primary hover:bg-[var(--color-paper-100)]">
                        Phiên mới
                      </button>
                    </div>
                  </div>
                )}
```

(`import { Link } from "@tanstack/react-router"` gộp vào import sẵn có. Câu 403/404 là `detail` máy chủ đi qua `loiTheoStatus` — không chép lại ở FE.) Dưới `TheKetQua` của lượt đang chạy, sau khối `traCuu.ketQua !== null && (...)`:

```tsx
                      {traCuu.loiLuu !== null && (
                        <p className="mt-3 mb-0 text-[12px] text-muted-foreground" role="status">{traCuu.loiLuu}</p>
                      )}
```

Ở vị trí `<aside aria-label="Lịch sử phiên"` hiện có: bọc điều kiện `!daDangNhap &&` (cột trong bộ nhớ chỉ còn cho ẩn danh/máy dev — spec §6 "mọi thứ như hiện nay") và đặt ngay trên nó một dòng `{/* CỘT PHIÊN — Task 7: {daDangNhap && doiChieu.dang === null && soanThao === null && <CotPhien …/>} */}`.

- [x] **Step 4: Xanh** — `npm run typecheck && npm run lint && npm run kiem-lich-su && npm run kiem-sse && npx prettier --check src/hooks/use-tra-cuu.ts src/routes/dung-thu.tsx`. Chạy `npm run dev` (port 3000, backend 8000 đang chạy) và mở `http://localhost:3000/dung-thu?phien=khong-hop-le` → URL rớt tham số; `?phien=<uuid bất kỳ>` ở máy dev (ẩn danh) → không gọi `/hoi-thoai`, màn chào như cũ.

- [x] **Step 5: Commit**

```bash
git add frontend/src/hooks/use-tra-cuu.ts frontend/src/routes/dung-thu.tsx
git commit -m "feat(frontend): open, continue and create conversations from /dung-thu?phien=

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `CotPhien` — danh sách phiên, đổi tên, xoá, sheet dưới xl

**Files:**
- Create: `frontend/src/components/klaw/DanhSachPhien.tsx`
- Modify: `frontend/src/routes/dung-thu.tsx` (thay dòng đánh dấu Task 7 bằng `<CotPhien …/>`)

**Interfaces:**
- Consumes: Task 5 `TrangThaiHoiThoai`, `cauPhienAn`, `thoiGianTuongDoi`; Task 6 `chonPhien`, `phienMoi`, `phienId`, `hoiThoai`.
- Produces: `CotPhien(props: { hoiThoai: TrangThaiHoiThoai; phienDangMo: string | undefined; onChon: (id: string) => void; onPhienMoi: () => void; onDaXoa: (id: string) => void })` — tự chứa aside ≥xl (thu gọn được) và nút "Phiên" + sheet <xl.

- [x] **Step 1: Component** `frontend/src/components/klaw/DanhSachPhien.tsx`

```tsx
import { Link } from "@tanstack/react-router";
import { Check, ChevronRight, MessageSquare, Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { TrangThaiHoiThoai } from "@/hooks/use-hoi-thoai";
import type { PhienTomTat } from "@/lib/klaw";
import { cauPhienAn, thoiGianTuongDoi } from "@/lib/phien";
import { cn } from "@/lib/utils";

/**
 * Cột phiên hội thoại (spec 2026-09-07 §6). Một danh sách, hai vỏ: aside cố
 * định từ xl (80rem) và sheet trượt lên dưới đó — cùng khuôn với ngăn kéo bộ
 * lọc của trang Tra cứu. Đổi tên và xoá đều làm TẠI CHỖ (Enter lưu, Esc huỷ;
 * xác nhận xoá là hai nút, không `confirm()` — hộp thoại trình duyệt chặn cả
 * tab và không theo được giao diện).
 */
interface Props {
  hoiThoai: TrangThaiHoiThoai;
  phienDangMo: string | undefined;
  onChon: (id: string) => void;
  onPhienMoi: () => void;
  /** Phiên vừa xoá xong — cha quyết định có phải điều hướng đi không. */
  onDaXoa: (id: string) => void;
}

const NUT_PHU =
  "focus-brass grid size-8 cursor-pointer place-items-center rounded-md text-muted-foreground transition-colors hover:bg-[var(--color-brass-500)]/10 hover:text-foreground";

function MotPhien({
  phien, dangMo, onChon, onDoiTen, onXoa,
}: {
  phien: PhienTomTat;
  dangMo: boolean;
  onChon: () => void;
  onDoiTen: (tieuDe: string) => Promise<boolean>;
  onXoa: () => Promise<boolean>;
}) {
  const [cheDo, datCheDo] = useState<"xem" | "sua" | "xoa">("xem");
  const [nhap, datNhap] = useState(phien.tieu_de);
  const [loi, datLoi] = useState<string | null>(null);
  const [dangGui, datDangGui] = useState(false);
  const o = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    if (cheDo === "sua") o.current?.select();
  }, [cheDo]);

  const luuTen = async () => {
    const ten = nhap.trim();
    if (ten === "" || ten === phien.tieu_de) { datCheDo("xem"); datNhap(phien.tieu_de); return; }
    datDangGui(true);
    const ok = await onDoiTen(ten);
    datDangGui(false);
    if (ok) { datCheDo("xem"); datLoi(null); } else datLoi("Tôi chưa đổi tên được, thử lại nhé.");
  };
  const xoa = async () => {
    datDangGui(true);
    const ok = await onXoa();
    datDangGui(false);
    if (!ok) datLoi("Tôi chưa xoá được phiên này, thử lại nhé.");
  };

  if (cheDo === "sua") {
    return (
      <li className="rounded-lg border border-[var(--color-brass-500)]/60 bg-card p-2">
        <input
          ref={o}
          value={nhap}
          maxLength={120}
          disabled={dangGui}
          onChange={(su) => datNhap(su.target.value)}
          onKeyDown={(su) => {
            if (su.key === "Enter") { su.preventDefault(); void luuTen(); }
            if (su.key === "Escape") { su.preventDefault(); datCheDo("xem"); datNhap(phien.tieu_de); }
          }}
          aria-label="Tên phiên"
          className="w-full bg-transparent text-[13px] outline-none"
        />
        <div className="mt-1.5 flex items-center justify-end gap-1">
          <button type="button" onClick={() => void luuTen()} aria-label="Lưu tên" className={NUT_PHU}><Check className="size-4" aria-hidden /></button>
          <button type="button" onClick={() => { datCheDo("xem"); datNhap(phien.tieu_de); }} aria-label="Huỷ đổi tên" className={NUT_PHU}><X className="size-4" aria-hidden /></button>
        </div>
        {loi !== null && <p className="m-0 mt-1 text-[12px] text-destructive">{loi}</p>}
      </li>
    );
  }
  if (cheDo === "xoa") {
    return (
      <li className="rounded-lg border border-border bg-card p-2.5 text-[12px]">
        <p className="m-0 text-foreground">Xoá phiên này? Các lượt đã hỏi sẽ không mở lại được.</p>
        <div className="mt-2 flex gap-2">
          <button type="button" disabled={dangGui} onClick={() => void xoa()} className="focus-brass min-h-8 cursor-pointer rounded-md bg-destructive px-2.5 font-medium text-white disabled:opacity-60">Xoá</button>
          <button type="button" onClick={() => datCheDo("xem")} className="focus-brass min-h-8 cursor-pointer rounded-md border border-border px-2.5 font-medium text-primary">Giữ lại</button>
        </div>
        {loi !== null && <p className="m-0 mt-1 text-destructive">{loi}</p>}
      </li>
    );
  }
  return (
    <li className={cn("group flex items-start gap-1 rounded-lg border p-2 text-[12px]", dangMo ? "border-[var(--color-brass-500)]/60 bg-card shadow-soft" : "border-transparent hover:bg-card")}>
      <button type="button" onClick={onChon} aria-current={dangMo ? "true" : undefined} className="focus-brass min-w-0 flex-1 cursor-pointer rounded-md p-1 text-left">
        <span className="block truncate text-[13px] font-medium text-foreground">{phien.tieu_de}</span>
        <span className="mt-0.5 block text-muted-foreground">{phien.so_luot} lượt · {thoiGianTuongDoi(phien.cap_nhat_luc)}</span>
      </button>
      <div className="flex shrink-0 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
        <button type="button" onClick={() => datCheDo("sua")} aria-label={`Đổi tên phiên ${phien.tieu_de}`} className={NUT_PHU}><Pencil className="size-3.5" aria-hidden /></button>
        <button type="button" onClick={() => datCheDo("xoa")} aria-label={`Xoá phiên ${phien.tieu_de}`} className={NUT_PHU}><Trash2 className="size-3.5" aria-hidden /></button>
      </div>
    </li>
  );
}

function ThanDanhSach({ hoiThoai, phienDangMo, onChon, onPhienMoi, onDaXoa }: Props) {
  const { danhSach, dangTai, loi, taiLai, doiTen, xoa } = hoiThoai;
  return (
    <div className="soft-fade">
      <button type="button" onClick={onPhienMoi} className="focus-brass bg-gradient-ink mb-3 inline-flex min-h-9 w-full cursor-pointer items-center justify-center gap-1.5 rounded-lg px-3 text-[13px] font-medium text-primary-foreground transition-opacity hover:opacity-90">
        <Plus className="size-4" aria-hidden /> Phiên mới
      </button>
      {loi !== null ? (
        <div className="rounded-lg border border-dashed border-border p-2.5 text-[12px]">
          <p className="m-0 text-muted-foreground">{loi.message}</p>
          <button type="button" onClick={taiLai} className="focus-brass mt-2 min-h-8 cursor-pointer rounded-md border border-border px-2.5 font-medium text-primary">Tải lại</button>
        </div>
      ) : danhSach === null ? (
        <p className="text-[12px] text-muted-foreground" aria-live="polite">{dangTai ? "Đang tải phiên…" : ""}</p>
      ) : danhSach.items.length === 0 ? (
        <p className="text-[12px] text-muted-foreground">Chưa có phiên nào. Hỏi một câu để bắt đầu.</p>
      ) : (
        <>
          <ul className="m-0 list-none space-y-1 p-0">
            {danhSach.items.map((p) => (
              <MotPhien
                key={p.id}
                phien={p}
                dangMo={p.id === phienDangMo}
                onChon={() => onChon(p.id)}
                onDoiTen={async (t) => (await doiTen(p.id, t)).ok}
                onXoa={async () => { const kq = await xoa(p.id); if (kq.ok) onDaXoa(p.id); return kq.ok; }}
              />
            ))}
          </ul>
          {danhSach.tong_an > 0 && (
            <p className="mt-3 border-t border-border pt-2 text-[12px] text-muted-foreground">
              {cauPhienAn(danhSach.plan, danhSach.gioi_han, danhSach.tong_an)}{" "}
              <Link to="/bang-gia" className="focus-brass text-[var(--color-brass-600)] underline-offset-2 hover:underline">Xem bảng giá</Link>
            </p>
          )}
        </>
      )}
    </div>
  );
}

export function CotPhien(props: Props) {
  const [panelMo, datPanelMo] = useState(true);
  const [sheetMo, datSheetMo] = useState(false);
  // Chọn/tạo phiên từ sheet thì đóng sheet — người dùng muốn thấy hội thoại.
  const chon = (id: string) => { datSheetMo(false); props.onChon(id); };
  const moi = () => { datSheetMo(false); props.onPhienMoi(); };
  const than = <ThanDanhSach {...props} onChon={chon} onPhienMoi={moi} />;
  return (
    <>
      <aside aria-label="Phiên hội thoại" className={cn("hidden shrink-0 border-l border-border bg-[var(--color-paper-50)] transition-[width] duration-150 xl:block", panelMo ? "w-[300px]" : "w-[52px]")}>
        <div className="sticky top-[49px] p-3">
          <button type="button" onClick={() => datPanelMo((m) => !m)} aria-label={panelMo ? "Thu gọn cột phiên" : "Mở cột phiên"} aria-expanded={panelMo} className="focus-brass mb-3 cursor-pointer rounded-md p-1.5 text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/10">
            <ChevronRight className={cn("size-4 transition-transform duration-150", panelMo && "rotate-180")} aria-hidden />
          </button>
          {panelMo && (
            <>
              <p className="border-b border-border pb-2 text-[12px] font-semibold text-primary">Phiên hội thoại</p>
              <div className="mt-3">{than}</div>
            </>
          )}
        </div>
      </aside>

      <button type="button" hidden={sheetMo} onClick={() => datSheetMo(true)} aria-expanded={sheetMo} aria-controls="phien-ngan-keo" className="focus-brass fixed right-4 bottom-[132px] z-40 inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-full border border-[var(--color-brass-500)]/60 bg-card px-4 text-[13px] font-medium text-[var(--color-brass-600)] shadow-soft xl:hidden">
        <MessageSquare className="size-4" aria-hidden /> Phiên
      </button>
      {sheetMo && (
        <div className="fixed inset-0 z-50 xl:hidden">
          <div className="absolute inset-0 bg-[var(--color-ink-950)]/45" onClick={() => datSheetMo(false)} aria-hidden />
          <div id="phien-ngan-keo" role="dialog" aria-modal="true" aria-label="Phiên hội thoại" className="rise-in absolute inset-x-0 bottom-0 max-h-[82vh] overflow-y-auto rounded-t-2xl border-t border-border bg-background px-4 pt-4 pb-8">
            <div className="mb-2 flex items-center justify-between">
              <p className="font-display m-0 text-sm font-semibold text-primary">Phiên hội thoại</p>
              <button type="button" onClick={() => datSheetMo(false)} aria-label="Đóng danh sách phiên" className="focus-brass grid size-11 cursor-pointer place-items-center rounded-md text-muted-foreground hover:text-foreground"><X className="size-4" aria-hidden /></button>
            </div>
            {than}
          </div>
        </div>
      )}
    </>
  );
}
```

(Kiểm `text-destructive`/`bg-destructive` có trong token Tailwind của dự án — `grep -rn "destructive" frontend/src/styles frontend/src/index.css` — nếu không có, dùng token đỏ sẵn có theo `DESIGN.md`.) Nút sheet đặt `bottom-[132px] right-4` để không đè ô soạn câu hỏi (sticky đáy ~110px) — kiểm ở 375px.

- [x] **Step 2: Gắn vào `dung-thu.tsx`** — thay dòng đánh dấu Task 7:

```tsx
        {daDangNhap && doiChieu.dang === null && soanThao === null && (
          <CotPhien
            hoiThoai={hoiThoai}
            phienDangMo={phienId}
            onChon={chonPhien}
            onPhienMoi={phienMoi}
            onDaXoa={(id) => { if (id === phienId) phienMoi(); }}
          />
        )}
```

Import `CotPhien`. Khi khung soạn thảo/đối chiếu mở, cả nút sheet cũng ẩn (nằm trong cùng điều kiện). Cột "Lịch sử phiên" cũ vẫn render cho `!daDangNhap`.

- [x] **Step 3: Xanh** — `npm run typecheck && npm run lint && npx prettier --check src/components/klaw/DanhSachPhien.tsx src/routes/dung-thu.tsx && npm run build`. Chrome (ẩn danh, máy dev): `/dung-thu` không có cột mới, cột cũ còn; không lỗi console.

- [x] **Step 4: Commit**

```bash
git add frontend/src/components/klaw/DanhSachPhien.tsx frontend/src/routes/dung-thu.tsx
git commit -m "feat(frontend): conversation column with inline rename, delete and hidden-count notice

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

# BƯỚC 3 — GỘP VÀ ĐÓNG (checkout chính)

### Task 8: Gộp hai nhánh, kiểm toàn bộ, chứng cứ, đóng plan

**Files:**
- Modify: `docs/plans/active/lich-su-hoi-thoai.md` → `docs/plans/completed/`, `docs/superpowers/plans/2026-09-07-lich-su-hoi-thoai.md` (tick), `.tham-dinh-shots/` (ảnh mới).

- [x] **Step 1: Gộp** (checkout chính, nhánh `feat/tro-ly-phap-luat`):

```bash
git merge --no-ff wt-be-phien -m "merge: backend conversation history (wt-be-phien)" && git merge --no-ff wt-fe-phien -m "merge: frontend conversation history (wt-fe-phien)"
git worktree remove ../KLAW-be3 && git worktree remove ../KLAW-fe3 && git branch -d wt-be-phien wt-fe-phien
```

Xung đột chỉ có thể ở `frontend/src/lib/klaw.ts`/`api.ts` nếu BE stream sửa (không được phép) — nếu có, giữ bản FE.

- [x] **Step 2: Kiểm toàn bộ**

```bash
.venv/bin/ruff check src/ tests/ && .venv/bin/python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py
cd frontend && npm run kiem
```

Kỳ vọng: pytest xanh (2 test đỏ đã biết nằm trong đường bỏ qua); `npm run kiem` xanh gồm `kiem-phien`.

- [x] **Step 3: Chrome (máy dev, ẩn danh)** — backend 8000 (`KLAW_SUPABASE_URL` rỗng) + vite 3000: `/dung-thu` hỏi một câu → `bat_dau.hoi_thoai_id` null trong Network, không gọi `/hoi-thoai`, cột "Lịch sử phiên" cũ hoạt động; `?phien=<uuid>` bị bỏ qua. Chụp `.tham-dinh-shots/14-dung-thu-an-danh-khong-doi.png`.

- [x] **Step 4: Chrome (có danh tính)** — CẦN chủ sản phẩm đăng nhập trong tab Chrome đang kết nối (không bao giờ nhập thông tin đăng nhập thay họ) và backend chạy với `KLAW_SUPABASE_URL` thật. Nếu phiên đăng nhập có sẵn: tạo hai phiên, chuyển qua lại, hỏi nối tiếp ở phiên cũ ("còn ở khoản mấy?"), đổi tên, xoá, tải lại trang giữ `?phien=`. Chụp `15-cot-phien.png`, `16-doi-ten-xoa-tai-cho.png`, `17-phien-an-403.png` (tạm hạ `phien_luu.free` trong YAML để tạo phiên ẩn, rồi trả về 10). Không có phiên đăng nhập → ghi rõ trong báo cáo là bước này CHƯA chạy và để lại checklist cho chủ sản phẩm trong plan bền.

- [x] **Step 5: Đóng plan** — tick mọi `- [x]` trong plan này; điền "Kết quả" vào `docs/plans/active/lich-su-hoi-thoai.md` (commit gộp, số test, ảnh, bước 4 đã/chưa chạy) rồi `git mv` sang `docs/plans/completed/`.

```bash
git add docs/plans docs/superpowers/plans/2026-09-07-lich-su-hoi-thoai.md .tham-dinh-shots/14-*.png
git commit -m "docs(plans): close conversation-history plan with evidence

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Tự soát plan (đã chạy khi viết)

- **Phủ spec:** §4.1 migration → T1; §4.2 YAML + `phien_luu_toi_da` → T1; §4.3 quy tắc hiện → T2 `phien_bi_an`/`danh_sach`; §5.1 → T2; §5.2 → T3; §5.3 → T4; §6 kiểu/API → T1, hook → T5, route → T6, cột → T7; §7 → T2–T4 (lọc `user_sub`, 404 không tiết lộ, `loi_luu`), T7 render text node; §8 pytest → T1–T4, `kiem-phien` → T5, Chrome → T8.
- **Lệch spec có chủ ý:** §8 nêu FE kiểm `tieuDeMacDinh` — tiêu đề mặc định do MÁY CHỦ đặt (§5.1) và FE không có bản sao, nên `kiem-phien` kiểm `cauPhienAn`/`thoiGianTuongDoi`/predicate/`chuanHoaLuot` thay thế; test Python T2 phủ cắt 80 ranh giới từ. Câu ẩn dùng tên gói thật (`tenGoi`) thay vì cố định "Miễn phí" để gói pro không hiện sai.
- **Nhất quán tên:** `phien_luu_toi_da`, `plan_cua`, `nguoi_dung_bat_buoc` (T1) ↔ T2/T3/T4; `_chuan_bi_phien`, `_ghi_luot_nhe` (T3) ↔ routes_luong; `laDanhSachPhien`, `laChiTietPhien`, `chuanHoaLuot`, `SuKienLoiLuu` (T1) ↔ T5/T6; `useHoiThoai` trả `chiTiet/taiChiTiet/xoaChiTiet/taiLai/doiTen/xoa` (T5) ↔ T6/T7; `CotPhien` props (T7) ↔ T6 `chonPhien/phienMoi/phienId/hoiThoai`.
