import { Link } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";
import { ArrowLeft, Scale } from "lucide-react";
import { AuthBackdrop } from "@/components/three/AuthBackdrop";

const QUOTES = [
  {
    text: "Trước đây tôi mất cả buổi để đối chiếu hiệu lực một nghị định. Giờ là hai phút.",
    who: "Trưởng phòng Pháp chế, doanh nghiệp sản xuất (nhân vật minh họa)",
  },
  {
    text: "Điều tôi cần không phải là câu trả lời chung chung, mà là trích dẫn đúng tới từng điểm, khoản.",
    who: "Luật sư cộng sự, công ty luật tại Hà Nội (nhân vật minh họa)",
  },
  {
    text: "Bản hợp đồng đầu tiên vẫn phải rà lại, nhưng tôi bắt đầu từ một dự thảo đúng thể thức.",
    who: "Chủ doanh nghiệp nhỏ, lĩnh vực thương mại (nhân vật minh họa)",
  },
];

// "Cập nhật hằng ngày" đã gỡ: kho văn bản là một ảnh chụp tĩnh, không có
// đường cập nhật hằng ngày nào. Hai mục còn lại vẫn kèm dòng miễn trừ ngay
// bên dưới, nói rõ đây là định hướng chứ không phải cam kết dịch vụ.
const STATS = ["Trích dẫn tới cấp Điểm, Khoản, Điều", "Hạ tầng đặt tại Việt Nam"];

function QuoteRotator() {
  const [i, setI] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setI((v) => (v + 1) % QUOTES.length), 6000);
    return () => clearInterval(id);
  }, []);

  const q = QUOTES[i] ?? QUOTES[0]!;

  return (
    <div className="min-h-[190px]">
      <div key={i} className="quote-slide">
        <p className="font-display text-2xl leading-snug text-primary md:text-[28px]">“{q.text}”</p>
        <p className="mt-4 text-[13px] leading-relaxed text-muted-foreground">— {q.who}</p>
      </div>
      <div className="mt-6 flex gap-1.5" aria-hidden>
        {QUOTES.map((_, idx) => (
          <span
            key={idx}
            className={`h-px w-8 transition-colors duration-500 ${
              idx === i ? "bg-brass-500" : "bg-border"
            }`}
          />
        ))}
      </div>
    </div>
  );
}

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <AuthBackdrop />

      {/* Marketing shell header: wordmark only */}
      <header className="absolute inset-x-0 top-0 z-20 flex items-center justify-between px-6 py-6 md:px-10">
        <Link to="/" className="focus-brass flex items-center gap-2.5 rounded-md">
          <span className="grid size-9 place-items-center rounded-lg bg-brass-500/20 text-brass-600">
            <Scale className="size-4.5" />
          </span>
          <span className="font-display text-xl tracking-wide text-primary">KLAW</span>
        </Link>
        <Link
          to="/"
          className="focus-brass inline-flex items-center gap-2 rounded-md text-[13px] text-muted-foreground transition-colors hover:text-brass-600"
        >
          <ArrowLeft className="size-3.5" />
          Quay lại trang chủ
        </Link>
      </header>

      <div className="relative z-10 grid min-h-screen lg:grid-cols-[45fr_55fr]">
        {/* LEFT */}
        <aside className="relative hidden lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col lg:justify-between lg:px-14 lg:py-16">
          <div className="relative h-9" />
          <div className="relative max-w-md">
            <QuoteRotator />
          </div>
          <div className="relative grid grid-cols-3 gap-6 border-t border-border/70 pt-8">
            {STATS.map((s, i) => (
              <div key={s}>
                <p className="font-display text-lg text-brass-600">
                  {String(i + 1).padStart(2, "0")}
                </p>
                <p className="mt-1 text-[13px] leading-snug text-muted-foreground">{s}</p>
              </div>
            ))}
            <p className="col-span-3 text-[11px] text-muted-foreground">
              Các mục trên mang tính minh họa cho định hướng sản phẩm, không phải cam kết dịch vụ.
            </p>
          </div>
        </aside>

        {/* RIGHT */}
        <main
          id="noi-dung-chinh"
          className="flex items-center justify-center px-6 pt-28 pb-16 md:px-10"
        >
          <div className="w-full max-w-[440px] rounded-2xl border border-border/70 bg-card/85 p-6 shadow-soft backdrop-blur-xl md:p-8">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
