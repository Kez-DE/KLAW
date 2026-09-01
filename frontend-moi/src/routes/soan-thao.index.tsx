import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  Briefcase,
  Building2,
  FileSignature,
  Gavel,
  ScanSearch,
  Search,
  Stamp,
} from "lucide-react";
import { AppShell } from "@/components/app/AppShell";
import { CanCuChuaKiemBanner } from "@/components/legal/LegalBits";
import { MAU, NHOM, loaiBackendCua, type NhomMau } from "@/lib/mau-van-ban";
import { boDau } from "@/lib/khong-dau";
import { cn } from "@/lib/utils";
import { SITE_ORIGIN } from "./__root";

export const Route = createFileRoute("/soan-thao/")({
  head: () => ({
    meta: [
      { title: "Chọn mẫu văn bản pháp lý — KLAW" },
      {
        name: "description",
        content:
          "Hơn 25 mẫu hợp đồng lao động, thương mại, văn bản nội bộ và tố tụng theo pháp luật Việt Nam, sẵn sàng điền thông tin.",
      },
      { property: "og:title", content: "Chọn mẫu văn bản pháp lý — KLAW" },
      {
        property: "og:description",
        content:
          "Chọn loại hợp đồng hoặc văn bản, KLAW dựng bản thảo đúng thể thức với trích dẫn căn cứ pháp lý.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
    links: [{ rel: "canonical", href: `${SITE_ORIGIN}/soan-thao` }],
  }),
  component: ChonLoaiVanBan,
});

/** Đếm từ chính bản đồ, không viết cứng: thêm một ánh xạ là con số tự đúng. */
const SO_SOAT_DUOC = MAU.filter((m) => loaiBackendCua(m.id) !== undefined).length;

const NHOM_ICON: Record<NhomMau, typeof Briefcase> = {
  "lao-dong": Briefcase,
  "thuong-mai": FileSignature,
  "noi-bo": Building2,
  "to-tung": Gavel,
};

function ChonLoaiVanBan() {
  const [tab, setTab] = useState<NhomMau>("lao-dong");
  const [q, setQ] = useState("");

  const ketQua = useMemo(() => {
    const k = boDau(q.trim());
    const trong = k.length === 0;
    const list = MAU.filter((m) =>
      trong ? m.nhom === tab : boDau(`${m.ten} ${m.moTa}`).includes(k),
    );
    return { list, dangTim: !trong };
  }, [q, tab]);

  return (
    <AppShell active="/soan-thao">
      <div className="mx-auto w-full max-w-6xl px-5 py-6 lg:px-8">
        <CanCuChuaKiemBanner className="mb-5" />

        <h1 className="font-display text-[36px] leading-tight font-bold text-primary">
          Bạn cần soạn văn bản gì?
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Chọn một mẫu để mở không gian soạn thảo: điền thông tin các bên, chọn điều khoản và xem
          trước bản A4 theo thể thức văn bản Việt Nam. Toàn bộ diễn ra trên máy bạn.
        </p>
        <p className="mt-2 max-w-2xl text-[13px] text-muted-foreground">
          {SO_SOAT_DUOC}/{MAU.length} mẫu soát được với kho văn bản của KLAW — bộ soát hiện mới có
          rule và checklist cho hợp đồng lao động. Những mẫu còn lại vẫn soạn và xuất tệp bình
          thường, nhưng phần đối chiếu pháp lý phải do người làm.
        </p>

        <div className="relative mt-5 max-w-xl">
          <Search className="absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Tìm loại hợp đồng hoặc văn bản…"
            className="serif-body w-full rounded-xl border border-border bg-background py-3 pr-4 pl-10 text-[15px] outline-none transition-colors focus:border-[var(--color-brass-500)] focus:ring-2 focus:ring-[var(--color-brass-500)]/25"
          />
        </div>

        {!ketQua.dangTim && (
          <div className="mt-6 flex flex-wrap gap-2">
            {NHOM.map((n) => {
              const Icon = NHOM_ICON[n.id];
              return (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => setTab(n.id)}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-[13px] transition-colors",
                    tab === n.id
                      ? "border-[var(--color-brass-500)] bg-[var(--color-brass-500)]/12 text-[var(--color-brass-600)]"
                      : "border-border text-muted-foreground hover:bg-[var(--color-paper-100)]",
                  )}
                >
                  <Icon className="size-3.5" />
                  {n.ten}
                </button>
              );
            })}
          </div>
        )}

        <p className="mt-5 text-[12.5px] text-muted-foreground">
          {ketQua.dangTim
            ? `Tìm thấy ${ketQua.list.length} mẫu văn bản`
            : `${ketQua.list.length} mẫu trong nhóm này`}
        </p>

        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {ketQua.list.map((m) => {
            const Icon = NHOM_ICON[m.nhom];
            return (
              <Link
                key={m.id}
                to="/soan-thao/$loaiVanBan"
                params={{ loaiVanBan: m.id }}
                className="group flex flex-col rounded-xl border border-border bg-[var(--color-paper-50)] p-4 transition-all duration-150 hover:-translate-y-1 hover:border-[var(--color-brass-500)]/60 hover:shadow-lg"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="flex size-9 items-center justify-center rounded-lg bg-[var(--color-brass-500)]/12 text-[var(--color-brass-600)]">
                    <Icon className="size-4" />
                  </span>
                  {/* Hai nhãn KHÁC NHAU, vì hai năng lực khác nhau. Mọi mẫu đều
                      soạn và xuất tệp được ngay trên máy; chỉ một số ít soát
                      được với kho văn bản, và danh mục phải nói ra chỗ đó thay
                      vì để 25 thẻ trông giống hệt nhau. */}
                  {loaiBackendCua(m.id) === undefined ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-[var(--color-paper-100)] px-2 py-0.5 text-[10.5px] font-medium text-muted-foreground">
                      <Stamp className="size-3" aria-hidden /> Soạn được, chưa soát được
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--color-brass-500)]/45 bg-[var(--color-brass-500)]/10 px-2 py-0.5 text-[10.5px] font-medium text-[var(--color-brass-600)]">
                      <ScanSearch className="size-3" aria-hidden /> Soát được với KLAW
                    </span>
                  )}
                </div>
                <h2 className="mt-3 font-display text-[16.5px] leading-snug font-bold text-primary">
                  {m.ten}
                </h2>
                <p className="mt-1 line-clamp-2 text-[12.5px] text-muted-foreground">{m.moTa}</p>
                <p className="mt-3 font-jetbrains text-[11px] text-[var(--color-brass-600)]">
                  ≈ {m.soTruong} trường thông tin
                </p>
              </Link>
            );
          })}
        </div>

        {ketQua.list.length === 0 && (
          <p className="mt-8 text-sm text-muted-foreground">
            Không tìm thấy mẫu phù hợp. Thử từ khoá khác, ví dụ “dịch vụ”, “thử việc”, “ủy quyền”.
          </p>
        )}
      </div>
    </AppShell>
  );
}
