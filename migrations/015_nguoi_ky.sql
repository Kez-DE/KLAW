-- Người ký ban hành văn bản — hai cột, lấy MIỄN PHÍ từ dữ liệu đã tải.
--
-- ── Vì sao "miễn phí" ────────────────────────────────────────────────────────
-- `scripts/fetch_moj` đã tải toàn bộ response của 47 văn bản tầng sâu về
-- `data/raw/moj/*.json`, và mỗi response mang sẵn `documentIssues[]`:
--
--   {"agencyName": "Chính phủ", "personName": "Nguyễn Xuân Phúc",
--    "jobTitleName": "Thủ tướng", "orderIndex": 1}
--
-- `scripts/build_seed` đọc `agencyName` (→ `co_quan_ban_hanh`) rồi bỏ qua hai
-- trường còn lại. Lấy lại chúng là 0 request phát sinh tới MOJ — chỉ đọc lại
-- file đã có trên đĩa. Đo được: 47/47 văn bản có `personName`; 46 văn bản có
-- đúng một mục, 1 văn bản (13/2023/NĐ-CP) có hai mục TRÙNG người, khác cách
-- viết hoa và độ dài chức danh.
--
-- ── Vì sao HAI cột chứ không một chuỗi ghép ──────────────────────────────────
-- "Thủ tướng — Nguyễn Xuân Phúc" là một quyết định TRÌNH BÀY. Ghép ở tầng dữ
-- liệu thì mọi bên tiêu thụ về sau phải tách lại bằng chuỗi, và ký tự phân cách
-- sẽ trở thành một hợp đồng ngầm không ai viết ra.
--
-- ── Vì sao NULL được phép, và nghĩa của nó ───────────────────────────────────
-- 79/126 văn bản trong `documents` chỉ có metadata (`depth='metadata'`, nạp từ
-- `relationships.parquet` bởi `load_incoming_edges`); parquet không có trường
-- người ký nào. NULL ở đó nghĩa là KHÔNG BIẾT, không phải "không có người ký" —
-- cùng quy ước với `co_quan_ban_hanh`, cũng NULL trên đúng 79 dòng đó.
--
-- ── Idempotent ───────────────────────────────────────────────────────────────
-- `run_migrations()` chạy MỌI file mỗi lần khởi động. File này thuần DDL nên
-- `IF NOT EXISTS` là đủ. Nó KHÔNG nạp dữ liệu: `scripts/nap_nguoi_ky.py` làm
-- việc đó bằng UPDATE, cố ý KHÔNG qua `scripts/ingest`.
--
-- Vì sao không qua ingest: `ingest` bỏ qua mọi document có `checksum` không đổi,
-- và checksum băm HTML + dòng provisions — thêm một cột metadata không làm nó
-- đổi, nên ingest sẽ bỏ qua cả 47 văn bản. Ép nó chạy lại thì càng tệ: nó
-- `DELETE FROM documents` trước khi chèn, và CASCADE của khoá ngoại sẽ xoá sạch
-- `provisions` (đổi toàn bộ id) LẪN 4 dòng `sua_doi_dieu_khoan` neo vào chúng.
-- Một cột hiển thị không đáng để trả cái giá đó.

ALTER TABLE documents ADD COLUMN IF NOT EXISTS nguoi_ky TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS chuc_danh_nguoi_ky TEXT;

-- Chuỗi rỗng KHÔNG được phép: "" và NULL đọc giống hệt nhau trên giao diện
-- nhưng khác nhau ở tầng truy vấn (`IS NULL` bắt một cái, bỏ cái kia), và một
-- loader ghi "" khi không tìm thấy tên sẽ tạo ra một tầng "không biết" thứ hai
-- mà không bảng nào ghi lại là nó tồn tại.
ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_nguoi_ky_khong_rong_check;
ALTER TABLE documents ADD CONSTRAINT documents_nguoi_ky_khong_rong_check CHECK (
    (nguoi_ky IS NULL OR btrim(nguoi_ky) <> '')
    AND (chuc_danh_nguoi_ky IS NULL OR btrim(chuc_danh_nguoi_ky) <> '')
);
