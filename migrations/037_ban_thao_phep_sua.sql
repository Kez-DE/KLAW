-- Quyết định 2026-09-26 `docs/decisions/2026-09-26-luu-khuon-goc-va-dien-tai-cho.md`
-- (mục 3) — bản thảo trên một tài liệu có KHUÔN GỐC không mang văn bản do mô hình
-- viết lại, mà mang PHÉP SỬA (`phep_sua`) áp lên chính khuôn gốc của việc đọc
-- `viec_id`. Hợp đồng Storage của `docs/plans/active/khuon-goc-dien-tai-cho.md`.
--
-- - `viec_id` NULL: bản thảo không có nguồn (và mọi bản thảo trước migration này)
--   đi tiếp đường HTML. `ON DELETE SET NULL`, không CASCADE: xoá việc đọc (xoá
--   hội thoại qua `tai_lieu.xoa_theo_hoi_thoai`) cắt bản thảo khỏi khuôn gốc đã bị
--   xoá cứng, còn bản thảo vẫn mở được như văn bản — nó chỉ bị xoá mềm cùng hội
--   thoại như hôm nay (issue #3).
-- - `phep_sua` là danh sách phép ĐẦY ĐỦ của phiên bản đang sống; mỗi snapshot
--   trong `phien_ban_truoc` mang bản của nó, nên không cần bảng phiên bản riêng.
-- - Chỉ mục một phần trên `viec_id`: `SET NULL` phải tìm các bản thảo trỏ tới
--   việc đọc bị xoá; không có chỉ mục thì mỗi lần xoá hội thoại quét cả bảng.
--
-- Idempotent như mọi migration ở đây (`src/main.py::MIGRATIONS_KHOI_DONG` chạy
-- lại cả danh sách ở mỗi lần khởi động): `ADD COLUMN IF NOT EXISTS`, khoá ngoại
-- thêm trong khối DO chỉ khi `pg_constraint` chưa có nó.
ALTER TABLE ban_thao
    ADD COLUMN IF NOT EXISTS viec_id UUID NULL,
    ADD COLUMN IF NOT EXISTS phep_sua JSONB NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ban_thao_viec_id_fkey') THEN
        ALTER TABLE ban_thao ADD CONSTRAINT ban_thao_viec_id_fkey
            FOREIGN KEY (viec_id) REFERENCES viec_doc_tai_lieu(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_ban_thao_viec_id ON ban_thao (viec_id) WHERE viec_id IS NOT NULL;
