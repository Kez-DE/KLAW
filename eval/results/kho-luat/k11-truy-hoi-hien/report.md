# Eval Report — Retrieval Ablation (Plan 2, Task 9)

> **CẢNH BÁO:** golden_qa.yaml CHƯA được người duyệt tay (da_review: false trên toàn bộ 77 câu, Task 8) — con số dưới đây là CHỈ BÁO cho hướng phát triển, KHÔNG phải kết quả công bố được. Chưa ai, kể cả chủ dự án, duyệt tay từng câu.

## 1. Bảng ablation (77 câu golden_qa)

`lexical_only` là **truy hồi từ vựng bằng `tsvector` + `ts_rank` của PostgreSQL** (config `simple` + `unaccent`, truy vấn OR, chuẩn hoá độ dài `normalization=1`, lọc hư từ có) — **không phải BM25**: `ts_rank` không có tham số `k1`/`b` và không dùng IDF. Hai tham số trên chọn theo đo, không theo mặc định của Postgres; bảng sweep đầy đủ và lý do ở `docs/bm25-tuning.md` (tái lập: `python -m scripts.sweep_bm25`).

> **Sai số tái lập:** nhánh dense KHÔNG tất định tuyệt đối. Vector truy vấn do OpenRouter trả về đôi khi lệch tới ~2,7e-4 mỗi chiều giữa hai lần gọi CÙNG một câu (đo được: 1/4 lần gọi lệch), đủ để đảo thứ tự vài láng giềng sát nhau. Chạy `dense_only` ba lần cho Recall@10 0,7727 / 0,7792 / 0,7727: giữa hai lần đầu, 5/77 câu đổi thứ tự ở **hạng 7–10** và 1 câu đổi metric → biên độ Recall@10 ±0,0065, nDCG@10 ±0,0023. **Top-5 không đổi** ở cả hai lần, nên Recall@5/MRR@5/nDCG@5 ổn định; @10 phải đọc kèm sai số này. Nhánh từ vựng thì tất định tuyệt đối (0/77 câu lệch qua nhiều lần chạy).

| Config | Recall@5 | Recall@10 | MRR@5 | MRR@10 | nDCG@5 | nDCG@10 | n_ok/n_queries |
|---|---|---|---|---|---|---|---|
| hybrid | 0.5584 | 0.7208 | 0.3403 | 0.3624 | 0.3928 | 0.4461 | 77/77 |
| lexical_only | 0.1234 | 0.2013 | 0.0788 | 0.0905 | 0.0897 | 0.1173 | 77/77 |
| dense_only | 0.7403 | 0.8182 | 0.5361 | 0.5451 | 0.5832 | 0.6095 | 77/77 |

## 2. Tái lập

- `hybrid`: commit `6537fcc93b1ed81968f54cc5ade9ab85d971ffc5`, model embedding `voyageai/voyage-4-lite`, n=77, ts=2026-09-29T10:46:40.473488+00:00
- `lexical_only`: commit `6537fcc93b1ed81968f54cc5ade9ab85d971ffc5`, model embedding `voyageai/voyage-4-lite`, n=77, ts=2026-09-29T10:46:49.412462+00:00
- `dense_only`: commit `6537fcc93b1ed81968f54cc5ade9ab85d971ffc5`, model embedding `voyageai/voyage-4-lite`, n=77, ts=2026-09-29T10:47:32.841547+00:00

## 3. 10 câu tệ nhất (config `hybrid`)

### `lao-001-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu sếp em cứ chửi bới, xúc phạm em trước mặt mọi người thì có được không ạ?
- Điều luật đúng: 45/2019/QH14 > Điều 8
- Hệ thống trả về (top 3): 59/2026/NĐ-CP > Điều 34; 45/2019/QH14 > Điều 127; 95/2015/QH13 > Điều 152

