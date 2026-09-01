import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMemo, useState, type Dispatch, type SetStateAction } from "react";
import {
  ArrowRight,
  BookmarkPlus,
  Copy,
  FileSignature,
  Filter,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/app/AppShell";
import { ChuaNoiBanner } from "@/components/legal/LegalBits";
import { Chip, Highlight } from "@/components/legal/VanBanUI";
import {
  CO_QUAN,
  KHO_DA_NOI,
  LOAI_VAN_BAN,
  goiYDongNghia,
  laSoHieu,
  timKiem,
  timVanBanTheoSoHieu,
  type BoLoc,
  type KetQua,
} from "@/lib/van-ban";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/tra-cuu/")({
  head: () => ({
    meta: [
      { title: "Tra cứu văn bản pháp luật theo điều, khoản — KLAW" },
      {
        name: "description",
        content:
          "Tra cứu luật, bộ luật, nghị định, thông tư Việt Nam theo điều, khoản, điểm với tìm kiếm tiếng Việt không dấu và trích dẫn chuẩn.",
      },
      { property: "og:title", content: "Tra cứu văn bản pháp luật — KLAW" },
      {
        property: "og:description",
        content:
          "Tìm chính xác điều, khoản, điểm trong hệ thống văn bản pháp luật Việt Nam và sao chép trích dẫn chuẩn.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: TraCuuPage,
});

type Mode = "noi-dung" | "so-hieu" | "hoi-klaw";
type Sort = "lien-quan" | "moi-nhat" | "hieu-luc";

const MODES: { id: Mode; label: string }[] = [
  { id: "noi-dung", label: "Tìm theo nội dung" },
  { id: "so-hieu", label: "Tìm theo số hiệu" },
  { id: "hoi-klaw", label: "Hỏi KLAW" },
];

const SORTS: { id: Sort; label: string }[] = [
  { id: "lien-quan", label: "Liên quan nhất" },
  { id: "moi-nhat", label: "Mới nhất" },
  { id: "hieu-luc", label: "Còn hiệu lực trước" },
];

const NAM_MIN = 1990;
const NAM_MAX = 2026;

function CheckList({
  title,
  options,
  selected,
  onToggle,
}: {
  title: string;
  options: readonly string[];
  selected: string[];
  onToggle: (v: string) => void;
}) {
  return (
    <div className="border-b border-border py-3">
      <p className="mb-2 text-[12px] font-semibold tracking-wide text-primary uppercase">{title}</p>
      <div className="flex flex-col gap-1.5">
        {options.map((o) => (
          <label
            key={o}
            className="flex cursor-pointer items-start gap-2 text-[13px] text-muted-foreground transition-colors hover:text-foreground"
          >
            <input
              type="checkbox"
              checked={selected.includes(o)}
              onChange={() => onToggle(o)}
              className="mt-0.5 size-3.5 accent-[var(--color-brass-500)]"
            />
            <span>{o}</span>
          </label>
        ))}
      </div>
    </div>
  );
}

function ResultCard({ kq, query }: { kq: KetQua; query: string }) {
  const { vb, dieu, khoan } = kq;
  const suaDoi = dieu.soVanBanSuaDoi ?? 0;
  const doan = kq.diem ? `${khoan.text} ${kq.diem.ky}) ${kq.diem.text}` : khoan.text;
  const diaChi = kq.diem ? `Điểm ${kq.diem.ky} khoản ${khoan.so} Điều ${dieu.so}` : kq.diaChi;

  return (
    <article className="rounded-xl border border-border bg-card p-4 transition-colors duration-150 hover:border-[var(--color-brass-500)]/50">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12px] text-muted-foreground">
        <span className="font-jetbrains text-[12px] text-foreground">{vb.soHieu}</span>
        <span className="text-border">·</span>
        <span>{vb.loai}</span>
        <span className="text-border">·</span>
        <span>{vb.coQuan}</span>
      </div>

      <h3 className="mt-2 font-display text-[20px] leading-snug font-semibold text-primary">
        <Link to="/tra-cuu" params={{ soHieu: vb.soHieu }} className="hover:underline">
          <Highlight text={`${vb.ten} ${vb.soHieu}`} query={query} />
        </Link>
      </h3>

      <div className="mt-2.5 border-l-2 border-[var(--color-brass-500)] pl-3">
        <p className="serif-body text-[15px] leading-[1.8] text-foreground">
          <span className="font-semibold">{diaChi} — </span>
          <Highlight text={doan} query={query} />
        </p>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12px] text-muted-foreground">
        <span>Ngày ban hành: {vb.ngayBanHanh}</span>
        <span className="text-border">·</span>
        <span>Ngày hiệu lực: {vb.ngayHieuLuc}</span>
        <span className="text-border">·</span>
        <span className={cn(suaDoi > 0 && "font-medium text-[var(--color-brass-600)]")}>
          {suaDoi > 0 ? `${suaDoi} văn bản sửa đổi điều này` : "Chưa có văn bản sửa đổi điều này"}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3 text-[12px]">
        <Link
          to="/tra-cuu"
          hash={`dieu-${dieu.so}-khoan-${khoan.so}`}
          className="inline-flex items-center gap-1 font-medium text-[var(--color-brass-600)] hover:underline"
        >
          Xem toàn văn <ArrowRight className="size-3.5" />
        </Link>
        <button
          type="button"
          onClick={() => {
            void navigator.clipboard?.writeText(kq.trichDan);
            toast.success("Đã sao chép trích dẫn", { description: kq.trichDan });
          }}
          className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
        >
          <Copy className="size-3.5" /> Sao chép trích dẫn
        </button>
        <button
          type="button"
          onClick={() => toast.success("Đã lưu vào thư viện (bản dùng thử)")}
          className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
        >
          <BookmarkPlus className="size-3.5" /> Lưu
        </button>
        <Link
          to="/soan-thao"
          className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
        >
          <FileSignature className="size-3.5" /> Đưa vào bản thảo
        </Link>
      </div>
    </article>
  );
}

type LocProps = {
  loc: BoLoc;
  toggle: (key: "loai" | "coQuan", v: string) => void;
  setLoc: Dispatch<SetStateAction<BoLoc>>;
};

function FilterBody({ loc, toggle, setLoc }: LocProps) {
  return (
    <div>
      <CheckList
        title="Loại văn bản"
        options={LOAI_VAN_BAN}
        selected={loc.loai}
        onToggle={(v) => toggle("loai", v)}
      />
      <CheckList
        title="Cơ quan ban hành"
        options={CO_QUAN}
        selected={loc.coQuan}
        onToggle={(v) => toggle("coQuan", v)}
      />
      {/* KHÔNG có nhóm lọc "Tình trạng hiệu lực". `/bo-loc` cố ý không trả
          khoá đó: lọc theo tuyên bố của CSDL quốc gia là đúng lỗi hệ thống này
          tồn tại để chữa. Lọc hiệu lực đi qua `sap_xep=con_hieu_luc_truoc`. */}
      <div className="py-3">
        <p className="mb-2 text-[12px] font-semibold tracking-wide text-primary uppercase">
          Khoảng thời gian ban hành
        </p>
        <p className="font-jetbrains text-[12px] text-muted-foreground">
          {loc.namTu} — {loc.namDen}
        </p>
        <input
          type="range"
          min={NAM_MIN}
          max={NAM_MAX}
          value={loc.namTu}
          onChange={(e) =>
            setLoc((p) => ({
              ...p,
              namTu: Math.min(Number(e.target.value), p.namDen),
            }))
          }
          className="mt-2 w-full accent-[var(--color-brass-500)]"
        />
        <input
          type="range"
          min={NAM_MIN}
          max={NAM_MAX}
          value={loc.namDen}
          onChange={(e) =>
            setLoc((p) => ({
              ...p,
              namDen: Math.max(Number(e.target.value), p.namTu),
            }))
          }
          className="w-full accent-[var(--color-brass-500)]"
        />
      </div>
    </div>
  );
}

function TraCuuPage() {
  const navigate = useNavigate();
  const [raw, setRaw] = useState("");
  const [query, setQuery] = useState("thu viec");
  const [mode, setMode] = useState<Mode>("noi-dung");
  const [sort, setSort] = useState<Sort>("lien-quan");
  const [railOpen, setRailOpen] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [boQuaGoiY, setBoQuaGoiY] = useState<string[]>([]);

  const [loc, setLoc] = useState<BoLoc>({
    loai: [],
    coQuan: [],
    linhVuc: [],
    namTu: NAM_MIN,
    namDen: NAM_MAX,
  });

  const term = raw.trim() ? raw : query;
  const soHieuMatch = laSoHieu(term) ? timVanBanTheoSoHieu(term) : undefined;
  const goiY = goiYDongNghia(term).filter((g) => !boQuaGoiY.includes(g));

  const ketQua = useMemo(() => {
    const rs = timKiem(term, loc);
    if (sort === "moi-nhat")
      return [...rs].sort(
        (a, b) => Number(b.vb.ngayBanHanh.slice(-4)) - Number(a.vb.ngayBanHanh.slice(-4)),
      );
    // "Còn hiệu lực trước" là một phép sắp xếp của MÁY CHỦ
    // (`sap_xep=con_hieu_luc_truoc`, ba bậc), không phải một phép so sánh trên
    // một cột tình trạng ở FE. Đường dữ liệu thật được nối ở bước sau.
    return rs;
  }, [term, loc, sort]);

  const soVanBan = new Set(ketQua.map((k) => k.vb.soHieu)).size;

  const toggle = (key: "loai" | "coQuan", v: string) =>
    setLoc((p) => ({
      ...p,
      [key]: p[key].includes(v) ? p[key].filter((x) => x !== v) : [...p[key], v],
    }));

  const activeChips: { key: "loai" | "coQuan"; v: string }[] = [
    ...loc.loai.map((v) => ({ key: "loai" as const, v })),
    ...loc.coQuan.map((v) => ({ key: "coQuan" as const, v })),
  ];

  const submit = () => {
    const t = raw.trim();
    if (!t) return;
    const vb = laSoHieu(t) ? timVanBanTheoSoHieu(t) : undefined;
    if (vb && mode !== "noi-dung") {
      void navigate({ to: "/tra-cuu" });
      return;
    }
    if (mode === "hoi-klaw") {
      void navigate({ to: "/dung-thu" });
      return;
    }
    setQuery(t);
    setBoQuaGoiY([]);
  };

  return (
    <AppShell active="/tra-cuu">
      <ChuaNoiBanner />
      <div className="flex min-w-0 flex-1">
        {/* FILTER RAIL */}
        {railOpen ? (
          <aside className="hidden w-[280px] shrink-0 border-r border-border bg-[var(--color-paper-50)] px-4 py-4 xl:block">
            <div className="flex items-center justify-between">
              <p className="flex items-center gap-1.5 font-display text-sm font-semibold text-primary">
                <SlidersHorizontal className="size-4" /> Bộ lọc
              </p>
              <button
                type="button"
                onClick={() => setRailOpen(false)}
                className="text-[12px] text-muted-foreground hover:text-foreground"
              >
                Thu gọn
              </button>
            </div>
            <FilterBody loc={loc} toggle={toggle} setLoc={setLoc} />
          </aside>
        ) : (
          <button
            type="button"
            onClick={() => setRailOpen(true)}
            className="hidden w-11 shrink-0 flex-col items-center gap-2 border-r border-border bg-[var(--color-paper-50)] py-4 text-muted-foreground hover:text-foreground xl:flex"
          >
            <Filter className="size-4" />
          </button>
        )}

        {/* Bộ lọc dạng bottom sheet dưới 1280px */}
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          aria-expanded={sheetOpen}
          aria-controls="bo-loc-sheet"
          className="focus-brass fixed bottom-[68px] left-1/2 z-40 -translate-x-1/2 rounded-full border border-[var(--color-brass-500)]/60 bg-card px-4 py-2.5 text-[13px] font-medium text-[var(--color-brass-600)] shadow-soft xl:hidden md:bottom-5"
        >
          <span className="inline-flex items-center gap-1.5">
            <SlidersHorizontal className="size-4" aria-hidden />
            Bộ lọc ({activeChips.length})
          </span>
        </button>
        {sheetOpen && (
          <div className="fixed inset-0 z-50 xl:hidden">
            <div
              className="absolute inset-0 bg-[var(--color-ink-950)]/45"
              onClick={() => setSheetOpen(false)}
              aria-hidden
            />
            <div
              id="bo-loc-sheet"
              role="dialog"
              aria-modal="true"
              aria-label="Bộ lọc văn bản"
              className="rise-in absolute inset-x-0 bottom-0 max-h-[82vh] overflow-y-auto rounded-t-2xl border-t border-border bg-background px-4 pt-4 pb-8"
            >
              <div className="mb-2 flex items-center justify-between">
                <p className="font-display text-sm font-semibold text-primary">
                  Bộ lọc ({activeChips.length})
                </p>
                <button
                  type="button"
                  onClick={() => setSheetOpen(false)}
                  aria-label="Đóng bộ lọc"
                  className="focus-brass rounded-md p-1 text-muted-foreground hover:text-foreground"
                >
                  <X className="size-4" aria-hidden />
                </button>
              </div>
              <FilterBody loc={loc} toggle={toggle} setLoc={setLoc} />
            </div>
          </div>
        )}

        {/* MAIN */}
        <div className="min-w-0 flex-1 px-4 py-6 lg:px-8">
          <div className="mx-auto max-w-[900px]">
            <h1 className="font-display text-[28px] font-bold text-primary">
              Tra cứu văn bản pháp luật
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Tìm đến từng điều, khoản, điểm và sao chép trích dẫn theo đúng trật tự tiếng Việt.
            </p>

            <div className="relative mt-4">
              <Search className="absolute top-1/2 left-4 size-[18px] -translate-y-1/2 text-muted-foreground" />
              <input
                value={raw}
                onChange={(e) => setRaw(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                placeholder="Nhập câu hỏi, tên văn bản, hoặc số hiệu — ví dụ: 45/2019/QH14, thử việc, phạt hợp đồng"
                className="serif-body h-14 w-full rounded-xl border border-border bg-card pr-28 pl-11 text-[15px] text-foreground outline-none placeholder:text-muted-foreground/80 focus:border-[var(--color-brass-500)]"
              />
              <button
                type="button"
                onClick={submit}
                className="absolute top-1/2 right-2 -translate-y-1/2 rounded-lg bg-gradient-ink px-4 py-2 text-sm font-medium text-primary-foreground"
              >
                Tra cứu
              </button>
            </div>

            <div className="mt-3 flex flex-wrap gap-1.5">
              {MODES.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setMode(m.id)}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-[13px] transition-colors duration-150",
                    mode === m.id
                      ? "border-[var(--color-brass-500)] bg-[var(--color-brass-500)]/12 font-medium text-[var(--color-brass-600)]"
                      : "border-border text-muted-foreground hover:text-foreground",
                  )}
                >
                  {m.label}
                </button>
              ))}
            </div>

            {soHieuMatch && (
              <Link
                to="/tra-cuu"
                className="mt-3 flex items-center gap-2 rounded-lg border border-[var(--color-brass-500)]/50 bg-[var(--color-brass-500)]/10 px-3 py-2 text-[13px] text-foreground"
              >
                <ArrowRight className="size-4 text-[var(--color-brass-600)]" />
                <span className="font-medium text-[var(--color-brass-600)]">
                  Đi thẳng tới văn bản
                </span>
                <span className="font-jetbrains text-[12px]">{soHieuMatch.soHieu}</span>
                <span className="truncate text-muted-foreground">{soHieuMatch.ten}</span>
              </Link>
            )}

            {goiY.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="text-[12px] text-muted-foreground">Có thể bạn muốn tìm:</span>
                {goiY.map((g) => (
                  <Chip
                    key={g}
                    onClick={() => setQuery(g)}
                    onRemove={() => setBoQuaGoiY((p) => [...p, g])}
                  >
                    {g}
                  </Chip>
                ))}
              </div>
            )}

            {activeChips.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {activeChips.map((c) => (
                  <Chip key={`${c.key}-${c.v}`} onRemove={() => toggle(c.key, c.v)}>
                    {c.v}
                  </Chip>
                ))}
              </div>
            )}

            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3">
              <p className="text-[13px] text-muted-foreground">
                {KHO_DA_NOI ? (
                  <>
                    Tìm thấy{" "}
                    <span className="font-medium text-foreground">{ketQua.length} điều khoản</span>{" "}
                    trong <span className="font-medium text-foreground">{soVanBan} văn bản</span>
                    {term && (
                      <>
                        {" "}
                        cho “<span className="text-foreground">{term}</span>”
                      </>
                    )}
                  </>
                ) : (
                  <>Kho văn bản chưa được nối</>
                )}
              </p>
              <div className="flex items-center gap-1 rounded-full border border-border p-0.5">
                {SORTS.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setSort(s.id)}
                    className={cn(
                      "rounded-full px-2.5 py-1 text-[12px] transition-colors duration-150",
                      sort === s.id
                        ? "bg-[var(--color-brass-500)]/15 font-medium text-[var(--color-brass-600)]"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4 flex flex-col gap-3 pb-16">
              {ketQua.length === 0 &&
                // "Không tìm thấy" và "chưa nối" là hai câu khác nhau, và nói
                // nhầm câu thứ nhất khi đúng ra là câu thứ hai chính là kiểu
                // giả lập mà pha này phải loại bỏ.
                (KHO_DA_NOI ? (
                  <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                    Không tìm thấy điều khoản phù hợp. Thử bỏ bớt bộ lọc hoặc dùng từ khoá ngắn hơn
                    (ví dụ “thu viec”, “BLLĐ”).
                  </p>
                ) : (
                  <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                    Chưa có kết quả nào để hiện: bản dựng này chưa nối vào kho văn bản của KLAW. Ô
                    tìm kiếm, bộ lọc và cách sắp xếp vẫn thao tác được để xem trước giao diện.
                  </p>
                ))}
              {ketQua.map((kq, i) => (
                <ResultCard
                  key={`${kq.vb.soHieu}-${kq.dieu.so}-${kq.khoan.so}-${i}`}
                  kq={kq}
                  query={term}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
