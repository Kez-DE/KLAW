/**
 * Tải tài liệu lên và xem dữ kiện rút được (spec 2026-09-15).
 *
 * Lời hứa component này phải giữ: **mỗi dòng nói rõ nó đến từ đâu.** Chữ đọc
 * thẳng từ tệp, chữ máy đoán từ ảnh, và chữ người dùng tự gõ là ba hạng bằng
 * chứng khác nhau. Người dùng sắp đưa những con số này vào một văn bản pháp lý,
 * nên gộp ba hạng thành một bảng phẳng là để giao diện hứa nhiều hơn thứ nó giữ
 * được — cùng lỗi mà `KhungDoiChieu` tồn tại để không mắc với trích dẫn điều luật.
 */
import { useCallback, useRef, useState } from "react";
import { FileText, Loader2, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import { BaoLoi } from "@/components/klaw/BaoLoi";
import {
  DINH_DANG_CHAP_NHAN,
  canhBaoDoTin,
  loiTruocKhiGui,
  nhanNguon,
  seDungOcr,
  theoTrang,
  trichHienThi,
  tuTaiLieu,
  type DuKien,
  type TaiLieu,
} from "@/lib/tai-lieu";
import { sangSoanThao, suaDuKien, taiLen, xoaDuKien } from "@/lib/tai-lieu-api";
import { cn } from "@/lib/utils";
import type { ApiError } from "@/lib/klaw";

interface Props {
  /** `null` khi chưa đăng nhập hoặc chưa có cuộc trò chuyện — nút bị vô hiệu. */
  hoiThoaiId: string | null;
  /** Loại văn bản đang soạn, theo mã backend. `null` thì chưa biết rút trường gì. */
  loai: string | null;
  /** Gọi sau khi dữ kiện đã được đưa sang soạn thảo. */
  onDaDungDeSoan?: () => void;
}

const MAU_NGUON: Record<string, string> = {
  tai_lieu: "var(--color-status-ok, #1a7f5a)",
  tai_lieu_ocr: "var(--color-status-warn, #9a6b00)",
  nguoi_dung_nhap: "var(--color-status-neutral, #5b6470)",
  nguoi_dung_sua: "var(--color-status-neutral, #5b6470)",
};

export function TaiLieuDuKien({ hoiThoaiId, loai, onDaDungDeSoan }: Props) {
  const oTep = useRef<HTMLInputElement | null>(null);
  const [tep, datTep] = useState<TaiLieu | null>(null);
  const [dangKeo, datDangKeo] = useState(false);
  const [dangSua, datDangSua] = useState<string | null>(null);
  const [dangDung, datDangDung] = useState(false);
  // Gọi tay chứ không qua `useGoiApi`: hook đó đẩy kết quả vào state của chính
  // nó, còn ở đây phải phản ứng NGAY với kết quả (đóng toast, đếm dữ kiện).
  // Cùng khuôn `DanhSachPhien.tsx`.
  const [dangTai, datDangTai] = useState(false);
  const [loiTai, datLoiTai] = useState<ApiError | null>(null);

  const san = hoiThoaiId !== null && loai !== null;

  const gui = useCallback(
    async (f: File) => {
      if (!san) {
        toast.error("Cần một cuộc trò chuyện đã đăng nhập để đọc tài liệu.");
        return;
      }
      const loi = loiTruocKhiGui(f.name, f.size);
      if (loi) {
        toast.error(loi);
        return;
      }
      // Ảnh phải qua nhận dạng chữ, chậm hơn hẳn — nói trước thay vì để người
      // dùng nhìn một cái quay vòng không biết nó đang làm gì.
      const id = toast.loading(
        seDungOcr(f.name) ? "Đang nhận dạng chữ trong ảnh…" : "Đang đọc tài liệu…",
      );
      datDangTai(true);
      datLoiTai(null);
      const kq = await taiLen(f, hoiThoaiId, loai);
      datDangTai(false);
      if (!kq.ok) {
        datLoiTai(kq.error);
        toast.error(kq.error.message, { id });
        return;
      }
      datTep(kq.data);
      const n = kq.data.du_kien.length;
      toast.success(
        n > 0 ? `Đọc xong, rút được ${n} dữ kiện.` : "Đọc xong, không rút được dữ kiện nào.",
        { id },
      );
    },
    [san, hoiThoaiId, loai],
  );

  const sua = async (dk: DuKien, giaTri: string) => {
    if (!dk.id || giaTri === dk.gia_tri) return;
    datDangSua(dk.id);
    const kq = await suaDuKien(dk.id, giaTri);
    datDangSua(null);
    if (!kq.ok) {
      toast.error(kq.error.message);
      return;
    }
    datTep((t) =>
      t ? { ...t, du_kien: t.du_kien.map((x) => (x.id === dk.id ? kq.data : x)) } : t,
    );
  };

  const xoa = async (dk: DuKien) => {
    if (!dk.id) return;
    const kq = await xoaDuKien(dk.id);
    if (!kq.ok) {
      toast.error(kq.error.message);
      return;
    }
    datTep((t) => (t ? { ...t, du_kien: t.du_kien.filter((x) => x.id !== dk.id) } : t));
  };

  const dungDeSoan = async () => {
    if (!san) return;
    datDangDung(true);
    const kq = await sangSoanThao(hoiThoaiId, loai, true);
    datDangDung(false);
    if (!kq.ok) {
      toast.error(kq.error.message);
      return;
    }
    const thieu = kq.data.con_thieu.length;
    toast.success(
      thieu === 0
        ? "Đã đưa dữ kiện sang soạn thảo. Không còn trường bắt buộc nào trống."
        : `Đã đưa dữ kiện sang soạn thảo. Còn ${thieu} trường bắt buộc cần bạn điền.`,
    );
    onDaDungDeSoan?.();
  };

  const nhom = theoTrang(tep?.du_kien ?? []);

  return (
    <section
      aria-label="Tài liệu và dữ kiện"
      className="rounded-lg border border-border bg-[var(--color-paper-50)] p-4"
    >
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <FileText aria-hidden className="size-4" />
        Đọc dữ kiện từ tài liệu
      </h2>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          datDangKeo(true);
        }}
        onDragLeave={() => datDangKeo(false)}
        onDrop={(e) => {
          e.preventDefault();
          datDangKeo(false);
          const f = e.dataTransfer.files[0];
          if (f) void gui(f);
        }}
        className={cn(
          "rounded-md border border-dashed p-4 text-center text-sm transition-colors",
          dangKeo ? "border-foreground bg-background" : "border-border",
        )}
      >
        <input
          ref={oTep}
          type="file"
          accept={DINH_DANG_CHAP_NHAN}
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void gui(f);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          disabled={!san || dangTai}
          onClick={() => oTep.current?.click()}
          className="focus-brass inline-flex min-h-11 items-center gap-2 rounded-md border border-border px-4 disabled:opacity-50"
        >
          {dangTai ? (
            <Loader2 aria-hidden className="size-4 animate-spin" />
          ) : (
            <Upload aria-hidden className="size-4" />
          )}
          {dangTai ? "Đang đọc…" : "Chọn tệp"}
        </button>
        <p className="mt-2 text-xs text-muted-foreground">
          Kéo thả hoặc chọn tệp PDF, DOCX, hoặc ảnh chụp giấy tờ. Tối đa 20 MB. Tệp gốc không được
          lưu lại.
        </p>
        {!san && (
          <p className="mt-2 text-xs text-muted-foreground">
            Cần một cuộc trò chuyện đã đăng nhập và một loại văn bản đang soạn.
          </p>
        )}
      </div>

      {loiTai && (
        <div className="mt-3">
          <BaoLoi loi={loiTai} />
        </div>
      )}

      {tep?.co_ocr && (
        <p
          role="status"
          className="mt-3 border-l-4 px-3 py-2 text-xs"
          style={{ borderLeftColor: "var(--color-status-warn, #9a6b00)" }}
        >
          Tài liệu này được đọc bằng nhận dạng chữ từ ảnh. Chữ máy đọc ra không phải chữ gốc của tài
          liệu — hãy đối chiếu trước khi dùng.
        </p>
      )}

      {tep && tep.du_kien.length === 0 && (
        <p className="mt-3 text-sm text-muted-foreground">
          Không rút được dữ kiện nào từ tài liệu này. Có thể tài liệu không chứa các thông tin mà
          loại văn bản đang soạn cần.
        </p>
      )}

      {nhom.length > 0 && (
        <>
          <ul className="mt-3 space-y-3">
            {nhom.map((n) => (
              <li key={n.trang ?? "khac"}>
                <p className="mb-1 text-xs text-muted-foreground">
                  {n.trang === null ? "Không thuộc trang nào" : `Trang ${n.trang}`}
                </p>
                <ul className="space-y-2">
                  {n.items.map((dk) => {
                    const trich = trichHienThi(dk);
                    const canh = canhBaoDoTin(dk);
                    return (
                      <li
                        key={dk.id ?? dk.khoa}
                        className="rounded-md border border-border bg-background p-3"
                      >
                        <div className="flex flex-wrap items-baseline gap-2">
                          <span className="text-xs text-muted-foreground">
                            {dk.nhan ?? dk.khoa}
                          </span>
                          <span
                            className="rounded px-1.5 py-0.5 text-[11px]"
                            style={{ color: MAU_NGUON[dk.nguon] }}
                          >
                            {nhanNguon(dk.nguon)}
                            {dk.do_tin !== null && ` · ${Math.round(dk.do_tin * 100)}%`}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center gap-2">
                          <input
                            defaultValue={dk.gia_tri}
                            aria-label={`Giá trị của ${dk.nhan ?? dk.khoa}`}
                            onBlur={(e) => void sua(dk, e.target.value.trim())}
                            className="focus-brass min-h-11 flex-1 rounded border border-border bg-transparent px-2 font-jetbrains text-sm"
                          />
                          {dangSua === dk.id && (
                            <Loader2 aria-hidden className="size-4 animate-spin" />
                          )}
                          <button
                            type="button"
                            aria-label={`Bỏ dữ kiện ${dk.nhan ?? dk.khoa}`}
                            onClick={() => void xoa(dk)}
                            className="focus-brass grid size-11 place-items-center rounded border border-border"
                          >
                            <Trash2 aria-hidden className="size-4" />
                          </button>
                        </div>
                        {trich && (
                          <p className="mt-2 border-l-2 border-border pl-2 text-xs text-muted-foreground">
                            {trich.laGoc && <em>Trích của giá trị trước khi bạn sửa: </em>}“
                            {trich.chu}”
                          </p>
                        )}
                        {canh && (
                          <p
                            className="mt-1 text-xs"
                            style={{ color: "var(--color-status-warn, #9a6b00)" }}
                          >
                            {canh}
                          </p>
                        )}
                        {!tuTaiLieu(dk) && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            Giá trị này không đến từ tài liệu, nên không có trích dẫn đối chiếu.
                          </p>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ul>

          <button
            type="button"
            disabled={dangDung}
            onClick={() => void dungDeSoan()}
            className="focus-brass mt-3 inline-flex min-h-11 items-center gap-2 rounded-md border border-border px-4 disabled:opacity-50"
          >
            {dangDung && <Loader2 aria-hidden className="size-4 animate-spin" />}
            Dùng dữ kiện này để soạn thảo
          </button>
        </>
      )}
    </section>
  );
}
