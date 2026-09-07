import { useRef, useState } from "react";
import { MenuTaiKhoan } from "@/components/tai-khoan/MenuTaiKhoan";
import { useTaiKhoan } from "@/contexts/tai-khoan";
import { tenGoi } from "@/lib/goi";
import { chuCaiDau, tenHienThi } from "@/lib/tai-khoan";
import { cn } from "@/lib/utils";

/**
 * Thẻ tài khoản ở chân cột trái (spec 2A §7.3). `gon` là cột thu hẹp
 * (48rem–80rem): chỉ còn vòng chữ cái, nên tên và nút "Nâng cấp" phải rời đi
 * chứ không co lại thành một dòng chữ không đọc được.
 */
export function TheTaiKhoan({ gon }: { gon: boolean }) {
  const { user, hanMuc, moNangGoi } = useTaiKhoan();
  const [mo, datMo] = useState(false);
  const nut = useRef<HTMLButtonElement | null>(null);
  const ten = tenHienThi(user);
  const plan = hanMuc.hanMuc?.plan ?? "free";

  return (
    <div className="relative">
      <MenuTaiKhoan mo={mo} onDong={() => datMo(false)} nutMo={nut} />
      <button
        ref={nut}
        type="button"
        onClick={() => datMo((truoc) => !truoc)}
        aria-haspopup="menu"
        aria-expanded={mo}
        aria-label={gon ? "Tài khoản" : undefined}
        title={gon ? ten : undefined}
        className={cn(
          "focus-brass flex w-full cursor-pointer items-center gap-2.5 rounded-lg p-1.5 transition-colors hover:bg-[var(--color-paper-100)]",
          gon && "justify-center",
        )}
      >
        <span
          aria-hidden
          className="bg-gradient-ink grid size-8 shrink-0 place-items-center rounded-full text-[12px] font-semibold text-primary-foreground"
        >
          {chuCaiDau(ten)}
        </span>
        {!gon && (
          <span className="min-w-0 flex-1 text-left">
            <span className="block truncate text-[13px] font-medium text-foreground">{ten}</span>
            <span className="block truncate text-[12px] text-muted-foreground">{tenGoi(plan)}</span>
          </span>
        )}
      </button>
      {!gon && plan !== "pro" && (
        <button
          type="button"
          onClick={moNangGoi}
          className="focus-brass mt-1.5 min-h-9 w-full cursor-pointer rounded-lg border border-[var(--color-brass-500)]/60 text-[13px] font-medium text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/10"
        >
          Nâng cấp
        </button>
      )}
    </div>
  );
}
