import { useEffect, useId, useMemo, useRef, useState, type CSSProperties } from "react";
import { FilePen, Minus, Plus, RotateCcw, TextCursorInput, X } from "lucide-react";
import { layTrang } from "@/lib/api";
import { kepRong, type Bien } from "@/lib/keo-dan";
import {
  DUONG_DAN_KHUON,
  giaTriHienThi,
  khoaO,
  loiTrang,
  nhanNutDien,
  nhanO,
  oKeTiep,
  viTriO,
} from "@/lib/khuon-goc";
import { oHopLe, type ApiResult, type OTrang, type TrangAnh } from "@/lib/klaw";
import { cn } from "@/lib/utils";

const BIEN_ZOOM: Bien = { min: 50, max: 150 };
const BUOC_ZOOM = 10;
/** 1 pt = 4/3 px CSS (96 dpi): một trang A4 (595 pt) rộng ~794 px ở 100%,
 *  đúng bề rộng tờ của `XemTruocA4` — đổi qua lại hai kiểu xem không nhảy cỡ. */
const PX_MOI_PT = 4 / 3;
/** Khung chờ khi chưa biết khổ nào (lần tải đầu): A4 dọc. */
const KHO_A4: [number, number] = [595.28, 841.89];

// `max-[68rem]:` = bố cục hẹp (`useHaiCot`, `min-width: 68rem`): vùng chạm 44px
// (DESIGN.md Responsive) chỉ ở đó, bố cục rộng giữ nguyên mật độ.
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

/** Ghi chữ chờ lưu của MỘT chỗ trống vào `nhapODien` của trang gọi (khoá
 *  `khoaO`); `undefined` = bỏ chữ chờ lưu, chỗ đó đọc lại giá trị đang có. */
type DatNhap = (khoa: string, giaTri: string | undefined) => void;
/** Đóng ô nhập: 0 = tiêu điểm về nút của chính chỗ đó, ±1 = sang chỗ kế/trước
 *  theo thứ tự đọc, `null` = không dời tiêu điểm (người dùng đã bấm chỗ khác). */
type Huong = -1 | 0 | 1 | null;

/**
 * Chỗ trống đang mở ô nhập, và nút nhận tiêu điểm khi ô đóng — dùng chung cho
 * trang và danh sách "chưa định vị". Tiêu điểm tìm nút theo khoá `(don_vi,
 * so)`, không theo phần tử: ô nhập vừa đóng thì nút của nó mới dựng lại.
 */
function useSuaTaiCho(ds: readonly OTrang[]) {
  const [dangMo, datDangMo] = useState<string | null>(null);
  const nut = useRef(new Map<string, HTMLButtonElement>());
  const veTieuDiem = useRef<string | null>(null);
  useEffect(() => {
    const k = veTieuDiem.current;
    const n = k === null ? undefined : nut.current.get(k);
    if (n === undefined) return;
    veTieuDiem.current = null;
    n.focus();
  });
  return {
    dangMo,
    mo: datDangMo,
    // Chỉ ô ĐANG mở được đóng và dời tiêu điểm: một lời gọi muộn từ ô đã đóng
    // (blur tới sau Enter) không được kéo tiêu điểm khỏi ô người dùng vừa mở ở
    // chỗ khác. Ghi ref trong updater là lũy đẳng (StrictMode gọi hai lần).
    xong: (khoa: string, huong: Huong) => {
      datDangMo((cu) => {
        if (cu !== khoa) return cu;
        veTieuDiem.current =
          huong === null ? null : huong === 0 ? khoa : (oKeTiep(ds, khoa, huong) ?? khoa);
        return null;
      });
    },
    refNut: (khoa: string) => (el: HTMLButtonElement | null) => {
      if (el === null) nut.current.delete(khoa);
      else nut.current.set(khoa, el);
    },
  };
}

/**
 * Ô nhập tại chỗ của MỘT chỗ trống. KHÔNG tự lưu: mỗi lần lưu là một phiên bản
 * tính vào trần sửa (`TRAN_SUA` = 10, chung với lượt chat), nên lưu từng chỗ
 * thì một biểu mẫu 30 chỗ kẹt ở chỗ thứ 10. Chữ gõ tới đâu vào `nhapODien` của
 * trang gọi tới đó, và "Lưu" trên thanh công cụ gửi MỌI chỗ đổi trong MỘT
 * phiên bản (`oDaDoi`). Ô nhập không giữ chữ riêng, nên bị tháo giữa chừng
 * (danh sách đóng ở `mousedown`, trước cả blur) cũng không mất chữ.
 *
 * Enter xong và ở lại chỗ đó; Tab/Shift+Tab sang chỗ kế/trước theo thứ tự đọc;
 * Esc trả chỗ đó về chữ lúc mở ô; rời ô bằng chuột thì chỉ đóng ô.
 */
