import type { LuotDaXong } from "./lich-su";

/** Mã khách cho người chưa đăng nhập (spec 2026-09-07 §8.1). KHÔNG phải danh tính:
 *  máy chủ chỉ dùng nó làm khoá đếm 10 lượt/24 giờ. Sống trong localStorage để tải
 *  lại trang không được thêm lượt; đoạn chat thì KHÔNG lưu (state trang). */
export const KHACH_HEADER = "X-Khach-Id";
const KHOA = "klaw.khach_id";

/** Mã tạm của tab hiện tại. CACHE, không sinh mới mỗi lần gọi: mã này là KHOÁ ĐẾM
 *  của giỏ 10 lượt/24 giờ, nên một mã mới mỗi request nghĩa là khách ở cửa sổ ẩn
 *  danh không bao giờ tích vào đúng giỏ của mình. */
let tam: string | undefined;

function moiId(): string {
  // `crypto.randomUUID` KHÔNG tồn tại ở ngữ cảnh không bảo mật (http://192.168.x.x:…,
  // tức mọi lần mở trên điện thoại cùng mạng LAN). Không có nhánh này thì
  // `layKhachId` ném ở dòng try, ném LẠI trong catch, và lỗi thoát khỏi
  // `tieuDeXacThuc()` — mọi lời gọi API của ứng dụng hỏng, kể cả những endpoint
  // trước nhánh này vốn chạy được mà không cần đăng nhập.
  return typeof crypto?.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function layKhachId(): string {
  try {
    const cu = localStorage.getItem(KHOA);
    if (cu !== null && cu !== "") return cu;
    const moi = moiId();
    localStorage.setItem(KHOA, moi);
    return moi;
  } catch {
    return (tam ??= moiId()); // không có localStorage: một mã tạm cho cả tab này
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
