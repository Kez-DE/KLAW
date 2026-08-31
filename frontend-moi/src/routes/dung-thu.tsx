import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  ChevronRight,
  Copy,
  Check,
  FileDown,
  FileSignature,
  BookmarkPlus,
  Paperclip,
  Scale,
  Send,
  ThumbsDown,
  ThumbsUp,
  TriangleAlert,
} from "lucide-react";
import { AppShell, TrialMeter } from "@/components/app/AppShell";
import {
  CitationChip,
  MockDataBanner,
  SourceRow,
  StatusBadge,
} from "@/components/legal/LegalBits";
import { DOC, type LegalDoc } from "@/lib/mock-legal";
import { cn } from "@/lib/utils";

/* ------------------------------- canned data ------------------------------ */

type CannedAnswer = {
  short: string;
  body: string; // [[1]] markers become citation chips after sources resolve
  sources: LegalDoc[];
};

const SUGGESTIONS = [
  "Thời gian thử việc tối đa cho vị trí quản lý doanh nghiệp là bao lâu?",
  "Mức phạt vi phạm hợp đồng thương mại tối đa được thỏa thuận là bao nhiêu?",
  "Soạn hợp đồng dịch vụ giữa hai công ty, giá trị 500 triệu, thanh toán 2 đợt.",
  "Nghị định nào đang điều chỉnh việc bảo vệ dữ liệu cá nhân?",
];

