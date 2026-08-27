-- Thêm cấp `phu_luc` vào CHECK của provisions.cap.
--
-- Lý do: đã đo phân bố chữ mồ côi so với thẻ prov-* CUỐI CÙNG của mỗi văn bản —
-- 152668: 42.636 ký tự ở đuôi / 647 xen giữa; 152670: 25.316 / 560;
-- 134611: 21.296 / 653. Tức 97–98% nằm sau thẻ prov-* cuối. Ranh giới là thật.
-- Chữ đuôi (Phụ lục, khối chữ ký) trước đây gắn vào provision đang mở, làm
-- `145/2020/NĐ-CP > Điều 115` phình lên 44.106 ký tự và thành neo trích dẫn sai
-- cho mọi câu lấy từ Phụ lục. Giờ nó là MỘT bản ghi `phu_luc` cho mỗi văn bản,
-- cấp KHÔNG trích dẫn được, parent_id NULL, so_hieu_cap ''.
--
-- Nhận diện bằng VỊ TRÍ, không bằng regex tiếng Việt — nên nó không phải một
-- special case của parser mà là một quy tắc về cấu trúc tài liệu.
--
-- Idempotent theo đúng pattern 002: constraint đã tồn tại với định nghĩa cũ nên
-- phải DROP trước, `EXCEPTION ... NULL` một mình sẽ âm thầm giữ bản cũ.
ALTER TABLE provisions DROP CONSTRAINT IF EXISTS provisions_cap_check;

DO $$ BEGIN
    ALTER TABLE provisions ADD CONSTRAINT provisions_cap_check
        CHECK (cap IN ('phan', 'chuong', 'muc', 'tieu_muc', 'dieu', 'khoan',
                       'diem', 'phu_luc'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
