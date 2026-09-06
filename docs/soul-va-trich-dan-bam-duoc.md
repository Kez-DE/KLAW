# SOUL của KLAW và trích dẫn bấm được — hướng dẫn tích hợp

> Thẩm quyền thi công là `docs/superpowers/specs/2026-09-06-soul-trich-dan-bam-duoc-design.md`
> (đã chốt ba quyết định mở ở §8, đổi `data/link_cong_luat.yaml` → `data/seed/`,
> bỏ hai trường ngày khỏi `{van_ban}`). Tài liệu này giữ nguyên làm lý luận nền.

Lập 2026-09-06. Đi kèm bốn file mới trong `prompts/`:

| File | Vai | Node dùng |
|---|---|---|
| `soul.v1.md` | Linh hồn dùng chung — bạn là ai, điều gì không bao giờ đổi | tiêm làm `system` cho các node có hành văn hoặc phán đoán (xem §2) |
| `assemble.v2.md` | Giọng luật sư, ba tầng, thẻ `doc`/`cite` bấm được, chào có điều kiện | `assemble` |
| `rewrite_query.v2.md` | "Luật sư nghĩ trước khi mở sách": quan hệ pháp luật → lĩnh vực → truy vấn | `rewrite` |
| `klaw_agent_standalone.v1.md` | Một system prompt trọn gói cho agent tool-calling — test nhanh, prototype | KHÔNG dùng trong pipeline |

Không file nào ghi đè v1. Chuyển bằng cách đổi `PROMPT_PATH` ở node tương ứng;
giữ v1 để chạy A/B trong `eval/configs`.

Nguyên tắc không đổi, và mọi thứ dưới đây phục vụ nó: **mọi khẳng định neo vào một
trích dẫn kiểm chứng được, và phép kiểm là tra bảng, không phải suy luận của mô
hình.** Bảy phép kiểm 0 token vẫn nguyên; bản này THÊM hai phép kiểm 0 token (thẻ và
URL) chứ không bỏ phép nào.

---

## 1. Ý tưởng trong một đoạn

Người dùng muốn câu trả lời đọc như một luật sư đang tư vấn, có đường dẫn đầy đủ tới
văn bản, và bấm vào tên văn bản thì nguyên văn mở ngay bên cạnh. Ba việc đó chia cho
ba nơi, đúng nơi làm được nó một cách kiểm chứng được:

- **Mô hình** lo *giọng* và *chỗ đặt thẻ*: nó viết `[Bộ luật Lao động 2019 (số
  45/2019/QH14)](doc:143506)` và `[Khoản 3 Điều 102](cite:2)`. Nó KHÔNG viết URL,
  KHÔNG viết hiệu lực, KHÔNG viết miễn trừ.
- **Backend** lo *sự thật*: chỉ đưa cho mô hình những văn bản và căn cứ đã qua tầng
  1+2, đánh số chúng, rồi kiểm 0 token rằng mọi thẻ trong câu trả lời trỏ đúng vào
  tập đó. Đường dẫn cổng luật lấy từ `documents`.
- **Giao diện** lo *hành vi bấm*: thẻ `cite` mở `KhungDoiChieu` đã có (tô sáng
  `quote`), thẻ `doc` mở mục lục văn bản, khối "Liên kết tra cứu toàn văn" dựng từ
  `documents[].links`, chân trang miễn trừ là hằng số.

Ví dụ người dùng đưa (Luật Hôn nhân và gia đình kèm ba cổng và hai văn bản hướng
dẫn) sẽ hiện ra ĐÚNG như vậy — với điều kiện các văn bản đó có trong kho. Hiện T1 mới
nạp *luật gốc* của hôn nhân gia đình; Nghị định 126/2014/NĐ-CP và TTLT 01/2016 chưa
có, nên KLAW sẽ **không** nhắc chúng (quy tắc 6 của `assemble.v2`). Muốn câu trả lời
giàu như ví dụ thì mở rộng kho, không nới quy tắc.

---

## 2. Tiêm SOUL

`services/llm.py::chat(model, messages, json_schema)` đã nhận `messages` — chỉ cần
thêm một `system` message. Gợi ý một helper duy nhất:

