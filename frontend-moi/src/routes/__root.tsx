import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  useRouterState,

  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { type ReactNode } from "react";

import { Toaster } from "@/components/ui/sonner";

import appCss from "../styles.css?url";

/**
 * Gốc tuyệt đối dùng cho canonical và JSON-LD. Ba chỗ trong bản Lovable ghim
 * cứng legal-buddy-ai-00.lovable.app, tức là mọi trang tự khai bản chính nằm
 * trên tên miền của Lovable. Đặt VITE_SITE_ORIGIN khi triển khai; mặc định là
 * localhost để không có tên miền nào bị khẳng định nhầm.
 */
export const SITE_ORIGIN =
  import.meta.env["VITE_SITE_ORIGIN"] ?? "http://localhost:3000";

/** Two primary weights per family only, display=swap. */
const FONT_CSS =
  "https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600&family=JetBrains+Mono:wght@400&family=Playfair+Display:wght@600;700&family=Source+Serif+4:ital,wght@0,400;0,600&display=swap";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">
          Không tìm thấy trang
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Đường dẫn này không tồn tại hoặc đã được chuyển đi nơi khác.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Về trang chủ
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  const router = useRouter();

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          Trang không tải được
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Đã có lỗi ở phía KLAW. Bạn có thể thử lại hoặc quay về trang chủ.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Thử lại
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Về trang chủ
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "KLAW — Trợ lý AI Pháp luật Việt Nam" },
      {
        name: "description",
        content:
          "Tra cứu pháp luật Việt Nam và soạn thảo văn bản pháp lý với trợ lý AI KLAW.",
      },
      { name: "author", content: "KLAW" },
      { property: "og:title", content: "KLAW — Trợ lý AI Pháp luật Việt Nam" },
      {
        property: "og:description",
        content:
          "Tra cứu pháp luật Việt Nam và soạn thảo văn bản pháp lý với trợ lý AI KLAW.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
    links: [
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      {
        rel: "preconnect",
        href: "https://fonts.gstatic.com",
        crossOrigin: "anonymous",
      },
      {
        rel: "preload",
        as: "style",
        href: FONT_CSS,
      },
      { rel: "stylesheet", href: FONT_CSS },
      {
        rel: "stylesheet",
        href: appCss,
      },
      { rel: "icon", href: "/favicon.ico", type: "image/x-icon" },
    ],
    scripts: [
      {
        type: "application/ld+json",
        children: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "SoftwareApplication",
          name: "KLAW",
          applicationCategory: "BusinessApplication",
          operatingSystem: "Web",
          inLanguage: "vi-VN",
          url: SITE_ORIGIN + "/",
          description:
            "Trợ lý AI tra cứu pháp luật Việt Nam theo điều, khoản, điểm và soạn thảo văn bản pháp lý đúng thể thức.",
          offers: {
            "@type": "Offer",
            price: "0",
            priceCurrency: "VND",
            description: "Bản dùng thử miễn phí",
          },
        }),
      },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="vi">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <QueryClientProvider client={queryClient}>
      {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
      <div key={pathname} className="route-enter">
        <Outlet />
      </div>
      <Toaster position="bottom-right" />
    </QueryClientProvider>
  );
}

