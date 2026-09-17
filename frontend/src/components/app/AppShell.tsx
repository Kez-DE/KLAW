import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";
import {
  BookOpenText,
  FileSignature,
  LogIn,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Scale,
  Sparkles,
  SquarePen,
  UserRound,
} from "lucide-react";
import { SheetDuoi } from "@/components/app/SheetDuoi";
import { DanhSachBanThaoGanDay, DanhSachPhien } from "@/components/klaw/DanhSachPhien";
import { ChuongThongBao } from "@/components/tai-khoan/ChuongThongBao";
import { ThanTaiKhoan } from "@/components/tai-khoan/MenuTaiKhoan";
import { TheTaiKhoan } from "@/components/tai-khoan/TheTaiKhoan";
import { useTaiKhoan } from "@/contexts/tai-khoan";
import { useKhungModalDangMo } from "@/hooks/use-khung-modal";
import { useMinWidth } from "@/hooks/use-min-width";
import { datKhongGhiNhoPhien } from "@/lib/api";
import type { BanThaoTomTat } from "@/lib/klaw";
import { dichQuayLaiTu, type DichQuayLai } from "@/lib/quay-lai";
import { cn } from "@/lib/utils";

/**
 * Vỏ ứng dụng sau đăng nhập (spec 2A §7.1–§7.4). Ba bề rộng, một cây DOM:
 *
 * - **≥80rem**: cột trái đầy đủ — logo, "Phiên mới", ba mục điều hướng, danh
 *   sách "Gần đây", thẻ tài khoản ở chân.
 * - **48–80rem**: cột trái thu về dải icon; "Gần đây" chuyển vào sheet mở từ
 *   nút "Phiên" trên thanh trên, vì một dải 64px không chứa nổi danh sách.
 * - **<48rem**: cột trái biến mất, thanh dưới thay chỗ với ba mục điều hướng
 *   cộng "Tài khoản" mở sheet.
 *
 * Đầy đủ/dải icon (`rong`) không còn CHỈ là ngưỡng 80rem: một nút bấm được
 * đổi nó bằng tay và nhớ lựa chọn qua localStorage (`docCotTraiMoRong`) — 80rem
 * chỉ còn là mặc định LẦN ĐẦU. Vì vậy bề rộng cột (`w-16`/`w-[260px]`) và mọi
 * chỗ ẩn/hiện nhãn chữ trong cột đều đọc `rong` (JS), không còn lớp `xl:` nào:
 * hai nguồn sự thật cho cùng một trạng thái (CSS breakpoint lẫn JS override)
 * sẽ lệch nhau đúng lúc người dùng đã bấm nút. Ngưỡng 48rem (`coCotTrai`) thì
 * KHÔNG đổi — nút chỉ chọn giữa dải icon và đầy đủ, không hiện lại cột đã ẩn.
 *
 * "Hướng dẫn" rời khỏi điều hướng chính (nay là "Trợ giúp" trong menu tài
 * khoản), nên `/huong-dan` không làm sáng mục nào — chấp nhận.
 */
const NAV = [
  { to: "/dung-thu", label: "Trợ lý KLAW", icon: Sparkles },
  { to: "/tra-cuu", label: "Tra cứu luật", icon: BookOpenText },
  { to: "/soan-thao", label: "Soạn thảo", icon: FileSignature },
] as const;

/** Từ 80rem (`xl` của Tailwind) cột trái mở hết cỡ và ôm luôn danh sách "Gần đây". */
const NGUONG_COT_DAY_DU = 80;
/** Từ 48rem (`md`) có cột trái; dưới ngưỡng đó thanh dưới thay chỗ. */
const NGUONG_CO_COT_TRAI = 48;

/** Khoá nhớ lựa chọn thu gọn/mở rộng cột trái — MỘT LỰA CHỌN CHO THIẾT BỊ
 *  này, không theo tài khoản: đổi máy thì lại theo mặc định của bề rộng máy
 *  đó. Bọc try/catch như `keo-dan.ts`: chế độ ẩn danh hay site data bị chặn
 *  không được làm hỏng trang, chỉ mất đúng một tiện lợi nhỏ. */
const KHOA_COT_TRAI_MO_RONG = "klaw.cot-trai.mo-rong";

