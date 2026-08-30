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

### ⚠️ Phát hiện quan trọng nhất: `dieu_khong_ton_tai` 0/15 — KHÔNG phải "trích dẫn bịa" theo nghĩa hẹp, mà tệ hơn ở một cách khác

**Cả 15/15 câu hỏi về một Điều KHÔNG TỒN TẠI đều ra `result_type=answer`, không câu nào `abstain`.** Cơ chế trap giả định sai: retrieval khớp theo NGỮ NGHĨA (nội dung câu hỏi), không theo số Điều — nên model không bao giờ THỬ dẫn "Điều 999"/"Điều 250" để tầng 1 phép kiểm 1 bắt được; nó chỉ thấy các Điều THẬT liên quan chủ đề trong context và dẫn đúng những Điều đó. **Citation trong `citations[]` là THẬT và ĐÃ QUA CẢ HAI TẦNG** (tồn tại, đúng nguyên văn, được judge xác nhận) — đây không phải lỗi tra-bảng.

**Lỗi thật nằm ở bước hành văn cuối (`assemble` — LLM, KHÔNG qua tầng 1/2) — ca `trap-nonexist-09`:**

- Câu hỏi: "Điều 550 Bộ luật Tố tụng dân sự quy định thủ tục gì" (BLTTDS chỉ có tới Điều 517 — 550 không tồn tại)
- Citation thật (đã qua tầng 1+2): `92/2015/QH13 > Điều 363/364/365`
- **Answer (nguyên văn):** *"Điều 550 Bộ luật Tố tụng dân sự quy định thủ tục nhận và xử lý đơn yêu cầu, trả lại đơn yêu cầu và thông báo thụ lý đơn yêu cầu."*

Model lấy ĐÚNG nội dung từ Điều 363-365 (tiêu đề ba điều này khớp y hệt ba cụm trong câu) nhưng **viết văn xuôi gán nó cho "Điều 550"** — con số từ chính câu hỏi bịa, không phải từ citation đã verify. Người đọc chỉ xem `answer` (không đối chiếu `citations[]`) sẽ tin Điều 550 có thật và nói đúng điều đó. Đây là ảo giác THẬT, nhưng nằm ở **hành văn cuối (không được tầng 1/2 kiểm)**, không phải ở tầng verify — 13/15 câu khác hoàn toàn không nhắc lại số Điều bịa trong `answer` (im lặng thay thế bằng Điều thật, không sai nhưng cũng không nói rõ "999 không tồn tại").

**Đối chứng — 1/15 câu hành văn ĐÚNG:** `trap-nonexist-07` ("Điều 450 Bộ luật Hình sự"): *"Thông tin bạn cung cấp không đề cập đến Điều 450 Bộ luật Hình sự."* — model tự nhận không có căn cứ, nhưng `result_type` vẫn là `answer` (có 1 citation kèm theo, quan hệ khá xa). Cho thấy `result_type` hai giá trị hiện tại không phân biệt được "trả lời có căn cứ" với "trả lời kèm tự bác bỏ".

**Kết luận cho khoá luận:** tầng 1 phép kiểm 1 (provision tồn tại) làm ĐÚNG việc nó được thiết kế để làm (không cho qua provision_id bịa) — nhưng KHÔNG bảo vệ được trường hợp câu hỏi tự mang một tiền đề sai (số Điều không tồn tại) mà model né tránh bằng cách âm thầm trả lời một câu hỏi khác. Đây là một lớp lỗ hổng NGOÀI phạm vi bốn phép kiểm hiện có — bước hành văn cuối cùng của `assemble` không được đối chiếu lại với accuracy của chính câu hỏi gốc.

### Bảng 40/40 theo nhóm

| Nhóm | Đúng/Tổng | % | Ghi chú |
|---|---|---|---|
| `ngoai_pham_vi` (kỳ vọng out_of_scope) | 14/15 | 93% | 1 câu route sai → `abstain` (an toàn, không phải trả lời sai) |
| `dieu_khong_ton_tai` (kỳ vọng abstain) | 0/15 | 0% | Tất cả `answer` — xem phân tích ở trên. Citation thật, hành văn có 1 ca gán sai số Điều |
| `van_ban_bi_thay` (kỳ vọng warning) | 10/10 | 100% | Xem chi tiết mục dưới — kết quả THÀNH CÔNG rõ ràng nhất của tập bẫy |
| **TỔNG** | **24/40** | **60%** | Đo đủ 40/40, không phải mẫu chọn |

### Nhóm `van_ban_bi_thay` — chi tiết (10/10 đúng)

