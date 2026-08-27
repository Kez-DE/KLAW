-- Thêm cấp `tieu_muc` (Tiểu mục) vào CHECK của provisions.cap.
--
-- Lý do: đã đếm class thật trên HTML của cả 21 văn bản — `prov-subsection`
-- xuất hiện 43 lần (22 Tiểu mục của Bộ luật Dân sự) nhưng không có trong
-- CLASS_TO_CAP lẫn CHECK constraint, nên 22 Tiểu mục mất trắng.
-- Thứ tự cây: phan > chuong > muc > tieu_muc > dieu > khoan > diem.
--
-- KHÁC pattern của 001_init.sql một điểm: constraint này ĐÃ TỒN TẠI với định
-- nghĩa CŨ, nên `ADD CONSTRAINT` sẽ ném duplicate_object và `EXCEPTION ... NULL`
-- sẽ âm thầm GIỮ LẠI bản cũ. Phải DROP trước. Vẫn idempotent: DROP IF EXISTS
-- chạy được cả trên DB mới và DB đã có constraint.
ALTER TABLE provisions DROP CONSTRAINT IF EXISTS provisions_cap_check;

DO $$ BEGIN
    ALTER TABLE provisions ADD CONSTRAINT provisions_cap_check
        CHECK (cap IN ('phan', 'chuong', 'muc', 'tieu_muc', 'dieu', 'khoan', 'diem'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
