# Soạn thảo trong chat và card câu trả lời — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trong `/dung-thu`, một câu "soạn cho tôi hợp đồng nghỉ việc" nhận về một card gợi ý đúng loại văn bản (kèm loại thay thế), bấm "Soạn ngay tại đây" mở nguyên màn soạn thảo ở khung bên cạnh (biểu mẫu → xem trước → soát → tải .docx/.pdf) mà không rời hội thoại; mọi câu trả lời của trợ lý nằm trong card.

**Architecture:** Router LLM (lượt gọi đã có) trả thêm `loai_van_ban` trong đúng tập checklist trên đĩa; `assemble` kiểm 0 token và trả `soan_thao_goi_y`; FE có nhánh card gợi ý và mở màn soạn thảo hiện có — tách từ route `/soan-thao/$loaiVanBan` thành component `KhongGianSoanThao` — trong khung phải của chat. Thêm checklist "Thoả thuận chấm dứt HĐLĐ" như một mẫu dữ liệu. Hợp đồng dữ liệu additive khoá ở Bước 0, hai worktree BE/FE ở Bước 1, gộp và bật ở Bước 2.

**Tech Stack:** Python 3.12 · FastAPI · LangGraph · pydantic · pytest · React 19 · TanStack Start · TypeScript (`exactOptionalPropertyTypes`) · Tailwind 4 · Node 22 · Chrome MCP.

**Spec:** `docs/superpowers/specs/2026-09-06-soan-thao-trong-chat-design.md`

## Global Constraints

- Bất biến: không LLM viết điều khoản; văn bản dựng từ checklist (`config/checklist_*.yaml`, mỗi mục một `can_cu` khớp `provisions.duong_dan`). Node `route` KHÔNG tiêm SOUL (không import `src.services.prompts`).
- Mọi trường schema mới có mặc định (`TraCuuResponse.soan_thao: SoanThaoGoiYOut | None = None`); mọi field mới của `TraCuuResponse` khai trong `KLawState` (test `test_moi_field_TraCuuResponse_deu_duoc_KLawState_khai` canh).
- Xưng "tôi", gọi "bạn"; chuỗi hiển thị (hằng số BE, `TheKetQua.tsx`) không chứa: "hệ thống", "không diễn giải", "chưa đủ căn cứ", "truy hồi", "database", "để bạn tự đối chiếu", "máy chủ trả về".
- Prompt mặc định: `Settings.route_prompt = "prompts/route.v1.md"` cho tới Task 9; A/B qua env `ROUTE_PROMPT=prompts/route.v2.md`.
- Không chạy `make check`/`make format` (target format ghi đè cả cây). Dùng `make lint`, pytest tập trung, `ruff format --check <file đã sửa>` chỉ trên dòng mới, và một lượt pytest rộng foreground: `python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py` (hai đường bị bỏ chứa 2 lỗi có sẵn đọc dữ liệu corpus). FE: `npm run typecheck && npm run lint` + script `kiem-*` liên quan; `npm run build` ở task tách component.
- Không stage file dirty của phiên khác (`docs/guide/*`, `scripts/log_*.py`, `README_boilerplate.md`, `src/services/checklist.py`, `tests/test_services/test_moi_mau.py`, `qh3.html`, `.impeccable/`, `eval/results/lexical_only-*.json`): `git add` theo đường dẫn.
- Commit tiếng Anh, conventional commits, kết bằng `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Song song bằng `git worktree`, không hai implementer trên một branch.
- Bắt đầu SAU khi plan `2026-09-06-soul-trich-dan-bam-duoc` qua review tổng và dọn worktree (nhánh `feat/tro-ly-phap-luat`).

---

## File Structure

| Đường dẫn | Việc | Bước |
|---|---|---|
| `config/checklist_thoa_thuan_cham_dut_hdld.yaml` (mới) | checklist hai bên, 8 mục, `can_cu` đã tra DB | 0 |
| `src/models/schemas.py` | `LoaiVanBan` thêm giá trị; `LoaiGoiYOut`, `SoanThaoGoiYOut`, `TraCuuResponse.soan_thao` | 0 |
| `frontend/src/lib/mau-van-ban.ts` | `MAU` + `LOAI_BACKEND` + `LoaiVanBanBackend` thêm mẫu; (1-FE) `slugCuaLoai()` | 0, 1-FE |
| `frontend/scripts/kiem-khung.ts` | đếm 28 → 29 | 0 |
| `src/agents/state.py` | `soan_thao_goi_y` | 0 |
| `src/api/routes.py` | `_payload_cache`, `tra_cuu_response` | 0 |
| `src/config.py` | `route_prompt` | 0 |
| `src/agents/nodes/route.py`, `src/agents/graph_tra_cuu.py` | `prompt_path`; (1-BE) schema v2, `soan_thao_goi_y` | 0, 1-BE |
| `frontend/src/lib/klaw.ts` | `LoaiGoiY`, `SoanThaoGoiY`, `TraCuuKetQua.soan_thao` | 0 |
| `docs/plans/active/soan-thao-trong-chat.md` (mới) | plan bền | 0 |
| `prompts/route.v2.md` (mới), `tests/test_agents/test_route.py` | router v2 | 1-BE |
| `src/agents/nodes/assemble.py`, `tests/test_agents/test_assemble.py`, `tests/test_agents/test_huong_dan_soan_thao.py` | nhánh `soan_thao` dựng gợi ý | 1-BE |
| `eval/datasets/trap.yaml`, `eval/run_trap.py`, `tests/test_eval/test_run_trap.py` | nhóm bẫy `soan_thao` | 1-BE |
| `frontend/src/routes/dung-thu.tsx` | card bọc trả lời; khung phải soạn thảo | 1-FE |
| `frontend/scripts/kiem-goi-y-soan-thao.ts` (mới), `frontend/package.json` | kiểm `slugCuaLoai` | 1-FE |
| `frontend/src/components/soan-thao/KhongGianSoanThao.tsx` (mới), `frontend/src/routes/soan-thao.$loaiVanBan.tsx` | tách component | 1-FE |
| `frontend/src/components/klaw/TheKetQua.tsx` | nhánh `huong_dan_soan_thao` → `TheGoiYSoanThao` | 1-FE |

---

# BƯỚC 0 — Mẫu mới và hợp đồng dữ liệu (tuần tự, nhánh `feat/tro-ly-phap-luat`)

### Task 1: Checklist "Thoả thuận chấm dứt hợp đồng lao động" + đăng ký hai phía

**Files:**
- Create: `config/checklist_thoa_thuan_cham_dut_hdld.yaml`
- Modify: `src/models/schemas.py` (`LoaiVanBan` Literal, ~dòng 302–331)
- Modify: `frontend/src/lib/mau-van-ban.ts` (`MAU` sau mục `don-xin-nghi-viec`; `LOAI_BACKEND` cuối map; `LoaiVanBanBackend` cuối union)
- Modify: `frontend/scripts/kiem-khung.ts` (dòng `assert.equal(MAU.length, 28);`)
- Create: `docs/plans/active/soan-thao-trong-chat.md`
- Test: `tests/test_services/test_moi_mau.py` (có sẵn, parametrize theo file), `frontend/scripts/kiem-khung.ts`

**Interfaces:**
- Produces: `loai = "thoa_thuan_cham_dut_hdld"` hợp lệ ở `cac_loai()`, `LoaiVanBan`, `GET /mau/{loai}`; slug FE `thoa-thuan-cham-dut-hop-dong-lao-dong`. Task 3 đưa loại này vào enum router; Task 8 mở khung bằng slug.

- [ ] **Step 1: Kiểm căn cứ trong DB trước khi viết YAML** (đọc, không ghi)

```bash
python3 - <<'PY'
from sqlalchemy import text
from src.services.db import get_engine
cands = ["45/2019/QH14 > Điều 34 > Khoản 3","45/2019/QH14 > Điều 46 > Khoản 1","45/2019/QH14 > Điều 48 > Khoản 1",
         "45/2019/QH14 > Điều 48 > Khoản 2","45/2019/QH14 > Điều 48 > Khoản 3 > Điểm a","45/2019/QH14 > Điều 48 > Khoản 3 > Điểm b"]
with get_engine().connect() as c:
    rows = {r["duong_dan"]: r for r in c.execute(text(
        "SELECT duong_dan, length(btrim(noi_dung)) dai, btrim(noi_dung)=btrim(tieu_de) rong_than FROM provisions WHERE duong_dan = ANY(:d)"),
        {"d": cands}).mappings()}
for d in cands:
    r = rows.get(d); print("OK " if r and not r["rong_than"] else "FAIL", d, r["dai"] if r else "-")
