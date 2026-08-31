import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight,
  BookOpenText,
  ChevronDown,
  FileSignature,
  Gavel,
  Landmark,
  MessageSquareQuote,
  MousePointer2,
  Scale,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { HeroCanvas } from "@/components/three/HeroCanvas";
import { useMouseTilt } from "@/hooks/use-mouse-tilt";
import { ChatbotFab } from "@/components/ChatbotFab";
import { useReveal } from "@/hooks/use-reveal";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "KLAW — Trợ lý AI Pháp luật & Soạn thảo Văn bản Pháp lý" },
      {
        name: "description",
        content:
          "KLAW là trợ lý AI giúp tra cứu quy định pháp luật Việt Nam theo điều khoản và soạn thảo hợp đồng, đơn từ, công văn đúng thể thức trong vài giây.",
      },
      {
        property: "og:title",
        content: "KLAW — Trợ lý AI Pháp luật & Soạn thảo Văn bản Pháp lý",
      },
      {
        property: "og:description",
        content:
          "Tra cứu điều luật có dẫn chiếu và soạn thảo văn bản pháp lý chuẩn thể thức cùng trợ lý AI KLAW.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Landing,
});

const FEATURES = [
  {
    icon: Search,
    title: "Tra cứu theo điều khoản",
    desc: "Đặt câu hỏi bằng tiếng Việt tự nhiên, KLAW dẫn chiếu đúng điều, khoản, điểm và tên văn bản quy phạm pháp luật.",
  },
  {
    icon: FileSignature,
    title: "Soạn thảo tự động",
    desc: "Hợp đồng, đơn từ, công văn, thỏa thuận — đầy đủ quốc hiệu, căn cứ pháp lý, điều khoản và phần ký kết.",
  },
  {
    icon: MessageSquareQuote,
    title: "Giải thích dễ hiểu",
    desc: "Diễn giải điều luật phức tạp thành ngôn ngữ thường ngày, kèm ví dụ áp dụng thực tế.",
  },
  {
    icon: ShieldCheck,
    title: "Cảnh báo rủi ro",
    desc: "Chỉ ra điều khoản bất lợi, thời hạn bắt buộc và những nội dung cần cân nhắc trước khi ký.",
  },
  {
    icon: Landmark,
    title: "Thủ tục hành chính",
    desc: "Hướng dẫn từng bước hồ sơ, cơ quan tiếp nhận và thời hạn giải quyết theo quy định hiện hành.",
  },
  {
    icon: Users,
    title: "Dành cho mọi người",
    desc: "Phù hợp với luật sư, pháp chế doanh nghiệp, chủ doanh nghiệp nhỏ và cả người dân tra cứu quyền lợi.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Đặt câu hỏi hoặc yêu cầu",
    desc: "Mô tả tình huống của bạn, hoặc yêu cầu soạn một loại văn bản cụ thể.",
  },
  {
    n: "02",
    title: "KLAW phân tích & dẫn chiếu",
    desc: "Trợ lý xác định lĩnh vực pháp luật liên quan và trích dẫn quy định tương ứng.",
  },
  {
    n: "03",
    title: "Nhận kết quả hoàn chỉnh",
    desc: "Câu trả lời có dẫn chiếu, hoặc bản văn bản đúng thể thức, sẵn sàng để chỉnh sửa.",
  },
];

const AREAS = [
  "Dân sự",
  "Doanh nghiệp",
  "Lao động",
  "Đất đai & Nhà ở",
  "Hôn nhân & Gia đình",
  "Thuế",
  "Hành chính",
  "Hình sự",
  "Sở hữu trí tuệ",
  "Đầu tư",
  "Hợp đồng thương mại",
  "Bảo hiểm xã hội",
];

const FAQS = [
  {
    q: "KLAW có thay thế luật sư được không?",
    a: "Không. KLAW là công cụ hỗ trợ tra cứu và soạn thảo, giúp bạn tiết kiệm thời gian ở bước đầu. Với vụ việc phức tạp hoặc tranh chấp, bạn vẫn cần luật sư thẩm định.",
  },
  {
    q: "Văn bản do KLAW soạn có dùng ngay được không?",
    a: "Bản soạn tuân theo thể thức chuẩn và có căn cứ pháp lý, nhưng bạn cần điền thông tin các bên và rà soát lại nội dung điều khoản cho phù hợp với thỏa thuận thực tế.",
  },
  {
    q: "KLAW dựa trên nguồn nào?",
    a: "KLAW trả lời dựa trên hệ thống pháp luật Việt Nam và luôn nêu rõ tên văn bản, điều khoản để bạn tự kiểm chứng với văn bản gốc còn hiệu lực.",
  },
  {
    q: "Tôi có cần biết thuật ngữ pháp lý không?",
    a: "Không cần. Bạn cứ mô tả tình huống bằng lời thường ngày, KLAW sẽ hỏi thêm thông tin còn thiếu và diễn giải bằng ngôn ngữ dễ hiểu.",
  },
];