/** `null` = người dùng CHƯA từng bấm nút — ngưỡng bề rộng còn quyết định. */
function docCotTraiMoRong(): boolean | null {
  try {
    const raw = localStorage.getItem(KHOA_COT_TRAI_MO_RONG);
    return raw === null ? null : raw === "1";
  } catch {
    return null; // không đọc được = coi như chưa chọn, ngưỡng bề rộng vẫn quyết định
  }
}

function luuCotTraiMoRong(moRong: boolean): void {
  try {
    localStorage.setItem(KHOA_COT_TRAI_MO_RONG, moRong ? "1" : "0");
  } catch {
    // Không ghi được thì thôi: lựa chọn chỉ sống trong phiên này. Phiền, không hỏng.
  }
}

const NUT_DAC =
  "focus-brass bg-gradient-ink inline-flex min-h-9 cursor-pointer items-center justify-center rounded-lg px-3 text-[13px] font-medium whitespace-nowrap text-primary-foreground no-underline transition-opacity hover:opacity-90";
const NUT_VIEN =
  "focus-brass inline-flex min-h-9 cursor-pointer items-center justify-center rounded-lg border border-border px-3 text-[13px] font-medium whitespace-nowrap text-primary no-underline transition-colors hover:bg-[var(--color-paper-100)]";
const LIEN_KET_PHU =
  "focus-brass rounded text-muted-foreground underline underline-offset-2 hover:text-primary";

function NutKhach({
  next,
  onRoi,
  lopDangKy,
}: {
  next: DichQuayLai;
  onRoi: () => void;
  /** Thanh trên dưới 40rem không đủ chỗ cho cả hai nút; sheet "Tài khoản" ở
   *  thanh dưới vẫn có "Đăng ký miễn phí", nên không lối nào mất đi. */
  lopDangKy?: string;
}) {
  return (
    <>
      <Link to="/dang-nhap" search={{ next }} onClick={onRoi} className={NUT_DAC}>
        Đăng nhập
      </Link>
      <Link to="/dang-ky" search={{ next }} onClick={onRoi} className={cn(NUT_VIEN, lopDangKy)}>
        Đăng ký miễn phí
      </Link>
    </>
  );
}

function LienKetKhach() {
  return (
    <span className="flex flex-wrap gap-x-3 gap-y-1 text-[12px]">
      <Link to="/bang-gia" className={LIEN_KET_PHU}>
        Xem các gói dịch vụ
      </Link>
      <Link to="/huong-dan" className={LIEN_KET_PHU}>
        Trợ giúp
      </Link>
    </span>
  );
}

/** Khối chân cột khi chưa biết người dùng là ai (thiếu cấu hình, hoặc đang kiểm phiên). */
function ChanTrungLap() {
  return (
    <div className="rounded-lg border border-border bg-card p-3 text-[12px] text-muted-foreground">
      KLAW là trợ lý pháp lý, không thay thế ý kiến của luật sư.
      <span className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
        <Link to="/mien-tru" className={LIEN_KET_PHU}>
          Giới hạn
        </Link>
        <Link to="/du-lieu" className={LIEN_KET_PHU}>
          Nguồn dữ liệu
        </Link>
      </span>
    </div>
  );
}

