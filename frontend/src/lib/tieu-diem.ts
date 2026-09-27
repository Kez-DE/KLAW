/**
 * Nơi trả tiêu điểm khi sân khấu đóng (WCAG 2.4.3). Chỉ kiểu cấu trúc, không
 * DOM: `scripts/kiem-tieu-diem.ts` chạy bằng `node` trần.
 *
 * Nút đã mở sân khấu, nếu còn trong DOM (bố cục rộng). Ở bố cục hẹp, lượt vẽ mở
 * sân khấu tháo CẢ cây chat, nên nút đó đã rời DOM; đóng sân khấu dựng lại cây
 * đó, và bản dựng lại mang cùng `data-mo-san-khau` — `tim` tìm nó. Không có thì
 * `duPhong` (ô hỏi), không bao giờ `<body>`.
 */
interface NutTieuDiem {
  isConnected: boolean;
  getAttribute(ten: string): string | null;
}

export function noiTraTieuDiem<T extends NutTieuDiem>(
  noiMo: T | null,
  tim: (khoa: string) => T | null,
  duPhong: T | null,
): T | null {
  if (noiMo?.isConnected) return noiMo;
  const khoa = noiMo?.getAttribute("data-mo-san-khau") ?? null;
  return (khoa === null ? null : tim(khoa)) ?? duPhong;
}