function Landing() {
  useReveal();
  useMouseTilt();

  return (
    <div className="min-h-screen bg-background">
      {/* ---------- Nav ---------- */}
      <header className="fixed inset-x-0 top-0 z-50 border-b border-border/60 bg-background/75 backdrop-blur-md">
        <nav className="mx-auto flex max-w-6xl items-center gap-3 px-5 py-3">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-xl bg-gradient-ink text-primary-foreground shadow-soft">
              <Scale className="size-4.5" />
            </span>
            <span className="font-display text-lg font-bold tracking-tight text-primary">
              KLAW
            </span>
          </Link>
          <div className="ml-auto hidden items-center gap-6 text-sm text-muted-foreground md:flex">
            <Link to="/tra-cuu" className="transition-colors hover:text-primary">
              Tra cứu luật
            </Link>
            <Link to="/soan-thao" className="transition-colors hover:text-primary">
              Soạn thảo
            </Link>
            <Link to="/huong-dan" className="transition-colors hover:text-primary">
              Hướng dẫn
            </Link>
            <a href="#tinh-nang" className="transition-colors hover:text-primary">
              Tính năng
            </a>
            <a href="#faq" className="transition-colors hover:text-primary">
              Hỏi đáp
            </a>
          </div>
          <div className="ml-auto flex items-center gap-2 md:ml-6">
            <Link
              to="/dang-nhap"
              className="hidden rounded-xl border border-border px-3.5 py-2 text-sm text-primary transition-colors hover:border-accent sm:inline-flex"
            >
              Đăng nhập
            </Link>
            <Link
              to="/chat"
              className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-soft transition-all hover:-translate-y-0.5 hover:shadow-elegant"
            >
              Dùng thử agent
              <ArrowRight className="size-4" />
            </Link>
          </div>
        </nav>
      </header>

      {/* ---------- Hero with interactive 3D ---------- */}
      <section className="relative flex min-h-[100svh] max-h-[1000px] items-center overflow-hidden pt-16">
        <div className="absolute inset-0">
          <HeroCanvas />
        </div>
        {/* readability veil, does not block the 3D pointer interaction */}
        <div
          className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background via-background/80 via-40% to-transparent md:bg-gradient-to-r md:via-background/85 md:via-45%"
          aria-hidden
        />

        <div className="pointer-events-none relative mx-auto w-full max-w-6xl px-5 pb-20">
          <div className="max-w-xl">
            <span className="pointer-events-auto inline-flex items-center gap-2 rounded-full border border-accent/50 bg-accent/15 px-3.5 py-1.5 text-xs font-medium text-accent-foreground">
              <Sparkles className="size-3.5" />
              Trợ lý AI pháp luật Việt Nam
            </span>

            <h1 className="mt-6 font-display text-[40px] leading-[1.05] font-bold tracking-tight text-primary md:text-6xl lg:text-7xl">
              Tra cứu pháp luật.
              <br />
              <span className="animate-shimmer bg-gradient-gold bg-clip-text text-transparent">
                Soạn thảo tức thì.
              </span>
            </h1>

            <p className="mt-6 max-w-lg text-base leading-relaxed text-muted-foreground sm:text-lg">
              KLAW đọc hiểu câu hỏi của bạn, dẫn chiếu đúng điều khoản trong hệ
              thống pháp luật Việt Nam và soạn thảo văn bản pháp lý chuẩn thể thức
              chỉ trong vài giây.
            </p>

            <div className="pointer-events-auto mt-9 flex flex-wrap items-center gap-3">
              <Link
                to="/chat"
                className="group relative inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3.5 text-sm font-semibold text-primary-foreground shadow-elegant transition-all hover:-translate-y-0.5"
              >
                Bắt đầu trò chuyện
                <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <a
                href="#tinh-nang"
                className="inline-flex items-center gap-2 rounded-xl border border-border bg-card/80 px-6 py-3.5 text-sm font-semibold text-primary backdrop-blur transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-soft"
              >
                <BookOpenText className="size-4" />
                Tìm hiểu thêm
              </a>
            </div>

            <div className="mt-10 flex flex-wrap gap-x-8 gap-y-3 text-sm">
              {[
                ["12+", "lĩnh vực pháp luật"],
                ["30+", "mẫu văn bản pháp lý"],
                ["< 10s", "cho một bản dự thảo"],
              ].map(([v, l]) => (
                <div key={l}>
                  <p className="font-display text-2xl font-bold text-primary">{v}</p>
                  <p className="text-xs text-muted-foreground">{l}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* interaction hint */}
        <div className="pointer-events-none absolute right-6 bottom-24 hidden items-center gap-2 rounded-full border border-border bg-card/85 px-4 py-2 text-xs text-muted-foreground shadow-soft backdrop-blur lg:flex">
          <MousePointer2 className="size-3.5 text-accent-foreground" />
          Kéo chuột để xoay và cuộn để phóng khung cảnh 3D
        </div>
        <div className="pointer-events-none absolute bottom-7 left-1/2 -translate-x-1/2 text-muted-foreground">
          <ChevronDown className="animate-scroll-hint size-5" />
        </div>
      </section>

      {/* ---------- Features ---------- */}
      <section id="tinh-nang" className="relative py-24">
        <div className="mx-auto max-w-6xl px-5">
          <div className="reveal mx-auto max-w-2xl text-center">
            <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent-foreground uppercase">
              Tính năng
            </p>
            <h2 className="mt-3 font-display text-3xl font-bold text-primary sm:text-4xl">
              Một trợ lý, trọn quy trình pháp lý
            </h2>
            <p className="mt-4 text-muted-foreground">
              Từ lúc bạn thắc mắc một quy định cho tới khi có bản thảo văn bản
              hoàn chỉnh trong tay.
            </p>
          </div>

          <div className="tilt-stage mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <article
                key={f.title}
                data-tilt
                className="reveal tilt-card rounded-2xl border border-border bg-card p-6 shadow-soft"
                data-reveal-delay={i * 70}
              >
                <span className="tilt-lift inline-flex size-11 items-center justify-center rounded-xl bg-gradient-ink text-primary-foreground shadow-soft">
                  <f.icon className="size-5" />
                </span>
                <h3 className="tilt-lift mt-5 font-display text-lg font-semibold text-primary">
                  {f.title}
                </h3>
                <p className="mt-2.5 text-sm leading-relaxed text-muted-foreground">
                  {f.desc}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- How it works ---------- */}
      <section id="quy-trinh" className="paper-texture border-y border-border py-24">
        <div className="mx-auto max-w-6xl px-5">
          <div className="reveal mx-auto max-w-2xl text-center">
            <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent-foreground uppercase">
              Quy trình
            </p>
            <h2 className="mt-3 font-display text-3xl font-bold text-primary sm:text-4xl">
              Ba bước tới câu trả lời
            </h2>
          </div>

          <div className="mt-14 grid gap-6 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <div
                key={s.n}
                className="reveal relative rounded-2xl border border-border bg-card p-7 shadow-soft"
                data-reveal-delay={i * 120}
              >
                <span className="animate-float-slow font-display bg-gradient-gold bg-clip-text text-5xl font-bold text-transparent">
                  {s.n}
                </span>
                <h3 className="mt-4 font-display text-lg font-semibold text-primary">
                  {s.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {s.desc}
                </p>
                {i < STEPS.length - 1 && (
                  <ArrowRight className="absolute top-1/2 -right-3 hidden size-6 text-accent md:block" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- Practice areas ---------- */}
      <section id="linh-vuc" className="py-24">
        <div className="mx-auto max-w-6xl px-5">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div className="reveal">
              <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent-foreground uppercase">
                Lĩnh vực
              </p>
              <h2 className="mt-3 font-display text-3xl font-bold text-primary sm:text-4xl">
                Bao phủ những lĩnh vực bạn cần nhất
              </h2>
              <p className="mt-4 leading-relaxed text-muted-foreground">
                KLAW được huấn luyện để làm việc với các nhóm quy định phổ biến
                nhất trong đời sống và hoạt động doanh nghiệp tại Việt Nam. Mỗi câu
                trả lời đều nêu rõ văn bản và điều khoản để bạn kiểm chứng.
              </p>
              <Link
                to="/chat"
                className="mt-8 inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground shadow-soft transition-all hover:-translate-y-0.5 hover:shadow-elegant"
              >
                <Gavel className="size-4" />
                Hỏi KLAW một câu
              </Link>
            </div>

            <ul className="-mx-5 flex snap-x snap-mandatory gap-2.5 overflow-x-auto px-5 pb-2 md:mx-0 md:flex-wrap md:overflow-visible md:px-0">
              {AREAS.map((a, i) => (
                <li
                  key={a}
                  className="reveal shrink-0 snap-start rounded-full border border-border bg-card px-4 py-2 text-sm whitespace-nowrap text-primary shadow-soft transition-all hover:-translate-y-0.5 hover:border-accent hover:bg-accent/10 md:shrink"
                  data-reveal-delay={i * 45}
                >
                  {a}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ---------- FAQ ---------- */}
      <section id="faq" className="paper-texture border-t border-border py-24">
        <div className="mx-auto max-w-3xl px-5">
          <div className="reveal text-center">
            <p className="font-display text-sm font-semibold tracking-[0.2em] text-accent-foreground uppercase">
              Hỏi đáp
            </p>
            <h2 className="mt-3 font-display text-3xl font-bold text-primary sm:text-4xl">
              Những câu hỏi thường gặp
            </h2>
          </div>

          <div className="mt-12 space-y-3">
            {FAQS.map((f, i) => (
              <details
                key={f.q}
                className="reveal group rounded-xl border border-border bg-card px-5 py-4 shadow-soft transition-colors open:border-accent"
                data-reveal-delay={i * 80}
              >
                <summary className="flex cursor-pointer list-none items-center gap-3 font-medium text-primary">
                  <span className="flex-1">{f.q}</span>
                  <ChevronDown className="size-4 shrink-0 transition-transform group-open:rotate-180" />
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  {f.a}
                </p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* ---------- CTA ---------- */}
      <section className="relative overflow-hidden py-24">
        <div className="mx-auto max-w-4xl px-5">
          <div className="reveal relative overflow-hidden rounded-3xl bg-gradient-ink px-8 py-16 text-center shadow-elegant">
            <span className="animate-pulse-ring absolute top-1/2 left-1/2 size-40 -translate-x-1/2 -translate-y-1/2 rounded-full border border-accent/40" />
            <span className="relative inline-flex size-14 items-center justify-center rounded-2xl bg-accent/20 text-accent shadow-gold">
              <Scale className="size-7" />
            </span>
            <h2 className="relative mt-6 font-display text-3xl font-bold text-primary-foreground sm:text-4xl">
              Sẵn sàng tra cứu và soạn thảo?
            </h2>
            <p className="relative mx-auto mt-4 max-w-lg text-sm leading-relaxed text-primary-foreground/75">
              Mở KLAW và đặt câu hỏi pháp lý đầu tiên của bạn. Không cần đăng ký,
              không cần thuật ngữ chuyên ngành.
            </p>
            <div className="relative mt-9 flex flex-wrap justify-center gap-3">
              <Link
                to="/chat"
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-gold px-7 py-3.5 text-sm font-bold text-accent-foreground shadow-gold transition-transform hover:-translate-y-0.5"
              >
                Trò chuyện với KLAW
                <ArrowRight className="size-4" />
              </Link>
              <Link
                to="/huong-dan"
                className="inline-flex items-center gap-2 rounded-xl border border-primary-foreground/30 px-7 py-3.5 text-sm font-semibold text-primary-foreground transition-colors hover:border-accent"
              >
                <BookOpenText className="size-4" />
                Xem hướng dẫn
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ---------- Footer ---------- */}
      <footer className="border-t border-border bg-card">
        <div className="mx-auto max-w-6xl px-5 py-10">
          <div className="flex flex-wrap items-center gap-4">
            <span className="flex size-9 items-center justify-center rounded-xl bg-gradient-ink text-primary-foreground">
              <Scale className="size-4.5" />
            </span>
            <div>
              <p className="font-display text-base font-bold text-primary">KLAW</p>
              <p className="text-xs text-muted-foreground">
                Trợ lý AI tra cứu pháp luật &amp; soạn thảo văn bản pháp lý
              </p>
            </div>
            <Link
              to="/chat"
              className="ml-auto text-sm font-medium text-primary underline-offset-4 hover:underline"
            >
              Mở trợ lý
            </Link>
          </div>
          <p className="mt-8 border-t border-border pt-6 text-xs leading-relaxed text-muted-foreground">
            ⚖️ KLAW cung cấp thông tin mang tính tham khảo, không thay thế tư vấn
            pháp lý của luật sư hoặc tổ chức hành nghề luật. Vui lòng đối chiếu với
            văn bản quy phạm pháp luật đang có hiệu lực trước khi sử dụng.
          </p>
        </div>
      </footer>

      <ChatbotFab />
    </div>
  );
}
