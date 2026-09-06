# Truy cập bằng tài khoản và dọn giao diện trả lời — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Một cửa vào trợ lý (gộp "Trò chuyện" vào `/dung-thu`), đăng nhập mới hỏi được, trang Tra cứu luôn có danh sách văn bản, và card trả lời chỉ dẫn luật còn hiệu lực.

**Architecture:** Backend thêm đúng một endpoint đọc `GET /van-ban` (danh sách văn bản theo bộ lọc, dùng lại `danh_gia_toan_bo` và kiểm giá trị lọc của `/tim-kiem`). Frontend: tách màn chào thành `ManChao`, xoá `KlawChat`, `/chat` chỉ còn redirect; `/dung-thu` khoá ô hỏi bằng `useAuth` khi Supabase đã cấu hình mà chưa có phiên; `TheKetQua` bỏ khối cảnh báo và danh sách trích dẫn, giữ một khối "Căn cứ" dự phòng; nhãn hiệu lực chuyển vào header `KhungDoiChieu`. Thi công tuần tự trên `feat/tro-ly-phap-luat` tại checkout chính.

**Tech Stack:** FastAPI + SQLAlchemy `text()` + pydantic v2 (backend); React 19 + TanStack Start/Router + Tailwind 4 + lucide-react (frontend, `exactOptionalPropertyTypes: true`); pytest (integration, fixture `client`); node check scripts `frontend/scripts/kiem-*.ts`.

**Spec:** `docs/superpowers/specs/2026-09-06-truy-cap-va-giao-dien-tra-loi-design.md`

## Global Constraints

- Card trả lời chỉ dẫn luật còn hiệu lực: không render `warnings[]`; căn cứ có `hieu_luc ∈ {het_hieu_luc, bi_thay_the}` (nhóm 4 theo `nhomHieuLuc`) không hiển thị ở đâu trong card; khối "Căn cứ" chỉ hiện khi văn xuôi không có thẻ nào bấm được.
- Backend KHÔNG đổi `warnings`/`citations`; `/van-ban` và `/tim-kiem` không bao giờ trả `documents.tinh_trang`.
- Chuỗi hiển thị trong `frontend/src/components/klaw/TheKetQua.tsx` phải qua `tests/test_agents/test_giong_tra_loi.py` (cấm: "hệ thống", "không diễn giải", "chưa đủ căn cứ", "truy hồi", "database", "để bạn tự đối chiếu", "máy chủ trả về"); giọng xưng "tôi".
- Thẻ khoá đăng nhập KHÔNG viết cứng số lượt ("50"); nguồn số là `config/han_muc.yaml` và `HanMucThang`.
- `next` sau đăng nhập chỉ nhận đúng `"/dung-thu"` hoặc `"/soan-thao"`; giá trị khác bị bỏ.
- Frontend: không thêm dependency; `exactOptionalPropertyTypes: true` (prop tuỳ chọn khai `?: T | undefined` khi truyền `undefined`).
- KHÔNG đụng: `frontend/src/routes/soan-thao.$loaiVanBan.tsx`; trong `dung-thu.tsx` giữ nguyên `Luot` (`<div className="mt-4">{children}</div>`) và state `dangMo`; trong `TheKetQua.tsx` giữ nhánh `if (loai === "partial_coverage")` — plan soạn-thảo-trong-chat neo vào đó.
- Không chạy `make check` / `make format`. Kiểm Python: `make lint` + pytest có đích + `ruff format --check <file .py đã sửa>` (ba file `src/main.py`, `src/services/db.py`, `src/agents/nodes/assemble.py` có lệch format từ trước — không phải việc của plan này). Pytest chạy FOREGROUND, `timeout` 600000, không để job nền khi kết thúc lượt.
- Chỉ `git add` file mình sửa. Không stage file bẩn có từ trước phiên: `docs/guide/chapter-*.md`, `docs/guide/*/_index.md`, `scripts/log_*.py`, `scripts/setup*.{sh,ps1}`, `README_boilerplate.md`, `src/services/checklist.py`, `tests/test_services/test_moi_mau.py`, `qh3.html`, `.impeccable/`, `eval/results/lexical_only-*.json`, `presentation/README.md`, `config/checklist_don_xin_nghi_viec.yaml`, `eval/datasets/golden_qa_candidates.yaml`, `.agents/`.
- Commit tiếng Anh, conventional, kèm dòng `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Lệnh npm chạy trong `frontend/`. `npm run build` sinh lại `src/routeTree.gen.ts` — commit cùng khi nó đổi.

---

## File Structure

| File | Trách nhiệm | Task |
|---|---|---|
| `src/api/routes_van_ban.py` | thêm `GET /van-ban` (danh sách văn bản theo bộ lọc) | 1 |
| `src/api/routes_tim_kiem.py` | `_kiem_gia_tri_loc` → `kiem_gia_tri_loc` (dùng chung) | 1 |
| `src/models/schemas.py` | `VanBanTomTat`, `DanhSachVanBanResponse` | 1 |
| `tests/test_api/test_danh_sach_van_ban.py` (mới) | test tích hợp endpoint | 1 |
| `docs/plans/active/truy-cap-va-giao-dien-tra-loi.md` (mới) | plan bền (AGENTS.md) | 1, 9 |
| `frontend/src/lib/trich-dan.ts` | bỏ `ghiChuHieuLuc`; thêm `canCuConHieuLuc`, `chiSoCuaThe`, `coTagBamDuoc` | 2 |
| `frontend/scripts/kiem-xep-trich-dan.ts` | kiểm ba hàm mới, bỏ kiểm `ghiChuHieuLuc` | 2 |
| `frontend/src/hooks/use-doi-chieu.ts` | `MoDoiChieu.hieuLuc` | 2 |
| `frontend/src/components/klaw/KhungDoiChieu.tsx` | prop `hieuLuc` + `BadgeHieuLuc` trong header | 2 |
| `frontend/src/routes/dung-thu.tsx` | truyền `hieuLuc` (2); `ManChao`, placeholder, miễn trừ (4); cổng đăng nhập (6) | 2, 4, 6 |
| `frontend/src/components/klaw/TheKetQua.tsx` | bỏ `KhoiCanhBao`, `DaiTrichDan`; thêm `KhoiCanCu`; `TheTrichDan` dùng `chiSoCuaThe` | 3 |
| `frontend/src/components/klaw/ManChao.tsx` (mới) | màn chào + bốn gợi ý | 4 |
| `frontend/src/routes/chat.tsx` | redirect sang `/dung-thu` | 5 |
| `frontend/src/components/KlawChat.tsx` | XOÁ | 5 |
| `frontend/src/components/app/AppShell.tsx`, `frontend/src/components/AppNav.tsx` | bỏ mục "Trò chuyện" | 5 |
| `frontend/src/routes/index.tsx`, `frontend/src/routes/huong-dan.tsx` | link `/chat` → `/dung-thu`, nhãn nút | 5 |
| `frontend/src/lib/quay-lai.ts` (mới), `frontend/scripts/kiem-quay-lai.ts` (mới), `frontend/package.json` | whitelist `next` | 6 |
| `frontend/src/components/klaw/TheDangNhap.tsx` (mới) | thẻ khoá ô hỏi | 6 |
| `frontend/src/routes/dang-nhap.tsx`, `frontend/src/routes/dang-ky.tsx` | `validateSearch` `next`, điều hướng, câu thành công | 6 |
| `frontend/src/routes/__root.tsx`, `frontend/src/lib/api.ts`, `frontend/src/components/klaw/BaoLoi.tsx`, `frontend/src/routes/bang-gia.tsx` | chữ "dùng thử", thông điệp 401 + link, bảng giá | 7 |
| `frontend/src/lib/klaw.ts` | `VanBanTomTat`, `DanhSachVanBan`, `laDanhSachVanBan` | 8 |
| `frontend/src/routes/tra-cuu.index.tsx` | chế độ duyệt kho khi ô từ khoá rỗng, `TheVanBan` | 8 |

Thứ tự (spec §8): Task 1 (BE) → 2, 3 (card) → 4, 5 (gộp chat) → 6, 7 (truy cập) → 8 (tra cứu FE) → 9 (đóng).

---

# BƯỚC A — BACKEND

### Task 1: `GET /van-ban` — danh sách văn bản theo bộ lọc

**Files:**
- Modify: `src/models/schemas.py` (chèn sau class `TimKiemResponse`, trước comment `# ══ GET /van-ban/{doc_id}/hieu-luc`)
- Modify: `src/api/routes_tim_kiem.py` (đổi tên `_kiem_gia_tri_loc` → `kiem_gia_tri_loc`, 1 def + 2 chỗ gọi)
- Modify: `src/api/routes_van_ban.py` (thêm SQL, hàm sync, route)
- Create: `tests/test_api/test_danh_sach_van_ban.py`
- Create: `docs/plans/active/truy-cap-va-giao-dien-tra-loi.md`

**Interfaces:**
- Consumes: `danh_gia_toan_bo(engine, as_of) -> dict[str, Effectivity]`, `bac_con_song(e) -> int` (`src/services/effectivity.py`); `_ra(e) -> HieuLucOut` (đã có trong `routes_van_ban.py`); `as_of_hieu_luc(date | None)`; `get_engine()`.
- Produces: `GET /api/v1/van-ban?loai[]&co_quan[]&tu_nam&den_nam&sap_xep&limit&offset&as_of_date` → `DanhSachVanBanResponse{tong, limit, offset, sap_xep, ket_qua: VanBanTomTat[]}`; `VanBanTomTat{doc_id, so_ky_hieu, bo_luat, loai_van_ban, co_quan_ban_hanh, ngay_ban_hanh, hieu_luc: HieuLucOut}`. Task 8 đọc đúng các tên này.

