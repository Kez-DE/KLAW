import { RotateCcw } from "lucide-react";
import { Link } from "@tanstack/react-router";
import type { ApiError, ApiErrorKind } from "@/lib/klaw";

/**
 * Lỗi hệ thống — mạng, timeout, máy chủ, body sai hình dạng.
 *
 * **Không dùng màu hiệu lực.** Đỏ trong bảng màu này dành riêng cho luật đã bị
 * thay thế hoặc hết hiệu lực: đó là thứ khiến người dùng hành động sai. Một
 * lỗi mạng mượn cùng tín hiệu thì nhãn đỏ mất nghĩa, và lần sau người dùng sẽ
 * lướt qua một cảnh báo hiệu lực thật vì tưởng lại là lỗi mạng. Lỗi hệ thống
 * nói bằng CHỮ, trên khay trung tính, kèm một nút thử lại.
 *
 * Tám nhánh, không phải một. Bản Klaw_FE có đúng một trạng thái `error` chung,
 * và một câu chung không nói được điều mà tám tình huống này cần nói: người
 * gặp `timeout` phải tách câu hỏi ra, người gặp `network` phải kiểm mạng, còn
 * người gặp `invalid_response` thì KHÔNG có gì để làm — và phải được nói thẳng
 * là lỗi không nằm ở câu hỏi của họ.
 */

/**
 * Câu thứ hai: nói người dùng nên làm gì. Trả `null` khi thành thật là không
 * có việc gì để họ làm — thà im còn hơn bịa một hành động vô ích.
 *
 * `switch` trên `ApiErrorKind` và KHÔNG có `default`: `noFallthroughCasesInSwitch`
 * cộng union đóng nghĩa là thêm một nhánh lỗi thứ chín mà quên viết gợi ý sẽ
 * làm gãy `tsc`, không phải gãy màn hình của người dùng.
 */
function goiY(kind: ApiErrorKind): string | null {
  switch (kind) {
    case "network":
      return "Kiểm tra kết nối mạng rồi thử lại. Câu hỏi của bạn chưa được gửi đi.";
    case "timeout":
      return "Một lượt tra cứu mất 10–60 giây; lượt này vượt quá ngưỡng đó. Câu hỏi có thể quá phức tạp — thử tách thành từng ý ngắn hơn.";
    case "aborted":
      // Người dùng tự bấm huỷ. Đây không phải lỗi và gần như không bao giờ
      // được hiển thị — `useGoiApi` nuốt nhánh này. Giữ câu ở đây để nếu có
      // nơi nào lỡ hiện nó ra thì nó vẫn đọc như một sự việc bình thường.
      return "Lượt tra cứu đã dừng theo yêu cầu của bạn.";
    case "not_implemented":
      // Nhánh DUY NHẤT trong tệp này không nói về lỗi hạ tầng: 501 phát ra khi
      // một loại văn bản chưa có checklist/căn cứ riêng, hoặc khi xác thực chưa
      // được cấu hình — cả hai là "chưa dựng xong", không phải "vừa hỏng". Câu
      // cũ ("chưa có nội dung pháp lý trong hệ thống") là một phát biểu về ĐỘ
      // PHỦ đội lốt thông báo lỗi, nên nó nói bằng giọng của người trả lời.
      // Không nêu đích danh nguyên nhân: `loi.message` ngay trên đã mang
      // `detail` của máy chủ, và đoán sai giữa hai nguyên nhân thì tệ hơn im.
      return "Phần này mình chưa dựng xong nên chưa có kết quả thật để đưa cho bạn — không phải lỗi ở phía bạn.";
    case "not_found":
      // R5, và ranh giới của nó: bỏ chữ "kho" KHÔNG được thành "pháp luật Việt
      // Nam không có điều khoản này" — 404 chỉ nói KLAW chưa có nguyên văn của
      // nó, một điều hẹp hơn hẳn và là điều duy nhất đúng ở đây.
      return "KLAW chưa có nguyên văn của văn bản hoặc điều khoản này.";
    case "unauthorized":
      // KHÔNG khuyên "kiểm tra lại nội dung đã nhập": nội dung không liên
      // quan gì. Cổng bảo vệ chặn vì thiếu quyền, và người dùng không sửa
      // được điều đó bằng cách viết lại câu hỏi.
      return "Bạn chưa đăng nhập hoặc phiên đã hết hạn. Đăng nhập rồi hỏi lại — câu hỏi của bạn không có gì sai.";
    case "rate_limited":
      // Ba nguyên nhân cùng mang mã 429 (quá nhịp, hết hạn mức, trần chi phí
      // ngày) và câu ngay trên đã nói rõ là cái nào, KÈM mốc mở lại. Nên câu
      // này chỉ trỏ lên dòng đó chứ không hẹn "chờ một lát rồi thử lại": 429 là
      // nhánh DUY NHẤT bị giấu nút Thử lại, và một lời khuyên trỏ tới cái nút
      // không có ở đó là một lời khuyên sai.
      return "Bạn đã chạm giới hạn lượt gọi; dòng trên cho biết khi nào mở lại. Câu hỏi của bạn không có gì sai.";
    case "invalid_request":
      return "Yêu cầu gửi lên chưa hợp lệ. Kiểm tra lại nội dung đã nhập rồi thử lại.";
    case "server_error":
      return "Lỗi ở phía máy chủ KLAW, không phải ở câu hỏi của bạn. Thử lại sau ít phút.";
    case "invalid_response":
      // Nhánh nguy hiểm nhất và dễ mất nhất: 2xx nhưng body sai hình dạng.
      // Không có nhánh này thì giao diện hoặc sập, hoặc — tệ hơn — render một
      // câu trả lời rỗng như thể đó là câu trả lời thật.
      return "Máy chủ trả về dữ liệu không đúng định dạng nên không hiển thị được. Đây là lỗi hệ thống, không phải lỗi câu hỏi — và hệ thống chọn không hiển thị gì thay vì hiển thị một phần dữ liệu không đọc được.";
  }
}

