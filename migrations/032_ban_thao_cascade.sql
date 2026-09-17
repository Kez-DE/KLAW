-- Spec 2026-09-17 Phase 6 (D10) — một bản thảo chết theo cuộc hội thoại của
-- nó, khớp cách `viec_doc_tai_lieu` đã khai từ migration 026 thay vì kiểu
-- `SET NULL` mà `024` đặt.
--
-- KHÔNG đổi hành vi hôm nay: `hoi_thoai.xoa_mem` chỉ xoá MỀM (đặt `xoa_luc`),
-- nên ràng buộc FK không bao giờ nổ — chưa từng có một xoá THẬT hàng
-- `hoi_thoai` nào trong `src/`. Đổi ở đây là để LỜI KHAI BÁO không còn nói
-- ngược với `viec_doc_tai_lieu` (cùng bảng cha, cùng lý do FR-027/D10), và để
-- một lần xoá thật trong tương lai làm đúng việc thay vì âm thầm để lại một
-- bản thảo mồ côi — cùng bài học migration 026 đã nêu: đẩy bất biến vào
-- Postgres, không tin vào kỷ luật của người gọi.
ALTER TABLE ban_thao DROP CONSTRAINT IF EXISTS ban_thao_hoi_thoai_id_fkey;
ALTER TABLE ban_thao ADD CONSTRAINT ban_thao_hoi_thoai_id_fkey
    FOREIGN KEY (hoi_thoai_id) REFERENCES hoi_thoai(id) ON DELETE CASCADE;
