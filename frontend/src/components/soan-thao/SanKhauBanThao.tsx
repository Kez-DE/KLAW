import { useRef, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, Download, FileDown, Minus, Plus, X } from "lucide-react";
import { Toggle } from "@/components/draft/DraftBits";
import { TayKeo } from "@/components/ui/TayKeo";
import { docRongDaLuu, kepRong, luuRong, type Bien } from "@/lib/keo-dan";
import type { BanThao, CauTruc } from "@/lib/klaw";
import { mucTuBanThao } from "@/lib/xuat-tep";
import { cn } from "@/lib/utils";
import { XemTruocA4 } from "./XemTruocA4";

interface Props {
  banThao: BanThao;
  /** Từ `GET /mau/{loai}` — nạp một lần ở nơi mở sân khấu, không tự tải lại
   *  đây (cùng khung sống qua các phiên bản của một bản thảo). */
  cauTruc: CauTruc | null;
  /** `cauTruc` đang tải — cột trái đợi thay vì đoán số mục từ `clauses` rồi
   *  vẽ lại một lần nữa khi khung tới. */
  dangTai: boolean;
  mucDangChon: string | null;
  onChonMuc: (key: string) => void;
  /** Mở drawer sửa mục (Task 25). Tạm thời chọn mục đó làm đích chỉnh sửa —
   *  giống bấm thẳng vào mục trong khung xem trước — cho tới khi drawer thật
   *  thay chỗ. */
  onSuaMuc: (key: string) => void;
  onLui: () => void;
  onDong: () => void;
  onPhimTat: (loai: "rut_gon" | "trang_trong" | "soat_luat") => void;
}

const KHOA_RONG_MUC = "klaw.san-khau.muc";
const RONG_MUC_MAC_DINH = 320;
const BIEN_MUC: Bien = { min: 240, max: 480 };
const BIEN_ZOOM: Bien = { min: 50, max: 150 };
const BUOC_ZOOM = 10;

const NUT_PHU =
  "focus-brass inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-[12.5px] text-primary transition-colors hover:bg-[var(--color-paper-100)] disabled:cursor-not-allowed disabled:opacity-60";

/**
 * Sân khấu bản thảo (spec 2026-09-09 §9.4) — bản thảo chiếm toàn bề rộng
 * `<main>` khi mở, trợ lý lùi ra thành cửa sổ nổi (`CuaSoTroLy`) bên cạnh.
 *
 * Khung mục (cột trái) quyết định THỨ TỰ và CĂN CỨ của từng mục; `clauses` của
 * `banThao` chỉ góp nội dung — `mucTuBanThao` (xuat-tep.ts) đã gộp hai nguồn
 * này, dùng lại nguyên, không tính lại ở đây.
 */
