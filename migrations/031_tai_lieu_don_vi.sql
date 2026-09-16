-- Quyết định 2026-09-16 `docs/decisions/2026-09-16-luu-bieu-dien-tai-lieu-theo-hoi-thoai.md`
-- — lưu BIỂU DIỄN ĐÃ ĐỌC của tài liệu theo hội thoại.
--
-- Trước migration này `don_vi` (các đơn vị văn bản kèm trang, toạ độ bảng,
-- nguồn chữ, độ tin OCR) chỉ sống trong bộ nhớ của request tải lên. Đủ cho việc
-- điền một biểu mẫu có checklist, nhưng lượt hỏi kế tiếp không còn gì để neo
-- vào — và đó chính là thứ chặn mọi tài liệu ngoài 29 loại có sẵn.
--
-- Hai giới hạn của quyết định nằm ngay ở hình dạng cột:
--
-- 1. JSONB chữ + vị trí, KHÔNG phải bytes, KHÔNG phải OOXML. FR-022 vẫn đúng
--    nguyên văn: tệp gốc không được lưu. Hệ quả có chủ đích: sửa tài liệu "giữ
--    nguyên bố cục" (documen.md GĐ3) nằm ngoài phạm vi cho tới khi có một
--    quyết định lưu OOXML riêng.
-- 2. Không có bảng mới, không có phạm vi tài khoản. Nội dung tài liệu thường
--    mang dữ liệu cá nhân của bên thứ ba chưa từng dùng KLAW, nên nó sống đúng
--    bằng đời cuộc hội thoại: `hoi_thoai_id ... ON DELETE CASCADE` của
--    migration 026 dọn nó, và `tai_lieu.xoa_theo_hoi_thoai` dọn cả đường xoá
--    MỀM (FR-024, FR-027).
--
-- `mo_ta` là một câu mô hình đọc ra tài liệu này là gì — cột cạnh `don_vi` vì
-- nó chỉ có nghĩa khi có `don_vi`, và mất cùng lúc với `don_vi`.
--
-- Cả hai cột nullable: dòng cũ (`can_chon_loai`, hoặc đã rút dữ kiện xong từ
-- trước) vẫn hợp lệ với `don_vi IS NULL`, và mọi truy vấn mới lọc chúng ra
-- bằng chính điều kiện đó thay vì bịa một giá trị mặc định.
ALTER TABLE viec_doc_tai_lieu
    ADD COLUMN IF NOT EXISTS don_vi JSONB,
    ADD COLUMN IF NOT EXISTS mo_ta  TEXT;
