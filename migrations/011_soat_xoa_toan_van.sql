-- Xoá toàn văn tài liệu người dùng khỏi 30 dòng `traces` của `/api/v1/soat`.
--
-- Vì sao đây là lỗi chứ không phải một lựa chọn lưu trữ. Hai endpoint, hai loại
-- dữ liệu:
--
--   /api/v1/tra-cuu     n=328  max_len=96         avg=39      <- câu người dùng HỎI
--   /api/v1/soan-thao   n=51   max_len=4          avg=4       <- chỉ `loai_van_ban`
--   /api/v1/soat        n=30   max_len=2.000.000  avg=66.793  <- TOÀN BỘ hợp đồng
--
-- `/tra-cuu.query` là câu hỏi của CHÍNH người dùng — ngắn, dữ liệu của họ, và
-- eval cần nguyên văn. GIỮ NGUYÊN, file này không đụng tới.
--
-- `/soat.text` là TÀI LIỆU của người dùng, và dữ liệu cá nhân trong đó thường
-- thuộc về NGƯỜI THỨ BA: người lao động có tên trong hợp đồng, số CCCD của họ,
-- mức lương của họ. Người đó chưa từng dùng KLAW và chưa đồng ý bất cứ điều gì
-- — không một ô checkbox nào trên giao diện xin phép được thay cho họ.
-- `routes.soat()` từ nay ghi `dau_van_ban(...)` (hash + độ dài + số clause) thay
-- cho `req.text`; file này dọn những dòng đã lưu trước khi có thay đổi đó.
--
-- KHÔNG XOÁ DÒNG, chỉ xoá NỘI DUNG: `result_type`, `cost_usd`, `latency_ms`,
-- các cột claim và model là dữ liệu đo lường của khoá luận và phải nguyên vẹn.
-- `UPDATE` dưới đây chỉ chạm đúng một cột `query`.
--
-- ── Vì sao dòng cũ KHÔNG có sha256 ──────────────────────────────────────────
-- Dòng mới mang `sha256` của dạng đã chuẩn hoá bằng `verify_tier1.normalize`
-- (NFC → gộp khoảng trắng → strip → Ð/ð→Đ/đ + bỏ zero-width). Bản SQL gần nhất
-- của phép đó là:
--   translate(btrim(regexp_replace(normalize(query, NFC), '\s+', ' ', 'g')),
--             'Ðð' || U&'\200B' || U&'\FEFF', 'Đđ')
-- ĐÃ ĐO trên đúng 30 dòng này: nó trùng hash Python ở **28/30 dòng**, lệch 2
-- (`\s` của POSIX trong Postgres không phủ cùng tập ký tự trắng Unicode như `\s`
-- của Python). Một hash sai 6,7% số dòng TỆ HƠN không có hash: người đọc bảng
-- sẽ so nó với hash của dòng mới và kết luận "không có tài liệu nào bị soát hai
-- lần" — một kết luận sai, im lặng. Nên dòng cũ ghi `sha256=khong_co`: nói
-- thẳng là không biết, thay vì bịa một số trông như biết.
-- `len` thì vẫn tính được chính xác từ dữ liệu đang có, nên giữ lại.
--
-- ── Idempotent ──────────────────────────────────────────────────────────────
-- `run_migrations()` chạy MỌI file mỗi lần khởi động, nên `UPDATE` này phải tự
-- chặn lần thứ hai — không có `WHERE ... NOT LIKE` thì lần chạy sau sẽ hash/đo
-- độ dài của CHÍNH CHUỖI DẤU vừa ghi, và `len` biến thành độ dài của cái dấu
-- chứ không phải của tài liệu. Cùng tinh thần với `008`: chạy hai lần phải cho
-- cùng kết quả, và bảng KHÔNG rỗng nên phép thử đó có nghĩa.

UPDATE traces
SET query = 'soat sha256=khong_co len=' || length(query) || ' clauses=khong_co'
WHERE endpoint = '/api/v1/soat'
  AND query IS NOT NULL
  AND query NOT LIKE 'soat sha256=%';
