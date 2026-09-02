import { Plug } from "lucide-react";
import { cn } from "@/lib/utils";

// StatusBadge, CitationChip và SourceRow đã bị gỡ cùng lib/mock-legal.ts: cả ba
// nhận LegalDoc — bản ghi văn bản bịa với ba nhãn tình trạng bịa. KLAW có năm
// nhãn hiệu lực (con_hieu_luc, bi_thay_the, mot_phan_khong_xac_dinh,
// bi_sua_doi, can_doi_chieu_tay) và chúng phải bắt nguồn từ effectivity.py,
// không phải từ một enum ba giá trị viết trong FE. Dựng lại ở pha nối FE, theo
// hợp đồng thật.

// ChuaNoiBanner đã gỡ: mọi màn hình nay nối vào máy chủ thật, nên một dải nói
// "chưa nối dữ liệu" sẽ là lời khai sai theo chiều ngược lại.

/**
 * Màn soạn thảo chạy thật và chạy hoàn toàn trên máy người dùng — nói "chưa nối
 * dữ liệu" ở đó là sai theo chiều ngược lại. Cái chưa có là việc đối chiếu căn
 * cứ pháp lý với kho văn bản của KLAW.
 *
 * Bản thảo in căn cứ ở HAI chỗ, và tình trạng đối chiếu của chúng KHÁC nhau —
 * đo ngày 2026-09-02 trên cả 26 kiểu backend:
 *
 * 1. Dòng "Căn cứ pháp lý mẫu" ở bước 1 — chuỗi viết cứng trong danh mục FE
 *    (`mau-van-ban.ts`), chưa bao giờ chạm kho.
 * 2. Chú thích căn cứ dưới từng điều — do máy chủ soạn theo từng mục
 *    (`cau_truc.muc[].can_cu`), xuất xứ tốt hơn hằng số FE. Nhưng **202/202 mục
 *    chỉ có `can_cu` dạng chuỗi, 0/202 có `can_cu_chi_tiet`** — tới FE nó vẫn là
 *    tham chiếu chưa phân giải, không kèm tình trạng hiệu lực.
 *
 * Chỉ `can_cu_goc` ở cấp văn bản là có phân giải, và cũng chỉ 21/26 kiểu.
 *
 * Vì vậy KHÔNG thu hẹp cảnh báo này xuống riêng cấp thẻ: thu hẹp là ngụ ý thân
 * văn bản đã đối chiếu, trong khi nó chưa. Cái sai của câu cũ là **lý do**
 * ("chuỗi viết cứng" — đúng cho chỗ 1, sai cho chỗ 2), không phải phạm vi.
 * `kiem-khung` canh mốc 0/202; nó đỏ nghĩa là máy chủ đã phân giải, lúc đó mới
 * sửa câu này.
 */
export function CanCuChuaKiemBanner({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex items-start gap-2 border-b border-border bg-[var(--color-paper-100)] px-4 py-2 text-[12px] text-muted-foreground",
        className,
      )}
    >
      <Plug className="mt-0.5 size-3.5 shrink-0" />
      <p>
        <span className="font-semibold text-foreground">Căn cứ pháp lý chưa được đối chiếu.</span>{" "}
        Bản thảo được dựng và xuất tệp ngay trên máy bạn, nội dung không rời trình duyệt. Căn cứ in
        trong bản thảo — cả dòng “Căn cứ pháp lý mẫu” lẫn chú thích dưới từng điều — mới là tham
        chiếu tới số hiệu, điều, khoản, điểm; chúng chưa được phân giải tới điều khoản trong kho văn
        bản của KLAW và chưa kiểm hiệu lực. Hãy tự đối chiếu trước khi ký.
      </p>
    </div>
  );
}
