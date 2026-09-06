# SOUL và trích dẫn bấm được — thiết kế thi công

Ngày: 2026-09-06 · Trạng thái: đã duyệt qua brainstorming, chờ kế hoạch thi công
Tiếp nối: `docs/soul-va-trich-dan-bam-duoc.md` (hướng dẫn tích hợp, cùng ngày),
`docs/superpowers/specs/2026-09-02-tro-ly-phap-luat-design.md`,
`docs/plans/active/tro-ly-8-linh-vuc.md`.

Đây là **sub-project 1 của 4**. Ba sub-project còn lại (gộp `/chat` vào
`/dung-thu` và đánh bóng UX; lưu hội thoại theo tài khoản; mở kho HN&GĐ) có spec
riêng, làm sau, tận dụng hợp đồng dữ liệu lập ở đây. Xem §11.

## 1. Bất biến và mục tiêu

Bất biến không đổi: **mọi khẳng định neo vào một trích dẫn kiểm chứng được, và
phép kiểm là tra bảng, không phải suy luận của mô hình.** Bảy phép kiểm 0 token
hiện có giữ nguyên; bản này THÊM hai phép kiểm 0 token (thẻ và URL).

Sau khi xong, quan sát được trên `/dung-thu`:

1. Câu trả lời đọc như luật sư tư vấn: mở đầu thẳng, ba tầng, xưng "tôi", gọi
   "bạn". Lượt đầu có cụm chào ngắn nối liền câu trả lời; lượt nối tiếp không chào.
2. Tên văn bản và số Điều trong văn xuôi là **nút bấm**. Bấm số Điều mở nguyên văn
   trong `KhungDoiChieu` bên cạnh, tô sáng câu trích. Bấm tên văn bản mở cùng
   khung tại điều khoản đầu tiên của văn bản đó được dẫn trong lượt.
3. Dưới văn xuôi có khối "Liên kết tra cứu toàn văn" dựng từ DB, mỗi dòng mở tab
   mới tới cổng luật. Văn bản chưa có link thì không có dòng.
4. Không một URL, không một câu hiệu lực, không một lời miễn trừ nào do mô hình
   viết. Chân trang ⚖️ là hằng số của giao diện, hiện ở `answer` và
   `partial_coverage`.
5. Một thẻ trỏ sai (doc lạ, cite ngoài tập, Điều trong thẻ khác Điều của căn cứ)
   hoặc một URL trong `answer` hạ cả lượt xuống `abstain`, ghi vào `traces`.

## 2. Quyết định đã chốt (chủ dự án, 2026-09-06)

| # | Quyết định | Hệ quả |
|---|---|---|
| Q1 | Xưng "tôi" toàn bộ, kể cả chào hỏi | Đổi 26 chỗ "mình" trong `src/agents/nodes/gioi_thieu.py`. Test `test_gioi_thieu.py` không canh chữ này. |
| Q2 | Bỏ hẳn ngày hiệu lực khỏi văn xuôi | Xoá đoạn "trừ khi…" ở quy tắc 12 của `assemble.v2.md`. Khối `{van_ban}` và `DocumentOut` **không** mang `ngay_ban_hanh`, `ngay_hieu_luc`. Nhãn hiệu lực cạnh trích dẫn là nơi duy nhất nói về hiệu lực. |
| Q3 | Kiểm link bằng trình duyệt thật + file seed | Không có script GET. `vbpl.vn` trả 403 cho bot (đã xác minh trong plan 8 lĩnh vực). Xem §4. |
| Q4 | Thi công "hợp đồng trước, song song" | Khoá schema additive ở bước 0, rồi BE / FE / DB chạy trong ba git worktree. Xem §9. |
| Q5 | Thẻ `doc` mở trong panel bên cạnh, không tab mới | Dùng `KhungDoiChieu` hiện có tại điều khoản đầu tiên của văn bản đó trong `citations`. Không viết panel thứ hai, không thêm chế độ mục lục. |

## 3. Hợp đồng dữ liệu

### 3.1 Cú pháp thẻ trong `answer`

Chỉ ở `result_type == "answer"`:

