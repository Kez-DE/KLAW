/**
 * Ngăn xếp drawer xếp chồng (Task 25, spec 2026-09-09 §9.4) — kiểu Payload
 * (`useEditDepth`): mở một mục trong sân khấu trượt ra một tấm; mở thứ gì đó
 * bên trong tấm đó trượt thêm một tấm chồng lên trên, breadcrumb cho biết
 * đang đứng ở đâu. Module THUẦN, không React: `NganXepDrawer.tsx` chỉ nối sự
 * kiện vào các hàm dưới đây, không tự quyết định gì về ngăn xếp.
 */

export interface Tam {
  id: string;
  tieuDe: string;
  noiDung: unknown;
}

/** Trần số tầng cùng lúc — quá sâu thì người dùng lạc breadcrumb, không phải
 *  một giới hạn kỹ thuật. */
export const TOI_DA_TANG = 3;

/**
 * Mở một tấm mới lên trên cùng. Trùng `id` với một tấm đã có → THAY TẠI CHỖ
 * (không đẩy lên trên, không nhân đôi): mở lại đúng mục đang mở là cập nhật
 * nội dung của nó, không phải chồng thêm một tầng.
 *
 * Đã ở trần (`toiDa` tầng) và `id` chưa từng có → bỏ qua, giữ nguyên ngăn xếp.
 */
export function moTam(ngan: Tam[], tam: Tam, toiDa = TOI_DA_TANG): Tam[] {
  const i = ngan.findIndex((t) => t.id === tam.id);
  if (i >= 0) return ngan.map((t, j) => (j === i ? tam : t));
  return ngan.length >= toiDa ? ngan : [...ngan, tam];
}

/** Đóng tấm trên cùng (Esc, hoặc nút Đóng của tấm đó). Ngăn xếp rỗng → rỗng. */
export function dongTrenCung(ngan: Tam[]): Tam[] {
  return ngan.slice(0, -1);
}

/** "Mục 10 › Khoản 2 › Căn cứ" — nơi đang đứng, nối bằng " › ". */
export function breadcrumb(ngan: Tam[]): string {
  return ngan.map((t) => t.tieuDe).join(" › ");
}
