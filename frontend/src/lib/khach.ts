import type { LuotDaXong } from "./lich-su";

/** Mã khách cho người chưa đăng nhập (spec 2026-09-07 §8.1). KHÔNG phải danh tính:
 *  máy chủ chỉ dùng nó làm khoá đếm 10 lượt/24 giờ. Sống trong localStorage để tải
 *  lại trang không được thêm lượt; đoạn chat thì KHÔNG lưu (state trang). */
export const KHACH_HEADER = "X-Khach-Id";
const KHOA = "klaw.khach_id";

export function layKhachId(): string {
  try {
    const cu = localStorage.getItem(KHOA);
    if (cu !== null && cu !== "") return cu;
    const moi = crypto.randomUUID();
    localStorage.setItem(KHOA, moi);
    return moi;
  } catch {
    return crypto.randomUUID(); // không có localStorage: mã tạm cho tab này
  }
}

const KHOA_THREAD = "klaw.khach_thread";

/** Cất đoạn chat khách trước khi rời sang đăng nhập/đăng ký (spec 2A §8.4). */
export function catThreadKhach(luot: LuotDaXong[]): void {
  try {
    if (luot.length > 0) sessionStorage.setItem(KHOA_THREAD, JSON.stringify(luot.slice(-10)));
  } catch {
    /* không có sessionStorage: bỏ qua, người dùng vẫn đăng nhập được */
  }
}
export function layThreadKhach(): LuotDaXong[] | null {
  try {
    const tho = sessionStorage.getItem(KHOA_THREAD);
    if (tho === null) return null;
    const du: unknown = JSON.parse(tho);
    return Array.isArray(du) && du.length > 0 ? (du as LuotDaXong[]) : null;
  } catch {
    return null;
  }
}
export function xoaThreadKhach(): void {
  try {
    sessionStorage.removeItem(KHOA_THREAD);
  } catch {
    /* bỏ qua */
  }
}
