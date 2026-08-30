# Eval Report — Retrieval Ablation (Plan 2, Task 9)

> **CẢNH BÁO:** `golden_qa.yaml` (77 câu) toàn bộ đang `da_review: false` — chưa ai, kể cả chủ dự án, duyệt tay từng câu (Task 8). Mọi con số dưới đây là **CHỈ BÁO cho hướng phát triển**, KHÔNG phải kết quả công bố được trong khóa luận cho tới khi review xong.

## 1. Bảng ablation (77 câu golden_qa)

`lexical_only` là **truy hồi từ vựng bằng `tsvector` + `ts_rank` của PostgreSQL** (config `simple` + `unaccent`, truy vấn OR, chuẩn hoá độ dài `normalization=1`, lọc hư từ có) — **không phải BM25**: `ts_rank` không có tham số `k1`/`b` và không dùng IDF. Hai tham số trên chọn theo đo, không theo mặc định của Postgres; bảng sweep đầy đủ và lý do ở `docs/bm25-tuning.md` (tái lập: `python -m scripts.sweep_bm25`).

> **Sai số tái lập:** nhánh dense KHÔNG tất định tuyệt đối. Vector truy vấn do OpenRouter trả về đôi khi lệch tới ~2,7e-4 mỗi chiều giữa hai lần gọi CÙNG một câu (đo được: 1/4 lần gọi lệch), đủ để đảo thứ tự vài láng giềng sát nhau. Chạy `dense_only` ba lần cho Recall@10 0,7727 / 0,7792 / 0,7727: giữa hai lần đầu, 5/77 câu đổi thứ tự ở **hạng 7–10** và 1 câu đổi metric → biên độ Recall@10 ±0,0065, nDCG@10 ±0,0023. **Top-5 không đổi** ở cả hai lần, nên Recall@5/MRR@5/nDCG@5 ổn định; @10 phải đọc kèm sai số này. Nhánh từ vựng thì tất định tuyệt đối (0/77 câu lệch qua nhiều lần chạy).

| Config | Recall@5 | Recall@10 | MRR@5 | MRR@10 | nDCG@5 | nDCG@10 | n_ok/n_queries |
|---|---|---|---|---|---|---|---|
| hybrid | 0.5455 | 0.7532 | 0.366 | 0.393 | 0.4069 | 0.4764 | 77/77 |
| lexical_only | 0.3117 | 0.4156 | 0.2245 | 0.2381 | 0.2455 | 0.2802 | 77/77 |
| dense_only | 0.6494 | 0.7727 | 0.487 | 0.5037 | 0.526 | 0.5659 | 77/77 |

## 2. Tái lập

- `hybrid`: commit `5b7355c437520394dd029b5a9efb1ceac2963cb4`, model embedding `baai/bge-m3`, n=77, ts=2026-08-28T21:09:49.194080+00:00
- `lexical_only`: commit `5b7355c437520394dd029b5a9efb1ceac2963cb4`, model embedding `baai/bge-m3`, n=77, ts=2026-08-28T21:09:52.500572+00:00
- `dense_only`: commit `5b7355c437520394dd029b5a9efb1ceac2963cb4`, model embedding `baai/bge-m3`, n=77, ts=2026-08-28T21:14:51.856543+00:00

## 3. 10 câu tệ nhất (config `hybrid`)

### `lao-001-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu sếp em cứ chửi bới, xúc phạm em trước mặt mọi người thì có được không ạ?
- Điều luật đúng: 45/2019/QH14 > Điều 127
- Hệ thống trả về (top 3): 95/2015/QH13 > Điều 152; 100/2015/QH13 > Điều 155; 101/2015/QH13 > Điều 73

### `lao-001-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Công ty có được trừ thẳng tiền lương của em vì đi muộn vài lần không ạ?
- Điều luật đúng: 45/2019/QH14 > Điều 127
- Hệ thống trả về (top 3): 45/2019/QH14 > Điều 97; 100/2015/QH13 > Điều 273; 45/2019/QH14 > Điều 102

