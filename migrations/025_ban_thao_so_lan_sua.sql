-- Spec 2026-09-09 §8.4 — bộ đếm lần sửa ĐƠN ĐIỆU của một bản thảo. Trần sửa trước đây đo
-- bằng `length(phien_ban_truoc)`, mà `lui` lại BỚT chính mảng đó: xen kẽ `lui` (miễn phí)
-- với `dung` (một lượt LLM trả phí) đặt lại trần và mở một vòng lặp tiêu tiền không chặn
-- được. Cột này chỉ do `sua()` tăng, không ai giảm — `lui` không đụng tới.
ALTER TABLE ban_thao ADD COLUMN IF NOT EXISTS so_lan_sua INTEGER NOT NULL DEFAULT 0;
