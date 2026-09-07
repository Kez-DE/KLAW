import { Link } from "@tanstack/react-router";
import { LogIn } from "lucide-react";
import type { DichQuayLai } from "@/lib/quay-lai";

const CAU_MO: Record<DichQuayLai, string> = {
  "/dung-thu": "Đăng nhập để hỏi KLAW. Tài khoản mới dùng gói Miễn phí.",
  "/soan-thao": "Đăng nhập để soạn văn bản. Tài khoản mới dùng gói Miễn phí.",
};

/**
 * Thay chỗ ô nhập của một màn cần danh tính khi Supabase đã cấu hình mà chưa
 * có phiên. Từ 2A màn hỏi KHÔNG còn dùng thẻ này — khách hỏi thử được 10 lượt
 * và tự gặp `TheHetLuot` khi hết; nơi còn khoá thật là màn soạn thảo.
 *
 * Câu mở đi theo `next` vì đó là việc người dùng ĐANG định làm; một câu chung
 * ("đăng nhập để dùng KLAW") bắt họ tự suy ra vì sao mình bị chặn.
 *
 * KHÔNG viết cứng số lượt: nguồn số là `config/han_muc.yaml`, và `HanMucThang`
 * hiện nó sau đăng nhập — một con số chép tay ở đây là đồng hồ "còn N/20 lượt"
 * mà mã đã phải gỡ một lần.
 */
export function TheDangNhap({ next }: { next: DichQuayLai }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 shadow-soft">
      <p className="m-0 text-sm leading-6 text-foreground">
        <LogIn className="mr-2 inline size-4 align-text-bottom text-muted-foreground" aria-hidden />
        {CAU_MO[next]}
      </p>
      <div className="flex gap-2">
        <Link
          to="/dang-nhap"
          search={{ next }}
          className="focus-brass bg-gradient-ink inline-flex min-h-10 items-center rounded-lg px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          Đăng nhập
        </Link>
        <Link
          to="/dang-ky"
          search={{ next }}
          className="focus-brass inline-flex min-h-10 items-center rounded-lg border border-border px-4 text-sm text-primary transition-colors hover:bg-[var(--color-paper-100)]"
        >
          Tạo tài khoản
        </Link>
      </div>
    </div>
  );
}
