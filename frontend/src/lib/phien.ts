/**
 * Chữ và số cho cột phiên hội thoại (spec 2026-09-07 §6). Thuần — kiểm bằng
 * `scripts/kiem-phien.ts` không cần dựng trang.
 */

/** Tên gói hiện cho người dùng; gói lạ trả nguyên mã để không bịa tên. */
export function tenGoi(plan: string): string {
  if (plan === "free") return "Miễn phí";
  if (plan === "pro") return "Pro";
  return plan;
}

/** Dòng cuối cột phiên khi có phiên bị ẩn theo gói. */
export function cauPhienAn(plan: string, gioiHan: number, tongAn: number): string {
  return `Gói ${tenGoi(plan)} giữ ${gioiHan} phiên gần nhất. ${tongAn} phiên cũ hơn đang ẩn.`;
}

const PHUT = 60_000;
const GIO = 60 * PHUT;
const NGAY = 24 * GIO;

/** "vừa xong" / "5 phút trước" / "3 giờ trước" / "hôm qua" / "4 ngày trước" / "29/07/2026".
 *  `bayGio` truyền vào được để kiểm tất định. Chuỗi ngày sai → "" (không đoán). */
export function thoiGianTuongDoi(iso: string, bayGio: number = Date.now()): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const cach = Math.max(0, bayGio - t);
  if (cach < PHUT) return "vừa xong";
  if (cach < GIO) return `${Math.floor(cach / PHUT)} phút trước`;
  if (cach < NGAY) return `${Math.floor(cach / GIO)} giờ trước`;
  const ngay = Math.floor(cach / NGAY);
  if (ngay === 1) return "hôm qua";
  if (ngay < 30) return `${ngay} ngày trước`;
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(t);
}