- [ ] **Step 1: Plan bền** — tạo `docs/plans/active/truy-cap-va-giao-dien-tra-loi.md`:

```markdown
# Execution Plan: Truy cập bằng tài khoản và dọn giao diện trả lời

Date: 2026-09-06

## Status

Active

## Spec / Plan

- docs/superpowers/specs/2026-09-06-truy-cap-va-giao-dien-tra-loi-design.md
- docs/superpowers/plans/2026-09-06-truy-cap-va-giao-dien-tra-loi.md

## Progress

- [ ] Task 1 GET /van-ban
- [ ] Task 2 nhãn hiệu lực sang KhungDoiChieu, helper căn cứ
- [ ] Task 3 TheKetQua chỉ luật còn hiệu lực
- [ ] Task 4 ManChao trong /dung-thu
- [ ] Task 5 xoá Trò chuyện, /chat redirect
- [ ] Task 6 khoá ô hỏi khi chưa đăng nhập, next=
- [ ] Task 7 chữ "dùng thử", 401, bảng giá
- [ ] Task 8 Tra cứu duyệt kho
- [ ] Task 9 kiểm chung, chụp màn, đóng plan

## Decisions

(ghi khi có)

## Result

(điền ở Task 9)
```

- [ ] **Step 2: Test đỏ** — `tests/test_api/test_danh_sach_van_ban.py`:

```python
"""`GET /api/v1/van-ban` — danh sách văn bản theo bộ lọc, KHÔNG cần từ khoá.

Tồn tại vì trang Tra cứu tick "Nghị định" (696) mà ô từ khoá rỗng thì trước
đây trống: `/tim-kiem` bắt buộc `q`. Cùng ba bất biến với `/tim-kiem`: giá trị
lọc lạ → 422 nêu giá trị thật; `hieu_luc` là phán quyết KLAW, không bao giờ
`documents.tinh_trang`; chỉ văn bản có toàn văn (`depth <> 'metadata'`), cùng
tập mà `/bo-loc` đếm.
"""

import pytest

BAC = {"con_hieu_luc": 0, "het_hieu_luc": 2, "bi_thay_the": 2}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_mac_dinh_20_dong_moi_nhat(client):
    r = await client.get("/api/v1/van-ban")
    assert r.status_code == 200
    d = r.json()
    assert d["sap_xep"] == "moi_nhat" and d["limit"] == 20 and d["offset"] == 0
    assert d["tong"] > 0
    assert len(d["ket_qua"]) == min(20, d["tong"])
    ngay = [k["ngay_ban_hanh"] for k in d["ket_qua"] if k["ngay_ban_hanh"] is not None]
    assert ngay == sorted(ngay, reverse=True), "moi_nhat phải giảm dần theo ngày ban hành"
    k = d["ket_qua"][0]
    for truong in ("doc_id", "so_ky_hieu", "bo_luat", "loai_van_ban", "co_quan_ban_hanh",
                   "ngay_ban_hanh", "hieu_luc"):
        assert truong in k, f"thiếu {truong} — FE không dựng được dòng"
    assert "tinh_trang" not in k and "tinh_trang" not in d


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_tong_khop_bo_loc(client):
    bo_loc = (await client.get("/api/v1/bo-loc")).json()
    loai = bo_loc["loai_van_ban"][0]
    r = await client.get("/api/v1/van-ban", params={"loai": loai["gia_tri"]})
    assert r.status_code == 200
    d = r.json()
    # Cùng tập `depth <> 'metadata'` với `/bo-loc`, nên con số phải TRÙNG — đây
    # là con số người dùng thấy cạnh ô tick, và họ đếm được dòng.
    assert d["tong"] == loai["so_van_ban"]
    assert all(k["loai_van_ban"] == loai["gia_tri"] for k in d["ket_qua"])
    khong_loc = (await client.get("/api/v1/van-ban")).json()
    assert khong_loc["tong"] == bo_loc["tong_van_ban"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_loc_theo_nam_va_phan_trang(client):
    r = await client.get("/api/v1/van-ban", params={"tu_nam": 2019, "den_nam": 2019, "limit": 5})
    assert r.status_code == 200
    d = r.json()
    assert all((k["ngay_ban_hanh"] or "2019")[:4] == "2019" for k in d["ket_qua"])
    trang2 = (await client.get(
        "/api/v1/van-ban", params={"tu_nam": 2019, "den_nam": 2019, "limit": 5, "offset": 5}
    )).json()
    ids1 = {k["doc_id"] for k in d["ket_qua"]}
    ids2 = {k["doc_id"] for k in trang2["ket_qua"]}
    assert ids1.isdisjoint(ids2), "hai trang không được lặp văn bản"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_con_hieu_luc_truoc_xep_theo_bac(client):
    r = await client.get("/api/v1/van-ban", params={"sap_xep": "con_hieu_luc_truoc", "limit": 50})
    assert r.status_code == 200
    bac = [BAC.get(k["hieu_luc"]["verdict"], 1) for k in r.json()["ket_qua"]]
    assert bac == sorted(bac), "còn hiệu lực → chưa rõ → đã chết, không trộn"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_van_ban_tu_choi_tham_so_sai(client):
    assert (await client.get("/api/v1/van-ban", params={"tu_nam": 2020, "den_nam": 2019})).status_code == 422
    assert (await client.get("/api/v1/van-ban", params={"limit": 51})).status_code == 422
    assert (await client.get("/api/v1/van-ban", params={"sap_xep": "lien_quan"})).status_code == 422
    r = await client.get("/api/v1/van-ban", params={"loai": "Loại bịa"})
    assert r.status_code == 422
    assert "Giá trị thật" in r.json()["detail"]
```

- [ ] **Step 3: Chạy đỏ**

```bash
python -m pytest tests/test_api/test_danh_sach_van_ban.py -q
```

Expected: 5 FAIL (404 vì route chưa có).

- [ ] **Step 4: Schemas** — chèn vào `src/models/schemas.py` ngay sau class `TimKiemResponse`:

```python
# ══ GET /van-ban — danh sách văn bản theo bộ lọc (duyệt kho, không từ khoá) ═══
class VanBanTomTat(BaseModel):
    """Một dòng của `GET /van-ban`. `hieu_luc` là phán quyết KLAW cấp văn bản
    (`effectivity.danh_gia_toan_bo`), KHÔNG PHẢI `documents.tinh_trang`."""

    doc_id: str
    so_ky_hieu: str
    bo_luat: str
    loai_van_ban: str
    co_quan_ban_hanh: str | None
    ngay_ban_hanh: date | None
    hieu_luc: HieuLucOut


class DanhSachVanBanResponse(BaseModel):
    # `tong` của TOÀN tập khớp bộ lọc, không phải của trang — trang Tra cứu hiện
    # "696 văn bản · Nghị định" và phải trùng số cạnh ô tick của `/bo-loc`.
    tong: int
    limit: int
    offset: int
    sap_xep: str
    ket_qua: list[VanBanTomTat]
```

(`HieuLucOut` được khai ở dưới `TimKiemResponse` trong file — nếu vậy đặt hai class mới NGAY SAU `HieuLucOut` để không tham chiếu trước khai báo.)

- [ ] **Step 5: Đổi tên helper dùng chung** — trong `src/api/routes_tim_kiem.py`, `_kiem_gia_tri_loc` → `kiem_gia_tri_loc` (def + hai chỗ gọi trong `_tim_kiem_sync`). Không đổi thân hàm.

- [ ] **Step 6: Endpoint** — `src/api/routes_van_ban.py`. Thêm import:

```python
from typing import Literal

from src.api.routes_tim_kiem import kiem_gia_tri_loc
from src.models.schemas import DanhSachVanBanResponse, VanBanTomTat  # gộp vào import sẵn có
from src.services.effectivity import bac_con_song, danh_gia_toan_bo  # gộp vào import sẵn có
```

Thêm sau `_ra`:

