import { Link } from "@tanstack/react-router";
import { LogOut, Scale, UserRound } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/use-auth";

const LINKS = [
  { to: "/tra-cuu", label: "Tra cứu luật" },
  { to: "/soan-thao", label: "Soạn thảo" },
  { to: "/huong-dan", label: "Hướng dẫn" },
  { to: "/chat", label: "Trò chuyện" },
] as const;

export function AppNav({ active }: { active?: string }) {
  const { user, signOut } = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/85 backdrop-blur-md">
      <nav className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3">
        <Link to="/" className="flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-xl bg-gradient-ink text-primary-foreground shadow-soft">
            <Scale className="size-4.5" />
          </span>
          <span className="font-display text-lg font-bold tracking-tight text-primary">
            KLAW
          </span>
        </Link>
        <div className="ml-auto flex items-center gap-1 overflow-x-auto text-sm">
          {LINKS.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              className={cn(
                "shrink-0 rounded-lg px-3 py-1.5 transition-colors",
                active === l.to
                  ? "bg-secondary font-medium text-primary"
                  : "text-muted-foreground hover:text-primary",
              )}
            >
              {l.label}
            </Link>
          ))}
          {user ? (
            <button
              onClick={() => signOut()}
              className="ml-1 inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-primary"
              title={user.email ?? undefined}
            >
              <LogOut className="size-3.5" />
              Đăng xuất
            </button>
          ) : (
            <Link
              to="/dang-nhap"
              className="ml-1 inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground shadow-soft transition-opacity hover:opacity-90"
            >
              <UserRound className="size-3.5" />
              Đăng nhập
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