function ONhapTaiCho({
  o,
  nhap,
  onNhap,
  onXong,
  phai = false,
  className,
  style,
}: {
  o: OTrang;
  /** Chữ chờ lưu của chỗ này (vắng = chưa gõ gì, ô hiện giá trị đang có). */
  nhap: string | undefined;
  onNhap: (giaTri: string | undefined) => void;
  onXong: (huong: Huong) => void;
  /** Chỗ nằm ở nửa phải trang: dòng gợi ý canh theo mép PHẢI ô nhập, không tràn
   *  khỏi tờ. */
  phai?: boolean;
  className?: string;
  style?: CSSProperties;
}) {
  const id = useId();
  // Chữ chờ lưu lúc MỞ ô (có thể chưa có) — Esc trả về đúng nó.
  const [lucMo] = useState(nhap);
  return (
    <div className={cn(className, phai && "flex flex-col items-end")} style={style}>
      <input
        // Mở ô là do chính người dùng bấm/Enter trên chỗ trống đó.
        autoFocus
        type="text"
        value={nhap ?? giaTriHienThi(o)}
        onChange={(e) => onNhap(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            onXong(0);
          } else if (e.key === "Escape") {
            // `preventDefault`: Esc của sân khấu/popover không đóng thêm lớp ngoài.
            e.preventDefault();
            onNhap(lucMo);
            onXong(0);
          } else if (e.key === "Tab") {
            e.preventDefault();
            onXong(e.shiftKey ? -1 : 1);
          }
        }}
        onBlur={() => onXong(null)}
        aria-label={`Giá trị cho ${nhanO(o)}`}
        aria-describedby={`${id}-goi-y`}
        maxLength={500}
        autoComplete="off"
        spellCheck={false}
        lang="vi"
        // `--ring` (brass, 3,20:1): ranh giới ô nhập phải đạt 3:1 (WCAG 1.4.11);
        // `brass-500` chỉ 1,93:1 (DESIGN.md).
        className="focus-brass min-h-7 w-full rounded-[3px] border border-[var(--ring)] bg-white px-1 text-foreground shadow-soft"
      />
      {/* `100cqw` = bề rộng tờ (`@container` của trang): gợi ý không tràn tờ. */}
      <p
        id={`${id}-goi-y`}
        className="m-0 mt-1 w-max max-w-[min(22rem,100cqw)] rounded-md bg-card/95 px-1.5 py-0.5 text-[11px] leading-4 text-muted-foreground shadow-soft"
      >
        Enter xong · Esc huỷ · Tab sang chỗ kế
      </p>
    </div>
  );
}

/**
 * "Chỗ trống chưa định vị (n)": chỗ máy chủ không đo được vị trí trên trang vẫn
 * điền được, bằng CÙNG ô nhập, trong một danh sách nhỏ ở thanh công cụ. Bấm ra
 * ngoài hay Esc (ngoài ô nhập) thì đóng, tiêu điểm về nút mở.
 *
 * Bố cục hẹp: danh sách neo vào THANH CÔNG CỤ (nơi gọi đặt `relative`), không
 * vào nút — nút đứng sau thanh thu phóng, neo vào nó thì danh sách tràn mép
 * phải màn 390px. Bố cục rộng: neo ngay dưới nút.
 */
