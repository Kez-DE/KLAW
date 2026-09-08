import { createFileRoute, Link } from "@tanstack/react-router";
import { BaoLoi } from "@/components/klaw/BaoLoi";
import { LichHoatDong } from "@/components/tai-khoan/LichHoatDong";
import { ThuocMucDung } from "@/components/tai-khoan/ThuocMucDung";
import { TheTaiKhoanKhoa } from "@/components/tai-khoan/TheTaiKhoanKhoa";
import { useTaiKhoan } from "@/contexts/tai-khoan";
import { useTaiMot } from "@/hooks/use-goi-api";
import { goi } from "@/lib/api";
import { dinhDangMoc, laBiKhoa, soNgayCon } from "@/lib/han-muc";
import { tenGoi } from "@/lib/goi";
import { laHoSo } from "@/lib/klaw";
import { chuCaiDau, tenHienThi } from "@/lib/tai-khoan";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/tai-khoan/")({
  component: HoSoPage,
  head: () => ({ meta: [{ title: "Hồ sơ — KLAW" }] }),
});

const MUI_GIO_MAC_DINH = "Asia/Ho_Chi_Minh";
const SAP_HET_HAN_NGAY = 7;
const SO_NGAY_GAN_DAY = 30;
const MS_NGAY = 86_400_000;

/**
 * "2026-09-07T10:00:00Z" → "07/09/2026" theo múi giờ gói (không phải giờ
 * máy). `tao_luc` là một MỐC THỜI GIAN thật (có giờ), khác chuỗi ngày thuần
 * "YYYY-MM-DD" mà `lib/utils.ts#ngayVietNam` xử lý bằng cắt chuỗi — ở đây cần
 * quy đổi múi giờ nên phải qua `Intl.DateTimeFormat`, cùng kỹ thuật
 * `dinhDangMoc` (`han-muc.ts`) nhưng giữ lại năm thay vì cắt bỏ.
 */
function ngayThamGia(iso: string, muiGio: string): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: muiGio,
  }).format(t);
}

