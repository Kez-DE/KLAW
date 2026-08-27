# Phase 0 — Findings (KLAW)

| # | Câu hỏi | Trả lời | Nguồn |
|---|---|---|---|
| 1 | Railway Postgres bật được `pgvector` + `unaccent`? | | |
| 2 | Railway auto-detect Dockerfile, hay cần `railway.json`? | | |
| 3 | Class `prov-*` có phủ đều cả 18 văn bản? | | |
| 4 | `/doc/{id}/related` có trả cạnh ĐI VÀO không? | KHÔNG — endpoint chỉ trả cạnh đi ra | https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/139094/related?pageNumber=0&pageSize=50 |
| 5 | **[NGƯỜI DÙNG]** Đối chiếu tay 10 điều BLLĐ với văn bản hợp nhất | | |
| 6 | `doc_id` của NĐ 157/2018, 141/2017, 122/2015 | 157/2018/NĐ-CP: `132862`, 141/2017/NĐ-CP: `126319`, 122/2015/NĐ-CP: `92898` | data/raw/metadata.parquet |
| 7 | **[NGƯỜI DÙNG]** Đối chiếu tay hiệu lực 6 luật gốc, ưu tiên Luật BHXH 41/2024 (`175027`) | | |

## Việc KHÔNG delegate được

#5 và #7 cần đọc văn bản hợp nhất và phán đoán pháp lý. Agent không làm thay.
Chặn: task Rule engine (plan 3) và cơ chế hiệu lực Mức 2 guard (plan 2).