### `lao-002-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu lương tối thiểu vùng mới thấp hơn lương cũ, công ty tôi có phải trả lương cũ cho nhân viên đã làm từ trước không?
- Điều luật đúng: 293/2025/NĐ-CP > Điều 5
- Hệ thống trả về (top 3): 122/2015/NĐ-CP > Điều 5; 157/2018/NĐ-CP > Điều 5; 141/2017/NĐ-CP > Điều 5

### `lao-004-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Tôi ký hợp đồng với công ty hôm nay, vậy là từ lúc nào tôi bắt đầu đi làm chính thức?
- Điều luật đúng: 45/2019/QH14 > Điều 23
- Hệ thống trả về (top 3): 95/2015/QH13 > Điều 151; 337/2025/NĐ-CP > Điều 28; 12/2022/NĐ-CP > Điều 46

### `lao-005-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu công ty tôi đóng cửa và tôi bị mất việc, tôi có được nhận tiền hỗ trợ gì không và bao nhiêu?
- Điều luật đúng: 45/2019/QH14 > Điều 47
- Hệ thống trả về (top 3): 84/2015/QH13 > Điều 55; 101/2015/QH13 > Điều 486; 145/2020/NĐ-CP > Điều 8 > Khoản 1

### `lao-005-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Tôi làm ở công ty này được 5 năm, giờ bị cho nghỉ việc, thì tôi sẽ được nhận bao nhiêu tiền hỗ trợ mất việc?
- Điều luật đúng: 45/2019/QH14 > Điều 47
- Hệ thống trả về (top 3): 145/2020/NĐ-CP > Điều 5; 145/2020/NĐ-CP > Điều 8 > Khoản 5; 101/2015/QH13 > Điều 78

### `lao-009-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu tôi làm sai gì đó ở nước ngoài, thì cán bộ ở Đại sứ quán Việt Nam có thể phạt tôi bao nhiêu tiền?
- Điều luật đúng: 12/2022/NĐ-CP > Điều 56
- Hệ thống trả về (top 3): 12/2022/NĐ-CP > Điều 42 > Khoản 9; 12/2022/NĐ-CP > Điều 46; 12/2022/NĐ-CP > Điều 42 > Khoản 8

### `lao-009-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Tôi có thể bị phạt tối đa bao nhiêu nếu tôi vi phạm quy định nào đó khi làm việc với cơ quan đại diện của Việt Nam ở nước ngoài?
- Điều luật đúng: 12/2022/NĐ-CP > Điều 56
- Hệ thống trả về (top 3): 12/2022/NĐ-CP > Điều 43 > Khoản 6; 12/2022/NĐ-CP > Điều 46; 12/2022/NĐ-CP > Điều 44

### `lao-010-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Tôi muốn làm việc chỉ 4 tiếng một ngày thôi thì có được không ạ?
- Điều luật đúng: 45/2019/QH14 > Điều 32
- Hệ thống trả về (top 3): 18/2021/TT-BLĐTBXH > Điều 4; 45/2019/QH14 > Điều 25; 18/2021/TT-BLĐTBXH > Điều 5

### `lao-011-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Công ty tôi từ chối ngồi lại nói chuyện với đại diện nhân viên để bàn về quyền lợi chung thì có bị phạt không?
- Điều luật đúng: 12/2022/NĐ-CP > Điều 16
- Hệ thống trả về (top 3): 12/2022/NĐ-CP > Điều 35; 12/2022/NĐ-CP > Điều 28; 92/2015/QH13 > Điều 375

## 4. Task 10 — Graph + endpoint + tập bẫy (Plan 3)

### Ba bug trong pseudocode brief đã sửa khi nối graph