```python
# src/services/prompts.py
from pathlib import Path

SOUL_PATH = Path("prompts/soul.v1.md")

def soul() -> str:
    return SOUL_PATH.read_text(encoding="utf-8")

def messages(user_prompt: str, *, co_soul: bool = True) -> list[dict]:
    m = [{"role": "system", "content": soul()}] if co_soul else []
    return [*m, {"role": "user", "content": user_prompt}]
```

Rồi ở mỗi node: `llm.chat(model, messages(prompt), json_schema=...)` thay cho
`[{"role": "user", "content": prompt}]`.

**Tiêm ở đâu — và KHÔNG tiêm ở đâu:**

| Node | SOUL? | Lý do |
|---|---|---|
| `assemble`, `hoi_lai`, `giai_nghia`, `draft_generate` | ✅ | có hành văn hướng tới người đọc, hoặc phán đoán về ý người hỏi |
| `generate_claims` | ✅ | phương pháp "ba lớp" và "không bịa" là của SOUL; giữ prompt node như cũ |
| `route`, `rewrite_query` | ⚪ tuỳ | việc cơ học, model flash-lite; `rewrite_query.v2` đã tự mang phần cần thiết. Bỏ SOUL ở đây tiết kiệm ~1.500–2.000 token/lượt |
| `verify_tier2` | ❌ **không** | đây là người thẩm định độc lập. Tiêm cùng một "linh hồn" vào người kiểm và người viết là làm mất tính độc lập mà `judge_model` khác họ với `generate_model` đang cố giữ |

SOUL không chứa ngoặc nhọn, nên nối vào bất kỳ prompt nào rồi `.format()` vẫn an toàn
(đã kiểm bằng `str.format` lúc soạn).

Chi phí: SOUL dài ~1.250 chữ tiếng Việt, ước ~1.500–2.000 token đầu vào mỗi lần tiêm
(tokenizer từng model khác nhau — đo bằng `Usage` của `llm.chat`). Với 4 node có SOUL,
một lượt `tra_cuu` đầy đủ tăng ~6.000–8.000 token đầu vào, tức thêm khoảng 0,1–0,2
cent/lượt ở giá flash. Nếu cần rẻ hơn: tiêm bản đầy đủ chỉ ở `assemble` và
`generate_claims`, còn `hoi_lai`/`giai_nghia` dùng ba đoạn đầu (ba lời hứa + giọng).
Đo lại trong `eval/run.py` và ghi vào `docs/cost-management.md`.

---

## 3. `assemble.v2` — thay đổi trong `assemble.py`

### 3.1 Ba placeholder mới

`assemble.v2.md` dùng `{cau_hoi}`, `{claims}` (như v1) cộng `{mo_dau}` và `{van_ban}`.

```python
# assemble.py, quanh dòng 683 hiện tại

MO_DAU_LUOT_DAU = (
    "Đây là lượt đầu của cuộc trò chuyện: mở bằng một cụm chào ngắn, tự nhiên "
    "(\"Chào bạn,\") nối LIỀN vào câu trả lời thẳng — không thành câu riêng, không "
    "\"rất vui được hỗ trợ\"."
)
MO_DAU_NOI_TIEP = "Đây là lượt nối tiếp: KHÔNG chào, vào thẳng câu trả lời."

def _khoi_van_ban(citations_dung_cho_prose: list[dict], docs: dict[str, dict]) -> str:
    """Mỗi văn bản một dòng, khoá là doc_id — đúng thứ mô hình được phép đặt vào thẻ doc."""
    dong, da = [], set()
    for c in citations_dung_cho_prose:
        d = docs[c["doc_id"]]
        if d["id"] in da:
            continue
        da.add(d["id"])
        dong.append(
            f"[doc:{d['id']}] {d['ten']} — {d['so_ky_hieu']} — ban hành "
            f"{_ngay(d.get('ngay_ban_hanh'))} — hiệu lực từ {_ngay(d.get('ngay_hieu_luc'))}"
        )
    return "\n".join(dong)

claims_txt = "\n".join(
    f"[{k}] {c['duong_dan']} — {c['bo_luat']}\n    {r.claim.text}"
    for k, (r, c) in enumerate(zip(dung_cho_prose, citations_dung_cho_prose, strict=True), start=1)
)
prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
    cau_hoi=state.get("query", ""),
    mo_dau=MO_DAU_NOI_TIEP if state.get("lich_su") else MO_DAU_LUOT_DAU,
    van_ban=_khoi_van_ban(citations_dung_cho_prose, docs),
    claims=claims_txt,
)
```

