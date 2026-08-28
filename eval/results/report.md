# Eval Report — Retrieval Ablation (Plan 2, Task 9)

> **CẢNH BÁO:** `golden_qa.yaml` (77 câu) toàn bộ đang `da_review: false` — chưa ai, kể cả chủ dự án, duyệt tay từng câu (Task 8). Mọi con số dưới đây là **CHỈ BÁO cho hướng phát triển**, KHÔNG phải kết quả công bố được trong khóa luận cho tới khi review xong.

## 1. Bảng ablation (77 câu golden_qa)

| Config | Recall@5 | Recall@10 | MRR@5 | MRR@10 | nDCG@5 | nDCG@10 | n_ok/n_queries |
|---|---|---|---|---|---|---|---|
| hybrid | 0.5649 | 0.7338 | 0.3043 | 0.3282 | 0.368 | 0.4268 | 77/77 |
| bm25_only | 0.1299 | 0.1558 | 0.0784 | 0.0826 | 0.0914 | 0.1001 | 77/77 |
| dense_only | 0.6753 | 0.7857 | 0.511 | 0.5253 | 0.5507 | 0.5857 | 77/77 |

## 2. Tái lập

- `hybrid`: commit `a50b524d6039633b3a0f02fe74d6c03fe6236cff`, model embedding `baai/bge-m3`, n=77, ts=2026-08-28T17:24:19.059339+00:00
- `bm25_only`: commit `a50b524d6039633b3a0f02fe74d6c03fe6236cff`, model embedding `baai/bge-m3`, n=77, ts=2026-08-28T17:24:24.101040+00:00
- `dense_only`: commit `a50b524d6039633b3a0f02fe74d6c03fe6236cff`, model embedding `baai/bge-m3`, n=77, ts=2026-08-28T17:25:23.419127+00:00

## 3. 10 câu tệ nhất (config `hybrid`)

### `lao-000-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Công ty tôi có 50 nhân viên, trong đó có 30 nữ. Vậy công ty tôi có phải là công ty sử dụng nhiều lao động nữ không?
- Điều luật đúng: 145/2020/NĐ-CP > Điều 74
- Hệ thống trả về (top 3): 12/2022/NĐ-CP > Điều 28; 145/2020/NĐ-CP > Điều 80; 45/2019/QH14 > Điều 42

### `lao-001-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu sếp em cứ chửi bới, xúc phạm em trước mặt mọi người thì có được không ạ?
- Điều luật đúng: 45/2019/QH14 > Điều 127
- Hệ thống trả về (top 3): 101/2015/QH13 > Điều 73; 100/2015/QH13 > Điều 155; 101/2015/QH13 > Điều 326

### `lao-001-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Công ty có được trừ thẳng tiền lương của em vì đi muộn vài lần không ạ?
- Điều luật đúng: 45/2019/QH14 > Điều 127
- Hệ thống trả về (top 3): 12/2022/NĐ-CP > Điều 17; 100/2015/QH13 > Điều 273; 45/2019/QH14 > Điều 102

### `lao-002-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu lương tối thiểu vùng mới thấp hơn lương cũ, công ty tôi có phải trả lương cũ cho nhân viên đã làm từ trước không?
- Điều luật đúng: 293/2025/NĐ-CP > Điều 5
- Hệ thống trả về (top 3): 122/2015/NĐ-CP > Điều 5; 157/2018/NĐ-CP > Điều 5; 141/2017/NĐ-CP > Điều 5

### `lao-004-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Tôi ký hợp đồng với công ty hôm nay, vậy là từ lúc nào tôi bắt đầu đi làm chính thức?
- Điều luật đúng: 45/2019/QH14 > Điều 23
- Hệ thống trả về (top 3): 100/2015/QH13 > Điều 317; 337/2025/NĐ-CP > Điều 28; 100/2015/QH13 > Điều 278

### `lao-004-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu tôi và công ty thỏa thuận là hợp đồng có hiệu lực vào tuần sau, thì có được không?
- Điều luật đúng: 45/2019/QH14 > Điều 23
- Hệ thống trả về (top 3): 293/2025/NĐ-CP > Điều 5; 92/2015/QH13 > Điều 39 > Khoản 2; 91/2015/QH13 > Điều 401

### `lao-009-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Tôi có thể bị phạt tối đa bao nhiêu nếu tôi vi phạm quy định nào đó khi làm việc với cơ quan đại diện của Việt Nam ở nước ngoài?
- Điều luật đúng: 12/2022/NĐ-CP > Điều 56
- Hệ thống trả về (top 3): 12/2022/NĐ-CP > Điều 44; 12/2022/NĐ-CP > Điều 32; 12/2022/NĐ-CP > Điều 45

### `lao-010-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Tôi muốn làm việc chỉ 4 tiếng một ngày thôi thì có được không ạ?
- Điều luật đúng: 45/2019/QH14 > Điều 32
- Hệ thống trả về (top 3): 145/2020/NĐ-CP > Điều 114; 45/2019/QH14 > Điều 105; 145/2020/NĐ-CP > Điều 102

### `lao-013-0` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Công ty tôi mới mở, tôi cần phải làm gì với mấy bạn nhân viên mới ngay từ đầu để đúng quy định của nhà nước?
- Điều luật đúng: 45/2019/QH14 > Điều 12
- Hệ thống trả về (top 3): 84/2015/QH13 > Điều 14; 145/2020/NĐ-CP > Điều 103; 45/2019/QH14 > Điều 144

### `lao-013-1` — recall@5=0.0, mrr@5=0.0
- Câu hỏi: Nếu công ty tôi có thay đổi về nhân sự, ví dụ có người nghỉ việc hay có người mới vào, thì tôi có cần báo cáo cho cơ quan chức năng không và báo cáo khi nào?
- Điều luật đúng: 45/2019/QH14 > Điều 12
- Hệ thống trả về (top 3): 101/2015/QH13 > Điều 73; 145/2020/NĐ-CP > Điều 4; 101/2015/QH13 > Điều 78