const CANNED: { match: RegExp; answer: CannedAnswer }[] = [
  {
    match: /thử việc/i,
    answer: {
      short:
        "Với người quản lý doanh nghiệp, thời gian thử việc tối đa là 180 ngày. Đây là mức trần, hai bên vẫn có thể thoả thuận ngắn hơn và chỉ được thử việc một lần cho một công việc.",
      body: "Thời gian thử việc do hai bên thoả thuận căn cứ vào tính chất và mức độ phức tạp của công việc, nhưng bị giới hạn bởi các mức trần luật định [[1]].\n\nCác mức trần gồm: 180 ngày với công việc của người quản lý doanh nghiệp theo Luật Doanh nghiệp và Luật Quản lý, sử dụng vốn nhà nước; 60 ngày với chức danh cần trình độ chuyên môn từ cao đẳng trở lên; 30 ngày với chức danh trung cấp, công nhân kỹ thuật, nhân viên nghiệp vụ; 6 ngày làm việc với các công việc còn lại [[1]].\n\nTiền lương thử việc do hai bên thoả thuận nhưng ít nhất phải bằng 85% mức lương của công việc đó. Nội dung thử việc có thể ghi trong hợp đồng lao động hoặc lập hợp đồng thử việc riêng; hợp đồng có thời hạn dưới 01 tháng thì không áp dụng thử việc [[1]].\n\nLưu ý khi soạn thảo: nếu ghi thời gian thử việc vượt mức trần, điều khoản đó vô hiệu và doanh nghiệp có thể bị xử phạt hành chính, đồng thời phải trả đủ lương theo hợp đồng chính thức cho phần thời gian vượt [[2]].",
      sources: [DOC("45/2019/QH14"), DOC("91/2015/QH13")],
    },
  },
  {
    match: /phạt vi phạm|mức phạt/i,
    answer: {
      short:
        "Trong hợp đồng thương mại, mức phạt vi phạm do các bên thoả thuận nhưng không quá 8% giá trị phần nghĩa vụ hợp đồng bị vi phạm. Phạt vi phạm chỉ áp dụng nếu đã được ghi trong hợp đồng.",
      body: "Chế tài phạt vi phạm chỉ phát sinh khi các bên có thoả thuận rõ trong hợp đồng; không có điều khoản phạt thì bên bị vi phạm chỉ có thể yêu cầu bồi thường thiệt hại thực tế [[1]].\n\nMức phạt hoặc tổng mức phạt cho nhiều vi phạm không được vượt quá 8% giá trị phần nghĩa vụ hợp đồng bị vi phạm — cơ sở tính là phần nghĩa vụ bị vi phạm, không phải toàn bộ giá trị hợp đồng [[1]].\n\nPhạt vi phạm và bồi thường thiệt hại có thể áp dụng đồng thời nếu hợp đồng có thoả thuận phạt; bên yêu cầu bồi thường phải chứng minh thiệt hại và mối quan hệ nhân quả [[1]].\n\nVới hợp đồng dân sự không mang tính thương mại, mức phạt không bị giới hạn 8% mà theo thoả thuận của các bên [[2]].",
      sources: [DOC("36/2005/QH11"), DOC("91/2015/QH13")],
    },
  },
  {
    match: /hợp đồng dịch vụ|soạn hợp đồng|500 triệu/i,
    answer: {
      short:
        "Đã dựng khung hợp đồng dịch vụ giữa hai công ty, giá trị 500.000.000 đồng, thanh toán 2 đợt (50% tạm ứng, 50% sau nghiệm thu). Bạn có thể đưa bản thảo sang trang Soạn thảo để điền thông tin các bên.",
      body: "Cấu trúc đề xuất: (1) Căn cứ pháp lý và thông tin các bên; (2) Điều 1 — Nội dung và phạm vi dịch vụ; (3) Điều 2 — Giá trị hợp đồng: 500.000.000 đồng, đã/chưa bao gồm thuế GTGT; (4) Điều 3 — Tiến độ thanh toán: đợt 1 là 250.000.000 đồng trong 05 ngày làm việc kể từ ngày ký, đợt 2 là 250.000.000 đồng trong 10 ngày làm việc kể từ ngày ký biên bản nghiệm thu; (5) Điều 4 — Quyền và nghĩa vụ mỗi bên; (6) Điều 5 — Phạt vi phạm và bồi thường; (7) Điều 6 — Bất khả kháng; (8) Điều 7 — Giải quyết tranh chấp; (9) Điều 8 — Hiệu lực.\n\nHợp đồng dịch vụ là sự thoả thuận giữa các bên, theo đó bên cung ứng dịch vụ thực hiện công việc cho bên sử dụng dịch vụ và được trả tiền [[2]].\n\nĐiều khoản phạt vi phạm nên đặt ở mức không quá 8% giá trị phần nghĩa vụ bị vi phạm để bảo đảm hiệu lực trong quan hệ thương mại [[1]].\n\nKhuyến nghị bổ sung: mốc nghiệm thu bằng văn bản, tiêu chí chất lượng đo được, quy định về bảo mật và về xuất hoá đơn cho từng đợt thanh toán.",
      sources: [DOC("36/2005/QH11"), DOC("91/2015/QH13")],
    },
  },
  {
    match: /dữ liệu cá nhân/i,
    answer: {
      short:
        "Văn bản trung tâm hiện nay là Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân, áp dụng cho mọi tổ chức, cá nhân xử lý dữ liệu cá nhân của người tại Việt Nam.",
      body: "Nghị định 13/2023/NĐ-CP quy định khái niệm dữ liệu cá nhân cơ bản và dữ liệu cá nhân nhạy cảm, các nguyên tắc xử lý, quyền của chủ thể dữ liệu và trách nhiệm của bên kiểm soát, bên xử lý dữ liệu [[1]].\n\nNghĩa vụ thường gặp với doanh nghiệp: có căn cứ hợp pháp trước khi xử lý (thường là sự đồng ý rõ ràng, riêng biệt), lập và lưu hồ sơ đánh giá tác động xử lý dữ liệu cá nhân, thông báo vi phạm cho cơ quan chuyên trách trong 72 giờ, và bảo đảm điều kiện khi chuyển dữ liệu ra nước ngoài [[1]].\n\nCác quy định liên quan cần đọc kèm gồm pháp luật về an ninh mạng, giao dịch điện tử và bảo vệ quyền lợi người tiêu dùng; một phần nội dung đang trong quá trình cập nhật ở cấp luật [[2]].",
      sources: [DOC("13/2023/ND-CP"), DOC("91/2025/QH15")],
    },
  },
];