```python
# ── GET /van-ban — duyệt kho theo bộ lọc, không từ khoá ──────────────────────
#
# Cùng bốn mệnh đề lọc với `loc` trong `/tim-kiem` để một chip lọc cho ra cùng
# tập ở hai chế độ. `depth <> 'metadata'` là tập `/bo-loc` đếm: văn bản chỉ có
# thông tin không mở được nguyên văn nên không nằm trong danh sách bấm được.
_LOC_VAN_BAN = (
    " FROM documents d"
    " WHERE d.depth <> 'metadata'"
    "   AND (CAST(:loai AS text[]) IS NULL OR d.loai_van_ban = ANY(CAST(:loai AS text[])))"
    "   AND (CAST(:co_quan AS text[]) IS NULL"
    "        OR d.co_quan_ban_hanh = ANY(CAST(:co_quan AS text[])))"
    "   AND (CAST(:tu_ngay AS date) IS NULL OR d.ngay_ban_hanh >= CAST(:tu_ngay AS date))"
    "   AND (CAST(:den_ngay AS date) IS NULL OR d.ngay_ban_hanh <= CAST(:den_ngay AS date))"
)
_SQL_DEM_VAN_BAN = text("SELECT count(*)::int AS tong" + _LOC_VAN_BAN)
_COT_VAN_BAN = (
    "SELECT d.id AS doc_id, d.so_ky_hieu, d.ten AS bo_luat, d.loai_van_ban,"
    " d.co_quan_ban_hanh, d.ngay_ban_hanh"
)
# Chốt đuôi `d.id` ở mọi nhánh: ORDER BY không tất định thì hai trang lặp/sót.
_SAP_XEP_VAN_BAN = {
    "moi_nhat": " ORDER BY d.ngay_ban_hanh DESC NULLS LAST, d.so_ky_hieu, d.id",
    "con_hieu_luc_truoc": (
        " ORDER BY array_position(CAST(:thu_tu_doc AS text[]), d.id),"
        " d.ngay_ban_hanh DESC NULLS LAST, d.so_ky_hieu, d.id"
    ),
}
_SQL_TRANG_VAN_BAN = {
    k: text(_COT_VAN_BAN + _LOC_VAN_BAN + v + " LIMIT :limit OFFSET :offset")
    for k, v in _SAP_XEP_VAN_BAN.items()
}
SapXepVanBan = Literal["moi_nhat", "con_hieu_luc_truoc"]
_THIEU = HieuLucOut(
    verdict="chua_xac_dinh", tin_cay="thap",
    ly_do="không đánh giá được hiệu lực của văn bản này",
)


def _danh_sach_van_ban_sync(
    loai: list[str] | None, co_quan: list[str] | None,
    tu_nam: int | None, den_nam: int | None, sap_xep: str,
    limit: int, offset: int, as_of: date,
) -> DanhSachVanBanResponse:
    tham_so: dict = {
        "loai": loai,
        "co_quan": co_quan,
        "tu_ngay": date(tu_nam, 1, 1) if tu_nam else None,
        "den_ngay": date(den_nam, 12, 31) if den_nam else None,
    }
    # TRƯỚC `connect()`, như `/tim-kiem`: `danh_gia_toan_bo` tự mở connection.
    eff = danh_gia_toan_bo(get_engine(), as_of)
    with get_engine().connect() as c:
        kiem_gia_tri_loc(c, "loai_van_ban", loai)
        kiem_gia_tri_loc(c, "co_quan_ban_hanh", co_quan)
        tong = c.execute(_SQL_DEM_VAN_BAN, tham_so).mappings().one()["tong"]
        if sap_xep == "con_hieu_luc_truoc":
            tham_so["thu_tu_doc"] = [
                doc_id for doc_id, e in sorted(eff.items(), key=lambda kv: bac_con_song(kv[1]))
            ]
        rows = c.execute(
            _SQL_TRANG_VAN_BAN[sap_xep], {**tham_so, "limit": limit, "offset": offset}
        ).mappings().all()
    return DanhSachVanBanResponse(
        tong=tong, limit=limit, offset=offset, sap_xep=sap_xep,
        ket_qua=[
            VanBanTomTat(
                doc_id=r["doc_id"], so_ky_hieu=r["so_ky_hieu"], bo_luat=r["bo_luat"],
                loai_van_ban=r["loai_van_ban"], co_quan_ban_hanh=r["co_quan_ban_hanh"],
                ngay_ban_hanh=r["ngay_ban_hanh"],
                hieu_luc=_ra(e) if (e := eff.get(r["doc_id"])) is not None else _THIEU,
            )
            for r in rows
        ],
    )


@router.get("/van-ban", response_model=DanhSachVanBanResponse)
async def danh_sach_van_ban(
    loai: list[str] | None = Query(default=None),
    co_quan: list[str] | None = Query(default=None),
    tu_nam: int | None = Query(default=None, ge=1900, le=2100),
    den_nam: int | None = Query(default=None, ge=1900, le=2100),
    sap_xep: SapXepVanBan = "moi_nhat",
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    as_of_date: date | None = None,
) -> DanhSachVanBanResponse:
    """Danh sách văn bản có toàn văn theo bộ lọc, cho trang Tra cứu khi ô từ
    khoá rỗng (spec 2026-09-06 §6). Không LLM ⇒ không `cong_bao_ve`. Không có
    `lien_quan`: không có từ khoá thì không có gì để xếp theo độ liên quan."""
    if tu_nam and den_nam and tu_nam > den_nam:
        raise HTTPException(
            status_code=422, detail=f"tu_nam ({tu_nam}) lớn hơn den_nam ({den_nam})"
        )
    return await run_in_threadpool(
        _danh_sach_van_ban_sync, loai, co_quan, tu_nam, den_nam, sap_xep, limit, offset,
        as_of_hieu_luc(as_of_date),
    )
```

- [ ] **Step 7: Xanh**

```bash
make lint && ruff format --check src/api/routes_van_ban.py src/api/routes_tim_kiem.py src/models/schemas.py tests/test_api/test_danh_sach_van_ban.py && python -m pytest tests/test_api/test_danh_sach_van_ban.py tests/test_api/test_tim_kiem.py tests/test_api/test_hieu_luc.py -q
```

Expected: PASS toàn bộ.

- [ ] **Step 8: Commit**

```bash
git add src/api/routes_van_ban.py src/api/routes_tim_kiem.py src/models/schemas.py tests/test_api/test_danh_sach_van_ban.py docs/plans/active/truy-cap-va-giao-dien-tra-loi.md
git commit -m "feat(api): list documents by filter for browse mode (GET /van-ban)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

# BƯỚC B — CARD TRẢ LỜI CHỈ DẪN LUẬT CÒN HIỆU LỰC

### Task 2: Helper căn cứ + nhãn hiệu lực vào `KhungDoiChieu`

**Files:**
- Modify: `frontend/src/lib/trich-dan.ts` (bỏ `ghiChuHieuLuc`; thêm `canCuConHieuLuc`, `chiSoCuaThe`, `coTagBamDuoc`)
- Modify: `frontend/scripts/kiem-xep-trich-dan.ts` (bỏ mục 7 `ghiChuHieuLuc`, thêm mục 7–8 mới)
- Modify: `frontend/src/hooks/use-doi-chieu.ts` (`MoDoiChieu.hieuLuc`)
- Modify: `frontend/src/components/klaw/KhungDoiChieu.tsx` (prop `hieuLuc`, `BadgeHieuLuc` trong header)
- Modify: `frontend/src/routes/dung-thu.tsx` (`chonTrichDan` truyền `hieuLuc`; call site `KhungDoiChieu`)

**Interfaces:**
- Consumes: `xepTrichDan<T>(citations) -> { trichDan: T; chiSoGoc: number }[]`, `nhomHieuLuc(hieuLuc) -> 1|2|3|4`, `chiSoDauCuaVanBan(citations, docId) -> number` (đã có trong `trich-dan.ts`); `catManh(chu) -> Manh[]` với `Manh = { kieu: "chu"; chu } | { kieu: "the"; chu; loai: "cite" | "doc"; khoa: string }` (`lib/van-xuoi.ts`); `Citation.k: number | null`, `Citation.doc_id`, `Citation.hieu_luc: HieuLuc | null` (`lib/klaw.ts`).
- Produces: `canCuConHieuLuc(citations: readonly Citation[]) -> { trichDan: Citation; chiSoGoc: number }[]`; `chiSoCuaThe(manh: Extract<Manh, { kieu: "the" }>, citations: readonly Citation[]) -> number` (−1 khi không trỏ được); `coTagBamDuoc(answer: string | null, citations: readonly Citation[]) -> boolean`; `MoDoiChieu.hieuLuc?: string | null`; `KhungDoiChieuProps.hieuLuc?: string | null`. Task 3 dùng ba hàm đầu.

- [ ] **Step 1: Kiểm đỏ** — trong `frontend/scripts/kiem-xep-trich-dan.ts`: đổi dòng import 18 thành

```ts
import { canCuConHieuLuc, coTagBamDuoc, nhomHieuLuc, xepTrichDan } from "../src/lib/trich-dan.ts";
import type { Citation } from "../src/lib/klaw.ts";
```

Xoá trọn mục 7 (`ghiChuHieuLuc`, các dòng comment từ "// 7." tới hết bốn `assert` của nó). Thêm cuối file, trước dòng `console.info` tổng kết (nếu có; không có thì thêm cuối):

```ts
// Dựng Citation đủ trường — `canCuConHieuLuc`/`coTagBamDuoc` nhận kiểu thật.
const trich = (so_ky_hieu: string, hieu_luc: string | null, them: Partial<Citation> = {}): Citation => ({
  provision_id: 1,
  khop_tai_id: 1,
  doc_id: "d",
  duong_dan: `${so_ky_hieu} > Điều 1`,
  bo_luat: "Bộ luật",
  so_ky_hieu,
  quote: "…",
  hieu_luc: hieu_luc as Citation["hieu_luc"],
  tin_cay: null,
  k: null,
  ...them,
});

// 7. `canCuConHieuLuc` bỏ nhóm 4 (hết hiệu lực / bị thay thế) nhưng giữ chỉ số
//    GỐC — nút "Căn cứ" mở khung theo chỉ số trong `citations` thật.
{
  const cs = [trich("A", "het_hieu_luc"), trich("B", "con_hieu_luc"), trich("C", "bi_thay_the"), trich("D", null)];
  const con = canCuConHieuLuc(cs);
  assert.deepEqual(con.map((m) => m.trichDan.so_ky_hieu), ["B", "D"]);
  assert.deepEqual(con.map((m) => m.chiSoGoc), [1, 3]);
}