```
[chữ hiển thị](doc:<documents.id>)
[chữ hiển thị](cite:<K>)        K đếm từ 1, theo thứ tự căn cứ đưa cho mô hình
```

Regex dùng chung hai phía: `\[([^\]]+)\]\((doc|cite):([^)\s]+)\)`.
`[sic]` hay ngoặc vuông không theo cú pháp trên là chữ thường.

### 3.2 Schema — toàn bộ additive

`src/models/schemas.py`:

```python
class CitationOut(BaseModel):
    ...
    # Số thứ tự căn cứ trong văn xuôi (thẻ cite:K). None = nằm trong vết kiểm
    # toán nhưng không được dùng để hành văn (bị phép kiểm thứ bảy lọc).
    k: int | None = None

class LinkVanBanOut(BaseModel):
    vbpl: str | None = None
    chinhphu: str | None = None
    tvpl: str | None = None

class DocumentOut(BaseModel):
    doc_id: str
    ten: str
    so_ky_hieu: str
    loai_van_ban: str
    links: LinkVanBanOut

class TraCuuResponse(BaseModel):
    ...
    documents: list[DocumentOut] = []
```

Mọi trường mới có mặc định, nên dòng `answer_cache` ghi trước bản này và FE cũ
đều đọc được. Ba chỗ phải đi cùng nhau, cùng khuôn `bang` (T4):

- `KLawState.documents: list[dict]` — **bắt buộc khai**, LangGraph loại khoá
  không khai khỏi state trả về (bẫy đã sập bốn lần, xem chú thích `bang`/`nguon`
  trong `state.py`).
- `routes._payload_cache`: thêm `"documents": st.get("documents") or []`.
- `routes.tra_cuu_response`: `documents=payload.get("documents") or []`.

`frontend/src/lib/klaw.ts`: `Citation.k?: number | null`, `VanBanTraLoi`
(khớp `DocumentOut`), `TraCuuKetQua.documents: VanBanTraLoi[]`. Bộ kiểm kiểu
`laTraCuuKetQua` chấp nhận thiếu `documents` (coi như `[]`) để không vỡ với
payload cache cũ.

### 3.3 `_db_provisions`

`src/agents/graph_tra_cuu.py:65` mở rộng SELECT:
`id, so_ky_hieu, ten, loai_van_ban, link_vbpl, link_chinhphu, link_tvpl`.
Không lấy `tinh_trang` của MOJ — đúng lý do `VanBanMetaMixin` không có nó.

## 4. DB và link cổng luật

### 4.1 Migration

```sql
-- migrations/019_link_cong_luat.sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS link_vbpl     TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS link_chinhphu TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS link_tvpl     TEXT;
```

NULL nghĩa là "chưa có link đã kiểm". Giao diện không render dòng NULL.

### 4.2 Seed và loader

`data/link_cong_luat.yaml` (giá trị minh hoạ, không phải dữ liệu thật):

```yaml
"139264":                         # Bộ luật Lao động 45/2019/QH14
  vbpl: https://vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=139264
  chinhphu: https://vanban.chinhphu.vn/?pageid=27160&docid=000000
  tvpl: null
  kiem_luc: 2026-09-06            # YYYY-MM-DD
  kiem_boi: chu-du-an
```

`scripts/nap_link_cong_luat.py` theo khuôn `scripts/nap_linh_vuc.py`: đọc YAML,
UPDATE thuần, idempotent. Ba phép kiểm trước khi ghi, sai là dừng chứ không bỏ
qua im lặng:

1. `doc_id` phải tồn tại trong `documents`.
2. URL phải là `https://` và host thuộc allowlist đúng ba giá trị
   `vbpl.vn`, `vanban.chinhphu.vn`, `thuvienphapluat.vn`. Cột không thuộc
   allowlist là lỗi cấu hình, không phải dữ liệu.
3. `kiem_luc` là ngày hợp lệ, không ở tương lai.

### 4.3 Cách kiểm

