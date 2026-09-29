-- Quyết định 2026-09-28 `docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md`
-- mục 12 — một cạnh hiệu lực ĐÃ ĐỐI CHIẾU với nguyên văn chính thống. Một dòng ở đây
-- nói: cạnh `reference_id` đúng, và điều khoản `dieu_khoan` cùng câu trích `trich`
-- (mở tại `url`) là bằng chứng. `effectivity` không hạ cạnh như vậy bằng phép chặn
-- "khác chủ đề" (`cung_chu_de`), vì bằng chứng là chữ của văn bản, không phải tiêu đề.
--
-- Vì sao khoá là `reference_id` mà seed lại khoá bằng số hiệu: `load_incoming_edges`
-- xoá rồi chèn lại MỌI cạnh loai 20..23 ở mỗi lượt nạp, nên id cạnh không bền. Seed
-- `data/seed/canh_doi_chieu.yaml` khoá bằng (số hiệu đi, số hiệu đến, loai) và
-- `scripts/nap_canh_doi_chieu.py` phân giải ra id ở mỗi lần nạp; ON DELETE CASCADE
-- để một cạnh bị xoá không để lại bằng chứng mồ côi cho một cạnh không còn.
--
-- `trich` ≤ 400 ký tự: một câu trích làm bằng chứng, không phải bản sao văn bản.
-- `url` https: link người đọc mở được (Công báo, vanban.chinhphu.vn, vbpl.vn...).
--
-- Idempotent như mọi migration ở đây (`src/main.py::MIGRATIONS_KHOI_DONG` chạy lại
-- ở mỗi lần khởi động): CREATE TABLE IF NOT EXISTS, CHECK khai inline.
CREATE TABLE IF NOT EXISTS canh_doi_chieu (
    reference_id BIGINT PRIMARY KEY REFERENCES "references"(id) ON DELETE CASCADE,
    dieu_khoan   TEXT NOT NULL,
    trich        TEXT NOT NULL CHECK (length(trich) <= 400),
    url          TEXT NOT NULL CHECK (url LIKE 'https://%'),
    kiem_boi     TEXT NOT NULL,
    kiem_luc     TIMESTAMPTZ NOT NULL
);
