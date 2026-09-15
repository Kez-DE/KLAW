-- Spec 2026-09-15c — trạng thái `can_chon_loai`.
--
-- Hệ thống tự nhận ra loại văn bản từ dòng tiêu đề. Khi KHÔNG nhận ra, nó nói
-- ra điều đó thay vì đoán bừa: đoán sai loại nghĩa là rút sai bộ trường, và
-- người dùng nhìn một bảng dữ kiện sai mà không hiểu vì sao. Cùng nguyên tắc
-- `abstain` của phần trả lời — thà hỏi một câu còn hơn sai im lặng.
ALTER TABLE viec_doc_tai_lieu DROP CONSTRAINT IF EXISTS ck_viec_doc_trang_thai;
ALTER TABLE viec_doc_tai_lieu ADD CONSTRAINT ck_viec_doc_trang_thai
    CHECK (trang_thai IN ('dang_doc', 'can_chon_loai', 'xong', 'hong', 'huy'));