Mở từng link bằng Chrome (MCP `claude-in-chrome`) cho 21 văn bản `deep` trong
`scripts/fetch_moj.py::DOC_IDS`, xác nhận trang mở được và tiêu đề chứa
`so_ky_hieu`. Giả thuyết `vbpl ItemID = documents.id` chỉ được suy rộng sau khi
đúng trên ít nhất 3 văn bản; sai thì điền tay từng dòng. Thứ tự ưu tiên hiển thị
vbpl → chinhphu → tvpl. `tvpl` là trang tư nhân, chỉ điền khi có người kiểm.

## 5. Backend

### 5.1 SOUL — `src/services/prompts.py`

```python
from functools import lru_cache
from pathlib import Path

SOUL_PATH = Path("prompts/soul.v1.md")

@lru_cache(maxsize=1)
def soul() -> str:
    return SOUL_PATH.read_text(encoding="utf-8")

def messages(user_prompt: str, *, co_soul: bool = True) -> list[dict]:
    he = [{"role": "system", "content": soul()}] if co_soul else []
    return [*he, {"role": "user", "content": user_prompt}]
```

| Node | SOUL | Ghi chú |
|---|---|---|
| `assemble`, `hoi_lai`, `giai_nghia`, `draft_generate`, `generate_claims` | ✅ | thay `[{"role": "user", ...}]` bằng `messages(prompt)` |
| `route`, `rewrite_query` | ❌ | việc cơ học, tiết kiệm ~1.500–2.000 token/lượt |
| `verify_tier2` | ❌ | thẩm định độc lập, không được cùng "linh hồn" với người viết |

`FakeLlm` trong test đã nhận `messages` nên không đổi chữ ký test. Thêm test
canh `messages()[0]["role"] == "system"` và `co_soul=False` không có system.

### 5.2 Chọn prompt bằng Settings

`src/config.py` thêm `assemble_prompt: str = "prompts/assemble.v1.md"` và
`rewrite_prompt: str = "prompts/rewrite_query.v1.md"`. Hai node đọc đường dẫn
từ Settings thay cho hằng `PROMPT_PATH`. Preset `eval/configs/soul_v2.yaml` ghi
đè sang v2 — `eval.run.overlay_settings` đã có nên A/B không cần code mới. Đổi
mặc định sang v2 ở bước 2 của §9, sau khi eval xanh.

### 5.3 `assemble` với v2

Sửa `prompts/assemble.v2.md` quy tắc 12: xoá đoạn "trừ khi…" (Q2).

Trong `assemble()` từ dòng ~683:

- `MO_DAU_LUOT_DAU` / `MO_DAU_NOI_TIEP` chọn theo `state.get("lich_su")`.
- Gán `k` (từ 1) cho `citations_dung_cho_prose` theo thứ tự; `citations` khác
  giữ `k=None`.
- `claims_txt`: `[k] duong_dan — bo_luat\n    claim.text`.
- `_khoi_van_ban(citations_dung_cho_prose, db_provisions)` → mỗi văn bản một
  dòng `[doc:ID] ten — so_ky_hieu — loai_van_ban`, khử trùng theo `doc_id`.
  **Không có ngày** (Q2).
- `prompt = ...format(cau_hoi, mo_dau, van_ban, claims)`; gọi
  `llm.chat(model, messages(prompt), json_schema=ANSWER_SCHEMA)`.
- `documents = _dung_documents(citations_dung_cho_prose, db_provisions)` → list
  dict khớp `DocumentOut`, `links` lấy từ ba cột link, đi qua `_base(**kw)`.

### 5.4 Phép kiểm thứ tám và thứ chín — thẻ và URL

Chạy **trước** `_dieu_khong_duoc_chong_do`, trên cả đường LLM và đường fallback:

```python
_RE_THE = re.compile(r"\[([^\]]+)\]\((doc|cite):([^)\s]+)\)")
_RE_URL = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(vn|com|net|org|gov)\b", re.I)

def _the_khong_hop_le(answer, citations_prose, doc_ids) -> list[str]:
    # "url" nếu có URL; "doc:X" nếu X không trong doc_ids; "cite:K" nếu K không
    # phải số trong [1, len]; "cite:K≠[Điều]" nếu Điều trong chữ hiển thị khác
    # Điều của duong_dan[K-1]. Trả về rỗng = hợp lệ.
```

