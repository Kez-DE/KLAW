import { Link } from "@tanstack/react-router";
import { Check, ChevronRight, MessageSquare, Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { TrangThaiHoiThoai } from "@/hooks/use-hoi-thoai";
import type { PhienTomTat } from "@/lib/klaw";
import { cauPhienAn, thoiGianTuongDoi } from "@/lib/phien";
import { cn } from "@/lib/utils";

/**
 * Cột phiên hội thoại (spec 2026-09-07 §6). Một danh sách, hai vỏ: aside cố
 * định từ xl (80rem) và sheet trượt lên dưới đó — cùng khuôn với ngăn kéo bộ
 * lọc của trang Tra cứu. Đổi tên và xoá đều làm TẠI CHỖ (Enter lưu, Esc huỷ;
 * xác nhận xoá là hai nút, không `confirm()` — hộp thoại trình duyệt chặn cả
 * tab và không theo được giao diện).
 */
interface Props {
  hoiThoai: TrangThaiHoiThoai;
  phienDangMo: string | undefined;
  onChon: (id: string) => void;
  onPhienMoi: () => void;
  /** Phiên vừa xoá xong — cha quyết định có phải điều hướng đi không. */
  onDaXoa: (id: string) => void;
}

const NUT_PHU =
  "focus-brass grid size-8 cursor-pointer place-items-center rounded-md text-muted-foreground transition-colors hover:bg-[var(--color-brass-500)]/10 hover:text-foreground";

function MotPhien({
  phien,
  dangMo,
  onChon,
  onDoiTen,
  onXoa,
}: {
  phien: PhienTomTat;
  dangMo: boolean;
  onChon: () => void;
  onDoiTen: (tieuDe: string) => Promise<boolean>;
  onXoa: () => Promise<boolean>;
}) {
  const [cheDo, datCheDo] = useState<"xem" | "sua" | "xoa">("xem");
  const [nhap, datNhap] = useState(phien.tieu_de);
  const [loi, datLoi] = useState<string | null>(null);
  const [dangGui, datDangGui] = useState(false);
  const o = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    if (cheDo === "sua") o.current?.select();
  }, [cheDo]);

  const luuTen = async () => {
    const ten = nhap.trim();
    if (ten === "" || ten === phien.tieu_de) {
      datCheDo("xem");
      datNhap(phien.tieu_de);
      return;
    }
    datDangGui(true);
    const ok = await onDoiTen(ten);
    datDangGui(false);
    if (ok) {
      datCheDo("xem");
      datLoi(null);
    } else datLoi("Tôi chưa đổi tên được, thử lại nhé.");
  };
  const xoa = async () => {
    datDangGui(true);
    const ok = await onXoa();
    datDangGui(false);
    if (!ok) datLoi("Tôi chưa xoá được phiên này, thử lại nhé.");
  };

  if (cheDo === "sua") {
    return (
      <li className="rounded-lg border border-[var(--color-brass-500)]/60 bg-card p-2">
        <input
          ref={o}
          value={nhap}
          maxLength={120}
          disabled={dangGui}
          onChange={(su) => datNhap(su.target.value)}
          onKeyDown={(su) => {
            if (su.key === "Enter") {
              su.preventDefault();
              void luuTen();
            }
            if (su.key === "Escape") {
              su.preventDefault();
              datCheDo("xem");
              datNhap(phien.tieu_de);
            }
          }}
          aria-label="Tên phiên"
          className="w-full bg-transparent text-[13px] outline-none"
        />
        <div className="mt-1.5 flex items-center justify-end gap-1">
          <button
            type="button"
            onClick={() => void luuTen()}
            aria-label="Lưu tên"
            className={NUT_PHU}
          >
            <Check className="size-4" aria-hidden />
          </button>
          <button
            type="button"
            onClick={() => {
              datCheDo("xem");
              datNhap(phien.tieu_de);
            }}
            aria-label="Huỷ đổi tên"
            className={NUT_PHU}
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
        {loi !== null && (
          <p role="alert" className="m-0 mt-1 text-[12px] text-destructive">
            {loi}
          </p>
        )}
      </li>
    );
  }
  if (cheDo === "xoa") {
    return (
      <li className="rounded-lg border border-border bg-card p-2.5 text-[12px]">
        <p className="m-0 text-foreground">Xoá phiên này? Các lượt đã hỏi sẽ không mở lại được.</p>
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            disabled={dangGui}
            onClick={() => void xoa()}
            className="focus-brass min-h-8 cursor-pointer rounded-md bg-destructive px-2.5 font-medium text-white disabled:opacity-60"
          >
            Xoá
          </button>
          <button
            type="button"
            onClick={() => datCheDo("xem")}
            className="focus-brass min-h-8 cursor-pointer rounded-md border border-border px-2.5 font-medium text-primary"
          >
            Giữ lại
          </button>
        </div>
        {loi !== null && (
          <p role="alert" className="m-0 mt-1 text-destructive">
            {loi}
          </p>
        )}
      </li>
    );
  }
  return (
    <li
      className={cn(
        "group flex items-start gap-1 rounded-lg border p-2 text-[12px]",
        dangMo
          ? "border-[var(--color-brass-500)]/60 bg-card shadow-soft"
          : "border-transparent hover:bg-card",
      )}
    >
      <button
        type="button"
        onClick={onChon}
        aria-current={dangMo ? "true" : undefined}
        className="focus-brass min-w-0 flex-1 cursor-pointer rounded-md p-1 text-left"
      >
        <span className="block truncate text-[13px] font-medium text-foreground">
          {phien.tieu_de}
        </span>
        <span className="mt-0.5 block text-muted-foreground">
          {phien.so_luot} lượt · {thoiGianTuongDoi(phien.cap_nhat_luc)}
        </span>
      </button>
      <div className="flex shrink-0 opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
        <button
          type="button"
          onClick={() => datCheDo("sua")}
          aria-label={`Đổi tên phiên ${phien.tieu_de}`}
          className={NUT_PHU}
        >
          <Pencil className="size-3.5" aria-hidden />
        </button>
        <button
          type="button"
          onClick={() => datCheDo("xoa")}
          aria-label={`Xoá phiên ${phien.tieu_de}`}
          className={NUT_PHU}
        >
          <Trash2 className="size-3.5" aria-hidden />
        </button>
      </div>
    </li>
  );
}

