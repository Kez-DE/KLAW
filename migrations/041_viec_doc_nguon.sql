-- Quyết định 2026-09-29 `docs/decisions/2026-09-29-the-thuc-moi-ban-thao.md` mục 5 và
-- thiết kế `docs/plans/active/khuon-mau-thiet-ke.md` §3 — bản thảo KLAW dựng từ một
-- KHUÔN MẪU được lưu như một tệp tải lên (một dòng `viec_doc_tai_lieu` + `khuon_goc`),
-- để mọi route của khuôn gốc (trang, ô điền, tải về, lùi) chạy không đổi. Cột này nói
-- dòng nào là tài liệu NGƯỜI DÙNG tải lên (`tai_len`) và dòng nào là khuôn mẫu KLAW
-- dựng (`khuon_mau`): danh sách tài liệu của hội thoại, tài liệu router thấy và hạn
-- mức tài liệu mỗi ngày chỉ đếm `tai_len`.
--
-- Idempotent như 040: ADD COLUMN IF NOT EXISTS mang CHECK inline (cột đã có thì cả
-- mệnh đề bỏ qua). Mặc định hằng không viết lại bảng (Postgres 11+); mọi dòng có sẵn
-- là tệp tải lên.
ALTER TABLE viec_doc_tai_lieu ADD COLUMN IF NOT EXISTS nguon TEXT NOT NULL DEFAULT 'tai_len'
    CONSTRAINT ck_viec_doc_nguon CHECK (nguon IN ('tai_len', 'khuon_mau'));
