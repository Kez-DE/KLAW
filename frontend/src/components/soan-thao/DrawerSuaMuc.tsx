import { useState } from "react";
import { BrassButton } from "@/components/auth/AuthUI";
import type { BanThao, TruongDuKien } from "@/lib/klaw";
import type { Muc } from "@/lib/xuat-tep";

interface Props {
  banThao: BanThao;
  muc: Muc;
  truong: TruongDuKien[];
  /** Lưu — gửi TOÀN bộ facts đã sửa lên `POST /ban-thao/{id}/dung` (dựng lại
   *  cả bản thảo, không chỉ mục này: mục và trường dữ kiện là hai không gian
   *  khoá khác nhau, xem `nhanFactDoi` ở `lib/klaw.ts`). */
  onLuu: (facts: Record<string, string>) => void | Promise<void>;
  /** Mở tấm thứ hai (`KhungDoiChieu`) cho căn cứ của mục. */
  onMoCanCu: (canCu: string) => void;
  /** Huỷ — đóng tấm này mà không lưu. */
  onHuy: () => void;
}

const O_NHAP =
  "focus-brass mt-1 h-11 w-full rounded-lg border border-input bg-card px-2 text-[14px] text-foreground outline-none";
const NUT_HUY =
  "focus-brass cursor-pointer rounded-lg border border-border px-4 py-2 text-[13px] font-medium text-primary hover:bg-secondary";

/**
 * Form sửa một mục trong tấm giữa của drawer xếp chồng (Task 25, spec
 * 2026-09-09 §9.4). Điền từ `banThao.facts` (TOÀN bộ dữ kiện của bản thảo —
 * chỉnh một mục ở đây thực chất là sửa dữ kiện rồi dựng lại cả văn bản, vì
 * nội dung mọi mục cùng sinh từ một bộ facts).
 */
export function DrawerSuaMuc({ banThao, muc, truong, onLuu, onMoCanCu, onHuy }: Props) {
  const [facts, datFacts] = useState<Record<string, string>>(() => ({ ...banThao.facts }));
  const [dangLuu, datDangLuu] = useState(false);

  const luu = async () => {
    datDangLuu(true);
    try {
      await onLuu(facts);
    } finally {
      datDangLuu(false);
    }
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void luu();
      }}
      className="flex h-full flex-col gap-4"
    >
      <div className="min-h-0 flex-1 overflow-y-auto">
        <p className="m-0 rounded-lg bg-[var(--color-paper-50)] p-3 text-[13px] leading-relaxed whitespace-pre-wrap text-muted-foreground">
          {muc.noiDung}
        </p>
        {muc.canCu !== null && (
          <button
            type="button"
            onClick={() => onMoCanCu(muc.canCu ?? "")}
            className="focus-brass font-jetbrains mt-2 cursor-pointer rounded text-[11px] text-[var(--color-brass-600)] hover:underline"
          >
            Căn cứ: {muc.canCu}
          </button>
        )}

        <div className="mt-4 flex flex-col gap-3">
          {truong.map((t) => (
            <label key={t.key} className="block text-[13px] text-muted-foreground">
              {t.nhan}
              {t.lua_chon !== null && t.lua_chon.length > 0 ? (
                <select
                  value={facts[t.key] ?? ""}
                  onChange={(su) => datFacts((cu) => ({ ...cu, [t.key]: su.target.value }))}
                  className={O_NHAP}
                >
                  <option value="">— chưa chọn —</option>
                  {t.lua_chon.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  value={facts[t.key] ?? ""}
                  onChange={(su) => datFacts((cu) => ({ ...cu, [t.key]: su.target.value }))}
                  className={O_NHAP}
                />
              )}
            </label>
          ))}
        </div>
      </div>

      <div className="flex justify-end gap-2 border-t border-border pt-3">
        <button type="button" onClick={onHuy} disabled={dangLuu} className={NUT_HUY}>
          Huỷ
        </button>
        <div className="w-32">
          <BrassButton loading={dangLuu} loadingLabel="Đang lưu…">
            Lưu
          </BrassButton>
        </div>
      </div>
    </form>
  );
}