function ThanDanhSach({ hoiThoai, phienDangMo, onChon, onPhienMoi, onDaXoa }: Props) {
  const { danhSach, dangTai, loi, taiLai, doiTen, xoa } = hoiThoai;
  return (
    <div className="soft-fade">
      <button
        type="button"
        onClick={onPhienMoi}
        className="focus-brass bg-gradient-ink mb-3 inline-flex min-h-9 w-full cursor-pointer items-center justify-center gap-1.5 rounded-lg px-3 text-[13px] font-medium text-primary-foreground transition-opacity hover:opacity-90"
      >
        <Plus className="size-4" aria-hidden /> Phiên mới
      </button>
      {loi !== null ? (
        <div className="rounded-lg border border-dashed border-border p-2.5 text-[12px]">
          <p className="m-0 text-muted-foreground">{loi.message}</p>
          <button
            type="button"
            onClick={taiLai}
            className="focus-brass mt-2 min-h-8 cursor-pointer rounded-md border border-border px-2.5 font-medium text-primary"
          >
            Tải lại
          </button>
        </div>
      ) : danhSach === null ? (
        <p className="text-[12px] text-muted-foreground" aria-live="polite">
          {dangTai ? "Đang tải phiên…" : ""}
        </p>
      ) : danhSach.items.length === 0 ? (
        <p className="text-[12px] text-muted-foreground">
          Chưa có phiên nào. Hỏi một câu để bắt đầu.
        </p>
      ) : (
        <>
          <ul className="m-0 list-none space-y-1 p-0">
            {danhSach.items.map((p) => (
              <MotPhien
                key={p.id}
                phien={p}
                dangMo={p.id === phienDangMo}
                onChon={() => onChon(p.id)}
                onDoiTen={async (t) => (await doiTen(p.id, t)).ok}
                onXoa={async () => {
                  const kq = await xoa(p.id);
                  if (kq.ok) onDaXoa(p.id);
                  return kq.ok;
                }}
              />
            ))}
          </ul>
          {danhSach.tong_an > 0 && (
            <p className="mt-3 border-t border-border pt-2 text-[12px] text-muted-foreground">
              {cauPhienAn(danhSach.plan, danhSach.gioi_han, danhSach.tong_an)}{" "}
              <Link
                to="/bang-gia"
                className="focus-brass text-[var(--color-brass-600)] underline-offset-2 hover:underline"
              >
                Xem bảng giá
              </Link>
            </p>
          )}
        </>
      )}
    </div>
  );
}

