-- Plan 4 hardening — ba cổng trước ví tiền + một tầng giảm chấn.
--
-- Bối cảnh ĐO ĐƯỢC trên chính DB này (không phải giả thuyết):
--   * `/tra-cuu` gọi LLM tối đa 5 lần; p50 10.000ms, p95 50.289ms
--     (`percentile_disc` trên 204 dòng traces của endpoint đó)
--   * request đắt nhất đã ghi nhận: $0,00735
--   * ngày cao nhất tới nay: 118 request / $0,18329 (2026-08-30)
--   * dự án ĐÃ gặp HTTP 429 từ OpenRouter khi nhiều tiến trình chạy song song
-- Mở endpoint ra công khai nguyên trạng thì một vòng `curl` rút cạn key trong
-- một buổi. Ba bảng/cột dưới đây là cái chặn việc đó.
--
-- `010` SỞ HỮU `answer_cache`, `rate_limit_luot`, `traces.cache_hit` và
-- `ix_traces_ts` — và chỉ nó, theo quy tắc "một object, một owner, file mới
-- nhất" mà `002:17` đặt ra và `005`/`007`/`008`/`009` đã tuân.

-- ── Cache câu trả lời ───────────────────────────────────────────────────────
-- Postgres, KHÔNG Redis: dự án sẽ scale worker khi deploy thật, và một cache
-- in-process là N cache khác nhau trên N worker — N lần chi phí, và N câu trả
-- lời có thể lệch nhau cho cùng một câu hỏi.
--
-- `khoa` = sha256 của (câu hỏi đã chuẩn hoá | config_name | as_of_date |
-- corpus_checksum). Hash chứ không phải khoá tổ hợp bốn cột, vì `query` cho
-- phép tới 2.000 ký tự và 2.000 ký tự tiếng Việt là ~6.000 byte UTF-8 — vượt
-- trần ~2.704 byte của một dòng index btree, tức INSERT sẽ NỔ đúng trên câu
-- hỏi dài. Bốn thành phần vẫn được lưu nguyên (`cau_hoi_chuan`, `config_name`,
-- `as_of_date`, `corpus_checksum`) để một dòng cache đọc được bằng mắt: một
-- cache phục vụ câu trả lời PHÁP LÝ mà không audit được là một hộp đen.
--
-- `as_of_date` NOT NULL — được GIẢI QUYẾT trước khi vào khoá
-- (`config.as_of_hieu_luc`: request → settings → hôm nay). Nếu để NULL nghĩa
-- là "hôm nay", hai request cách nhau một đêm sẽ dùng CHUNG một dòng cache
-- trong khi "hôm nay" đã khác — tức trả về hiệu lực của ngày hôm trước.
CREATE TABLE IF NOT EXISTS answer_cache (
    khoa            TEXT PRIMARY KEY,
    cau_hoi_chuan   TEXT NOT NULL,
    config_name     TEXT NOT NULL,
    as_of_date      DATE NOT NULL,
    corpus_checksum TEXT NOT NULL,
    tra_loi         JSONB NOT NULL,
    tao_luc         TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- TTL quét theo `tao_luc` ở MỌI lượt đọc và dọn ở mỗi lượt ghi.
CREATE INDEX IF NOT EXISTS ix_answer_cache_tao_luc ON answer_cache(tao_luc);

-- ── Rate limit — bộ đếm trong Postgres, một dòng một lượt ───────────────────
-- Cửa sổ TRƯỢT (đếm các dòng trong `now() - cửa sổ`), không phải cửa sổ cố
-- định theo phút: cửa sổ cố định cho phép gấp đôi hạn mức quanh mốc chuyển
-- phút. `ip` là TEXT chứ không INET — giá trị có thể là nhãn
-- `khong-xac-dinh` khi ASGI scope không mang `client` (ép INET thì dòng đó
-- nổ ngay tại tầng đang bảo vệ hệ thống).
CREATE TABLE IF NOT EXISTS rate_limit_luot (
    id   BIGSERIAL PRIMARY KEY,
    ip   TEXT NOT NULL,
    ts   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_rate_limit_luot_ip_ts ON rate_limit_luot(ip, ts);

-- ── Trần chi phí ngày đọc từ `traces` ───────────────────────────────────────
-- KHÔNG dựng bộ đếm chi phí thứ hai: `traces` đã ghi chi phí THẬT từng request
-- (`cost_usd`, cộng từ 5 điểm gọi LLM — xem `_tong_hop_traces`). Một bộ đếm
-- song song sẽ lệch khỏi nó và không cách nào biết bên nào đúng.
CREATE INDEX IF NOT EXISTS ix_traces_ts ON traces(ts);

-- `cache_hit` — cờ phân biệt lượt phục vụ TỪ CACHE khỏi lượt gọi LLM thật.
-- Bắt buộc cho chương đánh giá: một cache hit có latency ~10ms và cost $0;
-- trộn chung cột với lượt thật (p50 10s) sẽ kéo p50 latency và chi phí trung
-- bình xuống một cách vô nghĩa, và bảng số liệu của khoá luận thành số của
-- cache. NOT NULL DEFAULT false: 259 dòng đã có đều là lượt gọi thật, nên
-- `false` là giá trị ĐÚNG cho chúng — không phải một mặc định bịa ra.
ALTER TABLE traces ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN NOT NULL DEFAULT false;
