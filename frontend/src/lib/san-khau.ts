/**
 * Sân khấu của `/dung-thu` — bản thảo, hoặc "Bản tải lên" (khuôn gốc đúng như
 * tệp, chỉ xem). MỘT state cho cả hai nên chúng loại trừ nhau và dùng chung một
 * cửa đóng (`onDongSanKhau`). Thuần, không DOM: `scripts/kiem-ui-muot.ts` kiểm
 * được mà không dựng cả trang (router, tài khoản, vỏ ứng dụng).
 */
export type SanKhau =
  | { loai: "ban_thao"; banThaoId: string }
  | { loai: "ban_tai_len"; viecId: string; tenTep: string; soTrang: number | null }
  | null;

/** Phản hồi `layBanThao(id)` về muộn chỉ áp khi sân khấu VẪN nhắm đúng bản thảo
 *  đó: người dùng đã bấm mở bản khác (hay đã đóng) trong lúc chờ thì phản hồi cũ
 *  không được đè lên bản mới — sân khấu kẹt ở "Đang mở bản thảo…" — và một lỗi
 *  cũ không được đóng sân khấu người dùng vừa mở. */
export const vanNham = (sk: SanKhau, id: string) => sk?.loai === "ban_thao" && sk.banThaoId === id;

/** `?ban_thao=` còn trỏ tới bản thảo KHÁC bản sắp mở: phải gỡ nó qua cửa đóng.
 *  Giữ lại thì tải lại trang mở nhầm bản cũ, và bấm lại đúng bản cũ ở danh sách
 *  của vỏ trang không đổi URL nên không làm gì — một cú bấm bị nuốt. */
export const urlTroBanKhac = (banThaoTrenUrl: string | undefined, id: string) =>
  banThaoTrenUrl !== undefined && banThaoTrenUrl !== id;

/** Cập nhật bản thảo đang mở CHỈ bằng chính nó (cùng `id`): một lượt lưu hay lùi
 *  về muộn của bản thảo trước không được thay bản người dùng vừa chuyển sang. */
export const apNeuCungBan = <T extends { id: string }>(cu: T | null, moi: T): T | null =>
  cu !== null && cu.id === moi.id ? moi : cu;
