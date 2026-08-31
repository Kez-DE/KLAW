import { useState } from "react";
import { Link, createFileRoute } from "@tanstack/react-router";
import { Check, Minus, ChevronDown } from "lucide-react";
import { MarketingShell } from "@/components/marketing/MarketingShell";

type TierId = "ca-nhan" | "doanh-nghiep" | "to-chuc";

const TIERS: {
  id: TierId;
  name: string;
  tagline: string;
  monthly: number | null;
  annual: number | null;
  popular?: boolean;
  features: string[];
  cta: string;
  ctaTo: string;
}[] = [
  {
    id: "ca-nhan",
    name: "Cá nhân",
    tagline: "Dành cho luật sư và chuyên viên độc lập",
    monthly: 499_000,
    annual: 399_000,
    features: [
      "Tra cứu không giới hạn",
      "50 lượt hỏi AI/tháng",
      "10 bản thảo/tháng",
      "Xuất Word, PDF",
    ],
    cta: "Dùng thử miễn phí",
    ctaTo: "/dang-ky",
  },
  {
    id: "doanh-nghiep",
    name: "Doanh nghiệp",
    tagline: "Phù hợp phòng pháp chế và công ty luật nhỏ",
    monthly: 1_490_000,
    annual: 1_190_000,
    popular: true,
    features: [
      "Mọi tính năng gói Cá nhân",
      "5 người dùng",
      "500 lượt hỏi AI/tháng",
      "Bản thảo không giới hạn",
      "Thư viện biểu mẫu của tổ chức",
      "Hỗ trợ ưu tiên",
    ],
    cta: "Dùng thử miễn phí",
    ctaTo: "/dang-ky",
  },
  {
    id: "to-chuc",
    name: "Tổ chức lớn",
    tagline: "Liên hệ báo giá",
    monthly: null,
    annual: null,
    features: [
      "Không giới hạn người dùng",
      "Tích hợp hệ thống nội bộ (API)",
      "Triển khai riêng",
      "Quản trị phân quyền",
      "Đào tạo và hỗ trợ chuyên trách",
    ],
    cta: "Liên hệ báo giá",
    ctaTo: "mailto:baogia@klaw.vn",
  },
];

type Row = {
  label: string;
  values: [string | boolean, string | boolean, string | boolean];
};

const COMPARISON: Row[] = [
  {
    label: "Tra cứu văn bản pháp luật",
    values: [true, true, true],
  },
  {
    label: "Lượt hỏi AI mỗi tháng",
    values: ["50", "500", "Không giới hạn"],
  },
  {
    label: "Bản thảo soạn thảo mỗi tháng",
    values: ["10", "Không giới hạn", "Không giới hạn"],
  },
  { label: "Xuất Word, PDF", values: [true, true, true] },
  { label: "Trích dẫn chuẩn tới Điểm, Khoản, Điều", values: [true, true, true] },
  { label: "Số người dùng", values: ["1", "5", "Không giới hạn"] },
  { label: "Thư viện biểu mẫu của tổ chức", values: [false, true, true] },
  { label: "Hỗ trợ", values: ["Chuẩn", "Ưu tiên", "Chuyên trách"] },
  { label: "Tích hợp hệ thống nội bộ (API)", values: [false, false, true] },
  { label: "Triển khai riêng", values: [false, false, true] },
  { label: "Quản trị phân quyền", values: [false, false, true] },
];

// Bốn câu hỏi thường gặp cũ mô tả một hệ thống thanh toán chưa tồn tại: hình
// thức thanh toán, xuất hoá đơn GTGT, huỷ gói trong Cài đặt tài khoản, hạn mức
// làm mới theo chu kỳ, và cam kết hoàn tiền 7 ngày. Không có cái nào được dựng —
// không có cổng thanh toán, không có trang cài đặt tài khoản, không có bảng hạn
// mức. Một cam kết hoàn tiền là lời hứa với người tiêu dùng, nên nó là chuỗi
// nguy hiểm nhất trên trang này.
const FAQS: { q: string; a: string }[] = [
  {
    q: "Có đăng ký được ngay không?",
    a: "Chưa. Bảng giá này là dự kiến. KLAW chưa mở thanh toán: chưa có cổng thanh toán, chưa có hoá đơn, chưa có chính sách huỷ hay hoàn tiền có hiệu lực. Các mức giá dưới đây để tham khảo và có thể thay đổi.",
  },
  {
    q: "Hạn mức lượt hỏi tính thế nào?",
    a: "Chưa tính. Hệ thống hạn mức chưa được dựng ở cả giao diện lẫn máy chủ, nên các con số lượt hỏi trong bảng là dự kiến chứ chưa được thực thi.",
  },
];

