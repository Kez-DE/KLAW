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
/** Bề rộng thật của `TayKeo` (`w-2`/`h-2`, `components/ui/TayKeo.tsx`) — hàng
 *  chat+splitter+panel có BA phần, không phải hai; thiếu số này thì
 *  `bienPanelDoiChieu` tính trần panel để lọt vừa panel + sàn chat, còn
 *  chính cái splitter đứng giữa hai bên lại tràn thêm ra ngoài (đo trực
 *  tiếp: panel ở đúng trần tự báo + chat ở đúng sàn vẫn tràn 8px, y hệt bề
 *  rộng splitter — Phase 9 U4 fix round 1). */
export const RONG_TAY_KEO_PX = 8;

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

/**
 * `beRongConLai` (Phase 9 U4 fix round 1, đổi tên từ `beRongCuaSo`) — PHẢI là
 * bề rộng THẬT còn lại cho hàng chat+splitter+panel, không phải
 * `window.innerWidth`. Bản thân hàm này không đổi gì (vẫn chỉ tính "còn lại
 * bao nhiêu cho panel bên phải mà chat vẫn còn `CHAT_TOI_THIEU`"); cái đổi là
 * NGHĨA của tham số nó nhận — reviewer đo được `window.innerWidth` LỚN HƠN
 * bề rộng thật khi cột trái của `AppShell` đang hiện (tới 260px ở ≥80rem),
 * nên trần panel tính ra có thể vượt phần thật sự còn lại: panel đứng
 * `shrink-0` ở đúng trần đó cộng cột chat đã có sàn riêng (`sanRongChat`) thì
 * tổng bề rộng tràn ra ngoài khung nhìn, không chỉ ép chat co lại như trước.
 * Người gọi (`dung-thu.tsx`) đo bằng `ResizeObserver` trên chính khung bọc
 * hàng đó, không tính lại logic cột trái ở đây — đo THẬT luôn đúng hơn suy
 * ra lại một mô hình khác của cùng bố cục.
 */
export function bienPanelDoiChieu(beRongConLai: number): Bien {
  const max = Math.max(
    RONG_TOI_THIEU,
    Math.min(Math.round(0.6 * beRongConLai), beRongConLai - CHAT_TOI_THIEU - RONG_TAY_KEO_PX),
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

/**
 * Sàn CSS bắt buộc cho cột chat (Phase 9 U4, `.sdd/phase-9-brief.md`) — đo
 * được cửa sổ 1512px cho cột chat khoảng 215px, dưới xa `CHAT_TOI_THIEU`.
 * Nguyên nhân GỐC (`bienPanelDoiChieu` tính trần panel bên cạnh từ
 * `window.innerWidth` mà không trừ cột trái của `AppShell`) đã sửa ở
 * `dung-thu.tsx` (đo THẬT bề rộng còn lại bằng `ResizeObserver` — xem
 * `bienPanelDoiChieu`); sàn này GIỮ LẠI làm lớp phòng thủ thứ hai, không thay
 * cho lớp thứ nhất — một `min-width` áp thẳng lên cột chat đúng bất kể một
 * phép tính bề rộng nào đó ở nơi khác (kể cả một phép tính tương lai) có đúng
 * hay không, "cho nó một sàn không thể xuống dưới", không phải kẹp chữ hiển
 * thị.
 *
 * `undefined` CHỈ khi đang ở khung hẹp cố ý 420px để CHỌN LOẠI văn bản
 * (`soanThao` mở, hai cột) — một tính năng khác, không phải chỗ bug này xảy
 * ra, và một sàn 480px ở đó sẽ ĐÈ mất chủ đích 420px (CSS `min-width` luôn
 * thắng `max-width` khi xung đột).
 */
export function sanRongChat(dangChonLoaiVanBan: boolean): number | undefined {
  return dangChonLoaiVanBan ? undefined : CHAT_TOI_THIEU;
}
