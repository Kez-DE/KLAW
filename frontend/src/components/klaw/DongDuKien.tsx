/**
 * Một dòng dữ kiện rút từ tài liệu, và bảng gom chúng theo trang.
 *
 * Tách khỏi `TaiLieuDuKien.tsx` vì nay có HAI chỗ hiện cùng tập dữ kiện đó:
 * khung đính kèm (sửa được, xoá được) và thẻ kết quả `tai_lieu` (chỉ đọc).
 * Lời hứa phải giống hệt nhau ở cả hai chỗ — mỗi dòng nói rõ nó đến từ đâu,
 * giá trị đã sửa hiện trích của giá trị CŨ kèm ghi chú, OCR yếu thì cảnh báo —
 * và cách duy nhất chắc chắn giống nhau là chỉ có một bản mã dựng nó.
 */
import { Loader2, Trash2, TriangleAlert } from "lucide-react";
import {
  canhBaoDoTin,
  nhanNguon,
  theoTrang,
  trichHienThi,
  tuTaiLieu,
  type DuKien,
} from "@/lib/tai-lieu";

const MAU_NGUON: Record<string, string> = {
  tai_lieu: "var(--color-status-ok, #1a7f5a)",
  tai_lieu_ocr: "var(--color-status-warn, #9a6b00)",
  nguoi_dung_nhap: "var(--color-status-neutral, #5b6470)",
  nguoi_dung_sua: "var(--color-status-neutral, #5b6470)",
};

export function DongDuKien({
  dk,
  onSua,
  onXoa,
  dangSua,
}: {
  dk: DuKien;
  /** Vắng ⇒ chỉ đọc: giá trị hiện thành chữ, không có ô nhập và không có nút xoá. */
  onSua?: ((dk: DuKien, giaTri: string) => void) | undefined;
  onXoa?: ((dk: DuKien) => void) | undefined;
  dangSua?: boolean | undefined;
}) {
  const trich = trichHienThi(dk);
  const canh = canhBaoDoTin(dk);
  const ten = dk.nhan ?? dk.khoa;
  return (
    <li className="rounded-md border border-border bg-background p-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="text-xs text-muted-foreground">{ten}</span>
        <span className="rounded px-1.5 py-0.5 text-[11px]" style={{ color: MAU_NGUON[dk.nguon] }}>
          {nhanNguon(dk.nguon)}
          {dk.do_tin !== null && ` · ${Math.round(dk.do_tin * 100)}%`}
        </span>
      </div>
      {onSua === undefined ? (
        <p className="mt-1 mb-0 font-jetbrains text-sm text-foreground">{dk.gia_tri}</p>
      ) : (
        <div className="mt-1 flex items-center gap-2">
          <input
            defaultValue={dk.gia_tri}
            aria-label={`Giá trị của ${ten}`}
            onBlur={(e) => onSua(dk, e.target.value.trim())}
            className="focus-brass min-h-11 flex-1 rounded border border-border bg-transparent px-2 font-jetbrains text-sm"
          />
          {dangSua && <Loader2 aria-hidden className="size-4 animate-spin" />}
          {onXoa && (
            <button
              type="button"
              aria-label={`Bỏ dữ kiện ${ten}`}
              onClick={() => onXoa(dk)}
              className="focus-brass grid size-11 place-items-center rounded border border-border"
            >
              <Trash2 aria-hidden className="size-4" />
            </button>
          )}
        </div>
      )}
      {trich && (
        <p className="mt-2 border-l-2 border-border pl-2 text-xs text-muted-foreground">
          {trich.laGoc && <em>Trích của giá trị trước khi bạn sửa: </em>}“{trich.chu}”
        </p>
      )}
      {canh && (
        // Biểu tượng + chữ, không chỉ màu: cảnh báo chỉ bằng màu là cảnh báo
        // không tới được người không phân biệt được màu đó.
        <p
          className="mt-1 flex items-start gap-1.5 text-xs"
          style={{ color: "var(--color-status-warn, #9a6b00)" }}
        >
          <TriangleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          <span>{canh}</span>
        </p>
      )}
      {!tuTaiLieu(dk) && (
        <p className="mt-1 text-xs text-muted-foreground">
          Giá trị này không đến từ tài liệu, nên không có trích dẫn đối chiếu.
        </p>
      )}
    </li>
  );
}

/** Dữ kiện gom theo trang, đúng thứ tự tài liệu — xem `theoTrang`. */
export function BangDuKien({
  duKien,
  onSua,
  onXoa,
  dangSua,
}: {
  duKien: DuKien[];
  onSua?: ((dk: DuKien, giaTri: string) => void) | undefined;
  onXoa?: ((dk: DuKien) => void) | undefined;
  /** Id của dữ kiện đang lưu, để hiện vòng quay đúng dòng đó. */
  dangSua?: string | null | undefined;
}) {
  const nhom = theoTrang(duKien);
  if (nhom.length === 0) return null;
  return (
    <ul className="mt-3 space-y-3">
      {nhom.map((n) => (
        <li key={n.trang ?? "khac"}>
          <p className="mb-1 text-xs text-muted-foreground">
            {n.trang === null ? "Không thuộc trang nào" : `Trang ${n.trang}`}
          </p>
          <ul className="space-y-2">
            {n.items.map((dk) => (
              <DongDuKien
                key={dk.id ?? dk.khoa}
                dk={dk}
                onSua={onSua}
                onXoa={onXoa}
                dangSua={dangSua !== null && dangSua !== undefined && dangSua === dk.id}
              />
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}
