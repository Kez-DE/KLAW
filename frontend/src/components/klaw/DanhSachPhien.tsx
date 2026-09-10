import { Check, Eye, EyeOff, Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { TrangThaiHoiThoai } from "@/hooks/use-hoi-thoai";
import { danhSachBanThao } from "@/lib/api";
import type { BanThaoTomTat, PhienTomTat } from "@/lib/klaw";
import { thoiGianTuongDoi } from "@/lib/phien";
import { cn } from "@/lib/utils";

/**
 * Danh sách phiên hội thoại "Gần đây" (spec 2A §6). THUẦN thân danh sách: vỏ
 * do `AppShell` quyết định — cột trái từ 80rem, sheet trượt lên dưới đó — nên
 * cùng một danh sách không bị dựng hai lần với hai hành vi lệch nhau.
 *
 * Đổi tên và xoá đều làm TẠI CHỖ (Enter lưu, Esc huỷ; xác nhận xoá là hai nút,
 * không `confirm()` — hộp thoại trình duyệt chặn cả tab và không theo được
 * giao diện).
 */
interface Props {
  hoiThoai: TrangThaiHoiThoai;
  phienDangMo: string | undefined;
  onChon: (id: string) => void;
  /** Chỉ dùng ở trạng thái rỗng: lúc đó đây là lối đi DUY NHẤT trong danh
   *  sách. Nút "Phiên mới" thường trực nằm ở `AppShell`, không nhân đôi ở đây. */
  onPhienMoi: () => void;
  /** Phiên vừa xoá xong — cha quyết định có phải điều hướng đi không. */
  onDaXoa: (id: string) => void;
  /** Bật/tắt công tắc "không ghi nhớ" của MỘT phiên (spec 2026-09-09 §6.6).
   *  Trả `boolean` như `onDoiTen`/`onXoa` — để `MotPhien` báo được thất bại. */
  onDoiGhiNho: (id: string, khongGhiNho: boolean) => Promise<boolean>;
}

const NUT_PHU =
  "focus-brass grid size-8 cursor-pointer place-items-center rounded-md text-muted-foreground transition-colors hover:bg-[var(--color-brass-500)]/10 hover:text-foreground";

function MotPhien({
  phien,
  dangMo,
  onChon,
  onDoiTen,
  onXoa,
  onDoiGhiNho,
}: {
  phien: PhienTomTat;
  dangMo: boolean;
  onChon: () => void;
  onDoiTen: (tieuDe: string) => Promise<boolean>;
  onXoa: () => Promise<boolean>;
  onDoiGhiNho: (id: string, khongGhiNho: boolean) => Promise<boolean>;
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
  const doiGhiNho = async () => {
    datDangGui(true);
    const ok = await onDoiGhiNho(phien.id, !(phien.khong_ghi_nho ?? false));
    datDangGui(false);
    if (ok) datLoi(null);
    else datLoi("Tôi chưa đổi được công tắc ghi nhớ, thử lại nhé.");
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
            disabled={dangGui}
            onClick={() => {
              datCheDo("xem");
              datNhap(phien.tieu_de);
            }}
            aria-label="Huỷ đổi tên"
            className={cn(NUT_PHU, "disabled:opacity-60")}
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
            disabled={dangGui}
            onClick={() => datCheDo("xem")}
            className="focus-brass min-h-8 cursor-pointer rounded-md border border-border px-2.5 font-medium text-primary disabled:opacity-60"
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
        "group rounded-lg border p-2 text-[12px]",
        dangMo
          ? "border-[var(--color-brass-500)]/60 bg-card shadow-soft"
          : "border-transparent hover:bg-card",
      )}
    >
      <div className="flex items-start gap-1">
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
            onClick={() => {
              datNhap(phien.tieu_de);
              datCheDo("sua");
            }}
            aria-label={`Đổi tên phiên ${phien.tieu_de}`}
            className={NUT_PHU}
          >
            <Pencil className="size-3.5" aria-hidden />
          </button>
          <button
            type="button"
            disabled={dangGui}
            onClick={() => void doiGhiNho()}
            aria-pressed={phien.khong_ghi_nho ?? false}
            aria-label={
              (phien.khong_ghi_nho ?? false)
                ? `Ghi nhớ lại phiên ${phien.tieu_de}`
                : `Không ghi nhớ phiên ${phien.tieu_de}`
            }
            title={
              (phien.khong_ghi_nho ?? false)
                ? "Phiên này không được ghi nhớ"
                : "Không ghi nhớ phiên này"
            }
            className={cn(NUT_PHU, "disabled:opacity-60")}
          >
            {(phien.khong_ghi_nho ?? false) ? (
              <EyeOff className="size-3.5" aria-hidden />
            ) : (
              <Eye className="size-3.5" aria-hidden />
            )}
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
      </div>
      {loi !== null && (
        <p role="alert" className="m-0 mt-1 text-destructive">
          {loi}
        </p>
      )}
    </li>
  );
}

