import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChevronRight, Paperclip, Plug, Scale, Send } from "lucide-react";
import { AppShell } from "@/components/app/AppShell";
import { ChuaNoiBanner } from "@/components/legal/LegalBits";
import { cn } from "@/lib/utils";

// Pha 0 của bản port: màn dùng thử KHÔNG trả lời.
//
// Bản Lovable chở bốn câu trả lời đóng hộp khớp bằng regex, phát ra từng token
// một qua setInterval 28ms để trông như đang suy nghĩ, kèm chip trích dẫn và
// bảng nguồn dựng sẵn. Một trong bốn câu dẫn Nghị định 13/2023/NĐ-CP như luật
// đang điều chỉnh, gắn nhãn "Còn hiệu lực" — nghị định đó đã hết hiệu lực toàn
// bộ từ 01/01/2026.
//
// Đó không phải bản demo, đó là bằng chứng giả. Toàn bộ đã bị xoá và KHÔNG được
// thay bằng một bộ khác. Màn hình giữ nguyên bố cục để pha nối FE có chỗ đặt
// bốn nhánh result_type thật, nhưng cho tới lúc đó nó nói thẳng là chưa nối.

const SUGGESTIONS = [
  "Thời gian thử việc tối đa với công việc của người quản lý doanh nghiệp là bao lâu?",
  "Người sử dụng lao động phải báo trước bao nhiêu ngày khi đơn phương chấm dứt hợp đồng lao động?",
  "Mức lương tối thiểu vùng đang áp dụng cho vùng I là bao nhiêu?",
  "Người lao động được nghỉ hằng năm bao nhiêu ngày và tính lương thế nào?",
];

type Msg =
  { id: string; role: "user"; text: string } | { id: string; role: "assistant"; kind: "chua-noi" };

const uid = () => Math.random().toString(36).slice(2);

function ChuaNoiBlock() {
  return (
    <div className="soft-fade border-l-2 border-border bg-[var(--color-paper-50)] px-5 py-5">
      <div className="flex items-center gap-2 font-sans text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
        <Plug className="size-3.5" />
        Chưa nối máy chủ KLAW
      </div>
      <p className="doc-prose mt-2 text-foreground">
        Bản dựng này mới có giao diện. Câu hỏi của bạn chưa đi tới đâu, và màn hình sẽ không dựng ra
        câu trả lời để lấp chỗ trống. Khi đường tra cứu được nối, mỗi câu trả lời sẽ kèm điều,
        khoản, điểm và nhãn hiệu lực để bạn tự đối chiếu với văn bản gốc.
      </p>
      <div className="mt-4 flex flex-wrap gap-2 font-sans">
        <Link
          to="/soan-thao"
          className="rounded-md border border-border px-3 py-1.5 text-[13px] font-medium text-primary transition-colors hover:bg-[var(--color-paper-100)]"
        >
          Sang màn soạn thảo
        </Link>
      </div>
    </div>
  );
}