const NO_BASIS_TEXT =
  "Tôi chưa tìm thấy căn cứ pháp lý đủ rõ cho câu hỏi này trong cơ sở dữ liệu hiện có. Tôi sẽ không đưa ra câu trả lời khi không dẫn được nguồn. Bạn có thể thu hẹp câu hỏi hoặc cung cấp số hiệu văn bản liên quan.";

/* --------------------------------- types --------------------------------- */

type Msg =
  | { id: string; role: "user"; text: string }
  | {
      id: string;
      role: "assistant";
      kind: "answer";
      answer: CannedAnswer;
      streaming: boolean;
      typed: string;
    }
  | { id: string; role: "assistant"; kind: "nobasis"; question: string };

const uid = () => Math.random().toString(36).slice(2);

function pick(question: string): CannedAnswer | null {
  return CANNED.find((c) => c.match.test(question))?.answer ?? null;
}

/* ------------------------------ chip rendering ---------------------------- */

function BodyText({
  text,
  sources,
  showChips,
}: {
  text: string;
  sources: LegalDoc[];
  showChips: boolean;
}) {
  return (
    <>
      {text.split("\n\n").map((para, pi) => (
        <p key={pi}>
          {para.split(/(\[\[\d\]\])/).map((seg, si) => {
            const m = seg.match(/^\[\[(\d)\]\]$/);
            if (!m) return <span key={si}>{seg}</span>;
            const idx = Number(m[1]);
            const doc = sources[idx - 1];
            // Never show a citation before its source has resolved.
            if (!showChips || !doc) return null;
            return <CitationChip key={si} index={idx} doc={doc} />;
          })}
        </p>
      ))}
    </>
  );
}

/* ------------------------------- assistant -------------------------------- */

function ActionRow() {
  const [copied, setCopied] = useState(false);
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  return (
    <div className="mt-5 flex flex-wrap items-center gap-1.5 border-t border-border/60 pt-3 font-sans text-[12px]">
      <button
        onClick={() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        }}
        className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-[var(--color-paper-100)] hover:text-primary"
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        {copied ? "Đã sao chép" : "Sao chép"}
      </button>
      <span className="text-border">·</span>
      <button className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-[var(--color-paper-100)] hover:text-primary">
        <FileDown className="size-3.5" /> Xuất Word
      </button>
      <span className="text-border">·</span>
      <button className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-[var(--color-paper-100)] hover:text-primary">
        <BookmarkPlus className="size-3.5" /> Lưu vào thư viện
      </button>
      <span className="text-border">·</span>
      <Link
        to="/soan-thao"
        className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-muted-foreground transition-colors hover:bg-[var(--color-paper-100)] hover:text-primary"
      >
        <FileSignature className="size-3.5" /> Đưa vào bản thảo
      </Link>
      <div className="ml-auto flex items-center gap-1">
        <button
          onClick={() => setVote("up")}
          aria-label="Hữu ích"
          className={cn(
            "rounded-md p-1.5 transition-colors hover:bg-[var(--color-paper-100)]",
            vote === "up" ? "text-[var(--color-brass-600)]" : "text-muted-foreground",
          )}
        >
          <ThumbsUp className="size-3.5" />
        </button>
        <button
          onClick={() => setVote("down")}
          aria-label="Chưa hữu ích"
          className={cn(
            "rounded-md p-1.5 transition-colors hover:bg-[var(--color-paper-100)]",
            vote === "down" ? "text-[var(--color-status-expired)]" : "text-muted-foreground",
          )}
        >
          <ThumbsDown className="size-3.5" />
        </button>
      </div>
    </div>
  );
}