export function SanKhauBanThao({
  banThao,
  cauTruc,
  dangTai,
  mucDangChon,
  onChonMuc,
  onSuaMuc,
  onLui,
  onDong,
  onPhimTat,
}: Props) {
  const muc = mucTuBanThao(banThao, cauTruc);
  const [hienThayDoi, datHienThayDoi] = useState(false);
  const [thuPhong, datThuPhongRaw] = useState(100);
  const datThuPhong = (delta: number) => datThuPhongRaw((z) => kepRong(z + delta, BIEN_ZOOM));
  const [hienCanCu, datHienCanCu] = useState(false);
  const [dangXuat, datDangXuat] = useState<"docx" | "pdf" | null>(null);

  const [rongMuc, datRongMucRaw] = useState(() =>
    kepRong(docRongDaLuu(KHOA_RONG_MUC, RONG_MUC_MAC_DINH), BIEN_MUC),
  );
  const datRongMuc = (px: number) => {
    datRongMucRaw(px);
    luuRong(KHOA_RONG_MUC, px);
  };

  const khungRef = useRef<HTMLDivElement | null>(null);

  const xuatTep = async (dinhDang: "docx" | "pdf") => {
    const sheet = khungRef.current?.querySelector<HTMLElement>("article") ?? null;
    if (sheet === null) {
      toast.error("Chưa tải được khung xem trước. Vui lòng thử lại.");
      return;
    }
    datDangXuat(dinhDang);
    const id = toast.loading(dinhDang === "docx" ? "Đang tạo tệp Word…" : "Đang tạo tệp PDF…");
    try {
      const { xuatWord, xuatPDF } = await import("@/lib/xuat-tep");
      if (dinhDang === "docx") await xuatWord(sheet, banThao.ten);
      else await xuatPDF(sheet, banThao.ten);
      toast.success(dinhDang === "docx" ? "Đã tải tệp .docx." : "Đã tải tệp .pdf.", {
        id,
        description: "Bản thảo cần được pháp chế rà soát trước khi ký kết.",
      });
    } catch {
      // Lỗi ra bằng toast, không bằng console — bản dựng công khai không nhả
      // stack ra console trình duyệt.
      toast.error("Xuất tệp thất bại. Vui lòng thử lại.", { id });
    } finally {
      datDangXuat(null);
    }
  };

  return (
    <div className="grid h-full min-w-0 flex-1 grid-rows-[auto_1fr]">
      <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
        <h2 className="m-0 min-w-0 flex-1 truncate font-display text-base font-semibold text-primary">
          {banThao.ten}
        </h2>
        <span className="font-jetbrains text-[12.5px] text-muted-foreground">
          v{banThao.phien_ban}
        </span>
        {banThao.phien_ban > 1 && (
          <button type="button" onClick={onLui} className={NUT_PHU}>
            <ChevronLeft className="size-3.5" aria-hidden /> Lùi
          </button>
        )}
        {banThao.doi_so_voi_truoc.length > 0 && (
          <button
            type="button"
            aria-pressed={hienThayDoi}
            onClick={() => datHienThayDoi((v) => !v)}
            className={cn(NUT_PHU, hienThayDoi && "bg-[var(--color-paper-100)]")}
          >
            Hiện thay đổi
          </button>
        )}
        <button
          type="button"
          onClick={() => void xuatTep("docx")}
          disabled={dangXuat !== null}
          className={NUT_PHU}
        >
          <FileDown className="size-3.5 text-[var(--color-brass-600)]" aria-hidden />
          {dangXuat === "docx" ? "Đang tạo tệp Word…" : "Tải Word (.docx)"}
        </button>
        <button
          type="button"
          onClick={() => void xuatTep("pdf")}
          disabled={dangXuat !== null}
          className={NUT_PHU}
        >
          <Download className="size-3.5 text-[var(--color-brass-600)]" aria-hidden />
          {dangXuat === "pdf" ? "Đang tạo tệp PDF…" : "Tải PDF"}
        </button>
        <button
          type="button"
          onClick={onDong}
          aria-label="Đóng sân khấu bản thảo"
          className="focus-brass cursor-pointer rounded-md border border-border p-1.5 text-muted-foreground hover:bg-[var(--color-paper-100)]"
        >
          <X className="size-4" aria-hidden />
        </button>
      </header>

      <div className="flex min-h-0" style={{ ["--rong-muc" as string]: `${rongMuc}px` }}>
        <div
          id="san-khau-danh-sach-muc"
          className="w-[var(--rong-muc)] shrink-0 overflow-y-auto border-r border-border p-3"
        >
          {dangTai ? (
            <p className="m-0 text-[13px] text-muted-foreground">Đang tải khung mục…</p>
          ) : (
            <ol className="m-0 flex list-none flex-col gap-2 p-0">
              {muc.map((m) => (
                <li key={m.key} className="rounded-lg border border-border p-2">
                  <div className="flex items-start justify-between gap-2">
                    <p className="m-0 min-w-0 flex-1 text-[13px] font-medium text-foreground">
                      {m.stt}. {m.ten}
                      {m.noiDung === "[…]" && (
                        <span className="ml-2 inline-block rounded-full bg-[var(--color-paper-100)] px-2 py-0.5 text-[11px] font-normal text-muted-foreground">
                          thiếu
                        </span>
                      )}
                    </p>
                    <button
                      type="button"
                      onClick={() => onSuaMuc(m.key)}
                      className="focus-brass shrink-0 cursor-pointer text-[12px] font-medium text-primary hover:underline"
                    >
                      Sửa
                    </button>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>

        <TayKeo
          giaTri={rongMuc}
          bien={BIEN_MUC}
          nhan="Kéo để đổi bề rộng danh sách mục"
          dieuKhienId="san-khau-danh-sach-muc"
          onDoi={datRongMuc}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-wrap items-center gap-3 border-b border-border px-3 py-2">
            <div className="flex items-center gap-1 rounded-lg border border-border p-0.5">
              <button
                type="button"
                aria-label="Thu nhỏ"
                onClick={() => datThuPhong(-BUOC_ZOOM)}
                className="focus-brass cursor-pointer rounded-md p-1.5 hover:bg-[var(--color-paper-100)]"
              >
                <Minus className="size-3.5" aria-hidden />
              </button>
              <span className="font-jetbrains w-10 text-center text-[11px]">{thuPhong}%</span>
              <button
                type="button"
                aria-label="Phóng to"
                onClick={() => datThuPhong(BUOC_ZOOM)}
                className="focus-brass cursor-pointer rounded-md p-1.5 hover:bg-[var(--color-paper-100)]"
              >
                <Plus className="size-3.5" aria-hidden />
              </button>
            </div>
            <label className="flex items-center gap-2 text-[12px]">
              <Toggle checked={hienCanCu} onChange={datHienCanCu} label="Hiển thị căn cứ pháp lý" />
              Hiển thị căn cứ
            </label>
            <div className="ml-auto flex flex-wrap gap-2">
              <button type="button" onClick={() => onPhimTat("rut_gon")} className={NUT_PHU}>
                Rút gọn
              </button>
              <button type="button" onClick={() => onPhimTat("trang_trong")} className={NUT_PHU}>
                Trang trọng hơn
              </button>
              <button type="button" onClick={() => onPhimTat("soat_luat")} className={NUT_PHU}>
                Soát lại theo luật
              </button>
            </div>
          </div>
          <div
            ref={khungRef}
            className="min-h-0 flex-1 overflow-y-auto bg-[var(--color-paper-100)] p-6"
          >
            <XemTruocA4
              tieuDe={cauTruc?.tieu_de ?? banThao.ten}
              kyHieu={null}
              muc={muc}
              thuPhong={thuPhong}
              hienCanCu={hienCanCu}
              mucDangChon={mucDangChon}
              onChonMuc={onChonMuc}
              mucDoi={hienThayDoi ? banThao.doi_so_voi_truoc : []}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