PY
```

Expected: sáu dòng `OK` (đã tra 2026-09-06: thân 49/466/237/288/180/172 ký tự). Một dòng `FAIL` thì DỪNG và báo — không đổi căn cứ sang đường khác mà không tra.

- [ ] **Step 2: Ghi mốc số ca test mẫu hiện tại**

```bash
python -m pytest tests/test_services/test_moi_mau.py -q 2>&1 | tail -1
```

- [ ] **Step 3: Tạo `config/checklist_thoa_thuan_cham_dut_hdld.yaml`**

```yaml
# Checklist nội dung của THOẢ THUẬN CHẤM DỨT HỢP ĐỒNG LAO ĐỘNG — HAI BÊN cùng
# thoả thuận (BLLĐ Đ34.3). Khác `don_xin_nghi_viec` (NLĐ đơn phương, Đ35) và
# `quyet_dinh_cham_dut_hdld` (NSDLĐ đơn phương/thông báo, Đ34, Đ36, Đ45): cùng
# một chương nhưng ba bộ điều kiện khác nhau — KHÔNG dùng chung can_cu.
#
# `la_hop_dong: true`: khối các bên và chữ ký do khung hợp đồng chung cấp
# (BLDS Đ385/Đ400.4, xem `routes._khung_hop_dong`), nên không lặp mục `cac_ben`.
#
# Mọi can_cu đã tra DB 2026-09-06 bằng phép canh rong_than của
# `checklist_don_xin_nghi_viec.yaml` — cả sáu đường có thân (rong_than = false):
#   Đ34.3 (49 ký tự: "Hai bên thỏa thuận chấm dứt hợp đồng lao động."), Đ46.1,
#   Đ48.1 (hạn 14 ngày), Đ48.2 (các khoản ưu tiên), Đ48.3.a (BHXH + trả giấy
#   tờ), Đ48.3.b (bản sao hồ sơ). Đ34 trần RỖNG THÂN — không dẫn.
loai: thoa_thuan_cham_dut_hdld
ten: "thoả thuận chấm dứt hợp đồng lao động"
tieu_de: "THOẢ THUẬN CHẤM DỨT HỢP ĐỒNG LAO ĐỘNG"
don_vi_muc: "Điều"
la_hop_dong: true
rules: []
can_cu_goc: "45/2019/QH14 > Điều 34 > Khoản 3"
can_cu_chi_tiet: "45/2019/QH14 > Điều 48 > Khoản 1"
muc_do_thieu: chan
khong_bat_buoc:
  can_cu: "45/2019/QH14 > Điều 46 > Khoản 1"
  ghi_chu: >
    Trợ cấp thôi việc chỉ phát sinh khi người lao động đã làm việc thường xuyên
    từ đủ 12 tháng trở lên (Đ46.1); bản sao hồ sơ chỉ cấp khi người lao động
    yêu cầu (Đ48.3.b). Thoả thuận không có hai mục này không phải là thiếu.
  keys: [tro_cap_thoi_viec, ban_sao_ho_so]
muc:
  - {stt: 1, key: hop_dong_dang_cham_dut, ten: "Hợp đồng lao động đang chấm dứt: số, ngày ký, loại hợp đồng", can_cu: "45/2019/QH14 > Điều 34 > Khoản 3", tu_khoa: ["hợp đồng lao động số", "ký ngày", "hợp đồng lao động đã ký"]}
  - {stt: 2, key: y_chi_thoa_thuan, ten: "Ý chí tự nguyện của cả hai bên về việc chấm dứt hợp đồng lao động", can_cu: "45/2019/QH14 > Điều 34 > Khoản 3", tu_khoa: ["thỏa thuận chấm dứt", "thoả thuận chấm dứt", "hai bên thống nhất", "tự nguyện"]}
  - {stt: 3, key: thoi_diem_cham_dut, ten: "Thời điểm chấm dứt và ngày làm việc cuối cùng", can_cu: "45/2019/QH14 > Điều 34 > Khoản 3", tu_khoa: ["kể từ ngày", "ngày làm việc cuối cùng", "chấm dứt kể từ"]}
  - {stt: 4, key: thanh_toan_14_ngay, ten: "Thanh toán đầy đủ các khoản liên quan đến quyền lợi của mỗi bên trong 14 ngày làm việc", can_cu: "45/2019/QH14 > Điều 48 > Khoản 1", tu_khoa: ["14 ngày làm việc", "thanh toán đầy đủ"]}
  - {stt: 5, key: cac_khoan_uu_tien, ten: "Tiền lương, bảo hiểm xã hội, bảo hiểm y tế, bảo hiểm thất nghiệp, trợ cấp và các quyền lợi khác của người lao động", can_cu: "45/2019/QH14 > Điều 48 > Khoản 2", tu_khoa: ["tiền lương", "bảo hiểm xã hội", "quyền lợi khác"]}
  - {stt: 6, key: tro_cap_thoi_viec, ten: "Trợ cấp thôi việc khi người lao động đã làm việc thường xuyên từ đủ 12 tháng", can_cu: "45/2019/QH14 > Điều 46 > Khoản 1", tu_khoa: ["trợ cấp thôi việc"]}
  - {stt: 7, key: chot_bhxh_tra_giay_to, ten: "Người sử dụng lao động xác nhận thời gian đóng bảo hiểm và trả lại bản chính giấy tờ đã giữ", can_cu: "45/2019/QH14 > Điều 48 > Khoản 3 > Điểm a", tu_khoa: ["xác nhận thời gian đóng bảo hiểm", "trả lại bản chính giấy tờ", "sổ bảo hiểm xã hội"]}
  - {stt: 8, key: ban_sao_ho_so, ten: "Cung cấp bản sao tài liệu liên quan đến quá trình làm việc khi người lao động yêu cầu, chi phí do người sử dụng lao động trả", can_cu: "45/2019/QH14 > Điều 48 > Khoản 3 > Điểm b", tu_khoa: ["bản sao các tài liệu", "quá trình làm việc"]}
```

- [ ] **Step 4: Thêm giá trị vào `LoaiVanBan`** (`src/models/schemas.py`) — sau dòng `"thoa_thuan_bao_mat",`:

```python
    "thoa_thuan_cham_dut_hdld",
```

- [ ] **Step 5: Đăng ký FE** (`frontend/src/lib/mau-van-ban.ts`)

Sau mục `don-xin-nghi-viec` trong `MAU`:

```ts
  {
    // Mặt thứ ba của chấm dứt HĐLĐ: NLĐ đơn phương (Đ35, đơn xin nghỉ việc),
    // NSDLĐ đơn phương (Đ34/Đ36, quyết định chấm dứt) — và đây là HAI BÊN cùng
    // thoả thuận (Đ34.3). Backend `thoa_thuan_cham_dut_hdld`, checklist riêng.
    id: "thoa-thuan-cham-dut-hop-dong-lao-dong",
    ten: "Thoả thuận chấm dứt hợp đồng lao động",
    moTa: "Hai bên cùng thoả thuận chấm dứt hợp đồng lao động: thời điểm, các khoản thanh toán, giấy tờ.",
    soTruong: 8,
    nhom: "lao-dong",
    kyHieu: "TTCD",
    canCu: [BLLD],
  },
```

Cuối `LOAI_BACKEND` (sau dòng `"don-xin-nghi-viec": ...,`):

```ts
  "thoa-thuan-cham-dut-hop-dong-lao-dong": { loai: "thoa_thuan_cham_dut_hdld", phamVi: "noi_dung" },
```

Cuối union `LoaiVanBanBackend`: đổi `| "don_xin_nghi_viec";` thành `| "don_xin_nghi_viec"` và thêm dòng `| "thoa_thuan_cham_dut_hdld";`.

`frontend/scripts/kiem-khung.ts`: `assert.equal(MAU.length, 28);` → `assert.equal(MAU.length, 29);`.

- [ ] **Step 6: Tạo `docs/plans/active/soan-thao-trong-chat.md`**

```markdown
# Execution Plan: Soạn thảo trong chat và card câu trả lời

Date: 2026-09-06

## Status

Active

## Outcome

Trên `/dung-thu`: mọi câu trả lời nằm trong card; câu "soạn cho tôi hợp đồng
nghỉ việc" ra card gợi ý đúng loại (kèm loại thay thế) với nút "Soạn ngay tại
đây" mở màn soạn thảo ở khung bên cạnh; điền → soát → tải .docx/.pdf không rời
hội thoại. Kho mẫu có thêm "Thoả thuận chấm dứt hợp đồng lao động".

## Context

- Spec: `docs/superpowers/specs/2026-09-06-soan-thao-trong-chat-design.md`
- Plan từng bước: `docs/superpowers/plans/2026-09-06-soan-thao-trong-chat.md`
- Tiếp nối: `docs/plans/completed/soul-trich-dan-bam-duoc.md`

## Scope

In scope: checklist mới; router trả loại văn bản; `soan_thao_goi_y` trong
response; card bọc mọi trả lời; nhánh `huong_dan_soan_thao` có nút; tách
`KhongGianSoanThao`; khung soạn thảo bên phải; bẫy `soan_thao`.

Out of scope: trích dữ kiện từ câu chat; biểu mẫu trọn trong card; lưu hội
thoại; mở kho HN&GĐ.

## Approach

Bước 0 mẫu mới + hợp đồng dữ liệu → Bước 1 hai worktree (BE: router/assemble/
bẫy; FE: card/tách component/khung) → Bước 2 gộp, đo bẫy với
`ROUTE_PROMPT=prompts/route.v2.md`, đổi mặc định nếu xanh, đóng plan.

## Risks And Recovery

- Router chọn sai loại → giữ `route_prompt` v1; card vẫn có "Chọn loại văn bản".
- Tách component vỡ `/soan-thao` → `npm run build`/typecheck đỏ → revert commit tách.
- Khung soạn thảo chật cạnh chat → co cột chat hoặc phủ toàn màn dưới 80rem.
- `can_cu` mẫu mới không tồn tại → `test_moi_mau` integration đỏ → hạ cấp hoặc bỏ mục.

## Progress

- [ ] Bước 0: Task 1–2
- [ ] Bước 1 BE: Task 3–5
- [ ] Bước 1 FE: Task 6–8
- [ ] Bước 2: Task 9

## Decisions

- 2026-09-06: Q1 mức B (biểu mẫu + bản thảo, không LLM viết điều khoản); Q2
  router LLM chọn loại; Q3 thêm mẫu thoả thuận chấm dứt; Q4 PA1 khung bên
  cạnh; Q5 card cho mọi trả lời. Chủ dự án chọn.

## Validation