// 8. `coTagBamDuoc`: thẻ cite trỏ đúng `k`, thẻ doc trỏ đúng `doc_id`; thẻ trỏ
//    lệch hoặc không có thẻ → false — khi đó card mới hiện khối "Căn cứ".
{
  const cs = [trich("B", "con_hieu_luc", { k: 1, doc_id: "d1" })];
  assert.equal(coTagBamDuoc("xem [Điều 1](cite:1).", cs), true);
  assert.equal(coTagBamDuoc("xem [Luật](doc:d1).", cs), true);
  assert.equal(coTagBamDuoc("xem [Điều 9](cite:9) và [X](doc:khac).", cs), false);
  assert.equal(coTagBamDuoc("không có thẻ nào", cs), false);
  assert.equal(coTagBamDuoc(null, cs), false);
}
```

(Nếu `Citation` có trường khác ngoài danh sách trên, thêm vào `trich` với giá trị rỗng hợp kiểu — đọc `interface Citation` ở `lib/klaw.ts:56`.)

- [ ] **Step 2: Đỏ** — `node scripts/kiem-xep-trich-dan.ts` → lỗi import.

- [ ] **Step 3: `lib/trich-dan.ts`** — xoá `export function ghiChuHieuLuc` (và hằng/regex chỉ nó dùng). Thêm import `import { catManh, type Manh } from "./van-xuoi";` và cuối file:

```ts
/**
 * Căn cứ được hiện trong card: bỏ nhóm 4 (hết hiệu lực / bị thay thế) — spec
 * 2026-09-06 §7: câu trả lời chỉ dẫn luật còn hiệu lực. Giữ `chiSoGoc` để nút
 * mở đúng khung theo chỉ số trong `citations` thật.
 */
export function canCuConHieuLuc(
  citations: readonly Citation[],
): { trichDan: Citation; chiSoGoc: number }[] {
  return xepTrichDan(citations).filter((m) => nhomHieuLuc(m.trichDan.hieu_luc) !== 4);
}

/** Chỉ số citation mà một thẻ trỏ tới; −1 khi không trỏ được. Dùng chung cho
 * nút thẻ trong văn xuôi và cho `coTagBamDuoc`, để hai chỗ không lệch nhau. */
export function chiSoCuaThe(
  manh: Extract<Manh, { kieu: "the" }>,
  citations: readonly Citation[],
): number {
  return manh.loai === "cite"
    ? citations.findIndex((c) => c.k === Number(manh.khoa))
    : chiSoDauCuaVanBan(citations, manh.khoa);
}

/** Văn xuôi có ít nhất một thẻ bấm được? `catManh` chạy trên toàn `answer`:
 * nó chỉ tách thẻ, không cần tách đoạn trước. */
export function coTagBamDuoc(answer: string | null, citations: readonly Citation[]): boolean {
  if (answer === null) return false;
  return catManh(answer).some((m) => m.kieu === "the" && chiSoCuaThe(m, citations) >= 0);
}
```

Kiểm vòng import: `lib/van-xuoi.ts` không được import `trich-dan.ts` (grep; nếu có, chuyển `chiSoCuaThe`/`coTagBamDuoc` sang `van-xuoi.ts` và ghi vào báo cáo).

- [ ] **Step 4: `hooks/use-doi-chieu.ts`** — trong `interface MoDoiChieu` thêm:

```ts
  /** Nhãn hiệu lực của căn cứ đang mở — hiện ở header khung (spec 2026-09-06 §7). */
  hieuLuc?: string | null;
```

- [ ] **Step 5: `KhungDoiChieu.tsx`** — import `import { BadgeHieuLuc } from "./BadgeHieuLuc";`. Trong `KhungDoiChieuProps` thêm `hieuLuc?: string | null;`; destructure `hieuLuc = null`. Trong header, ngay sau `<span className="font-jetbrains block text-[13px] text-foreground">{vanBan?.so_ky_hieu ?? ""}</span>`:

```tsx
            {/* Nhãn hiệu lực ở ĐÂY, không ở card: câu trả lời chỉ dẫn luật còn
                hiệu lực (spec 2026-09-06 §7), nên ai mở nguyên văn mới cần biết
                văn bản này đang ở trạng thái nào. `BadgeHieuLuc` tự ẩn khi null. */}
            <BadgeHieuLuc hieuLuc={hieuLuc} gonGang className="mt-1" />
```

- [ ] **Step 6: `dung-thu.tsx`** — trong `chonTrichDan`, object truyền `doiChieu.mo({...})` thêm `hieuLuc: trichDan.hieu_luc,`. Ở call site `<KhungDoiChieu …>` thêm `hieuLuc={doiChieu.dang.hieuLuc ?? null}`.

- [ ] **Step 7: Xanh**

```bash
node scripts/kiem-xep-trich-dan.ts && npm run typecheck && npm run lint
```

Typecheck sẽ ĐỎ ở `TheKetQua.tsx` vì import `ghiChuHieuLuc` không còn — Task 3 sửa. Để Task 2 tự xanh: trong `TheKetQua.tsx` chỉ xoá `ghiChuHieuLuc` khỏi dòng import và xoá đúng khối `{...(trichDan.hieu_luc === "chua_hieu_luc" ? (() => {…})() : {})}` trong `chip` của `DaiTrichDan` (giữ `<BadgeHieuLuc hieuLuc={trichDan.hieu_luc} className="mt-1.5" />`). Không sửa gì khác ở file đó trong task này.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/trich-dan.ts frontend/scripts/kiem-xep-trich-dan.ts frontend/src/hooks/use-doi-chieu.ts frontend/src/components/klaw/KhungDoiChieu.tsx frontend/src/routes/dung-thu.tsx frontend/src/components/klaw/TheKetQua.tsx
git commit -m "feat(fe): show effectivity badge in the side panel; add in-force citation helpers

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `TheKetQua` — bỏ cảnh báo và danh sách trích dẫn, thêm khối "Căn cứ"

**Files:**
- Modify: `frontend/src/components/klaw/TheKetQua.tsx`

**Interfaces:**
- Consumes: `canCuConHieuLuc`, `chiSoCuaThe`, `coTagBamDuoc` (Task 2).
- Produces: không đổi API component. Nhánh `if (loai === "partial_coverage")` và `TheKetQuaProps` giữ nguyên tên/vị trí.

- [ ] **Step 1: Mốc** — `python -m pytest tests/test_agents/test_giong_tra_loi.py -q` xanh; ghi số test.

- [ ] **Step 2: Xoá** trong `TheKetQua.tsx`:
  - hàm `KhoiCanhBao` (từ comment "Cảnh báo hiệu lực — KHÔNG BAO GIỜ giấu…" tới hết hàm) và bốn chỗ gọi `<KhoiCanhBao warnings={warnings} />` (nhánh abstain, out_of_scope, partial_coverage, mặc định);
  - hàm `DaiTrichDan` (từ `function DaiTrichDan({` tới `</section>\n  );\n}` của nó) và hai chỗ gọi;
  - `warnings` khỏi destructure trong `NoiDungKetQua` (không còn ai đọc);
  - `useState` khỏi import react nếu không còn dùng; `nhomHieuLuc`, `xepTrichDan` khỏi import `trich-dan` (thay bằng ba hàm mới); `BadgeHieuLuc` import nếu không còn dùng.

- [ ] **Step 3: `TheTrichDan`** — thay hai dòng tính `chiSo` bằng `const chiSo = chiSoCuaThe(manh, ketQua.citations);`.

- [ ] **Step 4: Thêm `KhoiCanCu`** (đặt chỗ `DaiTrichDan` cũ):

```tsx
/**
 * Chốt an toàn cho căn cứ (spec 2026-09-06 §7.1): chỉ hiện khi văn xuôi KHÔNG
 * có thẻ nào bấm được — mô hình quên gắn thẻ thì bằng chứng vẫn còn đường mở.
 * Chỉ căn cứ còn hiệu lực; nhóm đã hết hiệu lực/bị thay thế không hiện ở đâu
 * trong card. Không nhãn hiệu lực ở đây: nhãn nằm trong khung khi mở.
 */
