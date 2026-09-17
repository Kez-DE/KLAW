/** Kéo dãn theo W3C Window Splitter (spec 2026-09-09 §9.1): một hàm kẹp duy nhất cho cả
 *  giá trị mắt thấy (px) và giá trị đọc màn hình nghe (aria-valuenow %). */
export const RONG_DOI_CHIEU_MAC_DINH = 420;
/** Bề rộng mặc định của khung bản thảo (sân khấu) khi mở hai cột (D5, canvas-
 *  tai-lieu Phase 2) — rộng hơn khung đối chiếu vì nó còn cõng cột "Các mục" +
 *  bản xem trước A4, 420px không đủ chỗ cho cả hai. Cùng khuôn `RONG_DOI_CHIEU_MAC_DINH`:
 *  chỉ là điểm khởi đầu, `kepRong` vẫn kẹp vào biên thật của cửa sổ. */
export const RONG_SAN_KHAU_MAC_DINH = 640;
export const BUOC_PHIM = 24;
export const BUOC_PHIM_LON = 96;
export const RONG_TOI_THIEU = 320;
export const CHAT_TOI_THIEU = 480;

export interface Bien {
  min: number;
  max: number;
}

export function kepRong(px: number, bien: Bien): number {
  return Math.min(bien.max, Math.max(bien.min, Math.round(px)));
}

export function phanTram(px: number, bien: Bien): number {
  if (bien.max <= bien.min) return 100;
  return Math.round(((kepRong(px, bien) - bien.min) / (bien.max - bien.min)) * 100);
}

export function bienPanelDoiChieu(beRongCuaSo: number): Bien {
  const max = Math.max(
    RONG_TOI_THIEU,
    Math.min(Math.round(0.6 * beRongCuaSo), beRongCuaSo - CHAT_TOI_THIEU),
  );
  return { min: RONG_TOI_THIEU, max };
}

export function docRongDaLuu(khoa: string, macDinh: number): number {
  try {
    const raw = globalThis.localStorage?.getItem(khoa);
    const so = raw === null || raw === undefined ? NaN : Number(raw);
    return Number.isFinite(so) ? so : macDinh;
  } catch {
    return macDinh;
  }
}

export function luuRong(khoa: string, px: number): void {
  try {
    globalThis.localStorage?.setItem(khoa, String(px));
  } catch {
    /* không có localStorage: bỏ qua, độ rộng vẫn đúng trong phiên */
  }
}
