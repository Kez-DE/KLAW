import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  {
    icon: Search,
    title: "Tra cứu quy định",
    prompt:
      "Điều kiện để một hợp đồng dân sự có hiệu lực theo Bộ luật Dân sự 2015 là gì?",
  },
  {
    icon: FileSignature,
    title: "Soạn hợp đồng",
    prompt:
      "Soạn giúp tôi hợp đồng thuê nhà ở giữa cá nhân với cá nhân, thời hạn 12 tháng.",
  },
  {
    icon: Landmark,
    title: "Thủ tục hành chính",
    prompt:
      "Thủ tục thành lập công ty TNHH một thành viên theo Luật Doanh nghiệp 2020 gồm những bước nào?",
  },
  {
    icon: Gavel,
    title: "Soạn đơn / công văn",
    prompt:
      "Soạn giúp tôi đơn xin nghỉ việc theo đúng quy định Bộ luật Lao động 2019.",
  },
];

export function KlawChat() {
  const [input, setInput] = useState("");
  const transport = useMemo(
    () => new DefaultChatTransport({ api: "/api/chat" }),
    [],
  );
  const { messages, sendMessage, status, error } = useChat({ transport });
  const isBusy = status === "submitted" || status === "streaming";

  const scrollRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, status]);

  const submit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isBusy) return;
    setInput("");
    sendMessage({ text: trimmed });
  };

  return (
    <div className="flex h-dvh flex-col">
      <header className="border-b border-border bg-card/80 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center gap-3 px-4 py-3.5">
          <Link
            to="/"
            className="flex size-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-secondary hover:text-primary"
            aria-label="Về trang giới thiệu"
          >
            <ArrowLeft className="size-4" />
          </Link>
          <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <Scale className="size-5" />
          </div>
          <div>
            <h1 className="font-display text-xl font-bold tracking-tight text-primary">
              KLAW
            </h1>
            <p className="text-xs text-muted-foreground">
              Trợ lý AI tra cứu pháp luật &amp; soạn thảo văn bản pháp lý
            </p>
          </div>
          <div className="ml-auto hidden items-center gap-1.5 rounded-full border border-accent/50 bg-accent/15 px-3 py-1 text-xs font-medium text-accent-foreground sm:flex">
            <BookOpenText className="size-3.5" />
            Pháp luật Việt Nam
          </div>
        </div>
      </header>

      <div ref={scrollRef} className="paper-texture flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl px-4 py-6">
          {messages.length === 0 ? (
            <div className="animate-fade-up mx-auto mt-8 max-w-2xl text-center">
              <div className="mx-auto mb-5 flex size-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-md">
                <Scale className="size-8" />
              </div>
              <h2 className="font-display text-3xl font-bold text-primary">
                Xin chào, tôi là KLAW
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                Tôi giúp bạn tra cứu quy định pháp luật Việt Nam, giải thích điều
                khoản, và soạn thảo các văn bản pháp lý như hợp đồng, đơn từ, công
                văn. Hãy chọn một gợi ý bên dưới hoặc đặt câu hỏi của riêng bạn.
              </p>
              <div className="mt-8 grid gap-3 sm:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.title}
                    onClick={() => submit(s.prompt)}
                    className="group rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-accent hover:shadow-md"
                  >
                    <div className="flex items-center gap-2 text-primary">
                      <s.icon className="size-4" />
                      <span className="font-display text-sm font-semibold">
                        {s.title}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                      {s.prompt}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div
              aria-live="polite"
              aria-label="Hội thoại với KLAW"
              className="space-y-5 pb-4"
            >
              {messages.map((m) => {
                const isUser = m.role === "user";
                const text = m.parts
                  .filter((p) => p.type === "text")
                  .map((p) => p.text)
                  .join("");
                if (!text) return null;
                return (
                  <div
                    key={m.id}
                    className={cn(
                      "animate-fade-up flex",
                      isUser ? "justify-end" : "justify-start",
                    )}
                  >
                    <div
                      className={cn(
                        "max-w-[85%] rounded-2xl px-4 py-3 shadow-sm sm:max-w-[75%]",
                        isUser
                          ? "rounded-br-md bg-primary text-primary-foreground"
                          : "rounded-bl-md border border-border bg-card",
                      )}
                    >
                      {isUser ? (
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">
                          {text}
                        </p>
                      ) : (
                        <div className="chat-prose">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {text}
                          </ReactMarkdown>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {status === "submitted" && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-border bg-card px-4 py-3.5 shadow-sm">
                    <span className="thinking-dot size-1.5 rounded-full bg-primary" />
                    <span className="thinking-dot size-1.5 rounded-full bg-primary" />
                    <span className="thinking-dot size-1.5 rounded-full bg-primary" />
                  </div>
                </div>
              )}

              {error && (
                <div className="flex justify-center">
                  <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
                    Đã xảy ra lỗi khi kết nối AI. Vui lòng thử lại.
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

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
            disabled={isBusy || !input.trim()}
            className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-40"
            aria-label="Gửi"
          >
            <SendHorizonal className="size-4.5" />
          </button>
        </form>
        <p className="mx-auto max-w-4xl px-4 pb-3 text-center text-[11px] text-muted-foreground">
          ⚖️ KLAW cung cấp thông tin tham khảo, không thay thế tư vấn của luật
          sư. Vui lòng kiểm chứng văn bản pháp luật hiện hành.
        </p>
      </div>
    </div>
  );
}
