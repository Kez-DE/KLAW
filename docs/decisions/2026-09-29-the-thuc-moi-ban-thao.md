# Thể thức đầy đủ cho mọi bản thảo, hợp đồng đủ điều khoản bắt buộc, và câu hỏi về hệ thống pháp luật

Date: 2026-09-29

## Status

Accepted (chủ dự án chốt bốn phương án đề xuất, 2026-09-29).

## Context

Chủ dự án, 2026-09-29: "tất cả các văn bản soạn thảo tôi đều thấy thiếu CỘNG HOÀ XÃ
HỘI CHỦ NGHĨA VIỆT NAM, Độc lập - Tự do - Hạnh phúc, … ngày … tháng … năm …, thiếu rất
nhiều … thêm dữ liệu chính xác các hợp đồng soạn thảo, phải có đầy đủ"; và câu hỏi
"hiện tại pháp luật Việt Nam chia thành những gì" nhận về đoạn giới thiệu KLAW.

Đo 2026-09-29 (chỉ đọc):

- Bản thảo theo checklist (ví dụ đơn xin nghỉ việc) không có quốc hiệu, tiêu ngữ
  hay dòng địa danh, ngày tháng. Bản thảo tổng quát có đủ cả hai ở 16/38 bản, thiếu
  cả hai ở 15/38 — tuỳ model.
- Câu hỏi về hệ thống pháp luật được định tuyến `hoi_ve_kho` rồi rơi vào
  `gioi_thieu.cau_gioi_thieu`. Kho không có Luật Ban hành văn bản quy phạm pháp luật
  (64/2025/QH15) hay Hiến pháp, nên không có căn cứ để trả lời.
- Các checklist ghi Nghị định 30/2020/NĐ-CP chỉ áp cho cơ quan nhà nước; văn bản của
  doanh nghiệp tư và hợp đồng dân sự không bắt buộc theo nghị định đó, nhưng quốc
  hiệu, tiêu ngữ, số hiệu, địa danh ngày tháng là tập quán thể thức của mọi văn bản
  Việt Nam và có trong các mẫu chính thức do bộ ngành ban hành.

## Decision

1. **Mọi bản thảo KLAW sinh ra mang đủ thể thức theo loại văn bản** (checklist và
   tổng quát): văn bản hành chính theo Phụ lục I Nghị định 30/2020/NĐ-CP; hợp đồng,
   đơn và biểu mẫu theo mẫu chính thức của bộ ngành khi có (tra trên trang .gov.vn,
   ghi nguồn). Thể thức do mã dựng từ dữ liệu cấu hình, không do model tự viết.
   **Khuôn gốc giữ nguyên 100%** — không thêm gì.
2. **Ô chưa biết để "…" đúng thể thức** ("…, ngày … tháng … năm …", "Số: …/…/HĐTTS");
   chỉ điền giá trị người dùng đã cho; người dùng bấm vào chỗ trống trên trang để
   điền, như khuôn gốc. Không tự điền ngày hôm nay, địa danh hay số văn bản.
3. **Hợp đồng đủ điều khoản bắt buộc theo luật điều chỉnh**, mỗi mục kèm căn cứ mở
   được (ví dụ BLLĐ Điều 21 cho hợp đồng lao động; BLDS Điều 398 và các điều của
   từng hợp đồng thông dụng); bổ sung mẫu cho các hợp đồng thông dụng chưa có (thuê
   tài sản, dịch vụ, vay tài sản, đặt cọc, mua bán tài sản…) khi căn cứ đã có toàn
   văn trong kho.
4. **Câu hỏi về hệ thống pháp luật được trả lời từ luật, có trích dẫn**: nạp sâu
   Hiến pháp 2013 (kèm văn bản sửa đổi còn hiệu lực) và Luật Ban hành văn bản quy
   phạm pháp luật 64/2025/QH15 (kèm 87/2025/QH15) — mở rộng ngoài 8 lĩnh vực của
   quyết định 2026-09-28 mục 4, cho nhóm "nền tảng". Định tuyến: hỏi về pháp luật
   Việt Nam thì tra luật; hỏi về KLAW hay kho thì trả số liệu kho; đoạn giới thiệu
   KLAW chỉ dành cho câu hỏi về chính KLAW.

## Alternatives Considered

1. Chỉ trả lời câu hỏi hệ thống pháp luật từ số liệu kho. Loại: kho không phải
   pháp luật Việt Nam (CONTEXT.md "kho"), người hỏi cần câu trả lời có căn cứ.
2. Liệt kê ngành luật theo học thuyết. Loại: không có điều luật để trích, trái cam
   kết trích dẫn kiểm chứng được.
3. Để model tự viết phần đầu văn bản. Loại: đo được 15/38 bản thiếu; thể thức là dữ
   liệu cố định theo loại văn bản, không phải việc sáng tác.
4. Tự điền ngày hôm nay và địa danh. Loại: văn bản người dùng đem đi ký; điền sẵn là
   KLAW khai thay người dùng.

## Consequences

- Bản thảo dài thêm phần đầu và phần cuối (nơi nhận, chữ ký); xuất Word/PDF phải
  đo lại tràn trang.
- Văn bản của doanh nghiệp tư mang quốc hiệu theo tập quán dù Nghị định 30/2020
  không bắt buộc — ghi rõ điều này ở ghi chú mẫu, không nói là luật đòi.
- Kho có thêm nhóm "nền tảng"; bộ đo phải chạy lại sau khi nạp.

## Follow-Up

- Plan: `docs/plans/active/the-thuc-va-he-thong-phap-luat.md`.
