# Lưu khuôn gốc theo hội thoại và điền tại chỗ

Date: 2026-09-26

## Status

Accepted. Thay thế một phần `2026-09-16-luu-bieu-dien-tai-lieu-theo-hoi-thoai.md`
(lệnh cấm lưu bytes tệp gốc) và mục 3 của
`2026-09-18-trung-thuc-bieu-mau-va-media.md` (cấm lưu bytes tệp gốc và OOXML),
chỉ trong phạm vi **khuôn gốc** định nghĩa ở `CONTEXT.md`. Mọi phần khác của hai
quyết định đó giữ nguyên chữ.

## Context

Chủ dự án, 2026-09-26: "khi đưa lên 1 file pdf, docx, doc bảo agent hiểu, đọc hiểu
toàn bộ và render lại phải y hệt như bản upload lên … giới hạn số trang A4 là 10
trang".

Quyết định 2026-09-18 đã tự ghi trần của nó: không giữ OOXML thì vị trí chỉ suy
lại, và bản thảo đi qua mô hình không bao giờ trung thực bằng bản sao khuôn. Đo
ngày 2026-09-26 xác nhận trần đó là nguyên nhân gốc của cả hai lỗi chủ dự án thấy:

- Mô hình viết lại mọi khối (`schema_hieu`, `van_ban.muc`), rồi định dạng, giãn
  cách, căn lề và bảng được gắn lại bằng tra **nguyên văn**
  (`hieu_tai_lieu.py:1214-1332`, `_khop_bang`). Một chữ bị diễn đạt lại là mất
  định dạng; một bảng không khớp ô bị ép viền đều và hàng đầu tô nền.
- `clauses_tu` (`dung_ban_thao_tong_quat.py:92-106`) làm rơi `trang` và `anh`,
  nên mọi bản thảo hiện trên một tờ.
- Số trang đọc từ ngắt trang khai báo đếm thiếu: Evaluation Form 4 trang thật,
  đọc ra 1; Report_instruction 3, đọc ra 1.

Thử nghiệm trên bản sao 8 biểu mẫu thật của chủ dự án: đọc rồi ghi lại
`word/document.xml` (giữ nguyên khai báo namespace gốc) cho số trang và từng trang
dựng bằng LibreOffice trùng tới từng điểm ảnh với tệp gốc; điền một chỗ trống giữ
định dạng của run. `libreoffice-writer` đã có trong image (Phase 13, `.doc`).

## Decision

1. **Lưu khuôn gốc.** Tệp tải lên được giữ theo hội thoại: `.docx`, `.doc` giữ
   dưới dạng `.docx` đã quy đổi, hoặc PDF. Bảng riêng, khoá ngoại tới
   `viec_doc_tai_lieu` với `ON DELETE CASCADE`, nên bị **xoá cứng** cùng hội thoại
   như `anh_tai_lieu`. Khuôn gốc không vào log, trace, hồ sơ tài khoản, bộ nhớ dài
   hạn hay dataset; chịu nguyên FR-023, FR-025, FR-026, FR-027, FR-028.
2. **Trần 10 trang, đếm bằng dàn trang thật**: số trang LibreOffice dựng cho
   docx, số trang của PDF. Tài liệu vượt trần bị từ chối lúc tải lên và không trừ
   vào hạn mức tài liệu mỗi ngày. Tài liệu trong trần được gửi trọn cho mô hình,
   không cắt ngầm.
3. **Một đường cho bản thảo trên tài liệu có khuôn gốc**: mô hình chỉ trả về
   **phép sửa** gắn với đơn vị văn bản — điền chỗ trống, thay đoạn, chèn đoạn, xoá
   đoạn — và KLAW áp chúng lên chính khuôn gốc, giữ định dạng của đoạn. Mô hình
   không viết lại văn bản. Dãy chấm được thay bằng giá trị; chỗ trống không có giá
   trị giữ nguyên dãy chấm và được liệt kê trong chat. Ngoại lệ có tên: đường
   checklist (người dùng chọn loại văn bản) vẫn soạn **mẫu của KLAW** từ dữ kiện,
   vì kết quả đó là một văn bản khác, không phải bản sao của tệp tải lên.
4. **Hiển thị bằng chính tệp**: "Bản tải lên" và bản đã điền được dựng
   LibreOffice → PDF → ảnh từng trang, giữ khổ giấy gốc (Letter vẫn là Letter).
5. **Tải xuống**: `.docx` đã điền kèm PDF cho đầu vào docx hoặc `.doc`; PDF đã
   điền cho đầu vào PDF (chữ đặt đúng toạ độ; PDF scan định vị bằng OCR).
6. Lượt soạn trên khuôn gốc **không gộp vào hồ sơ tài khoản**.

Tài liệu tải lên trước quyết định này không có khuôn gốc và đi tiếp đường HTML cũ.

## Alternatives Considered

1. Giữ lệnh cấm và làm dày biểu diễn thêm (hộp văn bản, vị trí tuyệt đối). Loại:
   trần đã được đo, và phân trang trên trình duyệt chỉ xấp xỉ Word.
2. Dựng docx phía trình duyệt bằng thư viện JS. Loại: phân trang xấp xỉ, không
   đọc `.doc`, không có PDF chuẩn, và vẫn cần lưu tệp.
3. Quy đổi PDF sang docx rồi đi chung đường docx. Loại: bảng phức tạp lệch sau
   quy đổi; ghi đè đúng toạ độ giữ trang gốc nguyên vẹn.

## Consequences

Positive:

- Phần không bị sửa của văn bản giữ nguyên từng điểm ảnh; tải xuống mở bằng Word
  là chính khuôn gốc đã điền.
- Chi phí mô hình giảm: đầu ra là danh sách phép sửa, không phải cả văn bản.

Tradeoffs:

- **Dữ liệu cá nhân của bên thứ ba được lưu** (tên, con dấu, chữ ký trong tệp).
  Hàng rào duy nhất là xoá cứng theo hội thoại cộng các FR riêng tư ở trên.
- **LibreOffice không phải Word.** Trang dựng trên máy chủ dùng phông thay thế
  cùng kích thước (Liberation, Carlito, Caladea); mức lệch so với Word được đo và
  khai, không hứa trước.
- Mỗi lần tải lên và mỗi lần lưu tốn một lượt LibreOffice (khoảng 1–2 giây, 3 lượt
  đồng thời), dùng chung với quy đổi `.doc`.
- PDF không dàn lại được: trên PDF chỉ điền chỗ trống và thay chữ trong đúng ô của
  nó; không chèn hay xoá đoạn. Định vị chỗ trống trên PDF scan là xấp xỉ.
- `ban_thao` và `luot_hoi_thoai` vẫn chỉ bị xoá mềm cùng hội thoại, nên phép sửa
  (gồm giá trị đã điền) còn trong DB như bản thảo hiện nay. Theo dõi ở issue riêng.

## Follow-Up

- Ghi chú dưới FR-022 và Key Entity "Tài liệu tải lên" của spec 2026-09-15 trỏ về
  quyết định này.
- Sửa lời hứa "Tệp gốc không được lưu" trong menu đính kèm cùng lần phát hành.
- Issue: xoá hội thoại chỉ xoá mềm `ban_thao` và `luot_hoi_thoai`.
- Thước đo: số trang và so ảnh từng trang so với Word, trên 8 biểu mẫu của chủ
  dự án.
