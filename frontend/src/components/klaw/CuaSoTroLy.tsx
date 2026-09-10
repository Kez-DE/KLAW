import { useRef, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { Maximize2, MessageCircle, Minus } from "lucide-react";
import { TayKeo } from "@/components/ui/TayKeo";
import {
  BUOC_PHIM,
  BUOC_PHIM_LON,
  CUA_SO_CAO_MIN,
  CUA_SO_RONG_MIN,
  kepCuaSo,
  type CuaSo,
} from "@/lib/keo-dan";

interface Props {
  cuaSo: CuaSo;
  onDoiCuaSo: (cs: CuaSo) => void;
  chuaDoc: number;
  onVeHaiCot: () => void;
  children: ReactNode;
}

const NHAN_CUA_SO = "cua-so-tro-ly";

/**
 * Trợ lý KLAW dạng cửa sổ nổi khi bản thảo là sân khấu (spec 2026-09-09 §9.4).
 *
 * Ba việc di chuyển/đổi cỡ — kéo tiêu đề, kéo hai cạnh — đều đi qua đúng MỘT
 * hàm kẹp (`kepCuaSo`), và cả ba đều thao tác được bằng bàn phím: tiêu đề nhận
 * tiêu điểm và di chuyển bằng phím mũi tên (Shift để đi bước lớn), hai cạnh
 * đổi cỡ dùng lại `TayKeo` — cùng tay kéo W3C Window Splitter đã kiểm ở nơi
 * khác, không viết thêm một lượt xử lý bàn phím thứ hai cho cùng một việc.
 */
export function CuaSoTroLy({ cuaSo, onDoiCuaSo, chuaDoc, onVeHaiCot, children }: Props) {
  const vp = () => ({ w: window.innerWidth, h: window.innerHeight });
  const keo = useRef<{ x: number; y: number; cs: CuaSo } | null>(null);

  const batDauDi = (e: PointerEvent<HTMLElement>) => {
    keo.current = { x: e.clientX, y: e.clientY, cs: cuaSo };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const di = (e: PointerEvent<HTMLElement>) => {
    const k = keo.current;
    if (k === null) return;
    const x = k.cs.x + (e.clientX - k.x);
    const y = k.cs.y + (e.clientY - k.y);
    onDoiCuaSo(kepCuaSo({ ...k.cs, x, y }, vp()));
  };
  const thaDi = (e: PointerEvent<HTMLElement>) => {
    keo.current = null;
    e.currentTarget.releasePointerCapture(e.pointerId);
  };
  /** Tiêu đề nhận tiêu điểm (`tabIndex=0`) rồi di chuyển bằng phím mũi tên —
   *  không có phím này thì cửa sổ chỉ kéo được bằng chuột, hỏng đúng điều mà
   *  tay kéo bên cạnh (`TayKeo`) đã làm đúng. */
  const phimDi = (e: KeyboardEvent<HTMLElement>) => {
    const buoc = e.shiftKey ? BUOC_PHIM_LON : BUOC_PHIM;
    const dx = e.key === "ArrowRight" ? buoc : e.key === "ArrowLeft" ? -buoc : 0;
    const dy = e.key === "ArrowDown" ? buoc : e.key === "ArrowUp" ? -buoc : 0;
    if (dx === 0 && dy === 0) return;
    e.preventDefault();
    onDoiCuaSo(kepCuaSo({ ...cuaSo, x: cuaSo.x + dx, y: cuaSo.y + dy }, vp()));
  };

  if (cuaSo.thu) {
    return (
      <button
        type="button"
        onClick={() => onDoiCuaSo({ ...cuaSo, thu: false })}
        aria-label={chuaDoc > 0 ? `Mở trợ lý KLAW, ${chuaDoc} tin chưa đọc` : "Mở trợ lý KLAW"}
        className="focus-brass bg-gradient-ink fixed right-6 bottom-6 z-50 grid size-14 cursor-pointer place-items-center rounded-full text-primary-foreground shadow-elegant"
      >
        <MessageCircle className="size-6" aria-hidden />
        {chuaDoc > 0 && (
          <span className="absolute -top-1 -right-1 grid size-5 place-items-center rounded-full bg-[var(--color-brass-600)] text-[11px] font-bold text-white">
            {chuaDoc}
          </span>
        )}
      </button>
    );
  }

  return (
    <section
      id={NHAN_CUA_SO}
      role="dialog"
      aria-label="Trợ lý KLAW"
      style={{ left: cuaSo.x, top: cuaSo.y, width: cuaSo.w, height: cuaSo.h }}
      // `fixed` tự nó đã là khối chứa cho hai tay kéo cạnh (absolute, bên
      // dưới) — thêm `relative` chỉ thắng `fixed` trong cùng lớp utility và
      // ném cửa sổ ra ngoài màn hình.
      className="fixed z-50 flex flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-elegant"
    >
      <header
        tabIndex={0}
        aria-label="Di chuyển cửa sổ trợ lý — kéo hoặc dùng phím mũi tên, giữ Shift để đi bước lớn"
        onPointerDown={batDauDi}
        onPointerMove={di}
        onPointerUp={thaDi}
        onPointerCancel={thaDi}
        onKeyDown={phimDi}
        className="focus-brass flex cursor-move touch-none items-center gap-2 border-b border-border px-3 py-2 select-none"
      >
        <span className="font-display flex-1 text-sm font-semibold text-primary">Trợ lý KLAW</span>
        <button
          type="button"
          onClick={onVeHaiCot}
          aria-label="Về bố cục hai cột"
          className="focus-brass cursor-pointer rounded p-1 hover:bg-secondary"
        >
          <Maximize2 className="size-4" aria-hidden />
        </button>
        <button
          type="button"
          onClick={() => onDoiCuaSo({ ...cuaSo, thu: true })}
          aria-label="Thu thành bong bóng"
          className="focus-brass cursor-pointer rounded p-1 hover:bg-secondary"
        >
          <Minus className="size-4" aria-hidden />
        </button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      <TayKeo
        giaTri={cuaSo.w}
        bien={{ min: CUA_SO_RONG_MIN, max: vp().w }}
        nhan="Kéo để đổi bề rộng cửa sổ trợ lý"
        dieuKhienId={NHAN_CUA_SO}
        huong="doc"
        onDoi={(w) => onDoiCuaSo(kepCuaSo({ ...cuaSo, w }, vp()))}
        className="absolute top-0 right-0 h-full"
      />
      <TayKeo
        giaTri={cuaSo.h}
        bien={{ min: CUA_SO_CAO_MIN, max: vp().h }}
        nhan="Kéo để đổi chiều cao cửa sổ trợ lý"
        dieuKhienId={NHAN_CUA_SO}
        huong="ngang"
        onDoi={(h) => onDoiCuaSo(kepCuaSo({ ...cuaSo, h }, vp()))}
        className="absolute right-0 bottom-0 w-full"
      />
    </section>
  );
}