function KhoiCanCu({
  ketQua,
  chiSoDangMo,
  onChon,
}: {
  ketQua: TraCuuKetQua;
  chiSoDangMo: number | null;
  onChon: (chiSo: number) => void;
}) {
  if (coTagBamDuoc(ketQua.answer, ketQua.citations)) return null;
  const canCu = canCuConHieuLuc(ketQua.citations);
  if (canCu.length === 0) return null;
  return (
    <section aria-label="Căn cứ" className="mt-4">
      <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">Căn cứ</h3>
      <ul className="mt-2 mb-0 flex list-none flex-col gap-2 p-0">
        {canCu.map(({ trichDan, chiSoGoc }) => (
          <li key={`${trichDan.doc_id}-${trichDan.khop_tai_id}`}>
            <button
              type="button"
              onClick={() => onChon(chiSoGoc)}
              aria-expanded={chiSoDangMo === chiSoGoc}
              className={cn(
                "focus-brass block w-full cursor-pointer rounded-lg border p-3 text-left transition-colors",
                chiSoDangMo === chiSoGoc
                  ? "border-[var(--ring)] bg-[var(--color-paper-100)]"
                  : "border-border bg-card hover:bg-[var(--color-paper-50)]",
              )}
            >
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="font-jetbrains text-[13px] text-foreground">{trichDan.so_ky_hieu}</span>
                <span className="text-[13px] text-muted-foreground">{trichDan.duong_dan}</span>
              </span>
              <span className="serif-body mt-1.5 block text-[14px] leading-6 text-foreground">
                “{trichDan.quote}”
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

Chỗ gọi: nhánh `partial_coverage` (thay `<DaiTrichDan …/>`) và nhánh mặc định (thay `<DaiTrichDan …/>`, giữ `<KhoiLienKet documents={ketQua.documents} />` ngay trước):

```tsx
      <KhoiCanCu ketQua={ketQua} chiSoDangMo={chiSoDangMo} onChon={chon} />
```

- [ ] **Step 5: Câu khi `answer` rỗng** — chuỗi "Lượt này tôi đối chiếu được trích dẫn nhưng chưa viết ra được lời giải thích. Bạn đọc nguyên văn các điều khoản ngay dưới đây." giữ nguyên: khi `answer` rỗng thì `coTagBamDuoc` là false nên `KhoiCanCu` hiện đúng "ngay dưới đây".

- [ ] **Step 6: Xanh**

```bash
npm run typecheck && npm run lint && node scripts/kiem-trich-dan.ts && node scripts/kiem-van-xuoi.ts && cd .. && python -m pytest tests/test_agents/test_giong_tra_loi.py -q && grep -c "KhoiCanhBao\|DaiTrichDan\|warnings" frontend/src/components/klaw/TheKetQua.tsx
```

Expected: xanh; `grep -c` ra `0` (không còn tham chiếu nào tới ba tên đó).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/klaw/TheKetQua.tsx
git commit -m "feat(fe): answer card shows in-force law only; drop warning block and citation list

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

# BƯỚC C — GỘP "TRÒ CHUYỆN" VÀO "TRỢ LÝ KLAW"

### Task 4: `ManChao` làm trạng thái trống của `/dung-thu`

**Files:**
- Create: `frontend/src/components/klaw/ManChao.tsx`
- Modify: `frontend/src/routes/dung-thu.tsx` (nhánh `chuaHoiGiCa`, `GOI_Y`, placeholder, dòng miễn trừ)

**Interfaces:**
- Produces: `ManChao({ onChonGoiY }: { onChonGoiY: (cau: string) => void })`; trong `dung-thu.tsx` hàm `dienGoiY(cau: string)` (Task 6 sửa hàm này để điều hướng khi khoá).

- [ ] **Step 1: `ManChao.tsx`**

```tsx
import { FileSignature, Gavel, Landmark, Scale, Search } from "lucide-react";

/**
 * Màn chào của trợ lý — chuyển nguyên từ `KlawChat` (route `/chat`, đã xoá:
 * spec 2026-09-06 §4). Bấm gợi ý thì ĐIỀN vào ô soạn, không gửi — người dùng
 * còn sửa câu trước khi hỏi; ô soạn và cổng đăng nhập là việc của `/dung-thu`.
 */
const GOI_Y = [
  {
    icon: Search,
    tieuDe: "Tra cứu quy định",
    cau: "Thời gian thử việc tối đa với công việc của người quản lý doanh nghiệp là bao lâu?",
  },
  {
    icon: FileSignature,
    tieuDe: "Soạn hợp đồng",
    cau: "Soạn giúp tôi hợp đồng lao động xác định thời hạn 12 tháng cho vị trí nhân viên kinh doanh.",
  },
  {
    icon: Landmark,
    tieuDe: "Nghĩa vụ của người sử dụng lao động",
    cau: "Người sử dụng lao động phải báo trước bao nhiêu ngày khi đơn phương chấm dứt hợp đồng lao động?",
  },
  {
    icon: Gavel,
    tieuDe: "Soạn đơn",
    cau: "Soạn giúp tôi đơn xin nghỉ việc theo đúng thời hạn báo trước của Bộ luật Lao động 2019.",
  },
] as const;

export function ManChao({ onChonGoiY }: { onChonGoiY: (cau: string) => void }) {
  return (
    <div className="soft-fade mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center py-14 text-center">
      <span className="bg-gradient-ink flex size-16 items-center justify-center rounded-2xl text-primary-foreground shadow-soft">
        <Scale className="size-8" aria-hidden />
      </span>
      <h2 className="font-display mt-5 text-3xl font-bold text-primary">Xin chào, tôi là KLAW</h2>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Tôi tra cứu quy định pháp luật lao động Việt Nam theo điều, khoản, điểm và soạn thảo văn
        bản pháp lý. Mỗi câu trả lời nêu rõ văn bản và điều khoản để bạn tự kiểm chứng.
      </p>
      <div className="mt-8 grid w-full gap-3 sm:grid-cols-2">
        {GOI_Y.map((g) => (
          <button
            key={g.tieuDe}
            type="button"
            onClick={() => onChonGoiY(g.cau)}
            className="focus-brass group cursor-pointer rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-all duration-150 hover:-translate-y-1 hover:border-[var(--color-brass-500)]/60 hover:shadow-lg motion-reduce:hover:translate-y-0"
          >
            <span className="flex items-center gap-2 text-primary">
              <g.icon className="size-4" aria-hidden />
              <span className="font-display text-sm font-semibold">{g.tieuDe}</span>
            </span>
            <span className="mt-2 line-clamp-2 block text-xs leading-relaxed text-muted-foreground">
              {g.cau}
            </span>
          </button>
        ))}
      </div>
      <p className="mt-3 text-xs text-muted-foreground">Chọn một gợi ý để điền vào ô soạn bên dưới.</p>
    </div>
  );
}
```

- [ ] **Step 2: `dung-thu.tsx`**
  - Import `import { ManChao } from "@/components/klaw/ManChao";`; xoá hằng `GOI_Y` (cùng JSDoc của nó) và `Scale` khỏi import lucide nếu không còn dùng.
  - Thêm trong `ManHoiKlaw`, sau `gui`:

```tsx
  // Gợi ý chỉ ĐIỀN, không gửi — người dùng còn sửa câu (spec 2026-09-06 §4.1).
  const dienGoiY = (cau: string) => {
    datNhap(cau);
    oHoi.current?.focus();
  };
```

  - Thay TOÀN BỘ khối `<div className="soft-fade flex flex-1 flex-col items-center justify-center py-14">…</div>` trong nhánh `chuaHoiGiCa ? (` bằng `<ManChao onChonGoiY={dienGoiY} />`.
  - `placeholder` của textarea → `"Hỏi về quy định pháp luật hoặc yêu cầu soạn văn bản…"`.
  - Đoạn `<p className="mt-1.5 text-[12px] text-muted-foreground">Kho văn bản là bản GỐC…</p>` đổi chữ thành: `KLAW cung cấp thông tin tham khảo, không thay thế tư vấn của luật sư. Vui lòng kiểm chứng với văn bản quy phạm pháp luật đang có hiệu lực.` (câu "bản gốc, không phải bản hợp nhất" đã có trong `NhacMienTru` của từng card).

- [ ] **Step 3: Kiểm**

```bash
npm run typecheck && npm run lint && npm run build 2>&1 | tail -2
```

Chrome nếu `npm run dev` đang chạy: `/dung-thu` hiện màn chào bốn thẻ; bấm thẻ → ô soạn có chữ và tiêu điểm, chưa gửi.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/klaw/ManChao.tsx frontend/src/routes/dung-thu.tsx
git commit -m "feat(fe): welcome screen with four suggestion cards inside the assistant page

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: `/chat` chỉ còn redirect; xoá `KlawChat`; bỏ mục nav; đổi link và nhãn

**Files:**
- Modify: `frontend/src/routes/chat.tsx` (viết lại)
- Delete: `frontend/src/components/KlawChat.tsx`
- Modify: `frontend/src/components/app/AppShell.tsx`, `frontend/src/components/AppNav.tsx`
- Modify: `frontend/src/routes/index.tsx` (5 link), `frontend/src/routes/huong-dan.tsx` (1 link)
- Modify (tự sinh): `frontend/src/routeTree.gen.ts`

- [ ] **Step 1: `chat.tsx`** — thay toàn bộ file:

```tsx
import { createFileRoute, redirect } from "@tanstack/react-router";

/**
 * `/chat` từng là màn chào riêng rồi đẩy câu hỏi sang `/dung-thu?q=`. Màn chào
 * nay nằm trong `/dung-thu` (spec 2026-09-06 §4). Giữ route chỉ để link đã chia
 * sẻ không 404; `q` đi theo.
 */
export const Route = createFileRoute("/chat")({
  validateSearch: (tho: Record<string, unknown>): { q?: string } => {
    const q = tho["q"];
    return typeof q === "string" && q.trim() !== "" ? { q } : {};
  },
  beforeLoad: ({ search }) => {
    throw redirect({ to: "/dung-thu", search });
  },
});
```

- [ ] **Step 2: Xoá** — `git rm frontend/src/components/KlawChat.tsx`. `grep -rn "KlawChat" frontend/src` phải rỗng.

- [ ] **Step 3: Nav** — `AppShell.tsx`: xoá dòng `{ to: "/chat", label: "Trò chuyện", icon: MessagesSquare },` và `MessagesSquare` khỏi import. `AppNav.tsx`: dòng `{ to: "/chat", label: "Trò chuyện" },` → `{ to: "/dung-thu", label: "Trợ lý KLAW" },`.

- [ ] **Step 4: Link và nhãn**
  - `routes/index.tsx`: cả năm `to="/chat"` → `to="/dung-thu"`. Nhãn: `Dùng thử agent` → `Mở trợ lý KLAW`; `Bắt đầu trò chuyện` → `Hỏi KLAW`; `Trò chuyện với KLAW` → `Mở trợ lý KLAW`; `Hỏi KLAW một câu` và `Mở trợ lý` giữ.
  - `routes/huong-dan.tsx`: `to="/chat"` → `to="/dung-thu"`, nhãn `Thử ngay với KLAW` → `Mở trợ lý KLAW`.
  - `grep -rn '"/chat"' frontend/src` chỉ còn `routes/chat.tsx` (chuỗi route) và `routeTree.gen.ts`.

- [ ] **Step 5: Kiểm**

```bash
npm run build 2>&1 | tail -2 && npm run typecheck && npm run lint && git status --short src/routeTree.gen.ts
```

Chrome: nav ứng dụng và nav landing không còn "Trò chuyện"; `/chat?q=abc` chuyển thành `/dung-thu?q=abc`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/chat.tsx frontend/src/components/app/AppShell.tsx frontend/src/components/AppNav.tsx frontend/src/routes/index.tsx frontend/src/routes/huong-dan.tsx frontend/src/routeTree.gen.ts
git commit -m "refactor(fe): fold the chat entry into the assistant page; /chat redirects

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

(`git rm` ở Step 2 đã stage việc xoá `KlawChat.tsx`.)

---

# BƯỚC D — ĐĂNG NHẬP MỚI HỎI ĐƯỢC

### Task 6: Khoá ô hỏi khi chưa đăng nhập; `next=` cho đăng nhập/đăng ký

**Files:**
- Create: `frontend/src/lib/quay-lai.ts`, `frontend/scripts/kiem-quay-lai.ts`, `frontend/src/components/klaw/TheDangNhap.tsx`
- Modify: `frontend/package.json` (script + chuỗi `kiem`)
- Modify: `frontend/src/routes/dang-nhap.tsx`, `frontend/src/routes/dang-ky.tsx`
- Modify: `frontend/src/routes/dung-thu.tsx`

**Interfaces:**
- Consumes: `useAuth() -> { session, user, loading, chuaCauHinh, signOut }` (`hooks/use-auth.ts`); `dienGoiY` (Task 4).
- Produces: `DICH_QUAY_LAI = ["/dung-thu", "/soan-thao"] as const`, `type DichQuayLai`, `locNext(tho: unknown) -> DichQuayLai | undefined`; `TheDangNhap({ next }: { next: DichQuayLai })`; `Route.useSearch()` của `/dang-nhap` và `/dang-ky` trả `{ next?: DichQuayLai }`.

- [ ] **Step 1: Kiểm đỏ** — `frontend/scripts/kiem-quay-lai.ts`:

```ts
/**
 * `locNext`: đích quay lại sau đăng nhập chỉ nhận hai trang bị khoá. Một chuỗi
 * ngoài danh sách (URL ngoài, `//evil`, đường con) bị bỏ — không open redirect.
 * Chạy: `npm run kiem-quay-lai`.
 */
import assert from "node:assert/strict";
import { DICH_QUAY_LAI, locNext } from "../src/lib/quay-lai.ts";

assert.deepEqual([...DICH_QUAY_LAI], ["/dung-thu", "/soan-thao"]);
assert.equal(locNext("/dung-thu"), "/dung-thu");
assert.equal(locNext("/soan-thao"), "/soan-thao");
assert.equal(locNext("/soan-thao/don-xin-nghi-viec"), undefined);
assert.equal(locNext("//evil.example"), undefined);
assert.equal(locNext("https://evil.example/dung-thu"), undefined);
assert.equal(locNext(""), undefined);
assert.equal(locNext(undefined), undefined);
assert.equal(locNext(["/dung-thu"]), undefined);
console.info("kiem-quay-lai: 9/9 đạt");
```

- [ ] **Step 2: Đỏ** — `node scripts/kiem-quay-lai.ts` → lỗi import.

- [ ] **Step 3: `lib/quay-lai.ts`**

```ts
/**
 * Đích quay lại sau đăng nhập/đăng ký (`?next=`). Chỉ hai trang bị khoá; mọi
 * giá trị khác bị bỏ — danh sách trắng thay cho kiểm tiền tố, nên không có
 * open redirect và `navigate({ to })` vẫn được TanStack kiểm kiểu.
 */
export const DICH_QUAY_LAI = ["/dung-thu", "/soan-thao"] as const;
export type DichQuayLai = (typeof DICH_QUAY_LAI)[number];

export function locNext(tho: unknown): DichQuayLai | undefined {
  return DICH_QUAY_LAI.find((d) => d === tho);
}
```

`package.json`: thêm `"kiem-quay-lai": "node scripts/kiem-quay-lai.ts",` và chèn `npm run kiem-quay-lai && ` vào chuỗi `"kiem"` ngay sau `npm run kiem-documents && `.

- [ ] **Step 4: `TheDangNhap.tsx`**

```tsx
import { Link } from "@tanstack/react-router";
import { LogIn } from "lucide-react";
import type { DichQuayLai } from "@/lib/quay-lai";

/**
 * Thay chỗ ô hỏi khi Supabase đã cấu hình mà chưa có phiên (spec 2026-09-06
 * §5.1). KHÔNG viết cứng số lượt: nguồn số là `config/han_muc.yaml`, và
 * `HanMucThang` hiện nó sau đăng nhập — một con số chép tay ở đây là đồng hồ
 * "còn N/20 lượt" mà mã đã phải gỡ một lần.
 */
export function TheDangNhap({ next }: { next: DichQuayLai }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 shadow-soft">
      <p className="m-0 text-sm leading-6 text-foreground">
        <LogIn className="mr-2 inline size-4 align-text-bottom text-muted-foreground" aria-hidden />
        Đăng nhập để hỏi KLAW. Tài khoản mới dùng gói Miễn phí.
      </p>
      <div className="flex gap-2">
        <Link
          to="/dang-nhap"
          search={{ next }}
          className="focus-brass bg-gradient-ink inline-flex min-h-10 items-center rounded-lg px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          Đăng nhập
        </Link>
        <Link
          to="/dang-ky"
          search={{ next }}
          className="focus-brass inline-flex min-h-10 items-center rounded-lg border border-border px-4 text-sm text-primary transition-colors hover:bg-[var(--color-paper-100)]"
        >
          Tạo tài khoản
        </Link>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: `dang-nhap.tsx` và `dang-ky.tsx`** (làm giống nhau ở cả hai):
  - Import `import { locNext, type DichQuayLai } from "@/lib/quay-lai";`.
  - Trong `createFileRoute(...)({ … })` thêm, trước `component:`:

```ts
  validateSearch: (tho: Record<string, unknown>): { next?: DichQuayLai } => {
    const next = locNext(tho["next"]);
    return next === undefined ? {} : { next };
  },
```

  - Trong component, sau `const navigate = useNavigate();` thêm `const { next } = Route.useSearch();`.
  - `navigate({ to: "/dung-thu" })` → `navigate({ to: next ?? "/dung-thu" })`.
  - Chữ `Đang mở phiên dùng thử…` → `Đang mở trợ lý KLAW…` (cả hai file).

- [ ] **Step 6: `dung-thu.tsx`**
  - Import `useNavigate` từ `@tanstack/react-router` (gộp vào import `createFileRoute`); `import { useAuth } from "@/hooks/use-auth";`; `import { TheDangNhap } from "@/components/klaw/TheDangNhap";`.
  - Trong `ManHoiKlaw`, sau `const haiCot = useHaiCot();`:

```tsx
  const navigate = useNavigate();
  const { user, loading: dangKiemPhien, chuaCauHinh } = useAuth();
  // Cổng chỉ đóng khi máy chủ cũng đóng: Supabase đã cấu hình mà chưa có phiên
  // (spec 2026-09-06 §5.1). Chưa cấu hình (máy dev) thì backend cho ẩn danh.
  const canDangNhap = !chuaCauHinh && !dangKiemPhien && user === null;
```

  - Effect hỏi từ `?q=`: điều kiện đầu đổi thành
    `if (cauHoiTrenUrl === undefined || dangKiemPhien || canDangNhap || daHoiTuUrl.current === cauHoiTrenUrl) return;`
    và thêm `dangKiemPhien, canDangNhap` vào mảng deps.
  - `dienGoiY` (Task 4) thành:

```tsx
  const dienGoiY = (cau: string) => {
    if (canDangNhap) {
      void navigate({ to: "/dang-nhap", search: { next: "/dung-thu" } });
      return;
    }
    datNhap(cau);
    oHoi.current?.focus();
  };
```

  - Ô soạn: bọc `<div className="flex items-end gap-2 rounded-xl border border-border bg-card p-2 shadow-soft">…</div>` (khối chứa nút kẹp, textarea, nút gửi) bằng:

```tsx
              {dangKiemPhien && !chuaCauHinh ? (
                <div aria-hidden className="min-h-[56px] rounded-xl border border-border bg-card" />
              ) : canDangNhap ? (
                <TheDangNhap next="/dung-thu" />
              ) : (
                <div className="flex items-end gap-2 rounded-xl border border-border bg-card p-2 shadow-soft">
                  …(khối cũ nguyên vẹn)…
                </div>
              )}
```

  Dòng miễn trừ dưới ô vẫn hiện ở cả ba trạng thái.

- [ ] **Step 7: Xanh**

```bash
node scripts/kiem-quay-lai.ts && npm run typecheck && npm run lint && npm run build 2>&1 | tail -2
```

Chrome: đăng xuất → `/dung-thu` hiện màn chào và thẻ "Đăng nhập để hỏi KLAW"; bấm gợi ý → sang `/dang-nhap?next=%2Fdung-thu`; đăng nhập → quay về `/dung-thu` với ô soạn; `/dang-nhap?next=https://x` → URL bị lọc `next`.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/quay-lai.ts frontend/scripts/kiem-quay-lai.ts frontend/package.json frontend/src/components/klaw/TheDangNhap.tsx frontend/src/routes/dang-nhap.tsx frontend/src/routes/dang-ky.tsx frontend/src/routes/dung-thu.tsx frontend/src/routeTree.gen.ts
git commit -m "feat(fe): require sign-in to ask the assistant; return to the page after login

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Chữ "dùng thử", thông điệp 401 kèm link, bảng giá có gói Miễn phí

**Files:**
- Modify: `frontend/src/routes/__root.tsx` (JSON-LD `offers.description`)
- Modify: `frontend/src/lib/api.ts` (thông điệp 401/403)
- Modify: `frontend/src/components/klaw/BaoLoi.tsx` (gợi ý + link "Đăng nhập")
- Modify: `frontend/src/routes/bang-gia.tsx`

- [ ] **Step 1: `__root.tsx`** — `description: "Bản dùng thử miễn phí"` → `description: "Gói Miễn phí"`.

- [ ] **Step 2: `api.ts`** — dòng `return chung("unauthorized", "Máy chủ KLAW từ chối yêu cầu vì thiếu quyền truy cập.");` → `return chung("unauthorized", "Bạn cần đăng nhập để dùng tính năng này.");`

- [ ] **Step 3: `BaoLoi.tsx`**
  - Import `import { Link } from "@tanstack/react-router";`.
  - `case "unauthorized":` trả `"Bạn chưa đăng nhập hoặc phiên đã hết hạn. Đăng nhập rồi hỏi lại — câu hỏi của bạn không có gì sai."`.
  - Sau đoạn `{them !== null && (<p …>{them}</p>)}` thêm:

```tsx
      {loi.kind === "unauthorized" && (
        <Link
          to="/dang-nhap"
          search={{ next: "/dung-thu" }}
          className="focus-brass mt-3 inline-flex min-h-11 items-center rounded-lg border border-border px-4 text-[15px] font-medium text-primary transition-colors hover:bg-[var(--color-paper-100)]"
        >
          Đăng nhập
        </Link>
      )}
```

  (`BaoLoi` cũng dùng ở màn Soạn thảo; `next` là `/dung-thu` vì màn Soạn thảo chưa bị khoá và `/soan-thao` chỉ có ý nghĩa khi khoá màn đó — ngoài phạm vi.)

- [ ] **Step 4: `bang-gia.tsx`**
  - `type TierId = "mien-phi" | "ca-nhan" | "doanh-nghiep" | "to-chuc";`; kiểu phần tử `TIERS` thêm `sapRaMat?: boolean;`.
  - Chèn ĐẦU mảng `TIERS`:

```ts
  {
    id: "mien-phi",
    name: "Miễn phí",
    tagline: "Cho người mới bắt đầu — không cần thẻ",
    monthly: 0,
    annual: 0,
    features: ["Tra cứu không giới hạn", "50 lượt hỏi AI/tháng", "Xuất Word, PDF"],
    cta: "Tạo tài khoản",
    ctaTo: "/dang-ky",
  },
```

  - Gói `ca-nhan`: `"50 lượt hỏi AI/tháng"` → `"500 lượt hỏi AI/tháng"`; `cta: "Sắp ra mắt"`, thêm `sapRaMat: true`. Gói `doanh-nghiep`: `cta: "Sắp ra mắt"`, `sapRaMat: true`. `ctaTo` của hai gói này giữ nguyên chuỗi (không dùng khi `sapRaMat`).
  - `type Row = { label: string; values: [string | boolean, string | boolean, string | boolean, string | boolean] }` (4 cột). Chèn giá trị cột Miễn phí vào ĐẦU mỗi `values` của `COMPARISON`, theo thứ tự dòng: `true`, `"50"`, `"Tính vào lượt hỏi AI"`, `true`, `true`, `"1"`, `false`, `"Cộng đồng"`, `false`, `false`, `false`. Dòng "Lượt hỏi AI mỗi tháng" cột Cá nhân `"50"` → `"500"`.
  - Lưới thẻ (chỗ `TIERS.map` đầu, khoảng dòng 222): lớp cột rộng nhất `grid-cols-3` → `grid-cols-4` (giữ breakpoint hiện có, vd `lg:grid-cols-4`).
  - Khối giá: khi `t.monthly === 0` hiện `<span className="font-display text-[34px] leading-none text-primary">Miễn phí</span>` thay `vnd(...)`+`/tháng`, và dòng phụ `Không cần thẻ thanh toán` thay cho "Mức dự kiến…" — thêm nhánh `t.monthly === 0` TRƯỚC nhánh `t.monthly == null`.
  - Nút: trong nhánh không phải `mailto:`, nếu `t.sapRaMat`:

```tsx
              <button
                type="button"
                disabled
                aria-disabled
                className="mt-7 inline-flex h-11 cursor-default items-center justify-center rounded-lg border border-border text-[14px] font-medium text-muted-foreground opacity-70"
              >
                {t.cta}
              </button>
```

    ngược lại giữ `<Link …>` cũ.
  - FAQ: câu "Có đăng ký được ngay không?" → a: `"Có tài khoản Miễn phí ngay: bấm Tạo tài khoản, không cần thẻ. Gói trả phí chưa mở thanh toán — chưa có cổng thanh toán, hoá đơn, chính sách huỷ hay hoàn tiền; mức giá chỉ để tham khảo."`. Câu "Hạn mức lượt hỏi tính thế nào?" → a: `"Gói Miễn phí có 50 lượt hỏi AI mỗi tháng, đếm ở máy chủ theo tài khoản và đặt lại đầu tháng; soạn một bản thảo cũng tính một lượt. Gói trả phí chưa mở."`.

- [ ] **Step 5: Kiểm**

```bash
npm run typecheck && npm run lint && npm run build 2>&1 | tail -2 && grep -rn "dùng thử\|Dùng thử" src --include='*.tsx' --include='*.ts'
```

`grep` chỉ còn hai comment "người dùng thử lại mãi" trong `dang-nhap.tsx`/`dang-ky.tsx` (không phải chữ hiển thị). Chrome: `/bang-gia` bốn thẻ, thẻ Miễn phí ghi "Miễn phí", hai nút "Sắp ra mắt" không bấm được; bảng so sánh bốn cột.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/__root.tsx frontend/src/lib/api.ts frontend/src/components/klaw/BaoLoi.tsx frontend/src/routes/bang-gia.tsx
git commit -m "feat(fe): free tier on pricing, paid tiers marked coming soon, sign-in link on 401

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

# BƯỚC E — TRA CỨU DUYỆT KHO

### Task 8: Danh sách văn bản khi ô từ khoá rỗng

**Files:**
- Modify: `frontend/src/lib/klaw.ts` (sau `interface TimKiem`; predicate cạnh `laTimKiem`)
- Modify: `frontend/src/routes/tra-cuu.index.tsx`

**Interfaces:**
- Consumes: `GET /van-ban` (Task 1); `BadgeHieuLuc`, `Link`, `goi`, `thamSo`, `MOI_TRANG`, `NHAN_SAP_XEP`, `doi`, `chipDangBat` (đã có trong file).
- Produces: `VanBanTomTat`, `DanhSachVanBan`, `laDanhSachVanBan(x: unknown): x is DanhSachVanBan`; component `TheVanBan({ vanBan }: { vanBan: VanBanTomTat })`.

- [ ] **Step 1: `lib/klaw.ts`** — sau `export interface TimKiem { … }`:

```ts
/* ── GET /van-ban — danh sách văn bản theo bộ lọc, không cần từ khoá ─────── */
export interface VanBanTomTat {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  loai_van_ban: string;
  co_quan_ban_hanh: string | null;
  ngay_ban_hanh: string | null;
  hieu_luc: HieuLucChiTiet;
}

export interface DanhSachVanBan {
  tong: number;
  limit: number;
  offset: number;
  sap_xep: string;
  ket_qua: VanBanTomTat[];
}
```

Sau `laTimKiem`:

```ts
export function laDanhSachVanBan(x: unknown): x is DanhSachVanBan {
  return laBanGhi(x) && Array.isArray(x["ket_qua"]) && typeof x["tong"] === "number";
}
```

- [ ] **Step 2: `tra-cuu.index.tsx` — state và tải**
  - Import thêm `laDanhSachVanBan, type DanhSachVanBan, type VanBanTomTat` từ `@/lib/klaw` (gộp vào import sẵn có); `BadgeHieuLuc` đã được import (dùng trong `TheDong`) — nếu chưa, thêm.
  - Sau `const [ketQua, datKetQua] = useState<TimKiem | null>(null);` thêm `const [danhSach, datDanhSach] = useState<DanhSachVanBan | null>(null);`.
  - Trong effect tải (`useEffect(() => { if (q.trim() === "") {…}`), thay nhánh `if (q.trim() === "")` bằng:

```tsx
    const locChung: [string, string | number | undefined][] = [
      ...(loaiKhoa === "" ? [] : loaiKhoa.split("|").map((v): [string, string] => ["loai", v])),
      ...(coQuanKhoa === ""
        ? []
        : coQuanKhoa.split("|").map((v): [string, string] => ["co_quan", v])),
      ["tu_nam", tuNam],
      ["den_nam", denNam],
      ["limit", MOI_TRANG],
      ["offset", (trang - 1) * MOI_TRANG],
    ];
    if (q.trim() === "") {
      // Duyệt kho (spec 2026-09-06 §6.2): không từ khoá thì không có "liên quan".
      datKetQua(null);
      const dieuKhien = new AbortController();
      datDangChay(true);
      const sapXepDuyet = sapXep === undefined || sapXep === "lien_quan" ? "moi_nhat" : sapXep;
      void goi(`/van-ban${thamSo([...locChung, ["sap_xep", sapXepDuyet]])}`, laDanhSachVanBan, {
        signal: dieuKhien.signal,
      }).then((kq) => {
        datDangChay(false);
        if (kq.ok) {
          datDanhSach(kq.data);
          datLoi(null);
          return;
        }
        if (kq.error.kind === "aborted") return;
        datDanhSach(null);
        datLoi(kq.error);
      });
      return () => dieuKhien.abort();
    }
    datDanhSach(null);
```

    và nhánh tìm kiếm phía dưới dùng `thamSo([["q", q], ...locChung, ["sap_xep", sapXep]])` thay mảng cũ (giữ hành vi). Kiểm chữ ký `thamSo` trong file: nó nhận mảng cặp `[khoa, gia]` và bỏ `undefined` — nếu kiểu khai khác `[string, string | number | undefined][]`, dùng đúng kiểu đó.
  - `tongTrang`:

```tsx
  const tongMuc = ketQua?.tong_dieu_khoan ?? danhSach?.tong ?? null;
  const tongTrang = tongMuc === null ? 0 : Math.max(1, Math.ceil(tongMuc / MOI_TRANG));
```

- [ ] **Step 3: Dòng tổng và chip sắp xếp**
  - Thay nhánh `{q.trim() === "" ? ("Nhập từ khoá để bắt đầu.") : …` bằng:

```tsx
                {dangChay ? (
                  q.trim() === "" ? "Đang tải…" : "Đang tìm…"
                ) : q.trim() === "" ? (
                  danhSach === null ? (
                    ""
                  ) : (
                    <>
                      <span className="font-medium text-foreground">{danhSach.tong} văn bản</span>
                      {chipDangBat.length > 0 && ` · ${chipDangBat.map((c) => c.gia).join(" · ")}`}
                    </>
                  )
                ) : ketQua === null ? (
                  ""
                ) : (
                  <>…(khối "N điều khoản trong M văn bản cho “q”" giữ nguyên)…</>
                )}
```

  - Chip: `const sapXepHienThi = q.trim() === "" ? sapXepCoThe.filter((c) => c !== "lien_quan") : sapXepCoThe;` và dùng `sapXepHienThi` thay `sapXepCoThe` ở cả điều kiện `.length > 0` và `.map`. `dangBat` = `(sapXep ?? (q.trim() === "" ? "moi_nhat" : "lien_quan")) === cach`.

- [ ] **Step 4: Dòng văn bản** — thêm component (đặt sau `TheDong`):

```tsx
/** Một văn bản ở chế độ duyệt kho (chưa có từ khoá). Nhãn hiệu lực là của cả
 * văn bản — cùng nguồn `effectivity` với `TheDong`, không phải `tinh_trang`. */
function TheVanBan({ vanBan }: { vanBan: VanBanTomTat }) {
  const nam = vanBan.ngay_ban_hanh === null ? null : vanBan.ngay_ban_hanh.slice(0, 4);
  return (
    <article className="rounded-xl border border-border bg-card p-4 transition-colors duration-150 hover:border-[var(--color-brass-500)]/50">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12px] text-muted-foreground">
        <span className="font-jetbrains text-[12px] text-foreground">{vanBan.so_ky_hieu}</span>
        <span className="text-border" aria-hidden>
          ·
        </span>
        <span>{vanBan.loai_van_ban}</span>
        {vanBan.co_quan_ban_hanh !== null && (
          <>
            <span className="text-border" aria-hidden>
              ·
            </span>
            <span>{vanBan.co_quan_ban_hanh}</span>
          </>
        )}
        {nam !== null && (
          <>
            <span className="text-border" aria-hidden>
              ·
            </span>
            <span>{nam}</span>
          </>
        )}
      </div>
      <h3 className="font-display mt-2 text-[18px] leading-snug font-semibold text-primary">
        <Link
          to="/tra-cuu/$docId"
          params={{ docId: vanBan.doc_id }}
          className="focus-brass rounded hover:underline"
        >
          {vanBan.bo_luat}
        </Link>
      </h3>
      <p className="m-0 mt-2">
        <BadgeHieuLuc hieuLuc={vanBan.hieu_luc.verdict} gonGang />
      </p>
    </article>
  );
}
```

(Nếu typecheck đòi `search` cho `/tra-cuu/$docId`, thêm `search={{}}` — đọc `validateSearch` của `routes/tra-cuu.$docId.tsx`.)

  Trong khối danh sách kết quả, trước `{ketQua?.ket_qua.map(...)}`:

```tsx
              {danhSach !== null && danhSach.ket_qua.length === 0 && (
                <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                  Không có văn bản nào khớp bộ lọc này. Bỏ bớt một chip hoặc nới khoảng năm.
                </p>
              )}
              {danhSach?.ket_qua.map((vb) => <TheVanBan key={vb.doc_id} vanBan={vb} />)}
```

  Cập nhật JSDoc đầu file (đoạn "`/tim-kiem` + `/bo-loc`") thêm một câu: "Ô từ khoá rỗng thì gọi `GET /van-ban` — duyệt kho theo bộ lọc (spec 2026-09-06 §6)."

- [ ] **Step 5: Kiểm**

```bash
npm run typecheck && npm run lint && npm run build 2>&1 | tail -2
```

Chrome (backend chạy): `/tra-cuu` hiện danh sách 20 văn bản, dòng tổng "1626 văn bản" (số thật của kho), chip "Liên quan nhất" không hiện; tick "Nghị định" → "696 văn bản · Nghị định" và danh sách thu hẹp; "Trang sau" đổi trang; bấm một dòng → `/tra-cuu/<docId>`; gõ từ khoá → hành vi cũ, "Liên quan nhất" trở lại.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/klaw.ts frontend/src/routes/tra-cuu.index.tsx
git commit -m "feat(fe): browse the corpus by filter when the search box is empty

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

# BƯỚC F — ĐÓNG

### Task 9: Kiểm chung, chụp màn, đóng plan bền

**Files:**
- Move: `docs/plans/active/truy-cap-va-giao-dien-tra-loi.md` → `docs/plans/completed/`
- Create: `.tham-dinh-shots/09-man-chao-khoa-dang-nhap.png`, `10-tra-cuu-duyet-kho.png`, `11-card-chi-luat-con-hieu-luc.png` (nếu công cụ chụp lưu được file)

- [ ] **Step 1: Kiểm toàn bộ (foreground)**

```bash
make lint && python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py
cd frontend && npm run kiem
```

Expected: pytest xanh ngoài hai fail đã biết (`test_tang_sau_moi_so_ky_hieu_la_duy_nhat`, `test_chi_nhung_canh_ngay_mau_thuan_DA_BIET_moi_duoc_bo` nằm trong đường bị ignore); `npm run kiem` xanh đủ chuỗi kể cả `kiem-quay-lai` và `kiem-xep-trich-dan`.

- [ ] **Step 2: Kiểm bằng Chrome thật** (backend `uvicorn` + `npm run dev` đang chạy): (a) đăng xuất, `/dung-thu` → màn chào + thẻ khoá; đăng nhập → ô soạn; hỏi "Thời gian thử việc tối đa với công việc của người quản lý doanh nghiệp là bao lâu?" → card không có khối đỏ, không có danh sách trích dẫn; bấm "Khoản 1 Điều 25" → khung mở, dưới số ký hiệu có nhãn hiệu lực; (b) `/tra-cuu` → danh sách; tick Nghị định → thu hẹp; (c) nav không còn "Trò chuyện"; `/chat` → `/dung-thu`. Chụp ba ảnh nếu được.

- [ ] **Step 3: Đóng plan bền** — tick hết Progress; Decisions: "Thứ tự BE→card→gộp→truy cập→tra cứu", "next whitelist hai giá trị", "Free column trong bảng so sánh"; điền `## Result` (số văn bản hiện ở `/tra-cuu`, ba ảnh, các commit); `Status: Completed`; `git mv docs/plans/active/truy-cap-va-giao-dien-tra-loi.md docs/plans/completed/`.

- [ ] **Step 4: Commit**

```bash
git add docs/plans/ .tham-dinh-shots/09-*.png .tham-dinh-shots/10-*.png .tham-dinh-shots/11-*.png
git commit -m "docs(plan): close account-gated assistant and answer-card cleanup plan

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

(Chỉ `git add` các ảnh thật sự có.)

---

## Việc tiếp theo (ngoài plan này)

- Chạy plan `docs/superpowers/plans/2026-09-06-soan-thao-trong-chat.md` (card cho mọi trả lời, gợi ý soạn thảo, khung soạn thảo bên cạnh).
- Đổi URL `/dung-thu` → `/tro-ly` sau khi plan trên gộp.
- Khoá màn Soạn thảo trước "Dựng bản thảo" khi `KhongGianSoanThao` đã tách.
