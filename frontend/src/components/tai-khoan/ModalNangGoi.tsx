import { useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { X } from "lucide-react";
import { useTaiKhoan } from "@/contexts/tai-khoan";
import { useGoiApi } from "@/hooks/use-goi-api";
import { goi } from "@/lib/api";
import { GOI_CARD } from "@/lib/goi";
import { soNgayCon } from "@/lib/han-muc";
import { laYeuCauNangGoi, laYeuCauNangGoiHoacNull, type YeuCauNangGoi } from "@/lib/klaw";

const NHAN_TIEU_DIEM =
  'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])';

const NUT_DAC =
  "focus-brass inline-flex h-11 w-full cursor-pointer items-center justify-center rounded-lg bg-primary px-4 text-[14px] font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60";
const NUT_KHOA =
  "inline-flex h-11 w-full cursor-default items-center justify-center rounded-lg border border-border px-4 text-[14px] font-medium text-muted-foreground";

function CardGoi({
  card,
  nut,
  ghiChu,
}: {
  card: (typeof GOI_CARD)["free"];
  nut: ReactNode;
  ghiChu?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <p className="m-0 text-[13px] font-medium text-brass-600">{card.nhan}</p>
      <h3 className="font-display mt-1 text-2xl text-primary">{card.tieuDe}</h3>
      <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">{card.moTa}</p>
      <p className="font-display mt-4 text-[26px] text-primary">{card.gia}</p>
      <div className="mt-4">{nut}</div>
      {ghiChu !== undefined && <p className="mt-2 text-[12px] text-muted-foreground">{ghiChu}</p>}
      <p className="mt-5 text-[13px] font-medium text-foreground">{card.tieuDeDanhSach}</p>
      <ul className="m-0 mt-2 list-none space-y-2 p-0">
        {card.danhSach.map((d) => {
          const Icon = d.icon;
          return (
            <li key={d.chu} className="flex items-start gap-2 text-[13px] text-foreground/80">
              <Icon className="mt-0.5 size-4 shrink-0 text-brass-600" aria-hidden />
              <span>{d.chu}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * Nâng cấp gói — hai card cạnh nhau (spec 2A §7.5). Mở từ `MenuTaiKhoan`, chân
 * sidebar, thẻ 429, trang Hồ sơ, đều qua `moNangGoi()` của `TaiKhoanProvider`.
 *
 * Mở modal thì gọi `GET /nang-goi/yeu-cau` để biết đã có yêu cầu đang chờ duyệt
 * chưa — thiếu bước này thì nút "Yêu cầu nâng lên Cá nhân" luôn hiện được dù
 * người dùng vừa gửi xong, và bấm lại sẽ ăn 409. Gửi yêu cầu cũng đi qua cùng
 * `useGoiApi`: 409 (đã có yêu cầu chờ) tự tải lại GET thay vì hiện lỗi, vì đó
 * không phải một lỗi mà là trạng thái mới nhất của chính yêu cầu.
 */
export function ModalNangGoi() {
  const { nangGoiMo, dongNangGoi, hanMuc, laKhach } = useTaiKhoan();
  const yeuCauApi = useGoiApi<YeuCauNangGoi | null>();
  const { chay } = yeuCauApi;
  const hopThoai = useRef<HTMLDivElement | null>(null);
  const nutDong = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!nangGoiMo) return;
    void chay((signal) => goi("/nang-goi/yeu-cau", laYeuCauNangGoiHoacNull, { signal }));
  }, [nangGoiMo, chay]);

  useEffect(() => {
    if (!nangGoiMo) return;
    const truoc = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    nutDong.current?.focus();
    return () => {
      // `useKhungModalDangMo` giữ `inert` trên chrome còn lại thêm một khung hình
      // sau khi dialog gỡ khỏi DOM (cùng lý do `SheetDuoi.tsx`) — focus() đồng bộ
      // ở đây rơi vào lúc đích vẫn còn `inert` nên lặng lẽ không làm gì.
      requestAnimationFrame(() => truoc?.focus());
    };
  }, [nangGoiMo]);

  useEffect(() => {
    if (!nangGoiMo) return;
    const nghe = (su: globalThis.KeyboardEvent) => {
      if (su.key === "Escape") dongNangGoi();
    };
    window.addEventListener("keydown", nghe);
    return () => window.removeEventListener("keydown", nghe);
  }, [nangGoiMo, dongNangGoi]);

  if (!nangGoiMo) return null;

  const guiYeuCau = () => {
    void chay(async (signal) => {
      const ketQuaGui = await goi("/nang-goi/yeu-cau", laYeuCauNangGoi, {
        method: "POST",
        body: { goi_muon: "pro" },
        signal,
      });
      // 409 = đã có một yêu cầu đang chờ duyệt — không phải lỗi để hiện cho
      // người dùng, mà là dấu hiệu tải lại GET để thẻ chuyển sang "Đang chờ
      // duyệt" đúng như trạng thái thật hiện có.
      if (ketQuaGui.ok || ketQuaGui.error.status !== 409) return ketQuaGui;
      return goi("/nang-goi/yeu-cau", laYeuCauNangGoiHoacNull, { signal });
    });
  };

  const bayTab = (su: KeyboardEvent<HTMLDivElement>) => {
    if (su.key !== "Tab") return;
    const moc = Array.from(hopThoai.current?.querySelectorAll<HTMLElement>(NHAN_TIEU_DIEM) ?? []);
    const dau = moc[0];
    const cuoi = moc[moc.length - 1];
    if (dau === undefined || cuoi === undefined) return;
    const dangO = document.activeElement;
    const oBienLui = dangO === dau || dangO === hopThoai.current;
    if (su.shiftKey ? oBienLui : dangO === cuoi) {
      su.preventDefault();
      (su.shiftKey ? cuoi : dau).focus();
    }
  };

  const yeuCau = yeuCauApi.ketQua;
  const plan = hanMuc.hanMuc?.plan ?? "free";
  const ngayCon = soNgayCon(hanMuc.hanMuc?.het_han_luc ?? null);
  const dangCho = yeuCau?.trang_thai === "cho_duyet";

  let nutCaNhan: ReactNode;
  if (laKhach) {
    nutCaNhan = (
      <Link to="/dang-ky" className={NUT_DAC}>
        Đăng ký miễn phí để nâng gói
      </Link>
    );
  } else if (plan === "free") {
    nutCaNhan = dangCho ? (
      <button type="button" disabled className={NUT_KHOA}>
        Đang chờ duyệt
      </button>
    ) : (
      <button type="button" onClick={guiYeuCau} disabled={yeuCauApi.dangChay} className={NUT_DAC}>
        Yêu cầu nâng lên Cá nhân
      </button>
    );
  } else if (plan === "pro" && ngayCon !== null && ngayCon > 7) {
    nutCaNhan = (
      <button type="button" disabled className={NUT_KHOA}>
        Gói hiện tại · còn {ngayCon} ngày
      </button>
    );
  } else if (plan === "pro") {
    nutCaNhan = dangCho ? (
      <button type="button" disabled className={NUT_KHOA}>
        Đang chờ duyệt
      </button>
    ) : (
      <button type="button" onClick={guiYeuCau} disabled={yeuCauApi.dangChay} className={NUT_DAC}>
        Gia hạn 30 ngày
      </button>
    );
  } else {
    // Gói lạ, ngoài free/pro — hợp đồng backend không hứa giá trị này; không
    // đoán một hành động, để card Cá nhân không hiện nút thay vì hiện sai.
    nutCaNhan = null;
  }

  const nutMienPhi =
    plan === "free" ? (
      <button type="button" disabled className={NUT_KHOA}>
        Gói hiện tại của bạn
      </button>
    ) : null;

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-[var(--color-ink-950)]/45 p-4"
      onClick={dongNangGoi}
    >
      <div
        ref={hopThoai}
        role="dialog"
        aria-modal="true"
        aria-labelledby="nang-goi-tieu-de"
        tabIndex={-1}
        onClick={(su) => su.stopPropagation()}
        onKeyDown={bayTab}
        className="rise-in relative w-full max-w-3xl rounded-2xl border border-border bg-background p-6 focus:outline-none sm:p-8"
      >
        <button
          ref={nutDong}
          type="button"
          onClick={dongNangGoi}
          aria-label="Đóng"
          className="focus-brass absolute top-4 right-4 grid size-9 cursor-pointer place-items-center rounded-md text-muted-foreground hover:text-foreground"
        >
          <X className="size-4" aria-hidden />
        </button>
        <h2 id="nang-goi-tieu-de" className="font-display pr-10 text-2xl text-primary">
          Nâng cấp gói
        </h2>
        {yeuCauApi.loi !== null && (
          <p role="alert" className="mt-3 text-[13px] text-destructive">
            {yeuCauApi.loi.message}
          </p>
        )}
        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <CardGoi card={GOI_CARD.free} nut={nutMienPhi} />
          <div>
            <CardGoi
              card={GOI_CARD.pro}
              nut={nutCaNhan}
              ghiChu="Chưa có thanh toán trực tuyến. Tôi sẽ báo qua email khi gói được mở."
            />
            {yeuCau?.trang_thai === "tu_choi" && yeuCau.ly_do !== null && (
              <p role="status" className="mt-2 mb-0 text-[13px] leading-5 text-muted-foreground">
                Yêu cầu trước chưa được duyệt: {yeuCau.ly_do}. Bạn gửi lại được ngay.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
