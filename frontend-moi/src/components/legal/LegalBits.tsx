import { Link } from "@tanstack/react-router";
import { FlaskConical, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { STATUS_LABEL, type DocStatus, type LegalDoc } from "@/lib/mock-legal";

export function MockDataBanner({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex items-start gap-2 border-b border-[var(--color-brass-500)]/35 bg-[var(--color-paper-100)] px-4 py-2 text-[12px] text-muted-foreground",
        className,
      )}
    >
      <FlaskConical className="mt-0.5 size-3.5 shrink-0 text-[var(--color-brass-600)]" />
      <p>
        <span className="font-semibold text-foreground">Dữ liệu minh hoạ.</span>{" "}
        Toàn bộ nội dung, số hiệu và trích dẫn trên trang dùng thử là ví dụ mô phỏng, chưa
        đồng bộ với cơ sở dữ liệu pháp luật chính thức.
      </p>
    </div>
  );
}

const STATUS_STYLE: Record<DocStatus, string> = {
  active:
    "border-[var(--color-status-active)]/45 text-[var(--color-status-active)] bg-[var(--color-status-active)]/10",
  partial:
    "border-[var(--color-status-partial)]/55 text-[var(--color-brass-600)] bg-[var(--color-status-partial)]/12",
  expired:
    "border-[var(--color-status-expired)]/45 text-[var(--color-status-expired)] bg-[var(--color-status-expired)]/10",
};

export function StatusBadge({ status }: { status: DocStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
        STATUS_STYLE[status],
      )}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {STATUS_LABEL[status]}
    </span>
  );
}

export function CitationChip({
  index,
  doc,
  label,
}: {
  index: number;
  doc: LegalDoc;
  label?: string;
}) {
  return (
    <Link
      to="/tra-cuu/$soHieu"
      params={{ soHieu: doc.soHieu }}
      title={`${doc.soHieu} — ${doc.ten}`}
      className="mx-0.5 inline-flex items-baseline gap-1 rounded-md border border-[var(--color-brass-500)]/45 bg-[var(--color-brass-500)]/10 px-1.5 py-px align-baseline font-sans text-[12px] font-medium text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/20"
    >
      <span className="font-mono text-[11px]">[{index}]</span>
      <span>{label ?? doc.soHieu}</span>
    </Link>
  );
}

export function SourceRow({ index, doc }: { index: number; doc: LegalDoc }) {
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-border/60 py-2.5 last:border-b-0">
      <span className="font-mono text-[12px] text-[var(--color-brass-600)]">
        {index}. {doc.soHieu}
      </span>
      <span className="text-sm font-medium text-foreground">{doc.ten}</span>
      <span className="text-[12px] text-muted-foreground">{doc.coQuan}</span>
      <span className="text-[12px] text-muted-foreground">· {doc.ngay}</span>
      <StatusBadge status={doc.status} />
      <Link
        to="/tra-cuu/$soHieu"
        params={{ soHieu: doc.soHieu }}
        className="ml-auto inline-flex items-center gap-1 text-[12px] font-medium text-primary hover:underline"
      >
        Xem toàn văn <ExternalLink className="size-3" />
      </Link>
    </li>
  );
}
