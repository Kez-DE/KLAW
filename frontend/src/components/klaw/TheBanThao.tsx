import { FileText } from "lucide-react";
import type { TraCuuKetQua } from "@/lib/klaw";

/** Thẻ bàn giao (theo teardown Claude Artifacts): báo có sản phẩm, KHÔNG phải
 *  nơi làm việc — bấm "Mở bản thảo" đưa sang khung soạn thảo hiện có (Task 21);
 *  một sân khấu thật đến ở giai đoạn 5. `document`/`clauses`/`audit_report`
 *  của `ban_thao` là bản thảo được MÁY DỰNG, kiểm toán riêng ở `audit_report`
 *  — không phải một khẳng định pháp lý đã trích dẫn, nên card này không mượn
 *  màu hay khay của các nhánh tra cứu. */
export function TheBanThao({ ketQua, onMo }: { ketQua: TraCuuKetQua; onMo: (id: string) => void }) {
  const bt = ketQua.ban_thao;
  if (!bt) return null;
  return (
    <section
      aria-label="Bản thảo đã sẵn sàng"
      className="rounded-xl border border-border bg-card p-4 shadow-soft"
    >
      <div className="flex items-start gap-3">
        <FileText className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="m-0 text-[15px] font-semibold text-foreground">
            Bản thảo đã sẵn sàng · {bt.ten}
          </p>
          <p className="m-0 mt-0.5 text-[13px] text-muted-foreground">
            Phiên bản {bt.phien_ban}
            {/* ĐẾM, không liệt kê: `doi_so_voi_truoc` là khoá field thô
                (`luong`, `thoi_han_hop_dong`) và nhãn tiếng Việt của chúng chỉ
                có sau khi `GET /mau/{loai}` về — thẻ này không nạp mẫu. Tên
                từng dữ kiện đã hiện đúng ở sân khấu, nơi nhãn đã có. */}
            {bt.doi_so_voi_truoc.length > 0 && ` · đã đổi ${bt.doi_so_voi_truoc.length} dữ kiện`} ·{" "}
            {bt.clauses.length} mục
          </p>
        </div>
        <button
          type="button"
          onClick={() => onMo(bt.id)}
          className="focus-brass bg-gradient-ink cursor-pointer rounded-lg px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Mở bản thảo
        </button>
      </div>
    </section>
  );
}
