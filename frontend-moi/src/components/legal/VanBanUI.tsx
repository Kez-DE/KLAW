import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/utils";

// StatusBadge đã bị xoá cùng `TinhTrang` — xem ghi chú trong `lib/van-ban.ts`.
// Nhãn hiệu lực duy nhất của ứng dụng là `components/klaw/BadgeHieuLuc.tsx`,
// và nguồn duy nhất của nó là `GET /van-ban/{doc_id}/hieu-luc`.
import { boDau, moRongTruyVan } from "@/lib/van-ban";

/** Tô sáng cụm từ khớp (không phân biệt dấu) với nền brass-300 ~25%. */
export function Highlight({ text, query }: { text: string; query: string }): ReactNode {
  const terms = moRongTruyVan(query)
    .filter((t) => t.length >= 2)
    .sort((a, b) => b.length - a.length);
  if (!terms.length) return text;

  const flat = boDau(text);
  type Span = [number, number];
  const spans: Span[] = [];
  for (const t of terms) {
    let i = flat.indexOf(t);
    while (i !== -1) {
      spans.push([i, i + t.length]);
      i = flat.indexOf(t, i + t.length);
    }
  }
  if (!spans.length) return text;
  spans.sort((a, b) => a[0] - b[0]);
  const merged: Span[] = [];
  for (const s of spans) {
    const last = merged[merged.length - 1];
    if (last && s[0] <= last[1]) last[1] = Math.max(last[1], s[1]);
    else merged.push([s[0], s[1]]);
  }

  const out: ReactNode[] = [];
  let cur = 0;
  merged.forEach(([a, b], k) => {
    if (a > cur) out.push(<Fragment key={`t${k}`}>{text.slice(cur, a)}</Fragment>);
    out.push(
      <mark
        key={`m${k}`}
        className="rounded-[2px] bg-[var(--color-brass-400)]/25 px-0.5 text-inherit"
      >
        {text.slice(a, b)}
      </mark>,
    );
    cur = b;
  });
  if (cur < text.length) out.push(<Fragment key="tail">{text.slice(cur)}</Fragment>);
  return out;
}

export function Chip({
  children,
  onRemove,
  onClick,
}: {
  children: ReactNode;
  onRemove?: () => void;
  onClick?: () => void;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-[var(--color-brass-500)]/50 bg-[var(--color-brass-500)]/10 px-2.5 py-1 text-[12px] text-[var(--color-brass-600)] transition-colors",
        onClick && "cursor-pointer hover:bg-[var(--color-brass-500)]/20",
      )}
      onClick={onClick}
    >
      {children}
      {onRemove && (
        <button
          type="button"
          aria-label="Bỏ"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="text-[var(--color-brass-600)]/70 hover:text-[var(--color-brass-600)]"
        >
          ×
        </button>
      )}
    </span>
  );
}
