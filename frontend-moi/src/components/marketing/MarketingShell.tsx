import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { Scale } from "lucide-react";

// Light marketing shell: luminous parchment + brass, wordmark header, fine-print footer.
export function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen bg-gradient-aurora text-foreground">
      <div className="brass-lines pointer-events-none fixed inset-0" aria-hidden />
      <div className="relative">
        <header className="sticky top-0 z-30 border-b border-border/70 bg-card/75 backdrop-blur-xl">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
            <Link to="/" className="focus-brass flex items-center gap-2.5 rounded-md">
              <span className="grid size-9 place-items-center rounded-lg bg-brass-500/20 text-brass-600 shadow-soft">
                <Scale className="size-4.5" />
              </span>
              <span className="font-display text-xl tracking-wide text-primary">KLAW</span>
            </Link>
            <Link
              to="/"
              className="focus-brass rounded-md text-[13px] text-muted-foreground transition-colors hover:text-brass-600"
            >
              Quay lại trang chủ
            </Link>
          </div>
        </header>

        <main>{children}</main>

        <footer className="border-t border-border/70 py-10">
          <div className="mx-auto max-w-6xl px-6">
            <p className="text-[12px] leading-relaxed text-muted-foreground">
              KLAW — trợ lý AI hỗ trợ tra cứu pháp luật và soạn thảo văn bản pháp lý. Nội dung do
              KLAW tạo ra chỉ mang tính tham khảo; luôn đối chiếu với văn bản gốc và rà soát bởi
              luật sư trước khi sử dụng.
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
}