Lỗi → `_ngo_cut(..., ResultType.abstain)`, `traces["assemble_the_loi"] = loi`.
`_dieu_khong_duoc_chong_do` vẫn chạy sau đó trên `answer` nguyên văn: chữ hiển
thị của thẻ vẫn chứa "Điều N" nên phép kiểm cũ không mất tác dụng.

Đường fallback (LLM lỗi → nối `claim.text`) không có thẻ, `k` vẫn được gán,
`documents` vẫn dựng; giao diện hiện dải trích dẫn và khối liên kết như thường.

### 5.5 `rewrite_query` với v2

`QUERIES_SCHEMA` mở rộng, mọi khoá mới optional:
`quan_he: str`, `vai: str`, `linh_vuc: str`, `ba_lop: list[str]`,
`du_kien_van_ban: list[str]`. Node vẫn chỉ dùng `queries` để truy hồi; ghi
`linh_vuc_du_doan` vào state (khai trong `KLawState`) và `quan_he`/`vai` vào
`traces["rewrite_query_nhan_dien"]`. Đường fallback và đếm `degraded` giữ nguyên.
Với `rewrite_prompt` = v1, các khoá mới vắng mặt và node hành xử y như hôm nay.

## 6. Cộng điểm mềm theo lĩnh vực

Đặt **sau RRF**, trong `n_retrieve` của `graph_tra_cuu.py`, không sửa
`Retriever.hybrid`:

1. Lấy `provision_ids` như hiện tại (đã xếp hạng).
2. Nếu `state.linh_vuc_du_doan` có và `settings.linh_vuc_bonus > 0`: một truy
   vấn `provisions → documents.linh_vuc` cho các ứng viên. `provision_ids` chỉ
   trả thứ tự, không trả điểm, nên điểm được dựng lại từ vị trí:
   `diem = 1 / (hang + 1)` với `hang` đếm từ 0, cộng `bonus` cho provision cùng
   lĩnh vực, rồi sắp giảm dần **ổn định** (bằng điểm thì giữ thứ tự cũ).
3. Không loại provision khác lĩnh vực — mô hình đoán sai lĩnh vực thì truy hồi
   vẫn cứu được.

`linh_vuc_bonus` mặc định `0.0` (tắt). Preset `eval/configs/hybrid_linh_vuc.yaml`
bật để đo trên golden 77 câu. Chỉ đổi mặc định khi Recall@10 không tụt.

## 7. Giao diện

### 7.1 Parser — `frontend/src/lib/van-xuoi.ts`

```ts
export type Manh =
  | { kieu: "chu"; chu: string }
  | { kieu: "the"; loai: "cite" | "doc"; khoa: string; chu: string };
export function catManh(chu: string): Manh[]
```

Thuần, không sửa chữ ngoài việc tách cú pháp thẻ. `catDoan` giữ nguyên.
`scripts/kiem-van-xuoi.ts` thêm năm ca: thẻ giữa câu, hai thẻ liền, thẻ trong
mục danh sách, `[sic]` ra `chu`, thẻ lỗi cú pháp (`(cite:)`, `(doc:a b)`) ra `chu`.

### 7.2 Hành vi bấm — `TheKetQua.tsx`

- `KhoiVanXuoi` nhận thêm `ketQua?` và `onChonTrichDan?`. Mỗi đoạn và mỗi mục
  render `catManh(...)`; mảnh `the` → `<TheTrichDan>`.
- `cite:K`: tìm `chiSo = citations.findIndex(c => c.k === K)`; không có → chữ
  thường. Có → `<button type="button" class="the-luat">` gọi
  `onChonTrichDan(chiSo)`. Nhờ vậy logic `dangMo`, `aria-expanded` và tô sáng
  chip trong `dung-thu.tsx` dùng lại nguyên, không có trạng thái mới.
- `doc:ID` (Q5): tìm `chiSo` của trích dẫn **đầu tiên** có `doc_id === ID` và
  `k` nhỏ nhất trong `citations`; không có → chữ thường. Có → cùng nút, cùng
  `onChonTrichDan(chiSo)`. Nói cách khác thẻ `doc` là một lối tắt tới điều khoản
  đầu tiên của văn bản đó; `KhungDoiChieu` đã hiện tên văn bản và nhãn hiệu lực
  ở đầu khung.
