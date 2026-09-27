-- Quyết định 2026-09-26 `docs/decisions/2026-09-26-luu-khuon-goc-va-dien-tai-cho.md`
-- — lưu KHUÔN GỐC: chính tệp khách tải lên (`.docx`, `.doc` giữ dưới dạng `.docx`
-- đã quy đổi, hoặc PDF), để "Bản tải lên" hiện đúng từng trang và bản điền được
-- áp lên chính tệp đó. Quyết định ấy thay một phần lệnh cấm lưu bytes tệp gốc của
-- 2026-09-16 và mục 3 của 2026-09-18, CHỈ trong phạm vi khuôn gốc.
--
-- Cùng khuôn `anh_tai_lieu` (035), cùng lý lẽ:
--
-- - BẢNG RIÊNG, không thêm cột vào `viec_doc_tai_lieu`: dòng việc đọc được đọc
--   ở mọi lượt hỏi (`lay_viec`, `tai_lieu_cua_hoi_thoai`), còn tệp chỉ cần khi có
--   người mở trang hoặc điền. Chỉ `tai_lieu.khuon_goc_cua` kéo `noi_dung` ra.
-- - MỘT khoá ngoại tới `viec_doc_tai_lieu` với `ON DELETE CASCADE`, không
--   `hoi_thoai_id`/`user_sub` riêng: xoá CỨNG hội thoại cascade qua 026, xoá MỀM
--   đi qua `tai_lieu.xoa_theo_hoi_thoai` (DELETE chính dòng việc đọc), xoá tài
--   khoản cascade `users` → `viec_doc_tai_lieu` (026) → đây. Chủ sở hữu đọc qua
--   JOIN — một nguồn sự thật cho quyền sở hữu.
-- - `viec_id` là KHOÁ CHÍNH: một việc đọc có đúng một tệp tải lên.
-- - `so_byte` là cột riêng, khoá bằng `octet_length(noi_dung)`, để thống kê đọc
--   được kích thước mà không kéo bytes ra khỏi Postgres. 20 MB là
--   `tai_lieu.TRAN_BYTE`; 10 trang là `tai_lieu.TRAN_TRANG` — trần ở tầng DB để
--   một script nạp tay hay một endpoint tương lai không mở lại được cửa này.
-- - `kho` là khổ TỪNG trang `[rộng_pt, cao_pt]` của bản dựng, nên độ dài mảng
--   bằng đúng `so_trang`.
--
-- PDF và PNG dựng từ tệp KHÔNG lưu: dựng lại khi cần (ponytail: thêm bảng đệm
-- khi một lần dựng đo được là quá chậm).
--
-- Idempotent như mọi migration ở đây (`src/main.py::MIGRATIONS_KHOI_DONG` chạy
-- lại toàn bộ danh sách ở mỗi lần khởi động): `CREATE TABLE IF NOT EXISTS`, ràng
-- buộc `CHECK` khai INLINE nên không có `ALTER TABLE ADD CONSTRAINT` nào chạy lần
-- thứ hai.
CREATE TABLE IF NOT EXISTS khuon_goc (
    viec_id     UUID PRIMARY KEY REFERENCES viec_doc_tai_lieu(id) ON DELETE CASCADE,
    dinh_dang   TEXT NOT NULL,
    noi_dung    BYTEA NOT NULL,
    so_byte     INTEGER NOT NULL,
    so_trang    INTEGER NOT NULL,
    kho         JSONB NOT NULL,
    tao_luc     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_khuon_goc_dinh_dang CHECK (dinh_dang IN ('docx', 'pdf')),
    CONSTRAINT ck_khuon_goc_so_byte
        CHECK (so_byte = octet_length(noi_dung) AND so_byte <= 20 * 1024 * 1024),
    CONSTRAINT ck_khuon_goc_so_trang CHECK (so_trang BETWEEN 1 AND 10),
    -- CASE chứ không AND: Postgres không hứa thứ tự tính của AND, và
    -- `jsonb_array_length` trên một vô hướng là lỗi chứ không phải `false`.
    CONSTRAINT ck_khuon_goc_kho
        CHECK (CASE WHEN jsonb_typeof(kho) = 'array' THEN jsonb_array_length(kho) = so_trang ELSE false END)
);
