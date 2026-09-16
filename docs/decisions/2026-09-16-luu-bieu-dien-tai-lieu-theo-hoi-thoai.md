# Lưu biểu diễn văn bản đã đọc theo hội thoại, không lưu tệp gốc

Ngày: 2026-09-16

## Status

Accepted

## Bối cảnh

Spec 2026-09-15 (FR-022, SC-005) cấm lưu tệp gốc của người dùng sau khi xử lý,
và bản triển khai đầu chỉ giữ dữ kiện đã rút kèm đoạn trích. Điều đó đủ cho
việc điền biểu mẫu có checklist, nhưng không cho phép hỏi đáp về tài liệu ở
lượt sau: `don_vi` (các đơn vị văn bản đã đọc) chỉ sống trong bộ nhớ của request
tải lên.

`documen.md` §10.1 nêu bốn phương án và yêu cầu chủ dự án chốt trước khi viết
migration.

## Quyết định

Lưu **biểu diễn văn bản đã đọc** — danh sách đơn vị văn bản kèm trang, toạ độ
bảng, nguồn chữ và độ tin OCR — gắn vào `viec_doc_tai_lieu`, sống cùng cuộc hội
thoại và bị xoá cùng nó. **Không** lưu bytes tệp gốc, **không** lưu OOXML.

Hệ quả trực tiếp: sửa tài liệu "giữ nguyên bố cục" (documen.md GĐ3) không nằm
trong phạm vi cho tới khi có quyết định lưu OOXML riêng.

## Căn cứ

- documen.md §10.1, phương án 3 (lưu biểu diễn đã làm sạch) — thu hẹp thêm:
  không giữ OOXML, chỉ giữ chữ và vị trí.
- Spec 2026-09-15 FR-022 vẫn đúng nguyên văn: tệp gốc không được lưu. FR-024
  (xoá theo hội thoại) và FR-027 (không log nội dung) áp cho biểu diễn này.
- Quyết định của chủ dự án 2026-09-16 (vòng grill, câu 1).

## Bằng chứng

- Migration bổ sung cột JSONB nullable; ràng buộc `ON DELETE CASCADE` theo
  `hoi_thoai_id` đã có từ migration 026.
- Test: xoá hội thoại (kể cả xoá mềm) làm trống biểu diễn; người khác đọc trả
  404; log và traces không chứa nội dung.

## Hệ quả

Tích cực: hỏi đáp, phân tích, trích dữ kiện và đối chiếu luật hoạt động qua
nhiều lượt mà không phải tải lại tệp.

Đánh đổi: nội dung tài liệu — thường mang dữ liệu cá nhân của bên thứ ba — nằm
trong Postgres trong suốt đời cuộc hội thoại. Chặn bằng: cascade xoá theo hội
thoại, xoá mềm hội thoại cũng dọn biểu diễn, không chảy vào hồ sơ tài khoản hay
bộ nhớ dài hạn, không vào log/trace/dataset.

## Việc còn lại

- Ghi chú dưới FR-022 của spec 2026-09-15 trỏ về quyết định này.
- Nếu sau này cần "giữ nguyên bố cục", mở quyết định riêng cho OOXML.
