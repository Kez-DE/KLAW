import { useRef, type KeyboardEvent, type PointerEvent } from "react";
import { BUOC_PHIM, BUOC_PHIM_LON, kepRong, phanTram, type Bien } from "@/lib/keo-dan";
import { cn } from "@/lib/utils";

interface Props {
  /** Kích cỡ hiện tại của pane CHÍNH (px). */
  giaTri: number;
  bien: Bien;
  nhan: string;
  dieuKhienId: string;
  onDoi: (px: number) => void;
  onThuGon?: () => void;
  /** Bấm đôi: đưa pane chính về độ rộng mặc định. */
  onMacDinh?: () => void;
  /** "doc" = vách dọc kéo trái/phải (mặc định). */
  huong?: "doc" | "ngang";
  /** Kéo sang phải LÀM TĂNG hay GIẢM pane chính — panel bên phải dùng `-1`. */
  chieu?: 1 | -1;
  className?: string;
}

/** Tay kéo theo W3C APG Window Splitter: separator có tiêu điểm, mũi tên/Home/End/Enter, pointer capture. */
export function TayKeo({
  giaTri,
  bien,
  nhan,
  dieuKhienId,
  onDoi,
  onThuGon,
  onMacDinh,
  huong = "doc",
  chieu = 1,
  className,
}: Props) {
  const goc = useRef<{ toaDo: number; giaTri: number } | null>(null);
  const doc = huong === "doc";

  const batDau = (e: PointerEvent<HTMLDivElement>) => {
    goc.current = { toaDo: doc ? e.clientX : e.clientY, giaTri };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const keo = (e: PointerEvent<HTMLDivElement>) => {
    if (goc.current === null) return;
    const lech = (doc ? e.clientX : e.clientY) - goc.current.toaDo;
    onDoi(kepRong(goc.current.giaTri + chieu * lech, bien));
  };
  const ketThuc = (e: PointerEvent<HTMLDivElement>) => {
    goc.current = null;
    e.currentTarget.releasePointerCapture(e.pointerId);
  };
  const phim = (e: KeyboardEvent<HTMLDivElement>) => {
    const buoc = e.shiftKey ? BUOC_PHIM_LON : BUOC_PHIM;
    const tang = doc ? ["ArrowRight"] : ["ArrowDown"];
    const giam = doc ? ["ArrowLeft"] : ["ArrowUp"];
    if (tang.includes(e.key)) onDoi(kepRong(giaTri + chieu * buoc, bien));
    else if (giam.includes(e.key)) onDoi(kepRong(giaTri - chieu * buoc, bien));
    else if (e.key === "Home") onDoi(bien.min);
    else if (e.key === "End") onDoi(bien.max);
    else if (e.key === "Enter" && onThuGon) onThuGon();
    else return;
    e.preventDefault();
  };

  return (
    <div
      role="separator"
      tabIndex={0}
      aria-orientation={doc ? "vertical" : "horizontal"}
      aria-label={nhan}
      aria-controls={dieuKhienId}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={phanTram(giaTri, bien)}
      onPointerDown={batDau}
      onPointerMove={keo}
      onPointerUp={ketThuc}
      onPointerCancel={ketThuc}
      onKeyDown={phim}
      onDoubleClick={onMacDinh}
      className={cn(
        // Phase 15 R8 — vùng BẤM 24px (WCAG 2.2 SC 2.5.8) nhưng chỗ chiếm trong
        // bố cục vẫn 8px (`RONG_TAY_KEO_PX`, keo-dan.ts tính biên panel theo
        // số này) và vạch vẽ bên dưới không đổi: nới bằng một `::before` trong
        // suốt tràn 8px mỗi bên — pseudo-element vẫn thuộc phần tử này khi
        // hit-test, nên `onPointerDown`/capture nhận được như bấm vào vạch.
        "focus-brass group relative shrink-0 touch-none select-none before:absolute",
        doc
          ? "w-2 cursor-col-resize before:inset-y-0 before:-left-2 before:-right-2"
          : "h-2 cursor-row-resize before:inset-x-0 before:-top-2 before:-bottom-2",
        className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          "absolute rounded-full bg-border transition-colors group-hover:bg-[var(--color-brass-500)] group-focus-visible:bg-[var(--color-brass-500)]",
          doc
            ? "top-1/2 left-1/2 h-10 w-1 -translate-x-1/2 -translate-y-1/2"
            : "top-1/2 left-1/2 h-1 w-10 -translate-x-1/2 -translate-y-1/2",
        )}
      />
    </div>
  );
}