1. **`_db_provisions` phẳng → đổi sang đệ quy.** Mẫu code trong brief tự viết một
   SELECT phẳng (`WHERE p.id = ANY(:ids)`), không JOIN đệ quy, không mang
   `parent_id`. `verify_tier1._cay_con` cần duyệt XUỐNG toàn bộ hậu duệ
   (Khoản/Điểm) để so quote — 73,6% số Điều trong corpus chỉ có `noi_dung` là
   tiêu đề (đo ở Task 5), thân nằm ở con. Bản phẳng sẽ loại NHẦM phần lớn claim
   hợp lệ trên các Điều đó, và còn làm `assemble` không bao giờ hiển thị đúng
   `khop_tai` (luôn rơi về `claim.provision_id` — tiêu đề rỗng nội dung). Sửa:
   dùng lại `nap_provisions()` (đệ quy, đã test ở Task 5) + join `documents`
   lấy `so_ky_hieu`/`ten`, MỘT hình dạng dùng chung cho tier1/tier2/assemble.
2. **Import thiếu.** Brief dùng `Effectivity(...)`/`EffectivityVerdict...` làm
   fallback trong `n_tier1` nhưng chỉ import `danh_gia` (không dùng tới, và
   cũng không import hai tên trên) — `NameError` nếu chạy đúng như viết.
3. **`n_tier2` gọi `verify_tier2()` (không trace) thay vì `verify_tier2_and_trace()`.**
   Task 6 đã xây `verify_tier2_and_trace` đúng để ghi `tier2_generate_model`/
   `tier2_judge_model`/Usage thật vào `traces`, nhưng brief's `n_tier2` gọi
   hàm KHÔNG trace — bỏ mất toàn bộ số liệu yêu cầu #1 cần. Sửa: gọi
   `verify_tier2_and_trace`, gộp `traces` trả về vào state.

### Bốn yêu cầu tích luỹ — cách chốt

1. **Tên model tầng 2 xuống DB thật.** Cột mới `traces.generate_model`/
   `judge_model` lấy từ `state["traces"]["tier2_generate_model"/"tier2_judge_model"]`
   (Task 6 đặt) — KHÔNG gọi lại `generate_model()`/`judge_model()` từ Settings,
   vì đó là cấu hình TĨNH chứ không phải bằng chứng "request này đã dùng gì".
   NULL khi tầng 2 không chạy (ngoai_pham_vi, insufficient_evidence, hoặc
   `VERIFY_TIER2_ENABLED=false`) — NULL nghĩa là "không chạy", không phải "quên
   ghi".
2. **Kích thước expand.** Cột mới `expand_before` (= `len(retrieved)` trước khi
   gọi `expand()`) / `expand_after` (= `len(deep)` — CHỈ nhánh sâu, không gồm
   `shallow`, vì đó mới là tập THẬT SỰ chảy xuống `generate_claims`; đo được
   trên 2 câu thật bên dưới: 14→177 (12,6×) và 28→455 (16,3×) — cùng cấp độ lớn
   với trung vị 10,1×/max 30,5× mà Task 7 đo trên mẫu 11 câu, dù phương pháp
   khác (ở đây có rewrite_query sinh thêm biến thể truy vấn nên "trước" thường
   > 10).
3. **Quy ước cộng dồn traces.** Có **5** điểm gọi LLM trong pipeline — brief chỉ
   liệt kê 4 (route/rewrite_query/generate_claims/verify_tier2), bỏ sót
   `assemble` (hành văn câu trả lời cuối cũng gọi LLM). Mỗi node vẫn GHI ĐÈ
   đúng khoá riêng của mình vào `state["traces"]` (không đổi 9 node đã build).
   `_tong_hop_traces()` (mới, `src/api/routes.py`) cộng RÕ RÀNG 5 bộ khoá
   (`route_*`, `rewrite_query_*`, khoá TRẦN của `generate_claims`, `tier2_*`,
   `assemble_*`) thành `token_in`/`token_out`/`cost_usd` của MỘT hàng traces —
   cố ý dùng danh sách khoá tường minh, không dùng quy tắc ngầm "mọi khoá kết
   thúc bằng `_token_in`" (một khoá tương lai trùng hậu tố mà không phải chi
   phí thật của request sẽ bị cộng nhầm). Thêm node gọi LLM thứ 6 → sửa 3 danh
   sách khoá trong `routes.py`, không sửa chỗ khác. Test thuần (không DB/LLM)
   khoá quy ước này: `tests/test_api/test_tra_cuu.py::test_tong_hop_traces_*`.