export function NutChuaDinhVi({
  ds,
  nhap,
  onNhap,
}: {
  ds: OTrang[];
  nhap: Readonly<Record<string, string>>;
  onNhap: DatNhap;
}) {
  const id = useId();
  const [mo, datMo] = useState(false);
  const sua = useSuaTaiCho(ds);
  const khung = useRef<HTMLDivElement | null>(null);
  const nutMo = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (!mo) return;
    const ngoai = (su: MouseEvent) => {
      if (!khung.current?.contains(su.target as Node)) datMo(false);
    };
    const phim = (su: KeyboardEvent) => {
      // Esc của ô nhập đã `preventDefault` (nó chỉ đóng ô). Esc ở đây đóng
      // danh sách, và chặn Esc của sân khấu (nghe ở `window`, sau `document`).
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

  return (
    <div ref={khung} className="min-[68rem]:relative">
      <button
        ref={nutMo}
        type="button"
        aria-expanded={mo}
        aria-controls={`${id}-ds`}
        onClick={() => {
          datMo((v) => !v);
          // Mở lại danh sách là mở lại từ đầu, không bật lại ô nhập còn dở.
          sua.mo(null);
        }}
        className={cn(NUT_PHU, "max-[68rem]:min-h-11")}
      >
        <TextCursorInput className="size-3.5 text-[var(--color-brass-600)]" aria-hidden />
        Chỗ trống chưa định vị ({ds.length})
      </button>
      {mo && (
        <div
          id={`${id}-ds`}
          role="group"
          aria-label="Chỗ trống chưa định vị"
          className="absolute top-full left-3 z-30 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-xl border border-border bg-card p-2 shadow-lg min-[68rem]:left-0"
        >
          <p className="m-0 px-1.5 pb-1.5 text-[12px] leading-5 text-muted-foreground">
            KLAW chưa định vị được những chỗ này trên trang — điền ở đây.
          </p>
          <ul className="m-0 flex max-h-[50dvh] list-none flex-col gap-1 overflow-y-auto p-1">
            {ds.map((o) => {
              const k = khoaO(o);
              const gt = giaTriHienThi(o);
              const choLuu = nhap[k];
              const doi = choLuu !== undefined && choLuu.trim() !== gt;
              return (
                <li key={k}>
                  {sua.dangMo === k ? (
                    <ONhapTaiCho
                      o={o}
                      nhap={choLuu}
                      onNhap={(v) => onNhap(k, v)}
                      onXong={(huong) => sua.xong(k, huong)}
                      className="text-[13.5px]"
                    />
                  ) : (
                    <button
                      ref={sua.refNut(k)}
                      type="button"
                      data-o={k}
                      aria-label={nhanNutDien(o, choLuu)}
                      onClick={() => sua.mo(k)}
                      className="focus-brass flex min-h-10 w-full cursor-pointer flex-col items-start rounded-md px-2 py-1 text-left hover:bg-[var(--color-paper-100)]"
                    >
                      <span className="text-[12.5px] text-foreground">{nhanO(o)}</span>
                      <span className="text-[12px] text-muted-foreground">
                        {doi ? `${choLuu.trim() || "để trống"} · chưa lưu` : gt || "còn trống"}
                      </span>
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
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
  /** Chữ chờ lưu theo `khoaO` (`nhapODien` của trang gọi) — hiện ngay trên chỗ
   *  trống cho tới khi "Lưu" gửi nó. */
  nhap?: Readonly<Record<string, string>>;
  /** Có = sửa tại chỗ: mỗi chỗ trống ĐỊNH VỊ ĐƯỢC của payload `o` thành một
   *  nút phủ đúng hộp của nó trên trang. Vắng = chỉ xem, không phủ gì ("Bản
   *  tải lên" giữ sạch). */
  onNhap?: DatNhap;
  /** Báo chỗ trống của payload vừa hiện (`null` = máy chủ cũ không gửi `o`) —
   *  thanh công cụ dựng "Chỗ trống chưa định vị" từ đó. PHẢI ổn định tham chiếu. */
  onO?: (o: OTrang[] | null) => void;
}

/**
 * Các trang của một khuôn gốc, đúng như máy chủ dựng (LibreOffice → PDF →
 * PNG), xếp chồng như những tờ giấy — mỗi tờ theo khổ CỦA NÓ (Letter vẫn là
 * Letter). Có `onNhap` thì điền được NGAY TRÊN trang.
 *
 * Tải MỘT lần cho mỗi `duongDan`: một lượt dựng giữ suất LibreOffice của CẢ
 * tài khoản (lượt thứ hai cùng lúc là 503 `qua_tai`), còn sân khấu vẽ lại trên
 * mỗi token chat và mỗi pixel kéo. Đổi đường dẫn huỷ lượt cũ và bỏ phản hồi
 * muộn của nó (so `duongDan`, không tin thứ tự về). Ảnh là `data:` URL dựng
 * một lần mỗi payload (`useMemo`) — không object URL nào để thu hồi.
 *
 * Trong lúc phiên bản KẾ đang dựng (vừa "Lưu"), trang cũ đứng yên, mờ,
 * nút chỉ nhận tiêu điểm: chớp thành khung chờ là tháo đúng nút đang giữ tiêu
 * điểm. Nơi gọi đặt `key` theo bản thảo, nên trang cũ luôn là của cùng nguồn.
 */
export function KhungTrangAnh({
  duongDan,
  soTrang,
  thuPhong,
  nhan,
  nhap = {},
  onNhap,
  onO,
}: PropsKhung) {
  const [lanThu, datLanThu] = useState(0);
  const [ket, datKet] = useState<{ duongDan: string; kq: ApiResult<TrangAnh> } | null>(null);
  // Payload hiện gần nhất: khung chờ của lượt kế đứng đúng tỉ lệ, và trang cũ
  // đứng yên trong lúc lượt kế dựng.
  const [daHien, datDaHien] = useState<TrangAnh | null>(null);

  useEffect(() => {
    const dieuKhien = new AbortController();
    void layTrang(duongDan, dieuKhien.signal).then((kq) => {
      if (dieuKhien.signal.aborted) return;
      datKet({ duongDan, kq });
      if (kq.ok) datDaHien(kq.data);
    });
    return () => dieuKhien.abort();
  }, [duongDan, lanThu]);

  const kq = ket !== null && ket.duongDan === duongDan ? ket.kq : null;
  const dangTai = kq === null;
  const data = kq?.ok ? kq.data : dangTai ? daHien : null;
  const laCu = dangTai && data !== null;
  const anh = useMemo(
    () =>
      data === null
        ? null
        : data.trang.map((b64, i) => ({
            src: `data:image/png;base64,${b64}`,
            kho: data.kho[i] ?? KHO_A4,
          })),
    [data],
  );
  const o = useMemo(() => (data === null ? null : oHopLe(data.o, data.kho)), [data]);
  useEffect(() => {
    if (!laCu && data !== null) onO?.(o);
  }, [o, laCu, data, onO]);
  // Thứ tự Tab = thứ tự DOM = từng trang, trong trang theo thứ tự đọc của payload.
  const oTheoTrang = useMemo(
    () => (anh ?? []).map((_, i) => (o ?? []).filter((x) => x.trang === i)),
    [anh, o],
  );
  const dsDoc = useMemo(() => oTheoTrang.flat(), [oTheoTrang]);
  const sua = useSuaTaiCho(dsDoc);

  const loi = kq !== null && !kq.ok ? loiTrang(kq.error, duongDan) : null;
  // Khổ thật (pt → px) nhưng không quá khung, RỒI nhân mức thu phóng: màn hẹp
  // vừa khung ở 100% mà "Phóng to"/"Thu nhỏ" vẫn đổi cỡ thật (vùng cuộn của sân
  // khấu cuộn ngang) — chặn `maxWidth: 100%` sau khi nhân thì phóng to vô hiệu.
  const rong = (w: number) => `calc(min(100%, ${w * PX_MOI_PT}px) * ${thuPhong / 100})`;
  const thuLai = () => {
    datKet(null);
    datLanThu((n) => n + 1);
  };

  return (
    <>
      {/* NGOÀI vùng `aria-busy`: trình đọc màn hình hoãn thông báo trong một cây
          đang bận, nên "Đang dựng trang…" nằm trong đó thì không được đọc. */}
      <p
        role="status"
        className={cn(
          "m-0 mb-4 text-center text-[13px] text-muted-foreground",
          !dangTai && "sr-only",
        )}
      >
        {dangTai ? "Đang dựng trang…" : anh !== null ? `Đã hiện ${anh.length} trang.` : ""}
      </p>
      {/* `items-center-safe`: tờ phóng rộng hơn khung thì canh TRÁI, không tràn
          về bên trái nơi không cuộn tới được. */}
      <div
        role="region"
        aria-label={nhan}
        aria-busy={dangTai}
        className="flex flex-col items-center-safe gap-4"
      >
        {loi !== null && (
          <div
            role="alert"
            className="w-full max-w-[794px] rounded-xl border border-l-2 border-border bg-[var(--color-paper-50)] p-4"
            style={{ borderLeftColor: "var(--color-status-neutral)" }}
          >
            <p className="m-0 text-[14px] leading-6 text-foreground">{loi.cau}</p>
            {loi.thuLai && (
              <button
                type="button"
                onClick={thuLai}
                className={cn(NUT_PHU, "mt-3 max-[68rem]:min-h-11")}
              >
                <RotateCcw className="size-3.5" aria-hidden /> Thử lại
              </button>
            )}
          </div>
        )}
        {dangTai &&
          data === null &&
          Array.from({ length: soTrang ?? daHien?.kho.length ?? 1 }, (_, i) => {
            const [w, h] = daHien?.kho[i] ?? daHien?.kho[0] ?? KHO_A4;
            return (
              <div
                key={i}
                data-khung-cho=""
                aria-hidden
                className="animate-pulse rounded-md border border-border bg-white/70 shadow-soft"
                style={{ width: rong(w), aspectRatio: `${w} / ${h}` }}
              />
            );
          })}
        {anh?.map((a, i) => (
          // `@container`: cỡ chữ ô nhập tính bằng `cqw` (phần trăm bề rộng tờ)
          // — theo đúng tờ đang vẽ ở mọi mức thu phóng và bề rộng. `isolate`:
          // vùng bấm nới rộng (`before:`) của MỌI chỗ nằm DƯỚI hộp thật của mọi
          // chỗ (và trên ảnh `-z-20`) — dòng cách dòng ~8px ở màn 390px, nên
          // vùng nới của chỗ dòng dưới không được đè lên chấm của chỗ dòng trên.
          <div
            key={i}
            className={cn(
              "@container relative isolate",
              sua.dangMo !== null && oTheoTrang[i]?.some((x) => khoaO(x) === sua.dangMo) && "z-10",
              laCu && "opacity-60",
            )}
            style={{ width: rong(a.kho[0]) }}
          >
            <img
              src={a.src}
              alt={`Trang ${i + 1} / ${anh.length}`}
              width={Math.round(a.kho[0] * PX_MOI_PT)}
              height={Math.round(a.kho[1] * PX_MOI_PT)}
              decoding="async"
              className="relative -z-20 block h-auto w-full rounded-md border border-border bg-white shadow-soft"
              style={{ aspectRatio: `${a.kho[0]} / ${a.kho[1]}` }}
            />
            {onNhap !== undefined &&
              (oTheoTrang[i] ?? []).map((x) => {
                const k = khoaO(x);
                const v = viTriO(x.hop!, a.kho);
                const choLuu = nhap[k];
                const doi = choLuu !== undefined && choLuu.trim() !== giaTriHienThi(x);
                return sua.dangMo === k ? (
                  <ONhapTaiCho
                    key={k}
                    o={x}
                    nhap={choLuu}
                    onNhap={(gt) => onNhap(k, gt)}
                    onXong={(huong) => sua.xong(k, huong)}
                    phai={v.trai > 50}
                    className="absolute z-10"
                    style={{
                      // Không tràn mép phải tờ: chỗ sát lề phải lùi vào vừa ô.
                      left: `min(${v.trai}%, calc(100% - max(12ch, ${v.rong}%)))`,
                      top: `${v.tren}%`,
                      width: `max(12ch, ${v.rong}%)`,
                      fontSize: `max(12px, ${v.coChu}cqw)`,
                    }}
                  />
                ) : (
                  <button
                    key={k}
                    ref={sua.refNut(k)}
                    type="button"
                    data-o={k}
                    aria-label={nhanNutDien(x, choLuu)}
                    // Trang cũ đang chờ bản mới: nút giữ tiêu điểm, không mở ô
                    // trên một phiên bản sắp bị thay.
                    aria-disabled={laCu || undefined}
                    onClick={() => {
                      if (!laCu) sua.mo(k);
                    }}
                    className={cn(
                      // `before:`: vùng bấm cao tối thiểu 24px (WCAG 2.5.8) dù
                      // dòng chấm trên ảnh chỉ cao ~12px.
                      "focus-brass absolute flex cursor-text items-center rounded-[2px] transition-colors before:absolute before:inset-x-0 before:top-1/2 before:-z-10 before:h-6 before:min-h-full before:-translate-y-1/2 before:content-[''] hover:bg-brass-500/10 hover:outline hover:outline-1 hover:outline-brass-500",
                      // Chữ chưa lưu che chấm/giá trị cũ trên ảnh, viền đứt: thấy
                      // ngay chỗ nào còn chờ "Lưu".
                      doi
                        ? "bg-white outline-1 outline-[var(--ring)] outline-dashed hover:bg-white"
                        : giaTriHienThi(x) !== "" && "bg-brass-500/15",
                    )}
                    style={{
                      left: `${v.trai}%`,
                      top: `${v.tren}%`,
                      width: `${v.rong}%`,
                      height: `${v.cao}%`,
                      fontSize: `max(10px, ${v.coChu}cqw)`,
                    }}
                  >
                    {doi && (
                      <span aria-hidden className="w-full truncate px-px leading-none">
                        {choLuu.trim()}
                      </span>
                    )}
                  </button>
                );
              })}
          </div>
        ))}
      </div>
    </>
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
        <button
          type="button"
          onClick={onDienBieuMau}
          className={cn(NUT_PHU, "max-[68rem]:min-h-11")}
        >
          <FilePen className="size-3.5 text-[var(--color-brass-600)]" aria-hidden />
          Điền biểu mẫu
        </button>
        <button
          type="button"
          onClick={onDong}
          aria-label="Đóng bản tải lên"
          className="focus-brass inline-grid cursor-pointer place-items-center rounded-md border border-border p-1.5 text-muted-foreground hover:bg-[var(--color-paper-100)] max-[68rem]:size-11"
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
