import { useEffect, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
import { breadcrumb, type Tam } from "@/lib/ngan-xep-drawer";
import { cn } from "@/lib/utils";

interface Props {
  ngan: Tam[];
  /**
   * Đóng tấm trên cùng. PHẢI là một tham chiếu ỔN ĐỊNH qua các lần render
   * (`useCallback` ở nơi gọi, không phải một hàm mũi tên trần) — nó nằm
   * trong dependency của effect bên dưới, và effect đó chạy lại bước "đưa
   * tiêu điểm vào tấm trên cùng" mỗi khi nó đổi tham chiếu, dù `ngan` không
   * đổi. Một tham chiếu không ổn định (đổi ở MỌI lần render của nơi gọi —
   * một token stream ở chỗ khác, đổi zoom…) giật tiêu điểm ra khỏi ô đang gõ
   * dở, về lại nút Đóng.
   */
  onDong: () => void;
  render: (tam: Tam, tang: number) => ReactNode;
}

/** Drawer xếp chồng kiểu Payload (useEditDepth): tấm trên cùng nhận tiêu điểm, Esc đóng nó, nền mờ chung. */
export function NganXepDrawer({ ngan, onDong, render }: Props) {
  const noiMo = useRef<HTMLElement | null>(null);
  const tamTrenCung = useRef<HTMLDivElement | null>(null);
  const soTang = ngan.length;

  useEffect(() => {
    if (soTang === 0) return;
    const dangGiu = document.activeElement;
    if (dangGiu instanceof HTMLElement && !tamTrenCung.current?.contains(dangGiu))
      noiMo.current = dangGiu;
    tamTrenCung.current?.querySelector<HTMLElement>("input, select, textarea, button")?.focus();
    const nghe = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDong();
      if (e.key === "Tab" && tamTrenCung.current) {
        const dong = tamTrenCung.current.querySelectorAll<HTMLElement>(
          "input, select, textarea, button, a[href], [tabindex]:not([tabindex='-1'])",
        );
        if (dong.length === 0) return;
        const dau = dong[0]!,
          cuoi = dong[dong.length - 1]!;
        if (e.shiftKey && document.activeElement === dau) {
          e.preventDefault();
          cuoi.focus();
        } else if (!e.shiftKey && document.activeElement === cuoi) {
          e.preventDefault();
          dau.focus();
        }
      }
    };
    window.addEventListener("keydown", nghe);
    return () => window.removeEventListener("keydown", nghe);
  }, [soTang, onDong]);

  useEffect(() => {
    if (soTang === 0 && noiMo.current?.isConnected) noiMo.current.focus();
  }, [soTang]);

  if (soTang === 0) return null;
  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-[var(--color-ink-950)]/30"
        onClick={onDong}
        aria-hidden
      />
      {ngan.map((tam, tang) => {
        const trenCung = tang === soTang - 1;
        return (
          <div
            key={tam.id}
            ref={trenCung ? tamTrenCung : undefined}
            role="dialog"
            aria-modal={trenCung || undefined}
            aria-label={tam.tieuDe}
            // Tấm không phải trên cùng: `inert` (native, React 19) gỡ nó khỏi
            // CẢ BA — con trỏ, Tab, và cây trợ năng — cùng lúc. `pointer-events-none`
            // một mình chỉ chặn được con trỏ; trình đọc màn hình ở chế độ
            // duyệt (không qua Tab) vẫn đọc được vào một tấm bị che. Chỉ đặt
            // khi KHÔNG phải tấm trên cùng — tấm trên cùng không mang `inert`.
            inert={!trenCung}
            style={{ right: (soTang - 1 - tang) * 24, zIndex: 41 + tang }}
            className={cn(
              "fixed inset-y-0 flex w-[480px] max-w-full flex-col border-l border-border bg-card shadow-elegant",
              !trenCung && "opacity-90",
            )}
          >
            <header className="flex items-center gap-2 border-b border-border px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="m-0 truncate text-[12px] text-muted-foreground">
                  {breadcrumb(ngan.slice(0, tang + 1))}
                </p>
                <h2 className="font-display m-0 truncate text-[16px] font-bold text-primary">
                  {tam.tieuDe}
                </h2>
              </div>
              {trenCung && (
                <button
                  type="button"
                  onClick={onDong}
                  aria-label="Đóng"
                  className="focus-brass cursor-pointer rounded p-1 hover:bg-secondary"
                >
                  <X className="size-4" aria-hidden />
                </button>
              )}
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">{render(tam, tang)}</div>
          </div>
        );
      })}
    </>
  );
}
