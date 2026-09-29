-- Quyết định 2026-09-28 `docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md`
-- mục 9 — bản PDF ĐÃ KÝ chính thức (nút "Bản gốc có chữ ký (PDF)") và ảnh xem trước
-- trang 1 của nó.
--
-- `link_pdf_ban_ky`: chỉ tệp trên `datafiles.chinhphu.vn` (nơi vanban.chinhphu.vn
-- để bản ký số). Ràng buộc ở tầng DB, cùng hạng `ck_anh_tai_lieu_kich_thuoc` (035): một
-- script nạp tay hay một endpoint sau này không mở được cửa cho host khác.
--
-- `anh_van_ban`: MỘT ảnh PNG trang 1 mỗi văn bản, nên khoá chính là `doc_id`. Bảng riêng
-- chứ không cột bytea trên `documents` (cùng lý lẽ 035): mọi truy vấn đọc `documents`
-- — liệt kê, tìm kiếm, phán quyết hiệu lực toàn kho — không kéo vài trăm KB ảnh qua dây.
-- `so_byte` là cột riêng để đọc kích thước không phải kéo bytes; trần 300 KB/ảnh và
-- `octet_length(png) = so_byte` giữ ở DB. Xoá văn bản thì ảnh đi theo (CASCADE).
--
-- Idempotent: ADD COLUMN IF NOT EXISTS mang CHECK inline (cột đã có thì cả mệnh đề bỏ
-- qua), CREATE TABLE IF NOT EXISTS với CHECK inline.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS link_pdf_ban_ky TEXT
    CONSTRAINT ck_documents_link_pdf_ban_ky
    CHECK (link_pdf_ban_ky IS NULL OR link_pdf_ban_ky LIKE 'https://datafiles.chinhphu.vn/%');

CREATE TABLE IF NOT EXISTS anh_van_ban (
    doc_id   TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    png      BYTEA NOT NULL,
    so_byte  INTEGER NOT NULL,
    rong     INTEGER,
    cao      INTEGER,
    tao_luc  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_anh_van_ban_kich_thuoc
        CHECK (so_byte > 0 AND so_byte <= 307200 AND octet_length(png) = so_byte)
);