4. **Migration `008_traces_model_expand.sql`** — 4 cột mới, đều NULLABLE
   (không NOT NULL/DEFAULT: một request hợp lệ có thể không đi qua tầng 2 hay
   expand). `ADD COLUMN IF NOT EXISTS` tự idempotent; test chạy migration hai
   lần SAU KHI đã insert một dòng `traces` thật
   (`test_migration_idempotent_KHI_DA_CO_DONG_traces`), đúng quy tắc Plan 1
   "bảng rỗng không bắt được lỗi".

### 5 câu thật chạy end-to-end (graph thật, Postgres thật, OpenRouter thật)

| Câu hỏi | result_type | claims_raw→tier1→tier2 | expand trước→sau | cảnh báo hiệu lực |
|---|---|---|---|---|
| "người lao động đơn phương chấm dứt hợp đồng lao động thì có quyền lợi gì" | answer | 21→20→13 | 14→177 (12,6×) | Có — 45/2019/QH14 hết hiệu lực một phần (sửa đổi bởi 19/2023/QH15) |
| "công ty nợ lương thì làm sao" | answer | 9→8→8 | 28→455 (16,3×) | Có — cùng cảnh báo trên |
| "thu nhập bao nhiêu thì phải đóng thuế thu nhập cá nhân" | out_of_scope | 0→0→0 | — | không áp dụng |
| "đăng ký kết hôn cần thủ tục gì" | out_of_scope | 0→0→0 | — | không áp dụng |
| "thủ tục nhập học lớp một cần giấy tờ gì" | abstain | 0→0→0 | 23→219 (9,5×) | không áp dụng |

Hai câu đầu là **regression thật từ hai pain point coordinator nêu** (không có
trong brief, không có trong trap.yaml — chọn để kiểm tra trên graph đã nối đầy
đủ tier1+tier2):

- **Nhầm phía chủ thể** (Điều 35 người lao động vs Điều 36 người sử dụng lao
  động, Plan 2 đo được hệ thống xếp Điều 36 hạng 1 cho câu hỏi về NLĐ): trên
  graph đầy đủ, câu trả lời trích dẫn **đúng Điều 35** (7/13 citation đã qua
  tầng 2 là Điều 35, phần còn lại là Điều 40/138/145-89/12-2022 liên quan hợp
  lệ) — KHÔNG thấy Điều 36. Pain point này **không tái lập** trên pipeline đã
  verify đầy đủ trong lần chạy này.
- **Nhiễu xuyên miền** ("công ty nợ lương thì làm sao" từng ra hạng 1 là Điều
  273 BLHS): câu trả lời trích Điều 94/97/48/35 Bộ luật Lao động + NĐ 12/2022 —
  KHÔNG có Điều 273 BLHS. Cũng không tái lập trong lần chạy này.

Cả hai chỉ là **một lần chạy, không phải benchmark lặp lại** (LLM không tất
định tuyệt đối dù `LLM_TEMPERATURE=0.0` — xem ghi chú sai số tái lập dense ở
mục 1) — không kết luận "đã sửa dứt điểm", chỉ ghi nhận KHÔNG tái lập trong
lần đo này.

Câu "thủ tục nhập học lớp một cần giấy tờ gì" (nhóm `ngoai_pham_vi` của
trap.yaml) là ca `route()` PHÂN LOẠI SAI (đưa qua `tra_cuu` thay vì
`ngoai_pham_vi`) nhưng lớp an toàn hạ nguồn (`generate_claims` tự nhận
`insufficient_evidence` vì corpus không phủ giáo dục) vẫn chặn được, kết thúc ở
`abstain` thay vì một câu trả lời tự tin sai. Không phải hành vi trap.yaml
mong đợi (`out_of_scope`), nhưng KHÔNG PHẢI câu trả lời bịa — ghi nhận đúng như
đo được.