interface BaoLoiProps {
  loi: ApiError;
  onThuLai?: () => void;
  /**
   * Mở màn nâng gói. Chỉ truyền khi 429 đến từ HẠN MỨC đã cạn và người dùng
   * đang ở một gói nâng lên được — nút này không có nghĩa gì với lỗi mạng.
   */
  onNangGoi?: () => void;
}

export function BaoLoi({ loi, onThuLai, onNangGoi }: BaoLoiProps) {
  const them = goiY(loi.kind);
  // 429 KHÔNG kèm nút thử lại: bấm lại ngay chỉ nhận đúng 429 đó thêm một lần.
  // Ba nguyên nhân của mã này (quá nhịp, hết hạn mức, trần chi phí) đều cần
  // thời gian hoặc một gói khác, không cần thêm một cú bấm.
  const hienThuLai = onThuLai !== undefined && loi.kind !== "rate_limited";
  return (
    <div
      role="alert"
      className="mt-4 rounded-xl border-l-2 border border-border bg-[var(--color-paper-50)] p-4"
      style={{ borderLeftColor: "var(--color-status-neutral)" }}
    >
      <p className="doc-prose m-0 text-foreground">{loi.message}</p>
      {them !== null && (
        <p className="mt-2 mb-0 text-[14px] leading-6 text-muted-foreground">{them}</p>
      )}
      {loi.kind === "unauthorized" && (
        <Link
          to="/dang-nhap"
          search={{ next: "/dung-thu" }}
          className="focus-brass mt-3 inline-flex min-h-11 items-center rounded-lg border border-border px-4 text-[15px] font-medium text-primary transition-colors hover:bg-[var(--color-paper-100)]"
        >
          Đăng nhập
        </Link>
      )}
      {loi.status !== undefined && (
        <p className="mt-2 mb-0 font-jetbrains text-[12px] text-muted-foreground">
          Mã lỗi HTTP {loi.status} · {loi.kind}
        </p>
      )}
      {(hienThuLai || onNangGoi !== undefined) && (
        <div className="mt-3 flex flex-wrap gap-2">
          {hienThuLai && (
            <button
              type="button"
              onClick={onThuLai}
              className="focus-brass inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg bg-primary px-4 text-[15px] font-medium text-primary-foreground transition-opacity hover:opacity-90"
            >
              <RotateCcw className="size-4" aria-hidden />
              Thử lại
            </button>
          )}
          {onNangGoi !== undefined && (
            <button
              type="button"
              onClick={onNangGoi}
              className="focus-brass inline-flex min-h-11 cursor-pointer items-center rounded-lg bg-primary px-4 text-[15px] font-medium text-primary-foreground transition-opacity hover:opacity-90"
            >
              Nâng cấp
            </button>
          )}
        </div>
      )}
    </div>
  );
}