function AssistantAnswer({ msg }: { msg: Extract<Msg, { kind: "answer" }> }) {
  const [shortPart, bodyPart] = msg.typed.split("\u0000");
  const done = !msg.streaming;

  return (
    <div className="soft-fade border-l-2 border-[var(--color-brass-500)] bg-[var(--color-paper-50)] px-5 py-5">
      <div className="rounded-lg bg-[var(--color-paper-100)] px-4 py-3">
        <p className="font-sans text-[11px] font-semibold uppercase tracking-wider text-[var(--color-brass-600)]">
          Trả lời ngắn
        </p>
        <p
          className={cn(
            "mt-1.5 doc-prose text-foreground",
            bodyPart === undefined && "brass-caret",
          )}
        >
          {shortPart}
        </p>
      </div>

      {bodyPart !== undefined && (
        <div className="mt-5">
          <p className="font-sans text-[11px] font-semibold uppercase tracking-wider text-[var(--color-brass-600)]">
            Căn cứ pháp lý
          </p>
          <div
            className={cn("mt-2 doc-prose text-foreground", !done && "brass-caret")}
          >
            <BodyText text={bodyPart} sources={msg.answer.sources} showChips={done} />
          </div>
        </div>
      )}

      {done && (
        <div className="mt-6">
          <p className="font-sans text-[11px] font-semibold uppercase tracking-wider text-[var(--color-brass-600)]">
            Nguồn trích dẫn
          </p>
          <ol className="mt-1.5 font-sans">
            {msg.answer.sources.map((doc, i) => (
              <div
                key={doc.soHieu}
                className="rise-in"
                style={{ animationDelay: `${i * 300}ms` }}
              >
                <SourceRow index={i + 1} doc={doc} />
              </div>
            ))}
          </ol>
          <ActionRow />
        </div>
      )}
    </div>
  );
}

function NoBasisBlock({ onNarrow }: { onNarrow: () => void }) {
  return (
    <div className="soft-fade border-l-2 border-[var(--color-status-partial)] bg-[var(--color-status-partial)]/8 px-5 py-5">
      <div className="flex items-center gap-2 font-sans text-[11px] font-semibold uppercase tracking-wider text-[var(--color-brass-600)]">
        <TriangleAlert className="size-3.5" />
        Không đủ căn cứ để trả lời
      </div>
      <p className="mt-2 doc-prose text-foreground">{NO_BASIS_TEXT}</p>
      <div className="mt-4 flex flex-wrap gap-2 font-sans">
        <button
          onClick={onNarrow}
          className="rounded-md bg-[var(--color-brass-500)] px-3 py-1.5 text-[13px] font-medium text-[var(--color-ink-950)] transition-opacity hover:opacity-90"
        >
          Thu hẹp câu hỏi
        </button>
        <button className="rounded-md border border-[var(--color-brass-500)]/50 px-3 py-1.5 text-[13px] font-medium text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/10">
          Yêu cầu chuyên gia rà soát
        </button>
      </div>
    </div>
  );
}

/* --------------------------------- page ---------------------------------- */

