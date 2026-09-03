import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import {
  ArrowLeft,
  BookOpenText,
  FileSignature,
  Landmark,
  Scale,
  Search,
  SendHorizonal,
  Gavel,
} from "lucide-react";

// `/chat` là CỬA VÀO, không phải một màn hỏi thứ hai.
//
// Bản Lovable gọi `/api/chat` — một lượt LLM trần, không truy hồi, không kiểm
// chứng nguồn. Route đó đã bị xoá cùng `ai-gateway.server.ts`. Ở pha nối
// backend, câu hỏi gõ ở đây được giao cho `/dung-thu`, nơi có đủ SSE, bốn
// `result_type`, nhãn hiệu lực và khung đối chiếu nguyên văn.
//
// Dựng một dòng hội thoại thứ hai ở đây sẽ là hai bản cài đặt của cùng một
// việc, và bản nào cũng có thể quên một trong bốn nhánh kết quả. Một cửa vào
// thì không quên được gì.

const SUGGESTIONS = [
  {
    icon: Search,
    title: "Tra cứu quy định",
    prompt: "Thời gian thử việc tối đa với công việc của người quản lý doanh nghiệp là bao lâu?",
  },
  {
    icon: FileSignature,
    title: "Soạn hợp đồng",
    prompt:
      "Soạn giúp tôi hợp đồng lao động xác định thời hạn 12 tháng cho vị trí nhân viên kinh doanh.",
  },
  {
    icon: Landmark,
    title: "Nghĩa vụ của người sử dụng lao động",
    prompt:
      "Người sử dụng lao động phải báo trước bao nhiêu ngày khi đơn phương chấm dứt hợp đồng lao động?",
  },
  {
    icon: Gavel,
    title: "Soạn đơn",
    prompt:
      "Soạn giúp tôi đơn xin nghỉ việc theo đúng thời hạn báo trước của Bộ luật Lao động 2019.",
  },
];

export function KlawChat() {
  const [input, setInput] = useState("");
  const dieuHuong = useNavigate();

  const submit = (text: string) => {
    const cauHoi = text.trim();
    if (cauHoi === "") return;
    void dieuHuong({ to: "/dung-thu", search: { q: cauHoi } });
  };

  return (
    <div className="flex h-dvh flex-col">
      <header className="border-b border-border bg-card/80 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center gap-3 px-4 py-3.5">
          <Link
            to="/"
            className="focus-brass flex size-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-secondary hover:text-primary"
            aria-label="Về trang giới thiệu"
          >
            <ArrowLeft className="size-4" />
          </Link>
          <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <Scale className="size-5" />
          </div>
          <div>
            <h1 className="font-display text-xl font-bold tracking-tight text-primary">KLAW</h1>
            <p className="text-xs text-muted-foreground">
              Trợ lý tra cứu pháp luật lao động &amp; soạn thảo văn bản
            </p>
          </div>
          <div className="ml-auto hidden items-center gap-1.5 rounded-full border border-border bg-secondary px-3 py-1 text-xs font-medium text-muted-foreground sm:flex">
            <BookOpenText className="size-3.5" />
            Pháp luật Việt Nam
          </div>
        </div>
      </header>

      <main id="noi-dung-chinh" className="paper-texture flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-4 py-6">
          <div className="animate-fade-up mx-auto mt-8 max-w-2xl text-center">
            <div className="mx-auto mb-5 flex size-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-md">
              <Scale className="size-8" />
            </div>
            <h2 className="font-display text-3xl font-bold text-primary">Xin chào, tôi là KLAW</h2>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Tôi tra cứu quy định pháp luật lao động Việt Nam theo điều, khoản, điểm và soạn thảo
              văn bản pháp lý. Mỗi câu trả lời nêu rõ văn bản và điều khoản để bạn tự kiểm chứng.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s.title}
                  type="button"
                  onClick={() => setInput(s.prompt)}
                  className="focus-brass group cursor-pointer rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-all duration-150 hover:-translate-y-1 hover:border-[var(--color-brass-500)]/60 hover:shadow-lg motion-reduce:hover:translate-y-0"
                >
                  <div className="flex items-center gap-2 text-primary">
                    <s.icon className="size-4" />
                    <span className="font-display text-sm font-semibold">{s.title}</span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                    {s.prompt}
                  </p>
                </button>
              ))}
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Chọn một gợi ý để điền vào ô soạn bên dưới.
            </p>
          </div>
        </div>
      </main>

      <div className="border-t border-border bg-card/90 backdrop-blur">
        <form
          className="mx-auto flex max-w-4xl items-end gap-2 px-4 py-3.5"
          onSubmit={(e) => {
            e.preventDefault();
            submit(input);
          }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit(input);
              }
            }}
            rows={1}
            placeholder="Hỏi về quy định pháp luật hoặc yêu cầu soạn văn bản…"
            className="max-h-36 min-h-11 flex-1 resize-none rounded-xl border border-input bg-background px-4 py-3 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/20"
          />
          <button
            type="submit"
            disabled={!input.trim()}
            className="focus-brass flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-40"
            aria-label="Gửi"
          >
            <SendHorizonal className="size-4.5" />
          </button>
        </form>
        <p className="mx-auto max-w-4xl px-4 pt-1.5 pb-3 text-center text-[11px] text-muted-foreground">
          KLAW cung cấp thông tin tham khảo, không thay thế tư vấn của luật sư. Vui lòng kiểm chứng
          với văn bản quy phạm pháp luật đang có hiệu lực.
        </p>
      </div>
    </div>
  );
}
