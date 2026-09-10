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
  /** Dưới ngưỡng hai cột (Task 26, spec 2026-09-09 §9.7): mỗi tấm phủ TOÀN
   *  MÀN thay vì tấm 480px lệch dần sang trái — ở màn hẹp không còn chỗ để
   *  thấy tấm bên dưới nhô ra, nên độ lệch (`right`) và bề rộng cố định đều
   *  vô nghĩa. */
  toanMan: boolean;
}

/** Drawer xếp chồng kiểu Payload (useEditDepth): tấm trên cùng nhận tiêu điểm, Esc đóng nó, nền mờ chung. */
export function NganXepDrawer({ ngan, onDong, render, toanMan }: Props) {
  const noiMo = useRef<HTMLElement | null>(null);
  const tamTrenCung = useRef<HTMLDivElement | null>(null);
  const soTang = ngan.length;

  useEffect(() => {
    if (soTang === 0) return;
    // Chỉ bắt nơi mở ở lần chuyển 0 → >0. Mở tấm thứ hai thì `activeElement`
    // là một nút BÊN TRONG tấm thứ nhất (sắp bị `inert`); đóng bớt một tấm thì
    // nó là `<body>` (nút của tấm vừa gỡ đã biến mất). Ghi đè trong cả hai
    // trường hợp làm mất đường về: `.focus()` trên `<body>` không làm gì, và
    // người dùng bàn phím bị bỏ ở đầu tài liệu.
    const dangGiu = document.activeElement;
    if (
      noiMo.current === null &&
      dangGiu instanceof HTMLElement &&
      !tamTrenCung.current?.contains(dangGiu)
    )
      noiMo.current = dangGiu;
    tamTrenCung.current?.querySelector<HTMLElement>("input, select, textarea, button")?.focus();
    const nghe = (e: KeyboardEvent) => {
      // Escape trong ô nhập là để đóng dropdown hay bỏ gõ, KHÔNG phải để vứt
      // phần đang sửa dở trong tấm (`DrawerSuaMuc` giữ `facts` ở state cục bộ,
      // không có nơi lưu). Cùng hai chốt như khung soạn thảo ở dung-thu.tsx.
      if (e.key === "Escape") {
        if (e.defaultPrevented) return;
        if (e.target instanceof HTMLElement && e.target.closest("input, textarea, select")) return;
        onDong();
      }
      if (e.key === "Tab" && tamTrenCung.current) {
        // Lọc `disabled` và phần tử đang ẩn: lúc đang lưu, hai control cuối
        // của `DrawerSuaMuc` (Huỷ `disabled`, Lưu) không giữ được tiêu điểm,
        // nên "phần tử cuối" tính theo selector thô không bao giờ khớp
        // `activeElement` và Tab đi thẳng ra ngoài tấm.
        const dong = Array.from(
          tamTrenCung.current.querySelectorAll<HTMLElement>(
            "input, select, textarea, button, a[href], [tabindex]:not([tabindex='-1'])",
          ),
        ).filter((el) => !el.hasAttribute("disabled") && el.offsetParent !== null);
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
    if (soTang !== 0) return;
    if (noiMo.current?.isConnected) noiMo.current.focus();
    noiMo.current = null; // đóng hết ⇒ quên nơi mở, lần mở sau bắt lại từ đầu
  }, [soTang]);

  if (soTang === 0) return null;
  return (
    <>
      {/* Trên `CuaSoTroLy` (z-50): cửa sổ trợ lý nổi cũng neo phải, cũng
          `fixed`, nên ở z-40 nó vẽ đè lên tấm drawer ĐANG MODAL và vẫn bấm
          được — nền mờ phải phủ cả nó. Ở bố cục hẹp, sân khấu (`z-50`,
          `fixed`) tự tạo ngữ cảnh xếp lớp và drawer nằm TRONG đó, nên hai số
          này chỉ so với nhau bên trong sân khấu, không đội lên trên nó. */}
      <div
        className="fixed inset-0 z-[60] bg-[var(--color-ink-950)]/30"
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
            style={{ right: toanMan ? 0 : (soTang - 1 - tang) * 24, zIndex: 61 + tang }}
            className={cn(
              "fixed inset-y-0 flex flex-col border-l border-border bg-card shadow-elegant",
              toanMan ? "w-full" : "w-[480px] max-w-full",
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
