# Trích dẫn đầy đủ, liên kết nguồn chính thống và khối "Căn cứ" trong bản thảo

Date: 2026-09-28

## Status

Accepted. Thay thế một phần spec `docs/superpowers/specs/2026-09-06-soul-trich-dan-bam-duoc-design.md`:
quyết định Q2 (khối `{van_ban}` và `DocumentOut` không mang ngày ban hành, ngày
hiệu lực) và §4.3 (link cổng luật chỉ được hiển thị khi có người mở bằng trình
duyệt thật).

## Context

Chủ dự án, 2026-09-28: "hoàn thiện các văn bản pháp lý, đầy đủ, có trích dẫn: văn
bản này trích dẫn từ đâu, văn bản nào, phát hành ngày bao nhiêu, liên kết đầy đủ".
Sáu phương án (Q1–Q6) được chủ dự án chốt cùng ngày.

Kiểm kho ngày 2026-09-28 (chỉ đọc):

- 1.634 văn bản; 54 văn bản có toàn văn, khớp nguyên văn CSDL quốc gia của Bộ Tư
  pháp 8.609/8.609 điều khoản. 1.580 văn bản còn lại chỉ có tên, thiếu cơ quan ban
  hành, người ký và tình trạng hiệu lực.
- `link_vbpl` = 0/1.634. vbpl.vn không còn chặn bot; mẫu link người mở được là
  `https://vbpl.vn/van-ban/chi-tiet/{id}` (id của gateway Bộ Tư pháp chính là id
  của vbpl.vn). Mẫu cũ `…/vbpq-toanvan.aspx?ItemID=` chuyển hướng về trang chủ.
- Một trích dẫn hiện ra chỉ có số hiệu và đường dẫn nội bộ; không tên đầy đủ, cơ
  quan, ngày ban hành hay link. Bản thảo tải về không có phần "Căn cứ".

## Decision

1. **Nguồn chuẩn** cho nội dung và siêu dữ liệu là CSDL quốc gia về văn bản pháp
   luật của Bộ Tư pháp (gateway `vbpl-bientap-gateway.moj.gov.vn`). Bộ dữ liệu
   HuggingFace `th1nhng0/vietnamese-legal-documents` (CC-BY-4.0) dùng để nạp hàng
   loạt và được ghi nguồn. Công cụ tìm kiếm và Firecrawl chỉ dùng để tìm văn bản
   còn thiếu và kiểm link. Không chép chữ từ trang thương mại.
2. **Link do máy kiểm được hiển thị** khi đạt đủ: HTTP 200, tiêu đề trang chứa đúng
   số hiệu, ngày ban hành trên trang bằng ngày trong kho; bằng chứng (thời điểm,
   URL canonical, người/máy kiểm) được lưu cùng link. Thứ tự ưu tiên hiển thị:
   vbpl.vn → vanban.chinhphu.vn. Link không đạt thì không hiện.
3. **Một trích dẫn hiện đủ**: điều/khoản/điểm, tên văn bản, loại và số hiệu, cơ
   quan ban hành, ngày ban hành, ngày hiệu lực, nhãn hiệu lực KLAW đánh giá (kèm
   văn bản thay thế/sửa đổi nếu có) và link nguồn chính thống — trong khung đối
   chiếu và trong mục "Căn cứ pháp lý" cuối mỗi câu trả lời. Nhãn hiệu lực vẫn là
   nơi duy nhất KLAW phán về hiệu lực; ngày chỉ là dữ kiện của văn bản.
4. **Kho được mở rộng có ranh giới**: bổ sung văn bản mà văn bản trong kho dẫn chiếu
   tới (hướng dẫn, sửa đổi, thay thế) theo quan hệ `references` của Bộ Tư pháp,
   trong 8 lĩnh vực hiện có. Không mở lĩnh vực mới.
