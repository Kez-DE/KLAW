/**
 * Con chip của một tài liệu đính kèm — trên ô soạn câu hỏi và trên lượt hỏi đã
 * gửi. Đọc tài liệu là việc NỀN (chủ dự án 2026-09-27: "đọc dữ liệu tài liệu
 * thì làm dưới nền, ko cần hiển thị lên UI"): chat không bung bảng dữ kiện nào,
 * con chip là lối vào DUY NHẤT, và mọi thứ làm được với tệp nằm trong menu nhỏ
 * của nó. "Dữ kiện đã đọc" vẫn mở được bảng dữ kiện theo yêu cầu (FR-012,
 * FR-013, FR-024 — xem, sửa, xoá dữ kiện rút từ tài liệu).
 */
import { useEffect, useRef, useState } from "react";
import { Eye, FilePen, FileText, Paperclip, X } from "lucide-react";
import { cn } from "@/lib/utils";

/** Một tệp đã đính kèm. `co_khuon_goc` vắng = chưa biết (tệp gắn lại từ một
 *  lượt cũ): menu chỉ mời "Dữ kiện đã đọc", nơi hai việc kia vẫn có nếu tệp có
 *  khuôn gốc. */
export interface TepDinhKem {
  id: string;
  ten_tep: string;
  co_khuon_goc?: boolean;
  so_trang?: number | null;
}

export interface HanhDongTep {
  onXemBanTaiLen: (tep: { id: string; ten_tep: string; so_trang: number | null }) => void;
  onDienBieuMau: (viecId: string) => void;
  onDuKien: (viecId: string) => void;
}

const MUC =
  "focus-brass flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm hover:bg-muted max-[68rem]:min-h-11";

export function ChipTaiLieu({
  tep,
  hanhDong,
  onBo,
  moLen = true,
}: {
  tep: TepDinhKem;
  hanhDong: HanhDongTep;
  /** Bỏ ĐÚNG tệp này khỏi lượt sắp gửi — chỉ có ở ô soạn. */
  onBo?: ((id: string) => void) | undefined;
  /** Menu mở lên trên (ô soạn ở đáy màn) hay xuống dưới (lượt đã gửi). */
  moLen?: boolean;
}) {
  const [mo, datMo] = useState(false);
  const khung = useRef<HTMLSpanElement | null>(null);
  const nutMo = useRef<HTMLButtonElement | null>(null);
  const mucDau = useRef<HTMLButtonElement | null>(null);

  // Cùng khuôn `MenuDinhKem`: bấm ra ngoài hay Esc thì đóng. Esc trả tiêu điểm
  // về con chip và chặn Esc của sân khấu (nghe ở `window`, sau `document`).
  useEffect(() => {
    if (!mo) return;
    mucDau.current?.focus();
    const ngoai = (su: MouseEvent) => {
      if (!khung.current?.contains(su.target as Node)) datMo(false);
    };
    const phim = (su: KeyboardEvent) => {
      if (su.key !== "Escape" || su.defaultPrevented) return;
      su.preventDefault();
      datMo(false);
      nutMo.current?.focus();
    };
    document.addEventListener("mousedown", ngoai);
    document.addEventListener("keydown", phim);
    return () => {
      document.removeEventListener("mousedown", ngoai);
      document.removeEventListener("keydown", phim);
    };
  }, [mo]);

  /** Tiêu điểm về con chip TRƯỚC khi mở sân khấu/drawer: nơi mở ghi lại
   *  `activeElement`, và mục menu sắp bị tháo — trả tiêu điểm về đó là trả về
   *  `<body>`. */
  const chon = (lam: () => void) => () => {
    nutMo.current?.focus();
    datMo(false);
    lam();
  };

  const coKhuon = tep.co_khuon_goc === true;
  return (
    // Ô soạn (`moLen`): menu neo vào DANH SÁCH chip (nơi gọi đặt `relative`),
    // mép trái — chip nằm sát lề trái màn hẹp, menu 240px neo `right-0` vào một
    // chip ngắn thì tràn khỏi mép trái; neo `left-0` vào chip thứ hai thì tràn
    // mép phải. Lượt đã gửi: chip canh phải, neo `right-0` vào chính nó.
    <span
      ref={khung}
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-[12px]",
        !moLen && "relative",
      )}
    >
      <Paperclip aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
      <button
        ref={nutMo}
        type="button"
        onClick={() => datMo((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={mo}
        aria-label={`Tài liệu ${tep.ten_tep}`}
        title={tep.ten_tep}
        // Đóng sân khấu ở bố cục hẹp dựng lại cả cây chat: trang tìm lại ĐÚNG
        // con chip này bằng khoá để trả tiêu điểm (`noiTraTieuDiem`).
        data-mo-san-khau={`tai_lieu:${tep.id}`}
        // `min-h-6`: nó đứng sát nút bỏ đính kèm, và hai đích dưới 24px cạnh
        // nhau là chỗ ngón tay bấm nhầm (WCAG 2.5.8 AA).
        className="focus-brass inline-flex min-h-6 min-w-0 cursor-pointer items-center truncate rounded px-0.5 underline decoration-dotted underline-offset-2"
      >
        {tep.ten_tep}
      </button>
      {onBo && (
        <button
          type="button"
          onClick={() => onBo(tep.id)}
          aria-label={`Bỏ đính kèm ${tep.ten_tep}`}
          title="Bỏ đính kèm"
          className="focus-brass -mr-1 grid size-5 shrink-0 place-items-center rounded-full hover:bg-background"
        >
          <X aria-hidden className="size-3.5" />
        </button>
      )}
      {mo && (
        <span
          role="menu"
          aria-label={`Việc với ${tep.ten_tep}`}
          className={cn(
            "absolute z-50 flex w-[240px] flex-col rounded-xl border border-border bg-card p-1.5 text-foreground shadow-lg",
            moLen ? "bottom-full left-0 mb-2" : "top-full right-0 mt-2",
          )}
        >
          {coKhuon && (
            <>
              <button
                ref={mucDau}
                type="button"
                role="menuitem"
                onClick={chon(() =>
                  hanhDong.onXemBanTaiLen({
                    id: tep.id,
                    ten_tep: tep.ten_tep,
                    so_trang: tep.so_trang ?? null,
                  }),
                )}
                className={MUC}
              >
                <Eye aria-hidden className="size-4 shrink-0 text-[var(--color-brass-600)]" />
                Xem bản tải lên
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={chon(() => hanhDong.onDienBieuMau(tep.id))}
                className={MUC}
              >
                <FilePen aria-hidden className="size-4 shrink-0 text-[var(--color-brass-600)]" />
                Điền biểu mẫu
              </button>
            </>
          )}
          <button
            ref={coKhuon ? undefined : mucDau}
            type="button"
            role="menuitem"
            onClick={chon(() => hanhDong.onDuKien(tep.id))}
            className={MUC}
          >
            <FileText aria-hidden className="size-4 shrink-0 text-muted-foreground" />
            Dữ kiện đã đọc
          </button>
        </span>
      )}
    </span>
  );
}
