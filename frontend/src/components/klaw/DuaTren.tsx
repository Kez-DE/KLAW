import { useState } from "react";
import { Pencil } from "lucide-react";
import type { HoSoDaDung } from "@/lib/klaw";

/**
 * "Dựa trên: vai của bạn: người lao động (tôi đoán) · loại hợp đồng: không xác định thời hạn"
 * — dữ kiện về người hỏi mà lượt này đã dùng (spec 2026-09-09 §6.6). Giả định của máy in
 * nghiêng kèm "tôi đoán" để người đọc biết đâu là điều họ chưa nói; sửa một chạm để lượt sau đúng.
 */
export function DuaTren({
  muc,
  onSua,
}: {
  muc: HoSoDaDung[];
  onSua?: (khoa: string, giaTri: string | null) => void;
}) {
  const [dangSua, datDangSua] = useState<string | null>(null);
  const [nhap, datNhap] = useState("");
  if (muc.length === 0) return null;
  return (
    <p className="mb-3 flex flex-wrap items-center gap-x-1 text-[13px] leading-6 text-muted-foreground">
      <span>Dựa trên:</span>
      {muc.map((m, i) => (
        <span key={m.khoa} className="inline-flex items-center gap-1">
          {dangSua === m.khoa ? (
            <input
              autoFocus
              value={nhap}
              maxLength={120}
              aria-label={`Sửa ${m.nhan}`}
              onChange={(e) => datNhap(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  onSua?.(m.khoa, nhap.trim() || null);
                  datDangSua(null);
                }
                if (e.key === "Escape") datDangSua(null);
              }}
              onBlur={() => datDangSua(null)}
              className="focus-brass rounded border border-border bg-card px-1.5 text-foreground"
            />
          ) : (
            <span className={m.gia_dinh ? "italic" : "text-foreground"}>
              {m.nhan.toLowerCase()}: {m.gia_tri}
              {m.gia_dinh && " (tôi đoán)"}
            </span>
          )}
          {onSua && dangSua !== m.khoa && (
            <button
              type="button"
              aria-label={`Sửa ${m.nhan}`}
              onClick={() => {
                datNhap(m.gia_tri);
                datDangSua(m.khoa);
              }}
              className="focus-brass cursor-pointer rounded p-0.5 hover:text-foreground"
            >
              <Pencil className="size-3" aria-hidden />
            </button>
          )}
          {i < muc.length - 1 && <span aria-hidden>·</span>}
        </span>
      ))}
    </p>
  );
}
