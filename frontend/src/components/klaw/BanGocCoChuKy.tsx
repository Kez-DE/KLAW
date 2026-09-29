import { FileText } from "lucide-react";
import { apiGoc } from "@/lib/api";
import type { VanBanMeta } from "@/lib/klaw";
import { banGocKy } from "@/lib/trich-dan";
import { cn } from "@/lib/utils";

/**
 * Dòng "Bản gốc có chữ ký" của "Thông tin văn bản" (quyết định 2026-09-28,
 * mục 9): nút mở bản PDF đã ký trên Cổng TTĐT Chính phủ và, khi có, ảnh trang 1
 * — bấm ảnh cũng mở PDF. Không có link hợp lệ thì KHÔNG vẽ gì: không "Chưa có".
 *
 * Ảnh đi thẳng `<img src>`: endpoint công khai như chính trang văn bản, không
 * cần Bearer. `width`/`height` giữ chỗ tỉ lệ A4 dọc cho tới khi ảnh về.
 */
export function BanGocCoChuKy({ vanBan }: { vanBan: VanBanMeta }) {
  const banGoc = banGocKy(vanBan);
  if (banGoc === null) return null;
  const moTabMoi = { href: banGoc.url, target: "_blank", rel: "noopener noreferrer" } as const;
  return (
    <div
      className={cn(
        "flex justify-between gap-3 border-b border-border/60 py-1.5 last:border-0",
        banGoc.coAnh && "sm:col-span-2",
      )}
    >
      <dt className="text-muted-foreground">Bản gốc có chữ ký</dt>
      <dd className="flex min-w-0 flex-col items-end gap-2 text-right font-medium">
        <a
          {...moTabMoi}
          className="focus-brass inline-flex min-h-11 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/10 sm:min-h-8"
        >
          <FileText className="size-3.5" aria-hidden />
          Bản gốc có chữ ký (PDF)
          <span className="sr-only"> (mở tab mới)</span>
        </a>
        {banGoc.coAnh && (
          <a {...moTabMoi} className="focus-brass block rounded">
            <img
              src={`${apiGoc()}/van-ban/${encodeURIComponent(vanBan.doc_id)}/anh-xem-truoc`}
              alt={`Trang 1 bản gốc có chữ ký của ${vanBan.so_ky_hieu}`}
              loading="lazy"
              width={240}
              height={339}
              className="h-auto w-full max-w-[240px] rounded border border-border bg-white shadow-soft"
            />
            <span className="sr-only"> (mở tab mới)</span>
          </a>
        )}
      </dd>
    </div>
  );
}
