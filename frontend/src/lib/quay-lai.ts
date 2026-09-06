/**
 * Đích quay lại sau đăng nhập/đăng ký (`?next=`). Chỉ hai trang bị khoá; mọi
 * giá trị khác bị bỏ — danh sách trắng thay cho kiểm tiền tố, nên không có
 * open redirect và `navigate({ to })` vẫn được TanStack kiểm kiểu.
 */
export const DICH_QUAY_LAI = ["/dung-thu", "/soan-thao"] as const;
export type DichQuayLai = (typeof DICH_QUAY_LAI)[number];

export function locNext(tho: unknown): DichQuayLai | undefined {
  return DICH_QUAY_LAI.find((d) => d === tho);
}
