import type { MucHanMuc } from "@/lib/klaw";
import { dinhDangMoc, laKhongGioiHan, mucMau, phanTram } from "@/lib/han-muc";
import { cn } from "@/lib/utils";

const MAU = {
  brass: "bg-[var(--color-brass-500)]",
  amber: "bg-amber-500",
  do: "bg-destructive",
} as const;

export function ThuocMucDung({
  muc,
  muiGio,
  gon = false,
}: {
  muc: MucHanMuc[];
  muiGio: string;
  gon?: boolean;
}) {
  return (
    <ul className="m-0 list-none space-y-3 p-0">
      {muc.map((m) => {
        const pt = phanTram(m);
        const khongGioiHan = laKhongGioiHan(m.han_muc);
        return (
          <li key={m.khoa}>
            <div className="flex items-baseline justify-between gap-3 text-[13px]">
              <span className="font-medium text-foreground">{m.nhan}</span>
              <span className="text-muted-foreground">
                {khongGioiHan ? "Không giới hạn" : `${pt}% đã dùng`}
              </span>
            </div>
            {!khongGioiHan && (
              <>
                <div
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={pt}
                  aria-label={m.nhan}
                  className="mt-1 h-2 overflow-hidden rounded-full bg-[var(--color-paper-200)]"
                >
                  <div
                    className={cn("h-full rounded-full transition-[width]", MAU[mucMau(pt)])}
                    style={{ width: `${pt}%` }}
                  />
                </div>
                {!gon && (
                  <p className="m-0 mt-1 text-[12px] text-muted-foreground">
                    {m.da_dung}/{m.han_muc} · Đặt lại {dinhDangMoc(m.dat_lai_luc, muiGio)} ({muiGio}
                    )
                  </p>
                )}
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
