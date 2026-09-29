import { ExternalLink } from "lucide-react";
import { BanGocCoChuKy } from "@/components/klaw/BanGocCoChuKy";
import type { VanBanMeta } from "@/lib/klaw";
import { banGocKy, vanBanHopLe } from "@/lib/trich-dan";

/**
 * Trang của một văn bản được hiện mà KLAW chưa có toàn văn (quyết định
 * 2026-09-28, mục 16): nói thẳng là chưa có, đưa người đọc tới bản trên cổng
 * chính thống (link đã kiểm, `lien_ket`) và bản gốc có chữ ký khi có. Không câu
 * nào ở đây ngụ ý kho đã đọc nội dung văn bản.
 */
export function ChuaCoToanVan({ vanBan }: { vanBan: VanBanMeta }) {
  const lienKet = vanBanHopLe(vanBan).lien_ket;
  return (
    <section
      aria-label="Toàn văn"
      className="mt-8 rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground"
    >
      <p className="m-0 font-medium text-foreground">KLAW chưa có toàn văn của văn bản này.</p>
      {lienKet !== null && (
        <p className="mt-2 mb-0">
          <a
            href={lienKet.url}
            target="_blank"
            rel="noopener noreferrer"
            className="focus-brass inline-flex min-h-11 items-center gap-1 rounded font-medium text-[var(--color-brass-600)] underline-offset-2 hover:underline sm:min-h-0"
          >
            Xem toàn văn trên {lienKet.nhan}
            <ExternalLink className="size-3.5" aria-hidden />
            <span className="sr-only"> (mở tab mới)</span>
          </a>
        </p>
      )}
      {banGocKy(vanBan) !== null && (
        <dl className="mt-3 mb-0 text-[13px]">
          <BanGocCoChuKy vanBan={vanBan} />
        </dl>
      )}
    </section>
  );
}