- Focused proof: `pytest tests/test_agents/test_route.py tests/test_agents/test_assemble.py
  tests/test_agents/test_huong_dan_soan_thao.py tests/test_services/test_moi_mau.py
  tests/test_eval/test_run_trap.py`; `npm run kiem-khung`, `kiem-goi-y-soan-thao`.
- Integration / end-to-end: `pytest tests/test_api/test_tra_cuu.py`; 3 câu bẫy
  `soan_thao` với route v2; kiểm bằng mắt trên `/dung-thu`.
- Repository-required checks: `make lint`, pytest rộng, `npm run typecheck && npm run lint && npm run build`.

## Result

Chưa xong.
```

- [ ] **Step 7: Chạy kiểm**

```bash
python -m pytest tests/test_services/test_moi_mau.py -q 2>&1 | tail -1
python -c "from src.agents.graph_soan_thao import cac_loai; print('thoa_thuan_cham_dut_hdld' in cac_loai(), len(cac_loai()))"
make lint
cd frontend && node scripts/kiem-khung.ts && npm run typecheck && cd ..
```

Expected: số `passed` tăng so với Step 2, không `failed`; in `True 29`; `kiem-khung` đạt với 29; typecheck sạch. Nếu `test_moi_mau` báo `can_cu không tồn tại`, quay lại Step 1 — không sửa test.

- [ ] **Step 8: Commit**

```bash
git add config/checklist_thoa_thuan_cham_dut_hdld.yaml src/models/schemas.py \
        frontend/src/lib/mau-van-ban.ts frontend/scripts/kiem-khung.ts \
        docs/plans/active/soan-thao-trong-chat.md
git commit -m "feat(mau): add two-party labour-contract termination agreement checklist

Bases verified against provisions (BLLĐ 34.3, 46.1, 48.1, 48.2, 48.3.a, 48.3.b).
Registered on both sides (LoaiVanBan literal, MAU/LOAI_BACKEND) and the
durable plan for in-chat drafting is opened.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Hợp đồng dữ liệu — `soan_thao` trong response, `route_prompt`, `prompt_path` cho `route`

**Files:**
- Modify: `src/models/schemas.py` (sau class `DocumentOut`; `TraCuuResponse` sau `documents`)
- Modify: `src/agents/state.py` (cuối `KLawState`)
- Modify: `src/api/routes.py` (`_payload_cache`, `tra_cuu_response`)
- Modify: `src/config.py` (cạnh `assemble_prompt`/`rewrite_prompt`)
- Modify: `src/agents/nodes/route.py` (chữ ký + đọc template), `src/agents/graph_tra_cuu.py` (`n_route`)
- Modify: `frontend/src/lib/klaw.ts` (sau `VanBanTraLoi`; trong `TraCuuKetQua` sau `documents`)
- Test: `tests/test_api/test_tra_cuu.py`, `tests/test_config.py`, `tests/test_agents/test_route.py`

**Interfaces:**
- Produces: `SoanThaoGoiYOut{loai: str|None, ten: str|None, ly_do: str, thay_the: list[LoaiGoiYOut{loai, ten}], ho_tro: bool}`; `TraCuuResponse.soan_thao: SoanThaoGoiYOut | None = None`; `KLawState.soan_thao_goi_y: dict | None`; `Settings.route_prompt: str`; `route(state, llm, model, prompt_path: Path | None = None)`; FE `SoanThaoGoiY`, `TraCuuKetQua.soan_thao?: SoanThaoGoiY | null`. Task 3 điền `soan_thao_goi_y` thô, Task 4 điền bản đầy đủ, Task 8 đọc `ketQua.soan_thao`.

- [ ] **Step 1: Viết test đỏ**

Thêm cuối `tests/test_api/test_tra_cuu.py`:

```python
async def test_soan_thao_goi_y_khong_bi_loc_o_bien_HTTP(client, monkeypatch):
    """Spec 2026-09-06 (soạn thảo trong chat) §4.3: gợi ý loại văn bản phải
    sống qua pydantic ở biên — cùng lớp lỗi khop_tai_id/doc_id/bang/nguon/documents."""
    from src.agents.nodes.assemble import ResultType
    from src.api import routes

    class FakeGraph:
        async def ainvoke(self, *a, **k):
            return {
                "result_type": ResultType.huong_dan_soan_thao, "answer": "Tôi hiểu bạn cần đơn xin nghỉ việc.",
                "citations": [], "warnings": [],
                "soan_thao_goi_y": {
                    "loai": "don_xin_nghi_viec", "ten": "đơn xin nghỉ việc", "ly_do": "bạn là người lao động muốn nghỉ",
                    "thay_the": [{"loai": "thoa_thuan_cham_dut_hdld", "ten": "thoả thuận chấm dứt hợp đồng lao động"}],
                    "ho_tro": True,
                },
            }

    monkeypatch.setattr(routes, "_g", lambda: FakeGraph())
    r = await client.post("/api/v1/tra-cuu", json={"query": "soạn cho tôi đơn nghỉ việc"})
    assert r.status_code == 200
    gy = r.json()["soan_thao"]
    assert gy["loai"] == "don_xin_nghi_viec" and gy["ho_tro"] is True
    assert gy["thay_the"][0]["loai"] == "thoa_thuan_cham_dut_hdld"


def test_tra_cuu_response_chap_nhan_payload_cache_cu_khong_co_soan_thao():
    from src.api.routes import tra_cuu_response

    payload = {"result_type": "huong_dan_soan_thao", "answer": "x", "warnings": [],
               "coverage_note": None, "nguon": [], "citations": []}
    assert tra_cuu_response(payload, "t", "full").soan_thao is None
```

Thêm vào `tests/test_config.py`:

```python
def test_route_prompt_mac_dinh_v1():
    from src.config import Settings

    assert Settings(_env_file=None).route_prompt == "prompts/route.v1.md"
```

Thêm vào `tests/test_agents/test_route.py`:

```python
def test_route_doc_template_tu_prompt_path_khi_duoc_truyen(tmp_path):
    mau = tmp_path / "r.md"
    mau.write_text("MAU-RIENG {cau_hoi}", encoding="utf-8")

    class Ghi(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            self.prompt_cuoi = messages[-1]["content"]
            return super().chat(model, messages, json_schema)

    llm = Ghi({"intent": "tra_cuu"})
    st = route({"query": "x"}, llm, "m", prompt_path=mau)
    assert st["intent"] is Intent.tra_cuu and llm.prompt_cuoi.startswith("MAU-RIENG")
```

- [ ] **Step 2: Chạy, phải đỏ**

```bash
python -m pytest tests/test_api/test_tra_cuu.py tests/test_config.py tests/test_agents/test_route.py -k "soan_thao or route_prompt or prompt_path" -v
```

Expected: FAIL (`KeyError: 'soan_thao'`, `AttributeError: route_prompt`, `TypeError: prompt_path`).

- [ ] **Step 3: `src/models/schemas.py`** — sau class `DocumentOut`:

```python
class LoaiGoiYOut(BaseModel):
    loai: str
    ten: str


class SoanThaoGoiYOut(BaseModel):
    """Gợi ý loại văn bản cho `result_type == huong_dan_soan_thao` (spec
    2026-09-06 soạn thảo trong chat §4.3). `loai` là mã checklist trên đĩa
    (`graph_soan_thao.cac_loai()`), None khi router không chắc hoặc loại
    không có mẫu; FE mở khung soạn thảo theo `loai`, chip theo `thay_the`."""

    loai: str | None
    ten: str | None
    ly_do: str
    thay_the: list[LoaiGoiYOut] = []
    ho_tro: bool
```

Trong `TraCuuResponse`, sau `documents: list[DocumentOut] = []`:

```python
    # Chỉ nhánh `huong_dan_soan_thao` điền; mặc định None cùng lý do `bang`/
    # `documents` (payload cache cũ không có khoá).
    soan_thao: SoanThaoGoiYOut | None = None
```

- [ ] **Step 4: `src/agents/state.py`** — cuối `KLawState`:

```python
    # Gợi ý loại văn bản của router (v2) → assemble kiểm và làm đầy → response
    # `soan_thao`. Khai ở đây vì cùng bẫy LangGraph với `bang`/`nguon`/`documents`.
    soan_thao_goi_y: dict | None
```

- [ ] **Step 5: `src/api/routes.py`** — `_payload_cache` thêm dòng `"soan_thao": st.get("soan_thao_goi_y"),` sau `"documents"`; `tra_cuu_response` thêm `soan_thao=payload.get("soan_thao"),` sau `documents=...`.

- [ ] **Step 6: `src/config.py`** — sau `rewrite_prompt`:

```python
    # Router v2 trả thêm loại văn bản khi ý định là soạn thảo. Đổi qua env
    # `ROUTE_PROMPT=prompts/route.v2.md` để A/B; đổi mặc định sau khi bẫy xanh.
    route_prompt: str = "prompts/route.v1.md"
```

- [ ] **Step 7: `route.py` nhận `prompt_path`; graph truyền**

```python
def route(state: dict, llm, model: str, prompt_path: Path | None = None) -> dict:
    prior_traces = state.get("traces") or {}
    prompt = (prompt_path or PROMPT_PATH).read_text(encoding="utf-8").format(cau_hoi=state["query"])
```

`graph_tra_cuu.py`:

```python
    def n_route(st: KLawState) -> KLawState:
        return route(st, llm, router_model(), prompt_path=Path(s.route_prompt))
```

- [ ] **Step 8: `frontend/src/lib/klaw.ts`** — sau `interface VanBanTraLoi`:

