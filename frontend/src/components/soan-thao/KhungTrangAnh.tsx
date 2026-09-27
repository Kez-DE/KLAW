import { useEffect, useMemo, useState } from "react";
import { FilePen, Minus, Plus, RotateCcw, X } from "lucide-react";
import { layTrang } from "@/lib/api";
import { kepRong, type Bien } from "@/lib/keo-dan";
import { DUONG_DAN_KHUON, loiTrang } from "@/lib/khuon-goc";
import type { ApiResult, TrangAnh } from "@/lib/klaw";
import { cn } from "@/lib/utils";

const BIEN_ZOOM: Bien = { min: 50, max: 150 };
const BUOC_ZOOM = 10;
/** 1 pt = 4/3 px CSS (96 dpi): một trang A4 (595 pt) rộng ~794 px ở 100%,
 *  đúng bề rộng tờ của `XemTruocA4` — đổi qua lại hai kiểu xem không nhảy cỡ. */
const PX_MOI_PT = 4 / 3;
/** Khung chờ khi chưa biết khổ nào (lần tải đầu): A4 dọc. */
const KHO_A4: [number, number] = [595.28, 841.89];

const NUT_PHU =
  "focus-brass inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-[12.5px] text-primary transition-colors hover:bg-[var(--color-paper-100)] disabled:cursor-not-allowed disabled:opacity-60";

/** Thu nhỏ/phóng to — CÙNG bậc và biên cho mọi kiểu xem trên sân khấu. */
export function ThanhThuPhong({
  thuPhong,
  datThuPhong,
}: {
  thuPhong: number;
  datThuPhong: (doi: (z: number) => number) => void;
}) {
  const doi = (buoc: number) => datThuPhong((z) => kepRong(z + buoc, BIEN_ZOOM));
  return (
    <div className="flex items-center gap-1 rounded-lg border border-border p-0.5">
      <button
        type="button"
        aria-label="Thu nhỏ"
        onClick={() => doi(-BUOC_ZOOM)}
        className="focus-brass cursor-pointer rounded-md p-1.5 hover:bg-[var(--color-paper-100)]"
      >
        <Minus className="size-3.5" aria-hidden />
      </button>
      <span className="font-jetbrains w-10 text-center text-[11px]">{thuPhong}%</span>
      <button
        type="button"
        aria-label="Phóng to"
        onClick={() => doi(BUOC_ZOOM)}
        className="focus-brass cursor-pointer rounded-md p-1.5 hover:bg-[var(--color-paper-100)]"
      >
        <Plus className="size-3.5" aria-hidden />
      </button>
    </div>
  );
}

interface PropsKhung {
  /** `DUONG_DAN_KHUON.trangTaiLieu`/`trangBanThao` — cũng là KHOÁ tải: nó mang
   *  (nguồn, id, phiên bản), nên đổi nó (và chỉ nó) là tải lại. */
  duongDan: string;
  /** Số khung chờ trước khi biết khổ thật. */
  soTrang: number | null;
  thuPhong: number;
  /** Tên vùng cho trình đọc màn hình. */
  nhan: string;
}

/**
 * Các trang của một khuôn gốc, đúng như máy chủ dựng (LibreOffice → PDF →
 * PNG), xếp chồng như những tờ giấy — mỗi tờ theo khổ CỦA NÓ (Letter vẫn là
 * Letter). Chỉ đọc.
 *
 * Tải MỘT lần cho mỗi `duongDan`: một lượt dựng giữ suất LibreOffice của CẢ
 * tài khoản (lượt thứ hai cùng lúc là 503 `qua_tai`), còn sân khấu vẽ lại trên
 * mỗi token chat và mỗi pixel kéo. Đổi đường dẫn huỷ lượt cũ và bỏ phản hồi
 * muộn của nó (so `duongDan`, không tin thứ tự về). Ảnh là `data:` URL dựng
 * một lần mỗi payload (`useMemo`) — không object URL nào để thu hồi.
 */