function chuoiUTC(t: number): string {
  const d = new Date(t);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}`;
}

function OSo({ so, nhan }: { so: number; nhan: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="font-display m-0 text-2xl font-bold text-primary">
        {so.toLocaleString("vi-VN")}
      </p>
      <p className="m-0 mt-1 text-[12.5px] text-muted-foreground">{nhan}</p>
    </div>
  );
}

const NUT_GIA_HAN =
  "focus-brass mt-2 inline-flex min-h-9 cursor-pointer items-center rounded-lg border border-border px-3 text-[13px] font-medium text-primary transition-colors hover:bg-[var(--color-paper-100)]";

function HoSoPage() {
  const hoSo = useTaiMot("/ho-so", laHoSo);
  const { hanMuc, moNangGoi, user } = useTaiKhoan();

  // Tài khoản bị khoá: `/ho-so` trả 403, và `BaoLoi` gộp 401/403 vào cùng lời
  // khuyên "đăng nhập" — sai với người ĐANG đăng nhập nhưng bị khoá. Thẻ khoá
  // ưu tiên trước cả trạng thái tải/lỗi của `hoSo`.
  if (laBiKhoa(hanMuc.hanMuc)) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <TheTaiKhoanKhoa />
      </div>
    );
  }

  if (hoSo.loi !== null) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <BaoLoi
          loi={hoSo.loi}
          onThuLai={() => hoSo.chay((signal) => goi("/ho-so", laHoSo, { signal }))}
        />
      </div>
    );
  }

  if (hoSo.ketQua === null) {
    return (
      <div className="mx-auto max-w-3xl space-y-4 px-4 py-8">
        <div aria-hidden className="h-28 rounded-xl bg-[var(--color-paper-200)]" />
        <div aria-hidden className="h-16 rounded-xl bg-[var(--color-paper-200)]" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} aria-hidden className="h-20 rounded-xl bg-[var(--color-paper-200)]" />
          ))}
        </div>
        <div aria-hidden className="h-32 rounded-xl bg-[var(--color-paper-200)]" />
      </div>
    );
  }

  const { ketQua } = hoSo;
  const hm = hanMuc.hanMuc;
  const plan = hm?.plan ?? "free";
  const muiGio = hm?.mui_gio ?? MUI_GIO_MAC_DINH;
  const hetHanLuc = hm?.het_han_luc ?? null;
  const conLai = soNgayCon(hetHanLuc);
  const sapHet = conLai !== null && conLai <= SAP_HET_HAN_NGAY;
  const daHetHan = hetHanLuc !== null && Date.parse(hetHanLuc) < Date.now();
  const ten = tenHienThi(user);

  const mocHomNay = (() => {
    const homNay = new Date();
    return Date.UTC(homNay.getFullYear(), homNay.getMonth(), homNay.getDate());
  })();
  const catMoc30Ngay = chuoiUTC(mocHomNay - (SO_NGAY_GAN_DAY - 1) * MS_NGAY);
  const tong30Ngay = ketQua.hoat_dong
    .filter((h) => h.ngay >= catMoc30Ngay)
    .reduce((s, h) => s + h.so_luot, 0);

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4">
        <span
          aria-hidden
          className="bg-gradient-ink grid size-12 shrink-0 place-items-center rounded-full text-[16px] font-semibold text-primary-foreground"
        >
          {chuCaiDau(ten)}
        </span>
        <div className="min-w-0 flex-1">
          <p className="m-0 truncate text-[15px] font-medium text-foreground">{ten}</p>
          <p className="m-0 truncate text-[13px] text-muted-foreground">{user?.email ?? ""}</p>
          <p className="m-0 mt-1 text-[12px] text-muted-foreground">
            Gói {tenGoi(plan)} · Tham gia {ngayThamGia(ketQua.tao_luc, muiGio)}
          </p>
        </div>
      </div>

      {plan === "pro" && hetHanLuc !== null && (
        <div className="mt-4 rounded-xl border border-border bg-card p-4">
          <p className={cn("m-0 text-[13px]", sapHet ? "text-destructive" : "text-foreground")}>
            Còn {conLai} ngày · hết hạn {dinhDangMoc(hetHanLuc, muiGio)}
          </p>
          <button type="button" onClick={moNangGoi} className={NUT_GIA_HAN}>
            Gia hạn
          </button>
        </div>
      )}
      {plan !== "pro" && daHetHan && hetHanLuc !== null && (
        <div className="mt-4 rounded-xl border border-border bg-card p-4">
          <p className="m-0 text-[13px] text-foreground">
            Gói Cá nhân đã hết hạn ngày {dinhDangMoc(hetHanLuc, muiGio)}
          </p>
          <button type="button" onClick={moNangGoi} className={NUT_GIA_HAN}>
            Gia hạn
          </button>
        </div>
      )}

      <div className="mt-4 rounded-xl border border-border bg-card p-4">
        <ThuocMucDung muc={hm?.muc ?? []} muiGio={muiGio} />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <OSo so={ketQua.so_phien} nhan="Phiên" />
        <OSo so={ketQua.tong_hoi_dap} nhan="Lượt hỏi đáp" />
        <OSo so={ketQua.tong_ban_thao} nhan="Bản thảo" />
        <OSo so={tong30Ngay} nhan="30 ngày qua" />
      </div>

      <section className="mt-6">
        <h2 className="font-display m-0 text-[18px] font-bold text-primary">Hoạt động</h2>
        <div className="mt-3">
          <LichHoatDong hoatDong={ketQua.hoat_dong} />
        </div>
      </section>

      {ketQua.phan_loai.length > 0 && (
        <section className="mt-6">
          <h2 className="font-display m-0 text-[18px] font-bold text-primary">Phân loại câu hỏi</h2>
          <table className="mt-3 w-full border-collapse text-[13px]">
            <caption className="sr-only">Phân loại câu hỏi theo lĩnh vực</caption>
            <tbody>
              {ketQua.phan_loai.map((p) => (
                <tr key={p.khoa} className="border-b border-border last:border-0">
                  <td className="py-1.5 text-foreground">{p.nhan}</td>
                  <td className="py-1.5 text-right font-jetbrains text-muted-foreground">{p.so}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <div className="mt-6 flex flex-wrap gap-2">
        {plan !== "pro" && (
          <button
            type="button"
            onClick={moNangGoi}
            className="focus-brass inline-flex min-h-11 cursor-pointer items-center rounded-lg bg-primary px-4 text-[15px] font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Nâng cấp
          </button>
        )}
        <Link
          to="/tai-khoan/ca-nhan-hoa"
          className="focus-brass inline-flex min-h-11 items-center rounded-lg border border-border px-4 text-[15px] font-medium text-primary transition-colors hover:bg-[var(--color-paper-100)]"
        >
          Cá nhân hoá
        </Link>
      </div>
    </div>
  );
}