```ts
export interface LoaiGoiY {
  loai: string;
  ten: string;
}

/**
 * Gợi ý loại văn bản khi `result_type === "huong_dan_soan_thao"` — khớp
 * `SoanThaoGoiYOut` của `src/models/schemas.py`. `loai` là mã checklist phía
 * máy chủ; đổi sang slug thẻ bằng `slugCuaLoai()` trong `lib/mau-van-ban.ts`.
 */
export interface SoanThaoGoiY {
  loai: string | null;
  ten: string | null;
  ly_do: string;
  thay_the: LoaiGoiY[];
  ho_tro: boolean;
}
```

Trong `TraCuuKetQua`, sau `documents: VanBanTraLoi[];`:

```ts
  /** Chỉ nhánh `huong_dan_soan_thao`; vắng/null ở mọi nhánh khác và với payload cache cũ. */
  soan_thao?: SoanThaoGoiY | null;
```

- [ ] **Step 9: Chạy, phải xanh**

```bash
python -m pytest tests/test_api/test_tra_cuu.py tests/test_config.py tests/test_agents/test_route.py -q
make lint && ruff format --check src/models/schemas.py src/agents/state.py src/api/routes.py src/config.py src/agents/nodes/route.py src/agents/graph_tra_cuu.py
cd frontend && npm run typecheck && cd ..
python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py
```

Expected: PASS (kể cả `test_moi_field_TraCuuResponse_deu_duoc_KLawState_khai`); lint sạch (format-check chỉ cần dòng mới sạch); typecheck sạch; pytest rộng 0 failed.

- [ ] **Step 10: Commit và tạo worktree**

```bash
git add src/models/schemas.py src/agents/state.py src/api/routes.py src/config.py \
        src/agents/nodes/route.py src/agents/graph_tra_cuu.py frontend/src/lib/klaw.ts \
        tests/test_api/test_tra_cuu.py tests/test_config.py tests/test_agents/test_route.py
git commit -m "feat(api): add soan_thao suggestion to the response contract; route_prompt setting

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git worktree add ../KLAW-be2 -b wt-be-soan && git worktree add ../KLAW-fe2 -b wt-fe-soan
for w in ../KLAW-be2 ../KLAW-fe2; do cp .env.local "$w/"; ln -s "$PWD/.venv" "$w/.venv"; ln -s "$PWD/frontend/node_modules" "$w/frontend/node_modules"; ln -s "$PWD/data/raw" "$w/data/raw"; done
```

---

# BƯỚC 1 — BACKEND (worktree `../KLAW-be2`, nhánh `wt-be-soan`)

### Task 3: Router v2 — chọn loại văn bản trong cùng lượt gọi

**Files:**
- Create: `prompts/route.v2.md`
- Modify: `src/agents/nodes/route.py`
- Test: `tests/test_agents/test_route.py`

**Interfaces:**
- Consumes: `route(state, llm, model, prompt_path=None)` (Task 2); `cac_loai()` từ `src.agents.graph_soan_thao`; `load_checklist_cached(loai).ten` (import từ nơi `src/api/routes.py` đang import — kiểm bằng `grep -n "load_checklist_cached" src/api/routes.py src/services/checklist.py src/agents/graph_soan_thao.py`).
- Produces: `schema_v2() -> dict`; `danh_sach_loai() -> str`; state `soan_thao_goi_y = {"loai": str|None, "ly_do": str, "thay_the": list[str]}` khi template v2 (None khi intent khác `soan_thao`); khoá vắng khi template v1. Task 4 đọc dict này.

- [ ] **Step 1: Viết test đỏ** — thêm vào `tests/test_agents/test_route.py`:

```python
V2_MAU = "Phân loại. Khi soan_thao chọn loai_van_ban trong:\n{danh_sach_loai}\nCÂU HỎI: {cau_hoi}"


def _v2(tmp_path):
    p = tmp_path / "route.v2.md"
    p.write_text(V2_MAU, encoding="utf-8")
    return p


def test_v2_schema_enum_dung_tu_checklist_tren_dia():
    from src.agents.graph_soan_thao import cac_loai
    from src.agents.nodes.route import schema_v2

    enum = schema_v2()["properties"]["loai_van_ban"]["enum"]
    assert set(enum) == set(cac_loai()) | {"khong_ro"}
    assert "thoa_thuan_cham_dut_hdld" in enum
    assert schema_v2()["required"] == ["intent", "loai_van_ban", "thay_the", "ly_do"]


def test_v2_danh_sach_loai_co_ten_doc_duoc():
    from src.agents.nodes.route import danh_sach_loai

    ds = danh_sach_loai()
    assert "`don_xin_nghi_viec` — đơn xin nghỉ việc" in ds
    assert ds.count("\n") >= 28


def test_v2_soan_thao_ghi_goi_y_vao_state(tmp_path):
    class Ghi(FakeLlm):
        def chat(self, model, messages, json_schema=None):
            self.schema = json_schema
            self.prompt = messages[-1]["content"]
            return super().chat(model, messages, json_schema)

    llm = Ghi({"intent": "soan_thao", "loai_van_ban": "don_xin_nghi_viec",
               "thay_the": ["thoa_thuan_cham_dut_hdld"], "ly_do": "bạn là người lao động muốn nghỉ"})
    st = route({"query": "soạn cho tôi hợp đồng nghỉ việc"}, llm, "m", prompt_path=_v2(tmp_path))
    assert st["intent"] is Intent.soan_thao
    assert st["soan_thao_goi_y"] == {"loai": "don_xin_nghi_viec", "ly_do": "bạn là người lao động muốn nghỉ",
                                     "thay_the": ["thoa_thuan_cham_dut_hdld"]}
    assert llm.schema["required"][0] == "intent" and "loai_van_ban" in llm.schema["properties"]
    assert "`don_xin_nghi_viec` — " in llm.prompt, "danh sách loại phải được điền vào template"


def test_v2_khong_ro_thanh_None_va_intent_khac_khong_goi_y(tmp_path):
    st = route({"query": "x"}, FakeLlm({"intent": "soan_thao", "loai_van_ban": "khong_ro", "thay_the": [], "ly_do": ""}),
               "m", prompt_path=_v2(tmp_path))
    assert st["soan_thao_goi_y"] == {"loai": None, "ly_do": "", "thay_the": []}
    st2 = route({"query": "x"}, FakeLlm({"intent": "tra_cuu", "loai_van_ban": "khong_ro", "thay_the": [], "ly_do": ""}),
                "m", prompt_path=_v2(tmp_path))
    assert st2["intent"] is Intent.tra_cuu and st2["soan_thao_goi_y"] is None


def test_v1_khong_dat_khoa_goi_y():
    st = route({"query": "soạn hợp đồng"}, FakeLlm({"intent": "soan_thao"}), "m")
    assert "soan_thao_goi_y" not in st


def test_v2_khong_tiem_soul():
    from pathlib import Path
    assert "src.services.prompts" not in Path("src/agents/nodes/route.py").read_text(encoding="utf-8")
```

- [ ] **Step 2: Chạy, phải đỏ**

```bash
python -m pytest tests/test_agents/test_route.py -k "v2_ or v1_khong" -v
```

Expected: `ImportError: schema_v2`.

- [ ] **Step 3: Tạo `prompts/route.v2.md`** — bắt đầu bằng TOÀN BỘ nội dung `prompts/route.v1.md` trừ hai dòng cuối (`Trả về JSON…` và `CÂU HỌI…`), rồi nối:

```
Khi ý định là `soan_thao`, chọn thêm `loai_van_ban` — mã của loại văn bản người
hỏi cần, lấy ĐÚNG một mã trong danh sách dưới (mỗi dòng: mã — tên). Nêu `ly_do`
một câu ngắn bằng lời thường, nói vì sao loại đó khớp với điều họ mô tả (ai lập,
gửi cho ai, mục đích), không dẫn số Điều. Nếu hai hoặc ba loại cùng hợp, đặt loại
hợp nhất vào `loai_van_ban` và tối đa hai loại còn lại vào `thay_the`. Không chắc
loại nào thì `loai_van_ban` là `khong_ro` và `thay_the` là các loại gần nhất.
Với mọi ý định khác `soan_thao`: `loai_van_ban` là `khong_ro`, `thay_the` rỗng,
`ly_do` rỗng.

Ví dụ: "hợp đồng nghỉ việc" do người lao động tự viết → `don_xin_nghi_viec`,
thay thế `thoa_thuan_cham_dut_hdld`; "hai bên thoả thuận nghỉ" →
`thoa_thuan_cham_dut_hdld`; "công ty ra quyết định cho nghỉ" →
`quyet_dinh_cham_dut_hdld`.

DANH SÁCH LOẠI VĂN BẢN:
{danh_sach_loai}

Trả về JSON: {{"intent": "soan_thao", "loai_van_ban": "don_xin_nghi_viec", "thay_the": ["thoa_thuan_cham_dut_hdld"], "ly_do": "..."}}

CÂU HỎI: {cau_hoi}
```

Kiểm placeholder: `python3 -c "from pathlib import Path; Path('prompts/route.v2.md').read_text(encoding='utf-8').format(cau_hoi='c', danh_sach_loai='d'); print('OK')"`.

- [ ] **Step 4: Sửa `src/agents/nodes/route.py`**

Import thêm (sau `from pathlib import Path`):

```python
from src.agents.graph_soan_thao import cac_loai
from src.services.checklist import load_checklist_cached  # đổi module nếu grep ở Interfaces chỉ chỗ khác
```

Sau `INTENT_SCHEMA` thêm:

```python
_INTENT_ENUM = ["tra_cuu", "soan_thao", "ngoai_pham_vi", "gioi_thieu", "hoi_ve_kho"]


def schema_v2() -> dict:
    """Schema strict của template v2 (spec soạn-thảo-trong-chat §4.1). Enum loại
    dựng LÚC GỌI từ checklist trên đĩa — thêm một file YAML là router biết ngay,
    không có danh sách viết tay để lệch. Strict đòi mọi khoá `required`, nên đây
    là schema riêng thay vì v1 cộng khoá optional (cùng lý do QUERIES_V2_SCHEMA)."""
    loai = sorted(cac_loai())
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["intent", "loai_van_ban", "thay_the", "ly_do"],
        "properties": {
            "intent": {"type": "string", "enum": _INTENT_ENUM},
            "loai_van_ban": {"type": "string", "enum": [*loai, "khong_ro"]},
            "thay_the": {"type": "array", "items": {"type": "string", "enum": loai}, "maxItems": 2},
            "ly_do": {"type": "string"},
        },
    }


def danh_sach_loai() -> str:
    """Một dòng `mã — tên` cho mỗi checklist, điền vào `{danh_sach_loai}` của v2."""
    return "\n".join(f"- `{loai}` — {load_checklist_cached(loai).ten}" for loai in sorted(cac_loai()))
```

Thân `route()` — thay từ dòng `prompt = ...` tới `return` bằng:

```python
    mau = (prompt_path or PROMPT_PATH).read_text(encoding="utf-8")
    # Template nhắc `loai_van_ban` là template v2 — chọn theo NỘI DUNG, không theo tên file.
    la_v2 = "loai_van_ban" in mau
    prompt = mau.format(cau_hoi=state["query"], danh_sach_loai=danh_sach_loai() if la_v2 else "")
    # llm.chat(...) NẰM NGOÀI try — xem docstring module: lỗi hạ tầng phải nổ ra ngoài.
    raw, usage = llm.chat(model, [{"role": "user", "content": prompt}],
                          json_schema=schema_v2() if la_v2 else INTENT_SCHEMA)
    data: dict = {}
    try:
        data = json.loads(raw)
        intent = Intent(data["intent"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError, RuntimeError):
        # Route sai sang ngoai_pham_vi làm hệ thống từ chối oan. Mặc định tra_cuu.
        intent = Intent.tra_cuu
        data = data if isinstance(data, dict) else {}
    goi_y: dict | None = None
    if la_v2 and intent is Intent.soan_thao:
        lv = data.get("loai_van_ban")
        goi_y = {
            "loai": lv if isinstance(lv, str) and lv != "khong_ro" else None,
            "ly_do": str(data.get("ly_do") or "")[:300],
            "thay_the": [t for t in (data.get("thay_the") or []) if isinstance(t, str)][:2],
        }
    return {
        **state,
        "intent": intent,
        **({"soan_thao_goi_y": goi_y} if la_v2 else {}),
        "traces": {
            **prior_traces,
            "route_model": model,
            "route_token_in": usage.token_in if usage else 0,
            "route_token_out": usage.token_out if usage else 0,
            "route_cost_usd": usage.cost_usd if usage else 0.0,
        },
    }
```

Giữ nguyên chú thích dài về "llm.chat NẰM NGOÀI try" (rút thành một dòng như trên là chấp nhận được, hoặc để nguyên).

- [ ] **Step 5: Chạy, phải xanh**

```bash
python -m pytest tests/test_agents/test_route.py tests/test_agents/test_soul.py -q
make lint && ruff format --check src/agents/nodes/route.py tests/test_agents/test_route.py
python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py
```

Expected: PASS; `test_soul.py` vẫn khẳng định route không import SOUL; pytest rộng 0 failed.

- [ ] **Step 6: Commit**

```bash
git add prompts/route.v2.md src/agents/nodes/route.py tests/test_agents/test_route.py
git commit -m "feat(route): v2 template picks the document type from the checklist catalog

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `assemble` — nhánh `soan_thao` dựng gợi ý, 0 token

**Files:**
- Modify: `src/agents/nodes/assemble.py` (hằng số cạnh `HUONG_DAN_SOAN_THAO`; nhánh `if state.get("intent") == "soan_thao":`)
- Test: `tests/test_agents/test_assemble.py`, `tests/test_agents/test_huong_dan_soan_thao.py`

**Interfaces:**
- Consumes: `state["soan_thao_goi_y"]` thô (Task 3); `cac_loai()`, `load_checklist_cached(loai).ten`.
- Produces: `_goi_y_soan_thao(tho: dict | None) -> tuple[dict | None, str]`; state `soan_thao_goi_y` đầy đủ `{loai, ten, ly_do, thay_the:[{loai,ten}], ho_tro}` hoặc `None`; hằng số `GOI_Y_SOAN_THAO`, `GOI_Y_SOAN_THAO_CHUA_CO`, `GAN_NHAT_CO`, `GAN_NHAT_KHONG`.

- [ ] **Step 1: Viết test đỏ** — thêm vào `tests/test_agents/test_assemble.py`:

```python
def test_soan_thao_co_goi_y_dung_ten_tu_checklist_va_loc_thay_the():
    class Never(FakeLlm):
        def chat(self, *a, **k):
            raise AssertionError("nhánh soan_thao không gọi LLM")

    st = assemble({"intent": "soan_thao", "query": "soạn cho tôi hợp đồng nghỉ việc",
                   "soan_thao_goi_y": {"loai": "don_xin_nghi_viec", "ly_do": "bạn là người lao động muốn nghỉ",
                                       "thay_the": ["thoa_thuan_cham_dut_hdld", "loai_khong_co", "don_xin_nghi_viec"]}},
                  {}, Never(), "m")
    assert st["result_type"] is ResultType.huong_dan_soan_thao
    gy = st["soan_thao_goi_y"]
    assert gy["loai"] == "don_xin_nghi_viec" and gy["ten"] == "đơn xin nghỉ việc" and gy["ho_tro"] is True
    assert [t["loai"] for t in gy["thay_the"]] == ["thoa_thuan_cham_dut_hdld"]
    assert st["answer"].startswith("Tôi hiểu bạn cần đơn xin nghỉ việc: bạn là người lao động muốn nghỉ")
    assert "khung bên cạnh" in st["answer"]
    assert st["traces"]["assemble_token_in"] == 0


def test_soan_thao_loai_la_thanh_khong_ho_tro_va_neu_gan_nhat():
    st = assemble({"intent": "soan_thao", "query": "x",
                   "soan_thao_goi_y": {"loai": "loai_khong_co", "ly_do": "", "thay_the": ["don_xin_nghi_viec"]}},
                  {}, FakeLlm(), "m")
    gy = st["soan_thao_goi_y"]
    assert gy["loai"] is None and gy["ho_tro"] is False
    assert st["answer"].startswith("Kho mẫu của tôi chưa có loại văn bản này.")
    assert "đơn xin nghỉ việc" in st["answer"]


def test_soan_thao_khong_goi_y_giu_huong_dan_cu():
    from src.agents.nodes.assemble import HUONG_DAN_SOAN_THAO
    st = assemble({"intent": "soan_thao", "query": "x"}, {}, FakeLlm(), "m")
    assert st["answer"] == HUONG_DAN_SOAN_THAO and st["soan_thao_goi_y"] is None
    assert "Chọn loại văn bản" in HUONG_DAN_SOAN_THAO
```

- [ ] **Step 2: Chạy, phải đỏ**

```bash
python -m pytest tests/test_agents/test_assemble.py -k soan_thao -v
```

Expected: FAIL — `KeyError: 'soan_thao_goi_y'`.

- [ ] **Step 3: Sửa `assemble.py`**

Import: `from src.agents.graph_soan_thao import cac_loai` và `from src.services.checklist import load_checklist_cached` (cùng module Task 3 đã xác minh).

Đổi đoạn cuối của `HUONG_DAN_SOAN_THAO`: câu `"Bạn mở màn Soạn thảo, chọn loại văn bản rồi điền biểu mẫu. Tôi dựng bản thảo "` thành `"Bạn bấm Chọn loại văn bản bên dưới rồi điền biểu mẫu. Tôi dựng bản thảo "` (phần còn lại giữ nguyên).

Thêm ngay sau `HUONG_DAN_SOAN_THAO`:

```python
# Spec soạn-thảo-trong-chat §4.2 — lời đáp khi router (v2) đã đoán được loại.
# Không nêu số Điều ở đây: căn cứ nằm trong từng mục của checklist, hiện ở khung
# soạn thảo, không phải trong câu mời.
GOI_Y_SOAN_THAO = (
    "Tôi hiểu bạn cần {ten}: {ly_do}\n"
    "\n"
    "Bạn điền dữ kiện ở khung bên cạnh, tôi dựng bản thảo kèm căn cứ cho từng mục, "
    "soát lại theo luật trong kho, rồi bạn tải .docx hoặc .pdf ngay tại đây."
)
GOI_Y_SOAN_THAO_CHUA_CO = "Kho mẫu của tôi chưa có loại văn bản này. {gan_nhat}"
GAN_NHAT_CO = "Gần nhất là {ten_thay_the} — bạn chọn một loại để tôi mở biểu mẫu."
GAN_NHAT_KHONG = (
    "Bạn mô tả rõ hơn văn bản cần soạn — ai lập, gửi cho ai, về việc gì — hoặc bấm "
    "Chọn loại văn bản bên dưới."
)
LY_DO_MAC_DINH = "đây là loại văn bản khớp với điều bạn mô tả."


def _ten_loai(loai: str) -> str:
    return load_checklist_cached(loai).ten


