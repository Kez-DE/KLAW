-- Quyết định 2026-09-30 `docs/decisions/2026-09-30-tra-loi-tu-nhien-va-phan-tich.md`
-- mục 9 (chủ dự án chốt 2026-09-30) — điều khoản BỊ BÃI BỎ bởi một văn bản khác.
--
-- Một dòng nói: điều khoản `provision_id` (Điều/Khoản/Điểm, cùng mọi hậu duệ của nó)
-- hết hiệu lực từ `tu_ngay`, do `boi_dieu_khoan` của văn bản `boi_document_id` quy định;
-- `trich` là nguyên văn câu đó (các mảnh nối " … "), mở tại `url`. `effectivity` là nơi
-- phán nó đã tới ngày chưa; `hien_thi` ẩn điều khoản đã tới ngày khỏi truy hồi, trích dẫn
-- và thân trang văn bản, phần còn lại của văn bản vẫn hiện.
--
-- Bảng riêng, không phải thêm một loại vào `sua_doi_dieu_khoan` (014): mọi đường đọc 014
-- (Mức 4, `expand` bước 0, cạnh VBHN của `load_incoming_edges`) đọc dòng của nó là "bị sửa
-- bởi"; một dòng bãi bỏ lẫn vào đó sẽ được hiện là sửa đổi và kéo "điều khoản đi sửa" vào
-- căn cứ.
--
-- Dữ liệu: `data/seed/bai_bo_dieu_khoan.yaml` (`scripts/trich_bai_bo.py` đọc từ nguyên văn),
-- nạp bằng `scripts/nap_bai_bo_dieu_khoan.py`, khoá bằng (văn bản, `duong_dan`) nên nạp lại
-- được sau một lượt `ingest` đổi id điều khoản (CASCADE xoá dòng cũ). Idempotent như mọi
-- migration ở đây (`src/main.py::MIGRATIONS_KHOI_DONG`).
CREATE TABLE IF NOT EXISTS bai_bo_dieu_khoan (
    provision_id    BIGINT NOT NULL REFERENCES provisions(id) ON DELETE CASCADE,
    boi_document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    boi_dieu_khoan  TEXT NOT NULL CHECK (btrim(boi_dieu_khoan) <> ''),
    trich           TEXT NOT NULL CHECK (length(trich) BETWEEN 1 AND 2000),
    url             TEXT NOT NULL CHECK (url LIKE 'https://%'),
    tu_ngay         DATE NOT NULL,
    kiem_boi        TEXT NOT NULL,
    kiem_luc        TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (provision_id, boi_document_id)
);