export function AppShell({
  active,
  topRight,
  children,
}: {
  active?: string;
  topRight?: ReactNode;
  children: ReactNode;
}) {
  // Khung đối chiếu ở bố cục một cột khai `aria-modal`. Điều hướng và thanh
  // dưới là anh em của <main>, nên chỉ vỏ này gỡ được chúng khỏi vòng Tab.
  const modalMo = useKhungModalDangMo();
  const rongMacDinh = useMinWidth(NGUONG_COT_DAY_DU);
  // R3: đã chọn (bấm nút) ⇒ lựa chọn đó thắng ở MỌI bề rộng còn đủ chỗ cho cột
  // trái (48rem trở lên); chưa chọn ⇒ ngưỡng 80rem quyết định như trước đây.
  const [rongDaChon, datRongDaChon] = useState<boolean | null>(() => docCotTraiMoRong());
  const rong = rongDaChon ?? rongMacDinh;
  const doiRong = () => {
    const moi = !rong;
    datRongDaChon(moi);
    luuCotTraiMoRong(moi);
  };
  const coCotTrai = useMinWidth(NGUONG_CO_COT_TRAI);
  const { daDangNhap, laKhach, hoiThoai, phienMoi, catThreadTruocKhiRoi } = useTaiKhoan();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const search = useRouterState({ select: (s) => s.location.search as Record<string, unknown> });
  const phienTho = search["phien"];
  const phienTrenUrl =
    pathname === "/dung-thu" && typeof phienTho === "string" ? phienTho : undefined;
  const next = dichQuayLaiTu(pathname);
  const [sheetPhien, datSheetPhien] = useState(false);
  const [sheetTaiKhoan, datSheetTaiKhoan] = useState(false);

  // Cửa sổ rộng ra thì sheet phải ĐÓNG, không chỉ ẩn đi: một `aria-modal` còn
  // trong DOM vẫn khiến `useKhungModalDangMo` gỡ cả cột trái lẫn thanh trên
  // khỏi vòng Tab, và người dùng ngồi trước một vỏ ứng dụng chết mà không thấy
  // hộp thoại nào. Đóng luôn cũng tránh sheet tự bật lại khi thu nhỏ.
  useEffect(() => {
    if (rong) datSheetPhien(false);
  }, [rong]);
  useEffect(() => {
    if (coCotTrai) datSheetTaiKhoan(false);
  }, [coCotTrai]);

  // Chọn hay tạo phiên từ trong sheet thì đóng sheet: người dùng vừa yêu cầu
  // thấy hội thoại, không phải thấy lại danh sách.
  const danhSachPhien = (dong: () => void) => (
    <DanhSachPhien
      hoiThoai={hoiThoai}
      phienDangMo={phienTrenUrl}
      onChon={(id) => {
        dong();
        void navigate({ to: "/dung-thu", search: { phien: id } });
      }}
      onPhienMoi={() => {
        dong();
        phienMoi();
      }}
      onDaXoa={(id) => {
        if (id === phienTrenUrl) phienMoi();
      }}
      onDoiGhiNho={async (id, khongGhiNho) => {
        const kq = await datKhongGhiNhoPhien(id, khongGhiNho);
        if (kq.ok) hoiThoai.taiLai();
        return kq.ok;
      }}
    />
  );

  // Mở một bản thảo đã lưu (Task 21 → Task 24): sân khấu thật ở `/dung-thu`
  // nhận `?ban_thao=` rồi tự `layBanThao` — đây là lối vào bền duy nhất tới
  // việc đã lưu. Mở khung soạn thảo trống theo loại như trước là vứt đúng bản
  // thảo người dùng vừa bấm.
  //
  // Kèm `?phien=` khi bản thảo còn nhớ cuộc trò chuyện đã dựng ra nó: trợ lý
  // đứng cạnh sân khấu phải là ĐÚNG cuộc trò chuyện đó, không phải một khung
  // chat trắng — "rút gọn mục 3" chỉ có nghĩa khi lịch sử còn đây.
  const moBanThao = (banThao: BanThaoTomTat, dong: () => void) => {
    dong();
    void navigate({
      to: "/dung-thu",
      search: {
        ban_thao: banThao.id,
        ...(banThao.hoi_thoai_id !== null ? { phien: banThao.hoi_thoai_id } : {}),
      },
    });
  };
  const banThaoGanDay = (dong: () => void) => (
    <DanhSachBanThaoGanDay onMo={(banThao) => moBanThao(banThao, dong)} />
  );

  return (
    <div className="flex min-h-screen bg-background">
      <aside
        inert={modalMo}
        aria-label="Điều hướng chính"
        className={cn(
          "sticky top-0 z-40 hidden h-screen shrink-0 flex-col border-r border-border bg-[var(--color-paper-50)] py-4 md:flex",
          rong ? "w-[260px] px-3" : "w-16 px-2",
        )}
      >
        <Link
          to="/"
          aria-label="KLAW — về trang chủ"
          className={cn(
            "focus-brass mb-2 flex items-center gap-2.5 rounded-lg",
            rong ? "justify-start px-2" : "justify-center",
          )}
        >
          <span className="bg-gradient-ink flex size-9 shrink-0 items-center justify-center rounded-xl text-primary-foreground shadow-soft">
            <Scale className="size-4.5" aria-hidden />
          </span>
          <span
            className={cn(
              "font-display text-lg font-bold tracking-tight text-primary",
              rong ? "inline" : "hidden",
            )}
          >
            KLAW
          </span>
        </Link>

        {/* R3 (canvas-tai-lieu Phase 2): trước đây bề rộng cột chỉ do ngưỡng
            80rem quyết định, không có cách nào chọn tay. `aria-expanded` +
            nhãn nói ĐÚNG việc nút SẼ làm, không chỉ trạng thái hiện tại. */}
        <button
          type="button"
          onClick={doiRong}
          aria-expanded={rong}
          aria-label={rong ? "Thu gọn điều hướng" : "Mở rộng điều hướng"}
          title={rong ? "Thu gọn điều hướng" : "Mở rộng điều hướng"}
          className={cn(
            "focus-brass mb-3 flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-muted-foreground transition-colors hover:bg-[var(--color-paper-100)] hover:text-primary",
            rong ? "justify-start" : "justify-center",
          )}
        >
          {rong ? (
            <PanelLeftClose className="size-4 shrink-0" aria-hidden />
          ) : (
            <PanelLeftOpen className="size-4 shrink-0" aria-hidden />
          )}
          <span className={cn(rong ? "inline" : "hidden")}>Thu gọn điều hướng</span>
        </button>

        <button
          type="button"
          onClick={phienMoi}
          title="Phiên mới"
          className={cn(
            "focus-brass mb-3 flex cursor-pointer items-center gap-2.5 rounded-lg border border-[var(--color-brass-500)]/50 px-2.5 py-2.5 text-sm font-medium text-[var(--color-brass-600)] transition-colors hover:bg-[var(--color-brass-500)]/10",
            rong ? "justify-start" : "justify-center",
          )}
        >
          <SquarePen className="size-4 shrink-0" aria-hidden />
          <span className={cn(rong ? "inline" : "hidden")}>Phiên mới</span>
        </button>

        <nav className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const Icon = item.icon;
            const dangMo = active === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                aria-label={item.label}
                aria-current={dangMo ? "page" : undefined}
                title={item.label}
                className={cn(
                  "focus-brass flex items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-sm transition-colors",
                  rong ? "justify-start" : "justify-center",
                  dangMo
                    ? "bg-[var(--color-paper-200)] font-medium text-primary"
                    : "text-muted-foreground hover:bg-[var(--color-paper-100)] hover:text-primary",
                )}
              >
                <Icon className="size-4 shrink-0" aria-hidden />
                <span className={cn(rong ? "inline" : "hidden")}>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {daDangNhap && rong && (
          <div className="mt-5 flex min-h-0 flex-1 flex-col">
            <p className="m-0 mb-2 px-2 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
              Gần đây
            </p>
            <div className="min-h-0 flex-1 overflow-y-auto pr-0.5">
              {danhSachPhien(() => undefined)}
              {banThaoGanDay(() => undefined)}
            </div>
          </div>
        )}

        <div className="mt-auto pt-3">
          {daDangNhap ? (
            // `rong` (≥80rem): hàng ngang, đủ chỗ. `!rong` (48–80rem, dải icon
            // 64px): xếp dọc — một hàng ngang cần ~88px, rộng hơn cả dải.
            <div className={rong ? "flex items-center gap-2" : "flex flex-col items-center gap-2"}>
              <ChuongThongBao />
              <TheTaiKhoan gon={!rong} />
            </div>
          ) : laKhach ? (
            rong ? (
              <div className="rounded-xl border border-border bg-card p-3 shadow-soft">
                <p className="m-0 text-[12px] leading-5 text-muted-foreground">
                  Đăng nhập để lưu phiên, hỏi tiếp nhiều ngày và soạn văn bản.
                </p>
                <Link
                  to="/dang-nhap"
                  search={{ next }}
                  onClick={catThreadTruocKhiRoi}
                  className={cn(NUT_DAC, "mt-2.5 w-full")}
                >
                  Đăng nhập
                </Link>
                <span className="mt-2 block">
                  <LienKetKhach />
                </span>
              </div>
            ) : (
              <Link
                to="/dang-nhap"
                search={{ next }}
                onClick={catThreadTruocKhiRoi}
                aria-label="Đăng nhập"
                title="Đăng nhập"
                className="focus-brass grid size-10 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-[var(--color-paper-100)] hover:text-primary"
              >
                <LogIn className="size-4" aria-hidden />
              </Link>
            )
          ) : (
            <div className={cn(rong ? "block" : "hidden")}>
              <ChanTrungLap />
            </div>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col pb-14 md:pb-0">
        <header
          inert={modalMo}
          className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-background/90 px-4 py-2.5 backdrop-blur"
        >
          <Link
            to="/"
            aria-label="KLAW — về trang chủ"
            className="focus-brass flex items-center gap-2 rounded-lg md:hidden"
          >
            <span className="bg-gradient-ink flex size-8 items-center justify-center rounded-lg text-primary-foreground">
              <Scale className="size-4" aria-hidden />
            </span>
            <span className="font-display font-bold text-primary">KLAW</span>
          </Link>
          <div className="ml-auto flex items-center gap-2">
            {/* `coCotTrai`: dưới 48rem thanh dưới đã có "Tài khoản", và sheet
                đó chứa luôn "Gần đây" — không có nút này thì hai sheet cùng mở
                được một lúc, mỗi cái khai `aria-modal`. */}
            {daDangNhap && coCotTrai && !rong && pathname === "/dung-thu" && (
              <button
                type="button"
                onClick={() => datSheetPhien(true)}
                aria-expanded={sheetPhien}
                aria-controls="sheet-phien"
                className="focus-brass inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-border px-3 text-[13px] font-medium text-primary transition-colors hover:bg-[var(--color-paper-100)]"
              >
                <MessageSquare className="size-4" aria-hidden />
                Phiên
              </button>
            )}
            {topRight === undefined ? (
              laKhach && (
                <NutKhach
                  next={next}
                  onRoi={catThreadTruocKhiRoi}
                  lopDangKy="hidden sm:inline-flex"
                />
              )
            ) : (
              <>{topRight}</>
            )}
          </div>
        </header>
        <main id="noi-dung-chinh" className="flex min-w-0 flex-1 flex-col">
          {children}
        </main>
      </div>

      <nav
        inert={modalMo}
        aria-label="Điều hướng chính (thu gọn)"
        className="fixed inset-x-0 bottom-0 z-40 flex items-stretch border-t border-border bg-background/95 backdrop-blur md:hidden"
      >
        {NAV.map((item) => {
          const Icon = item.icon;
          const dangMo = active === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              aria-label={item.label}
              aria-current={dangMo ? "page" : undefined}
              className={cn(
                "focus-brass flex min-h-14 flex-1 flex-col items-center justify-center gap-1 px-1 text-[10px]",
                dangMo ? "font-medium text-primary" : "text-muted-foreground",
              )}
            >
              <Icon className="size-[18px]" aria-hidden />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
        <button
          type="button"
          onClick={() => datSheetTaiKhoan(true)}
          aria-expanded={sheetTaiKhoan}
          aria-controls="sheet-tai-khoan"
          className="focus-brass flex min-h-14 flex-1 cursor-pointer flex-col items-center justify-center gap-1 px-1 text-[10px] text-muted-foreground"
        >
          <UserRound className="size-[18px]" aria-hidden />
          <span className="truncate">Tài khoản</span>
        </button>
      </nav>

      {sheetPhien && !rong && (
        <SheetDuoi id="sheet-phien" nhan="Gần đây" onDong={() => datSheetPhien(false)}>
          {danhSachPhien(() => datSheetPhien(false))}
          {banThaoGanDay(() => datSheetPhien(false))}
        </SheetDuoi>
      )}

      {sheetTaiKhoan && !coCotTrai && (
        <SheetDuoi id="sheet-tai-khoan" nhan="Tài khoản" onDong={() => datSheetTaiKhoan(false)}>
          {daDangNhap ? (
            <>
              <div className="mb-2 flex justify-start">
                <ChuongThongBao viTri="sheet" />
              </div>
              <ThanTaiKhoan onChon={() => datSheetTaiKhoan(false)} />
              <p className="m-0 mt-4 mb-2 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                Gần đây
              </p>
              {danhSachPhien(() => datSheetTaiKhoan(false))}
              {banThaoGanDay(() => datSheetTaiKhoan(false))}
            </>
          ) : laKhach ? (
            <div>
              <p className="m-0 text-[13px] leading-6 text-muted-foreground">
                Đăng nhập để lưu phiên, hỏi tiếp nhiều ngày và soạn văn bản.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <NutKhach next={next} onRoi={catThreadTruocKhiRoi} />
              </div>
              <span className="mt-3 block">
                <LienKetKhach />
              </span>
            </div>
          ) : (
            <ChanTrungLap />
          )}
        </SheetDuoi>
      )}
    </div>
  );
}
