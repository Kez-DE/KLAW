import { useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { X } from "lucide-react";

const NHAN_TIEU_DIEM =
  'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * Sheet trượt lên từ đáy — cùng khuôn ngăn kéo bộ lọc của trang Tra cứu.
 *
 * Khai `aria-modal` nên `useKhungModalDangMo` tự gỡ cột trái, thanh trên và
 * thanh dưới khỏi vòng Tab trong lúc sheet mở. Nhưng chính vì thế, nút mở sheet
 * (nằm trên hai thanh ấy) BỊ `inert` ngay khi sheet mở và tiêu điểm của nó rơi
 * xuống `<body>` — người dùng bàn phím mất chỗ đứng. Nên sheet tự kéo tiêu điểm
 * vào tấm nền khi mở và trả về nút cũ khi đóng, sau một khung hình để `inert`
 * kịp được gỡ.
 *
 * `inert` cũng KHÔNG với tới `<main>`, và không được phép với tới: khung đối
 * chiếu của `KhungDoiChieu` sống trong đó. Nên Tab từ mục cuối trong sheet sẽ đi
 * thẳng ra trang đang nằm sau lớp phủ, và vòng Tab dưới đây là thứ khép lại chỗ
 * hở đó — bẫy tiêu điểm phải dựng tay đúng một lần, ở ngay đây.
 */
export function SheetDuoi({
  id,
  nhan,
  onDong,
  children,
}: {
  id: string;
  nhan: string;
  onDong: () => void;
  children: ReactNode;
}) {
  const nen = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const truoc = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    nen.current?.focus();
    return () => {
      requestAnimationFrame(() => truoc?.focus());
    };
  }, []);

  useEffect(() => {
    const nghe = (su: globalThis.KeyboardEvent) => {
      if (su.key === "Escape") onDong();
    };
    window.addEventListener("keydown", nghe);
    return () => window.removeEventListener("keydown", nghe);
  }, [onDong]);

  const bayTab = (su: KeyboardEvent<HTMLDivElement>) => {
    if (su.key !== "Tab") return;
    const moc = Array.from(nen.current?.querySelectorAll<HTMLElement>(NHAN_TIEU_DIEM) ?? []);
    const dau = moc[0];
    const cuoi = moc[moc.length - 1];
    if (dau === undefined || cuoi === undefined) return;
    // Lùi từ mục đầu (hoặc từ chính tấm nền, chỗ tiêu điểm đứng lúc vừa mở) thì
    // vòng xuống cuối; tiến từ mục cuối thì vòng lên đầu.
    const dangO = document.activeElement;
    const oBienLui = dangO === dau || dangO === nen.current;
    if (su.shiftKey ? oBienLui : dangO === cuoi) {
      su.preventDefault();
      (su.shiftKey ? cuoi : dau).focus();
    }
  };

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-[var(--color-ink-950)]/45" onClick={onDong} aria-hidden />
      <div
        ref={nen}
        id={id}
        role="dialog"
        aria-modal="true"
        aria-label={nhan}
        tabIndex={-1}
        onKeyDown={bayTab}
        className="rise-in focus:outline-none absolute inset-x-0 bottom-0 max-h-[82vh] overflow-y-auto rounded-t-2xl border-t border-border bg-background px-4 pt-4 pb-8"
      >
        <div className="mb-2 flex items-center justify-between">
          <p className="font-display m-0 text-sm font-semibold text-primary">{nhan}</p>
          <button
            type="button"
            onClick={onDong}
            aria-label={`Đóng ${nhan}`}
            className="focus-brass grid size-11 cursor-pointer place-items-center rounded-md text-muted-foreground hover:text-foreground"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