5. **Bản thảo HTML/checklist có khối "Căn cứ"** trong tệp tải về, theo khuôn lời mở
   đầu của chính văn bản luật ("Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20
   tháng 11 năm 2019;"), chỉ dẫn văn bản còn hiệu lực đã kiểm, không kèm câu khẳng
   định hiệu lực. **Bản thảo trên khuôn gốc giữ nguyên** (luật chủ dự án: soạn lại
   là đúng 100% tệp tải lên).
6. **Tình trạng hiệu lực** được làm mới một lần và có script chạy tay để làm mới từ
   Bộ Tư pháp; không chạy theo lịch.
7. Bộ golden 77 câu (cùng trap và mơ hồ) được đo **trước và sau** khi đổi kho.

8. **Quy tắc hiển thị (chủ dự án, 2026-09-28, bổ sung):** một văn bản chỉ được
   hiện cho người dùng (kho, tìm kiếm, bộ lọc, trang văn bản, trích dẫn) khi **đồng
   thời** còn hiệu lực (CHL, hoặc HHL1P — hiện nhãn "Còn hiệu lực một phần"), đã
   xác định được tình trạng từ Bộ Tư pháp, và có **link chính thống đã kiểm**. Văn
   bản hết hiệu lực (HHL) được **giữ trong DB ở dạng ẩn** để KLAW còn chỉ ra văn bản
   thay thế và kiểm trích dẫn cũ, nhưng không bao giờ được hiện hay trích như luật
   đang áp dụng. Nhãn "Chưa xác định" không bao giờ xuất hiện: văn bản chưa rõ tình
   trạng bị ẩn cho tới khi xác định được.
9. **Mọi văn bản được hiện có toàn văn** (chương, điều, khoản) lấy từ Bộ Tư pháp theo
   đúng quy trình đã kiểm; khi có bản PDF đã ký chính thức (vanban.chinhphu.vn) thì
   hiện nút "Bản gốc có chữ ký (PDF)" kèm ảnh xem trước trang 1.
10. **Không hiện dòng chẩn đoán** (mã tình trạng nội bộ, "độ tin cậy", "đánh giá tại
    ngày"). Chỉ hiện nhãn hiệu lực, và khi có, một câu thường nêu văn bản sửa đổi
    hoặc thay thế kèm link.

## Alternatives Considered

1. Chỉ hiện link người đã mở bằng trình duyệt (spec §4.3). Loại: không khả thi cho
   1.634 văn bản; phép kiểm máy nêu ở mục 2 kiểm chính điều người mở sẽ nhìn.
2. Hiện ngày hiệu lực như một phán quyết. Loại: nhãn hiệu lực đã tính theo
   `as_of_date` và đồ thị quan hệ; ngày thô chỉ là dữ kiện.
3. Thêm "Căn cứ" vào mọi bản thảo, kể cả khuôn gốc. Loại: trái luật "đúng 100%".

## Consequences

Positive:

- Người đọc thấy được một trích dẫn đến từ văn bản nào, ban hành ngày nào, mở được
  ở đâu — cam kết "trích dẫn kiểm chứng được" hiện ra ngoài giao diện, không chỉ
  nằm trong tầng kiểm.

Tradeoffs:

- Link máy kiểm có thể hỏng khi vbpl.vn đổi giao diện; script làm mới phải chạy lại.
- Mở rộng kho làm đổi số liệu đánh giá; chênh lệch được đo và ghi.
- Khối "Căn cứ" trong bản thảo là nội dung người dùng đem đi ký: chỉ dẫn văn bản đã
  kiểm, và vẫn chịu miễn trừ "không thay thế tư vấn của luật sư".

## Follow-Up

- Plan: `docs/plans/active/kho-luat-trich-dan-day-du.md`.
- Sửa các docstring và ghi nhớ nói vbpl.vn chặn bot (đã lỗi thời).
- Dữ liệu mới cần được đưa lên production bằng đường dump/restore hiện có.
