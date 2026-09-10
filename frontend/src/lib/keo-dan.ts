/** Kéo dãn theo W3C Window Splitter (spec 2026-09-09 §9.1): một hàm kẹp duy nhất cho cả
 *  giá trị mắt thấy (px) và giá trị đọc màn hình nghe (aria-valuenow %). */
export const RONG_DOI_CHIEU_MAC_DINH = 420;
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

/** Cửa sổ trợ lý nổi (spec 2026-09-09 §9.4): cùng khuôn kẹp min/max/viewport ở
 *  trên, áp cho VỊ TRÍ + KÍCH THƯỚC một lượt — `kepCuaSo` kẹp cả bốn số cùng
 *  nhau vì `w`/`h` đổi thì biên hợp lệ của `x`/`y` cũng đổi theo (cửa sổ lớn
 *  hơn thì góc trên-trái phải lùi lại để không tràn viewport). */
export interface Viewport {
  w: number;
  h: number;
}

export interface CuaSo {
  x: number;
  y: number;
  w: number;
  h: number;
  thu: boolean;
}

export const CUA_SO_RONG = 380;
export const CUA_SO_CAO = 520;
export const CUA_SO_RONG_MIN = 320;
export const CUA_SO_CAO_MIN = 400;
const LE = 24;

/** Vị trí mặc định lần đầu: góc phải dưới, cách mép `LE` px. */
export function CUA_SO_MAC_DINH(vp: Viewport): CuaSo {
  return {
    x: vp.w - CUA_SO_RONG - LE,
    y: vp.h - CUA_SO_CAO - LE,
    w: CUA_SO_RONG,
    h: CUA_SO_CAO,
    thu: false,
  };
}

/** Kẹp cửa sổ vào đúng viewport: không nhỏ hơn kích cỡ tối thiểu, không tràn
 *  ra ngoài bốn cạnh — dù đang kéo, đang thu dãn, hay vừa đọc từ localStorage
 *  của một màn hình khác rộng hơn. */
export function kepCuaSo(cs: CuaSo, vp: Viewport): CuaSo {
  const w = Math.min(vp.w, Math.max(CUA_SO_RONG_MIN, Math.round(cs.w)));
  const h = Math.min(vp.h, Math.max(CUA_SO_CAO_MIN, Math.round(cs.h)));
  const x = Math.min(vp.w - w, Math.max(0, Math.round(cs.x)));
  const y = Math.min(vp.h - h, Math.max(0, Math.round(cs.y)));
  return { x, y, w, h, thu: cs.thu };
}

/** Đọc cửa sổ đã nhớ, kẹp NGAY theo viewport hiện tại — cùng lý do với
 *  `docRongDaLuu`: một cửa sổ nhớ từ màn rộng hơn phải đúng ngay từ khung hình
 *  đầu tiên trên màn hẹp hơn, không đợi một lượt resize. */
export function docCuaSo(khoa: string, vp: Viewport): CuaSo {
  try {
    const raw = globalThis.localStorage?.getItem(khoa);
    if (!raw) return CUA_SO_MAC_DINH(vp);
    const cs = JSON.parse(raw) as Partial<CuaSo>;
    return kepCuaSo({ ...CUA_SO_MAC_DINH(vp), ...cs }, vp);
  } catch {
    return CUA_SO_MAC_DINH(vp);
  }
}

export function luuCuaSo(khoa: string, cs: CuaSo): void {
  try {
    globalThis.localStorage?.setItem(khoa, JSON.stringify(cs));
  } catch {
    /* không có localStorage: bỏ qua, cửa sổ vẫn đúng trong phiên */
  }
}