def _goi_y_soan_thao(tho: dict | None) -> tuple[dict | None, str]:
    """Kiểm 0 token gợi ý của router rồi dựng `soan_thao_goi_y` + `answer`.
    `loai` phải là checklist THẬT trên đĩa; `thay_the` lọc còn loại thật, khác
    `loai`, tối đa hai. Không có gợi ý (route v1) → lời hướng dẫn cũ."""
    if tho is None:
        return None, HUONG_DAN_SOAN_THAO
    co = cac_loai()
    loai = tho.get("loai") if tho.get("loai") in co else None
    thay_the = [{"loai": t, "ten": _ten_loai(t)}
                for t in dict.fromkeys(tho.get("thay_the") or []) if t in co and t != loai][:2]
    ly_do = " ".join(str(tho.get("ly_do") or "").split())[:300]
    if loai is None:
        gan = GAN_NHAT_CO.format(ten_thay_the=" hoặc ".join(t["ten"] for t in thay_the)) if thay_the else GAN_NHAT_KHONG
        return ({"loai": None, "ten": None, "ly_do": ly_do, "thay_the": thay_the, "ho_tro": False},
                GOI_Y_SOAN_THAO_CHUA_CO.format(gan_nhat=gan))
    ten = _ten_loai(loai)
    return ({"loai": loai, "ten": ten, "ly_do": ly_do, "thay_the": thay_the, "ho_tro": True},
            GOI_Y_SOAN_THAO.format(ten=ten, ly_do=ly_do or LY_DO_MAC_DINH))
```

Nhánh trong `assemble()`:

```python
    if state.get("intent") == "soan_thao":
        # (giữ chú thích cũ về đường rẽ tắt 0 token)
        goi_y, answer = _goi_y_soan_thao(state.get("soan_thao_goi_y"))
        return _base(state, ResultType.huong_dan_soan_thao, answer=answer, soan_thao_goi_y=goi_y)
```

- [ ] **Step 4: Chạy — kể cả test giọng và test hướng dẫn cũ**

```bash
python -m pytest tests/test_agents/test_assemble.py tests/test_agents/test_huong_dan_soan_thao.py tests/test_agents/test_giong_tra_loi.py -q
```

Nếu `test_huong_dan_soan_thao.py` ghim câu "mở màn Soạn thảo", đổi assertion đó sang "Chọn loại văn bản bên dưới" (cùng ý, câu mới). Không nới test giọng.

```bash
make lint && ruff format --check src/agents/nodes/assemble.py tests/test_agents/test_assemble.py
python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py
```

- [ ] **Step 5: Commit**

```bash
git add src/agents/nodes/assemble.py tests/test_agents/test_assemble.py tests/test_agents/test_huong_dan_soan_thao.py
git commit -m "feat(assemble): turn the router's document-type guess into a verified drafting suggestion

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Bẫy nhóm `soan_thao`

**Files:**
- Modify: `eval/datasets/trap.yaml` (cuối `items:`; header 54 → 57)
- Modify: `eval/run_trap.py` (`dung()`)
- Test: `tests/test_eval/test_run_trap.py`

**Interfaces:**
- Consumes: `st["soan_thao_goi_y"]` (Task 4).
- Produces: `ky_vong: soan_thao_loai` với trường `loai_chap_nhan: list[str | null]`.

- [ ] **Step 1: Test đỏ** — thêm vào `tests/test_eval/test_run_trap.py`:

```python
def test_soan_thao_loai():
    it = {"ky_vong": "soan_thao_loai", "loai_chap_nhan": ["thoa_thuan_cham_dut_hdld", "don_xin_nghi_viec"]}
    assert dung(it, {"result_type": "huong_dan_soan_thao", "soan_thao_goi_y": {"loai": "don_xin_nghi_viec", "ho_tro": True}})
    assert not dung(it, {"result_type": "huong_dan_soan_thao", "soan_thao_goi_y": {"loai": "hdld", "ho_tro": True}})
    assert not dung(it, {"result_type": "answer", "soan_thao_goi_y": None})
    it_null = {"ky_vong": "soan_thao_loai", "loai_chap_nhan": ["ban_tu_khai", None]}
    assert dung(it_null, {"result_type": "huong_dan_soan_thao", "soan_thao_goi_y": {"loai": None, "ho_tro": False}})
```

- [ ] **Step 2: Đỏ** — `python -m pytest tests/test_eval/test_run_trap.py -k soan_thao -v` → FAIL (`dung` trả False).

- [ ] **Step 3: `dung()`** — trước dòng `return False` cuối:

```python
    if kv == "soan_thao_loai":
        gy = st.get("soan_thao_goi_y") or {}
        return rt == "huong_dan_soan_thao" and gy.get("loai") in it.get("loai_chap_nhan", [])
```

- [ ] **Step 4: `trap.yaml`** — cuối `items:`:

```yaml
  # ── Nhóm 5: soạn thảo trong chat (spec 2026-09-06) — router phải ra đúng loại
  #    checklist; `null` trong loai_chap_nhan chấp nhận "chưa có mẫu" ────────────
  - id: trap-soan-01
    cau_hoi: "soạn cho tôi hợp đồng nghỉ việc"
    nhom: soan_thao
    ky_vong: soan_thao_loai
    loai_chap_nhan: [thoa_thuan_cham_dut_hdld, don_xin_nghi_viec]
  - id: trap-soan-02
    cau_hoi: "Soạn giúp tôi hợp đồng lao động xác định thời hạn 12 tháng cho vị trí nhân viên kinh doanh."
    nhom: soan_thao
    ky_vong: soan_thao_loai
    loai_chap_nhan: [hdld]
  - id: trap-soan-03
    cau_hoi: "viết cho tôi bản kiểm điểm cá nhân"
    nhom: soan_thao
    ky_vong: soan_thao_loai
    loai_chap_nhan: [ban_tu_khai, van_ban_giai_trinh, null]
```

Header: `54 câu` → `57 câu`, cộng `+3` vào phép cộng nhóm, thêm một dòng mô tả nhóm 5.

- [ ] **Step 5: Xanh**

```bash
python -m pytest tests/test_eval/test_run_trap.py -q && python3 -c "import yaml; print(len(yaml.safe_load(open('eval/datasets/trap.yaml'))['items']))"
make lint && ruff check eval/run_trap.py
```

Expected: PASS; in `57`.

- [ ] **Step 6: Commit**

```bash
git add eval/datasets/trap.yaml eval/run_trap.py tests/test_eval/test_run_trap.py
git commit -m "feat(eval): trap group for in-chat drafting type detection

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

# BƯỚC 1 — FRONTEND (worktree `../KLAW-fe2`, nhánh `wt-fe-soan`)

Mọi lệnh npm/node chạy trong `frontend/`; pytest giọng chạy từ gốc worktree:
`python -m pytest tests/test_agents/test_giong_tra_loi.py -q` sau mỗi lần sửa `TheKetQua.tsx`.

### Task 6: Card cho mọi câu trả lời + `slugCuaLoai`

**Files:**
- Modify: `frontend/src/routes/dung-thu.tsx` (hàm `Luot`)
- Modify: `frontend/src/lib/mau-van-ban.ts` (cuối file)
- Create: `frontend/scripts/kiem-goi-y-soan-thao.ts`
- Modify: `frontend/package.json` (scripts)

**Interfaces:**
- Produces: `slugCuaLoai(loai: string): string[]` (đảo `LOAI_BACKEND`, `hdld` → 2 slug, loại lạ → `[]`). Task 8 dùng.

- [ ] **Step 1: Kiểm đỏ `frontend/scripts/kiem-goi-y-soan-thao.ts`**

```ts
/**
 * `slugCuaLoai`: mã checklist phía máy chủ → slug thẻ FE. `hdld` có HAI thẻ
 * (xác định / không xác định thời hạn); loại chưa có thẻ → [] để card rơi về
 * nút "Chọn loại văn bản". Chạy: `npm run kiem-goi-y-soan-thao`.
 */
import assert from "node:assert/strict";
import { LOAI_BACKEND, slugCuaLoai } from "../src/lib/mau-van-ban.ts";

{
  const hdld = slugCuaLoai("hdld").sort();
  assert.deepEqual(hdld, ["hop-dong-lao-dong-khong-xac-dinh-thoi-han", "hop-dong-lao-dong-xac-dinh-thoi-han"]);
}
{
  assert.deepEqual(slugCuaLoai("don_xin_nghi_viec"), ["don-xin-nghi-viec"]);
  assert.deepEqual(slugCuaLoai("thoa_thuan_cham_dut_hdld"), ["thoa-thuan-cham-dut-hop-dong-lao-dong"]);
}
{
  assert.deepEqual(slugCuaLoai("khong_co_loai_nay"), []);
}
// Mọi slug trả về phải là khoá thật của LOAI_BACKEND.
{
  for (const [, v] of Object.entries(LOAI_BACKEND)) {
    for (const s of slugCuaLoai(v.loai)) assert.ok(s in LOAI_BACKEND, s);
  }
}
console.info("kiem-goi-y-soan-thao: 4/4 đạt");
```

- [ ] **Step 2: Đỏ** — `node scripts/kiem-goi-y-soan-thao.ts` → lỗi import `slugCuaLoai`.

- [ ] **Step 3: Thêm cuối `frontend/src/lib/mau-van-ban.ts`**

```ts
/**
 * Đảo `LOAI_BACKEND`: mã checklist máy chủ → các slug thẻ. `hdld` trả hai slug
 * vì HĐLĐ xác định và không xác định thời hạn dùng chung checklist; loại chưa
 * có thẻ (vd. `quyet_dinh_ky_luat`) trả [] — card gợi ý rơi về nút chọn tay.
 */
