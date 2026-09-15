import { X } from "lucide-react";
import { Link } from "@tanstack/react-router";

/**
 * Thẻ "hết lượt" trong dòng chat — ba tình huống, một hình dạng.
 *
 * Cả ba đều là NGÕ CỤT có lối ra, không phải lỗi: phiên đã đủ lượt (mở phiên
 * mới), khách đã dùng hết lượt thử (đăng nhập), gói Cá nhân đã hết hạn (gia
 * hạn). Nên chúng mang khay trung tính viền nét đứt như mọi trạng thái "đã
 * dừng, đây là đường đi tiếp" khác của màn hỏi — KHÔNG mượn màu hiệu lực,
 * thứ dành riêng cho luật không còn dùng được.
 *
 * `role="status"` chứ không `alert`: thẻ hiện ra sau một hành động của chính
 * người dùng và không đòi họ dừng việc đang làm.
 *
 * `onTat` CHỈ dành cho `het_han`. Hai loại kia là ngõ cụt cứng — người hỏi
 * không đi tiếp được nếu không bấm một trong hai nút, nên một dấu X ở đó là
 * giấu mất lối ra duy nhất. Gói hết hạn thì khác: tài khoản rơi về gói miễn
 * phí và vẫn hỏi được, nên thẻ là lời nhắc chứ không phải rào chắn.
 *
 * Chữ đi vào qua `chiTiet` vì con số (trần lượt, hạn mức, ngày hết hạn) đến từ
 * `GET /han-muc`. Chép tay một con số ở đây là dựng lại đúng cái đồng hồ sai
 * mà `TheDangNhap` đã phải gỡ một lần.
 */
export function TheHetLuot({
  loai,
  chiTiet,
  onPhienMoi,
  onNangGoi,
  onCatThread,
  onTat,
}: {
  loai: "khach" | "phien" | "het_han";
  chiTiet: string;
  onPhienMoi?: () => void;
  onNangGoi?: () => void;
  /** Cất đoạn chat khách trước khi rời trang — nếu không, đăng nhập xong là mất. */
  onCatThread?: () => void;
  /** Tắt thẻ. Chỉ truyền cho `het_han`; xem ghi chú ở đầu tệp. */
  onTat?: (() => void) | undefined;
}) {
  return (
    <div role="status" className="relative rounded-xl border border-dashed border-border px-4 py-3">
      {onTat !== undefined && loai === "het_han" && (
        <button
          type="button"
          onClick={onTat}
          aria-label="Tắt thông báo hết hạn gói"
          className="focus-brass absolute top-1 right-1 grid size-11 cursor-pointer place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-[var(--color-paper-100)]"
        >
          <X aria-hidden className="size-4" />
        </button>
      )}
      <p className="m-0 pr-12 text-[14px] leading-6 text-foreground">{chiTiet}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {loai === "phien" && onPhienMoi !== undefined && (
          <button
            type="button"
            onClick={onPhienMoi}
            className="focus-brass inline-flex min-h-10 cursor-pointer items-center rounded-lg border border-border px-4 text-sm font-medium text-primary transition-colors hover:bg-[var(--color-paper-100)]"
          >
            Phiên mới
          </button>
        )}
        {loai === "khach" && (
          <>
            <Link
              to="/dang-nhap"
              search={{ next: "/dung-thu" }}
              onClick={onCatThread}
              className="focus-brass bg-gradient-ink inline-flex min-h-10 items-center rounded-lg px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
            >
              Đăng nhập
            </Link>
            <Link
              to="/dang-ky"
              search={{ next: "/dung-thu" }}
              onClick={onCatThread}
              className="focus-brass inline-flex min-h-10 items-center rounded-lg border border-border px-4 text-sm text-primary transition-colors hover:bg-[var(--color-paper-100)]"
            >
              Đăng ký miễn phí
            </Link>
          </>
        )}
        {loai === "het_han" && onNangGoi !== undefined && (
          <button
            type="button"
            onClick={onNangGoi}
            className="focus-brass bg-gradient-ink inline-flex min-h-10 cursor-pointer items-center rounded-lg px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Gia hạn 30 ngày
          </button>
        )}
      </div>
    </div>
  );
}
