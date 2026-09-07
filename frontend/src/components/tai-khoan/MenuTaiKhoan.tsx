import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useRef, type RefObject } from "react";
import { CircleUserRound, LifeBuoy, LogOut, Settings2, Sparkles } from "lucide-react";
import { ThuocMucDung } from "@/components/tai-khoan/ThuocMucDung";
import { useTaiKhoan } from "@/contexts/tai-khoan";
import { tenGoi } from "@/lib/goi";
import { dinhDangMoc, mucRangBuoc, soNgayCon } from "@/lib/han-muc";
import { chuCaiDau, tenHienThi } from "@/lib/tai-khoan";
import { cn } from "@/lib/utils";

/**
 * Menu tài khoản của vỏ ứng dụng (spec 2A §7.3).
 *
 * Thân menu tách khỏi popover vì thanh dưới trên màn hẹp dựng ĐÚNG các mục ấy
 * trong một sheet: hai bản sao sẽ lệch nhau ngay lần thêm mục tiếp theo.
 *
 * `role="menu"` chỉ bọc phần danh sách mục, không bọc khối tên và thanh đo —
 * một menu khai rằng mọi con của nó là mục bấm được, và khối tên thì không.
 */
const MUI_GIO_MAC_DINH = "Asia/Ho_Chi_Minh";
const SAP_HET_HAN_NGAY = 7;

const MUC =
  "focus-brass flex min-h-10 w-full cursor-pointer items-center gap-2.5 rounded-lg px-2.5 text-left text-[13px] text-foreground no-underline transition-colors hover:bg-[var(--color-paper-100)]";

/** Thân menu: khối tên, thanh đo mục ràng buộc, hạn gói, rồi các mục điều hướng. */
export function ThanTaiKhoan({ onChon }: { onChon: () => void }) {
  const { user, hanMuc, moNangGoi, signOut } = useTaiKhoan();
  const navigate = useNavigate();
  const hm = hanMuc.hanMuc;
  const plan = hm?.plan ?? "free";
  const muiGio = hm?.mui_gio ?? MUI_GIO_MAC_DINH;
  const ten = tenHienThi(user);
  const muc = mucRangBuoc(hm);
  const conLai = soNgayCon(hm?.het_han_luc ?? null);
  const sapHet = conLai !== null && conLai <= SAP_HET_HAN_NGAY;

  const dangXuat = async () => {
    onChon();
    await signOut();
    void navigate({ to: "/" });
  };

  return (
    <>
      <div className="flex items-center gap-2.5 px-2.5 pb-2">
        <span
          aria-hidden
          className="bg-gradient-ink grid size-9 shrink-0 place-items-center rounded-full text-[13px] font-semibold text-primary-foreground"
        >
          {chuCaiDau(ten)}
        </span>
        <span className="min-w-0">
          <span className="block truncate text-[13px] font-medium text-foreground">{ten}</span>
          <span className="block truncate text-[12px] text-muted-foreground">
            {user?.email ?? ""}
          </span>
        </span>
      </div>
      <p className="m-0 px-2.5 pb-2 text-[12px] text-muted-foreground">Gói {tenGoi(plan)}</p>
      {muc !== null && (
        <div className="px-2.5 pb-3">
          <ThuocMucDung muc={[muc]} muiGio={muiGio} gon />
        </div>
      )}
      {plan === "pro" && conLai !== null && (
        <div className="px-2.5 pb-3">
          <p
            className={cn("m-0 text-[12px]", sapHet ? "text-destructive" : "text-muted-foreground")}
          >
            Còn {conLai} ngày · hết hạn {dinhDangMoc(hm?.het_han_luc ?? null, muiGio)}
          </p>
          {sapHet && (
            <button
              type="button"
              onClick={() => {
                onChon();
                moNangGoi();
              }}
              className="focus-brass mt-1.5 min-h-8 cursor-pointer rounded-md border border-border px-2.5 text-[12px] font-medium text-primary transition-colors hover:bg-[var(--color-paper-100)]"
            >
              Gia hạn
            </button>
          )}
        </div>
      )}

      <div role="menu" aria-label="Tài khoản" className="border-t border-border pt-1">
        {/* `/tai-khoan` và `/tai-khoan/ca-nhan-hoa` do Task 8 dựng; tới lúc đó bộ
            định tuyến chưa khai chúng nên `Link to` chưa kiểm kiểu được. Thẻ `a`
            thật vẫn tới đúng nơi, đổi lại một lượt tải trang — Task 8 đổi sang
            `Link` là xong. */}
        <a href="/tai-khoan" role="menuitem" onClick={onChon} className={MUC}>
          <CircleUserRound className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          Hồ sơ
        </a>
        {plan !== "pro" && (
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              onChon();
              moNangGoi();
            }}
            className={MUC}
          >
            <Sparkles className="size-4 shrink-0 text-[var(--color-brass-600)]" aria-hidden />
            Nâng cấp gói
          </button>
        )}
        <a href="/tai-khoan/ca-nhan-hoa" role="menuitem" onClick={onChon} className={MUC}>
          <Settings2 className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          Cá nhân hoá
        </a>
        <Link to="/huong-dan" role="menuitem" onClick={onChon} className={MUC}>
          <LifeBuoy className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          Trợ giúp
        </Link>
        <button type="button" role="menuitem" onClick={() => void dangXuat()} className={MUC}>
          <LogOut className="size-4 shrink-0 text-muted-foreground" aria-hidden />
          Đăng xuất
        </button>
      </div>
    </>
  );
}

interface Props {
  mo: boolean;
  onDong: () => void;
  nutMo: RefObject<HTMLButtonElement | null>;
}

export function MenuTaiKhoan({ mo, onDong, nutMo }: Props) {
  // Mở = mount, đóng = unmount. Nhờ vậy phần thân bên dưới không phải mang một
  // nhánh `if (!mo)` trong mọi hiệu ứng, và tiêu điểm trả về nút mở nằm gọn
  // trong hàm dọn dẹp — không có đường nào đóng menu mà quên trả tiêu điểm.
  if (!mo) return null;
  return <KhungMenu onDong={onDong} nutMo={nutMo} />;
}

function KhungMenu({ onDong, nutMo }: Omit<Props, "mo">) {
  const khung = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const nut = nutMo.current;
    khung.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();

    const phim = (su: KeyboardEvent) => {
      if (su.key !== "Escape") return;
      su.preventDefault();
      onDong();
    };
    // `mousedown` chứ không `click`: bấm ra ngoài phải đóng NGAY, trước khi
    // phần tử dưới con trỏ kịp nhận tiêu điểm.
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

  return (
    <div
      ref={khung}
      className="rise-in absolute bottom-full left-0 z-50 mb-2 w-64 rounded-xl border border-border bg-card p-2 shadow-soft"
    >
      <ThanTaiKhoan onChon={onDong} />
    </div>
  );
}
