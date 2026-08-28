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
