import { cn } from "@/lib/utils";

/**
 * Lịch hoạt động 365 ngày kiểu GitHub — 53 tuần × 7 ngày, tuần bắt đầu thứ
 * Hai (spec 2A §7.4, trang Hồ sơ).
 *
 * Mọi mốc ngày dựng bằng `Date.UTC`/`getUTC*`, KHÔNG đi qua giờ máy: chuỗi
 * `ngay` do component tự sinh được so khớp với `so_luot` của máy chủ chỉ bằng
 * so sánh CHUỖI (`Map<string, number>`), nên `ngay` gốc từ máy chủ không bao
 * giờ bị đưa qua `new Date(...)` rồi đọc lại theo múi giờ trình duyệt — đúng
 * thứ lỗi khiến một ô lùi sang ngày bên cạnh ở múi giờ âm.
 */

interface HoatDongNgay {
  ngay: string;
  so_luot: number;
}

const SO_TUAN = 53;
const SO_NGAY = SO_TUAN * 7 - 6; // 365 — 53 cột chứa đúng 365 ô thật + 6 ô đệm
const MS_NGAY = 86_400_000;

const MAU_MUC: Record<0 | 1 | 2 | 3 | 4, string> = {
  0: "bg-[var(--color-paper-200)]",
  1: "bg-[var(--color-brass-500)]/25",
  2: "bg-[var(--color-brass-500)]/50",
  3: "bg-[var(--color-brass-500)]/75",
  4: "bg-[var(--color-brass-500)]/100",
};

/** Tên tháng viết tắt tiếng Việt, dựng một lần — không lệ thuộc múi giờ trình duyệt. */
const THANG_NHAN = Array.from({ length: 12 }, (_, m) =>
  new Intl.DateTimeFormat("vi-VN", { month: "short", timeZone: "UTC" }).format(
    new Date(Date.UTC(2000, m, 1)),
  ),
);

function chuoiNgay(t: number): string {
  const d = new Date(t);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}`;
}

/** Tứ phân vị của các giá trị dương — bốn mức tô đậm dần cho ô có hoạt động. */
function tuPhanVi(duongTinh: number[]): readonly [number, number, number] {
  const s = [...duongTinh].sort((a, b) => a - b);
  const cuoi = s.length - 1;
  const tai = (p: number) => s[Math.max(0, Math.floor(cuoi * p))] ?? 0;
  return [tai(0.25), tai(0.5), tai(0.75)];
}

function mucCua(
  soLuot: number,
  [q1, q2, q3]: readonly [number, number, number],
): 0 | 1 | 2 | 3 | 4 {
  if (soLuot <= 0) return 0;
  if (soLuot <= q1) return 1;
  if (soLuot <= q2) return 2;
  if (soLuot <= q3) return 3;
  return 4;
}

interface O {
  t: number;
  ngay: string;
  soLuot: number;
  muc: 0 | 1 | 2 | 3 | 4;
}

export function LichHoatDong({ hoatDong }: { hoatDong: HoatDongNgay[] }) {
  const homNay = new Date();
  const mocHomNay = Date.UTC(homNay.getFullYear(), homNay.getMonth(), homNay.getDate());
  const theoNgay = new Map(hoatDong.map((h) => [h.ngay, h.so_luot]));
  const nguong = tuPhanVi(hoatDong.map((h) => h.so_luot).filter((n) => n > 0));

  const oNgay: O[] = Array.from({ length: SO_NGAY }, (_, i) => {
    const t = mocHomNay - (SO_NGAY - 1 - i) * MS_NGAY;
    const ngay = chuoiNgay(t);
    const soLuot = theoNgay.get(ngay) ?? 0;
    return { t, ngay, soLuot, muc: mucCua(soLuot, nguong) };
  });

  // Thứ Hai = 0 .. Chủ nhật = 6, suy từ `getUTCDay()` (Chủ nhật = 0).
  const dauTuan = (new Date(oNgay[0]!.t).getUTCDay() + 6) % 7;
  const oCuoi = 6 - dauTuan;
  const oLuoi: (O | null)[] = [
    ...Array.from({ length: dauTuan }, () => null),
    ...oNgay,
    ...Array.from({ length: oCuoi }, () => null),
  ];

  const nhanThang: string[] = [];
  let thangTruoc = -1;
  for (let c = 0; c < SO_TUAN; c++) {
    let thang = -1;
    for (let r = 0; r < 7; r++) {
      const o = oLuoi[c * 7 + r];
      if (o !== undefined && o !== null) {
        thang = new Date(o.t).getUTCMonth();
        break;
      }
    }
    nhanThang.push(thang !== thangTruoc ? (THANG_NHAN[thang] ?? "") : "");
    thangTruoc = thang;
  }

  return (
    <div
      role="region"
      tabIndex={0}
      aria-label="Lịch hoạt động 52 tuần"
      className="focus-brass overflow-x-auto rounded-lg"
    >
      <div className="grid grid-flow-col grid-rows-7 gap-[3px]" aria-hidden>
        {oLuoi.map((o, i) =>
          o === null ? (
            <div key={i} className="size-2.5" />
          ) : (
            <div
              key={o.ngay}
              title={`${o.ngay.slice(8, 10)}/${o.ngay.slice(5, 7)}: ${o.soLuot} lượt`}
              className={cn("size-2.5 rounded-[2px]", MAU_MUC[o.muc])}
            />
          ),
        )}
      </div>
      <div className="mt-1 flex gap-[3px]" aria-hidden>
        {nhanThang.map((nhan, i) => (
          <span
            key={i}
            className="w-2.5 shrink-0 text-left text-[9px] leading-none whitespace-nowrap text-muted-foreground"
          >
            {nhan}
          </span>
        ))}
      </div>
    </div>
  );
}
