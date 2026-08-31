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
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Toaster } from "@/components/ui/sonner";

import appCss from "../styles.css?url";

/**
 * Gốc tuyệt đối dùng cho canonical và JSON-LD. Ba chỗ trong bản Lovable ghim
 * cứng legal-buddy-ai-00.lovable.app, tức là mọi trang tự khai bản chính nằm
 * trên tên miền của Lovable. Đặt VITE_SITE_ORIGIN khi triển khai; mặc định là
 * localhost để không có tên miền nào bị khẳng định nhầm.
 */
export const SITE_ORIGIN = import.meta.env["VITE_SITE_ORIGIN"] ?? "http://localhost:3000";

/** Two primary weights per family only, display=swap. */
const FONT_CSS =
  "https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600&family=JetBrains+Mono:wght@400&family=Playfair+Display:wght@600;700&family=Source+Serif+4:ital,wght@0,400;0,600&display=swap";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">Không tìm thấy trang</h2>
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
        content: "Tra cứu pháp luật Việt Nam và soạn thảo văn bản pháp lý với trợ lý AI KLAW.",
      },
      { name: "author", content: "KLAW" },
      { property: "og:title", content: "KLAW — Trợ lý AI Pháp luật Việt Nam" },
      {
        property: "og:description",
        content: "Tra cứu pháp luật Việt Nam và soạn thảo văn bản pháp lý với trợ lý AI KLAW.",
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

/**
 * Thông báo chuyển tuyến cho trình đọc màn hình.
 *
 * Đây là ứng dụng một trang: đổi tuyến không tải lại trang, nên trình đọc màn
 * hình KHÔNG tự đọc gì cả. Người dùng bấm "Tra cứu luật" rồi ngồi im — không
 * có tín hiệu nào nói đã tới nơi. Vùng `aria-live` này là tín hiệu đó.
 *
 * Đọc `document.title` chứ không đọc đường dẫn: tiêu đề là câu người dùng hiểu
 * được, `/tra-cuu/$soHieu` thì không. Đợi một khung hình vì `HeadContent` của
 * tuyến mới đặt `document.title` ở cùng lượt commit, và đọc quá sớm sẽ lấy
 * nhầm tiêu đề của trang vừa rời.
 *
 * Nằm NGOÀI `<Outlet />` nên không bị gỡ mỗi lần đổi tuyến — một vùng
 * `aria-live` vừa được gắn vào DOM thì nội dung đầu tiên của nó không được
 * thông báo, và đó đúng là trường hợp ta cần thông báo.
 */
function ThongBaoChuyenTuyen({ pathname }: { pathname: string }) {
  const [loiNhan, datLoiNhan] = useState("");
  const tuyenDau = useRef(true);

  useEffect(() => {
    // Lần dựng đầu tiên là tải trang thật, trình duyệt đã tự đọc tiêu đề.
    if (tuyenDau.current) {
      tuyenDau.current = false;
      return;
    }
    const khung = requestAnimationFrame(() => {
      datLoiNhan(`Đã chuyển tới: ${document.title}`);
    });
    return () => cancelAnimationFrame(khung);
  }, [pathname]);

  return (
    <div aria-live="polite" role="status" className="sr-only">
      {loiNhan}
    </div>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <QueryClientProvider client={queryClient}>
      {/*
        Liên kết bỏ qua: người dùng bàn phím và trình đọc màn hình không phải
        Tab qua toàn bộ điều hướng ở MỌI trang trước khi tới nội dung. Mốc
        `#noi-dung-chinh` nằm trên <main> của cả ba vỏ trang.

        KHÔNG mang `inert` khi có khung modal: liên kết này nằm trước mọi thứ
        khác trong vòng Tab, nên nó không phải đường thoát ra khỏi modal — và
        một liên kết bỏ qua bị bịt lại thì tệ hơn là không có.
      */}
      <a href="#noi-dung-chinh" className="bo-qua-lien-ket">
        Bỏ qua để tới nội dung chính
      </a>
      <ThongBaoChuyenTuyen pathname={pathname} />
      {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
      <div key={pathname} className="route-enter">
        <Outlet />
      </div>
      <Toaster position="bottom-right" />
    </QueryClientProvider>
  );
}
