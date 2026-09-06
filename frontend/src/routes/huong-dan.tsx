import { createFileRoute, Link } from "@tanstack/react-router";
import {
  ArrowRight,
  BadgeCheck,
  BookOpenText,
  CircleAlert,
  FileSignature,
  MessageSquareQuote,
  Search,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { AppNav } from "@/components/AppNav";
import { ChatbotFab } from "@/components/ChatbotFab";
import { useReveal } from "@/hooks/use-reveal";

const STEPS = [
  {
    icon: MessageSquareQuote,
    title: "1. Mô tả tình huống thật của bạn",
    body: "Không cần dùng thuật ngữ pháp lý. Hãy kể bối cảnh: bạn là ai trong quan hệ đó, chuyện gì đã xảy ra, thời điểm nào, bạn muốn đạt được gì.",
    good: "Tôi ký hợp đồng lao động 12 tháng từ tháng 3/2025, công ty muốn chuyển tôi sang vị trí khác và giảm lương. Tôi có quyền từ chối không?",
    bad: "Luật lao động?",
  },
  {
    icon: Search,
    title: "2. Nêu rõ điều, khoản hoặc số hiệu nếu đã biết",
    body: "Khi cần đúng nguyên văn, hãy dùng trang Tra cứu và ghi rõ điều/khoản kèm tên văn bản và năm ban hành. Có thể viết không dấu.",
    good: "Khoản 2 Điều 468 Bộ luật Dân sự 2015",
    bad: "điều 468 là gì",
  },
  {
    icon: FileSignature,
    title: "3. Cung cấp dữ kiện khi cần soạn văn bản",
    body: "Trang Soạn thảo có sẵn form: chọn loại văn bản rồi điền các bên, giá trị, thời hạn, phương thức thanh toán. Ô nào chưa biết cứ để trống, KLAW sẽ chừa […] và nhắc bạn bổ sung.",
    good: "Hợp đồng dịch vụ, phí 30 triệu, tiến độ 2 giai đoạn, thanh toán 50/50",
    bad: "soạn hợp đồng giúp tôi",
  },
  {
    icon: BadgeCheck,
    title: "4. Kiểm chứng và tinh chỉnh",
    body: "Đối chiếu điều khoản KLAW dẫn chiếu với văn bản gốc còn hiệu lực, rồi yêu cầu chỉnh sửa tiếp trong cùng cuộc trò chuyện: thêm điều khoản phạt, đổi thời hạn, viết ngắn gọn hơn…",
    good: "Thêm điều khoản phạt vi phạm 8% giá trị hợp đồng và điều khoản bất khả kháng",
    bad: "sửa lại đi",
  },
];

const PROMPTS = [
  {
    group: "Tra cứu & giải thích",
    items: [
      "Điều kiện để hợp đồng dân sự có hiệu lực theo Bộ luật Dân sự 2015?",
      "Người lao động đơn phương chấm dứt hợp đồng cần báo trước bao nhiêu ngày?",
      "Giải thích Khoản 1 Điều 117 Bộ luật Dân sự 2015 bằng ví dụ thực tế.",
    ],
  },
  {
    group: "Soạn thảo",
    items: [
      "Soạn hợp đồng thuê nhà 12 tháng, giá 10 triệu/tháng, cọc 1 tháng.",
      "Soạn đơn xin nghỉ việc đúng thời hạn báo trước theo Bộ luật Lao động 2019.",
      "Soạn thỏa thuận bảo mật giữa hai công ty, thời hạn 3 năm.",
    ],
  },
  {
    group: "Rà soát & rủi ro",
    items: [
      "Rà soát điều khoản sau và chỉ ra rủi ro cho bên thuê: […]",
      "So sánh hợp đồng dịch vụ và hợp đồng lao động trong trường hợp của tôi.",
      "Những mốc thời hạn bắt buộc tôi cần lưu ý khi khởi kiện tranh chấp hợp đồng?",
    ],
  },
];

function Guide() {
  useReveal();

  return (
    <div className="min-h-screen bg-background">
      <AppNav active="/huong-dan" />

      <header className="paper-texture border-b border-border">
        <div className="mx-auto max-w-4xl px-4 py-14 text-center">
          <span className="animate-fade-up inline-flex items-center gap-2 rounded-full border border-accent/50 bg-accent/15 px-3.5 py-1.5 text-xs font-medium text-accent-foreground">
            <Sparkles className="size-3.5" />
            Dành cho người mới
          </span>
          <h1 className="animate-fade-up mt-5 font-display text-4xl font-bold tracking-tight text-primary sm:text-5xl">
            Hướng dẫn sử dụng KLAW
          </h1>
          <p className="animate-fade-up mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
            Từ cách đặt câu hỏi cho đúng, cách tra cứu theo điều khoản, đến cách để KLAW soạn một
            văn bản pháp lý hoàn chỉnh — tất cả trong 4 bước.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link
              to="/dung-thu"
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground shadow-elegant transition-all hover:-translate-y-0.5"
            >
              Mở trợ lý KLAW
              <ArrowRight className="size-4" />
            </Link>
            <Link
              to="/tra-cuu"
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-5 py-3 text-sm font-semibold text-primary shadow-soft transition-all hover:-translate-y-0.5 hover:border-accent"
            >
              <BookOpenText className="size-4" />
              Mở trang tra cứu
            </Link>
          </div>
        </div>
      </header>

      <main id="noi-dung-chinh" className="mx-auto max-w-4xl px-4 py-14">
        <section className="space-y-5">
          {STEPS.map((s, i) => (
            <article
              key={s.title}
              className="reveal rounded-2xl border border-border bg-card p-6 shadow-soft"
              data-reveal-delay={i * 80}
            >
              <div className="flex items-start gap-4">
                <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-gradient-ink text-primary-foreground shadow-soft">
                  <s.icon className="size-5" />
                </span>
                <div>
                  <h2 className="font-display text-lg font-semibold text-primary">{s.title}</h2>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.body}</p>
                </div>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-accent/40 bg-accent/10 p-3.5">
                  <p className="flex items-center gap-1.5 text-xs font-semibold text-accent-foreground">
                    <ThumbsUp className="size-3.5" />
                    Nên viết như vậy
                  </p>
                  <p className="mt-1.5 text-sm text-primary">“{s.good}”</p>
                </div>
                <div className="rounded-xl border border-border bg-muted/60 p-3.5">
                  <p className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                    <ThumbsDown className="size-3.5" />
                    Nên tránh
                  </p>
                  <p className="mt-1.5 text-sm text-muted-foreground">“{s.bad}”</p>
                </div>
              </div>
            </article>
          ))}
        </section>

        <section className="mt-16">
          <h2 className="reveal font-display text-2xl font-bold text-primary">
            Mẫu câu hỏi bạn có thể dùng ngay
          </h2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {PROMPTS.map((p, i) => (
              <div
                key={p.group}
                className="reveal rounded-2xl border border-border bg-card p-5 shadow-soft"
                data-reveal-delay={i * 90}
              >
                <p className="font-display text-sm font-semibold text-accent-foreground uppercase">
                  {p.group}
                </p>
                <ul className="mt-3 space-y-2.5 text-sm leading-relaxed text-muted-foreground">
                  {p.items.map((it) => (
                    <li key={it} className="border-l-2 border-accent/40 pl-3">
                      {it}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>

        <section className="reveal mt-16 rounded-2xl border border-border bg-card p-6 shadow-soft">
          <h2 className="flex items-center gap-2 font-display text-xl font-bold text-primary">
            <CircleAlert className="size-5 text-accent-foreground" />
            Ba điều cần nhớ
          </h2>
          <ul className="mt-4 space-y-3 text-sm leading-relaxed text-muted-foreground">
            <li>
              <strong className="text-primary">Luôn kiểm chứng dẫn chiếu.</strong> Văn bản pháp luật
              có thể đã được sửa đổi, bổ sung hoặc bãi bỏ — hãy đối chiếu điều khoản KLAW nêu với
              bản gốc còn hiệu lực.
            </li>
            <li>
              <strong className="text-primary">Bản thảo cần rà soát.</strong> Văn bản KLAW soạn đúng
              thể thức, nhưng nội dung điều khoản phải khớp với thỏa thuận thực tế của các bên.
            </li>
            <li>
              <strong className="text-primary">Không thay thế luật sư.</strong> Với tranh chấp, tố
              tụng hoặc giao dịch giá trị lớn, hãy để luật sư thẩm định trước khi quyết định.
            </li>
          </ul>
        </section>

        <div className="reveal mt-14 flex flex-wrap justify-center gap-3">
          <Link
            to="/soan-thao"
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground shadow-soft transition-all hover:-translate-y-0.5 hover:shadow-elegant"
          >
            <FileSignature className="size-4" />
            Bắt đầu soạn văn bản
          </Link>
          <Link
            to="/dang-nhap"
            className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-5 py-3 text-sm font-semibold text-primary shadow-soft transition-all hover:-translate-y-0.5 hover:border-accent"
          >
            Đăng nhập để lưu phiên
          </Link>
        </div>
      </main>
      <ChatbotFab />
    </div>
  );
}

export const Route = createFileRoute("/huong-dan")({
  head: () => ({
    meta: [
      { title: "Hướng dẫn sử dụng KLAW cho người mới" },
      {
        name: "description",
        content:
          "Cách đặt câu hỏi pháp luật đúng cách, tra cứu theo điều khoản và yêu cầu KLAW soạn thảo văn bản pháp lý hoàn chỉnh — hướng dẫn 4 bước kèm mẫu câu hỏi.",
      },
      { property: "og:title", content: "Hướng dẫn sử dụng KLAW cho người mới" },
      {
        property: "og:description",
        content: "Bốn bước từ câu hỏi đầu tiên đến bản thảo văn bản pháp lý hoàn chỉnh cùng KLAW.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Guide,
});