export function slugCuaLoai(loai: string): string[] {
  return Object.entries(LOAI_BACKEND)
    .filter(([, v]) => v.loai === loai)
    .map(([slug]) => slug);
}
```

- [ ] **Step 4: Card cho mọi trả lời** — trong `frontend/src/routes/dung-thu.tsx`, hàm `Luot`, đổi

```tsx
      <div className="mt-4">{children}</div>
```

thành

```tsx
      {/* Card cho MỌI câu trả lời (spec soạn-thảo-trong-chat §5.1): bọc ở đây
          nên TheKetQua, TrangThaiCho, BaoLoi cùng hưởng; --card và shadow-soft
          đã đo tương phản trong DESIGN.md. */}
      <div className="mt-4 rounded-xl border border-border bg-card p-5 shadow-soft">{children}</div>
```

- [ ] **Step 5: `frontend/package.json`** — thêm `"kiem-goi-y-soan-thao": "node scripts/kiem-goi-y-soan-thao.ts",` và chèn `npm run kiem-goi-y-soan-thao && ` vào chuỗi `"kiem"` ngay sau `npm run kiem-documents && `.

- [ ] **Step 6: Xanh**

```bash
node scripts/kiem-goi-y-soan-thao.ts && npm run typecheck && npm run lint
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/routes/dung-thu.tsx frontend/src/lib/mau-van-ban.ts frontend/scripts/kiem-goi-y-soan-thao.ts frontend/package.json
git commit -m "feat(fe): render every assistant turn in a card; map backend document types to template slugs

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Tách `KhongGianSoanThao` thành component dùng chung

**Files:**
- Create: `frontend/src/components/soan-thao/KhongGianSoanThao.tsx`
- Modify: `frontend/src/routes/soan-thao.$loaiVanBan.tsx` (còn lại `head` + wrapper)

**Interfaces:**
- Produces: `KhongGianSoanThao({ loaiVanBan, trongKhung = false, onDong }: { loaiVanBan: string | null; trongKhung?: boolean | undefined; onDong?: (() => void) | undefined })`. Task 8 render nó trong khung phải với `trongKhung`.

- [ ] **Step 1: Mốc trước khi tách**

```bash
npm run typecheck && npm run build 2>&1 | tail -3 && node scripts/kiem-khung.ts | tail -1
```

Ghi kết quả (phải xanh) để so sau.

- [ ] **Step 2: Di chuyển thân route sang component**

Tạo `frontend/src/components/soan-thao/KhongGianSoanThao.tsx` với:
- Toàn bộ import của route hiện tại TRỪ `createFileRoute` và `SITE_ORIGIN` (`Link` giữ lại nếu còn dùng trong thân). Đường import tương đối `./__root` không còn cần.
- Thêm `import { type ReactNode, useState } from "react";` (gộp với import react sẵn có) và `import { MAU, NHOM } from "@/lib/mau-van-ban";` (gộp).
- Toàn bộ mã từ `/* --- page --- */` tới hết file (các kiểu `Ben`, `NoiDung`, `DieuKhoan`, `Draft`, `draftRong`, `KhongGianSoanThao`, `BenForm`, `DiaChi`, `DieuKhoanRow`, `A4`, `tongTyLe`, `demDieuKhoan`, `demTrong`, `goiYPhamVi`, …), giữ nguyên từng dòng logic.

Thay chữ ký:

```tsx
export function KhongGianSoanThao({
  loaiVanBan,
  trongKhung = false,
  onDong,
}: {
  loaiVanBan: string | null;
  trongKhung?: boolean | undefined;
  onDong?: (() => void) | undefined;
}) {
  // Trong khung chat có thể mở với `null` (chưa chọn mẫu) rồi chọn tại chỗ; route
  // luôn truyền slug thật. State cục bộ để chip chọn mẫu đổi được.
  const [slug, setSlug] = useState<string | null>(loaiVanBan);
  const mau = slug === null ? undefined : mauTheoId(slug);
```

Thay MỌI `loaiVanBan` còn lại trong thân (sau dòng cũ `const { loaiVanBan } = Route.useParams();`, nay xoá) bằng `slug`. Xoá dòng `Route.useParams()`.

Bọc hai chỗ `<AppShell active="/soan-thao">…</AppShell>` bằng `<Vo>`; thêm ngay TRÊN `export function KhongGianSoanThao`:

```tsx
/** Vỏ ngoài: route dùng AppShell; trong khung chat chỉ là một div cao hết khung. */
function Vo({ trongKhung, children }: { trongKhung: boolean; children: ReactNode }) {
  return trongKhung ? (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto">{children}</div>
  ) : (
    <AppShell active="/soan-thao">{children}</AppShell>
  );
}

/** Lưới chọn mẫu khi khung chat mở mà chưa có loại (spec §5.4). */
function LuoiChonMau({ onChon }: { onChon: (slug: string) => void }) {
  return (
    <div className="p-4">
      <h2 className="font-display m-0 text-lg font-semibold text-primary">Chọn loại văn bản</h2>
      {NHOM.map((n) => (
        <section key={n.id} className="mt-4" aria-label={n.ten}>
          <h3 className="m-0 text-[13px] leading-5 text-muted-foreground">{n.ten}</h3>
          <ul className="mt-2 mb-0 grid list-none gap-2 p-0 sm:grid-cols-2">
            {MAU.filter((m) => m.nhom === n.id).map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  onClick={() => onChon(m.id)}
                  className="focus-brass w-full cursor-pointer rounded-lg border border-border bg-card p-3 text-left text-sm hover:bg-[var(--color-paper-100)]"
                >
                  <span className="font-medium text-foreground">{m.ten}</span>
                  <span className="mt-1 block text-[12px] leading-4 text-muted-foreground">{m.moTa}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
```

Trong thân `KhongGianSoanThao`, TRƯỚC nhánh `if (!mau)` hiện có, thêm:

```tsx
  if (slug === null) {
    return (
      <Vo trongKhung={trongKhung}>
        {onDong && <NutDong onDong={onDong} />}
        <LuoiChonMau onChon={setSlug} />
      </Vo>
    );
  }
```

và trong nhánh `if (!mau)`: khi `trongKhung`, thay `<Link to="/soan-thao">…Quay lại danh mục mẫu</Link>` bằng `<button type="button" onClick={() => setSlug(null)} …>Chọn loại khác</button>` (giữ Link cho route). Thêm nút đóng ở đầu khung chính khi `onDong` có:

```tsx
function NutDong({ onDong }: { onDong: () => void }) {
  return (
    <div className="flex justify-end p-2">
      <button type="button" onClick={onDong} aria-label="Đóng khung soạn thảo"
        className="focus-brass cursor-pointer rounded-md border border-border px-3 py-1.5 text-[13px] text-muted-foreground hover:bg-[var(--color-paper-100)]">
        Đóng
      </button>
    </div>
  );
}
```

Đặt `{onDong && <NutDong onDong={onDong} />}` làm con đầu của `<Vo>` ở màn chính. Chuỗi hiển thị mới không chứa cụm bị cấm.

- [ ] **Step 3: Route còn lại** — `frontend/src/routes/soan-thao.$loaiVanBan.tsx` thành:

```tsx
import { createFileRoute } from "@tanstack/react-router";
import { KhongGianSoanThao } from "@/components/soan-thao/KhongGianSoanThao";
import { MAU } from "@/lib/mau-van-ban";
import { SITE_ORIGIN } from "./__root";

export const Route = createFileRoute("/soan-thao/$loaiVanBan")({
  head: ({ params }) => {
    // (giữ NGUYÊN khối head hiện có)
  },
  component: TrangSoanThao,
});

function TrangSoanThao() {
  const { loaiVanBan } = Route.useParams();
  return <KhongGianSoanThao loaiVanBan={loaiVanBan} />;
}
```

(Nếu route hiện có `validateSearch`/`loader`, giữ nguyên chúng trong object `Route`.)

- [ ] **Step 4: Kiểm — hành vi route không đổi**

```bash
npm run typecheck && npm run lint && npm run build 2>&1 | tail -3 && node scripts/kiem-khung.ts | tail -1
```

Expected: cùng kết quả xanh như Step 1. Nếu `npm run dev` đang chạy, mở `/soan-thao/don-xin-nghi-viec` và kiểm biểu mẫu, xem trước, nút tải vẫn hiện.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/soan-thao/KhongGianSoanThao.tsx 'frontend/src/routes/soan-thao.$loaiVanBan.tsx'
git commit -m "refactor(fe): extract KhongGianSoanThao so the drafting screen can mount inside chat

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Card gợi ý `TheGoiYSoanThao` + khung soạn thảo bên phải

**Files:**
- Modify: `frontend/src/components/klaw/TheKetQua.tsx` (import; props; nhánh mới trước `if (loai === "partial_coverage")`)
- Modify: `frontend/src/routes/dung-thu.tsx` (import; state; hai call site `TheKetQua`; khối khung phải; `inert`; aside lịch sử)

**Interfaces:**
- Consumes: `ketQua.soan_thao` (Task 2), `slugCuaLoai`, `mauTheoId` (Task 6), `KhongGianSoanThao` (Task 7).
- Produces: prop `TheKetQua.onSoanThao?: ((slug: string | null) => void) | undefined`; state `soanThao: { slug: string | null } | null` trong `/dung-thu`.

- [ ] **Step 1: `TheKetQua.tsx`**

Import thêm: `import { mauTheoId, slugCuaLoai } from "@/lib/mau-van-ban";`.

Props: thêm vào `interface TheKetQuaProps`:

