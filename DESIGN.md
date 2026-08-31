# Design

<!-- impeccable:design-schema 1 -->

## Thế giới thị giác: máy đọc vi phim

Một cỗ máy tra cứu lưu trữ. Bạn gõ câu hỏi, máy tìm trong kho, **tiến tới đúng khung
phim**, và rọi sáng nguyên văn điều luật lên mặt kính.

Ẩn dụ này được chọn vì nó mang đúng lời hứa của sản phẩm và không thể mang một lời hứa
khác: *đây là nguyên văn, và đây là chỗ nó đến từ.* Một trợ lý pháp lý nói trôi chảy mà
không chỉ được nguồn thì phản bội chính nó; một máy đọc vi phim **không thể** làm vậy —
nó chỉ biết chiếu lại thứ có thật trên phim.

Ba lớp, người dùng chọn đi sâu tới đâu:

| Lớp | Nội dung | Ai dùng nhiều nhất |
|---|---|---|
| **Mặt đọc** | Câu trả lời bằng tiếng Việt thường | người lao động |
| **Dải khung** | Các trích dẫn, mỗi cái một khung phim có nhãn hiệu lực | nhân sự |
| **Khung rọi sáng** | Nguyên văn điều luật, câu trích được đánh dấu | sinh viên luật |

Một câu trả lời, ba lớp — không phải ba giao diện.

## Bảng màu

Ground tối là mặt máy; ánh sáng là thứ rọi qua phim.

```
--nen          #0F1113   mặt máy, ground
--nen-cao      #171A1D   khay, thanh công cụ
--phim         #F4F1EA   mặt phim được rọi — nền của văn bản luật
--muc          #14171A   chữ trên phim
--muc-nhat     #5A6169   chú thích, nhãn phụ
--den-sang     #E8B34B   ánh đèn máy: tiêu điểm, khung đang xem, con trỏ
--xanh-that    #3E8E6E   còn hiệu lực
--do-thay      #C4553D   đã bị thay thế / hết hiệu lực
--vang-mo      #C08A2E   một phần không xác định
--xam-cho      #6B7280   ABSTAIN, cần đối chiếu tay — TRUNG TÍNH
```

**`--xam-cho` là quyết định quan trọng nhất của bảng màu này.** `abstain` là hành vi
**đúng**, được tính điểm trong đánh giá. Nó không bao giờ được mang màu đỏ, không icon
cảnh báo, không rung. Một hệ thống thà nói "tôi không đủ căn cứ" còn hơn bịa một điều
luật — nếu giao diện tô đỏ câu đó, nó dạy người dùng rằng sự trung thực là thất bại.

Đỏ dành riêng cho **luật đã bị thay thế**. Đó mới là thứ khiến người dùng hành động sai.

## Chữ và bố cục

- **Mặt đọc**: sans humanist đọc tốt tiếng Việt có dấu, thân 17px trên di động và 18px
  trên desktop, dòng 1.7. Dấu tiếng Việt cần chiều cao dòng rộng hơn tiếng Anh.
- **Trên phim**: serif, vì nguồn là văn bản in. Chữ trên phim **không bao giờ** đổi màu
  theo trạng thái — phim là phim; trạng thái sống ở nhãn và ở viền khung.
- **Số hiệu, đường dẫn trích dẫn**: mono, vì `45/2019/QH14 > Điều 127 > Khoản 2` là một
  **địa chỉ**, không phải văn xuôi. Người dùng cần quét và so từng ký tự.
- Bề rộng đọc tối đa **68 ký tự** ở mặt đọc; dải khung không giới hạn ngang.

## Cấu trúc và điều hướng

Ba màn hình, một máy:

- **Tra cứu** — ô hỏi ở giữa khi trống, trượt lên đầu khi có kết quả
- **Soạn thảo** — nhập thông tin, máy sinh văn bản, mỗi điều khoản mang căn cứ riêng
- **Soát** — dán văn bản có sẵn, máy trả danh sách phát hiện, mỗi cái neo vào một khung

Chuyển giữa ba màn hình là **đổi khay phim**, không phải tải lại trang.

## Trạng thái — bốn kết quả, bốn cách hiển thị