`docs` cần `ngay_ban_hanh`, `ngay_hieu_luc`, `nguon_url` (và các cột link mới ở §4) —
mở rộng `SELECT` trong `graph_tra_cuu._db_provisions` hoặc truy vấn `documents` riêng
trong `n_assemble` rồi đưa vào state (cùng khuôn `tra_loi_kho`). **Không** đưa
`tinh_trang` của MOJ vào đây — đúng lý do `VanBanMetaMixin` không có nó.

### 3.2 Phép kiểm 0 token cho thẻ và URL — mở rộng lưới cuối

`_dieu_khong_duoc_chong_do` (dòng ~201) hiện chỉ bắt `Điều N` trần. Thêm một hàm
chạy TRƯỚC nó, cùng hậu quả (hạ xuống `abstain`, ghi trace):

```python
_RE_THE = re.compile(r"\[([^\]]+)\]\((doc|cite):([^)\s]+)\)")
_RE_URL = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(vn|com|net|org|gov)\b", re.I)

def _the_khong_hop_le(answer: str, citations_prose: list[dict], doc_ids: set[str]) -> list[str]:
    loi = []
    if _RE_URL.search(answer):
        loi.append("url")
    for chu, loai, khoa in _RE_THE.findall(answer):
        if loai == "doc":
            if khoa not in doc_ids:
                loi.append(f"doc:{khoa}")
        else:
            if not khoa.isdigit() or not (1 <= int(khoa) <= len(citations_prose)):
                loi.append(f"cite:{khoa}")
                continue
            # "Điều N" trong chữ hiển thị phải trùng Điều của chính căn cứ K
            dieu_the = _RE_DIEU.findall(normalize(chu))
            dieu_can_cu = _RE_DIEU.findall(normalize(citations_prose[int(khoa) - 1]["duong_dan"]))
            if dieu_the and dieu_the != dieu_can_cu:
                loi.append(f"cite:{khoa}≠{dieu_can_cu}")
    return loi
```

Sau khi thẻ hợp lệ, `_dieu_khong_duoc_chong_do` chạy như cũ trên `answer` — chữ
hiển thị của thẻ vẫn chứa "Điều N" nên phép kiểm cũ không mất tác dụng, và số Điều
trần ngoài thẻ (nếu mô hình lỡ viết) vẫn bị bắt.

Đường fallback (LLM lỗi → nối `claim.text`) không có thẻ; giao diện vẫn hiện dải
trích dẫn như hiện nay, chỉ thiếu bấm-trong-văn-xuôi. Không cần xử lý thêm.

### 3.3 Response: thêm `k` và `documents`

```python
class CitationOut(BaseModel):
    ...
    # Số thứ tự căn cứ trong văn xuôi (thẻ cite:K). None = trích dẫn nằm trong
    # vết kiểm toán nhưng không được dùng để hành văn (bị phép kiểm thứ bảy lọc).
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
    ngay_ban_hanh: date | None
    ngay_hieu_luc: date | None
    links: LinkVanBanOut

class TraCuuResponse(BaseModel):
    ...
    documents: list[DocumentOut] = []
```

**Bẫy đã sập bốn lần:** khai `documents: list[dict]` vào `KLawState` — LangGraph
loại bỏ khoá không khai (xem chú thích `bang`/`nguon` trong `state.py`).
`test_response_model_biet_moi_gia_tri_cua_ResultType` không bắt được lỗi này; viết
một test graph-thật kiểm `documents` không rỗng khi `result_type == "answer"`.

---

## 4. Đường dẫn cổng luật — từ DB, không từ mô hình

