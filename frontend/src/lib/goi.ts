/**
 * Chữ cho gói và thẻ so sánh gói (spec 2A §7.5). Thuần — kiểm bằng
 * `scripts/kiem-han-muc.ts` không cần dựng trang.
 */
import {
  BookOpenText,
  CalendarClock,
  Download,
  FileSignature,
  History,
  ListOrdered,
  MessageSquare,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

/** Tên gói hiện cho người dùng; gói lạ trả nguyên mã để không bịa tên. */
export function tenGoi(plan: string): string {
  if (plan === "free") return "Miễn phí";
  if (plan === "pro") return "Cá nhân";
  if (plan === "khach") return "Dùng thử";
  return plan;
}

export const GIA_PRO = 499_000;

export const GOI_CARD: Record<
  "free" | "pro",
  {
    nhan: string;
    tieuDe: string;
    moTa: string;
    gia: string;
    tieuDeDanhSach: string;
    danhSach: { icon: LucideIcon; chu: string }[];
  }
> = {
  free: {
    nhan: "Miễn phí",
    tieuDe: "Dùng thử KLAW",
    moTa: "Hỏi pháp luật lao động và nhận câu trả lời có căn cứ kiểm chứng được, soạn văn bản mẫu, tra cứu luật.",
    gia: "₫0 / tháng",
    tieuDeDanhSach: "Bắt đầu với những điều cơ bản:",
    danhSach: [
      { icon: MessageSquare, chu: "200 lượt hỏi đáp mỗi ngày" },
      { icon: ListOrdered, chu: "20 lượt mỗi phiên" },
      { icon: FileSignature, chu: "3 bản thảo mỗi ngày, 20 mỗi tháng" },
      { icon: History, chu: "Phiên và lịch sử không giới hạn" },
      { icon: BookOpenText, chu: "Tra cứu luật, soát văn bản không giới hạn" },
      { icon: Download, chu: "Xuất Word, PDF" },
    ],
  },
  pro: {
    nhan: "Cá nhân",
    tieuDe: "Dùng cho công việc",
    moTa: "Cho luật sư, chuyên viên nhân sự và pháp chế hỏi nhiều mỗi ngày và soạn văn bản thường xuyên.",
    gia: "₫499.000 / 30 ngày",
    tieuDeDanhSach: "Mọi thứ trong gói Miễn phí, cộng thêm:",
    danhSach: [
      { icon: Sparkles, chu: "Hỏi đáp không giới hạn ngày và tháng*" },
      { icon: ListOrdered, chu: "50 lượt mỗi phiên" },
      { icon: FileSignature, chu: "20 bản thảo mỗi ngày, không giới hạn tháng" },
      { icon: History, chu: "Trí nhớ hoàn cảnh xuyên phiên (sắp có)" },
      { icon: CalendarClock, chu: "Hiệu lực 30 ngày, gia hạn khi hết" },
    ],
  },
};
