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
