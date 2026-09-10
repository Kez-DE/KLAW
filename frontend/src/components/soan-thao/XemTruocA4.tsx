import { cn } from "@/lib/utils";
import type { Muc } from "@/lib/xuat-tep";

interface Props {
  tieuDe: string;
  kyHieu?: string | null;
  muc: Muc[];
  thuPhong: number; // 50–150
  hienCanCu: boolean;
  mucDangChon?: string | null;
  onChonMuc?: (key: string) => void;
  /** Khoá của các mục vừa đổi so với phiên bản trước (nút "Hiện thay đổi",
   *  Task 24) — viền vàng nhạt QUANH mục, cộng một nhãn chữ "(đã đổi)" để
   *  trạng thái không chỉ được báo bằng màu. */
  mucDoi?: string[];
}

/**
 * Trang A4 xem trước cho bản thảo `BanThao` (khung "sân khấu", Task 24).
 *
 * Bấm một mục để đánh dấu nó là đích cho lệnh sửa kế tiếp (khuôn Canvas "chọn vùng").
 * Mục bấm được luôn thao tác được bằng bàn phím (Enter/Space), không chỉ bằng chuột.
 */
export function XemTruocA4({
  tieuDe,
  kyHieu,
  muc,
  thuPhong,
  hienCanCu,
  mucDangChon = null,
  onChonMuc,
  mucDoi = [],
}: Props) {
  const chonMuc = (key: string) => onChonMuc?.(key);

  return (
    <div className="mx-auto w-full max-w-[794px]" style={{ fontSize: `${thuPhong}%` }}>
      <article className="aspect-[210/297] overflow-y-auto rounded-md border border-border bg-white px-[8%] py-[7%] text-[#111] shadow-soft">
        {/* `<h1>`, không `<h2>`: đây là tiêu đề CHÍNH của văn bản đang xem
            trước, và `docNoiDungTuDOM` (xuat-tep.ts) chỉ nhận diện tiêu đề
            xuất ra Word/PDF qua đúng thẻ `H1`. */}
        <h1 className="m-0 text-center font-serif text-[1.25em] font-bold uppercase tracking-wide">
          {tieuDe}
        </h1>
        {kyHieu && (
          <p className="mt-1 text-center font-mono text-[0.85em] text-[#555]">Số: {kyHieu}</p>
        )}
        <div className="mt-6 space-y-4">
          {muc.map((m) => {
            const daDoi = mucDoi.includes(m.key);
            return (
              <section
                key={m.key}
                data-muc={m.key}
                onClick={onChonMuc ? () => chonMuc(m.key) : undefined}
                onKeyDown={
                  onChonMuc
                    ? (e) => {
                        if (e.key !== "Enter" && e.key !== " ") return;
                        e.preventDefault();
                        chonMuc(m.key);
                      }
                    : undefined
                }
                role={onChonMuc ? "button" : undefined}
                tabIndex={onChonMuc ? 0 : undefined}
                aria-current={mucDangChon === m.key ? "true" : undefined}
                aria-label={
                  onChonMuc ? `Chọn mục ${m.stt}. ${m.ten} làm đích chỉnh sửa` : undefined
                }
                className={cn(
                  "rounded-sm px-2 py-1 -mx-2",
                  onChonMuc && "cursor-pointer hover:bg-[var(--color-paper-50)]",
                  // Viền vàng nhạt báo mục vừa đổi; nhãn chữ ngay dưới đây cộng
                  // thêm cho những ai không phân biệt được màu viền.
                  daDoi && "ring-1 ring-[var(--color-brass-400)]",
                  mucDangChon === m.key && "ring-2 ring-[var(--color-brass-600)]",
                )}
              >
                <p className="m-0 font-serif text-[1em] font-semibold">
                  Mục {m.stt}. {m.ten}
                  {daDoi && (
                    <span className="ml-2 text-[0.75em] font-medium text-[var(--color-brass-600)]">
                      (đã đổi)
                    </span>
                  )}
                </p>
                <p className="m-0 mt-1 whitespace-pre-wrap font-serif text-[1em] leading-relaxed">
                  {m.noiDung}
                </p>
                {hienCanCu && m.canCu && (
                  <p className="m-0 mt-1 font-mono text-[0.75em] text-[var(--color-brass-600)]">
                    Căn cứ: {m.canCu}
                  </p>
                )}
              </section>
            );
          })}
        </div>
      </article>
    </div>
  );
}
