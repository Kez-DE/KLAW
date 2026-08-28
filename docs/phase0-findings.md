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
| 8 | Điều trung bình có < 1.500 token (giả định Task 2 chunker)? | ĐÚNG — trung bình 283,7 token/Điều (n=3.112, trước khi cắt), p50=205, p95=789, max=4.581. Chỉ 19/3.112 Điều (0,6%) vượt `CHUNK_MAX_TOKENS=1.500` | đo trực tiếp bằng `build_chunks`/`load_provisions` trên corpus thật (`klaw-p1-db-1`) |
| 9 | Corpus ra bao nhiêu chunk (giả định Task 2: 2.000–4.000)? | ĐÚNG — 3.283 chunk. Token: min=15, p50=200, p95=738, max=1.718. 190 chunk neo vào Khoản (do 19 Điều bị cắt); 2/3.283 chunk (0,06%) vẫn vượt 1.500 token sau khi cắt vì bản thân Khoản đó (gồm cả Điểm con) đã dài hơn ngưỡng — thiết kế chỉ cắt một cấp Điều→Khoản, không cắt tiếp xuống Điểm | đo trực tiếp bằng `build_chunks`/`load_provisions` trên corpus thật (`klaw-p1-db-1`) |

## Việc KHÔNG delegate được

#5 và #7 cần đọc văn bản hợp nhất và phán đoán pháp lý. Agent không làm thay.
Chặn: task Rule engine (plan 3) và cơ chế hiệu lực Mức 2 guard (plan 2).
