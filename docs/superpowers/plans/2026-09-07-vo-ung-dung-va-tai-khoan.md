# Vỏ ứng dụng, tài khoản và hạn mức ngày/tháng — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Người đã đăng nhập có vỏ ứng dụng kiểu ChatGPT (sidebar trái, menu tài khoản, hồ sơ, cá nhân hoá, nâng gói hai card), hạn mức tính theo ngày/tháng/tính năng với thanh đo, gói Cá nhân theo chu kỳ 30 ngày; khách chưa đăng nhập dùng thử 10 lượt/24 giờ và mang đoạn chat vào tài khoản khi đăng nhập.

**Architecture:** `config/han_muc.yaml` đổi sang một khối mỗi gói (`goi.<plan>.{hoi_dap_ngay, soan_thao_ngay, soan_thao_thang, luot_moi_phien}`) + `la_chan` + `khach` + `chu_ky_pro_ngay`; `bao_ve` đếm trên `traces` theo mốc giờ Việt Nam, gói hiệu lực tính từ `users.plan_het_han`; `cong_bao_ve` tách hai biến thể (có/không cho khách); cơ chế ẩn phiên của gói 1 bị gỡ; router tài khoản thêm `/han-muc` v2, `/ho-so`, `/nang-goi/yeu-cau`, `/hoi-thoai/nhap`. Frontend: `TaiKhoanProvider` ở gốc giữ auth + danh sách phiên + hạn mức cho mọi trang; `AppShell` thành sidebar ChatGPT; `/dung-thu` bỏ cột phải, thêm khách và ba trạng thái hết hạn mức; hai route `/tai-khoan*`; `ModalNangGoi`.

**Tech Stack:** FastAPI + SQLAlchemy `text()` + pydantic v2 + `zoneinfo` + pytest (fixture `client`, `cai_dat`, `khoa_ky`, `_bearer`, `graph_gia_lap`, `khong_dung_db`); React 19 + TanStack Router 1.170 + Tailwind 4, TS `exactOptionalPropertyTypes: true`, check scripts `frontend/scripts/kiem-*.ts`, Supabase JS v2 (`auth.updateUser`).

**Spec:** `docs/superpowers/specs/2026-09-07-vo-ung-dung-va-tai-khoan-design.md`

## Global Constraints

