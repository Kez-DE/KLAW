import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Copy,
  ListTree,
  MessageSquareQuote,
  NotebookPen,
  Search,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/app/AppShell";
import { ChuaNoiBanner } from "@/components/legal/LegalBits";
import { StatusBadge } from "@/components/legal/VanBanUI";
import {
  boDau,
  idDieu,
  idKhoan,
  vanBanTheoSoHieu,
  type Dieu,
  type VanBan,
} from "@/lib/van-ban";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/tra-cuu/$soHieu")({
  loader: ({ params }) => {
    const vb = vanBanTheoSoHieu(params.soHieu);
    if (!vb) throw notFound();
    return { vb };
  },
  head: ({ loaderData }) => {
    const vb = loaderData?.vb;
    const title = vb ? `${vb.ten} ${vb.soHieu} — toàn văn | KLAW` : "Văn bản — KLAW";
    const desc = vb
      ? `${vb.loai} ${vb.soHieu} do ${vb.coQuan} ban hành ngày ${vb.ngayBanHanh}, tình trạng: ${vb.tinhTrang}. Đọc toàn văn theo điều, khoản, điểm.`
      : "Đọc toàn văn văn bản pháp luật theo điều, khoản, điểm trên KLAW.";
    return {
      meta: [
        { title },
        { name: "description", content: desc },
        { property: "og:title", content: title },
        { property: "og:description", content: desc },
        { property: "og:type", content: "article" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  component: DocReader,
  notFoundComponent: ChuaNoiKhoVanBan,
});

/**
 * Với kho rỗng, MỌI số hiệu đều rơi vào nhánh này. Trang 404 chung sẽ nói "không
 * tìm thấy trang", tức là nói sai chỗ hỏng: trang tồn tại, dữ liệu thì chưa nối.
 */
function ChuaNoiKhoVanBan() {
  return (
    <AppShell active="/tra-cuu">
      <ChuaNoiBanner />
      <div className="mx-auto max-w-xl px-5 py-20 text-center">
        <h1 className="font-display text-2xl font-semibold text-primary">
          Chưa mở được toàn văn văn bản
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Bản dựng này chưa nối vào kho văn bản của KLAW, nên chưa có số hiệu nào
          mở được toàn văn. Màn đọc — mục lục theo chương/điều, cuộn theo điều,
          thanh chọn đoạn và ghi chú — sẽ chạy ngay khi đường dữ liệu được nối.
        </p>
        <Link
          to="/tra-cuu"
          className="mt-6 inline-flex items-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium text-primary transition-colors hover:border-accent"
        >
          Quay lại tra cứu
        </Link>
      </div>
    </AppShell>
  );
}

/* ------------------------------- Tree ------------------------------------- */

function TreeContent({
  vb,
  activeDieu,
}: {
  vb: VanBan;
  activeDieu: string | null;
}) {
  const [filter, setFilter] = useState("");
  const [closed, setClosed] = useState<string[]>([]);
  const f = boDau(filter.trim());

  return (
    <div>
        <div className="relative">
          <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Lọc trong văn bản"
            className="h-9 w-full rounded-lg border border-border bg-card pr-2 pl-8 text-[13px] outline-none focus:border-[var(--color-brass-500)]"
          />
        </div>

        <nav className="mt-3">
          {vb.chuong.map((ch) => {
            const dieuList = ch.dieu.filter(
              (d) =>
                !f ||
                boDau(`Điều ${d.so} ${d.tieuDe}`).includes(f) ||
                d.khoan.some((k) => boDau(k.text).includes(f)),
            );
            if (!dieuList.length) return null;
            const isClosed = closed.includes(ch.so);
            return (
              <div key={ch.so} className="mb-2">
                <button
                  type="button"
                  onClick={() =>
                    setClosed((p) =>
                      p.includes(ch.so) ? p.filter((x) => x !== ch.so) : [...p, ch.so],
                    )
                  }
                  className="flex w-full items-start gap-1.5 rounded-md px-1.5 py-1 text-left text-[13px] font-semibold text-primary hover:bg-[var(--color-paper-100)]"
                >
                  {isClosed ? (
                    <ChevronRight className="mt-0.5 size-3.5 shrink-0 text-[var(--color-brass-600)]" />
                  ) : (
                    <ChevronDown className="mt-0.5 size-3.5 shrink-0 text-[var(--color-brass-600)]" />
                  )}
                  <span>
                    Chương {ch.so}. {ch.ten}
                  </span>
                </button>
                {!isClosed && (
                  <ul className="mt-1 ml-3 border-l border-border">
                    {dieuList.map((d) => {
                      const id = idDieu(d.so);
                      const active = activeDieu === id;
                      return (
                        <li key={d.so} className="relative">
                          {active && (
                            <span className="spy-rail absolute top-0 -left-px h-full w-[2px] bg-[var(--color-brass-500)]" />
                          )}
                          {d.muc && (
                            <p className="px-2.5 pt-2 text-[11px] tracking-wide text-muted-foreground uppercase">
                              {d.muc}
                            </p>
                          )}
                          <a
                            href={`#${id}`}
                            className={cn(
                              "block px-2.5 py-1.5 text-[13px] transition-colors duration-150",
                              active
                                ? "font-medium text-[var(--color-brass-600)]"
                                : "text-muted-foreground hover:text-foreground",
                            )}
                          >
                            Điều {d.so}. {d.tieuDe}
                          </a>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            );
          })}
        </nav>
    </div>
  );
}

/* ------------------------------- Body ------------------------------------- */

function DieuBlock({ vb, dieu }: { vb: VanBan; dieu: Dieu }) {
  return (
    <section id={idDieu(dieu.so)} className="scroll-mt-28 pt-8">
      <h3 className="font-display text-[20px] leading-snug font-semibold text-primary">
        <span className="text-[var(--color-brass-600)]">Điều {dieu.so}.</span>{" "}
        {dieu.tieuDe}
      </h3>
      <div className="mt-2 flex flex-col gap-3">
        {dieu.khoan.map((k) => (
          <div
            key={k.so}
            id={idKhoan(dieu.so, k.so)}
            data-citation={`Khoản ${k.so} Điều ${dieu.so} ${vb.tenNgan}`}
            className={cn(
              "scroll-mt-28",
              k.suaDoiBoi && "border-l border-[var(--color-status-partial)] pl-3",
            )}
          >
            <p
              className={cn(
                k.baiBo && "text-muted-foreground line-through opacity-55",
              )}
            >
              <span className="font-semibold">{k.so}.</span> {k.text}
              {k.suaDoiBoi && (
                <sup
                  title={k.suaDoiBoi}
                  className="ml-1 cursor-help font-jetbrains text-[11px] text-[var(--color-brass-600)]"
                >
                  [sđ]
                </sup>
              )}
              {k.baiBo && (
                <span className="ml-2 rounded border border-[var(--color-status-expired)]/45 px-1.5 py-0.5 align-middle font-sans text-[11px] text-[var(--color-status-expired)] no-underline">
                  Đã bị bãi bỏ
                </span>
              )}
            </p>
            {k.diem?.map((d) => (
              <p
                key={d.ky}
                data-citation={`Điểm ${d.ky} khoản ${k.so} Điều ${dieu.so} ${vb.tenNgan}`}
                className={cn(
                  "mt-1.5 ml-8",
                  d.suaDoiBoi && "border-l border-[var(--color-status-partial)] pl-3",
                  d.baiBo && "text-muted-foreground line-through opacity-55",
                )}
              >
                <span className="font-semibold">{d.ky})</span> {d.text}
                {d.suaDoiBoi && (
                  <sup
                    title={d.suaDoiBoi}
                    className="ml-1 cursor-help font-jetbrains text-[11px] text-[var(--color-brass-600)]"
                  >
                    [sđ]
                  </sup>
                )}
              </p>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

/* --------------------- Related documents / notes -------------------------- */

function RelationsContent({
  vb,
  tab,
  setTab,
  notes,
}: {
  vb: VanBan;
  tab: "lien-quan" | "ghi-chu";
  setTab: (t: "lien-quan" | "ghi-chu") => void;
  notes: { trichDan: string; text: string }[];
}) {
  return (
    <div>
            <div className="flex gap-1 rounded-full border border-border p-0.5 text-[12px]">
              {(
                [
                  ["lien-quan", "Văn bản liên quan"],
                  ["ghi-chu", "Ghi chú của tôi"],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setTab(id)}
                  className={cn(
                    "flex-1 rounded-full px-2 py-1 transition-colors duration-150",
                    tab === id
                      ? "bg-[var(--color-brass-500)]/15 font-medium text-[var(--color-brass-600)]"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>

            {tab === "lien-quan" ? (
              <div className="mt-4 flex flex-col gap-4">
                {vb.quanHe.map((g) => (
                  <div key={g.nhom}>
                    <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                      {g.nhom}
                    </p>
                    <ul className="mt-1.5 flex flex-col gap-1.5">
                      {g.items.map((it) => {
                        const target = vanBanTheoSoHieu(it.soHieu);
                        return (
                          <li
                            key={it.soHieu + it.ten}
                            className="rounded-lg border border-border bg-card p-2.5"
                          >
                            <p className="font-jetbrains text-[11px] text-[var(--color-brass-600)]">
                              {it.soHieu}
                            </p>
                            <p className="mt-0.5 text-[13px] text-foreground">{it.ten}</p>
                            {target ? (
                              <div className="mt-1.5 flex items-center justify-between gap-2">
                                <StatusBadge status={target.tinhTrang} />
                                <Link
                                  to="/tra-cuu/$soHieu"
                                  params={{ soHieu: target.soHieu }}
                                  className="text-[12px] text-[var(--color-brass-600)] hover:underline"
                                >
                                  Xem toàn văn
                                </Link>
                              </div>
                            ) : (
                              <p className="mt-1.5 text-[11px] text-muted-foreground">
                                Chưa có trong dữ liệu minh hoạ
                              </p>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-4">
                {notes.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-border p-4 text-[13px] text-muted-foreground">
                    Chọn một đoạn trong văn bản rồi bấm “Ghi chú” để lưu lại cùng trích dẫn
                    chuẩn.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {notes.map((n, i) => (
                      <li
                        key={i}
                        className="rounded-lg border border-border bg-card p-2.5 text-[13px]"
                      >
                        <p className="text-[11px] text-[var(--color-brass-600)]">
                          {n.trichDan}
                        </p>
                        <p className="mt-1 text-muted-foreground">{n.text}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
    </div>
  );
}

/* ------------------------------ Page -------------------------------------- */


function DocReader() {
  const { vb } = Route.useLoaderData();
  const [metaOpen, setMetaOpen] = useState(true);
  const [treeOpen, setTreeOpen] = useState(false);
  const [tab, setTab] = useState<"lien-quan" | "ghi-chu">("lien-quan");
  const [activeDieu, setActiveDieu] = useState<string | null>(null);
  const [notes, setNotes] = useState<{ trichDan: string; text: string }[]>([]);
  const bodyRef = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState<{ top: number; left: number; citation: string } | null>(
    null,
  );

  const dieuIds = useMemo(
    () => vb.chuong.flatMap((c) => c.dieu.map((d) => idDieu(d.so))),
    [vb],
  );

  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible) setActiveDieu(visible.target.id);
      },
      { rootMargin: "-100px 0px -60% 0px", threshold: 0 },
    );
    dieuIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) obs.observe(el);
    });
    return () => obs.disconnect();
  }, [dieuIds]);

  useEffect(() => {
    const onUp = () => {
      const s = window.getSelection();
      if (!s || s.isCollapsed || !s.toString().trim()) {
        setSel(null);
        return;
      }
      const node = s.anchorNode;
      const el =
        node instanceof Element ? node : (node?.parentElement ?? null);
      if (!el || !bodyRef.current?.contains(el)) {
        setSel(null);
        return;
      }
      const host = el.closest<HTMLElement>("[data-citation]");
      const rect = s.getRangeAt(0).getBoundingClientRect();
      setSel({
        top: rect.top - 44,
        left: rect.left,
        citation: host?.dataset["citation"] ?? vb.tenNgan,
      });
    };
    document.addEventListener("mouseup", onUp);
    return () => document.removeEventListener("mouseup", onUp);
  }, [vb]);

  const meta: [string, string][] = [
    ["Số hiệu", vb.soHieu],
    ["Loại văn bản", vb.loai],
    ["Cơ quan ban hành", vb.coQuan],
    ["Người ký", vb.nguoiKy],
    ["Chức vụ người ký", vb.chucVu],
    ["Ngày ban hành", vb.ngayBanHanh],
    ["Ngày có hiệu lực", vb.ngayHieuLuc],
    ["Ngày hết hiệu lực", vb.ngayHetHieuLuc ?? "—"],
    ["Lĩnh vực", vb.linhVuc],
    ["Tình trạng hiệu lực", vb.tinhTrang],
  ];

  return (
    <AppShell active="/tra-cuu">
      <ChuaNoiBanner />
      <div className="flex min-w-0 flex-1">
        <aside
          aria-label="Mục lục văn bản"
          className="hidden w-[300px] shrink-0 border-r border-border bg-[var(--color-paper-50)] lg:block"
        >
          <div className="sticky top-[52px] max-h-[calc(100vh-52px)] overflow-y-auto px-3 py-4">
            <TreeContent vb={vb} activeDieu={activeDieu} />
          </div>
        </aside>

        {/* CENTER */}
        <div className="min-w-0 flex-1">
          <div className="sticky top-[52px] z-20 border-b border-border bg-background/95 px-5 py-3 backdrop-blur">
            <div className="mx-auto max-w-[760px]">
              <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted-foreground">
                <Link to="/tra-cuu" className="hover:text-foreground">
                  Tra cứu
                </Link>
                <span>/</span>
                <span className="font-jetbrains text-foreground">{vb.soHieu}</span>
                <StatusBadge status={vb.tinhTrang} />
              </div>
              <h1 className="mt-1 font-display text-[22px] leading-tight font-bold text-primary">
                {vb.ten}
              </h1>
              {vb.canhBao && (
                <div className="mt-2 flex items-start gap-2 rounded-lg border border-[var(--color-status-partial)]/55 bg-[var(--color-status-partial)]/12 px-3 py-2 text-[13px] text-foreground">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-[var(--color-brass-600)]" />
                  <p>{vb.canhBao}</p>
                </div>
              )}
            </div>
          </div>

          <div className="px-5 pb-24">
            <div className="mx-auto max-w-[760px]">
              <div className="mt-4 rounded-xl border border-border bg-[var(--color-paper-50)]">
                <button
                  type="button"
                  onClick={() => setMetaOpen((v) => !v)}
                  className="flex w-full items-center justify-between px-4 py-2.5 text-left font-display text-sm font-semibold text-primary"
                >
                  Thông tin văn bản
                  <ChevronDown
                    className={cn(
                      "size-4 text-[var(--color-brass-600)] transition-transform duration-150",
                      !metaOpen && "-rotate-90",
                    )}
                  />
                </button>
                {metaOpen && (
                  <dl className="grid grid-cols-1 gap-x-6 border-t border-border px-4 py-3 text-[13px] sm:grid-cols-2">
                    {meta.map(([k, v]) => (
                      <div
                        key={k}
                        className="flex justify-between gap-3 border-b border-border/60 py-1.5 last:border-0"
                      >
                        <dt className="text-muted-foreground">{k}</dt>
                        <dd
                          className={cn(
                            "text-right font-medium text-foreground",
                            k === "Số hiệu" && "font-jetbrains",
                          )}
                        >
                          {v}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
              </div>

              <article
                ref={bodyRef}
                aria-label={`Toàn văn ${vb.tenNgan}`}
                className="doc-reader mt-6 text-foreground"
              >
                {vb.chuong.map((ch) => (
                  <div key={ch.so}>
                    <h2 className="mt-10 font-display text-[15px] font-semibold tracking-wide text-[var(--color-brass-600)] uppercase">
                      Chương {ch.so}. {ch.ten}
                    </h2>
                    {ch.dieu.map((d) => (
                      <DieuBlock key={d.so} vb={vb} dieu={d} />
                    ))}
                  </div>
                ))}
              </article>

              {/* Văn bản liên quan / ghi chú dạng tab dưới 1280px */}
              <section aria-label="Văn bản liên quan và ghi chú" className="mt-10 xl:hidden">
                <RelationsContent vb={vb} tab={tab} setTab={setTab} notes={notes} />
              </section>
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <aside className="hidden w-[320px] shrink-0 border-l border-border bg-[var(--color-paper-50)] xl:block">
          <div className="sticky top-[52px] max-h-[calc(100vh-52px)] overflow-y-auto px-4 py-4">
            <RelationsContent vb={vb} tab={tab} setTab={setTab} notes={notes} />
          </div>
        </aside>
      </div>

      {/* Mục lục dạng nút nổi dưới 1024px */}
      <button
        type="button"
        onClick={() => setTreeOpen(true)}
        aria-expanded={treeOpen}
        aria-controls="muc-luc-sheet"
        className="focus-brass fixed bottom-[68px] left-4 z-40 rounded-full border border-[var(--color-brass-500)]/60 bg-card px-4 py-2.5 text-[13px] font-medium text-[var(--color-brass-600)] shadow-soft md:bottom-5 lg:hidden"
      >
        <span className="inline-flex items-center gap-1.5">
          <ListTree className="size-4" aria-hidden />
          Mục lục
        </span>
      </button>
      {treeOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-[var(--color-ink-950)]/45"
            onClick={() => setTreeOpen(false)}
            aria-hidden
          />
          <div
            id="muc-luc-sheet"
            role="dialog"
            aria-modal="true"
            aria-label="Mục lục văn bản"
            className="absolute inset-y-0 left-0 w-[86vw] max-w-[330px] overflow-y-auto border-r border-border bg-background px-3 py-4"
          >
            <div className="mb-2 flex items-center justify-between">
              <p className="font-display text-sm font-semibold text-primary">Mục lục</p>
              <button
                type="button"
                onClick={() => setTreeOpen(false)}
                aria-label="Đóng mục lục"
                className="focus-brass rounded-md p-1 text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
            <div onClick={() => setTreeOpen(false)}>
              <TreeContent vb={vb} activeDieu={activeDieu} />
            </div>
          </div>
        </div>
      )}


      {/* Selection toolbar */}
      {sel && (
        <div
          className="fixed z-50 flex items-center gap-1 rounded-lg border border-[var(--color-brass-500)]/60 bg-card px-1.5 py-1 text-[12px] shadow-lg"
          style={{ top: Math.max(sel.top, 60), left: sel.left }}
        >
          <button
            type="button"
            onClick={() => {
              void navigator.clipboard?.writeText(sel.citation);
              toast.success("Đã sao chép trích dẫn chuẩn", {
                description: sel.citation,
              });
              setSel(null);
            }}
            className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[var(--color-brass-600)] hover:bg-[var(--color-brass-500)]/12"
          >
            <Copy className="size-3.5" /> Sao chép trích dẫn chuẩn
          </button>
          <Link
            to="/dung-thu"
            className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-muted-foreground hover:bg-[var(--color-paper-100)] hover:text-foreground"
          >
            <MessageSquareQuote className="size-3.5" /> Hỏi KLAW về đoạn này
          </Link>
          <button
            type="button"
            onClick={() => {
              const text = window.getSelection()?.toString().trim() ?? "";
              setNotes((p) => [{ trichDan: sel.citation, text }, ...p]);
              setTab("ghi-chu");
              setSel(null);
              toast.success("Đã thêm ghi chú");
            }}
            className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-muted-foreground hover:bg-[var(--color-paper-100)] hover:text-foreground"
          >
            <NotebookPen className="size-3.5" /> Ghi chú
          </button>
        </div>
      )}
    </AppShell>
  );
}