```tsx
  /** Mở khung soạn thảo bên cạnh với slug thẻ, hoặc `null` để chọn loại tại chỗ. */
  onSoanThao?: ((slug: string | null) => void) | undefined;
```

`NoiDungKetQua` nhận thêm `onSoanThao` từ props (destructure).

Thêm component trước `interface TheKetQuaProps`:

```tsx
/**
 * Card gợi ý soạn thảo (spec soạn-thảo-trong-chat §5.2). Văn xuôi của máy chủ
 * nói loại và lý do; nút chính mở khung bên cạnh với slug của loại đó, chip mở
 * loại thay thế, nút cuối mở lưới chọn tay. `hdld` có hai thẻ → hai nút.
 */
function TheGoiYSoanThao({
  ketQua,
  onSoanThao,
}: {
  ketQua: TraCuuKetQua;
  onSoanThao?: ((slug: string | null) => void) | undefined;
}) {
  const gy = ketQua.soan_thao ?? null;
  const chinh = gy?.ho_tro && gy.loai ? slugCuaLoai(gy.loai) : [];
  const nutPhu = "focus-brass cursor-pointer rounded-full border border-border bg-card px-3 py-1.5 text-[13px] text-foreground hover:bg-[var(--color-paper-100)]";
  return (
    <section aria-label="Gợi ý soạn thảo">
      <div className="doc-prose text-foreground">
        <KhoiVanXuoi chu={ketQua.answer ?? ""} />
      </div>
      {onSoanThao && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {chinh.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onSoanThao(s)}
              className="focus-brass bg-gradient-ink cursor-pointer rounded-lg px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              {chinh.length > 1 ? `Soạn ${mauTheoId(s)?.ten ?? s}` : "Soạn ngay tại đây"}
            </button>
          ))}
          {(gy?.thay_the ?? []).flatMap((t) =>
            slugCuaLoai(t.loai).map((s) => (
              <button key={s} type="button" onClick={() => onSoanThao(s)} className={nutPhu}>
                {mauTheoId(s)?.ten ?? t.ten}
              </button>
            )),
          )}
          <button type="button" onClick={() => onSoanThao(null)} className={cn(nutPhu, "text-muted-foreground")}>
            Chọn loại văn bản
          </button>
        </div>
      )}
    </section>
  );
}
```

Trong `NoiDungKetQua`, TRƯỚC `if (loai === "partial_coverage") {`:

```tsx
  if (loai === "huong_dan_soan_thao") {
    return <TheGoiYSoanThao ketQua={ketQua} onSoanThao={onSoanThao} />;
  }
```

- [ ] **Step 2: `dung-thu.tsx`**

Import: `import { KhongGianSoanThao } from "@/components/soan-thao/KhongGianSoanThao";`.

State (sau `dangMo`):

```tsx
  /** Khung soạn thảo bên phải; loại trừ với khung đối chiếu — một khung một lúc. */
  const [soanThao, datSoanThao] = useState<{ slug: string | null } | null>(null);
  const moSoanThao = (slug: string | null) => {
    datDangMo(null);
    doiChieu.dong();
    datSoanThao({ slug });
  };
```

Trong `chonTrichDan` (nhánh mở), thêm `datSoanThao(null);` trước `doiChieu.mo(...)`.

`khungMo`: đổi `inert={doiChieu.dang !== null && !haiCot}` thành `inert={(doiChieu.dang !== null || soanThao !== null) && !haiCot}`, và className cột hội thoại thành
`cn("flex min-w-0 flex-1 flex-col", soanThao !== null && haiCot && "max-w-[440px]")`.

Hai call site `<TheKetQua … />` (lịch sử và lượt đang chạy): thêm `onSoanThao={moSoanThao}`.

Sau khối `{doiChieu.dang !== null && (…KhungDoiChieu…)}` thêm:

```tsx
        {/* Khung soạn thảo (spec soạn-thảo-trong-chat §5.3). Hai cột: chiếm phần
            còn lại vì màn soạn thảo có hai pane; dưới 68rem: phủ toàn màn như
            KhungDoiChieu. */}
        {soanThao !== null && (
          <div
            className={cn(
              haiCot
                ? "min-w-[640px] flex-1 border-l border-border bg-[var(--color-paper-50)]"
                : "fixed inset-0 z-50 overflow-y-auto bg-background",
            )}
            role={haiCot ? undefined : "dialog"}
            aria-modal={haiCot ? undefined : true}
            aria-label="Soạn thảo văn bản"
          >
            <KhongGianSoanThao loaiVanBan={soanThao.slug} trongKhung onDong={() => datSoanThao(null)} />
          </div>
        )}
```

Aside lịch sử: `{doiChieu.dang === null && (` → `{doiChieu.dang === null && soanThao === null && (`.

- [ ] **Step 3: Kiểm**

```bash
npm run typecheck && npm run lint && npm run kiem-trich-dan && npm run kiem-documents && npm run build 2>&1 | tail -2
cd .. && python -m pytest tests/test_agents/test_giong_tra_loi.py -q
```

Kiểm bằng mắt nếu backend + `npm run dev` chạy: gõ "soạn cho tôi hợp đồng nghỉ việc" (backend cần `ROUTE_PROMPT=prompts/route.v2.md` để có gợi ý; với v1 card vẫn có nút "Chọn loại văn bản") → card → bấm → khung phải mở biểu mẫu → điền → tải .docx.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/klaw/TheKetQua.tsx frontend/src/routes/dung-thu.tsx
git commit -m "feat(fe): drafting suggestion card opens the drafting screen beside the chat

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

# BƯỚC 2 — GỘP, ĐO, BẬT

### Task 9: Gộp hai worktree, đo bẫy `soan_thao`, đổi mặc định, đóng plan

**Files:**
- Modify: `src/config.py`, `tests/test_config.py` (nếu bẫy xanh)
- Modify: `docs/plans/active/soan-thao-trong-chat.md` → `docs/plans/completed/`

- [ ] **Step 1: Gộp**

```bash
git checkout feat/tro-ly-phap-luat
git merge --no-ff wt-be-soan -m "merge: router v2 + drafting suggestion (wt-be-soan)"
git merge --no-ff wt-fe-soan -m "merge: in-chat drafting card and side panel (wt-fe-soan)"
make lint && python -m pytest -q --ignore=tests/test_infra --ignore=tests/test_services/test_effectivity.py
cd frontend && npm run kiem && cd ..
```

- [ ] **Step 2: Đo ba câu bẫy với route v2** (chỉ 3 lượt LLM)

```bash
ROUTE_PROMPT=prompts/route.v2.md python3 - <<'PY'
import asyncio, json, subprocess, yaml
from src.agents.graph_tra_cuu import build_graph_tra_cuu
from eval.run_trap import dung
items = [i for i in yaml.safe_load(open("eval/datasets/trap.yaml"))["items"] if i["nhom"] == "soan_thao"]
g = build_graph_tra_cuu(); ra = []
async def main():
    for it in items:
        st = await g.ainvoke({"query": it["cau_hoi"], "lich_su": []})
        rt = st["result_type"].value if hasattr(st["result_type"], "value") else st["result_type"]
        ra.append({"id": it["id"], "result_type": rt, "soan_thao_goi_y": st.get("soan_thao_goi_y"), "dung": dung(it, st)})
        print(ra[-1])
asyncio.run(main())
h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
json.dump({"commit_hash": h, "route_prompt": "prompts/route.v2.md", "items": ra}, open(f"eval/results/trap_soan_thao_{h}.json", "w"), ensure_ascii=False, indent=2)
PY
```

Ngưỡng bật: `trap-soan-01` và `trap-soan-02` `dung=True`. Đạt → Step 3. Không đạt → giữ v1, ghi kết quả vào plan bền, sửa `prompts/route.v2.md`, đo lại.

- [ ] **Step 3: Đổi mặc định** — `src/config.py`: `route_prompt: str = "prompts/route.v2.md"`; `tests/test_config.py::test_route_prompt_mac_dinh_v1` đổi kỳ vọng và tên thành `test_route_prompt_mac_dinh_v2`. `python -m pytest tests/test_config.py -q`.

- [ ] **Step 4: Kiểm bằng mắt và chụp** — backend mặc định + `npm run dev`; trên `/dung-thu` gõ "soạn cho tôi hợp đồng nghỉ việc": card trong khung viền, gợi ý đúng loại, bấm "Soạn ngay tại đây" → khung phải → điền vài trường → xem trước → tải .docx. Chụp `.tham-dinh-shots/07-card-goi-y-soan-thao.png`, `08-khung-soan-thao-ben-canh.png` nếu công cụ lưu được file.

- [ ] **Step 5: Đóng plan bền** — tick Progress, thêm Decisions (`route_prompt` v2 mặc định hoặc lý do giữ v1), điền `## Result` (kết quả 3 bẫy, file JSON, số mẫu 29), `Status: Completed`, `git mv docs/plans/active/soan-thao-trong-chat.md docs/plans/completed/`.

- [ ] **Step 6: Commit**

```bash
git add src/config.py tests/test_config.py eval/results/trap_soan_thao_*.json docs/plans/ .tham-dinh-shots/07-*.png .tham-dinh-shots/08-*.png
git commit -m "feat(route): make route.v2 the default; close the in-chat drafting plan

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

(Chỉ `git add` các file .png thật sự có.)

---

## Việc tiếp theo (ngoài plan này)

- Mức C: trích dữ kiện từ câu chat (cần xác nhận từng dữ kiện).
- PA2: biểu mẫu nằm trọn trong card, khi component đã tách.
- `quyet_dinh_ky_luat` chưa có thẻ FE — thêm `MAU`/`LOAI_BACKEND` để card mở được.
