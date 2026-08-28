-- PostgreSQL KHÔNG có text-search config 'vietnamese'.
-- Dùng 'simple' + unaccent: bỏ dấu rồi tách theo khoảng trắng.
-- Tách từ tiếng Việt (pyvi/underthesea) là tối ưu hóa sớm — chỉ thêm nếu đo
-- được Recall@k kém, và khi đó nó thành một dòng ablation.
--
-- Cột `chunks.tsv` và GIN index của nó (`ix_chunks_tsv`) đã do `001_init.sql`
-- tạo — file này KHÔNG đụng vào cột, chỉ thêm hàm + trigger tự cập nhật nó.
--
-- `klaw_tsv` khai báo IMMUTABLE dù thân hàm gọi `unaccent()` (mặc định STABLE
-- trong Postgres, vì volatility của nó phụ thuộc lý thuyết vào rule file mà
-- extension unaccent nạp). Ở đây khai báo IMMUTABLE là AN TOÀN vì: rule file
-- ('unaccent.rules') được nạp cố định lúc `CREATE EXTENSION unaccent` (xem
-- `000_extensions.sql`) và ứng dụng không bao giờ ALTER/reload nó lúc chạy —
-- với rule file cố định, cùng một chuỗi input luôn cho cùng một tsvector, tức
-- đúng định nghĩa IMMUTABLE trong thực tế vận hành của hệ thống này (không
-- phải trong lý thuyết tổng quát mọi cấu hình Postgres có thể có). Khai báo
-- tường minh IMMUTABLE là cách chuẩn để bỏ qua giới hạn "STABLE không được
-- dùng trong index hàm" (functional index) mà không cần viết lại unaccent()
-- bằng C. `006` không tự tạo thêm index nào trên `klaw_tsv(...)` — GIN index
-- có sẵn trên chính cột `tsv` đã đủ cho truy vấn BM25 — nhưng hàm vẫn cần khai
-- báo IMMUTABLE ngay từ đầu để không chặn đường một index hàm về sau.

CREATE OR REPLACE FUNCTION klaw_tsv(txt text)
RETURNS tsvector
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT to_tsvector('simple', unaccent(txt));
$$;

CREATE OR REPLACE FUNCTION chunks_tsv_trigger()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.tsv := klaw_tsv(NEW.noi_dung_embed);
    RETURN NEW;
END;
$$;

-- BEFORE INSERT OR UPDATE OF noi_dung_embed: bắt cả hai, không chỉ INSERT.
-- Task 6 ghi hàng loạt; nếu về sau UPDATE lại noi_dung_embed mà trigger chỉ
-- nghe INSERT thì tsv cũ bị bỏ quên — sai âm thầm, không lỗi, không test nào
-- bắt được ngoại trừ test chạy UPDATE thật (xem test_tsv.py).
DROP TRIGGER IF EXISTS chunks_tsv_update ON chunks;
CREATE TRIGGER chunks_tsv_update
    BEFORE INSERT OR UPDATE OF noi_dung_embed ON chunks
    FOR EACH ROW EXECUTE FUNCTION chunks_tsv_trigger();
