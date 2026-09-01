import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import {
  BookOpenText,
  FileSignature,
  LifeBuoy,
  MessagesSquare,
  Scale,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useKhungModalDangMo } from "@/hooks/use-khung-modal";

const NAV = [
  { to: "/dung-thu", label: "Trợ lý KLAW", icon: Sparkles },
  { to: "/tra-cuu", label: "Tra cứu luật", icon: BookOpenText },
  { to: "/soan-thao", label: "Soạn thảo", icon: FileSignature },
  { to: "/chat", label: "Trò chuyện", icon: MessagesSquare },
  { to: "/huong-dan", label: "Hướng dẫn", icon: LifeBuoy },
] as const;

// TrialMeter đã gỡ: nó hiện "còn N/20 lượt hỏi" trong khi không có hệ thống
// hạn mức nào — không ở FE, không ở backend. Dựng lại khi /han-muc có thật.

export function AppShell({
  active,
  topRight,
  children,
}: {
  active?: string;
  topRight?: ReactNode;
  children: ReactNode;
}) {
  // Khung đối chiếu ở bố cục một cột khai `aria-modal`. Điều hướng và thanh
  // dưới là anh em của <main>, nên chỉ vỏ này gỡ được chúng khỏi vòng Tab.
  const modalMo = useKhungModalDangMo();

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar: 260px ≥1280px, 64px icon rail 768–1280px, bottom bar <768px */}
      <aside
        inert={modalMo}
        aria-label="Điều hướng chính"
        className="sticky top-0 hidden h-screen w-16 shrink-0 flex-col border-r border-border bg-[var(--color-paper-50)] px-2 py-4 md:flex xl:w-[260px] xl:px-3"
      >
        <Link
          to="/"
          aria-label="KLAW — về trang chủ"
          className="focus-brass mb-6 flex items-center justify-center gap-2.5 rounded-lg xl:justify-start xl:px-2"
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-gradient-ink text-primary-foreground shadow-soft">
            <Scale className="size-4.5" />
          </span>
          <span className="hidden font-display text-lg font-bold tracking-tight text-primary xl:inline">
            KLAW
          </span>
        </Link>
        <nav className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const Icon = item.icon;
            const isActive = active === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                aria-label={item.label}
                aria-current={isActive ? "page" : undefined}
                title={item.label}
                className={cn(
                  "focus-brass flex items-center justify-center gap-2.5 rounded-lg px-2.5 py-2.5 text-sm transition-colors xl:justify-start",
                  isActive
                    ? "bg-[var(--color-paper-200)] font-medium text-primary"
                    : "text-muted-foreground hover:bg-[var(--color-paper-100)] hover:text-primary",
                )}
              >
                <Icon className="size-4 shrink-0" aria-hidden />
                <span className="hidden xl:inline">{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto hidden rounded-lg border border-border bg-card p-3 text-[12px] text-muted-foreground xl:block">
          KLAW là trợ lý pháp lý, không thay thế ý kiến của luật sư.
          <span className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
            <Link
              to="/mien-tru"
              className="focus-brass rounded underline underline-offset-2 hover:text-primary"
            >
              Giới hạn
            </Link>
            <Link
              to="/du-lieu"
              className="focus-brass rounded underline underline-offset-2 hover:text-primary"
            >
              Nguồn dữ liệu
            </Link>
          </span>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col pb-14 md:pb-0">
        <header
          inert={modalMo}
          className="sticky top-0 z-30 flex items-center gap-4 border-b border-border bg-background/90 px-4 py-2.5 backdrop-blur"
        >
          <Link
            to="/"
            aria-label="KLAW — về trang chủ"
            className="focus-brass flex items-center gap-2 rounded-lg md:hidden"
          >
            <span className="flex size-8 items-center justify-center rounded-lg bg-gradient-ink text-primary-foreground">
              <Scale className="size-4" aria-hidden />
            </span>
            <span className="font-display font-bold text-primary">KLAW</span>
          </Link>
          <div className="ml-auto">{topRight}</div>
        </header>
        <main id="noi-dung-chinh" className="flex min-w-0 flex-1 flex-col">
          {children}
        </main>
      </div>

      {/* Bottom navigation under 768px */}
      <nav
        inert={modalMo}
        aria-label="Điều hướng chính (thu gọn)"
        className="fixed inset-x-0 bottom-0 z-40 flex items-stretch border-t border-border bg-background/95 backdrop-blur md:hidden"
      >
        {NAV.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              aria-label={item.label}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "focus-brass flex min-h-14 flex-1 flex-col items-center justify-center gap-1 px-1 text-[10px]",
                isActive ? "font-medium text-primary" : "text-muted-foreground",
              )}
            >
              <Icon className="size-[18px]" aria-hidden />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