### `lao-001-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Công ty có được trừ thẳng tiền lương của em vì đi muộn vài lần không ạ?
- Điều luật đúng: 45/2019/QH14 > Điều 127
- Hệ thống trả về (top 3): 45/2019/QH14 > Điều 97; 158/2025/NĐ-CP > Điều 32; 45/2019/QH14 > Điều 102

### `lao-002-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu lương tối thiểu vùng mới thấp hơn lương cũ, công ty tôi có phải trả lương cũ cho nhân viên đã làm từ trước không?
- Điều luật đúng: 293/2025/NĐ-CP > Điều 5
- Hệ thống trả về (top 3): 45/2019/QH14 > Điều 29; 59/2020/QH14 > Điều 115; 293/2025/NĐ-CP > Điều 3

### `lao-005-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu công ty tôi đóng cửa và tôi bị mất việc, tôi có được nhận tiền hỗ trợ gì không và bao nhiêu?
- Điều luật đúng: 45/2019/QH14 > Điều 46
- Hệ thống trả về (top 3): 04/2017/QH14 > Điều 11; 145/2020/NĐ-CP > Điều 8 > Khoản 6; 59/2020/QH14 > Điều 156

### `lao-005-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Công ty em sáp nhập vào một chỗ khác rồi cắt bớt người, em làm ở đây được 5 năm mà giờ bị cho thôi, em được nhận bao nhiêu tiền?
- Điều luật đúng: 45/2019/QH14 > Điều 47
- Hệ thống trả về (top 3): 97/2022/NĐ-CP > Điều 13; 320/2025/NĐ-CP > Điều 10 > Khoản 8; 145/2020/NĐ-CP > Điều 8 > Khoản 5

### `lao-010-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Tôi muốn làm việc chỉ 4 tiếng một ngày thôi thì có được không ạ?
- Điều luật đúng: 45/2019/QH14 > Điều 32
- Hệ thống trả về (top 3): 18/2021/TT-BLĐTBXH > Điều 4; 18/2026/NĐ-CP > Điều 14 > Khoản 5; 52/2014/NĐ-CP > Điều 17

### `lao-011-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nghe nói công ty với công đoàn đã ký một bản cam kết chung cho cả xưởng từ năm ngoái, mà tới giờ chưa ai trong chúng tôi được đọc. Công ty giấu như vậy có sao không?
- Điều luật đúng: 283/2026/NĐ-CP > Điều 22
- Hệ thống trả về (top 3): 320/2025/NĐ-CP > Điều 10 > Khoản 8; 45/2019/QH14 > Điều 76; 07/2017/QH14 > Điều 31

### `lao-011-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Công ty tôi từ chối ngồi lại nói chuyện với đại diện nhân viên để bàn về quyền lợi chung thì có bị phạt không?
- Điều luật đúng: 283/2026/NĐ-CP > Điều 22
- Hệ thống trả về (top 3): 46/2024/QH15 > Điều 9; 283/2026/NĐ-CP > Điều 21; 104/2025/NĐ-CP > Điều 24

### `lao-013-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Công ty tôi mới mở, tôi cần phải làm gì với mấy bạn nhân viên mới ngay từ đầu để đúng quy định của nhà nước?
- Điều luật đúng: 45/2019/QH14 > Điều 12
- Hệ thống trả về (top 3): 45/2021/NĐ-CP > Điều 15 > Khoản 4; 59/2020/QH14 > Điều 8; 36/2006/CT-TTg > Khoản 2

### `lao-013-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu công ty tôi có thay đổi về nhân sự, ví dụ có người nghỉ việc hay có người mới vào, thì tôi có cần báo cáo cho cơ quan chức năng không và báo cáo khi nào?
- Điều luật đúng: 45/2019/QH14 > Điều 12; 145/2020/NĐ-CP > Điều 4
- Hệ thống trả về (top 3): 36/2006/CT-TTg > Khoản 1; 35/2022/NĐ-CP > Điều 73; 80/2026/NĐ-CP > Điều 2 > Khoản 2