### Phân bố `result_type` trên tập bẫy — **KHÔNG CHẠY ĐỦ 40/40**

**Chỉ 17/40 câu chạy xong thật trong ngân sách 38 lần gọi API** (2 câu demo ở
trên + 15/15 câu nhóm `ngoai_pham_vi` + 0/15 nhóm `dieu_khong_ton_tai` (1 câu
`trap-nonexist-01` bắt đầu chạy rồi bị chặn giữa chừng bởi trần ngân sách, trả
502) + 0/10 nhóm `van_ban_bi_thay`. Đây là con số THẬT, không phải mẫu chọn để
đẹp — báo đúng như brief yêu cầu.

| Nhóm | Chạy được | Đúng kỳ vọng |
|---|---|---|
| `ngoai_pham_vi` (out_of_scope) | 15/15 | 14/15 (93%) — 1 câu ("thủ tục nhập học lớp một...") route sai sang tra_cuu, an toàn nhờ lớp sau, kết thúc `abstain` chứ không phải `out_of_scope` |
| `dieu_khong_ton_tai` (abstain) | 0/15 | không đo được — hết ngân sách giữa câu đầu tiên |
| `van_ban_bi_thay` (warning_*) | 0/10 | không đo được — hết ngân sách trước khi tới nhóm này |

**Vì sao hụt ngân sách nặng đến vậy:** một câu hỏi thuộc phạm vi (route →
tra_cuu) tốn tới 8 lần gọi API thật (route + rewrite + 1-3 embed theo số biến
thể + generate_claims + tier2 + assemble hành văn) — 2 câu demo đã tiêu 16/38.
Câu ngoài phạm vi RẺ (1 call/câu, route → out_of_scope, 0 token sau đó) nên
chạy hết cả 15 câu chỉ tốn 15+6 (câu route sai) = 21 lần. Cộng dồn, 38 lần gọi
chỉ đủ cho ĐÚNG MỘT trong hai nhóm còn lại đắt tiền (`dieu_khong_ton_tai`/
`van_ban_bi_thay`) chạy được vài câu — không đủ cho cả hai. **Concern gửi
coordinator ở cuối báo cáo.**

### Step 6 — so ba cấu hình verify: KHÔNG chạy được (hết ngân sách)

Không còn lần gọi API nào để chạy `VERIFY_TIER2_ENABLED=false/true` trên cùng
tập câu. Thay vào đó, một quan sát **đọc từ code, KHÔNG PHẢI đo**: theo ruling
Task 9 trong `assemble.py` (dòng comment "RULING 2026-08-31"), khi
`tier2 = []` (tắt qua settings, hoặc không claim nào qua tầng 1),
`tier2.get(pos)` luôn `None` cho MỌI vị trí → `verified` luôn rỗng → `assemble`
luôn trả `abstain` cho bất kỳ câu nào có ít nhất một claim qua tầng 1. Nghĩa là
cấu hình "chỉ tầng 1" (`VERIFY_TIER2_ENABLED=false`), NẾU đo thật, gần như chắc
chắn sẽ cho tỉ lệ `abstain` gần 100% trên mọi câu có claim — đây là **suy luận
từ đọc code, chưa xác nhận bằng chạy thật**, nêu ra để coordinator biết trước
khi quyết có cần chạy xác nhận ở phiên sau không.

### Số lần gọi API thật

**38/38** (chat=29, embed=9) — dừng CỨNG đúng tại trần bằng một wrapper đếm
(`monkeypatch` `LlmClient.chat`/`EmbeddingClient.embed`, raise trước khi thực
sự gọi nếu đã chạm trần) trong script chạy một lần, không lặp lại. **Không
quan sát 429** trong lần chạy này (khác cảnh báo "OpenRouter đang trả 429
thật" trong brief — có thể do 38 lần chưa đủ chạm ngưỡng tải cao, hoặc đã đỡ
hơn tại thời điểm chạy).
