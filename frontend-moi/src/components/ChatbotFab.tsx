import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { MessageCircle, X, Scale, Search, FileSignature } from "lucide-react";

const QUICK = [
  { to: "/chat", icon: Scale, label: "Hỏi KLAW ngay" },
  { to: "/tra-cuu", icon: Search, label: "Tra cứu điều luật" },
  { to: "/soan-thao", icon: FileSignature, label: "Soạn văn bản" },
] as const;

export function ChatbotFab() {
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed right-5 bottom-5 z-50 flex flex-col items-end gap-3">
      {open && (
        <div className="animate-fade-up w-64 rounded-2xl border border-border bg-card p-3 shadow-elegant">
          <p className="px-1 pb-2 font-display text-sm font-semibold text-primary">
            Trợ lý KLAW
          </p>
          <div className="space-y-1.5">
            {QUICK.map((q) => (
              <Link
                key={q.to}
                to={q.to}
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-xl border border-transparent px-3 py-2 text-sm text-muted-foreground transition-colors hover:border-accent hover:bg-secondary hover:text-primary"
              >
                <q.icon className="size-4" />
                {q.label}
              </Link>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Mở trợ lý KLAW"
        className="relative flex size-14 items-center justify-center rounded-full bg-gradient-ink text-primary-foreground shadow-elegant transition-transform hover:scale-105"
      >
        <span className="animate-pulse-ring absolute inset-0 rounded-full border border-accent/60" />
        {open ? (
          <X className="relative size-6" />
        ) : (
          <MessageCircle className="relative size-6" />
        )}
      </button>
    </div>
  );
}