`documents.nguon_url` hiện là **endpoint API** của MOJ
(`vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/{doc_id}`, xem
`scripts/build_seed.py:129`) — không phải trang người đọc mở được. Cần thêm cột
link trang công khai:

```sql
-- migrations/019_link_cong_luat.sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS link_vbpl     TEXT;  -- vbpl.vn/TW/Pages/vbpq-toanvan.aspx?ItemID=...
ALTER TABLE documents ADD COLUMN IF NOT EXISTS link_chinhphu TEXT;  -- vanban.chinhphu.vn/?pageid=27160&docid=...
ALTER TABLE documents ADD COLUMN IF NOT EXISTS link_tvpl     TEXT;  -- thuvienphapluat.vn/van-ban/...
```

Ba quy tắc điền:

1. **Chỉ điền link đã kiểm còn sống** (script `scripts/kiem_link_cong_luat.py`: GET,
   200, tiêu đề trang chứa `so_ky_hieu`). Cột NULL thì giao diện không hiện dòng
   đó. Một link chết dưới nhãn "chính thức" hại uy tín hơn không có link.
2. `link_vbpl`: `ItemID` của vbpl.vn *có thể* trùng `documents.id` (MOJ doc_id) —
   **chưa xác minh trên corpus này**, coi là giả thuyết cần script kiểm, không
   viết `f"...ItemID={doc_id}"` rồi tin.
3. `link_tvpl` là trang tư nhân: điền tay hoặc bán tự động, có kiểm; ưu tiên hiển
   thị vbpl → chinhphu → tvpl, đúng thứ tự ví dụ người dùng đưa.

Mô hình không bao giờ thấy ba cột này. Nó chỉ đặt `doc:ID`; backend điền `links`
vào `documents[]`; giao diện render. Đó là lý do phép kiểm URL ở §3.2 có thể tuyệt
đối: **một URL trong `answer` luôn là lỗi.**

---

## 5. Giao diện

### 5.1 Parser thẻ trong `lib/van-xuoi.ts`

Bất biến hiện tại — "không sửa chữ" — giữ nguyên: parser chỉ CẮT một `doan` thành
các mảnh, không đổi ký tự nào ngoài việc tách cú pháp thẻ ra khỏi chữ hiển thị.

```ts
export type Manh =
  | { kieu: "chu"; chu: string }
  | { kieu: "the"; loai: "cite" | "doc"; khoa: string; chu: string };

const THE = /\[([^\]]+)\]\((doc|cite):([^)\s]+)\)/g;

export function catManh(chu: string): Manh[] {
  const ra: Manh[] = [];
  let cuoi = 0;
  for (const m of chu.matchAll(THE)) {
    if (m.index! > cuoi) ra.push({ kieu: "chu", chu: chu.slice(cuoi, m.index) });
    ra.push({ kieu: "the", loai: m[2] as "cite" | "doc", khoa: m[3]!, chu: m[1]! });
    cuoi = m.index! + m[0].length;
  }
  if (cuoi < chu.length) ra.push({ kieu: "chu", chu: chu.slice(cuoi) });
  return ra;
}
```

`Doan` giữ nguyên hình dạng; nơi render gọi `catManh(doan.chu)` (và cho từng mục
của `danh_sach`). Cập nhật `scripts/kiem-van-xuoi.ts`: thêm ca "thẻ giữa câu",
"hai thẻ liền", "thẻ trong mục danh sách", "ngoặc vuông không phải thẻ" (ví dụ
"[sic]") — ca cuối phải ra `chu`, không ra `the`.

### 5.2 Hành vi bấm — trong `TheKetQua.tsx`

```tsx
function TheTrichDan({ manh, ketQua, onChonTrichDan, onMoVanBan }: ...) {
  if (manh.loai === "cite") {
    const c = ketQua.citations.find((x) => x.k === Number(manh.khoa));
    if (!c) return <>{manh.chu}</>;           // thẻ lạ đã bị backend chặn; đây là lưới phụ
    return (
      <button type="button" className="the-luat" onClick={() => onChonTrichDan(c)}>
        {manh.chu}
      </button>
    );
  }
  const d = ketQua.documents.find((x) => x.doc_id === manh.khoa);
  if (!d || !onMoVanBan) return <>{manh.chu}</>;
  return (
    <button type="button" className="the-luat" onClick={() => onMoVanBan(d.doc_id)}>
      {manh.chu}
    </button>
  );
}
```