function vnd(n: number) {
  return `${n.toLocaleString("vi-VN").replace(/,/g, ".")} ₫`;
}

function CheckBrass() {
  return (
    <span className="mx-auto grid size-5 place-items-center rounded-full bg-brass-500/15 text-brass-600">
      <Check className="size-3" strokeWidth={2.5} />
    </span>
  );
}

function Cell({ value }: { value: string | boolean }) {
  if (value === true) return <CheckBrass />;
  if (value === false)
    return <Minus className="mx-auto size-3.5 text-muted-foreground" />;
  return <span className="text-[13px] text-muted-foreground">{value}</span>;
}

export const Route = createFileRoute("/bang-gia")({
  head: () => ({
    meta: [
      { title: "Bảng giá KLAW — Gói tra cứu & soạn thảo pháp lý" },
      {
        name: "description",
        content:
          "Bảng giá dự kiến của KLAW cho cá nhân, doanh nghiệp và tổ chức lớn. Chưa mở đăng ký và chưa mở thanh toán.",
      },
      { property: "og:title", content: "Bảng giá KLAW — Gói tra cứu & soạn thảo pháp lý" },
      {
        property: "og:description",
        content:
          "Ba mức dự kiến: Cá nhân, Doanh nghiệp và Tổ chức lớn. Chưa mở thanh toán.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: BangGiaPage,
});

function BangGiaPage() {
  const [annual, setAnnual] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  return (
    <MarketingShell>
      <section className="mx-auto max-w-6xl px-6 pt-16 pb-6 text-center">
        <p
          role="status"
          className="mx-auto mb-6 max-w-2xl rounded-xl border border-border bg-card px-4 py-3 text-[13px] leading-relaxed text-muted-foreground"
        >
          <span className="font-semibold text-foreground">Bảng giá dự kiến.</span>{" "}
          KLAW chưa mở thanh toán: chưa có cổng thanh toán, chưa có hạn mức được
          thực thi, chưa có chính sách huỷ hay hoàn tiền có hiệu lực. Mọi con số
          dưới đây là đề xuất và có thể thay đổi.
        </p>
        <p className="soft-fade text-[13px] uppercase tracking-[0.22em] text-brass-600/80">
          Bảng giá
        </p>
        <h1 className="soft-fade mt-3 font-display text-4xl leading-tight text-primary md:text-[44px]">
          Chọn gói phù hợp với công việc pháp lý của bạn
        </h1>
        <p className="soft-fade mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-muted-foreground">
          Bắt đầu dùng thử miễn phí. Nâng cấp bất cứ lúc nào — không ràng buộc
          dài hạn.
        </p>

        {/* Billing toggle */}
        <div className="mt-8 inline-flex items-center gap-1 rounded-full border border-border/70 bg-card/80 p-1">
          {(
            [
              { id: false, label: "Theo tháng" },
              { id: true, label: "Theo năm" },
            ] as const
          ).map((opt) => (
            <button
              key={String(opt.id)}
              type="button"
              onClick={() => setAnnual(opt.id)}
              className={`focus-brass rounded-full px-4 py-1.5 text-[13px] transition-colors duration-150 ${
                annual === opt.id
                  ? "bg-brass-500 font-medium text-ink-950"
                  : "text-muted-foreground hover:text-primary"
              }`}
            >
              {opt.label}
              {opt.id && (
                <span
                  className={`ml-2 rounded-full px-1.5 py-0.5 text-[11px] ${
                    annual
                      ? "bg-primary/10 text-primary"
                      : "bg-brass-500/15 text-brass-600"
                  }`}
                >
                  Tiết kiệm 20%
                </span>
              )}
            </button>
          ))}
        </div>
      </section>

      {/* Tier cards */}
      <section className="mx-auto grid max-w-6xl gap-6 px-6 pb-14 lg:grid-cols-3">
        {TIERS.map((t) => (
          <div
            key={t.id}
            className={`soft-fade relative flex flex-col rounded-2xl p-7 ${
              t.popular
                ? "border border-brass-500 bg-card shadow-[0_0_0_1px_var(--color-brass-500),0_24px_60px_-24px_oklch(0.735_0.112_82/0.35)]"
                : "border border-border/70 bg-card/80"
            }`}
          >
            {t.popular && (
              <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-brass-500 px-3 py-1 text-[12px] font-medium whitespace-nowrap text-ink-950">
                Phổ biến nhất
              </span>
            )}

            <h2 className="font-display text-2xl text-primary">{t.name}</h2>
            <p className="mt-1.5 min-h-[40px] text-[13px] leading-relaxed text-muted-foreground">
              {t.tagline}
            </p>

            <div className="mt-5 flex items-baseline gap-1.5">
              {t.monthly == null ? (
                <span className="font-display text-3xl text-brass-600">
                  Liên hệ báo giá
                </span>
              ) : (
                <>
                  <span className="font-display text-[34px] leading-none text-primary">
                    {vnd(annual ? t.annual! : t.monthly)}
                  </span>
                  <span className="text-[13px] text-muted-foreground">/tháng</span>
                </>
              )}
            </div>
            {t.monthly != null && (
              <p className="mt-1.5 text-[12px] text-muted-foreground">
                {annual
                  ? `Thanh toán theo năm — ${vnd(t.annual! * 12)} / năm`
                  : "Thanh toán hàng tháng, hủy bất cứ lúc nào"}
              </p>
            )}
            {t.monthly == null && (
              <p className="mt-1.5 text-[12px] text-muted-foreground">
                Báo giá theo quy mô và yêu cầu triển khai
              </p>
            )}

            <ul className="mt-6 flex-1 space-y-2.5 border-t border-border/60 pt-6">
              {t.features.map((f) => (
                <li key={f} className="flex items-start gap-2.5 text-[14px] text-foreground/80">
                  <Check className="mt-0.5 size-4 shrink-0 text-brass-600" strokeWidth={2.5} />
                  <span>{f}</span>
                </li>
              ))}
            </ul>

            {t.ctaTo.startsWith("mailto:") ? (
              <a
                href={t.ctaTo}
                className="focus-brass mt-7 inline-flex h-11 items-center justify-center rounded-lg border border-brass-500/60 text-[14px] font-medium text-brass-600 transition-colors duration-150 hover:bg-brass-500/10"
              >
                {t.cta}
              </a>
            ) : (
              <Link
                to={t.ctaTo}
                className={`focus-brass mt-7 inline-flex h-11 items-center justify-center rounded-lg text-[14px] font-medium transition-colors duration-150 ${
                  t.popular
                    ? "bg-brass-500 text-ink-950 hover:bg-brass-400"
                    : "border border-border text-primary hover:border-brass-500/60 hover:text-brass-600"
                }`}
              >
                {t.cta}
              </Link>
            )}
          </div>
        ))}
      </section>

      {/* Comparison table */}
      <section className="mx-auto max-w-6xl px-6 pb-4">
        <h2 className="font-display text-3xl text-primary">
          So sánh chi tiết các gói
        </h2>
        <div className="mt-6 overflow-x-auto rounded-2xl border border-border/70">
          <table className="w-full min-w-[640px] border-collapse text-left">
            <thead>
              <tr className="bg-card/85">
                <th className="px-5 py-4 text-[13px] font-normal text-muted-foreground">
                  Tính năng
                </th>
                {TIERS.map((t) => (
                  <th
                    key={t.id}
                    className={`px-5 py-4 text-center font-display text-[15px] ${
                      t.popular ? "text-brass-600" : "text-primary"
                    }`}
                  >
                    {t.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map((row, i) => (
                <tr
                  key={row.label}
                  className={`border-t border-border/60 ${i % 2 === 1 ? "bg-secondary/50" : ""}`}
                >
                  <td className="px-5 py-3.5 text-[14px] text-foreground/80">
                    {row.label}
                  </td>
                  {row.values.map((v, j) => (
                    <td key={j} className="px-5 py-3.5 text-center">
                      <Cell value={v} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[12px] text-muted-foreground">
          Giá hiển thị chưa bao gồm thuế GTGT.
        </p>
      </section>

      {/* FAQ */}
      <section className="mx-auto max-w-3xl px-6 pt-10 pb-20">
        <h2 className="text-center font-display text-3xl text-primary">
          Câu hỏi thường gặp
        </h2>
        <div className="mt-8 space-y-3">
          {FAQS.map((f, i) => {
            const open = openFaq === i;
            return (
              <div
                key={f.q}
                className={`rounded-xl border transition-colors duration-150 ${
                  open ? "border-brass-500/50 bg-card/85" : "border-border/70 bg-card/60"
                }`}
              >
                <button
                  type="button"
                  onClick={() => setOpenFaq(open ? null : i)}
                  aria-expanded={open}
                  className="focus-brass flex w-full items-center justify-between gap-4 rounded-xl px-5 py-4 text-left"
                >
                  <span className="text-[15px] text-primary">{f.q}</span>
                  <ChevronDown
                    className={`size-4 shrink-0 text-brass-600 transition-transform duration-150 ${
                      open ? "rotate-180" : ""
                    }`}
                  />
                </button>
                {open && (
                  <p className="soft-fade px-5 pb-4 text-[14px] leading-relaxed text-muted-foreground">
                    {f.a}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </MarketingShell>
  );
}
