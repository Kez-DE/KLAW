# Trung thực với biểu mẫu khách tải lên, và cho lưu media đã tách

Ngày: 2026-09-18

## Status

Accepted. Thay thế một phần bởi `2026-09-26-luu-khuon-goc-va-dien-tai-cho.md`
(lưu khuôn gốc theo hội thoại). Mục 3 (cấm lưu bytes
tệp gốc và OOXML) không còn áp cho khuôn gốc.

## Bối cảnh

Chủ dự án đặt lại mức yêu cầu cho đường tài liệu: khi khách tải lên một mẫu văn
bản, KLAW phải dựng lại **đúng** — đủ nội dung, đúng vị trí, đúng phông chữ và
kiểu, kể cả cấu trúc bảng và căn lề, mức mong muốn 99%.

Đo được trên `src/services/doc_tai_lieu.py` ngày 2026-09-18, bộ đọc hiện lấy:
chữ, trang, `w:tblGrid`, `w:gridSpan`, `can_le` theo đoạn. Grep toàn `src/`
KHÔNG thấy đọc: viền bảng (`w:tblBorders`, `w:tcBorders`), định dạng chữ
(`w:rPr`: đậm, nghiêng, gạch chân, cỡ, phông), thụt lề, tab, giãn dòng, lề
trang, chiều cao dòng (`w:trHeight`), và **không đọc ảnh**. Ba lớp dữ liệu
thiếu, không phải ba dòng mã thiếu.

Bốn lỗi chủ dự án chỉ ra cùng một gốc: một bảng KHÔNG VIỀN trong biểu mẫu Việt
Nam là **bố cục** (khối quốc hiệu, ô ký), nhưng KLAW vẽ mọi bảng có viền và tô
nền hàng đầu như bảng dữ liệu; và căn lề của chữ nằm trong ô bảng bị mất vì
`_can_le_theo_dong` (`hieu_tai_lieu.py:933`) chỉ tra theo đoạn văn độc lập.

Quyết định 2026-09-16 (`2026-09-16-luu-bieu-dien-tai-lieu-theo-hoi-thoai.md`)
cấm lưu bytes tệp gốc và OOXML, và tự ghi hệ quả: "giữ nguyên bố cục không nằm
trong phạm vi cho tới khi có quyết định lưu OOXML riêng". Yêu cầu mới đụng
thẳng vào câu đó.

## Quyết định

Chủ dự án chọn **làm dày biểu diễn, cộng media đã tách** — không lưu OOXML,
không lưu bytes tệp gốc.

1. Biểu diễn đã đọc được phép mang thêm: viền bảng và viền ô, chiều cao dòng,
   căn lề của chữ TRONG ô, định dạng chữ ở mức run (đậm, nghiêng, gạch chân,
   cỡ, tên phông), thụt lề, tab, giãn dòng và lề trang.
2. Media đã tách khỏi tệp (logo, con dấu, chữ ký ảnh) được lưu kèm hội thoại,
   cascade xoá theo hội thoại như biểu diễn, và chịu đúng FR-024/FR-027.
3. Vẫn CẤM: lưu bytes tệp gốc nguyên vẹn, lưu OOXML, và mọi đường đưa nội dung
   tài liệu vào hồ sơ tài khoản, bộ nhớ dài hạn, log, trace hay dataset.

Quyết định này **sửa hẹp** quyết định 2026-09-16: media đã tách là ngoại lệ
được gọi tên; hai lệnh cấm còn lại giữ nguyên chữ.

## Căn cứ

- Yêu cầu của chủ dự án 2026-09-18: "khi khách hàng đưa lên 1 mẫu văn bản phải
  render được chuẩn … kể cả cấu trúc bảng, cấu trúc đặt căn lề chính xác đến
  99%", và lựa chọn giữa ba mức trung thực trong cùng lượt trao đổi.
- Quyết định 2026-09-16, phần "Việc còn lại": mở quyết định riêng khi cần giữ
  bố cục. Đây là quyết định đó, ở mức hẹp hơn OOXML.
- Đo mã nguồn ngày 2026-09-18 nêu ở phần Bối cảnh.

## Hệ quả

Tích cực: khối quốc hiệu, ô ký, bảng bố cục và căn lề trong ô dựng lại được
đúng chuẩn văn bản hành chính; logo và con dấu hiện ra thay vì biến mất.

Đánh đổi, nói thẳng:

- **Trần thật thấp hơn 99%.** Không giữ OOXML thì vị trí tuyệt đối (hộp văn
  bản, khung, neo ảnh theo toạ độ trang, tab stop phức tạp, kiểu kế thừa từ
  `w:styles`) vẫn phải suy lại, không sao chép. Mức đạt được phải ĐO rồi khai,
  không hứa trước.
- **Bản thảo đi qua mô hình thì không bao giờ trung thực bằng bản sao khuôn.**
  Mô hình viết lại nội dung; chỉ đường nhân bản khuôn gốc mới giữ nguyên bố cục
  từng điểm ảnh, và đường đó cần OOXML — nằm ngoài quyết định này.
- **Media là dữ liệu cá nhân của bên thứ ba** (con dấu, chữ ký). Chặn bằng đúng
  hàng rào của biểu diễn: cascade xoá theo hội thoại, không vào log/trace, không
  vào hồ sơ tài khoản, không rời khỏi tài khoản đã tải lên.

## Việc còn lại

- Thước đo độ trung thực: bộ biểu mẫu mẫu + bảng chấm theo hạng mục (cấu trúc,
  căn lề, viền, định dạng chữ, media) để "99%" là con số đo được, không phải
  lời hứa.
- Ghi chú dưới FR-022 của spec 2026-09-15 trỏ về quyết định này.
- Nếu sau này vẫn cần vị trí tuyệt đối, mở quyết định riêng cho OOXML — lệnh
  cấm đó chưa được gỡ ở đây.