- Kiểu `.the-luat` trong `styles.css`: gạch chân, màu link theo `DESIGN.md`
  (navy đậm nền sáng, vàng đồng nền tối), `cursor: pointer`, `focus-visible` rõ,
  không `<a href="#">`.

### 7.3 Khối liên kết và chân trang

- `KhoiLienKet({ documents })` render dưới văn xuôi, trên `DaiTrichDan`, chỉ khi
  có ít nhất một link non-null. Mỗi dòng
  `<a target="_blank" rel="noopener noreferrer">`, nhóm theo văn bản, thứ tự
  vbpl → chinhphu → tvpl. Nhãn: "Cơ sở dữ liệu quốc gia về văn bản pháp luật
  (Bộ Tư pháp)", "Cổng Thông tin điện tử Chính phủ", "Thư Viện Pháp Luật".
  Biểu tượng 📖 🔗 là của giao diện; `assemble.v2` quy tắc 17 cấm mô hình dùng.
- `NhacMienTru` đã chứa dòng "⚖️ Thông tin chỉ mang tính tham khảo…" và link
  `/mien-tru`; render thêm ở nhánh `partial_coverage`. Không tách hằng số mới.

### 7.4 Bố cục

Hai cột theo `useHaiCot()` (≥ 68rem) như hiện tại; dưới ngưỡng là khung phủ
màn hình. Không ép hai cột trên màn hình nhỏ.

## 8. Đánh giá và test

### 8.1 Test đơn vị (pytest)

- `tests/test_services/test_prompts.py`: `messages()` có/không system.
- `tests/test_agents/test_assemble.py`: `_the_khong_hop_le` năm ca (hợp lệ; doc
  lạ; cite ngoài tập; Điều lệch; có URL) → ca lỗi ra `abstain` và
  `traces["assemble_the_loi"]`; `k` gán đúng thứ tự và `None` cho căn cứ bị lọc;
  `documents` khử trùng và có `links`.
- `tests/test_agents/test_rewrite_query.py` (**file mới**, node này chưa có
  test riêng): schema v2 parse, khoá mới vắng mặt không lỗi, fallback vẫn đếm
  `degraded`.
- `tests/test_agents/test_gioi_thieu.py`: không còn "mình"/"Mình" trong mọi
  hằng số hiển thị.
- Test graph-thật (khuôn `tests/test_api/test_tra_cuu.py`): `documents` không
  rỗng và mọi `k` hợp lệ khi `result_type == "answer"`.

### 8.2 Kiểm FE (`npm run kiem`)

Năm ca `catManh` trong `kiem-van-xuoi.ts`; `kiem-khung` cập nhật nếu đếm props.

### 8.3 Bẫy (`eval/datasets/trap.yaml`, `eval/run_trap.py`)

| `ky_vong` | Kỳ vọng |
|---|---|
| `khong_url` | `answer` không khớp `_RE_URL` |
| `the_hop_le` | mọi `cite:K` trong [1, n], `doc:ID` trong `documents[]` |
| `chao_dung_luot` | có "Chào" chỉ khi `lich_su` rỗng |
| `khong_mien_tru` | `answer` không chứa "tham khảo", "luật sư" |
| `van_ban_ngoai_kho` | câu HN&GĐ không nhắc NĐ 126/2014, TTLT 01/2016 |

`run_trap.dung()` mở rộng cho năm loại trên. Chạy trap **trước** (v1) và **sau**
(v2), ghi cả hai vào `eval/results/`.

### 8.4 Chi phí

Golden 77 câu với `soul_v2.yaml` so với `hybrid.yaml`: ghi token đầu vào/lượt
trước–sau vào `docs/cost-management.md`. Kỳ vọng tăng ~6.000–8.000 token đầu vào
cho một lượt `tra_cuu` đủ 5 node có SOUL.

## 9. Thi công (Q4)

Lập một plan `docs/plans/active/soul-trich-dan-bam-duoc.md` theo
`docs/templates/exec-plan.md` vì việc trải nhiều phiên và phối hợp nhiều agent.
Ba bước:

**Bước 0 — đường nối, một người, nhánh hiện tại.** Commit bốn prompt và tài
liệu soul. Hợp đồng §3 hai phía (pydantic, `KLawState`, `_payload_cache`,
`tra_cuu_response`, `klaw.ts`), migration 019, hai khoá Settings §5.2. Sửa quy
tắc 12 của `assemble.v2.md`. `make check` và `npm run kiem` xanh. Không đổi hành
vi nào người dùng thấy.

**Bước 1 — ba worktree song song** (quyết định 2026-09-02 trong plan 8 lĩnh
vực: không hai implementer trên cùng branch; worktree là cách song song hợp lệ):

| Worktree | Việc | Agent và soát |
|---|---|---|
| `wt-be-soul` | §5.1, §5.3, §5.4, §5.5, §6, Q1, test §8.1 | `ecc:tdd-guide` viết test trước; `ecc:python-reviewer` + `ecc:silent-failure-hunter` trên đường `assemble` |
| `wt-fe-the` | §7, test §8.2 | agent frontend; `ecc:react-reviewer`; `ecc:a11y-architect` cho `.the-luat` và `<a target=_blank>` |
| `wt-db-link` | §4.2 loader, §4.3 kiểm link 21 văn bản bằng Chrome, seed YAML | người điều phối; `ecc:database-reviewer` soát migration + loader; `ecc:security-reviewer` soát allowlist |

Mỗi agent nhận conventions của repo trong prompt (tiếng Việt cho tên/chú thích,
tiếng Anh cho commit, `make check`, không sửa file ngoài phạm vi worktree).

**Bước 2 — gộp và bật.** Rebase lần lượt BE → FE → DB lên nhánh hiện tại.
`make check`, `npm run kiem`, test graph-thật. Chạy `scripts/nap_link_cong_luat.py`.
Chạy golden 77 + trap với v1 và `soul_v2.yaml`; ghi delta. Nếu không tụt: đổi
mặc định `assemble_prompt`/`rewrite_prompt` sang v2. Chụp `.tham-dinh-shots`.
Chuyển ⬜ → ✅ dòng 7–9 của `docs/bo-luat-agent.md` **chỉ sau khi** bẫy tương
ứng đo được. Chuyển plan sang `docs/plans/completed/`.

## 10. Rủi ro và cách lùi

| Rủi ro | Dấu hiệu | Cách lùi |
|---|---|---|
| Mô hình không theo cú pháp thẻ | tỉ lệ `abstain` do `assemble_the_loi` tăng trong traces | giữ mặc định v1; sửa prompt v2; phép kiểm không nới |
| Token tăng quá dự kiến | `cost-management.md` ghi > +10.000/lượt | chỉ tiêm SOUL ở `assemble` + `generate_claims` |
| `documents` biến mất khỏi response | test graph-thật đỏ | kiểm `KLawState` đã khai khoá |
| Link vbpl không mở được bằng bot | 403 khi kiểm | Q3: kiểm bằng Chrome, NULL nếu không xác minh |
| `linh_vuc_du_doan` sai làm tụt recall | eval `hybrid_linh_vuc` < `hybrid` | `linh_vuc_bonus = 0`, giữ tắt |
| Cache cũ thiếu `documents`/`k` | 500 khi cache hit | `.get(...) or []` và mặc định pydantic đã chặn; test cache hit cũ |

## 11. Ngoài phạm vi sub-project này

- **Gộp `/chat` vào `/dung-thu`, đánh bóng UX** — sub-project 2, spec riêng.
- **Lưu hội thoại theo tài khoản** — sub-project 3. Phải đi cùng thời hạn lưu và
  quyền xoá tương đương `scripts/an_danh_traces.py`, và cập nhật trang `/du-lieu`.
- **Mở kho HN&GĐ** (NĐ 126/2014, TTLT 01/2016) — sub-project 4, pipeline MOJ đã có.
- Stream chữ của câu trả lời cuối: **không làm**. Phép kiểm 0 token phải chạy
  trên toàn bộ `answer` trước khi hiện; stream rồi rút lại phá bất biến §1.
- `klaw_agent_standalone.v1.md`: chỉ để test nhanh, không nối vào pipeline.
