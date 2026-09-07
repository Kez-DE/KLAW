import { dungLuoiHoatDong, type HoatDongNgay } from "@/lib/lich-hoat-dong";
import { cn } from "@/lib/utils";

/**
 * Lịch hoạt động 365 ngày kiểu GitHub — 53 tuần × 7 ngày, tuần bắt đầu thứ
 * Hai (spec 2A §7.4, trang Hồ sơ).
 *
 * Toán ngày, tứ phân vị và dựng lưới nằm ở `lib/lich-hoat-dong.ts` (kiểm bằng
 * `scripts/kiem-lich-hoat-dong.ts`, không cần dựng DOM); component này chỉ lo
 * phần vẽ.
 */
const MAU_MUC: Record<0 | 1 | 2 | 3 | 4, string> = {
  0: "bg-[var(--color-paper-200)]",
  1: "bg-[var(--color-brass-500)]/25",
  2: "bg-[var(--color-brass-500)]/50",
  3: "bg-[var(--color-brass-500)]/75",
  4: "bg-[var(--color-brass-500)]/100",
};

export function LichHoatDong({ hoatDong }: { hoatDong: HoatDongNgay[] }) {
  const { oLuoi, nhanThang } = dungLuoiHoatDong(hoatDong, new Date());

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
