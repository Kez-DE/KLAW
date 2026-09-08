import { useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { Bell } from "lucide-react";
import { useTaiKhoan } from "@/contexts/tai-khoan";
import { useThongBao } from "@/hooks/use-thong-bao";
import type { ThongBao } from "@/lib/klaw";
import { thoiGianTuongDoi } from "@/lib/phien";
import { duongDanTrongApp, formatBadge, nhomTheoNgay } from "@/lib/thong-bao";
import { cn } from "@/lib/utils";

const MUC =
  "focus-brass flex w-full cursor-pointer items-start rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-[var(--color-paper-100)]";

/**
 * Chuông thông báo của vỏ ứng dụng (spec 2B §7). Cùng khuôn `TheTaiKhoan` +
 * `MenuTaiKhoan`: nút mở/đóng bằng state cục bộ, popover đóng bằng Escape hoặc
 * bấm ra ngoài, tiêu điểm trả về nút khi đóng.
 */
export function ChuongThongBao() {
  const { daDangNhap } = useTaiKhoan();
  const { soChuaDoc, items, danhDauDaDoc } = useThongBao(daDangNhap);
  const [mo, datMo] = useState(false);
  const nut = useRef<HTMLButtonElement | null>(null);
  // Ổn định vì lý do giống `TheTaiKhoan`: `KhungThongBao` gắn hiệu ứng tiêu
  // điểm theo `onDong`.
  const dong = useCallback(() => datMo(false), []);
  const badge = formatBadge(soChuaDoc);

  return (
    <div className="relative">
      {mo && <KhungThongBao items={items} danhDauDaDoc={danhDauDaDoc} onDong={dong} nutMo={nut} />}
      <button
        ref={nut}
        type="button"
        onClick={() => datMo((truoc) => !truoc)}
        aria-haspopup="menu"
        aria-expanded={mo}
        aria-label={soChuaDoc > 0 ? `Thông báo, ${soChuaDoc} chưa đọc` : "Thông báo"}
        className="focus-brass relative grid size-9 shrink-0 cursor-pointer place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-[var(--color-paper-100)] hover:text-primary"
      >
        <Bell className="size-4" aria-hidden />
        {badge !== null && (
          <span
            aria-hidden
            className="absolute top-0.5 right-0.5 grid min-w-[15px] place-items-center rounded-full bg-destructive px-1 text-[10px] leading-[15px] font-semibold text-white"
          >
            {badge}
          </span>
        )}
      </button>
    </div>
  );
}

interface KhungProps {
  items: ThongBao[];
  danhDauDaDoc: (ids: number[]) => Promise<void>;
  onDong: () => void;
  nutMo: RefObject<HTMLButtonElement | null>;
}

function KhungThongBao({ items, danhDauDaDoc, onDong, nutMo }: KhungProps) {
  const khung = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();
  const nhom = nhomTheoNgay(items, new Date());
  const idsChuaDoc = items.filter((tb) => !tb.da_doc).map((tb) => tb.id);

  useEffect(() => {
    const nut = nutMo.current;
    khung.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();

    const phim = (su: KeyboardEvent) => {
      if (su.key !== "Escape") return;
      su.preventDefault();
      onDong();
    };
    // `mousedown` chứ không `click`: cùng lý do `MenuTaiKhoan` — bấm ra ngoài
    // phải đóng NGAY, trước khi phần tử dưới con trỏ kịp nhận tiêu điểm.
    const bam = (su: MouseEvent) => {
      const dich = su.target;
      if (!(dich instanceof Node)) return;
      if (khung.current?.contains(dich) === true) return;
      if (nut?.contains(dich) === true) return; // nút mở tự đảo trạng thái
      onDong();
    };
    document.addEventListener("keydown", phim);
    document.addEventListener("mousedown", bam);
    return () => {
      document.removeEventListener("keydown", phim);
      document.removeEventListener("mousedown", bam);
      nut?.focus();
    };
  }, [onDong, nutMo]);

  const chon = (tb: ThongBao) => {
    onDong();
    void danhDauDaDoc([tb.id]);
    void navigate({ to: duongDanTrongApp(tb.duong_dan) });
  };

  return (
    <div
      ref={khung}
      className="rise-in absolute right-0 bottom-full z-50 mb-2 max-h-[70vh] w-80 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-xl border border-border bg-card p-2 shadow-soft"
    >
      <div className="flex items-center justify-between gap-2 px-1 pb-1.5">
        <p className="m-0 text-[13px] font-semibold text-foreground">Thông báo</p>
        {idsChuaDoc.length > 0 && (
          <button
            type="button"
            onClick={() => void danhDauDaDoc(idsChuaDoc)}
            className="focus-brass cursor-pointer rounded-md text-[12px] font-medium text-primary hover:underline"
          >
            Đã đọc tất cả
          </button>
        )}
      </div>
      {items.length === 0 ? (
        <p className="m-0 px-1 py-3 text-[13px] text-muted-foreground">Chưa có thông báo nào.</p>
      ) : (
        <div role="menu" aria-label="Thông báo">
          {nhom.map((n) => (
            <div key={n.nhan}>
              <p className="m-0 px-1 pt-2 pb-1 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                {n.nhan}
              </p>
              {n.items.map((tb) => (
                <button
                  key={tb.id}
                  type="button"
                  role="menuitem"
                  onClick={() => chon(tb)}
                  className={MUC}
                >
                  <span className="min-w-0 flex-1">
                    <span
                      className={cn(
                        "block truncate text-[13px] text-foreground",
                        !tb.da_doc && "font-semibold",
                      )}
                    >
                      {tb.tieu_de}
                    </span>
                    <span className="mt-0.5 block truncate text-[12px] text-muted-foreground">
                      {tb.noi_dung}
                    </span>
                    <span className="mt-0.5 block text-[11px] text-muted-foreground">
                      {thoiGianTuongDoi(tb.tao_luc)}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
