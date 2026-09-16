/**
 * Menu bong bóng của nút kẹp giấy trên ô soạn câu hỏi.
 *
 * Bấm kẹp giấy là mở NGAY hộp chọn tệp của máy — đó là việc người dùng định
 * làm, và bắt họ đi qua một khung trung gian để tìm lại đúng cái nút đó là
 * thêm một bước không mua được gì.
 *
 * Menu tồn tại vì sau này còn nguồn khác (ảnh chụp màn hình, tệp đã tải lên
 * trước). Hôm nay nó có một mục, và một mục vẫn hơn một nút câm: nhãn nói ra
 * cái sắp xảy ra, thay vì để người dùng đoán biểu tượng.
 */
import { useEffect, useRef, useState } from "react";
import { Paperclip, Upload } from "lucide-react";
import { DINH_DANG_CHAP_NHAN } from "@/lib/tai-lieu";

export function MenuDinhKem({
  onChonTep,
  khoa,
}: {
  onChonTep: (tep: File) => void;
  /** Đang đọc một tệp khác — không nhận thêm cho tới khi xong. */
  khoa?: boolean | undefined;
}) {
  const [mo, datMo] = useState(false);
  const oTep = useRef<HTMLInputElement | null>(null);
  const khung = useRef<HTMLDivElement | null>(null);

  // Bấm ra ngoài hoặc Esc thì đóng. Menu che mất ô soạn, nên nó phải dễ bỏ
  // hơn là dễ mở.
  useEffect(() => {
    if (!mo) return;
    const ngoai = (su: MouseEvent) => {
      if (!khung.current?.contains(su.target as Node)) datMo(false);
    };
    const phim = (su: KeyboardEvent) => {
      if (su.key === "Escape") datMo(false);
    };
    document.addEventListener("mousedown", ngoai);
    document.addEventListener("keydown", phim);
    return () => {
      document.removeEventListener("mousedown", ngoai);
      document.removeEventListener("keydown", phim);
    };
  }, [mo]);

  return (
    <div ref={khung} className="relative">
      <input
        ref={oTep}
        type="file"
        accept={DINH_DANG_CHAP_NHAN}
        className="sr-only"
        onChange={(su) => {
          const tep = su.target.files?.[0];
          if (tep) onChonTep(tep);
          su.target.value = ""; // chọn lại CÙNG một tệp vẫn phải kích hoạt
          datMo(false);
        }}
      />
      <button
        type="button"
        disabled={khoa}
        aria-haspopup="menu"
        aria-expanded={mo}
        title="Đính kèm tài liệu để rút dữ kiện"
        aria-label="Đính kèm tài liệu để rút dữ kiện"
        onClick={() => datMo((cu) => !cu)}
        className="focus-brass mb-0.5 rounded-lg p-2 text-muted-foreground hover:bg-muted disabled:opacity-40"
      >
        <Paperclip className="size-4" aria-hidden />
      </button>

      {mo && (
        <div
          role="menu"
          aria-label="Nguồn đính kèm"
          className="absolute bottom-full left-0 z-50 mb-2 w-[320px] rounded-xl border border-border bg-card p-1.5 shadow-lg"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => oTep.current?.click()}
            className="focus-brass flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-muted"
          >
            <Upload aria-hidden className="size-4 shrink-0 text-muted-foreground" />
            <span className="min-w-0">
              <span className="block text-sm">Thêm tệp & hình</span>
              <span className="block truncate text-xs text-muted-foreground">
                PDF, DOCX hoặc ảnh chụp giấy tờ
              </span>
            </span>
          </button>
          {/* Câu này đổi cùng lúc với cơ chế: từ 2026-09-16 KLAW giữ NGUYÊN VĂN
              đã đọc trong hội thoại (để lượt sau còn hỏi tiếp về tài liệu), chứ
              không chỉ giữ mấy dữ kiện rút ra. Nói đúng thứ hệ thống giữ và
              đúng lúc nó biến mất là điều kiện để người dùng quyết định được
              có gửi tệp hay không. */}
          <p className="px-3 py-1.5 text-[11px] text-muted-foreground">
            Tệp gốc không được lưu. Nội dung đã đọc ở lại trong cuộc trò chuyện này và xoá cùng nó.
          </p>
        </div>
      )}
    </div>
  );
}