export function CotPhien(props: Props) {
  const [panelMo, datPanelMo] = useState(true);
  const [sheetMo, datSheetMo] = useState(false);
  // Chọn/tạo phiên từ sheet thì đóng sheet — người dùng muốn thấy hội thoại.
  const chon = (id: string) => {
    datSheetMo(false);
    props.onChon(id);
  };
  const moi = () => {
    datSheetMo(false);
    props.onPhienMoi();
  };
  const than = <ThanDanhSach {...props} onChon={chon} onPhienMoi={moi} />;
  return (
    <>
      <aside
        aria-label="Phiên hội thoại"
        className={cn(
          "hidden shrink-0 border-l border-border bg-[var(--color-paper-50)] transition-[width] duration-150 xl:block",
          panelMo ? "w-[300px]" : "w-[52px]",
        )}
      >
        <div className="sticky top-[49px] p-3">
          <button
            type="button"
            onClick={() => datPanelMo((m) => !m)}
            aria-label={panelMo ? "Thu gọn cột phiên" : "Mở cột phiên"}
            aria-expanded={panelMo}
            className="focus-brass mb-3 cursor-pointer rounded-md p-1.5 text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/10"
          >
            <ChevronRight
              className={cn("size-4 transition-transform duration-150", panelMo && "rotate-180")}
              aria-hidden
            />
          </button>
          {panelMo && (
            <>
              <p className="border-b border-border pb-2 text-[12px] font-semibold text-primary">
                Phiên hội thoại
              </p>
              <div className="mt-3">{than}</div>
            </>
          )}
        </div>
      </aside>

      <button
        type="button"
        hidden={sheetMo}
        onClick={() => datSheetMo(true)}
        aria-expanded={sheetMo}
        aria-controls="phien-ngan-keo"
        className="focus-brass fixed right-4 bottom-[132px] z-40 inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-full border border-[var(--color-brass-500)]/60 bg-card px-4 text-[13px] font-medium text-[var(--color-brass-600)] shadow-soft xl:hidden"
      >
        <MessageSquare className="size-4" aria-hidden /> Phiên
      </button>
      {sheetMo && (
        <div className="fixed inset-0 z-50 xl:hidden">
          <div
            className="absolute inset-0 bg-[var(--color-ink-950)]/45"
            onClick={() => datSheetMo(false)}
            aria-hidden
          />
          <div
            id="phien-ngan-keo"
            role="dialog"
            aria-modal="true"
            aria-label="Phiên hội thoại"
            className="rise-in absolute inset-x-0 bottom-0 max-h-[82vh] overflow-y-auto rounded-t-2xl border-t border-border bg-background px-4 pt-4 pb-8"
          >
            <div className="mb-2 flex items-center justify-between">
              <p className="font-display m-0 text-sm font-semibold text-primary">Phiên hội thoại</p>
              <button
                type="button"
                onClick={() => datSheetMo(false)}
                aria-label="Đóng danh sách phiên"
                className="focus-brass grid size-11 cursor-pointer place-items-center rounded-md text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
            {than}
          </div>
        </div>
      )}
    </>
  );
}