| Câu | Văn bản dẫn (`so_ky_hieu`) | Cảnh báo | Nêu đích danh văn bản thay thế? |
|---|---|---|---|
| superseded-01 | 90/2019/NĐ-CP | bi_thay_the | Có — "74/2024/NĐ-CP cùng chủ đề, hiệu lực từ 2024-07-01" |
| superseded-02 | 122/2015, 141/2017, 157/2018, 74/2024, 90/2019 (cả 5!) | 5 cảnh báo | Có, từng văn bản một |
| superseded-03 | 90/2019/NĐ-CP | bi_thay_the | Có — qua 74/2024 |
| superseded-04 | 122/2015, 141/2017, 157/2018, 90/2019 | 4 cảnh báo | Có, từng văn bản |
| superseded-05 | 122/2015/NĐ-CP | bi_thay_the | Có — "153/2016/NĐ-CP... từ 2017-01-01" |
| superseded-06 | 141/2017/NĐ-CP | bi_thay_the | Có — "đồ thị xác nhận: bị 157/2018 thay thế từ 2019-01-01" |
| superseded-07 | 157/2018/NĐ-CP | bi_thay_the | Có — "đồ thị xác nhận: bị 90/2019 thay thế từ 2020-01-01" |
| superseded-08 | 74/2024/NĐ-CP | het_hieu_luc | Có — "ngày hết hiệu lực 2026-01-01 đã qua tại 2026-08-31" |
| superseded-09 | 122/2015, 141/2017, 157/2018, 90/2019 | 4 cảnh báo | Có, từng văn bản |
| superseded-10 | 90/2019/NĐ-CP | bi_thay_the | Có — qua 74/2024 |

**10/10 — cả bốn nghị định MOJ đánh sai "còn hiệu lực" (122/2015, 141/2017, 157/2018, 90/2019) đều bị hệ thống gắn cảnh báo, và cảnh báo luôn NÊU ĐÍCH DANH văn bản thay thế + ngày hiệu lực, không phải một nhãn chung chung.** Đây là bằng chứng trực tiếp, đo đủ, cho đúng luận điểm trung tâm của khoá luận: lỗi của CSDL quốc gia (MOJ) đi tới được người dùng dưới dạng cảnh báo cụ thể, không bị mất dọc đường.

Một số câu (02, 04, 09) trả về NHIỀU citation từ cả 4 nghị định cùng lúc (model tổng hợp câu trả lời từ toàn bộ chuỗi lịch sử thay vì chỉ nghị định mới nhất được retrieve) — mỗi văn bản trong số đó đều nhận đúng cảnh báo riêng, không có văn bản nào "lọt lưới" dù câu trả lời gộp nhiều nguồn.

### Ablation 3 cấu hình (Step 6)

| Cấu hình | Cách đo | Kết quả trên câu có claim qua tầng 1 |
|---|---|---|
| không verify (lý thuyết) | suy ra từ `claims_raw` (chưa lọc gì) — KHÔNG đo trực tiếp | Mọi claim thô đều sẽ "trả lời" được, kể cả case gán sai số Điều ở `assemble` (nonexist-09) — đây chính xác là chế độ hỏng tầng 1 tồn tại để chặn |
| tầng 1 (`VERIFY_TIER2_ENABLED=false`) | **ĐO THẬT** — 4 câu (2 nonexist + 2 superseded), đều có tier1_ok≥4 | **4/4 → `abstain`** (100%). Xác nhận đúng suy luận từ code: `tier2=[]` → `verified` luôn rỗng → không câu nào qua được cổng `assemble` |
| tầng 1+2 (mặc định, ON) | **ĐO THẬT** — cùng 4 câu, dữ liệu từ round đo 40/40 ở trên | 4/4 → `answer` (có citation + cảnh báo khi áp dụng) |

**Đúng như đã suy luận trước khi đo: tắt tầng 2 làm hệ thống abstain 100% trên mọi câu có bằng chứng thật.** Đây LÀ kết quả của thiết kế hiện tại, không phải lỗi: `assemble.py`'s ruling (Task 9) coi "tier2 không chạy" và "tier2 chạy nhưng không supported" là CÙNG một trạng thái (không verified) — tầng 2 vì vậy là ĐIỀU KIỆN CẦN, không phải một bộ lọc tinh chỉnh thêm độ chính xác. Ablation "tầng 1 only" không tồn tại như một điểm giữa hữu ích trên đường cong precision/recall trong pipeline hiện tại — nó luôn từ chối.

### Số lần gọi API thật và chi phí

**294/300** (dừng trước khi chạm trần, còn dư 6 lần) — chat + embed cộng dồn qua 3 script chạy tuần tự trong cùng phiên (round 1: 38, round 2: 232, ablation OFF: 24). Không quan sát 429 lần nào trong toàn bộ 3 lượt.

Chi phí: mẫu đo `cost_usd` trên các hàng `traces` thật dao động 0,0012–0,0065 USD/request tuỳ độ dài câu trả lời (không đồng nhất bằng $0,0065 như ước tính ban đầu — câu có ít claim/answer ngắn rẻ hơn nhiều). Tổng cộng khoảng 60 request full-pipeline thật đã chạy trong 3 lượt — chi phí thực tế nằm trong khoảng đã ước tính (~$0,15–0,25), dưới ngân sách $0,20-0,30 coordinator chấp nhận.

### Stability check (3 lượt/câu) — làm được cho 2 câu regression trong round 2

`demo-subject-confusion` và `demo-cross-domain` mỗi câu chạy **3 lần** (1 lần round 1 + 2 lần round 2): cả 3 lần của MỖI câu đều ra `result_type=answer` với cảnh báo hiệu lực xuất hiện ổn định (không câu nào đổi sang abstain/thiếu cảnh báo giữa 3 lần) — token_out dao động nhẹ (vd. 6331/6527/6129 cho subject-confusion) đúng như dự đoán do OpenRouter không tất định tuyệt đối, nhưng KHÔNG đổi kết luận định tính qua 3 lần.