export function DanhSachPhien({
  hoiThoai,
  phienDangMo,
  onChon,
  onPhienMoi,
  onDaXoa,
  onDoiGhiNho,
}: Props) {
  const { danhSach, dangTai, loi, taiLai, doiTen, xoa } = hoiThoai;

  if (loi !== null) {
    return (
      <div className="soft-fade rounded-lg border border-dashed border-border p-2.5 text-[12px]">
        <p className="m-0 text-muted-foreground">{loi.message}</p>
        <button
          type="button"
          onClick={taiLai}
          className="focus-brass mt-2 min-h-8 cursor-pointer rounded-md border border-border px-2.5 font-medium text-primary"
        >
          Tải lại
        </button>
      </div>
    );
  }
  if (danhSach === null) {
    return (
      <p className="m-0 text-[12px] text-muted-foreground" aria-live="polite">
        {dangTai ? "Đang tải phiên…" : ""}
      </p>
    );
  }
  if (danhSach.items.length === 0) {
    return (
      <div className="soft-fade text-[12px] text-muted-foreground">
        <p className="m-0">Chưa có phiên nào. Hỏi một câu để bắt đầu.</p>
        <button
          type="button"
          onClick={onPhienMoi}
          className="focus-brass mt-2 inline-flex min-h-8 cursor-pointer items-center gap-1.5 rounded-md border border-border px-2.5 font-medium text-primary"
        >
          <Plus className="size-4" aria-hidden /> Phiên mới
        </button>
      </div>
    );
  }
  return (
    <ul className="soft-fade m-0 list-none space-y-1 p-0">
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
          onDoiGhiNho={onDoiGhiNho}
        />
      ))}
    </ul>
  );
}

function MotBanThaoGanDay({ banThao, onMo }: { banThao: BanThaoTomTat; onMo: () => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={onMo}
        className="focus-brass block w-full cursor-pointer rounded-lg p-2 text-left text-[12px] transition-colors hover:bg-card"
      >
        <span className="block truncate text-[13px] font-medium text-foreground">
          {banThao.ten}
        </span>
        <span className="mt-0.5 block text-muted-foreground">
          Phiên bản {banThao.phien_ban} · {thoiGianTuongDoi(banThao.cap_nhat_luc)}
        </span>
      </button>
    </li>
  );
}

/**
 * Mục "Bản thảo" dưới danh sách phiên trong cột "Gần đây" (Task 21) — gọn,
 * chỉ năm bản mới nhất, KHÔNG sửa/xoá tại chỗ (khác `MotPhien`): đây là lối
 * tắt mở lại, không phải nơi quản lý bản thảo.
 *
 * Tự tải `danhSachBanThao(5)` — không có state dùng chung như `hoiThoai` cho
 * phiên. Lỗi tải PHẢI hiện ra, không bị nuốt lặng lẽ: fire-and-forget nuốt
 * lỗi là một phát hiện đã sửa ở nơi khác trong kế hoạch này, không lặp lại ở
 * đây.
 */
export function DanhSachBanThaoGanDay({ onMo }: { onMo: (banThao: BanThaoTomTat) => void }) {
  const [trangThai, datTrangThai] = useState<
    | { dang: "dang_tai" }
    | { dang: "loi"; message: string }
    | { dang: "xong"; items: BanThaoTomTat[] }
  >({ dang: "dang_tai" });

  useEffect(() => {
    let huy = false;
    void danhSachBanThao(5).then((kq) => {
      if (huy) return;
      datTrangThai(
        kq.ok ? { dang: "xong", items: kq.data.items } : { dang: "loi", message: kq.error.message },
      );
    });
    return () => {
      huy = true;
    };
  }, []);

  if (trangThai.dang === "xong" && trangThai.items.length === 0) return null;

  return (
    <div className="mt-4">
      <p className="m-0 mb-2 px-2 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
        Bản thảo
      </p>
      {trangThai.dang === "dang_tai" && (
        <p className="m-0 px-2 text-[12px] text-muted-foreground" aria-live="polite">
          Đang tải bản thảo…
        </p>
      )}
      {trangThai.dang === "loi" && (
        <p role="alert" className="m-0 px-2 text-[12px] text-destructive">
          {trangThai.message}
        </p>
      )}
      {trangThai.dang === "xong" && (
        <ul className="m-0 list-none space-y-1 p-0">
          {trangThai.items.map((bt) => (
            <MotBanThaoGanDay key={bt.id} banThao={bt} onMo={() => onMo(bt)} />
          ))}
        </ul>
      )}
    </div>
  );
}