export function KhungTrangAnh({ duongDan, soTrang, thuPhong, nhan }: PropsKhung) {
  const [lanThu, datLanThu] = useState(0);
  const [ket, datKet] = useState<{ duongDan: string; kq: ApiResult<TrangAnh> } | null>(null);
  // Khổ của lần hiện gần nhất: khung chờ của phiên bản kế tiếp đứng đúng tỉ lệ.
  const [khoCu, datKhoCu] = useState<[number, number][] | null>(null);

  useEffect(() => {
    const dieuKhien = new AbortController();
    void layTrang(duongDan, dieuKhien.signal).then((kq) => {
      if (dieuKhien.signal.aborted) return;
      datKet({ duongDan, kq });
      if (kq.ok) datKhoCu(kq.data.kho);
    });
    return () => dieuKhien.abort();
  }, [duongDan, lanThu]);

  const kq = ket !== null && ket.duongDan === duongDan ? ket.kq : null;
  const anh = useMemo(
    () =>
      kq?.ok
        ? kq.data.trang.map((b64, i) => ({
            src: `data:image/png;base64,${b64}`,
            kho: kq.data.kho[i] ?? KHO_A4,
          }))
        : null,
    [kq],
  );
  const loi = kq !== null && !kq.ok ? loiTrang(kq.error, duongDan) : null;
  const dangTai = kq === null;
  const rong = (w: number) => `${(w * PX_MOI_PT * thuPhong) / 100}px`;
  const thuLai = () => {
    datKet(null);
    datLanThu((n) => n + 1);
  };

  return (
    <div
      role="region"
      aria-label={nhan}
      aria-busy={dangTai}
      className="flex flex-col items-center gap-4"
    >
      <p
        role="status"
        className={cn("m-0 text-[13px] text-muted-foreground", !dangTai && "sr-only")}
      >
        {dangTai ? "Đang dựng trang…" : anh !== null ? `Đã hiện ${anh.length} trang.` : ""}
      </p>
      {loi !== null && (
        <div
          role="alert"
          className="w-full max-w-[794px] rounded-xl border border-l-2 border-border bg-[var(--color-paper-50)] p-4"
          style={{ borderLeftColor: "var(--color-status-neutral)" }}
        >
          <p className="m-0 text-[14px] leading-6 text-foreground">{loi.cau}</p>
          {loi.thuLai && (
            <button type="button" onClick={thuLai} className={cn(NUT_PHU, "mt-3")}>
              <RotateCcw className="size-3.5" aria-hidden /> Thử lại
            </button>
          )}
        </div>
      )}
      {dangTai &&
        Array.from({ length: soTrang ?? khoCu?.length ?? 1 }, (_, i) => {
          const [w, h] = khoCu?.[i] ?? khoCu?.[0] ?? KHO_A4;
          return (
            <div
              key={i}
              data-khung-cho=""
              aria-hidden
              className="animate-pulse rounded-md border border-border bg-white/70 shadow-soft"
              style={{ width: rong(w), maxWidth: "100%", aspectRatio: `${w} / ${h}` }}
            />
          );
        })}
      {anh?.map((a, i) => (
        <img
          key={i}
          src={a.src}
          alt={`Trang ${i + 1} / ${anh.length}`}
          width={Math.round(a.kho[0] * PX_MOI_PT)}
          height={Math.round(a.kho[1] * PX_MOI_PT)}
          decoding="async"
          className="block h-auto rounded-md border border-border bg-white shadow-soft"
          style={{
            width: rong(a.kho[0]),
            maxWidth: "100%",
            aspectRatio: `${a.kho[0]} / ${a.kho[1]}`,
          }}
        />
      ))}
    </div>
  );
}

interface PropsBanTaiLen {
  viecId: string;
  tenTep: string;
  soTrang: number | null;
  /** Cửa đóng DUY NHẤT của sân khấu ở trang gọi (`onDongSanKhau`). */
  onDong: () => void;
  onDienBieuMau: () => void;
}

/**
 * Sân khấu "Bản tải lên" — tệp người dùng tải lên, đúng như tệp, chỉ xem
 * (`CONTEXT.md` khuôn gốc; nhãn KHÔNG phải "bản gốc", chữ đó là nguyên văn
 * luật). Cùng khuôn đầu/thanh công cụ/thân của `SanKhauBanThao`; tiêu đề nhận
 * tiêu điểm khi mở (`data-tieu-de-san-khau`, trang gọi đưa tiêu điểm vào).
 */
export function SanKhauBanTaiLen({
  viecId,
  tenTep,
  soTrang,
  onDong,
  onDienBieuMau,
}: PropsBanTaiLen) {
  const [thuPhong, datThuPhong] = useState(100);
  return (
    <div className="grid h-full min-w-0 flex-1 grid-rows-[auto_auto_1fr]">
      <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
        <h2
          data-tieu-de-san-khau=""
          tabIndex={-1}
          title={tenTep}
          className="focus-brass m-0 min-w-0 flex-1 truncate rounded-sm font-display text-base font-semibold text-primary"
        >
          {tenTep}
        </h2>
        <span className="rounded-md bg-[var(--color-paper-50)] px-2 py-0.5 text-[12px] text-muted-foreground">
          Bản tải lên · chỉ xem
        </span>
        <button type="button" onClick={onDienBieuMau} className={NUT_PHU}>
          <FilePen className="size-3.5 text-[var(--color-brass-600)]" aria-hidden />
          Điền biểu mẫu
        </button>
        <button
          type="button"
          onClick={onDong}
          aria-label="Đóng bản tải lên"
          className="focus-brass cursor-pointer rounded-md border border-border p-1.5 text-muted-foreground hover:bg-[var(--color-paper-100)]"
        >
          <X className="size-4" aria-hidden />
        </button>
      </header>
      <div className="flex flex-wrap items-center gap-3 border-b border-border px-3 py-2">
        <ThanhThuPhong thuPhong={thuPhong} datThuPhong={datThuPhong} />
      </div>
      <div className="min-h-0 overflow-y-auto bg-[var(--color-paper-100)] p-6">
        <KhungTrangAnh
          duongDan={DUONG_DAN_KHUON.trangTaiLieu(viecId)}
          soTrang={soTrang}
          thuPhong={thuPhong}
          nhan="Các trang của bản tải lên"
        />
      </div>
    </div>
  );
}