function TrialAgent() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<"tra-cuu" | "soan-thao">("tra-cuu");
  const [panelOpen, setPanelOpen] = useState(true);
  const [tab, setTab] = useState<"docs" | "history">("docs");
  const [used, setUsed] = useState(8);
  const streamRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(
    () => () => {
      if (streamRef.current) clearInterval(streamRef.current);
    },
    [],
  );

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

  const streaming = messages.some((m) => m.role === "assistant" && m.kind === "answer" && m.streaming);

  const send = (raw?: string) => {
    const text = (raw ?? input).trim();
    if (!text || streaming) return;
    setInput("");
    setUsed((u) => Math.min(u + 1, 20));

    const answer = pick(text);
    const userMsg: Msg = { id: uid(), role: "user", text };

    if (!answer) {
      setMessages((m) => [
        ...m,
        userMsg,
        { id: uid(), role: "assistant", kind: "nobasis", question: text },
      ]);
      return;
    }

    const id = uid();
    setMessages((m) => [
      ...m,
      userMsg,
      { id, role: "assistant", kind: "answer", answer, streaming: true, typed: "" },
    ]);

    const full = `${answer.short}\u0000${answer.body}`;
    const tokens = full.match(/\S+\s*|\s+/g) ?? [full];
    let i = 0;
    streamRef.current = setInterval(() => {
      i += 1;
      const typed = tokens.slice(0, i).join("");
      const finished = i >= tokens.length;
      if (finished && streamRef.current) clearInterval(streamRef.current);
      setMessages((m) =>
        m.map((msg) =>
          msg.id === id && msg.role === "assistant" && msg.kind === "answer"
            ? { ...msg, typed, streaming: !finished }
            : msg,
        ),
      );
    }, 28);
  };

  const citedDocs = useMemo(() => {
    const map = new Map<string, LegalDoc>();
    for (const m of messages) {
      if (m.role === "assistant" && m.kind === "answer" && !m.streaming) {
        m.answer.sources.forEach((d) => map.set(d.soHieu, d));
      }
    }
    return [...map.values()];
  }, [messages]);

  const questions = messages.filter((m) => m.role === "user") as Extract<
    Msg,
    { role: "user" }
  >[];

  return (
    <AppShell active="/dung-thu" topRight={<TrialMeter used={used} total={20} />}>
      <MockDataBanner />
      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="mx-auto flex w-full max-w-[860px] flex-1 flex-col px-4">
            {messages.length === 0 ? (
              <div className="soft-fade flex flex-1 flex-col items-center justify-center py-14">
                <span className="flex size-14 items-center justify-center rounded-2xl bg-gradient-ink text-primary-foreground shadow-soft">
                  <Scale className="size-7" />
                </span>
                <h2 className="mt-5 max-w-xl text-center font-display text-3xl font-semibold text-primary">
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
                  ) : m.kind === "answer" ? (
                    <AssistantAnswer key={m.id} msg={m} />
                  ) : (
                    <NoBasisBlock
                      key={m.id}
                      onNarrow={() => {
                        setInput(`${m.question} (nêu rõ số hiệu văn bản, phạm vi áp dụng) `);
                        taRef.current?.focus();
                      }}
                    />
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
                  className="mb-0.5 rounded-lg p-2 text-muted-foreground transition-colors hover:bg-[var(--color-paper-100)] hover:text-primary"
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
                    disabled={!input.trim() || streaming}
                    aria-label="Gửi"
                    className="rounded-lg bg-gradient-ink p-2 text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
                  >
                    <Send className="size-4" />
                  </button>
                </div>
              </div>
              <p className="mt-1.5 text-[12px] text-muted-foreground">
                KLAW có thể trả lời chưa đầy đủ. Luôn đối chiếu với văn bản gốc trước khi
                sử dụng.
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
                    {citedDocs.length === 0 ? (
                      <p className="text-[12px] text-muted-foreground">
                        Văn bản được dẫn sẽ xuất hiện ở đây sau khi trợ lý trả lời.
                      </p>
                    ) : (
                      citedDocs.map((d) => (
                        <Link
                          key={d.soHieu}
                          to="/tra-cuu/$soHieu"
                          params={{ soHieu: d.soHieu }}
                          className="block rounded-lg border border-border bg-card p-3 transition-colors hover:border-[var(--color-brass-500)]/50"
                        >
                          <p className="font-mono text-[11px] text-[var(--color-brass-600)]">
                            {d.soHieu}
                          </p>
                          <p className="mt-0.5 text-sm font-medium text-foreground">
                            {d.ten}
                          </p>
                          <p className="mt-0.5 text-[11px] text-muted-foreground">
                            {d.coQuan} · {d.ngay}
                          </p>
                          <div className="mt-2">
                            <StatusBadge status={d.status} />
                          </div>
                        </Link>
                      ))
                    )}
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
      "Trải nghiệm trợ lý KLAW: hỏi đáp pháp luật có trích dẫn văn bản, trạng thái hiệu lực và soạn thảo hợp đồng — dữ liệu minh hoạ trong bản dùng thử.";
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