- `onChonTrichDan(c)` → `useDoiChieu.mo({ docId: c.doc_id, khopTaiId: c.khop_tai_id,
  duongDan: c.duong_dan, quote: c.quote })` — đúng `KhungDoiChieu` hiện có, mở
  bằng `khop_tai_id`, tô sáng `quote`. Không viết panel thứ hai.
- `onMoVanBan(doc_id)` → mục lục `GET /van-ban/{doc_id}` — đường đã có cho `nguon[]`
  của `partial_coverage`; nay dùng chung cho thẻ `doc`.
- Hai cột bật theo `useHaiCot()` (≥ 68rem); dưới đó dùng đúng fallback một cột
  hiện tại. "Hiển thị luôn văn bản sang ngay bên cạnh" là hành vi hai cột; trên
  điện thoại nó là tấm trượt lên — đừng ép hai cột trên màn hình 360px.
- Kiểu chữ: gạch chân, màu link của hệ (navy đậm trên nền sáng, vàng đồng trên
  nền tối theo `DESIGN.md`), `cursor: pointer`, focus-visible rõ, là `<button>`
  để bàn phím dùng được. Không dùng `<a href="#">`.

### 5.3 Khối "Liên kết tra cứu toàn văn"

Render dưới văn xuôi, trên dải trích dẫn, từ `documents[]`:

```
📖 Liên kết tra cứu toàn văn:
1. 🔗 Toàn văn Bộ luật Lao động 2019 — Cơ sở dữ liệu quốc gia về văn bản pháp luật (Bộ Tư pháp)
2. 🔗 Toàn văn Bộ luật Lao động 2019 — Cổng Thông tin điện tử Chính phủ
3. 🔗 Toàn văn và văn bản hướng dẫn — Thư Viện Pháp Luật
```

Mỗi dòng là `<a target="_blank" rel="noopener noreferrer">`; dòng nào `links.x` NULL
thì không render. Nhiều văn bản thì nhóm theo văn bản. Tên hiển thị = `documents.ten`
(cột `ten` không nhất quán hoa/thường — chuẩn hoá ở giao diện bằng
`hien_van_ban`-tương-đương, không sửa DB).

Biểu tượng cảm xúc (📖 🔗 ⚖️) là của giao diện, không của mô hình — `assemble.v2`
quy tắc 17 cấm mô hình dùng chúng, để hai bên không chồng nhau.

### 5.4 Chân trang miễn trừ — hằng số

```ts
export const MIEN_TRU = "⚖️ Thông tin chỉ mang tính tham khảo, không thay thế tư vấn của luật sư.";
```

Hiện dưới mọi kết quả `answer` và `partial_coverage`. Không nằm trong `answer` của
mô hình (quy tắc 2 của `assemble.v2`), nên không tốn token và không bao giờ lệch chữ.
Trang `/mien-tru` đã có — link chân trang tới đó.

---

## 6. `rewrite_query.v2` — dùng phần "nghĩ trước" vào truy hồi

Node hiện parse `queries`; v2 trả thêm `linh_vuc`, `du_kien_van_ban`, `quan_he`,
`vai`, `ba_lop`. Hai cách dùng, đều rẻ:

1. `linh_vuc` → lọc mềm `documents.linh_vuc` (cột đã có, migration 018) trong
   `Retriever.hybrid`: cộng điểm cho văn bản cùng lĩnh vực, **không** loại văn bản
   khác lĩnh vực — mô hình đoán sai lĩnh vực thì truy hồi vẫn cứu được.
2. `quan_he`/`vai` → đưa vào `traces` để đọc lại khi eval fail; sau này có thể vào
   `hoi_lai` để hỏi đúng chiều còn thiếu.

