import { Plug } from "lucide-react";
import { cn } from "@/lib/utils";

// StatusBadge, CitationChip và SourceRow đã bị gỡ cùng lib/mock-legal.ts: cả ba
// nhận LegalDoc — bản ghi văn bản bịa với ba nhãn tình trạng bịa. KLAW có năm
// nhãn hiệu lực (con_hieu_luc, bi_thay_the, mot_phan_khong_xac_dinh,
// bi_sua_doi, can_doi_chieu_tay) và chúng phải bắt nguồn từ effectivity.py,
// không phải từ một enum ba giá trị viết trong FE. Dựng lại ở pha nối FE, theo
// hợp đồng thật.

/** Nói thẳng là màn hình chưa có đường dữ liệu — khác hẳn "không có kết quả". */
export function ChuaNoiBanner({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex items-start gap-2 border-b border-border bg-[var(--color-paper-100)] px-4 py-2 text-[12px] text-muted-foreground",
        className,
      )}
    >
      <Plug className="mt-0.5 size-3.5 shrink-0" />
      <p>
        <span className="font-semibold text-foreground">Chưa nối dữ liệu.</span> Bản dựng này mới có
        giao diện; kho văn bản pháp luật của KLAW chưa được nối vào. Màn hình không hiển thị nội
        dung minh hoạ thay thế.
      </p>
    </div>
  );
}

/**
 * Màn soạn thảo chạy thật và chạy hoàn toàn trên máy người dùng — nói "chưa nối
 * dữ liệu" ở đó là sai theo chiều ngược lại. Cái chưa có là việc đối chiếu căn
 * cứ pháp lý với kho văn bản của KLAW.
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
        Bản thảo được dựng và xuất tệp ngay trên máy bạn, nội dung không rời trình duyệt. Nhưng các
        căn cứ pháp lý in trong mẫu là chuỗi viết cứng, chưa kiểm với kho văn bản của KLAW và chưa
        kiểm hiệu lực — hãy tự đối chiếu trước khi ký.
      </p>
    </div>
  );
}
