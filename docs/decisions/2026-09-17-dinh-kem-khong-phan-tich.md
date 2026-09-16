# Đính kèm là một cử chỉ, không phải một lệnh chạy

Ngày: 2026-09-17

## Status

Accepted

## Bối cảnh

Bản triển khai tới 2026-09-16 làm hai việc ngay trong lần tải tệp lên:

1. `POST /tai-lieu` bắt buộc `hoi_thoai_id`. Phiên chỉ sinh ra sau câu hỏi đầu
   tiên, nên một người vừa đăng nhập, mở đoạn chat mới và kẹp tờ giấy họ đang
   cầm chỉ nhận lại "Cần đăng nhập và có một cuộc trò chuyện để đọc tài liệu" —
   dù họ đã đăng nhập. Đường đính kèm là một ngõ cụt cho đúng lượt đầu tiên.
2. Cùng request đó chạy `rut_du_kien` (một lượt mô hình) rồi giao diện bung
   khung dữ kiện ra giữa màn. Người dùng chưa nói họ muốn gì với tài liệu thì
   đã có một bảng dữ kiện chắn trước ô soạn câu hỏi.

Việc rút ở bước tải lên còn là việc thừa: node `hieu_tai_lieu` trong graph
`tra_cuu` là nơi DUY NHẤT thấy chữ của tài liệu, và nó đã tự rút dữ kiện, tự
neo, tự ghi vào `du_kien_tai_lieu` ở chính lượt hỏi kế tiếp. Hai chỗ cùng rút
là trả tiền mô hình hai lần cho một tờ giấy.

## Decision

Đính kèm chỉ đọc và lưu biểu diễn; phần hiểu nằm ở lượt hỏi.

- `hoi_thoai_id` của `POST /tai-lieu` thành tuỳ chọn. Vắng mặt thì máy chủ mở
  một phiên mới lấy tên tệp làm tiêu đề, và trả id đó trong `TaiLieuOut
  .hoi_thoai_id`. Giao diện ghim nó lên `?phien=` rồi hỏi tiếp vào đúng phiên
  ấy.
- Tải lên KHÔNG gọi mô hình. Nó đọc tệp, lưu `don_vi`, và vẫn tự nhận ra loại
  văn bản bằng `phan_loai` (tra bảng, 0 token) để nói ra nó hiểu tài liệu là gì.
- Ngoại lệ duy nhất còn gọi `rut_du_kien` là khi NGƯỜI DÙNG tự chọn loại văn
  bản ("Rút dữ kiện theo mẫu" → soạn thảo). Lúc đó việc rút chính là thứ họ vừa
  yêu cầu.
- Đính kèm không mở khung tài liệu nữa. Nó gắn một con chip ở ô soạn câu hỏi;
  bấm chip mới mở khung. Neo trong câu trả lời vẫn mở khung đúng đơn vị như cũ.

## Alternatives Considered

1. Giữ tệp ở trình duyệt, tải lên lúc bấm Gửi. Không sinh phiên rỗng, nhưng câu
   hỏi đầu phải chờ thêm một vòng mạng và luồng gửi thành ba bước.
2. Chỉ sửa giao diện (không bung khung), giữ nguyên việc rút ở máy chủ. Diff nhỏ
   nhất, nhưng vẫn trả tiền mô hình hai lần và con chip vẫn xuất hiện chậm.

## Consequences

Positive:

- Kẹp tệp ở một đoạn chat mới đi được — đúng cách ChatGPT/Claude làm.
- Mỗi tài liệu tốn một lượt mô hình thay vì hai.
- Ô soạn câu hỏi không bị một bảng dữ kiện chắn ngay sau khi đính kèm.

Tradeoffs:

- Một lần đính kèm rồi bỏ ngang để lại một phiên rỗng mang tên tệp.
- Tài liệu tự nhận ra loại nhưng chưa ai hỏi tới thì `du_kien` rỗng. Muốn dữ
  kiện theo mẫu ngay thì phải chọn loại ở "Rút dữ kiện theo mẫu".

## Follow-Up

- Dọn phiên rỗng không có lượt nào sau một khoảng thời gian.
