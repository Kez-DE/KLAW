import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * `trace_id` của máy chủ — bảo đảm #17.
 *
 * Backend trả trường này ở cấp 1 của MỌI đáp ứng `/tra-cuu` và `/soat`. Nó cố
 * ý nhỏ và câm: khi mọi thứ chạy đúng thì người dùng không cần tới nó. Nhưng
 * khi một câu trả lời sai, đây là khoá DUY NHẤT nối màn hình của họ với dòng
 * tương ứng trong bảng `traces` — không có nó, một báo lỗi chỉ còn là "hôm qua
 * tôi hỏi gì đó và nó trả lời sai", và không ai dựng lại được lượt chạy ấy.
 *
 * Mã hiện dưới dạng CHỮ chọn được; nút chép chỉ là lối tắt. `navigator.clipboard`
 * cần secure context và có thể bị chính sách trình duyệt chặn, nên nó không
 * được là con đường duy nhất lấy được mã. Chép hỏng thì KHÔNG báo "đã chép" —
 * một thông báo thành công sai chỗ này khiến người dùng dán một clipboard rỗng
 * vào báo lỗi rồi tưởng đã gửi đủ thông tin.
 */
export function MaTruyVet({ traceId, className }: { traceId: string; className?: string }) {
  const [daChep, datDaChep] = useState(false);

  useEffect(() => {
    if (!daChep) return;
    const hen = setTimeout(() => datDaChep(false), 2000);
    return () => clearTimeout(hen);
  }, [daChep]);

  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <span className="font-jetbrains break-all">trace {traceId}</span>
      <button
        type="button"
        onClick={() => {
          void navigator.clipboard.writeText(traceId).then(
            () => datDaChep(true),
            () => datDaChep(false),
          );
        }}
        aria-label={`Chép mã truy vết ${traceId}`}
        className="focus-brass shrink-0 cursor-pointer rounded p-0.5 text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/10"
      >
        {daChep ? (
          <Check className="size-3" aria-hidden />
        ) : (
          <Copy className="size-3" aria-hidden />
        )}
      </button>
      <span role="status" className="sr-only">
        {daChep ? "Đã chép mã truy vết" : ""}
      </span>
    </span>
  );
}
