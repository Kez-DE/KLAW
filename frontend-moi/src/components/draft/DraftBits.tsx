import { Link } from "@tanstack/react-router";
import { ChevronDown, Info } from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

export function BasisChip({
  soHieu,
  label,
}: {
  soHieu: string;
  label?: string;
}) {
  return (
    <Link
      to="/tra-cuu/$soHieu"
      params={{ soHieu }}
      title={soHieu}
      className="inline-flex items-baseline gap-1 rounded-md border border-[var(--color-brass-500)]/45 bg-[var(--color-brass-500)]/10 px-1.5 py-px font-sans text-[11px] font-medium text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/20"
    >
      <span className="font-jetbrains text-[10px]">{soHieu}</span>
      {label && <span>{label}</span>}
    </Link>
  );
}

export function fieldId(key: string) {
  return `f-${key}`;
}

export function focusField(key: string) {
  const el = document.getElementById(fieldId(key));
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  (el as HTMLElement).focus({ preventScroll: true });
}

const baseInput =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-[var(--color-brass-500)] focus:ring-2 focus:ring-[var(--color-brass-500)]/25";

export function Field({
  name,
  label,
  hint,
  children,
}: {
  name?: string;
  label: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <label className="block" htmlFor={name ? fieldId(name) : undefined}>
      <span className="mb-1 block text-[12.5px] font-medium text-foreground">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11.5px] text-muted-foreground">{hint}</span>}
    </label>
  );
}

export function TextField({
  name,
  label,
  value,
  onChange,
  placeholder,
  hint,
  type = "text",
}: {
  name: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  hint?: ReactNode;
  type?: string;
}) {
  return (
    <Field name={name} label={label} hint={hint}>
      <input
        id={fieldId(name)}
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={baseInput}
      />
    </Field>
  );
}

export function AreaField({
  name,
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
  action,
}: {
  name: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  action?: ReactNode;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-2">
        <label htmlFor={fieldId(name)} className="text-[12.5px] font-medium text-foreground">
          {label}
        </label>
        {action}
      </div>
      <textarea
        id={fieldId(name)}
        rows={rows}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={cn(baseInput, "resize-y leading-relaxed")}
      />
    </div>
  );
}

export function SelectField({
  name,
  label,
  value,
  onChange,
  options,
  hint,
  placeholder = "— Chọn —",
}: {
  name: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  hint?: ReactNode;
  placeholder?: string;
}) {
  return (
    <Field name={name} label={label} hint={hint}>
      <select
        id={fieldId(name)}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(baseInput, "appearance-none bg-background")}
      >
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function Group({
  title,
  right,
  defaultOpen = true,
  children,
}: {
  title: ReactNode;
  right?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-[var(--color-paper-50)]">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 text-left font-display text-[15px] font-bold text-primary"
        >
          <ChevronDown
            className={cn("size-4 text-[var(--color-brass-600)] transition-transform", !open && "-rotate-90")}
          />
          {title}
        </button>
        {right}
      </div>
      {open && <div className="space-y-3 p-4 soft-fade">{children}</div>}
    </section>
  );
}

export function InfoPopover({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label="Vì sao cần?"
        onClick={() => setOpen((v) => !v)}
        onBlur={() => setOpen(false)}
        className="inline-flex items-center gap-1 rounded-md border border-[var(--color-brass-500)]/45 px-1.5 py-px text-[11px] text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/12"
      >
        <Info className="size-3" /> Vì sao cần?
      </button>
      {open && (
        <span className="absolute top-full right-0 z-30 mt-1.5 w-64 rounded-lg border border-border bg-background p-3 text-[12px] leading-relaxed text-muted-foreground shadow-lg soft-fade">
          {children}
        </span>
      )}
    </span>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative h-5 w-9 shrink-0 rounded-full transition-colors",
        checked ? "bg-[var(--color-brass-500)]" : "bg-[var(--color-paper-200)]",
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 size-4 rounded-full bg-white shadow transition-all",
          checked ? "left-[18px]" : "left-0.5",
        )}
      />
    </button>
  );
}
