import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * "2026-01-01" → "01/01/2026".
 *
 * CẮT CHUỖI, không đi qua `Date`. `new Date("2026-01-01")` phân giải là nửa
 * đêm UTC, rồi `toLocaleDateString` in ra theo múi giờ của MÁY người dùng —
 * một người mở trang ở UTC−5 sẽ thấy 31/12/2025. Với một ngày dùng để hỏi
 * "luật tại thời điểm nào", lệch một ngày là lệch sang một văn bản khác.
 *
 * Chuỗi không đúng dạng ISO trả về NGUYÊN VĂN: thà hiện thứ máy chủ gửi còn
 * hơn hiện "NaN/NaN/NaN".
 */
export function ngayVietNam(iso: string): string {
  // Khớp CHẶT thay vì `split("-")`. Cắt ngây thơ nhận cả những chuỗi không
  // phải ngày ISO rồi trả ra thứ trông như ngày: "2026-01-01T00:00:00Z" thành
  // "01T00:00:00Z/01/2026", và "2026-1-1" thành "1/1/2026" — mất số 0 đứng đầu
  // mà hàm này tồn tại để giữ.
  const khop = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (khop === null) return iso;
  return `${khop[3]}/${khop[2]}/${khop[1]}`;
}