function TrialAgent() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<"tra-cuu" | "soan-thao">("tra-cuu");
  const [panelOpen, setPanelOpen] = useState(true);
  const [tab, setTab] = useState<"docs" | "history">("docs");
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  const autoGrow = () => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    const max = 6 * 26 + 20;
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
  };
  useEffect(autoGrow, [input]);

  const send = (raw?: string) => {
    const text = (raw ?? input).trim();
    if (!text) return;
    setInput("");
    setMessages((m) => [
      ...m,
      { id: uid(), role: "user", text },
      { id: uid(), role: "assistant", kind: "chua-noi" },
    ]);
  };

  const questions = messages.filter((m) => m.role === "user") as Extract<Msg, { role: "user" }>[];

  return (
    <AppShell active="/dung-thu">
      <ChuaNoiBanner />
      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="mx-auto flex w-full max-w-[860px] flex-1 flex-col px-4">
            {messages.length === 0 ? (
              <div className="soft-fade flex flex-1 flex-col items-center justify-center py-14">
                <span className="bg-gradient-ink flex size-14 items-center justify-center rounded-2xl text-primary-foreground shadow-soft">
                  <Scale className="size-7" />
                </span>
                <h2 className="font-display mt-5 max-w-xl text-center text-3xl font-semibold text-primary">
                  Bạn cần tra cứu hay soạn thảo gì hôm nay?
                </h2>
                <p className="mt-2 text-center text-sm text-muted-foreground">
                  Chọn một gợi ý bên dưới hoặc nhập câu hỏi của bạn.
                </p>
                <div className="mt-7 grid w-full gap-3 sm:grid-cols-2">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => {
                        setInput(s);
                        taRef.current?.focus();
                      }}
                      className="border-l-2 border-[var(--color-brass-500)] bg-[var(--color-paper-100)] px-4 py-3.5 text-left text-sm leading-relaxed text-foreground transition-colors hover:bg-[var(--color-paper-200)]"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div
                aria-live="polite"
                aria-label="Hội thoại với KLAW"
                className="flex-1 space-y-6 py-8"
              >
                {messages.map((m) =>
                  m.role === "user" ? (
                    <div key={m.id} className="flex justify-end">
                      <p className="max-w-[70%] rounded-2xl rounded-br-sm bg-[var(--color-ink-900)] px-4 py-2.5 text-sm leading-relaxed text-white">
                        {m.text}
                      </p>
                    </div>
                  ) : (
                    <ChuaNoiBlock key={m.id} />
                  ),
                )}
                <div ref={endRef} />
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="sticky bottom-0 border-t border-border bg-background/95 backdrop-blur">
            <div className="mx-auto w-full max-w-[860px] px-4 py-3">
              <div className="flex items-end gap-2 rounded-xl border border-border bg-card p-2 shadow-soft">
                <button
                  title="Đính kèm văn bản"
                  aria-label="Đính kèm văn bản"
                  disabled
                  className="mb-0.5 rounded-lg p-2 text-muted-foreground disabled:opacity-40"
                >
                  <Paperclip className="size-4" />
                </button>
                <textarea
                  ref={taRef}
                  rows={1}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                  placeholder={
                    mode === "tra-cuu"
                      ? "Nhập câu hỏi pháp lý, điều khoản hoặc số hiệu văn bản…"
                      : "Mô tả văn bản cần soạn: loại, các bên, giá trị, điều khoản chính…"
                  }
                  className="max-h-[176px] flex-1 resize-none bg-transparent py-2 text-sm leading-[26px] outline-none placeholder:text-muted-foreground"
                />
                <div className="mb-0.5 flex items-center gap-2">
                  <div className="flex rounded-lg border border-[var(--color-brass-500)]/45 p-0.5">
                    {(
                      [
                        ["tra-cuu", "Tra cứu"],
                        ["soan-thao", "Soạn thảo"],
                      ] as const
                    ).map(([v, label]) => (
                      <button
                        key={v}
                        onClick={() => setMode(v)}
                        className={cn(
                          "rounded-md px-2.5 py-1 text-[12px] font-medium transition-colors duration-150",
                          mode === v
                            ? "bg-[var(--color-brass-500)] text-[var(--color-ink-950)]"
                            : "text-[var(--color-brass-600)] hover:bg-[var(--color-brass-500)]/10",
                        )}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => send()}
                    disabled={!input.trim()}
                    aria-label="Gửi"
                    className="bg-gradient-ink rounded-lg p-2 text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
                  >
                    <Send className="size-4" />
                  </button>
                </div>
              </div>
              <p className="mt-1.5 text-[12px] text-muted-foreground">
                KLAW có thể trả lời chưa đầy đủ. Luôn đối chiếu với văn bản gốc trước khi sử dụng.
              </p>
            </div>
          </div>
        </div>

        {/* Context panel */}
        <aside
          className={cn(
            "hidden shrink-0 border-l border-border bg-[var(--color-paper-50)] transition-[width] duration-150 xl:block",
            panelOpen ? "w-[360px]" : "w-[52px]",
          )}
        >
          <div className="sticky top-[49px] p-3">
            <button
              onClick={() => setPanelOpen((o) => !o)}
              aria-label={panelOpen ? "Thu gọn bảng ngữ cảnh" : "Mở bảng ngữ cảnh"}
              className="mb-3 rounded-md p-1.5 text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/10"
            >
              <ChevronRight
                className={cn(
                  "size-4 transition-transform duration-150",
                  panelOpen && "rotate-180",
                )}
              />
            </button>

            {panelOpen && (
              <div className="soft-fade">
                <div className="flex gap-1 border-b border-border pb-2">
                  {(
                    [
                      ["docs", "Văn bản liên quan"],
                      ["history", "Lịch sử phiên"],
                    ] as const
                  ).map(([v, label]) => (
                    <button
                      key={v}
                      onClick={() => setTab(v)}
                      className={cn(
                        "rounded-md px-2.5 py-1.5 text-[12px] font-medium transition-colors duration-150",
                        tab === v
                          ? "bg-[var(--color-paper-200)] text-primary"
                          : "text-muted-foreground hover:text-primary",
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                {tab === "docs" ? (
                  <div className="mt-3 space-y-2">
                    <p className="text-[12px] text-muted-foreground">
                      Văn bản được dẫn sẽ xuất hiện ở đây khi màn hình nối được vào kho văn bản của
                      KLAW.
                    </p>
                  </div>
                ) : (
                  <div className="mt-3 space-y-2">
                    {questions.length === 0 ? (
                      <p className="text-[12px] text-muted-foreground">
                        Chưa có câu hỏi nào trong phiên này.
                      </p>
                    ) : (
                      questions.map((q, i) => (
                        <div
                          key={q.id}
                          className="rounded-lg border border-border bg-card p-2.5 text-[12px] text-muted-foreground"
                        >
                          <span className="font-mono text-[var(--color-brass-600)]">
                            {String(i + 1).padStart(2, "0")}
                          </span>{" "}
                          {q.text}
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </aside>
      </div>
    </AppShell>
  );
}

export const Route = createFileRoute("/dung-thu")({
  component: TrialAgent,
  head: () => {
    const title = "Dùng thử trợ lý pháp lý KLAW · Tra cứu & soạn thảo";
    const description =
      "Màn dùng thử của KLAW. Trong bản dựng này đường trả lời chưa được nối, nên màn hình không đưa ra câu trả lời hay trích dẫn nào.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
});