Nếu `llm.chat` chạy `json_schema` strict, mở rộng schema cho các khoá mới hoặc chỉ
nhận `queries` và bỏ phần còn lại — đừng để schema cũ làm v2 fail im lặng rồi rơi
về fallback `[query]` mà không ai biết (đếm qua traces như `rewrite_query.py` đang
làm).

---

## 7. Đánh giá — thêm vào golden QA và bẫy

| Phép kiểm | Kỳ vọng | Nơi |
|---|---|---|
| `answer` không chứa URL/tên miền | 0/N | `eval/metrics.py`, regex §3.2 |
| Mọi `cite:K` hợp lệ, "Điều N" trong thẻ trùng `duong_dan[K]` | 100% | như trên |
| Mọi `doc:ID` có trong `documents[]` | 100% | như trên |
| Tỉ lệ câu `answer` có ≥1 thẻ `doc` ở tầng 1 | ≥ 90% | đo giọng |
| "Chào" chỉ xuất hiện khi `lich_su` rỗng | 100% | bẫy lượt nối tiếp |
| `answer` không chứa "tham khảo", "luật sư" (miễn trừ) | 0/N | bẫy giọng |
| Câu hỏi ví dụ HN&GĐ: không nhắc NĐ 126/2014, TTLT 01/2016 khi chúng chưa trong kho | 0 nhắc | bẫy "văn bản ngoài kho" |
| Token đầu vào/lượt trước–sau SOUL | ghi số | `cost-management.md` |

`bo-luat-agent.md` dòng 7–9 (dự đoán kết quả, đường lách, tiêm lệnh) nay có nơi
cưỡng chế bằng prompt ở SOUL + `assemble.v2` quy tắc 13–14, 18 — chuyển ⬜ → ✅
sau khi có ca bẫy đo được, không trước.

---

## 8. Quyết định còn mở — cần chủ dự án chốt

1. **Xưng hô.** `gioi_thieu.py` dùng "mình"; `assemble` và SOUL dùng "tôi". Hai
   giọng trong một sản phẩm là thứ người đọc cảm thấy "máy" mà không gọi tên được.
   Đề xuất: "tôi" cho mọi câu trả lời pháp lý (đúng vai luật sư), giữ "mình" chỉ
   cho chào hỏi/cảm ơn nếu muốn ấm hơn — hoặc thống nhất "tôi" toàn bộ.
2. **Có nêu ngày hiệu lực trong văn xuôi không.** `assemble.v2` quy tắc 12 cho phép
   chép đúng ngày từ khối VĂN BẢN ĐÃ DÙNG. Đây là ngày hiệu lực CỦA VĂN BẢN GỐC,
   không phải của điều khoản sau sửa đổi — với văn bản `bi_sua_doi`, câu "có hiệu lực
   từ 01/01/2021" đứng cạnh nhãn "bị sửa bởi 113/2025/QH15 từ 01/7/2026" có thể gây
   hiểu nhầm. Phương án an toàn hơn: bỏ hẳn ngày trong văn xuôi, để nhãn hiệu lực
   nói. Nếu chọn phương án này, xoá đoạn "trừ khi…" ở quy tắc 12 và bỏ hai trường
   ngày khỏi `{van_ban}`.
3. **Mở kho HN&GĐ đủ sâu** (nghị định, thông tư liên tịch) nếu ví dụ đó là ca demo
   trọng tâm. Đây là việc corpus, không phải việc prompt.

---

## 9. Thứ tự làm

1. `services/prompts.py` + tiêm SOUL vào 4 node (§2) — chạy lại golden QA, ghi token.
2. Migration 019 + script kiểm link (§4) — điền `link_vbpl` cho 21 văn bản tầng sâu
   trước.
3. `assemble.py`: placeholder, đánh số, phép kiểm thẻ/URL, `k` + `documents` (§3) —
   đổi `PROMPT_PATH` sang v2 — test graph-thật.
4. FE: parser, nút thẻ, khối liên kết, chân trang (§5) — cập nhật
   `kiem-van-xuoi.ts`, chụp `.tham-dinh-shots`.
5. `rewrite_query.v2` (§6) — A/B trên `eval/configs` trước khi bật mặc định.