| `result_type` | Giao diện |
|---|---|
| `answer` | mặt đọc có văn bản; dải khung bên dưới; badge hiệu lực trên từng khung |
| `partial_coverage` | mặt đọc **để trống có chủ đích** — không diễn giải. Chỉ nêu văn bản tìm thấy + đường dẫn tới nguyên văn |
| `abstain` | *"Không tìm thấy căn cứ pháp lý cho câu hỏi này."* + gợi ý diễn đạt lại. Nền `--xam-cho`, chữ bình thường, **không icon lỗi** |
| `out_of_scope` | nêu rõ phạm vi: 6 Bộ luật + cụm Lao động; liệt kê cái **không** phủ (thuế, đất đai, hôn nhân gia đình) |

Badge hiệu lực trên mỗi khung, **luôn thấy được**, không nằm trong tooltip:

| Nhãn | Hiển thị |
|---|---|
| `con_hieu_luc` | chấm `--xanh-that`, không chữ |
| `bi_thay_the` / `het_hieu_luc` | viền `--do-thay` + câu nêu **đích danh** văn bản thay thế |
| `mot_phan_khong_xac_dinh` | viền `--vang-mo` + *"CSDL quốc gia không công bố dữ liệu cấp điều khoản"* |
| `can_doi_chieu_tay` | chấm `--xam-cho` + *"cần đối chiếu tay"* |

## Chuyển động — giải thích quan hệ, không trang trí

Bốn chuyển động, mỗi cái một việc:

1. **Tiến tới khung** — bấm một trích dẫn, khung trượt vào tiêu điểm và sáng lên. Đây là
   động tác trung tâm: nó *là* click-to-verify. `transform` + `opacity`, chạy trên
   compositor.
2. **Rọi tiêu điểm** — câu trích sáng dần trong nguyên văn, để mắt tìm được nó trong một
   Điều dài.
3. **Trạng thái chờ** — tra cứu mất **10–60 giây**. Không spinner. Máy đếm qua các bước
   **có thật** trong đồ thị: *đang tìm → đang mở rộng → đang kiểm chứng → đang dựng câu
   trả lời*. Người dùng thấy hệ thống đang làm gì, không phải một vòng tròn quay.
   Trên ngưỡng 10 giây, một chỉ báo không xác định đọc như **treo máy**: phải có tên
   bước đang chạy, tiến trình xác định, và **nút huỷ**. Hoãn 300–500ms trước khi hiện
   chỉ báo để câu trả lời nhanh không làm loé rồi tắt. Luôn có timeout dẫn tới lỗi thật
   kèm nút thử lại — không treo im lặng.
4. **Đổi khay** — chuyển giữa ba màn hình, trượt ngang có chiều sâu.

Chiều sâu 3D dùng `perspective` + `translateZ` ở dải khung, **không WebGL** — thư viện 3D
nặng sẽ giết trải nghiệm trên điện thoại đời cũ, mà người lao động là một trong ba nhóm
người dùng chính.

`prefers-reduced-motion`: thay dịch chuyển bằng đổi opacity, **giữ nguyên** phản hồi
trạng thái. Tắt hết không được — người dùng vẫn phải biết bước nào đang chạy trong 60
giây đó.

## Responsive

- **Di động**: một cột. Mặt đọc trước, dải khung cuộn ngang bên dưới, khung rọi sáng mở
  toàn màn hình. Vùng chạm tối thiểu 44px.
- **Máy tính**: hai cột — mặt đọc trái, khung rọi sáng phải, dải khung dưới mặt đọc. Đọc
  câu trả lời và nguyên văn **cùng lúc**, không chuyển qua lại.
- Điểm gãy theo **nội dung**, không theo tên thiết bị: cột đôi khi đủ chỗ cho 68 ký tự
  **và** một khung phim đọc được cạnh nhau.

## Ràng buộc không được vi phạm

- Định danh văn bản bằng `so_ky_hieu`, **không bao giờ** bằng tên
- Cảnh báo hiệu lực **không được** giấu vào tooltip hay metadata
- `abstain` **không bao giờ** mang màu lỗi
- `GET /van-ban/{id}` lazy — không tải cả cây 689 Điều
- Chữ trên phim là nguyên văn từ CSDL: **không** rút gọn, **không** sửa chính tả