- Số hạn mức (spec §4.1): Free `hoi_dap_ngay 200, soan_thao_ngay 3, soan_thao_thang 20, luot_moi_phien 20`; Pro `hoi_dap_ngay 100000, soan_thao_ngay 20, soan_thao_thang 100000, luot_moi_phien 50`; `la_chan {free_hoi_dap_thang 2000, pro_hoi_dap_ngay 500, ip_ngay 400}`; `khach {hoi_dap_24h 10, ip_24h 30}`; `chu_ky_pro_ngay 30`; `mui_gio Asia/Ho_Chi_Minh`; quy ước 0 = chặn, ≥100000 = không giới hạn. Khoá `phien_luu` bị gỡ và phải làm `_doc_han_muc` lỗi rõ nếu còn.
- Đếm lượt (§4.2): `traces` với `user_sub = :sub AND ts >= :moc AND NOT cache_hit AND endpoint = :ep AND (result_type IS NULL OR result_type NOT IN ('loi','out_of_scope'))`. `/tra-cuu` kiểm `hoi_dap_ngay` rồi lá chắn (`free_hoi_dap_thang`/`pro_hoi_dap_ngay`); `/soan-thao` kiểm `soan_thao_ngay` rồi `soan_thao_thang`. Mốc ngày/tháng theo `mui_gio`. 429 mang `detail` tiếng Việt có mốc mở lại và `Retry-After`.
- Gói hiệu lực (§5): `plan_hieu_luc(sub)` = `users.plan` khi `plan_het_han IS NULL OR plan_het_han > now()`, ngược lại `goi_mac_dinh`; mọi chỗ đọc gói dùng hàm này.
- Trần lượt mỗi phiên: 403 `LOI_PHIEN_DAY.format(n=…)` = "Phiên này đã đủ {n} lượt. Mở phiên mới để tiếp tục." tại lượt thứ n+1; gỡ hẳn `phien_bi_an`, `_SQL_HANG`, `LOI_PHIEN_AN`, `gioi_han/tong_hien/tong_an`.
- Khách (§8): header `X-Khach-Id` (UUID v4 do FE sinh, localStorage `klaw.khach_id`); chỉ `/tra-cuu*`; `/soan-thao` khách → 401 "Cần đăng nhập để soạn văn bản."; đếm `kiem_rate_limit("khach:{id}", 10, 86400)` rồi `("khach-ip:{ip}", 30, 86400)`; không tạo phiên, không ghi lượt. Chưa cấu hình Supabase: hành vi cũ, không đếm khách.
- `kiem_rate_limit` dọn hàng cũ THEO KHOÁ và nhận `cua_so_giay`; `Retry-After` tính từ lượt cũ nhất còn trong cửa sổ.
- Chữ hiển thị mới không chứa "hệ thống", "không diễn giải", "chưa đủ căn cứ", "truy hồi", "database", "để bạn tự đối chiếu", "máy chủ trả về"; xưng "tôi". Gói `pro` hiển thị "Cá nhân"; giá "₫499.000 / 30 ngày".
- Frontend không thêm dependency; `exactOptionalPropertyTypes: true`; user text render bằng text node; mật khẩu và tên hiển thị đi thẳng Supabase (`supabase.auth.updateUser`), backend không nhận.
- Không đụng: `TheKetQua.tsx`, `KhongGianSoanThao.tsx` (trừ điểm gắn `TheDangNhap` ở Task 10), `Luot`, `chonTrichDan`, khối `KhungDoiChieu`, khối khung soạn thảo trong `dung-thu.tsx`, các sửa lỗi gói 1 (`phienDangHien`, `daGhim`, `phienMoi` reset trước navigate, `thuLai` merge id).
- Không chạy `make check`/`make format`. Python: `.venv/bin/ruff check src/ tests/` + pytest có đích + `.venv/bin/ruff format --check <file đã sửa>` (drift dòng cũ là baseline). Pytest FOREGROUND, timeout 600000. DB local docker `klaw-db-1`; áp migration bằng `.venv/bin/python -c "from src.services.db import run_migrations; print(run_migrations('021'))"`.
- Worktree: symlink `.venv`, `.env.local`, `data/raw`, `frontend/node_modules`. Không stage file bẩn có từ trước (docs/guide/*, scripts/log_*.py, scripts/setup*, README_boilerplate.md, src/services/checklist.py, tests/test_services/test_moi_mau.py, qh3.html, .impeccable/, eval/results/lexical_only-*.json, config/checklist_don_xin_nghi_viec.yaml, eval/datasets/golden_qa_candidates.yaml, .agents/, presentation/README.md, prompts/, docs/soul-*.md, .tham-dinh-shots/ trừ ảnh của plan này).
- Commit tiếng Anh, conventional, kèm `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File Structure

| File | Trách nhiệm | Task |
|---|---|---|
| `config/han_muc.yaml` | hình mới §4.1 | 1 |
| `migrations/021_nang_goi.sql` | `yeu_cau_nang_goi`, `users.plan_het_han` | 1 |
| `src/services/bao_ve.py` | `_doc_han_muc` v2, `han_muc`, `la_chan`, `moc_*`, `plan_hieu_luc`, `dem_luot`, `kiem_han_muc`, `kiem_rate_limit` theo khoá + cửa sổ, `cong_bao_ve`/`cong_bao_ve_khach`, khách | 1, 3 |
| `src/models/schemas.py` | `MucHanMuc`, `HanMucResponse` v2, `HoSoResponse`, `YeuCauNangGoiRequest/Out`, `NhapPhienRequest/Response`, `DanhSachPhienResponse` v2 | 1 |
| `src/main.py` | migrations `("019","020","021")` | 1 |
| `src/services/hoi_thoai.py` | gỡ ẩn phiên; `LOI_PHIEN_DAY`, `dem_luot`, `nhap_phien` | 2 |
| `src/api/routes.py`, `src/api/routes_luong.py` | `_chuan_bi_phien` trần phiên; `cong_bao_ve_khach` | 2, 3 |
| `src/api/routes_hoi_thoai.py` | bỏ 403 ẩn; `luot_moi_phien`; `POST /hoi-thoai/nhap` | 2, 4 |
| `src/services/ho_so.py` (mới), `src/services/nang_goi.py` (mới) | tổng hợp hồ sơ; yêu cầu nâng gói | 4 |
| `src/api/routes_tai_khoan.py` | `/han-muc` v2, `/ho-so`, `/nang-goi/yeu-cau` | 4 |
| `frontend/src/lib/klaw.ts`, `frontend/src/lib/api.ts` | kiểu v2, guard, header `X-Khach-Id` | 1 |
| `frontend/src/lib/khach.ts` (mới), `frontend/src/lib/han-muc.ts` (mới), `frontend/src/lib/goi.ts` (mới), `frontend/src/lib/phien.ts` | mã khách + cất thread; phần trăm/màu/mốc; TIERS + `tenGoi`; bỏ `cauPhienAn` | 1, 5 |
| `frontend/src/hooks/use-han-muc.ts` (mới), `frontend/src/components/tai-khoan/ThuocMucDung.tsx` (mới), `frontend/scripts/kiem-han-muc.ts` (mới) | hạn mức + thanh đo | 5 |
| `frontend/src/contexts/tai-khoan.tsx` (mới), `frontend/src/routes/__root.tsx` | `TaiKhoanProvider`/`useTaiKhoan` | 6 |
| `frontend/src/components/app/AppShell.tsx`, `frontend/src/components/tai-khoan/TheTaiKhoan.tsx`, `MenuTaiKhoan.tsx` (mới), `frontend/src/components/klaw/DanhSachPhien.tsx` | vỏ ChatGPT | 6 |
| `frontend/src/routes/dung-thu.tsx` | bỏ cột phải; khách; trần phiên; 429; hết hạn Pro | 7 |
| `frontend/src/routes/tai-khoan.tsx`, `tai-khoan.index.tsx`, `tai-khoan.ca-nhan-hoa.tsx` (mới), `frontend/src/lib/quay-lai.ts`, `frontend/scripts/kiem-quay-lai.ts`, `frontend/src/routes/dang-ky.tsx` | hồ sơ, cá nhân hoá, bỏ Vai trò | 8 |
| `frontend/src/components/tai-khoan/ModalNangGoi.tsx` (mới), `frontend/src/routes/bang-gia.tsx` | nâng gói hai card; bảng giá | 9 |
| `frontend/src/components/soan-thao/KhongGianSoanThao.tsx` (một điểm), `frontend/src/routes/soan-thao.index.tsx` | khách → `TheDangNhap` khi bấm soạn; 429 | 10 |
| `docs/plans/active/vo-ung-dung-va-tai-khoan.md` → `completed/` | plan bền | 1, 11 |

Thứ tự: Task 1 (main) → worktree `../KLAW-be4` (`wt-be-tk`): 2 → 3 → 4; worktree `../KLAW-fe4` (`wt-fe-tk`): 5 → 6 → 7 → 8 → 9 → 10 (song song với BE) → Task 11 (main) gộp, kiểm, Chrome, đóng.

---

# BƯỚC 0 — HỢP ĐỒNG (checkout chính)

### Task 1: YAML v3, gói hiệu lực, migration 021, schema hai phía, header khách, worktree

**Files:**
- Create: `migrations/021_nang_goi.sql`, `docs/plans/active/vo-ung-dung-va-tai-khoan.md`, `tests/test_api/test_han_muc_yaml.py`, `frontend/src/lib/khach.ts`
- Modify: `config/han_muc.yaml` (thay toàn bộ), `src/services/bao_ve.py` (`_doc_han_muc`; thêm `han_muc`, `la_chan`, `mui_gio`, `moc_*`, `plan_hieu_luc_tu`, `plan_hieu_luc`, `khach_id_tu_request`; `ghi_nhan_nguoi_dung` trả gói hiệu lực; `han_muc_thang`/`phien_luu_toi_da` thành shim tạm), `src/models/schemas.py`, `src/main.py:53`, `tests/test_api/test_guard_khoi_dong.py`, `frontend/src/lib/klaw.ts`, `frontend/src/lib/api.ts`, `frontend/src/routes/bang-gia.tsx` (gỡ `HanMucThang`)
- Delete: `tests/test_api/test_han_muc_phien.py`, `frontend/src/components/klaw/HanMucThang.tsx`

**Interfaces:**
- Produces (BE): `bao_ve.han_muc(plan: str, khoa: str) -> int` (gói lạ → gói mặc định; khoá lạ → `KeyError`); `bao_ve.la_chan(khoa: str) -> int`; `bao_ve.mui_gio() -> ZoneInfo`; `bao_ve.moc_ngay(now=None) -> datetime`, `moc_ngay_sau`, `moc_thang`, `moc_thang_sau` (aware, theo `mui_gio`); `bao_ve.plan_hieu_luc_tu(plan, het_han: datetime | None) -> str`; `bao_ve.plan_hieu_luc(sub) -> str`; `bao_ve.ghi_nhan_nguoi_dung(sub, email) -> str` trả gói HIỆU LỰC; `bao_ve.KHACH_HEADER = "x-khach-id"`; `bao_ve.khach_id_tu_request(request) -> str | None`. Models: `MucHanMuc{khoa, nhan, da_dung, han_muc, dat_lai_luc: datetime | None}`, `PhienHanMuc{luot_toi_da: int | None}`, `HanMucResponse{ap_dung, plan, ten_goi, mui_gio, muc, phien, het_han_luc, ghi_chu}`, `HoatDongNgay{ngay: date, so_luot}`, `PhanLoai{khoa, nhan, so}`, `HoSoResponse{email, plan, ten_goi, tao_luc, het_han_luc, so_phien, tong_hoi_dap, tong_ban_thao, hoat_dong, phan_loai}`, `YeuCauNangGoiRequest{goi_muon}`, `YeuCauNangGoiOut{id, loai, goi_hien_tai, goi_muon, trang_thai, tao_luc, xu_ly_luc}`, `LuotNhap{cau_hoi, tra_loi: TraCuuResponse, trace_id}`, `NhapPhienRequest{luot: 1–10}`, `NhapPhienResponse{id}`, `DanhSachPhienResponse{plan, luot_moi_phien, tong, items}`.
- Produces (FE): `MucHanMuc`, `HanMuc` v2, `laHanMuc`, `HoSo`, `laHoSo`, `YeuCauNangGoi`, `laYeuCauNangGoi`, `laYeuCauNangGoiHoacNull`, `laNhapPhien`, `DanhSachPhien` v2, `laDanhSachPhien`; `lib/khach.ts`: `KHACH_HEADER`, `layKhachId()`; `api.ts` gửi `X-Khach-Id` khi không có bearer (cả `goi` và `traCuuLuong`).

- [ ] **Step 1: Plan bền** `docs/plans/active/vo-ung-dung-va-tai-khoan.md`

```markdown
# Execution Plan: Vỏ ứng dụng, tài khoản và hạn mức ngày/tháng (gói 2A)

Date: 2026-09-07

## Status

Active

## Spec / Plan

- docs/superpowers/specs/2026-09-07-vo-ung-dung-va-tai-khoan-design.md
- docs/superpowers/plans/2026-09-07-vo-ung-dung-va-tai-khoan.md

## Progress

- [ ] Task 1 hợp đồng: YAML v3, gói hiệu lực, migration 021, schema, header khách
- [ ] Task 2 gỡ ẩn phiên, trần lượt mỗi phiên
- [ ] Task 3 hạn mức ngày/tháng/lá chắn, cổng khách
- [ ] Task 4 /han-muc v2, /ho-so, /nang-goi, /hoi-thoai/nhap
- [ ] Task 5 FE khách + hạn mức + thanh đo
- [ ] Task 6 TaiKhoanProvider + AppShell ChatGPT
- [ ] Task 7 /dung-thu: khách, trần phiên, 429, hết hạn
- [ ] Task 8 /tai-khoan, cá nhân hoá, bỏ Vai trò
- [ ] Task 9 ModalNangGoi + bảng giá
- [ ] Task 10 soạn thảo: khách → đăng nhập
- [ ] Task 11 gộp, kiểm, Chrome, đóng

## Decisions

(ghi khi có)

## Result

(điền ở Task 11)
```

- [ ] **Step 2: Test đỏ** `tests/test_api/test_han_muc_yaml.py`

```python
"""`config/han_muc.yaml` v3 + gói hiệu lực (spec 2026-09-07 §4.1, §5)."""

from datetime import UTC, datetime, timedelta

import pytest

from src.services import bao_ve

YAML_OK = (
    "goi_mac_dinh: free\nmui_gio: Asia/Ho_Chi_Minh\n"
    "goi:\n  free: {hoi_dap_ngay: 200, soan_thao_ngay: 3, soan_thao_thang: 20, luot_moi_phien: 20}\n"
    "  pro: {hoi_dap_ngay: 100000, soan_thao_ngay: 20, soan_thao_thang: 100000, luot_moi_phien: 50}\n"
    "la_chan: {free_hoi_dap_thang: 2000, pro_hoi_dap_ngay: 500, ip_ngay: 400}\n"
    "khach: {hoi_dap_24h: 10, ip_24h: 30}\nchu_ky_pro_ngay: 30\n"
)


@pytest.fixture
def yaml_tam(tmp_path, monkeypatch):
    def _dat(noi_dung: str):
        f = tmp_path / "han_muc.yaml"
        f.write_text(noi_dung, encoding="utf-8")
        monkeypatch.setattr(bao_ve, "HAN_MUC_PATH", f)
        bao_ve._doc_han_muc.cache_clear()

    yield _dat
    bao_ve._doc_han_muc.cache_clear()


def test_yaml_that_doc_duoc_va_dung_so():
    bao_ve._doc_han_muc.cache_clear()
    assert bao_ve.han_muc("free", "hoi_dap_ngay") == 200
    assert bao_ve.han_muc("free", "luot_moi_phien") == 20
    assert bao_ve.han_muc("pro", "hoi_dap_ngay") >= 100_000
    assert bao_ve.han_muc("goi-la", "soan_thao_ngay") == bao_ve.han_muc("free", "soan_thao_ngay")
    assert bao_ve.la_chan("ip_ngay") == 400
    assert str(bao_ve.mui_gio()) == "Asia/Ho_Chi_Minh"
    with pytest.raises(KeyError):
        bao_ve.han_muc("free", "khoa-la")


@pytest.mark.parametrize(
    "hong, khop",
    [
        (YAML_OK.replace("chu_ky_pro_ngay: 30\n", ""), "chu_ky_pro_ngay"),
        (YAML_OK.replace("mui_gio: Asia/Ho_Chi_Minh\n", "mui_gio: Sao/Hoa\n"), "mui_gio"),
        (YAML_OK.replace(", luot_moi_phien: 20}", "}"), "luot_moi_phien"),
        (YAML_OK.replace("la_chan: {free_hoi_dap_thang: 2000, ", "la_chan: {"), "free_hoi_dap_thang"),
        (YAML_OK + "phien_luu: {free: 10}\n", "phien_luu"),
    ],
)
def test_yaml_hong_thi_fail_loud(yaml_tam, hong, khop):
    yaml_tam(hong)
    with pytest.raises(ValueError, match=khop):
        bao_ve._doc_han_muc()


def test_moc_ngay_thang_theo_gio_viet_nam():
    # 23:30 UTC ngày 7 = 06:30 ngày 8 giờ VN → mốc ngày là 00:00 ngày 8 (+07:00)
    luc = datetime(2026, 9, 7, 23, 30, tzinfo=UTC)
    assert bao_ve.moc_ngay(luc).isoformat() == "2026-09-08T00:00:00+07:00"
    assert bao_ve.moc_ngay_sau(luc).isoformat() == "2026-09-09T00:00:00+07:00"
    assert bao_ve.moc_thang(luc).isoformat() == "2026-09-01T00:00:00+07:00"
    assert bao_ve.moc_thang_sau(luc).isoformat() == "2026-10-01T00:00:00+07:00"


def test_plan_hieu_luc_tu_het_han():
    assert bao_ve.plan_hieu_luc_tu("pro", None) == "pro"
    assert bao_ve.plan_hieu_luc_tu("pro", datetime.now(UTC) + timedelta(days=1)) == "pro"
    assert bao_ve.plan_hieu_luc_tu("pro", datetime.now(UTC) - timedelta(seconds=1)) == "free"
    assert bao_ve.plan_hieu_luc_tu("free", None) == "free"
```

- [ ] **Step 3: Đỏ** — `.venv/bin/python -m pytest tests/test_api/test_han_muc_yaml.py -q` → AttributeError (`han_muc`, `la_chan`, `moc_ngay`…).

- [ ] **Step 4: `config/han_muc.yaml`** — thay toàn bộ nội dung:

```yaml
# Hạn mức theo gói (spec 2026-09-07 vo-ung-dung-va-tai-khoan §4). Đây là DỮ LIỆU,
# không phải code: đổi số là đổi file này. Quy ước: 0 = không cho lượt nào (nghĩa
# đen, không phải "không giới hạn"); "không giới hạn" = một số lớn (>= 100000).
#
# Đếm bằng SỐ LƯỢT gọi LLM thật của tài khoản trên `traces`: không tính lượt trả
# lời từ bộ đệm (cache_hit), câu ngoài phạm vi (out_of_scope) và lượt lỗi (loi).
# Tra cứu văn bản, soát văn bản, biểu mẫu không bao giờ tính.

goi_mac_dinh: free
# Mốc "ngày" và "tháng" tính theo múi giờ này, không theo UTC.
mui_gio: Asia/Ho_Chi_Minh

goi:
  free:
    hoi_dap_ngay: 200
    soan_thao_ngay: 3
    soan_thao_thang: 20
    luot_moi_phien: 20
  pro:
    hoi_dap_ngay: 100000
    soan_thao_ngay: 20
    soan_thao_thang: 100000
    luot_moi_phien: 50

# Lá chắn chống lạm dụng: cưỡng chế với 429 nói thật, nhưng KHÔNG hiện thanh đo
# (người thật không chạm; đây không phải lời hứa bán hàng).
la_chan:
  free_hoi_dap_thang: 2000
  pro_hoi_dap_ngay: 500
  ip_ngay: 400

# Khách chưa đăng nhập (chỉ khi Supabase đã cấu hình): cửa sổ 24 giờ trượt, vì
# khách không có mốc "ngày" nào gắn với tài khoản.
khach:
  hoi_dap_24h: 10
  ip_24h: 30

# Chu kỳ gói trả phí, tính từ lúc duyệt yêu cầu.
chu_ky_pro_ngay: 30
```

- [ ] **Step 5: `src/services/bao_ve.py`** — import thêm `import uuid` và `from zoneinfo import ZoneInfo, ZoneInfoNotFoundError`. Thay `_doc_han_muc` và thêm các hàm mới ngay sau nó:

```python
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
```

Shim tạm (Task 2–3 sẽ gỡ) — thay thân hai hàm cũ:

```python
def han_muc_thang(plan: str) -> int:
    """Tương thích tạm cho Task 2–3: lá chắn tháng của free; "không giới hạn" của pro."""
    return la_chan("free_hoi_dap_thang") if plan == "free" else 100_000


def phien_luu_toi_da(plan: str) -> int:
    """Tương thích tạm: cơ chế ẩn phiên bị gỡ ở Task 2 — không bao giờ ẩn."""
    return 100_000
```

`_SQL_UPSERT_USER`: `RETURNING plan` → `RETURNING plan, plan_het_han`. `ghi_nhan_nguoi_dung`:

```python
def ghi_nhan_nguoi_dung(sub: str, email: str | None) -> str:
    """Upsert dòng `users` và trả gói HIỆU LỰC (đã xét `plan_het_han`). CÓ THỂ RAISE."""
    with get_engine().begin() as c:
        r = c.execute(_SQL_UPSERT_USER, {"sub": sub, "email": email}).mappings().one()
    return plan_hieu_luc_tu(str(r["plan"]), r["plan_het_han"])
```

`plan_cua(sub)` giữ tên, thân trở thành `return plan_hieu_luc(sub)` (Task 2 xoá hẳn).

- [ ] **Step 6: Migration** `migrations/021_nang_goi.sql`

```sql
-- Spec 2026-09-07 vo-ung-dung-va-tai-khoan §5 — yêu cầu nâng/gia hạn gói và chu kỳ
-- gói trả phí. Duyệt (gói 2B; tạm SQL tay): UPDATE users SET plan='pro',
-- plan_het_han = greatest(now(), coalesce(plan_het_han, now())) + interval '30 days'.
CREATE TABLE IF NOT EXISTS yeu_cau_nang_goi (
    id           BIGSERIAL PRIMARY KEY,
    user_sub     UUID NOT NULL REFERENCES users(sub) ON DELETE CASCADE,
    loai         TEXT NOT NULL CHECK (loai IN ('nang_goi', 'gia_han')),
    goi_hien_tai TEXT NOT NULL,
    goi_muon     TEXT NOT NULL,
    trang_thai   TEXT NOT NULL DEFAULT 'cho_duyet'
                 CHECK (trang_thai IN ('cho_duyet', 'da_duyet', 'tu_choi')),
    tao_luc      TIMESTAMPTZ NOT NULL DEFAULT now(),
    xu_ly_luc    TIMESTAMPTZ,
    xu_ly_boi    UUID
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_yeu_cau_nang_goi_cho_duyet
    ON yeu_cau_nang_goi(user_sub) WHERE trang_thai = 'cho_duyet';

-- Chu kỳ gói trả phí: NULL = không hết hạn (free, hoặc pro cấp tay vô thời hạn).
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_het_han TIMESTAMPTZ;
```

Áp DB local: `.venv/bin/python -c "from src.services.db import run_migrations; print(run_migrations('021'))"`. `src/main.py:53`: `for mig in ("019", "020", "021"):`; cập nhật kỳ vọng trong `tests/test_api/test_guard_khoi_dong.py` thành `["019", "020", "021"]`.

- [ ] **Step 7: `src/models/schemas.py`** — thay `HanMucResponse` (dòng ~739) và `DanhSachPhienResponse` (~773); thêm các model sau ở CUỐI file (vì `LuotNhap` tham chiếu `TraCuuResponse`):

```python
class MucHanMuc(BaseModel):
    khoa: str
    nhan: str
    da_dung: int
    han_muc: int  # >= 100000 nghĩa là không giới hạn
    dat_lai_luc: datetime | None


class PhienHanMuc(BaseModel):
    luot_toi_da: int | None


class HanMucResponse(BaseModel):
    """Hạn mức của người gọi (spec 2026-09-07 §6.1). `ap_dung=False` khi Supabase chưa
    cấu hình: không đếm theo ai, `muc` rỗng — không bịa số 0."""

    ap_dung: bool
    plan: str | None
    ten_goi: str | None
    mui_gio: str
    muc: list[MucHanMuc]
    phien: PhienHanMuc
    het_han_luc: datetime | None
    ghi_chu: str


class HoatDongNgay(BaseModel):
    ngay: date
    so_luot: int


class PhanLoai(BaseModel):
    khoa: str
    nhan: str
    so: int


class HoSoResponse(BaseModel):
    email: str | None
    plan: str
    ten_goi: str
    tao_luc: datetime
    het_han_luc: datetime | None
    so_phien: int
    tong_hoi_dap: int
    tong_ban_thao: int
    hoat_dong: list[HoatDongNgay]
    phan_loai: list[PhanLoai]


class YeuCauNangGoiRequest(BaseModel):
    goi_muon: str = Field(..., min_length=1, max_length=32)


class YeuCauNangGoiOut(BaseModel):
    id: int
    loai: str
    goi_hien_tai: str
    goi_muon: str
    trang_thai: str
    tao_luc: datetime
    xu_ly_luc: datetime | None


class LuotNhap(BaseModel):
    cau_hoi: str = Field(..., min_length=1, max_length=2000)
    tra_loi: TraCuuResponse
    trace_id: str | None = None


class NhapPhienRequest(BaseModel):
    luot: list[LuotNhap] = Field(..., min_length=1, max_length=10)


class NhapPhienResponse(BaseModel):
    id: str


class DanhSachPhienResponse(BaseModel):
    plan: str
    luot_moi_phien: int
    tong: int
    items: list[PhienTomTatOut]
```

(Xoá định nghĩa `HanMucResponse` và `DanhSachPhienResponse` cũ ở vị trí cũ.)

- [ ] **Step 8: Frontend kiểu** — `frontend/src/lib/klaw.ts`: thay `HanMuc` (~506) và `laHanMuc` (~937), `DanhSachPhien` (~696) và `laDanhSachPhien` (~862); thêm `HoSo`, `YeuCauNangGoi` và guard:

```ts
export interface MucHanMuc {
  khoa: string;
  nhan: string;
  da_dung: number;
  han_muc: number;
  dat_lai_luc: string | null;
}

export interface HanMuc {
  ap_dung: boolean;
  plan: string | null;
  ten_goi: string | null;
  mui_gio: string;
  muc: MucHanMuc[];
  phien: { luot_toi_da: number | null };
  het_han_luc: string | null;
  ghi_chu: string;
}

export interface DanhSachPhien {
  plan: string;
  luot_moi_phien: number;
  tong: number;
  items: PhienTomTat[];
}

export interface HoSo {
  email: string | null;
  plan: string;
  ten_goi: string;
  tao_luc: string;
  het_han_luc: string | null;
  so_phien: number;
  tong_hoi_dap: number;
  tong_ban_thao: number;
  hoat_dong: { ngay: string; so_luot: number }[];
  phan_loai: { khoa: string; nhan: string; so: number }[];
}

export interface YeuCauNangGoi {
  id: number;
  loai: "nang_goi" | "gia_han";
  goi_hien_tai: string;
  goi_muon: string;
  trang_thai: "cho_duyet" | "da_duyet" | "tu_choi";
  tao_luc: string;
  xu_ly_luc: string | null;
}

export function laHanMuc(x: unknown): x is HanMuc {
  return (
    laBanGhi(x) && typeof x["ap_dung"] === "boolean" && Array.isArray(x["muc"]) && laBanGhi(x["phien"])
  );
}
export function laDanhSachPhien(x: unknown): x is DanhSachPhien {
  return laBanGhi(x) && Array.isArray(x["items"]) && typeof x["luot_moi_phien"] === "number";
}
export function laHoSo(x: unknown): x is HoSo {
  return (
    laBanGhi(x) && Array.isArray(x["hoat_dong"]) && Array.isArray(x["phan_loai"]) && typeof x["plan"] === "string"
  );
}
export function laYeuCauNangGoi(x: unknown): x is YeuCauNangGoi {
  return laBanGhi(x) && typeof x["id"] === "number" && typeof x["trang_thai"] === "string";
}
export function laYeuCauNangGoiHoacNull(x: unknown): x is YeuCauNangGoi | null {
  return x === null || laYeuCauNangGoi(x);
}
export function laNhapPhien(x: unknown): x is { id: string } {
  return laBanGhi(x) && typeof x["id"] === "string";
}
```

`frontend/src/lib/khach.ts` (mới):

```ts
/** Mã khách cho người chưa đăng nhập (spec 2026-09-07 §8.1). KHÔNG phải danh tính:
 *  máy chủ chỉ dùng nó làm khoá đếm 10 lượt/24 giờ. Sống trong localStorage để tải
 *  lại trang không được thêm lượt; đoạn chat thì KHÔNG lưu (state trang). */
export const KHACH_HEADER = "X-Khach-Id";
const KHOA = "klaw.khach_id";

export function layKhachId(): string {
  try {
    const cu = localStorage.getItem(KHOA);
    if (cu !== null && cu !== "") return cu;
    const moi = crypto.randomUUID();
    localStorage.setItem(KHOA, moi);
    return moi;
  } catch {
    return crypto.randomUUID(); // không có localStorage: mã tạm cho tab này
  }
}
```

`frontend/src/lib/api.ts` `tieuDeXacThuc` (dòng ~70): khi không có token (cả nhánh không session và nhánh `catch`) trả `{ [KHACH_HEADER]: layKhachId() }` thay `{}` (import từ `./khach`). `goi` và `traCuuLuong` đều đi qua hàm này. `frontend/src/routes/bang-gia.tsx`: xoá import `HanMucThang` (dòng 5) và dòng render `<HanMucThang …/>` (~199); xoá file `HanMucThang.tsx` (Task 9 đặt `ThuocMucDung` vào chỗ đó).

- [ ] **Step 9: Xanh**

```bash
.venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check src/services/bao_ve.py src/models/schemas.py tests/test_api/test_han_muc_yaml.py && .venv/bin/python -m pytest tests/test_api/test_han_muc_yaml.py tests/test_api/test_guard_khoi_dong.py tests/test_api/test_hoi_thoai.py tests/test_api/test_tra_cuu_phien.py tests/test_services/test_hoi_thoai.py -q
cd frontend && npm run typecheck && npm run lint && npm run kiem-sse && npm run kiem-phien
```

Kỳ vọng: xanh. `tests/test_api/test_tai_khoan.py` và các test `han_muc_thang`/`phien_luu` trong `test_xac_thuc_han_muc.py`, `test_hoi_thoai.py` (`gioi_han/tong_an`) sẽ đỏ cho tới Task 2–4 — chạy chúng, ghi số đỏ vào report, KHÔNG sửa ở đây (Task 2–4 viết lại). Riêng `test_hoi_thoai.py` test `gioi_han == 10` và `tong_an` đỏ ngay: chấp nhận đỏ tạm, ghi rõ.

- [ ] **Step 10: Commit**

```bash
git add config/han_muc.yaml migrations/021_nang_goi.sql src/services/bao_ve.py src/models/schemas.py src/main.py tests/test_api/test_han_muc_yaml.py tests/test_api/test_guard_khoi_dong.py frontend/src/lib/klaw.ts frontend/src/lib/api.ts frontend/src/lib/khach.ts frontend/src/routes/bang-gia.tsx docs/plans/active/vo-ung-dung-va-tai-khoan.md
git rm -q tests/test_api/test_han_muc_phien.py frontend/src/components/klaw/HanMucThang.tsx
git commit -m "feat(api): quota config v3, effective plan with expiry, migration 021, guest header and v2 contracts

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Step 11: Worktree**

```bash
git worktree add ../KLAW-be4 -b wt-be-tk && git worktree add ../KLAW-fe4 -b wt-fe-tk
for w in ../KLAW-be4 ../KLAW-fe4; do ln -s "$PWD/.venv" "$w/.venv"; ln -s "$PWD/.env.local" "$w/.env.local"; mkdir -p "$w/data" && ln -s "$PWD/data/raw" "$w/data/raw"; done
ln -s "$PWD/frontend/node_modules" ../KLAW-fe4/frontend/node_modules
(cd ../KLAW-be4 && .venv/bin/python -c "import src.config; print('be4 ok')") && (cd ../KLAW-fe4/frontend && npm run typecheck && echo fe4 ok)
```

---

# BƯỚC 1 — BACKEND (worktree `../KLAW-be4`, nhánh `wt-be-tk`)

Mọi lệnh chạy từ gốc worktree với `.venv/bin/python` / `.venv/bin/ruff`. Migration 021 đã áp lên DB local ở Task 1.

### Task 2: Gỡ cơ chế ẩn phiên, trần lượt mỗi phiên, `nhap_phien`

**Files:**
- Modify: `src/services/hoi_thoai.py`, `src/api/routes.py` (`_chuan_bi_phien`), `src/api/routes_hoi_thoai.py`, `src/services/bao_ve.py` (xoá `phien_luu_toi_da`, `plan_cua`)
- Test: `tests/test_services/test_hoi_thoai.py`, `tests/test_api/test_hoi_thoai.py`, `tests/test_api/test_tra_cuu_phien.py` (sửa)

**Interfaces:**
- Consumes: `bao_ve.han_muc(plan, "luot_moi_phien")`, `bao_ve.plan_hieu_luc(sub)`, `DanhSachPhienResponse{plan, luot_moi_phien, tong, items}` (Task 1).
- Produces: `hoi_thoai.LOI_PHIEN_DAY = "Phiên này đã đủ {n} lượt. Mở phiên mới để tiếp tục."`; `hoi_thoai.dem_luot(id: str) -> int`; `hoi_thoai.danh_sach(sub, limit, offset) -> tuple[list[dict], int]` (items, tong); `hoi_thoai.nhap_phien(sub, luot: list[dict]) -> str` (mỗi dict `{cau_hoi, tra_loi: dict, trace_id}`); `routes._chuan_bi_phien` 403 khi đủ trần; router `/hoi-thoai` không còn 403 ẩn.

- [ ] **Step 1: Sửa test thành đỏ**

`tests/test_services/test_hoi_thoai.py`: xoá `test_free_giu_N_phien_gan_nhat_va_xoa_thi_hien_lai`; thêm:

```python
def test_danh_sach_khong_an_va_dem_luot(nguoi):
    ids = [hoi_thoai.tao_phien(nguoi, f"câu {i}") for i in range(3)]
    for pid in ids:
        hoi_thoai.ghi_luot(pid, "q", PAYLOAD, None)
    hoi_thoai.ghi_luot(ids[2], "q2", PAYLOAD, None)
    items, tong = hoi_thoai.danh_sach(nguoi, limit=20, offset=0)
    assert tong == 3 and [i["id"] for i in items] == list(reversed(ids))
    assert hoi_thoai.dem_luot(ids[2]) == 2 and hoi_thoai.dem_luot(ids[0]) == 1


def test_nhap_phien_tao_phien_va_ghi_dung_thu_tu(nguoi):
    pid = hoi_thoai.nhap_phien(
        nguoi,
        [
            {"cau_hoi": "Câu một?", "tra_loi": PAYLOAD, "trace_id": "t1"},
            {"cau_hoi": "Câu hai?", "tra_loi": PAYLOAD, "trace_id": None},
        ],
    )
    ct = hoi_thoai.chi_tiet(nguoi, pid)
    assert ct["tieu_de"] == "Câu một?"
    assert [(lu["thu_tu"], lu["cau_hoi"], lu["trace_id"]) for lu in ct["luot"]] == [
        (1, "Câu một?", "t1"),
        (2, "Câu hai?", None),
    ]
```

`tests/test_api/test_hoi_thoai.py`: assert dòng 43 thành `assert d["plan"] == "free" and d["luot_moi_phien"] == 20 and d["tong"] == 1`; thay `test_phien_an_theo_goi_403_va_tong_an` bằng:

```python
@pytest.mark.asyncio
async def test_khong_con_an_theo_goi_va_xoa_phien_bat_ky(client, khoa_ky, hai_nguoi):
    a, _ = hai_nguoi
    ids = [hoi_thoai.tao_phien(a, f"c{i}") for i in range(3)]
    d = (await client.get("/api/v1/hoi-thoai", headers=_bearer(khoa_ky, a))).json()
    assert d["tong"] == 3 and len(d["items"]) == 3
    assert (await client.get(f"/api/v1/hoi-thoai/{ids[0]}", headers=_bearer(khoa_ky, a))).status_code == 200
    assert (await client.delete(f"/api/v1/hoi-thoai/{ids[0]}", headers=_bearer(khoa_ky, a))).status_code == 204
```

`tests/test_api/test_tra_cuu_phien.py`: thay `test_phien_nguoi_khac_404_va_phien_an_403` bằng (giữ hằng `SUPABASE` đang có trong file):

```python
@pytest.mark.asyncio
async def test_phien_nguoi_khac_404_va_phien_day_403(client, cai_dat, khoa_ky, graph_gia_lap, don_dep, monkeypatch):
    cai_dat(supabase_url=SUPABASE)
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    don_dep.extend([a, b])
    bao_ve.ghi_nhan_nguoi_dung(a, None)
    pid = hoi_thoai.tao_phien(a, "của A")
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x", "hoi_thoai_id": pid}, headers=_bearer(khoa_ky, b))
    assert r.status_code == 404
    monkeypatch.setattr(bao_ve, "han_muc", lambda plan, khoa: 2 if khoa == "luot_moi_phien" else 100_000)
    for i in range(2):
        hoi_thoai.ghi_luot(pid, f"q{i}", {"result_type": "answer", "answer": "", "citations": []}, None)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x", "hoi_thoai_id": pid}, headers=_bearer(khoa_ky, a))
    assert r.status_code == 403 and "đã đủ 2 lượt" in r.json()["detail"]
```

- [ ] **Step 2: Đỏ** — `.venv/bin/python -m pytest tests/test_services/test_hoi_thoai.py tests/test_api/test_hoi_thoai.py tests/test_api/test_tra_cuu_phien.py -q`.

- [ ] **Step 3: `src/services/hoi_thoai.py`** — xoá `from src.services.bao_ve import phien_luu_toi_da`, `LOI_PHIEN_AN`, `_SQL_HANG`, `phien_bi_an`; sửa docstring module (bỏ câu về "ẩn"); thêm/sửa:

```python
LOI_PHIEN_DAY = "Phiên này đã đủ {n} lượt. Mở phiên mới để tiếp tục."

_SQL_DEM_LUOT = text("SELECT count(*)::int FROM luot_hoi_thoai WHERE hoi_thoai_id = :id")


def dem_luot(id: str) -> int:
    with get_engine().connect() as c:
        return int(c.execute(_SQL_DEM_LUOT, {"id": id}).scalar_one())


def danh_sach(sub: str, limit: int, offset: int) -> tuple[list[dict], int]:
    """Phiên còn sống của `sub`, mới nhất trước. Không còn ẩn theo gói (spec 2A §4.3)."""
    with get_engine().connect() as c:
        tong = int(c.execute(_SQL_DEM, {"sub": sub}).scalar_one())
        items = [
            dict(r)
            for r in c.execute(_SQL_DANH_SACH, {"sub": sub, "limit": limit, "offset": offset}).mappings().all()
        ]
    return items, tong


def nhap_phien(sub: str, luot: list[dict]) -> str:
    """Mang đoạn chat của khách vào tài khoản (spec 2A §8.4): một transaction, tiêu đề
    từ câu đầu, `thu_tu` theo thứ tự nhận. Không đụng `traces`."""
    with get_engine().begin() as c:
        pid = str(c.execute(_SQL_TAO, {"sub": sub, "tieu_de": tieu_de_mac_dinh(luot[0]["cau_hoi"])}).scalar_one())
        for lu in luot:
            c.execute(
                _SQL_GHI,
                {
                    "id": pid,
                    "cau_hoi": lu["cau_hoi"],
                    "tra_loi": json.dumps(lu["tra_loi"], ensure_ascii=False),
                    "trace_id": lu.get("trace_id"),
                },
            )
        c.execute(_SQL_CHAM, {"id": pid})
    return pid
```

- [ ] **Step 4: `src/api/routes.py` `_chuan_bi_phien`** — thay hai dòng `plan_cua`/`phien_bi_an` bằng:

```python
    plan = await run_in_threadpool(plan_hieu_luc, user_sub)
    tran = han_muc(plan, "luot_moi_phien")
    if await run_in_threadpool(hoi_thoai_svc.dem_luot, pid) >= tran:
        raise HTTPException(status_code=403, detail=hoi_thoai_svc.LOI_PHIEN_DAY.format(n=tran))
```

Import `han_muc, plan_hieu_luc` từ `src.services.bao_ve` (bỏ `plan_cua`). Docstring: bỏ "kiểm ẩn theo gói (403)", thêm "đủ trần lượt của gói → 403".

- [ ] **Step 5: `src/api/routes_hoi_thoai.py`** — `_phien_mo_duoc` chỉ còn kiểm 404; import `han_muc, nguoi_dung_bat_buoc, plan_hieu_luc`; `danh_sach`:

```python
    sub = nguoi["sub"]
    plan = await run_in_threadpool(plan_hieu_luc, sub)
    items, tong = await run_in_threadpool(hoi_thoai.danh_sach, sub, limit, offset)
    return DanhSachPhienResponse(
        plan=plan,
        luot_moi_phien=han_muc(plan, "luot_moi_phien"),
        tong=tong,
        items=[PhienTomTatOut(**i) for i in items],
    )
```

Docstring module: bỏ "phiên ẩn theo gói là 403". `src/services/bao_ve.py`: xoá `phien_luu_toi_da`, `plan_cua`, `_SQL_PLAN_CUA`. Kiểm `grep -rn "phien_luu_toi_da\|plan_cua\|phien_bi_an\|LOI_PHIEN_AN" src tests` rỗng.

- [ ] **Step 6: Xanh**

```bash
.venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check src/services/hoi_thoai.py src/api/routes_hoi_thoai.py && .venv/bin/python -m pytest tests/test_services/test_hoi_thoai.py tests/test_api/test_hoi_thoai.py tests/test_api/test_tra_cuu_phien.py tests/test_api/test_han_muc_yaml.py -q
```

- [ ] **Step 7: Commit**

```bash
git add src/services/hoi_thoai.py src/api/routes.py src/api/routes_hoi_thoai.py src/services/bao_ve.py tests/test_services/test_hoi_thoai.py tests/test_api/test_hoi_thoai.py tests/test_api/test_tra_cuu_phien.py
git commit -m "feat(hoi-thoai): drop plan-based hiding, cap turns per session, import guest thread

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Hạn mức ngày/tháng/lá chắn, `kiem_rate_limit` theo khoá, cổng khách

**Files:**
- Modify: `src/services/bao_ve.py` (`_SQL_DON_LUOT`, `_SQL_LUOT_CU_NHAT`, `kiem_rate_limit`, `dem_luot`, `kiem_han_muc`, `mo_ta_muc`, `dem_cua_so`, `het_han_cua`, `ten_goi`, `xac_thuc_nguoi_goi_hoac_none`, `_cong`/`cong_bao_ve`/`cong_bao_ve_khach`; xoá `han_muc_thang`, `dem_luot_thang`, `kiem_han_muc_thang`, `_dau_thang_utc`, `_dau_thang_sau_utc`, `_SQL_DEM_LUOT_THANG`), `src/api/routes.py:433`, `src/api/routes_luong.py:188`, `src/api/routes_tai_khoan.py` (import + thân `/han-muc` tối thiểu để chạy; Task 4 viết lại)
- Test: `tests/test_api/test_han_muc_ngay.py` (mới), `tests/test_api/test_khach.py` (mới), sửa `tests/test_api/test_xac_thuc_han_muc.py`, `tests/test_api/test_han_muc_dua.py`, `tests/test_api/test_tai_khoan.py` (fixture)

**Interfaces:**
- Consumes: Task 1 `han_muc`, `la_chan`, `moc_*`, `plan_hieu_luc_tu`, `khach_id_tu_request`, `KHACH_HEADER`, `mui_gio`.
- Produces: `bao_ve.kiem_rate_limit(khoa: str, so_luot: int | None = None, cua_so_giay: int | None = None) -> None`; `bao_ve.dem_luot(sub, endpoint, tu_luc: datetime) -> int`; `bao_ve.kiem_han_muc(sub, plan, endpoint) -> None`; `bao_ve.mo_ta_muc(sub, plan) -> list[dict]` (`[{khoa, nhan, da_dung, han_muc, dat_lai_luc}]`, chỉ ba khoá `goi`); `bao_ve.dem_cua_so(khoa, cua_so_giay) -> tuple[int, datetime | None]`; `bao_ve.het_han_cua(sub) -> datetime | None`; `bao_ve.ten_goi(plan) -> str` ("Miễn phí"/"Cá nhân"/mã); `bao_ve.xac_thuc_nguoi_goi_hoac_none(request) -> dict | None`; `bao_ve.cong_bao_ve` (không cho khách) và `bao_ve.cong_bao_ve_khach` (cho khách); `bao_ve.LOI_KHACH_DANG_NHAP = "Cần đăng nhập để dùng tính năng này."`; `bao_ve.LOI_SOAN_THAO_DANG_NHAP = "Cần đăng nhập để soạn văn bản."`; `bao_ve.NHAN_MUC`.

- [ ] **Step 1: Test đỏ** `tests/test_api/test_han_muc_ngay.py`

```python
"""Hạn mức ngày/tháng/lá chắn trên `traces` theo giờ VN (spec 2A §4.2)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from src.services import bao_ve
from src.services.db import get_engine

pytestmark = pytest.mark.integration
TRA_CUU, SOAN_THAO = "/api/v1/tra-cuu", "/api/v1/soan-thao"


@pytest.fixture
def nguoi():
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, None)
    yield sub
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM traces WHERE user_sub = :s"), {"s": sub})
        c.execute(text("DELETE FROM users WHERE sub = :s"), {"s": sub})


def _ghi(sub, endpoint, ts, result_type="answer", cache_hit=False):
    with get_engine().begin() as c:
        c.execute(
            text(
                "INSERT INTO traces (id, ts, endpoint, config_name, result_type, cache_hit, user_sub)"
                " VALUES (:id, :ts, :ep, 'full', :rt, :ch, :sub)"
            ),
            {"id": str(uuid.uuid4()), "ts": ts, "ep": endpoint, "rt": result_type, "ch": cache_hit, "sub": sub},
        )


def test_dem_luot_loai_cache_loi_ngoai_pham_vi_va_NULL_van_dem(nguoi):
    now = datetime.now(UTC)
    _ghi(nguoi, TRA_CUU, now)
    _ghi(nguoi, TRA_CUU, now, cache_hit=True)
    _ghi(nguoi, TRA_CUU, now, result_type="loi")
    _ghi(nguoi, TRA_CUU, now, result_type="out_of_scope")
    _ghi(nguoi, SOAN_THAO, now, result_type=None)
    assert bao_ve.dem_luot(nguoi, TRA_CUU, bao_ve.moc_ngay(now)) == 1
    assert bao_ve.dem_luot(nguoi, SOAN_THAO, bao_ve.moc_ngay(now)) == 1


def test_moc_ngay_theo_VN_khong_theo_UTC(nguoi):
    moc = bao_ve.moc_ngay()
    _ghi(nguoi, TRA_CUU, (moc + timedelta(hours=3)).astimezone(UTC))  # 03:00 hôm nay giờ VN
    _ghi(nguoi, TRA_CUU, (moc - timedelta(minutes=1)).astimezone(UTC))  # hôm qua giờ VN
    assert bao_ve.dem_luot(nguoi, TRA_CUU, moc) == 1


def test_kiem_han_muc_ngay_truoc_la_chan_thang(nguoi, monkeypatch):
    monkeypatch.setattr(bao_ve, "han_muc", lambda plan, khoa: 2 if khoa == "hoi_dap_ngay" else 100_000)
    monkeypatch.setattr(bao_ve, "la_chan", lambda khoa: 3 if khoa == "free_hoi_dap_thang" else 100_000)
    now = datetime.now(UTC)
    _ghi(nguoi, TRA_CUU, now)
    _ghi(nguoi, TRA_CUU, now)
    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_han_muc(nguoi, "free", TRA_CUU)
    assert e.value.status_code == 429 and "2/2 lượt hỏi đáp" in e.value.detail and "Hôm nay" in e.value.detail
    assert int(e.value.headers["Retry-After"]) > 0


def test_la_chan_thang_free_chan_khi_ngay_con(nguoi, monkeypatch):
    monkeypatch.setattr(bao_ve, "han_muc", lambda plan, khoa: 100_000)
    monkeypatch.setattr(bao_ve, "la_chan", lambda khoa: 1 if khoa == "free_hoi_dap_thang" else 100_000)
    _ghi(nguoi, TRA_CUU, datetime.now(UTC))
    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_han_muc(nguoi, "free", TRA_CUU)
    assert e.value.status_code == 429 and "Tháng này" in e.value.detail


def test_soan_thao_kiem_ngay_roi_thang(nguoi, monkeypatch):
    monkeypatch.setattr(
        bao_ve, "han_muc", lambda plan, khoa: {"soan_thao_ngay": 5, "soan_thao_thang": 1}.get(khoa, 100_000)
    )
    _ghi(nguoi, SOAN_THAO, datetime.now(UTC), result_type=None)
    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_han_muc(nguoi, "free", SOAN_THAO)
    assert e.value.status_code == 429 and "bản thảo" in e.value.detail


def test_pro_khong_gioi_han_ngay_nhung_co_la_chan(nguoi, monkeypatch):
    monkeypatch.setattr(bao_ve, "la_chan", lambda khoa: 1 if khoa == "pro_hoi_dap_ngay" else 100_000)
    _ghi(nguoi, TRA_CUU, datetime.now(UTC))
    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_han_muc(nguoi, "pro", TRA_CUU)
    assert e.value.status_code == 429 and "Cá nhân" in e.value.detail


def test_mo_ta_muc_ba_dong_khong_gom_la_chan(nguoi):
    muc = bao_ve.mo_ta_muc(nguoi, "free")
    assert [m["khoa"] for m in muc] == ["hoi_dap_ngay", "soan_thao_ngay", "soan_thao_thang"]
    assert all(m["dat_lai_luc"] is not None for m in muc) and muc[0]["han_muc"] == 200
```

`tests/test_api/test_khach.py` (dùng hằng issuer `_URL` của `test_xac_thuc_han_muc` nếu `SUPABASE` khác):

```python
"""Chế độ khách (spec 2A §8): X-Khach-Id, 10 lượt/24h, soạn thảo cần đăng nhập."""

import uuid

import pytest

from src.services import bao_ve
from tests.test_api.test_tra_cuu_phien import SUPABASE


@pytest.fixture
def ghi_lai_rate_limit(monkeypatch):
    goi: list[tuple] = []

    def gia(khoa, so_luot=None, cua_so_giay=None):
        goi.append((khoa, so_luot, cua_so_giay))

    monkeypatch.setattr(bao_ve, "kiem_rate_limit", gia)
    monkeypatch.setattr(bao_ve, "kiem_tran_chi_phi", lambda: None)
    return goi


@pytest.mark.asyncio
async def test_khach_khong_header_401(client, cai_dat, graph_gia_lap):
    cai_dat(supabase_url=SUPABASE)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"})
    assert r.status_code == 401 and r.json()["detail"] == bao_ve.LOI_KHACH_DANG_NHAP


@pytest.mark.asyncio
async def test_khach_co_header_duoc_hoi_va_dem_dung_khoa(client, cai_dat, graph_gia_lap, ghi_lai_rate_limit):
    cai_dat(supabase_url=SUPABASE)
    kid = str(uuid.uuid4())
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"}, headers={"X-Khach-Id": kid})
    assert r.status_code == 200
    assert (f"khach:{kid}", 10, 86400) in ghi_lai_rate_limit
    khoa = [g[0] for g in ghi_lai_rate_limit]
    assert any(k.startswith("khach-ip:") for k in khoa) and any(k.startswith("ip-ngay:") for k in khoa)


@pytest.mark.asyncio
async def test_khach_header_khong_phai_uuid_401(client, cai_dat, graph_gia_lap):
    cai_dat(supabase_url=SUPABASE)
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"}, headers={"X-Khach-Id": "abc"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_khach_soan_thao_401(client, cai_dat, ghi_lai_rate_limit):
    cai_dat(supabase_url=SUPABASE)
    # Body lấy từ một test /soan-thao hiện có (tests/test_api/test_soan_thao*.py) — dependency chạy
    # sau khi parse body nên body phải hợp lệ.
    body = {"loai": "don_xin_nghi_viec", "du_lieu": {}}
    r = await client.post("/api/v1/soan-thao", json=body, headers={"X-Khach-Id": str(uuid.uuid4())})
    assert r.status_code == 401 and r.json()["detail"] == bao_ve.LOI_SOAN_THAO_DANG_NHAP


@pytest.mark.asyncio
async def test_chua_cau_hinh_supabase_khong_dem_khach(client, cai_dat, graph_gia_lap, ghi_lai_rate_limit):
    cai_dat(supabase_url="")
    r = await client.post("/api/v1/tra-cuu/luong", json={"query": "x"})
    assert r.status_code == 200
    assert not any(k.startswith("khach") or k.startswith("ip-ngay") for k, *_ in ghi_lai_rate_limit)


@pytest.mark.integration
def test_kiem_rate_limit_hai_cua_so_khong_don_nhau():
    """Giỏ 60 giây KHÔNG được xoá hàng của giỏ 24 giờ (dọn theo khoá)."""
    from fastapi import HTTPException

    k = f"test:{uuid.uuid4()}"
    for _ in range(3):
        bao_ve.kiem_rate_limit(k, 10, 86400)
    bao_ve.kiem_rate_limit(f"khac:{uuid.uuid4()}", 10, 60)
    with pytest.raises(HTTPException) as e:
        bao_ve.kiem_rate_limit(k, 3, 86400)  # lượt thứ 4 với trần 3
    assert e.value.status_code == 429 and int(e.value.headers["Retry-After"]) <= 86400
```

- [ ] **Step 2: Đỏ** — chạy hai file → AttributeError / 401 sai chỗ.

- [ ] **Step 3: `bao_ve.py` — `kiem_rate_limit` theo khoá + cửa sổ**

```python
_SQL_DON_LUOT = text(
    "DELETE FROM rate_limit_luot WHERE ip = :khoa AND ts < now() - make_interval(secs => :cua_so)"
)
_SQL_LUOT_CU_NHAT = text(
    "SELECT min(ts) FROM rate_limit_luot WHERE ip = :khoa AND ts >= now() - make_interval(secs => :cua_so)"
)


def _cau_429_nhip(khoa: str, so_luot: int, cua_so: int, con: int) -> str:
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
    Dọn hàng cũ THEO KHOÁ: bảng nay chứa nhiều cửa sổ khác nhau, một câu dọn chung theo
    60 giây sẽ xoá dữ liệu của giỏ 24 giờ. `Retry-After` = giây tới khi lượt cũ nhất rời
    cửa sổ. Lỗi DB là TỪ CHỐI (503)."""
    s = get_settings()
    if s.rate_limit_so_luot <= 0:
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
```

(Giữ tên tham số `:ip` ở `_SQL_KHOA_IP`/`_SQL_GHI_LUOT`/`_SQL_DEM_LUOT`; cột `ip` nay chứa khoá bất kỳ — sửa chú thích cạnh bảng.) `kiem_tran_chi_phi` giữ nguyên.

- [ ] **Step 4: `bao_ve.py` — đếm và kiểm hạn mức mới; xoá hàm tháng cũ**

```python
_SQL_DEM_LUOT_TU = text(
    "SELECT count(*) FROM traces WHERE user_sub = :sub AND ts >= :moc AND NOT cache_hit"
    " AND endpoint = :ep AND (result_type IS NULL OR result_type NOT IN ('loi', 'out_of_scope'))"
)
_SQL_HET_HAN = text("SELECT plan_het_han FROM users WHERE sub = :sub")
NHAN_MUC = {
    "hoi_dap_ngay": "Hỏi đáp hôm nay",
    "soan_thao_ngay": "Bản thảo hôm nay",
    "soan_thao_thang": "Bản thảo tháng này",
}
LOI_KHACH_DANG_NHAP = "Cần đăng nhập để dùng tính năng này."
LOI_SOAN_THAO_DANG_NHAP = "Cần đăng nhập để soạn văn bản."
EP_TRA_CUU, EP_SOAN_THAO = "/api/v1/tra-cuu", "/api/v1/soan-thao"


def ten_goi(plan: str) -> str:
    return {"free": "Miễn phí", "pro": "Cá nhân"}.get(plan, plan)


def dem_luot(sub: str, endpoint: str, tu_luc: datetime) -> int:
    with get_engine().connect() as c:
        return int(c.execute(_SQL_DEM_LUOT_TU, {"sub": sub, "moc": tu_luc, "ep": endpoint}).scalar_one())


def het_han_cua(sub: str) -> datetime | None:
    with get_engine().connect() as c:
        return c.execute(_SQL_HET_HAN, {"sub": sub}).scalar_one_or_none()


def _cau_429(plan: str, da_dung: int, tran: int, loai: str, ky: str, mo_lai: datetime) -> str:
    luc = mo_lai.astimezone(mui_gio()).strftime("%H:%M ngày %d/%m")
    return f"{ky} bạn đã dùng {da_dung}/{tran} lượt {loai} của gói {ten_goi(plan)}. Mở lại lúc {luc}."


def _kiem_mot(sub: str, plan: str, endpoint: str, tran: int, moc: datetime, mo_lai: datetime, loai: str, ky: str) -> None:
    if tran >= 100_000:
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
    """Spec 2A §4.2. `/tra-cuu*` (cả `/luong`) kiểm ngày rồi lá chắn (tháng free / ngày pro);
    `/soan-thao` kiểm ngày rồi tháng. Trần >= 100000 = không giới hạn."""
    if endpoint.startswith(EP_TRA_CUU):
        _kiem_mot(sub, plan, EP_TRA_CUU, han_muc(plan, "hoi_dap_ngay"), moc_ngay(), moc_ngay_sau(), "hỏi đáp", "Hôm nay")
        if plan == "free":
            _kiem_mot(sub, plan, EP_TRA_CUU, la_chan("free_hoi_dap_thang"), moc_thang(), moc_thang_sau(), "hỏi đáp", "Tháng này")
        elif plan == "pro":
            _kiem_mot(sub, plan, EP_TRA_CUU, la_chan("pro_hoi_dap_ngay"), moc_ngay(), moc_ngay_sau(), "hỏi đáp", "Hôm nay")
    elif endpoint.startswith(EP_SOAN_THAO):
        _kiem_mot(sub, plan, EP_SOAN_THAO, han_muc(plan, "soan_thao_ngay"), moc_ngay(), moc_ngay_sau(), "bản thảo", "Hôm nay")
        _kiem_mot(sub, plan, EP_SOAN_THAO, han_muc(plan, "soan_thao_thang"), moc_thang(), moc_thang_sau(), "bản thảo", "Tháng này")


def mo_ta_muc(sub: str, plan: str) -> list[dict]:
    """Các thanh đo của `/han-muc` (chỉ khoá trong `goi`, không gồm lá chắn)."""
    ra = []
    for khoa, ep, moc, sau in (
        ("hoi_dap_ngay", EP_TRA_CUU, moc_ngay(), moc_ngay_sau()),
        ("soan_thao_ngay", EP_SOAN_THAO, moc_ngay(), moc_ngay_sau()),
        ("soan_thao_thang", EP_SOAN_THAO, moc_thang(), moc_thang_sau()),
    ):
        ra.append({"khoa": khoa, "nhan": NHAN_MUC[khoa], "da_dung": dem_luot(sub, ep, moc), "han_muc": han_muc(plan, khoa), "dat_lai_luc": sau})
    return ra
```

Xoá `han_muc_thang`, `dem_luot_thang`, `kiem_han_muc_thang`, `_dau_thang_utc`, `_dau_thang_sau_utc`, `_SQL_DEM_LUOT_THANG`, `ENDPOINT_TON_LLM` (nếu chỉ còn dùng ở đó — `grep` trước). `routes_tai_khoan.py`: đổi import sang `moc_thang_sau`, `han_muc`, `mo_ta_muc` và thân `/han-muc` tạm trả `HanMucResponse(ap_dung=True, plan=plan, ten_goi=ten_goi(plan), mui_gio=str(mui_gio()), muc=[MucHanMuc(**m) for m in mo_ta_muc(sub, plan)], phien=PhienHanMuc(luot_toi_da=han_muc(plan, "luot_moi_phien")), het_han_luc=None, ghi_chu=GHI_CHU_CACHE)` — Task 4 hoàn thiện (khách, `het_han_luc`).

- [ ] **Step 5: `bao_ve.py` — cổng hai biến thể**

Thêm cạnh `xac_thuc_nguoi_goi`:

```python
def xac_thuc_nguoi_goi_hoac_none(request: Request) -> dict | None:
    """Như `xac_thuc_nguoi_goi`, nhưng KHÔNG có header Authorization → None (đường khách).
    Token có mà sai/hết hạn vẫn 401 — không để một token hỏng rơi xuống đường khách."""
    if not xac_thuc.da_cau_hinh():
        return None
    if request.headers.get(xac_thuc.TEN_HEADER.lower()) is None:
        return None
    return xac_thuc_nguoi_goi(request)
```

Thay `async def cong_bao_ve(request)` bằng factory (chuyển docstring cũ về `_cong`, thêm đoạn về khách):

```python
def _cong(cho_khach: bool):
    async def cong(request: Request) -> str | None:
        kiem_api_key(request)
        ip = ip_goi(request)
        await run_in_threadpool(kiem_rate_limit, f"chan-ip:{ip}", get_settings().rate_limit_ip_so_luot)
        da_cau_hinh = xac_thuc.da_cau_hinh()
        if da_cau_hinh:
            await run_in_threadpool(kiem_rate_limit, f"ip-ngay:{ip}", la_chan("ip_ngay"), 86400)
        nguoi = await run_in_threadpool(xac_thuc_nguoi_goi_hoac_none, request)
        if nguoi is None and not da_cau_hinh:
            await run_in_threadpool(kiem_rate_limit, ip)
            await run_in_threadpool(kiem_tran_chi_phi)
            return None
        if nguoi is None:
            if not cho_khach:
                raise HTTPException(status_code=401, detail=LOI_SOAN_THAO_DANG_NHAP, headers={"WWW-Authenticate": "Bearer"})
            kid = khach_id_tu_request(request)
            if kid is None:
                raise HTTPException(status_code=401, detail=LOI_KHACH_DANG_NHAP, headers={"WWW-Authenticate": "Bearer"})
            k = _doc_han_muc()["khach"]
            await run_in_threadpool(kiem_rate_limit, f"khach:{kid}", int(k["hoi_dap_24h"]), 86400)
            await run_in_threadpool(kiem_rate_limit, f"khach-ip:{ip}", int(k["ip_24h"]), 86400)
            await run_in_threadpool(kiem_tran_chi_phi)
            return None
        sub = nguoi["sub"]
        await run_in_threadpool(kiem_rate_limit, f"user:{sub}")
        try:
            plan = await run_in_threadpool(ghi_nhan_nguoi_dung, sub, nguoi["email"])
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
```

`routes.py:433` (`/tra-cuu`) và `routes_luong.py:188` (`/tra-cuu/luong`) → `Depends(cong_bao_ve_khach)`; `/soan-thao` giữ `cong_bao_ve`. Cập nhật import ở hai file.

- [ ] **Step 6: Sửa test cũ**

`tests/test_api/test_xac_thuc_han_muc.py`: fixture `khong_dung_db` dòng 120 → `monkeypatch.setattr(bao_ve, "dem_luot", lambda sub, ep, moc: 0)`; test 256–300 dùng `YAML_OK` import từ `tests.test_api.test_han_muc_yaml` và kiểm `bao_ve.han_muc("free", "hoi_dap_ngay") == 200`, `han_muc("goi-khong-ton-tai", "hoi_dap_ngay") == 200`; `test_thong_diep_429_neu_ro_GOI_va_MOC_RESET`: monkeypatch `han_muc` → 50, `dem_luot` → 50, gọi `kiem_han_muc("s", "free", "/api/v1/tra-cuu")`, assert 429, "Miễn phí" và "Mở lại lúc" trong detail, `Retry-After` > 0; mọi `kiem_han_muc_thang(sub, plan)` → `kiem_han_muc(sub, plan, "/api/v1/tra-cuu")`; test 336 (`vuot_han_muc_chan_TRUOC_khi_graph_chay`) monkeypatch `dem_luot` thay `dem_luot_thang`. `tests/test_api/test_han_muc_dua.py`: `han_muc_thang` → `han_muc` (lambda plan, khoa), `kiem_han_muc_thang` → `kiem_han_muc(sub, "free", "/api/v1/tra-cuu")`. `tests/test_api/test_tai_khoan.py` fixture dòng 12 → `dem_luot`. Test hai người sau cùng IP (dòng 479) và các test khoá `chan-ip:` phải còn xanh.

- [ ] **Step 7: Xanh**

```bash
.venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check tests/test_api/test_han_muc_ngay.py tests/test_api/test_khach.py && .venv/bin/python -m pytest tests/test_api/test_han_muc_ngay.py tests/test_api/test_khach.py tests/test_api/test_xac_thuc_han_muc.py tests/test_api/test_han_muc_dua.py tests/test_api/test_thu_tu_cong.py tests/test_api/test_tra_cuu_phien.py tests/test_api/test_tra_cuu.py tests/test_api/test_tai_khoan.py -q
```

(`test_tai_khoan.py` có thể còn đỏ ở hình `/han-muc` — Task 4 sửa; ghi rõ trong report.)

- [ ] **Step 8: Commit**

```bash
git add src/services/bao_ve.py src/api/routes.py src/api/routes_luong.py src/api/routes_tai_khoan.py tests/test_api/test_han_muc_ngay.py tests/test_api/test_khach.py tests/test_api/test_xac_thuc_han_muc.py tests/test_api/test_han_muc_dua.py tests/test_api/test_tai_khoan.py
git commit -m "feat(api): day/month/shield quotas in VN time, per-key sliding windows, guest gate

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `/han-muc` v2, `/ho-so`, `/nang-goi/yeu-cau`, `POST /hoi-thoai/nhap`

**Files:**
- Create: `src/services/ho_so.py`, `src/services/nang_goi.py`, `tests/test_api/test_ho_so_nang_goi.py`
- Modify: `src/api/routes_tai_khoan.py` (viết lại `/han-muc`; thêm `/ho-so`, `/nang-goi/yeu-cau` GET/POST), `src/api/routes_hoi_thoai.py` (`POST /hoi-thoai/nhap`), `tests/test_api/test_tai_khoan.py`

**Interfaces:**
- Consumes: Task 1 models; Task 2 `hoi_thoai.nhap_phien`; Task 3 `mo_ta_muc`, `dem_cua_so`, `het_han_cua`, `ten_goi`, `xac_thuc_nguoi_goi_hoac_none`, `khach_id_tu_request`, `han_muc`, `mui_gio`, `plan_hieu_luc_tu`.
- Produces: `ho_so.tong_hop(sub) -> dict | None`; `nang_goi.tao_yeu_cau(sub, goi_muon) -> dict` raise `nang_goi.GoiKhongHopLe | GoiConHieuLuc | DangCho`; `nang_goi.moi_nhat(sub) -> dict | None`; endpoints spec §6.1–6.4, §8.3, §8.4.

- [ ] **Step 1: Test đỏ**

`tests/test_api/test_tai_khoan.py`: hai test đầu theo hình mới — `d["muc"][0]["khoa"] == "hoi_dap_ngay"`, `d["muc"][0]["han_muc"] == 200`, `d["phien"]["luot_toi_da"] == 20`, `d["het_han_luc"] is None`, `d["ten_goi"] == "Miễn phí"` (fixture `khong_dung_db` monkeypatch `dem_luot` → 7 nên `da_dung == 7`); test chưa cấu hình: `ap_dung is False and d["muc"] == [] and d["plan"] is None`; thêm test khách: `cai_dat(supabase_url=SUPABASE)`, `GET /han-muc` với `X-Khach-Id` (monkeypatch `bao_ve.dem_cua_so` → `(3, None)`) → `plan == "khach"`, `muc[0]["khoa"] == "khach_24h"`, `han_muc == 10`, `da_dung == 3`, `phien.luot_toi_da == 10`; không header → 401.

`tests/test_api/test_ho_so_nang_goi.py`:

```python
"""/ho-so, /nang-goi/yeu-cau, /hoi-thoai/nhap (spec 2A §6.2–6.4, §8.4)."""

import uuid

import pytest
from sqlalchemy import text

from src.services import bao_ve, hoi_thoai
from src.services.db import get_engine
from tests.test_api.test_tra_cuu_phien import SUPABASE
from tests.test_api.test_xac_thuc_han_muc import _bearer

pytestmark = pytest.mark.integration
# Payload đúng hình `TraCuuResponse` — lấy từ một response thật của `graph_gia_lap` nếu thiếu trường.
P = {
    "result_type": "answer", "answer": "a", "citations": [], "nguon": [], "warnings": [], "coverage_note": None,
    "bang": [], "documents": [], "soan_thao": None, "trace_id": "t", "cau_hoi_day_du": None, "config_name": "full",
}


@pytest.fixture
def nguoi(cai_dat, khoa_ky):
    cai_dat(supabase_url=SUPABASE)
    sub = str(uuid.uuid4())
    bao_ve.ghi_nhan_nguoi_dung(sub, "a@test.local")
    yield sub
    with get_engine().begin() as c:
        for bang in ("yeu_cau_nang_goi", "hoi_thoai", "traces"):
            c.execute(text(f"DELETE FROM {bang} WHERE user_sub = :s"), {"s": sub})  # noqa: S608 — tên bảng là hằng
        c.execute(text("DELETE FROM users WHERE sub = :s"), {"s": sub})


@pytest.mark.asyncio
async def test_ho_so_tong_hop(client, khoa_ky, nguoi):
    pid = hoi_thoai.tao_phien(nguoi, "x")
    hoi_thoai.ghi_luot(pid, "x", P, "t")
    with get_engine().begin() as c:
        c.execute(
            text(
                "INSERT INTO traces (id, endpoint, config_name, result_type, user_sub) VALUES"
                " (:i, '/api/v1/tra-cuu', 'full', 'answer', :s), (:j, '/api/v1/soan-thao', 'full', NULL, :s)"
            ),
            {"i": str(uuid.uuid4()), "j": str(uuid.uuid4()), "s": nguoi},
        )
    d = (await client.get("/api/v1/ho-so", headers=_bearer(khoa_ky, nguoi))).json()
    assert d["email"] == "a@test.local" and d["plan"] == "free" and d["ten_goi"] == "Miễn phí"
    assert d["so_phien"] == 1 and d["tong_hoi_dap"] == 1 and d["tong_ban_thao"] == 1
    assert d["hoat_dong"][-1]["so_luot"] == 2 and {p["khoa"] for p in d["phan_loai"]} >= {"answer", "soan_thao"}


@pytest.mark.asyncio
async def test_yeu_cau_nang_goi_201_409_422(client, khoa_ky, nguoi):
    h = _bearer(khoa_ky, nguoi)
    r = await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)
    assert r.status_code == 201 and r.json()["loai"] == "nang_goi" and r.json()["trang_thai"] == "cho_duyet"
    assert (await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)).status_code == 409
    assert (await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "vip"}, headers=h)).status_code == 422
    assert (await client.get("/api/v1/nang-goi/yeu-cau", headers=h)).json()["trang_thai"] == "cho_duyet"


@pytest.mark.asyncio
async def test_gia_han_chi_khi_con_7_ngay(client, khoa_ky, nguoi):
    h = _bearer(khoa_ky, nguoi)
    with get_engine().begin() as c:
        c.execute(text("UPDATE users SET plan='pro', plan_het_han = now() + interval '20 days' WHERE sub = :s"), {"s": nguoi})
    assert (await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)).status_code == 422
    with get_engine().begin() as c:
        c.execute(text("UPDATE users SET plan_het_han = now() + interval '3 days' WHERE sub = :s"), {"s": nguoi})
    r = await client.post("/api/v1/nang-goi/yeu-cau", json={"goi_muon": "pro"}, headers=h)
    assert r.status_code == 201 and r.json()["loai"] == "gia_han"
    d = (await client.get("/api/v1/han-muc", headers=h)).json()
    assert d["plan"] == "pro" and d["het_han_luc"] is not None and d["phien"]["luot_toi_da"] == 50


@pytest.mark.asyncio
async def test_pro_het_han_ve_free(client, khoa_ky, nguoi):
    with get_engine().begin() as c:
        c.execute(text("UPDATE users SET plan='pro', plan_het_han = now() - interval '1 day' WHERE sub = :s"), {"s": nguoi})
    d = (await client.get("/api/v1/han-muc", headers=_bearer(khoa_ky, nguoi))).json()
    assert d["plan"] == "free" and d["het_han_luc"] is not None and d["phien"]["luot_toi_da"] == 20


@pytest.mark.asyncio
async def test_nhap_phien_201_va_422(client, khoa_ky, nguoi):
    h = _bearer(khoa_ky, nguoi)
    r = await client.post("/api/v1/hoi-thoai/nhap", json={"luot": [{"cau_hoi": "Câu?", "tra_loi": P, "trace_id": "t"}]}, headers=h)
    assert r.status_code == 201
    assert hoi_thoai.chi_tiet(nguoi, r.json()["id"])["luot"][0]["cau_hoi"] == "Câu?"
    assert (await client.post("/api/v1/hoi-thoai/nhap", json={"luot": [{"cau_hoi": "x", "tra_loi": {"rac": 1}}]}, headers=h)).status_code == 422
    assert (await client.post("/api/v1/hoi-thoai/nhap", json={"luot": []}, headers=h)).status_code == 422
```

- [ ] **Step 2: Đỏ.**

- [ ] **Step 3: `src/services/ho_so.py`**

```python
"""Tổng hợp hồ sơ tài khoản (spec 2A §6.2) — chỉ đọc, chỉ của `sub`."""

from sqlalchemy import text

from src.services.bao_ve import mui_gio
from src.services.db import get_engine

NHAN_PHAN_LOAI = {
    "answer": "Trả lời có căn cứ",
    "partial_coverage": "Trả lời một phần",
    "abstain": "Dừng vì thiếu căn cứ",
    "out_of_scope": "Ngoài phạm vi",
    "soan_thao": "Bản thảo",
}
_SQL_USER = text("SELECT email, plan, plan_het_han, created_at FROM users WHERE sub = :sub")
_SQL_SO_PHIEN = text("SELECT count(*)::int FROM hoi_thoai WHERE user_sub = :sub AND xoa_luc IS NULL")
_SQL_TONG = text(
    "SELECT endpoint, count(*)::int AS n FROM traces WHERE user_sub = :sub AND NOT cache_hit"
    " AND (result_type IS NULL OR result_type NOT IN ('loi', 'out_of_scope')) GROUP BY endpoint"
)
# Hoạt động là hoạt động: KHÔNG loại out_of_scope, chỉ loại lỗi và bộ đệm.
_SQL_HOAT_DONG = text(
    "SELECT (ts AT TIME ZONE :tz)::date AS ngay, count(*)::int AS so_luot FROM traces"
    " WHERE user_sub = :sub AND NOT cache_hit AND result_type IS DISTINCT FROM 'loi'"
    " AND ts >= now() - interval '365 days' GROUP BY 1 ORDER BY 1"
)
_SQL_PHAN_LOAI = text(
    "SELECT CASE WHEN endpoint = '/api/v1/soan-thao' THEN 'soan_thao' ELSE result_type END AS khoa,"
    " count(*)::int AS so FROM traces WHERE user_sub = :sub AND NOT cache_hit"
    " AND result_type IS DISTINCT FROM 'loi' GROUP BY 1 ORDER BY 2 DESC"
)


def tong_hop(sub: str) -> dict | None:
    with get_engine().connect() as c:
        u = c.execute(_SQL_USER, {"sub": sub}).mappings().one_or_none()
        if u is None:
            return None
        so_phien = int(c.execute(_SQL_SO_PHIEN, {"sub": sub}).scalar_one())
        tong = {r["endpoint"]: r["n"] for r in c.execute(_SQL_TONG, {"sub": sub}).mappings()}
        hoat_dong = [dict(r) for r in c.execute(_SQL_HOAT_DONG, {"sub": sub, "tz": str(mui_gio())}).mappings()]
        phan_loai = [
            {"khoa": r["khoa"], "nhan": NHAN_PHAN_LOAI.get(r["khoa"], "Khác"), "so": r["so"]}
            for r in c.execute(_SQL_PHAN_LOAI, {"sub": sub}).mappings()
            if r["khoa"] is not None
        ]
    return {
        "email": u["email"],
        "plan_tho": u["plan"],
        "plan_het_han": u["plan_het_han"],
        "tao_luc": u["created_at"],
        "so_phien": so_phien,
        "tong_hoi_dap": tong.get("/api/v1/tra-cuu", 0),
        "tong_ban_thao": tong.get("/api/v1/soan-thao", 0),
        "hoat_dong": hoat_dong,
        "phan_loai": phan_loai,
    }
```

`src/services/nang_goi.py`:

```python
"""Yêu cầu nâng/gia hạn gói (spec 2A §6.3). Duyệt thuộc gói 2B (tạm SQL tay)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.services.bao_ve import _doc_han_muc, plan_hieu_luc_tu
from src.services.db import get_engine

GIA_HAN_TRUOC_NGAY = 7


class GoiKhongHopLe(ValueError):
    pass


class GoiConHieuLuc(ValueError):
    pass


class DangCho(ValueError):
    pass


_SQL_USER = text("SELECT plan, plan_het_han FROM users WHERE sub = :sub")
_SQL_TAO = text(
    "INSERT INTO yeu_cau_nang_goi (user_sub, loai, goi_hien_tai, goi_muon) VALUES (:sub, :loai, :ht, :muon)"
    " RETURNING id, loai, goi_hien_tai, goi_muon, trang_thai, tao_luc, xu_ly_luc"
)
_SQL_MOI_NHAT = text(
    "SELECT id, loai, goi_hien_tai, goi_muon, trang_thai, tao_luc, xu_ly_luc FROM yeu_cau_nang_goi"
    " WHERE user_sub = :sub ORDER BY tao_luc DESC, id DESC LIMIT 1"
)


def tao_yeu_cau(sub: str, goi_muon: str) -> dict:
    d = _doc_han_muc()
    if goi_muon not in d["goi"] or goi_muon == d["goi_mac_dinh"]:
        raise GoiKhongHopLe(goi_muon)
    with get_engine().connect() as c:
        u = c.execute(_SQL_USER, {"sub": sub}).mappings().one()
    hieu_luc = plan_hieu_luc_tu(str(u["plan"]), u["plan_het_han"])
    if hieu_luc == goi_muon:
        het = u["plan_het_han"]
        if het is None or het - datetime.now(UTC) > timedelta(days=GIA_HAN_TRUOC_NGAY):
            raise GoiConHieuLuc()
        loai = "gia_han"
    else:
        loai = "nang_goi"
    try:
        with get_engine().begin() as c:
            r = c.execute(_SQL_TAO, {"sub": sub, "loai": loai, "ht": hieu_luc, "muon": goi_muon}).mappings().one()
            return dict(r)
    except IntegrityError as e:  # unique index: đã có yêu cầu cho_duyet
        raise DangCho() from e


def moi_nhat(sub: str) -> dict | None:
    with get_engine().connect() as c:
        r = c.execute(_SQL_MOI_NHAT, {"sub": sub}).mappings().one_or_none()
    return dict(r) if r is not None else None
```

- [ ] **Step 4: `src/api/routes_tai_khoan.py`** — imports: `Depends`, models mới, `from src.services import bao_ve, ho_so, nang_goi, xac_thuc`, `nguoi_dung_bat_buoc`. `GHI_CHU_CACHE = "Lượt trả lời từ bộ đệm, câu ngoài phạm vi và lượt lỗi không tính. Tra cứu luật, soát văn bản không bao giờ tính."`. Viết lại `/han-muc`:

```python
@router.get("/han-muc", response_model=HanMucResponse)
async def han_muc_cua_toi(request: Request) -> HanMucResponse:
    """Hạn mức của người gọi. KHÔNG đi qua `cong_bao_ve` (không tốn lượt, không tự khoá)."""
    bao_ve.kiem_api_key(request)
    tz = str(bao_ve.mui_gio())
    nguoi = await run_in_threadpool(bao_ve.xac_thuc_nguoi_goi_hoac_none, request)
    if nguoi is None and not xac_thuc.da_cau_hinh():
        return HanMucResponse(ap_dung=False, plan=None, ten_goi=None, mui_gio=tz, muc=[], phien=PhienHanMuc(luot_toi_da=None), het_han_luc=None, ghi_chu=GHI_CHU_TAT)
    if nguoi is None:
        kid = bao_ve.khach_id_tu_request(request)
        if kid is None:
            raise HTTPException(status_code=401, detail=bao_ve.LOI_KHACH_DANG_NHAP)
        k = bao_ve._doc_han_muc()["khach"]
        da_dung, mo_lai = await run_in_threadpool(bao_ve.dem_cua_so, f"khach:{kid}", 86400)
        return HanMucResponse(
            ap_dung=True, plan="khach", ten_goi="Dùng thử", mui_gio=tz,
            muc=[MucHanMuc(khoa="khach_24h", nhan="Lượt thử 24 giờ", da_dung=da_dung, han_muc=int(k["hoi_dap_24h"]), dat_lai_luc=mo_lai)],
            phien=PhienHanMuc(luot_toi_da=int(k["hoi_dap_24h"])), het_han_luc=None,
            ghi_chu="Đăng nhập miễn phí để có 200 lượt mỗi ngày, lưu phiên và soạn văn bản.",
        )
    sub = nguoi["sub"]
    try:
        plan = await run_in_threadpool(bao_ve.ghi_nhan_nguoi_dung, sub, nguoi["email"])
        muc = await run_in_threadpool(bao_ve.mo_ta_muc, sub, plan)
        het_han = await run_in_threadpool(bao_ve.het_han_cua, sub)
    except Exception as e:
        logger.exception("han_muc: không đọc được hạn mức của %s — TỪ CHỐI", sub)
        raise HTTPException(status_code=503, detail="Không đọc được hạn mức của tài khoản, vui lòng thử lại.") from e
    return HanMucResponse(
        ap_dung=True, plan=plan, ten_goi=bao_ve.ten_goi(plan), mui_gio=tz, muc=[MucHanMuc(**m) for m in muc],
        phien=PhienHanMuc(luot_toi_da=bao_ve.han_muc(plan, "luot_moi_phien")),
        het_han_luc=het_han, ghi_chu=GHI_CHU_CACHE,
    )
```

Thêm:

```python
@router.get("/ho-so", response_model=HoSoResponse)
async def ho_so_cua_toi(nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> HoSoResponse:
    d = await run_in_threadpool(ho_so.tong_hop, nguoi["sub"])
    if d is None:
        raise HTTPException(status_code=404, detail="Chưa có hồ sơ cho tài khoản này.")
    plan = bao_ve.plan_hieu_luc_tu(d["plan_tho"], d["plan_het_han"])
    return HoSoResponse(
        email=d["email"], plan=plan, ten_goi=bao_ve.ten_goi(plan), tao_luc=d["tao_luc"],
        het_han_luc=d["plan_het_han"], so_phien=d["so_phien"],
        tong_hoi_dap=d["tong_hoi_dap"], tong_ban_thao=d["tong_ban_thao"],
        hoat_dong=[HoatDongNgay(**h) for h in d["hoat_dong"]], phan_loai=[PhanLoai(**p) for p in d["phan_loai"]],
    )


@router.post("/nang-goi/yeu-cau", response_model=YeuCauNangGoiOut, status_code=201)
async def gui_yeu_cau(body: YeuCauNangGoiRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> YeuCauNangGoiOut:
    try:
        return YeuCauNangGoiOut(**await run_in_threadpool(nang_goi.tao_yeu_cau, nguoi["sub"], body.goi_muon))
    except nang_goi.GoiKhongHopLe as e:
        raise HTTPException(status_code=422, detail="Gói không hợp lệ.") from e
    except nang_goi.GoiConHieuLuc as e:
        raise HTTPException(status_code=422, detail="Gói còn hiệu lực, gia hạn được từ 7 ngày trước khi hết hạn.") from e
    except nang_goi.DangCho as e:
        raise HTTPException(status_code=409, detail="Bạn đã có một yêu cầu đang chờ duyệt.") from e


@router.get("/nang-goi/yeu-cau", response_model=YeuCauNangGoiOut | None)
async def yeu_cau_moi_nhat(nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> YeuCauNangGoiOut | None:
    r = await run_in_threadpool(nang_goi.moi_nhat, nguoi["sub"])
    return YeuCauNangGoiOut(**r) if r is not None else None
```

`src/api/routes_hoi_thoai.py`:

```python
@router.post("/hoi-thoai/nhap", response_model=NhapPhienResponse, status_code=201)
async def nhap(body: NhapPhienRequest, nguoi: dict = Depends(nguoi_dung_bat_buoc)) -> NhapPhienResponse:
    """Mang đoạn chat của khách vào tài khoản (spec 2A §8.4). `tra_loi` đã qua pydantic
    `TraCuuResponse` nên chỉ payload đúng hình mới vào được; không đụng `traces`."""
    luot = [{"cau_hoi": lu.cau_hoi, "tra_loi": lu.tra_loi.model_dump(mode="json"), "trace_id": lu.trace_id} for lu in body.luot]
    return NhapPhienResponse(id=await run_in_threadpool(hoi_thoai.nhap_phien, nguoi["sub"], luot))
```

- [ ] **Step 5: Xanh**

```bash
.venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check src/services/ho_so.py src/services/nang_goi.py tests/test_api/test_ho_so_nang_goi.py && .venv/bin/python -m pytest tests/test_api/test_tai_khoan.py tests/test_api/test_ho_so_nang_goi.py tests/test_api/test_hoi_thoai.py tests/test_api/test_khach.py -q
.venv/bin/python -m pytest tests/test_api tests/test_services -q --ignore=tests/test_services/test_effectivity.py
```

(Chỉ `tests/test_services/test_moi_mau.py` bẩn được đỏ.)

- [ ] **Step 6: Commit**

```bash
git add src/services/ho_so.py src/services/nang_goi.py src/services/bao_ve.py src/api/routes_tai_khoan.py src/api/routes_hoi_thoai.py tests/test_api/test_ho_so_nang_goi.py tests/test_api/test_tai_khoan.py
git commit -m "feat(api): quota meters, profile aggregate, upgrade requests with 30-day cycle, guest thread import

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

# BƯỚC 2 — FRONTEND (worktree `../KLAW-fe4`, nhánh `wt-fe-tk`; lệnh chạy trong `frontend/`)

Chạy song song với BƯỚC 1: BE chỉ sửa `src/`, `tests/`; FE chỉ sửa `frontend/`. Hợp đồng hai phía đã chốt ở Task 1. Không chạy `npm run dev` (cổng 3000 do chủ dự án dùng); kiểm bằng `npm run typecheck && npm run lint && npm run build` và các `kiem-*`.

### Task 5: Khách, hạn mức, thanh đo — `lib/khach.ts`, `lib/han-muc.ts`, `lib/goi.ts`, `use-han-muc.ts`, `ThuocMucDung`

**Files:**
- Create: `frontend/src/lib/han-muc.ts`, `frontend/src/lib/goi.ts`, `frontend/src/hooks/use-han-muc.ts`, `frontend/src/components/tai-khoan/ThuocMucDung.tsx`, `frontend/scripts/kiem-han-muc.ts`
- Modify: `frontend/src/lib/khach.ts` (thêm cất/lấy thread), `frontend/src/lib/phien.ts` (bỏ `cauPhienAn`, chuyển `tenGoi` sang `goi.ts`), `frontend/src/components/klaw/DanhSachPhien.tsx` (bỏ import `cauPhienAn`/khối `tong_an`), `frontend/scripts/kiem-phien.ts`, `frontend/package.json` (`kiem-han-muc` + nối vào `kiem`)

**Interfaces:**
- Consumes: Task 1 `HanMuc`, `MucHanMuc`, `laHanMuc`, `LuotDaXong` (`lib/lich-su.ts`), `useGoiApi`.
- Produces: `khach.ts`: `catThreadKhach(luot: LuotDaXong[]): void`, `layThreadKhach(): LuotDaXong[] | null`, `xoaThreadKhach(): void` (sessionStorage `klaw.khach_thread`); `han-muc.ts`: `KHONG_GIOI_HAN = 100000`, `laKhongGioiHan(hanMuc: number): boolean`, `phanTram(m: MucHanMuc): number` (0–100, không giới hạn → 0), `mucMau(pt): "brass" | "amber" | "do"` (<80 / 80–99 / ≥100), `dinhDangMoc(iso: string | null, muiGio: string): string` ("00:00 08/09", rỗng khi null), `mucRangBuoc(hm: HanMuc | null): MucHanMuc | null` (mục đầu tiên có trần thật), `cauChip(m: MucHanMuc): string`, `soNgayCon(iso: string | null): number | null`; `goi.ts`: `tenGoi(plan): string` ("Miễn phí"/"Cá nhân"/"Dùng thử" cho `khach`/mã), `GIA_PRO = 499_000`, `GOI_CARD: Record<"free" | "pro", { nhan: string; tieuDe: string; moTa: string; gia: string; tieuDeDanhSach: string; danhSach: { icon: LucideIcon; chu: string }[] }>` đúng chữ spec §7.5; `useHanMuc(kichHoat: boolean) → { hanMuc: HanMuc | null; dangTai: boolean; loi: ApiError | null; taiLai(): void }`; `ThuocMucDung({ muc, muiGio, gon? })`.

- [ ] **Step 1: Kiểm đỏ** `frontend/scripts/kiem-han-muc.ts`

```ts
/** Thanh đo hạn mức (spec 2A §7.2): phần trăm, ngưỡng màu, "Không giới hạn", mốc theo VN,
 *  câu chip. Chạy: `npm run kiem-han-muc`. */
import assert from "node:assert/strict";
import { tenGoi } from "../src/lib/goi.ts";
import {
  cauChip, dinhDangMoc, laKhongGioiHan, mucMau, mucRangBuoc, phanTram, soNgayCon,
} from "../src/lib/han-muc.ts";

const m = (khoa: string, da: number, han: number) => ({
  khoa, nhan: khoa, da_dung: da, han_muc: han, dat_lai_luc: "2026-09-07T17:00:00Z",
});
{
  assert.equal(phanTram(m("hoi_dap_ngay", 128, 200)), 64);
  assert.equal(phanTram(m("hoi_dap_ngay", 5, 100000)), 0);
  assert.equal(laKhongGioiHan(100000), true);
  assert.equal(laKhongGioiHan(200), false);
  assert.deepEqual([mucMau(0), mucMau(79), mucMau(80), mucMau(99), mucMau(100)], ["brass", "brass", "amber", "amber", "do"]);
}
{
  assert.equal(dinhDangMoc("2026-09-07T17:00:00Z", "Asia/Ho_Chi_Minh"), "00:00 08/09");
  assert.equal(dinhDangMoc(null, "Asia/Ho_Chi_Minh"), "");
}
{
  assert.equal(cauChip(m("hoi_dap_ngay", 194, 200)), "Còn 6 lượt hôm nay");
  assert.equal(cauChip(m("khach_24h", 3, 10)), "Còn 7/10 lượt thử");
  assert.equal(cauChip(m("soan_thao_ngay", 1, 3)), "Còn 2 bản thảo hôm nay");
  assert.equal(cauChip(m("hoi_dap_ngay", 200, 200)), "Hết lượt hôm nay");
}
{
  const hm = {
    ap_dung: true, plan: "pro", ten_goi: "Cá nhân", mui_gio: "Asia/Ho_Chi_Minh", het_han_luc: null, ghi_chu: "",
    phien: { luot_toi_da: 50 }, muc: [m("hoi_dap_ngay", 3, 100000), m("soan_thao_ngay", 1, 20)],
  };
  assert.equal(mucRangBuoc(hm)?.khoa, "soan_thao_ngay");
  assert.equal(mucRangBuoc(null), null);
  assert.equal(tenGoi("pro"), "Cá nhân");
  assert.equal(tenGoi("khach"), "Dùng thử");
  assert.equal(soNgayCon(null), null);
}
console.info("kiem-han-muc: 4/4 đạt");
```

`package.json`: `"kiem-han-muc": "node scripts/kiem-han-muc.ts"`, nối `&& npm run kiem-han-muc` sau `npm run kiem-phien`. `kiem-phien.ts`: bỏ nhóm kiểm `tenGoi`/`cauPhienAn`, sửa dòng cuối thành "kiem-phien: 3/3 đạt".

- [ ] **Step 2: Đỏ** — `npm run kiem-han-muc` → ERR_MODULE_NOT_FOUND.

- [ ] **Step 3: `lib/han-muc.ts`**

```ts
import type { HanMuc, MucHanMuc } from "./klaw";

export const KHONG_GIOI_HAN = 100_000;
export const laKhongGioiHan = (hanMuc: number): boolean => hanMuc >= KHONG_GIOI_HAN;

export function phanTram(m: MucHanMuc): number {
  if (laKhongGioiHan(m.han_muc) || m.han_muc <= 0) return 0;
  return Math.min(100, Math.round((m.da_dung / m.han_muc) * 100));
}

export function mucMau(pt: number): "brass" | "amber" | "do" {
  return pt >= 100 ? "do" : pt >= 80 ? "amber" : "brass";
}

export function dinhDangMoc(iso: string | null, muiGio: string): string {
  if (iso === null) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const gio = new Intl.DateTimeFormat("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: muiGio }).format(t);
  const ngay = new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", timeZone: muiGio }).format(t);
  return `${gio} ${ngay}`;
}

export function soNgayCon(iso: string | null): number | null {
  if (iso === null) return null;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : Math.max(0, Math.ceil((t - Date.now()) / 86_400_000));
}

/** Mục đầu tiên có trần thật — chip cạnh ô hỏi theo dõi mục này. */
export function mucRangBuoc(hm: HanMuc | null): MucHanMuc | null {
  return hm?.muc.find((m) => !laKhongGioiHan(m.han_muc)) ?? null;
}

const DON_VI: Record<string, [string, string]> = {
  hoi_dap_ngay: ["lượt", "hôm nay"],
  soan_thao_ngay: ["bản thảo", "hôm nay"],
  soan_thao_thang: ["bản thảo", "tháng này"],
};

export function cauChip(m: MucHanMuc): string {
  const con = Math.max(0, m.han_muc - m.da_dung);
  if (m.khoa === "khach_24h") return `Còn ${con}/${m.han_muc} lượt thử`;
  const [dv, ky] = DON_VI[m.khoa] ?? ["lượt", ""];
  return (con === 0 ? `Hết ${dv} ${ky}` : `Còn ${con} ${dv} ${ky}`).trim();
}
```

`lib/goi.ts`: `tenGoi` (chuyển từ `phien.ts`, thêm `khach → "Dùng thử"`), `GIA_PRO = 499_000`, `GOI_CARD` với icon lucide (`MessageSquare`, `ListOrdered`, `FileSignature`, `History`, `BookOpenText`, `Download`, `Sparkles`, `CalendarClock`) và chữ đúng bảng spec §7.5: Free nhãn "Miễn phí", tiêu đề "Dùng thử KLAW", mô tả "Hỏi pháp luật lao động và nhận câu trả lời có căn cứ kiểm chứng được, soạn văn bản mẫu, tra cứu luật.", giá "₫0 / tháng", "Bắt đầu với những điều cơ bản:", 6 dòng ("200 lượt hỏi đáp mỗi ngày", "20 lượt mỗi phiên", "3 bản thảo mỗi ngày, 20 mỗi tháng", "Phiên và lịch sử không giới hạn", "Tra cứu luật, soát văn bản không giới hạn", "Xuất Word, PDF"); Cá nhân nhãn "Cá nhân", tiêu đề "Dùng cho công việc", mô tả "Cho luật sư, chuyên viên nhân sự và pháp chế hỏi nhiều mỗi ngày và soạn văn bản thường xuyên.", giá "₫499.000 / 30 ngày", "Mọi thứ trong gói Miễn phí, cộng thêm:", 5 dòng ("Hỏi đáp không giới hạn ngày và tháng*", "50 lượt mỗi phiên", "20 bản thảo mỗi ngày, không giới hạn tháng", "Trí nhớ hoàn cảnh xuyên phiên (sắp có)", "Hiệu lực 30 ngày, gia hạn khi hết"). `phien.ts` chỉ còn `thoiGianTuongDoi`.

`lib/khach.ts` thêm:

```ts
import type { LuotDaXong } from "./lich-su";

const KHOA_THREAD = "klaw.khach_thread";

/** Cất đoạn chat khách trước khi rời sang đăng nhập/đăng ký (spec 2A §8.4). */
export function catThreadKhach(luot: LuotDaXong[]): void {
  try {
    if (luot.length > 0) sessionStorage.setItem(KHOA_THREAD, JSON.stringify(luot.slice(-10)));
  } catch {
    /* không có sessionStorage: bỏ qua, người dùng vẫn đăng nhập được */
  }
}
export function layThreadKhach(): LuotDaXong[] | null {
  try {
    const tho = sessionStorage.getItem(KHOA_THREAD);
    if (tho === null) return null;
    const du: unknown = JSON.parse(tho);
    return Array.isArray(du) && du.length > 0 ? (du as LuotDaXong[]) : null;
  } catch {
    return null;
  }
}
export function xoaThreadKhach(): void {
  try {
    sessionStorage.removeItem(KHOA_THREAD);
  } catch {
    /* bỏ qua */
  }
}
```

`hooks/use-han-muc.ts`:

```ts
import { useCallback, useEffect } from "react";
import { goi } from "@/lib/api";
import { laHanMuc, type ApiError, type HanMuc } from "@/lib/klaw";
import { useGoiApi } from "./use-goi-api";

export interface TrangThaiHanMuc {
  hanMuc: HanMuc | null;
  dangTai: boolean;
  loi: ApiError | null;
  taiLai: () => void;
}

/** `/han-muc` cho cả tài khoản và khách (`api.ts` tự gửi bearer hoặc `X-Khach-Id`). */
export function useHanMuc(kichHoat: boolean): TrangThaiHanMuc {
  const g = useGoiApi<HanMuc>();
  const { chay } = g;
  const taiLai = useCallback(() => {
    void chay((signal) => goi("/han-muc", laHanMuc, { signal }));
  }, [chay]);
  useEffect(() => {
    if (kichHoat) taiLai();
  }, [kichHoat, taiLai]);
  return { hanMuc: g.ketQua, dangTai: g.dangChay, loi: g.loi, taiLai };
}
```

`components/tai-khoan/ThuocMucDung.tsx`:

```tsx
import type { MucHanMuc } from "@/lib/klaw";
import { dinhDangMoc, laKhongGioiHan, mucMau, phanTram } from "@/lib/han-muc";
import { cn } from "@/lib/utils";

const MAU = { brass: "bg-[var(--color-brass-500)]", amber: "bg-amber-500", do: "bg-destructive" } as const;

export function ThuocMucDung({ muc, muiGio, gon = false }: { muc: MucHanMuc[]; muiGio: string; gon?: boolean }) {
  return (
    <ul className="m-0 list-none space-y-3 p-0">
      {muc.map((m) => {
        const pt = phanTram(m);
        const khongGioiHan = laKhongGioiHan(m.han_muc);
        return (
          <li key={m.khoa}>
            <div className="flex items-baseline justify-between gap-3 text-[13px]">
              <span className="font-medium text-foreground">{m.nhan}</span>
              <span className="text-muted-foreground">{khongGioiHan ? "Không giới hạn" : `${pt}% đã dùng`}</span>
            </div>
            {!khongGioiHan && (
              <>
                <div
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={pt}
                  aria-label={m.nhan}
                  className="mt-1 h-2 overflow-hidden rounded-full bg-[var(--color-paper-200)]"
                >
                  <div className={cn("h-full rounded-full transition-[width]", MAU[mucMau(pt)])} style={{ width: `${pt}%` }} />
                </div>
                {!gon && (
                  <p className="m-0 mt-1 text-[12px] text-muted-foreground">
                    {m.da_dung}/{m.han_muc} · Đặt lại {dinhDangMoc(m.dat_lai_luc, muiGio)} ({muiGio})
                  </p>
                )}
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
```

- [ ] **Step 4: Xanh** — `npm run typecheck && npm run lint && npm run kiem-han-muc && npm run kiem-phien && npx prettier --check src/lib/han-muc.ts src/lib/goi.ts src/lib/khach.ts src/lib/phien.ts src/hooks/use-han-muc.ts src/components/tai-khoan/ThuocMucDung.tsx scripts/kiem-han-muc.ts scripts/kiem-phien.ts src/components/klaw/DanhSachPhien.tsx`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/han-muc.ts frontend/src/lib/goi.ts frontend/src/lib/khach.ts frontend/src/lib/phien.ts frontend/src/hooks/use-han-muc.ts frontend/src/components/tai-khoan/ThuocMucDung.tsx frontend/scripts/kiem-han-muc.ts frontend/scripts/kiem-phien.ts frontend/package.json frontend/src/components/klaw/DanhSachPhien.tsx
git commit -m "feat(frontend): quota meter, guest thread stash, plan copy helpers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: `TaiKhoanProvider` và vỏ ứng dụng kiểu ChatGPT

**Files:**
- Create: `frontend/src/contexts/tai-khoan.tsx`, `frontend/src/components/tai-khoan/TheTaiKhoan.tsx`, `frontend/src/components/tai-khoan/MenuTaiKhoan.tsx`
- Modify: `frontend/src/routes/__root.tsx` (bọc `TaiKhoanProvider`), `frontend/src/components/app/AppShell.tsx` (viết lại), `frontend/src/components/klaw/DanhSachPhien.tsx` (xoá `CotPhien`, xuất `DanhSachPhien`), `frontend/src/lib/quay-lai.ts` (`dichQuayLaiTu`), `frontend/src/routes/dung-thu.tsx` (chỉ xoá import + khối mount `CotPhien` để typecheck qua; Task 7 làm phần còn lại)

**Interfaces:**
- Consumes: `useAuth`, `useHoiThoai` (gói 1), `useHanMuc` (Task 5), `catThreadKhach`, `locNext`.
- Produces: `useTaiKhoan(): { user: User | null; dangKiemPhien: boolean; chuaCauHinh: boolean; daDangNhap: boolean; laKhach: boolean; hoiThoai: TrangThaiHoiThoai; hanMuc: TrangThaiHanMuc; nangGoiMo: boolean; moNangGoi(): void; dongNangGoi(): void; signOut(): Promise<void>; datHanhDongPhienMoi(fn: (() => void) | null): void; phienMoi(): void; datLayThreadKhach(fn: (() => LuotDaXong[]) | null): void; catThreadTruocKhiRoi(): void }`; `DanhSachPhien({ hoiThoai, phienDangMo, onChon, onPhienMoi, onDaXoa })`; `dichQuayLaiTu(pathname: string): DichQuayLai`; `AppShell({ active?, topRight?, children })` giữ chữ ký.

- [ ] **Step 1: Context** `frontend/src/contexts/tai-khoan.tsx`

```tsx
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import type { User } from "@supabase/supabase-js";
import { useAuth } from "@/hooks/use-auth";
import { useHanMuc, type TrangThaiHanMuc } from "@/hooks/use-han-muc";
import { useHoiThoai, type TrangThaiHoiThoai } from "@/hooks/use-hoi-thoai";
import { catThreadKhach } from "@/lib/khach";
import type { LuotDaXong } from "@/lib/lich-su";

export interface TaiKhoan {
  user: User | null;
  dangKiemPhien: boolean;
  chuaCauHinh: boolean;
  daDangNhap: boolean;
  laKhach: boolean;
  hoiThoai: TrangThaiHoiThoai;
  hanMuc: TrangThaiHanMuc;
  nangGoiMo: boolean;
  moNangGoi: () => void;
  dongNangGoi: () => void;
  signOut: () => Promise<void>;
  /** `/dung-thu` đăng ký hàm "Phiên mới" của nó; nơi khác điều hướng về `/dung-thu`. */
  datHanhDongPhienMoi: (fn: (() => void) | null) => void;
  phienMoi: () => void;
  /** `/dung-thu` đăng ký hàm trả đoạn chat khách; nút Đăng nhập/Đăng ký cất nó trước khi rời. */
  datLayThreadKhach: (fn: (() => LuotDaXong[]) | null) => void;
  catThreadTruocKhiRoi: () => void;
}

const Ctx = createContext<TaiKhoan | null>(null);

export function TaiKhoanProvider({ children }: { children: ReactNode }) {
  const { user, loading: dangKiemPhien, chuaCauHinh, signOut } = useAuth();
  const daDangNhap = !chuaCauHinh && !dangKiemPhien && user !== null;
  const laKhach = !chuaCauHinh && !dangKiemPhien && user === null;
  const hoiThoai = useHoiThoai(daDangNhap);
  const hanMuc = useHanMuc(!chuaCauHinh && !dangKiemPhien); // khách cũng có thanh đo (X-Khach-Id)
  const [nangGoiMo, datNangGoiMo] = useState(false);
  const navigate = useNavigate();
  const hanhDongPhienMoi = useRef<(() => void) | null>(null);
  const layThread = useRef<(() => LuotDaXong[]) | null>(null);

  const phienMoi = useCallback(() => {
    if (hanhDongPhienMoi.current !== null) hanhDongPhienMoi.current();
    else void navigate({ to: "/dung-thu", search: {} });
  }, [navigate]);
  const catThreadTruocKhiRoi = useCallback(() => {
    const t = layThread.current?.();
    if (t !== undefined && t.length > 0) catThreadKhach(t);
  }, []);

  const gia = useMemo<TaiKhoan>(
    () => ({
      user, dangKiemPhien, chuaCauHinh, daDangNhap, laKhach, hoiThoai, hanMuc, nangGoiMo,
      moNangGoi: () => datNangGoiMo(true),
      dongNangGoi: () => datNangGoiMo(false),
      signOut,
      datHanhDongPhienMoi: (fn) => { hanhDongPhienMoi.current = fn; },
      phienMoi,
      datLayThreadKhach: (fn) => { layThread.current = fn; },
      catThreadTruocKhiRoi,
    }),
    [user, dangKiemPhien, chuaCauHinh, daDangNhap, laKhach, hoiThoai, hanMuc, nangGoiMo, signOut, phienMoi, catThreadTruocKhiRoi],
  );
  return <Ctx.Provider value={gia}>{children}</Ctx.Provider>;
}

export function useTaiKhoan(): TaiKhoan {
  const v = useContext(Ctx);
  if (v === null) throw new Error("useTaiKhoan phải nằm trong TaiKhoanProvider");
  return v;
}
```

`__root.tsx` (`RootComponent`): bọc phần `<a href="#noi-dung-chinh">…` tới `<Toaster/>` trong `<TaiKhoanProvider>` (bên trong `QueryClientProvider`; `RootComponent` là con của router nên `useNavigate` dùng được).

- [ ] **Step 2: `quay-lai.ts`** — thêm `export function dichQuayLaiTu(pathname: string): DichQuayLai { return locNext(pathname) ?? "/dung-thu"; }`.

- [ ] **Step 3: `DanhSachPhien.tsx`** — xoá `CotPhien`, sheet, nút "Phiên"; đổi `ThanDanhSach` thành `export function DanhSachPhien(props: Props)`; bỏ nút "Phiên mới" bên trong (AppShell có nút riêng) nhưng giữ prop `onPhienMoi` cho sheet mobile; giữ `MotPhien`, đổi tên/xoá, trạng thái tải/lỗi/rỗng.

- [ ] **Step 4: `TheTaiKhoan.tsx`, `MenuTaiKhoan.tsx`**

`TheTaiKhoan({ gon }: { gon: boolean })`: đọc `useTaiKhoan()`; vòng chữ cái đầu của `user.user_metadata.ten_hien_thi ?? user.user_metadata.ho_ten ?? user.email`; tên và nhãn `tenGoi(hanMuc.hanMuc?.plan ?? "free")`; `gon` (rail) chỉ vòng chữ; nút "Nâng cấp" (`moNangGoi`) ẩn khi plan là `pro`. Bấm thẻ mở `MenuTaiKhoan`.

`MenuTaiKhoan({ mo, onDong, nutMo }: { mo: boolean; onDong(): void; nutMo: RefObject<HTMLButtonElement | null> })`: popover định vị trên thẻ, `role="menu"`, mục `role="menuitem"`, đóng bằng Escape/click ngoài/chọn mục, trả tiêu điểm về `nutMo`. Đầu menu: tên + email + nhãn gói; `ThuocMucDung gon` cho `[mucRangBuoc(hanMuc)]` (nếu có); Pro: dòng "Còn N ngày · hết hạn DD/MM" (`soNgayCon`, `dinhDangMoc`), đỏ khi ≤7 kèm nút "Gia hạn" (`moNangGoi`). Mục: Hồ sơ → `/tai-khoan`; Nâng cấp gói → `moNangGoi()` (ẩn khi pro); Cá nhân hoá → `/tai-khoan/ca-nhan-hoa`; Trợ giúp → `/huong-dan`; Đăng xuất → `await signOut(); navigate({ to: "/" })`.

- [ ] **Step 5: `AppShell.tsx` viết lại** — giữ chữ ký, `useKhungModalDangMo`/`inert`, mốc `#noi-dung-chinh`.

```tsx
const NAV = [
  { to: "/dung-thu", label: "Trợ lý KLAW", icon: Sparkles },
  { to: "/tra-cuu", label: "Tra cứu luật", icon: BookOpenText },
  { to: "/soan-thao", label: "Soạn thảo", icon: FileSignature },
] as const;
```

Sidebar (`md+`, rộng ở `xl`): logo; nút "Phiên mới" (`SquarePen`, gọi `phienMoi()`; ở rail chỉ icon + `title`); NAV; khi `daDangNhap` và `xl`: tiêu đề "Gần đây" + `<DanhSachPhien hoiThoai={hoiThoai} phienDangMo={phienTrenUrl} onChon={(id) => navigate({ to: "/dung-thu", search: { phien: id } })} onPhienMoi={phienMoi} onDaXoa={(id) => { if (id === phienTrenUrl) phienMoi(); }} />` trong vùng `min-h-0 flex-1 overflow-y-auto` (`phienTrenUrl` = `useRouterState({ select: (s) => s.location.search })["phien"]` nếu là string, chỉ khi pathname là `/dung-thu`); chân: `daDangNhap` → `<TheTaiKhoan gon={!xl} />`; `laKhach` → (xl) thẻ mời "Đăng nhập để lưu phiên, hỏi tiếp nhiều ngày và soạn văn bản." + nút Đăng nhập (`Link /dang-nhap search={{ next: dichQuayLaiTu(pathname) }} onClick={catThreadTruocKhiRoi}`) và hai liên kết "Xem các gói dịch vụ" (`/bang-gia`), "Trợ giúp" (`/huong-dan`); `chuaCauHinh`/đang kiểm → khối cũ (KLAW là trợ lý pháp lý… Giới hạn · Nguồn dữ liệu). `xl` xác định bằng `matchMedia("(min-width: 80rem)")` (tái dùng khuôn `useHaiCot` trong `KhungDoiChieu.tsx` với ngưỡng 80rem — tách thành `useMinWidth(rem)` nếu tiện).

Header: nếu `laKhach` và không truyền `topRight` → góc phải hai nút: `Link /dang-nhap` (đặc, "Đăng nhập") và `Link /dang-ky` (viền, "Đăng ký miễn phí"), cả hai `search={{ next: dichQuayLaiTu(pathname) }}` và `onClick={catThreadTruocKhiRoi}`; nếu `daDangNhap` và `!xl` và pathname `/dung-thu` → nút "Phiên" (`MessageSquare`) mở sheet Gần đây (sheet dưới `role="dialog" aria-modal="true"`, lớp `rise-in`, khuôn `tra-cuu.index.tsx:807-838`).

Thanh dưới (`<md`): ba mục NAV + "Tài khoản" (`UserRound`) mở sheet: `daDangNhap` → các mục của `MenuTaiKhoan` dạng danh sách + Gần đây; `laKhach` → hai nút Đăng nhập/Đăng ký + hai liên kết. Mục "Hướng dẫn" rời NAV (Trợ giúp trong menu); `/huong-dan` vẫn dùng `AppShell active="/huong-dan"` — không mục nào sáng, chấp nhận.

- [ ] **Step 6: Xanh** — xoá import và khối mount `CotPhien` (dòng ~604–616) trong `dung-thu.tsx`; `npm run typecheck && npm run lint && npm run kiem-khung && npm run build && npx prettier --check src/contexts/tai-khoan.tsx src/components/app/AppShell.tsx src/components/tai-khoan/*.tsx src/components/klaw/DanhSachPhien.tsx src/routes/__root.tsx src/lib/quay-lai.ts src/routes/dung-thu.tsx`. Nếu `scripts/kiem-khung.ts` kiểm cấu trúc AppShell cũ, cập nhật kỳ vọng và ghi vào report.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/contexts/tai-khoan.tsx frontend/src/components/tai-khoan/TheTaiKhoan.tsx frontend/src/components/tai-khoan/MenuTaiKhoan.tsx frontend/src/components/app/AppShell.tsx frontend/src/components/klaw/DanhSachPhien.tsx frontend/src/routes/__root.tsx frontend/src/routes/dung-thu.tsx frontend/src/lib/quay-lai.ts frontend/scripts/kiem-khung.ts
git commit -m "feat(frontend): account provider and ChatGPT-style shell with recent sessions and account menu

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `/dung-thu` — khách, trần lượt mỗi phiên, 429, hết hạn Pro

**Files:**
- Create: `frontend/src/components/klaw/TheHetLuot.tsx`
- Modify: `frontend/src/routes/dung-thu.tsx`, `frontend/src/components/klaw/BaoLoi.tsx` (`onNangGoi?`, ẩn "Thử lại" khi 429), `frontend/src/components/klaw/TheDangNhap.tsx` (copy theo `next`)

**Interfaces:**
- Consumes: `useTaiKhoan` (Task 6), `mucRangBuoc`, `cauChip`, `phanTram`, `mucMau`, `soNgayCon`, `dinhDangMoc` (Task 5), `layThreadKhach/xoaThreadKhach`, `laNhapPhien`, `goi`.
- Produces: `TheHetLuot({ loai: "khach" | "phien" | "het_han"; chiTiet: string; onPhienMoi?: () => void; onNangGoi?: () => void; onCatThread?: () => void })`; `BaoLoi` prop `onNangGoi?: () => void`.

- [ ] **Step 1: Dọn** — xoá aside "Lịch sử phiên" trong bộ nhớ, `panelMo`, import `ChevronRight`, khối `TheDangNhap` khoá ô hỏi, `useAuth`, `useHoiThoai` trực tiếp; lấy `{ daDangNhap, laKhach, chuaCauHinh, dangKiemPhien, hoiThoai, hanMuc, moNangGoi, datHanhDongPhienMoi, datLayThreadKhach, catThreadTruocKhiRoi }` từ `useTaiKhoan()`. Bỏ nhánh `status === 403` "Xem bảng giá" trong khối `loiChiTiet` (chỉ còn `message` + "Phiên mới"). `dienGoiY` không chuyển tới đăng nhập nữa. Giữ nguyên `phienDangHien`, `daGhim`, `phienMoi` (bọc `useCallback([datLaiTraCuu, navigate])`), `thuLai`.

- [ ] **Step 2: Đăng ký với context**

```ts
useEffect(() => {
  datHanhDongPhienMoi(phienMoi);
  return () => datHanhDongPhienMoi(null);
}, [datHanhDongPhienMoi, phienMoi]);

useEffect(() => {
  datLayThreadKhach(() =>
    traCuu.cauHoi !== null && traCuu.ketQua !== null
      ? [...luuTru, { cauHoi: traCuu.cauHoi, ketQua: traCuu.ketQua }]
      : luuTru,
  );
  return () => datLayThreadKhach(null);
}, [datLayThreadKhach, luuTru, traCuu.cauHoi, traCuu.ketQua]);
```

- [ ] **Step 3: Mang đoạn chat khách vào tài khoản**

```ts
const daNhap = useRef(false);
const [loiNhap, datLoiNhap] = useState<string | null>(null);
const { taiLai: taiLaiPhien } = hoiThoai;
useEffect(() => {
  if (!daDangNhap || phienId !== undefined || daNhap.current) return;
  const t = layThreadKhach();
  if (t === null) return;
  daNhap.current = true;
  void goi("/hoi-thoai/nhap", laNhapPhien, {
    method: "POST",
    body: { luot: t.map((l) => ({ cau_hoi: l.cauHoi, tra_loi: l.ketQua, trace_id: l.ketQua.trace_id })) },
  }).then((kq) => {
    xoaThreadKhach();
    if (kq.ok) {
      taiLaiPhien();
      void navigate({ to: "/dung-thu", search: { phien: kq.data.id }, replace: true });
    } else datLoiNhap("Tôi chưa lưu được đoạn chat thử; bạn vẫn hỏi tiếp được.");
  });
}, [daDangNhap, phienId, navigate, taiLaiPhien]);
```

`loiNhap` hiện `role="status"` trên đầu dòng chat; xoá khi gửi câu mới.

- [ ] **Step 4: Trần lượt mỗi phiên, chip, ba thẻ**

```ts
const tranPhien = hanMuc.hanMuc?.phien.luot_toi_da ?? null; // khách 10, free 20, pro 50
const soLuotPhien = daTai.length + luuTru.length + (traCuu.ketQua !== null ? 1 : 0);
const phienDay = tranPhien !== null && soLuotPhien >= tranPhien;
const phienDai = tranPhien !== null && !phienDay && soLuotPhien >= Math.ceil(tranPhien * 0.75);
const mucChip = mucRangBuoc(hanMuc.hanMuc);
const hetLuot = mucChip !== null && mucChip.da_dung >= mucChip.han_muc;
const plan = hanMuc.hanMuc?.plan ?? null;
const hetHanPro = plan === "free" && hanMuc.hanMuc?.het_han_luc != null && Date.parse(hanMuc.hanMuc.het_han_luc) < Date.now();
```

Ô hỏi và nút gửi: `disabled={traCuu.dangChay || hoiThoai.loiChiTiet !== null || phienDay || hetLuot}`. Chip trong hàng composer (trước nút gửi): `mucChip !== null && <span className={cn("rounded-full px-2 py-0.5 text-[11px]", MAU_CHIP[mucMau(phanTram(mucChip))])} role="status">{cauChip(mucChip)}</span>`. Sau mỗi lượt kết thúc (`!traCuu.dangChay && traCuu.cauHoi !== null`) gọi `hanMuc.taiLai()` — với khách và tài khoản (effect hiện có gọi `hoiThoai.taiLai()` chỉ khi `daDangNhap`; tách thành hai effect).

Thẻ trong dòng chat:
- `phienDay` → `<TheHetLuot loai="phien" chiTiet={\`Phiên này đã đủ ${tranPhien} lượt. Mở phiên mới để tiếp tục.\`} onPhienMoi={phienMoi} />`; `phienDai` → `<p className="m-0 text-[12px] text-muted-foreground">Phiên dài rồi, mở phiên mới để câu trả lời bám sát hơn.</p>`.
- `hetLuot && laKhach` → `<TheHetLuot loai="khach" chiTiet="Bạn đã dùng 10 lượt thử. Đăng nhập miễn phí để tiếp tục, lưu đoạn chat này và có 200 lượt mỗi ngày." onCatThread={catThreadTruocKhiRoi} />` (bên trong: hai `Link` `/dang-nhap`, `/dang-ky` với `search={{ next: "/dung-thu" }}` và `onClick={onCatThread}`; số 10 lấy từ `mucChip.han_muc`).
- `traCuu.loi?.kind === "rate_limited"` → `BaoLoi loi={traCuu.loi} onNangGoi={plan === "free" ? moNangGoi : undefined}`; trong `BaoLoi`: ẩn nút "Thử lại" khi `kind === "rate_limited"`, hiện nút "Nâng cấp" khi có `onNangGoi`.
- `hetHanPro` → trên đầu dòng chat `<TheHetLuot loai="het_han" chiTiet={\`Gói Cá nhân đã hết hạn ngày ${dinhDangMoc(het_han_luc, mui_gio).slice(6)}. Gia hạn 30 ngày để tiếp tục hỏi không giới hạn và soạn 20 bản thảo mỗi ngày.\`} onNangGoi={moNangGoi} />`.

`TheHetLuot.tsx`: `<div role="status" className="rounded-xl border border-dashed border-border px-4 py-3">` + `<p>{chiTiet}</p>` + hàng nút theo `loai` (phien: "Phiên mới"; khach: "Đăng nhập" đặc + "Đăng ký miễn phí" viền; het_han: "Gia hạn 30 ngày"). Chữ chỉ qua text node.

- [ ] **Step 5: Khách và `?q=`** — effect `?q=` bỏ điều kiện `canDangNhap`. Khách (Supabase cấu hình, chưa đăng nhập) và ẩn danh dev đều gửi `lichSu: dungLichSu(luotTruoc)`; chỉ tài khoản gửi `hoiThoaiId`.

- [ ] **Step 6: Xanh** — `npm run typecheck && npm run lint && npm run kiem-lich-su && npm run kiem-sse && npm run build && npx prettier --check src/routes/dung-thu.tsx src/components/klaw/TheHetLuot.tsx src/components/klaw/BaoLoi.tsx src/components/klaw/TheDangNhap.tsx`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/routes/dung-thu.tsx frontend/src/components/klaw/TheHetLuot.tsx frontend/src/components/klaw/BaoLoi.tsx frontend/src/components/klaw/TheDangNhap.tsx
git commit -m "feat(frontend): guest trial in chat, per-session cap, quota chip and exhaustion cards

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: `/tai-khoan` (Hồ sơ), `/tai-khoan/ca-nhan-hoa`, bỏ Vai trò

**Files:**
- Create: `frontend/src/routes/tai-khoan.tsx`, `frontend/src/routes/tai-khoan.index.tsx`, `frontend/src/routes/tai-khoan.ca-nhan-hoa.tsx`, `frontend/src/components/tai-khoan/LichHoatDong.tsx`
- Modify: `frontend/src/lib/quay-lai.ts`, `frontend/scripts/kiem-quay-lai.ts`, `frontend/src/routes/dang-ky.tsx`, `frontend/src/routeTree.gen.ts` (tự sinh)

**Interfaces:**
- Consumes: `useTaiKhoan`, `useTaiMot` (`use-goi-api.ts`), `laHoSo`, `ThuocMucDung`, `soNgayCon`, `dinhDangMoc`, `tenGoi`, `supabase` (`@/integrations/supabase/client`), `dichQuayLaiTu`.
- Produces: routes `/tai-khoan`, `/tai-khoan/ca-nhan-hoa`; `DICH_QUAY_LAI = ["/dung-thu", "/soan-thao", "/tai-khoan", "/tai-khoan/ca-nhan-hoa"]`; `LichHoatDong({ hoatDong: { ngay: string; so_luot: number }[] })`.

- [ ] **Step 1: `quay-lai.ts` + kiểm** — mở rộng `DICH_QUAY_LAI`; `kiem-quay-lai.ts`: `assert.deepEqual([...DICH_QUAY_LAI], ["/dung-thu", "/soan-thao", "/tai-khoan", "/tai-khoan/ca-nhan-hoa"])` và `assert.equal(locNext("/tai-khoan/ca-nhan-hoa"), "/tai-khoan/ca-nhan-hoa")`. `npm run kiem-quay-lai` đỏ rồi xanh.

- [ ] **Step 2: Layout** `tai-khoan.tsx`

```tsx
import { Outlet, createFileRoute, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect } from "react";
import { AppShell } from "@/components/app/AppShell";
import { useTaiKhoan } from "@/contexts/tai-khoan";
import { dichQuayLaiTu } from "@/lib/quay-lai";

export const Route = createFileRoute("/tai-khoan")({
  component: TaiKhoanLayout,
  head: () => ({ meta: [{ title: "Tài khoản — KLAW" }] }),
});

function TaiKhoanLayout() {
  const { laKhach, dangKiemPhien } = useTaiKhoan();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  useEffect(() => {
    if (!dangKiemPhien && laKhach) void navigate({ to: "/dang-nhap", search: { next: dichQuayLaiTu(pathname) } });
  }, [laKhach, dangKiemPhien, navigate, pathname]);
  return (
    <AppShell active="/tai-khoan">
      <Outlet />
    </AppShell>
  );
}
```

- [ ] **Step 3: Hồ sơ** `tai-khoan.index.tsx` — `const hoSo = useTaiMot("/ho-so", laHoSo); const { hanMuc, moNangGoi, user } = useTaiKhoan();`. Bố cục trong `mx-auto max-w-3xl px-4 py-8`: thẻ định danh (vòng chữ cái, tên hiển thị `user?.user_metadata.ten_hien_thi` hoặc email, email, nhãn `ten_goi`, "Tham gia DD/MM/YYYY" từ `tao_luc`); Pro: "Còn N ngày · hết hạn DD/MM" (đỏ ≤7, nút Gia hạn → `moNangGoi`); Free đã hết hạn Pro (`het_han_luc` quá khứ): dòng "Gói Cá nhân đã hết hạn ngày DD/MM" + Gia hạn; `<ThuocMucDung muc={hanMuc.hanMuc?.muc ?? []} muiGio={hanMuc.hanMuc?.mui_gio ?? "Asia/Ho_Chi_Minh"} />`; bốn ô số: `so_phien` "Phiên", `tong_hoi_dap` "Lượt hỏi đáp", `tong_ban_thao` "Bản thảo", "30 ngày qua" = tổng `so_luot` của `hoat_dong` trong 30 ngày gần nhất; `<LichHoatDong hoatDong={hoSo.ketQua.hoat_dong} />`; bảng `phan_loai` (nhãn · số); nút "Nâng cấp" (Free) và "Cá nhân hoá". Trạng thái tải: ô xám `aria-hidden`; lỗi: `BaoLoi loi={hoSo.loi} onThuLai={…}`.

`LichHoatDong.tsx`: lưới 53 cột × 7 hàng (`grid grid-flow-col grid-rows-7 gap-[3px]`), tuần bắt đầu thứ Hai, 365 ngày lùi từ hôm nay (ngày theo chuỗi `ngay` `YYYY-MM-DD` của máy chủ, không dùng `Date` giờ máy để tính ngày trong ô); 5 mức: 0 → `bg-[var(--color-paper-200)]`, còn lại 4 mức theo tứ phân vị của `so_luot > 0` bằng `bg-[var(--color-brass-500)]/{25,50,75,100}`; ô `size-2.5 rounded-[2px]` với `title="07/09: 3 lượt"`; nhãn tháng dưới lưới, mỗi tháng một lần; `aria-label="Lịch hoạt động 52 tuần"`.

- [ ] **Step 4: Cá nhân hoá** `tai-khoan.ca-nhan-hoa.tsx`

```tsx
const { user } = useTaiKhoan();
const laEmail = user?.app_metadata?.["provider"] === "email";
const [ten, datTen] = useState(String(user?.user_metadata?.["ten_hien_thi"] ?? user?.user_metadata?.["ho_ten"] ?? ""));
async function luuTen() {
  const { error } = await supabase.auth.updateUser({ data: { ten_hien_thi: ten.trim() } });
  datThongBao(error ? `Tôi chưa lưu được tên: ${error.message}` : "Đã lưu tên hiển thị.");
}
async function doiMatKhau() {
  if (mk.length < 8 || mk !== mk2) { datThongBao("Mật khẩu cần ít nhất 8 ký tự và hai lần nhập giống nhau."); return; }
  const { error } = await supabase.auth.updateUser({ password: mk });
  if (error && /reauth|session|expired/i.test(error.message)) {
    void navigate({ to: "/dang-nhap", search: { next: "/tai-khoan/ca-nhan-hoa" } });
    return;
  }
  datThongBao(error ? `Tôi chưa đổi được mật khẩu: ${error.message}` : "Đã đổi mật khẩu.");
}
```

Form tên (1–60 ký tự, `maxLength={60}`), khối đổi mật khẩu chỉ khi `laEmail` (mật khẩu mới + nhập lại, `autoComplete="new-password"`), thông báo `role="status"`; dòng cuối "Xoá tài khoản và ngôn ngữ: sắp có." Sau lưu tên, `useAuth` nhận `USER_UPDATED` qua `onAuthStateChange` (session mới) → thẻ tài khoản đổi tên; nếu không, gọi `supabase.auth.refreshSession()` sau khi lưu.

- [ ] **Step 5: `dang-ky.tsx`** — xoá `ROLES` (dòng 51), trường `role` trong state `form` (108), khối `<label htmlFor="role">…</select>` (230–245). `dangKy(email, password, name)` không đổi.

- [ ] **Step 6: Xanh** — `npm run typecheck && npm run lint && npm run kiem-quay-lai && npm run build && npx prettier --check src/routes/tai-khoan.tsx src/routes/tai-khoan.index.tsx src/routes/tai-khoan.ca-nhan-hoa.tsx src/components/tai-khoan/LichHoatDong.tsx src/routes/dang-ky.tsx src/lib/quay-lai.ts scripts/kiem-quay-lai.ts`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/routes/tai-khoan.tsx frontend/src/routes/tai-khoan.index.tsx frontend/src/routes/tai-khoan.ca-nhan-hoa.tsx frontend/src/components/tai-khoan/LichHoatDong.tsx frontend/src/routes/dang-ky.tsx frontend/src/lib/quay-lai.ts frontend/scripts/kiem-quay-lai.ts frontend/src/routeTree.gen.ts
git commit -m "feat(frontend): account profile with activity calendar, personalization, drop role field

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: `ModalNangGoi` hai card và bảng giá

**Files:**
- Create: `frontend/src/components/tai-khoan/ModalNangGoi.tsx`
- Modify: `frontend/src/contexts/tai-khoan.tsx` (render `<ModalNangGoi />` trong provider), `frontend/src/routes/bang-gia.tsx`

**Interfaces:**
- Consumes: `useTaiKhoan` (`nangGoiMo`, `dongNangGoi`, `hanMuc`, `daDangNhap`, `moNangGoi`), `GOI_CARD`, `laYeuCauNangGoiHoacNull`, `laYeuCauNangGoi`, `soNgayCon`, `ThuocMucDung`, `useGoiApi`, `goi`.
- Produces: `ModalNangGoi()`; `/bang-gia` dùng `GOI_CARD` cho hai gói đầu và hiện `ThuocMucDung` sau đăng nhập.

- [ ] **Step 1: Modal** — `role="dialog" aria-modal="true" aria-labelledby="nang-goi-tieu-de"`, mở khi `nangGoiMo`; nền `bg-[var(--color-ink-950)]/45` click đóng; Escape đóng; nút X; tiêu điểm vào nút đóng khi mở, trả về `document.activeElement` lúc mở khi đóng. Khi mở: `useGoiApi<YeuCauNangGoi | null>` gọi `goi("/nang-goi/yeu-cau", laYeuCauNangGoiHoacNull)`. Hai card (`grid gap-4 md:grid-cols-2`) theo khuôn spec §7.5: nhãn nhỏ, tiêu đề `font-display text-2xl`, mô tả, giá lớn, nút, tiêu đề danh sách, `ul` icon + chữ.

```tsx
const plan = hanMuc.hanMuc?.plan ?? "free";
const hetHan = hanMuc.hanMuc?.het_han_luc ?? null;
const ngayCon = soNgayCon(hetHan);
const dangCho = yeuCau?.trang_thai === "cho_duyet";
// Card Cá nhân — nút:
//   plan === "free": dangCho ? khoá "Đang chờ duyệt" : đặc "Yêu cầu nâng lên Cá nhân" → POST { goi_muon: "pro" }
//   plan === "pro" && ngayCon !== null && ngayCon > 7: khoá "Gói hiện tại · còn {ngayCon} ngày"
//   plan === "pro" (ngayCon ≤ 7): dangCho ? khoá "Đang chờ duyệt" : đặc "Gia hạn 30 ngày" → POST { goi_muon: "pro" }
// Card Miễn phí — nút: plan === "free" ? khoá "Gói hiện tại của bạn" : không hiện.
```

POST qua `goi("/nang-goi/yeu-cau", laYeuCauNangGoi, { method: "POST", body: { goi_muon: "pro" } })`: 201 → `yeuCau` = data; 409 → tải lại GET; 422/khác → hiện `loi.message`. Dòng nhỏ dưới nút Cá nhân: "Chưa có thanh toán trực tuyến. Tôi sẽ báo qua email khi gói được mở." Khách (`laKhach`) mở modal → nút Cá nhân là `Link /dang-ky` "Đăng ký miễn phí để nâng gói". Render `<ModalNangGoi />` sau `{children}` trong `Ctx.Provider`.

- [ ] **Step 2: `bang-gia.tsx`** — `TIERS[0].features = GOI_CARD.free.danhSach.map((d) => d.chu)`, `TIERS[1].features = GOI_CARD.pro.danhSach.map((d) => d.chu)`; thêm trường `chuKy?: "30 ngày"` cho tier Cá nhân và hiển thị hậu tố "/ 30 ngày" thay "/ tháng" khi có; `COMPARISON` hàng "Phiên lưu" (~100): giá trị đầu `"Không giới hạn"`; FAQ hạn mức (~125) viết lại: "Gói Miễn phí có 200 lượt hỏi đáp mỗi ngày, 20 lượt mỗi phiên, 3 bản thảo mỗi ngày (20 mỗi tháng); đếm ở máy chủ theo tài khoản, đặt lại 0h giờ Việt Nam. Gói Cá nhân hỏi đáp không giới hạn trong sử dụng bình thường (lá chắn chống lạm dụng 500 lượt/ngày), 20 bản thảo mỗi ngày, hiệu lực 30 ngày. Chưa có thanh toán trực tuyến: bạn gửi yêu cầu, tôi duyệt và báo qua email."; chỗ `HanMucThang` cũ (~199): `const { hanMuc, daDangNhap, moNangGoi } = useTaiKhoan();` và `{hanMuc.hanMuc?.ap_dung && hanMuc.hanMuc.plan !== null && (<div className="soft-fade mx-auto mt-6 max-w-xl rounded-xl border border-border bg-card p-4 text-left"><p className="m-0 mb-2 text-[13px] font-semibold text-primary">Gói {hanMuc.hanMuc.ten_goi}</p><ThuocMucDung muc={hanMuc.hanMuc.muc} muiGio={hanMuc.hanMuc.mui_gio} /></div>)}`; CTA tier Cá nhân khi `daDangNhap` → nút gọi `moNangGoi()` ("Yêu cầu nâng lên Cá nhân") thay "Sắp ra mắt".

- [ ] **Step 3: Xanh** — `npm run typecheck && npm run lint && npm run build && npx prettier --check src/components/tai-khoan/ModalNangGoi.tsx src/contexts/tai-khoan.tsx src/routes/bang-gia.tsx`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/tai-khoan/ModalNangGoi.tsx frontend/src/contexts/tai-khoan.tsx frontend/src/routes/bang-gia.tsx
git commit -m "feat(frontend): two-card upgrade modal with request flow; pricing copy for quota v3

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Soạn thảo — khách phải đăng nhập, 429 có nút Nâng cấp

**Files:**
- Modify: nơi gọi `/soan-thao` (tìm bằng `grep -rn '"/soan-thao"' src` — dự kiến `frontend/src/components/soan-thao/KhongGianSoanThao.tsx` hoặc một hook/lib cạnh nó; sửa đúng một điểm quanh nút bắt đầu soạn và nơi hiện lỗi), `frontend/src/components/klaw/TheDangNhap.tsx` (copy theo `next`)

**Interfaces:**
- Consumes: `useTaiKhoan().laKhach`, `hanMuc`, `moNangGoi`; `BaoLoi onNangGoi` (Task 7); `TheDangNhap`.

- [ ] **Step 1** — Tìm nút bắt đầu soạn (`grep -n "onClick\|Soạn" <file>` quanh lời gọi `/soan-thao`). Nếu `laKhach`: thay nút đó bằng `<TheDangNhap next="/soan-thao" />` (một điểm; không đụng logic checklist/biểu mẫu). `TheDangNhap`: khi `next === "/soan-thao"` câu là "Đăng nhập để soạn văn bản. Tài khoản Miễn phí soạn được 3 bản thảo mỗi ngày."; các `next` khác giữ câu cũ.

- [ ] **Step 2** — Nơi hiện lỗi của lời gọi `/soan-thao`: nếu là `BaoLoi`, truyền `onNangGoi={hanMuc.hanMuc?.plan === "free" ? moNangGoi : undefined}` (429 có nút Nâng cấp); 401 khách hiện câu máy chủ ("Cần đăng nhập để soạn văn bản.") kèm liên kết đăng nhập (`BaoLoi` đã có cho `unauthorized`).

- [ ] **Step 3: Xanh** — `npm run typecheck && npm run lint && npm run build && npx prettier --check <các file đã sửa>`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/soan-thao/KhongGianSoanThao.tsx frontend/src/components/klaw/TheDangNhap.tsx
git commit -m "feat(frontend): drafting requires sign-in for guests; upgrade CTA on quota 429

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

(Nếu lời gọi `/soan-thao` nằm ở file khác, thêm file đó vào `git add` và ghi rõ trong report.)

---

# BƯỚC 3 — GỘP VÀ ĐÓNG (checkout chính)

### Task 11: Gộp hai nhánh, kiểm toàn bộ, Chrome, đóng plan

**Files:**
- Modify: `docs/plans/active/vo-ung-dung-va-tai-khoan.md` → `docs/plans/completed/`, plan này (tick), `.tham-dinh-shots/22-…29-….png`.

- [ ] **Step 1: Gộp**

```bash
git merge --no-ff wt-be-tk -m "merge: backend quotas v3, account endpoints, guest gate (wt-be-tk)" && git merge --no-ff wt-fe-tk -m "merge: frontend shell, account pages, guest mode (wt-fe-tk)"
git branch --merged HEAD | grep -E "wt-(be|fe)-tk"
git worktree remove --force ../KLAW-be4 && git worktree remove --force ../KLAW-fe4 && git branch -d wt-be-tk wt-fe-tk
```

- [ ] **Step 2: Kiểm toàn bộ**

```bash
.venv/bin/ruff check src/ tests/ && .venv/bin/python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py
cd frontend && npm run kiem
```

Kỳ vọng: pytest chỉ đỏ ở `test_moi_mau.py` bẩn; `npm run kiem` exit 0 (gồm `kiem-han-muc`, `kiem-quay-lai`).

- [ ] **Step 3: Khởi động lại backend** (uvicorn :8000 không có `--reload`): `kill $(lsof -ti tcp:8000)`; `KLAW_SUPABASE_URL=<project url> .venv/bin/uvicorn src.main:app --host 127.0.0.1 --port 8000 --log-level warning` (nền). Vite :3000 HMR tự cập nhật.

- [ ] **Step 4: Chrome khách** (cửa sổ ẩn danh, `http://localhost:3000/dung-thu`): header có "Đăng nhập" + "Đăng ký miễn phí", sidebar khách, chip "Còn 10/10 lượt thử"; hỏi một câu → chip giảm, Network có `X-Khach-Id`; tải lại → đoạn chat mất, chip vẫn 9; hạ tạm `khach.hoi_dap_24h: 2` (+ khởi động lại backend) → lượt 3 thấy thẻ hết lượt; bấm Đăng nhập từ thẻ (KHÔNG nhập thông tin đăng nhập, dừng ở màn đăng nhập; đường nhập thread đã có pytest). Trả YAML. Ảnh `22-khach-header-chip.png`, `23-khach-het-luot.png`.

- [ ] **Step 5: Chrome tài khoản** (tab đã đăng nhập của chủ dự án): sidebar (Phiên mới, Gần đây, thẻ tài khoản), menu tài khoản, `/tai-khoan` với lịch hoạt động, `/tai-khoan/ca-nhan-hoa` đổi tên hiển thị, modal nâng gói hai card → "Yêu cầu nâng lên Cá nhân" → "Đang chờ duyệt"; hạ tạm `goi.free.luot_moi_phien: 2` và `goi.free.hoi_dap_ngay: 2` (+ khởi động lại) để thấy thẻ đủ phiên và 429 có nút Nâng cấp; trả YAML. Duyệt tay: `UPDATE users SET plan='pro', plan_het_han = now() + interval '30 days' WHERE sub = '<sub>'` → thẻ "Cá nhân", menu "Còn 30 ngày"; `UPDATE users SET plan_het_han = now() - interval '1 day'` → thẻ "đã hết hạn" + Gia hạn; trả `plan='free', plan_het_han=NULL`, xoá dòng `yeu_cau_nang_goi` thử. Ảnh `24-sidebar-chatgpt.png`, `25-menu-tai-khoan.png`, `26-ho-so.png`, `27-modal-nang-goi.png`, `28-phien-day.png`, `29-het-han-pro.png`. Kiểm 375px: thanh dưới có Tài khoản, sheet mở.

- [ ] **Step 6: Đóng** — tick mọi `- [ ]` plan này; plan bền: Status Completed, Decisions (rulings ledger), Result (commit gộp, số test, ảnh), Nợ: admin duyệt yêu cầu (2B), xoá tài khoản, ngôn ngữ, trí nhớ (gói 3), Hướng dẫn rời NAV, `routes.py`/`bao_ve.py` vượt 800 dòng; `git mv` sang `completed/`; commit `docs(plans): close account-shell plan with evidence`.

---

## Tự soát plan (đã chạy khi viết)

- **Phủ spec**: §4.1 YAML → T1; §4.2 đếm/kiểm → T3; §4.3 gỡ ẩn → T2; §5 migration/`plan_hieu_luc` → T1; §6.1 → T3/T4; §6.2 → T4; §6.3 → T4 (+`loai`); §6.4 → T2; §7.1 → T6; §7.2 → T5/T6/T8; §7.3 → T7/T10; §7.4 → T8; §7.5 → T9; §7.6 → T9; §8.1–8.3 → T1/T3/T4/T5; §8.4 → T2/T4/T7; §8.5 → T6/T7/T8/T10; §9 → T3/T4 (401/404/409/422, text node); §10 → T1–T4 pytest, T5/T8 kiểm FE, T11 Chrome; §11 đo lường là vận hành (ghi nợ); §12 hai luồng — đúng cấu trúc plan.
- **Lệch spec có chủ ý**: `/han-muc.het_han_luc` và `/ho-so.het_han_luc` trả `users.plan_het_han` KHI CÓ (kể cả đã hết hạn, `plan` hiệu lực là free) để FE hiện thẻ "đã hết hạn" — spec §6.1 nói `null` với Free; sửa spec cho khớp. Thanh đo chỉ ba khoá `goi` (không có `luot_moi_phien`) — trần phiên nằm ở `phien.luot_toi_da`.
- **Nhất quán tên**: `han_muc/la_chan/moc_*/plan_hieu_luc(_tu)/khach_id_tu_request/KHACH_HEADER` (T1) ↔ T2–T4; `kiem_rate_limit(khoa, so_luot, cua_so_giay)`, `dem_luot`, `kiem_han_muc`, `mo_ta_muc`, `dem_cua_so`, `het_han_cua`, `ten_goi`, `xac_thuc_nguoi_goi_hoac_none`, `cong_bao_ve_khach` (T3) ↔ T4; `LOI_PHIEN_DAY`, `nhap_phien`, `danh_sach(sub, limit, offset)`, `dem_luot(id)` (T2) ↔ T4; FE `HanMuc/MucHanMuc/laHanMuc/laHoSo/laYeuCauNangGoi(HoacNull)/laNhapPhien` (T1) ↔ T5–T9; `useHanMuc/mucRangBuoc/cauChip/soNgayCon/dinhDangMoc/GOI_CARD/tenGoi` (T5) ↔ T6–T9; `useTaiKhoan` fields (T6) ↔ T7–T10.
