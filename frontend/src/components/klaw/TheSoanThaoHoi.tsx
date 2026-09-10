import { KhoiVanXuoi } from "./TheKetQua";
import type { TraCuuKetQua } from "@/lib/klaw";

/**
 * Card của nhánh `soan_thao_hoi` (Task 21) — nửa "còn thiếu dữ kiện" của một
 * hội thoại soạn thảo. `answer` đã mang nguyên văn câu hỏi/lý do (đăng nhập,
 * hết hạn mức, hay liệt kê dữ kiện còn thiếu — xem `assemble.py`), nên card
 * chỉ vẽ thêm hai việc UI thuần không có trong văn xuôi: chip điền nhanh cho
 * từng khoá có `lua_chon`, và (khi `can_dang_nhap`) một nút mở trang đăng
 * nhập. Bấm chip chỉ ĐIỀN vào ô hỏi qua `onChip`, không tự gửi — người hỏi
 * còn sửa câu trước khi gửi, giống mọi gợi ý khác trong màn `dung-thu`.
 */
export function TheSoanThaoHoi({
  ketQua,
  onChip,
  onDangNhap,
}: {
  ketQua: TraCuuKetQua;
  onChip: (chu: string) => void;
  onDangNhap?: () => void;
}) {
  const sh = ketQua.soan_thao_hoi;
  if (!sh) return null;
  const nhan = Object.fromEntries(sh.con_thieu.map((t) => [t.key, t.nhan]));
  return (
    <section aria-label="Cần thêm dữ kiện để soạn">
      <div className="doc-prose text-foreground">
        <KhoiVanXuoi chu={ketQua.answer ?? ""} />
      </div>
      {sh.can_dang_nhap && onDangNhap && (
        <button
          type="button"
          onClick={onDangNhap}
          className="focus-brass bg-gradient-ink mt-3 cursor-pointer rounded-lg px-4 py-2 text-sm font-medium text-primary-foreground"
        >
          Đăng nhập để soạn
        </button>
      )}
      {Object.entries(sh.chip).map(([khoa, luaChon]) => (
        <div
          key={khoa}
          className="mt-3 flex flex-wrap items-center gap-2"
          role="group"
          aria-label={nhan[khoa] ?? khoa}
        >
          <span className="text-[13px] text-muted-foreground">{nhan[khoa] ?? khoa}:</span>
          {luaChon.map((gt) => (
            <button
              key={gt}
              type="button"
              onClick={() => onChip(`${nhan[khoa] ?? khoa}: ${gt}`)}
              className="focus-brass cursor-pointer rounded-full border border-border bg-card px-3 py-1 text-[13px] hover:bg-[var(--color-paper-100)]"
            >
              {gt}
            </button>
          ))}
        </div>
      ))}
    </section>
  );
}
