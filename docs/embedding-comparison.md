# So sánh embedding model trên golden_qa (Task 10, Plan 2)

> **CẢNH BÁO:** golden_qa.yaml CHƯA được người duyệt tay (da_review: false trên toàn bộ câu, Task 8) — con số dưới đây là CHỈ BÁO cho hướng phát triển, KHÔNG phải kết quả công bố được.

Đo bằng cấu hình **`dense_only`**, không phải `hybrid`: trên golden_qa hiện tại BM25 quá yếu (Recall@5 ≈ 0,13, xem `eval/results/report.md`; đã tự sweep `rrf_k` không cứu được) nên trộn vào hybrid làm nhiễu tín hiệu — dense thuần là nơi chất lượng embedding hiện ra rõ nhất.

VN-MTEB không benchmark model thương mại (OpenAI/Google/Voyage) trên tiếng Việt — bảng dưới đây, dù nhỏ, là số liệu CHƯA từng công bố cho các model đó trên văn bản pháp luật Việt Nam.

Cột `chunks.embedding` là `vector(1024)` cố định (`migrations/001_init.sql`) — model trả về chiều khác 1024 KHÔNG nhét được. Script dò chiều thật của từng model bằng một lệnh gọi API rẻ TRƯỚC khi embed cả corpus; model chiều khác bị BỎ QUA có báo cáo, KHÔNG bị truncate/pad (làm vậy là bịa dữ liệu), và không làm dừng các model còn lại trong sweep.

## Bảng so sánh

| Model | Chiều | $/1M token | Chunks | Token | Chi phí | Recall@5 | MRR@5 | nDCG@5 | Ghi chú |
|---|---|---|---|---|---|---|---|---|---|
| baai/bge-m3 | 1024 | 0.01 | 3283 | 883935 | $0.0 | 0.6753 | 0.511 | 0.5507 | đã có sẵn trong DB — không embed lại |
| openai/text-embedding-3-small | 1536 | — | — | — | — | — | — | — | **BỎ QUA**: không so được vì chiều 1536 ≠ 1024 (chunks.embedding vector(1024) cố định) |
| qwen/qwen3-embedding-8b | 4096 | — | — | — | — | — | — | — | **BỎ QUA**: không so được vì chiều 4096 ≠ 1024 (chunks.embedding vector(1024) cố định) |
| google/gemini-embedding-001 | 3072 | — | — | — | — | — | — | — | **BỎ QUA**: không so được vì chiều 3072 ≠ 1024 (chunks.embedding vector(1024) cố định) |
| voyageai/voyage-4-lite | 1024 | 0.02 | 3283 | 883935 | $0.0177 | 0.8442 | 0.6539 | 0.6959 | embed mới |

Tổng chi phí embed thật đã tiêu trong lần so sánh này: **$0.0177**.

Model tốt nhất theo Recall@5 trong lần đo này: `voyageai/voyage-4-lite` (0.8442).

Đo tại commit `0fefd9f0cc96a19f70378bdc585d7276d3ef9b55`.
