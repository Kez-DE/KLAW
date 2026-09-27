/**
 * Chữ và số cho cột phiên hội thoại (spec 2026-09-07 §6). Thuần — kiểm bằng
 * `scripts/kiem-phien.ts` không cần dựng trang.
 */
import type { BanThao, BanThaoTomTat } from "./klaw";

const PHUT = 60_000;
const GIO = 60 * PHUT;
const NGAY = 24 * GIO;

/** "vừa xong" / "5 phút trước" / "3 giờ trước" / "hôm qua" / "4 ngày trước" / "29/07/2026".
 *  `bayGio` truyền vào được để kiểm tất định. Chuỗi ngày sai → "" (không đoán). */
export function thoiGianTuongDoi(iso: string, bayGio: number = Date.now()): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const cach = Math.max(0, bayGio - t);
  if (cach < PHUT) return "vừa xong";
  if (cach < GIO) return `${Math.floor(cach / PHUT)} phút trước`;
  if (cach < NGAY) return `${Math.floor(cach / GIO)} giờ trước`;
  const ngay = Math.floor(cach / NGAY);
  if (ngay === 1) return "hôm qua";
  if (ngay < 30) return `${ngay} ngày trước`;
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(t);
}

/** Danh sách "Bản thảo" của cột sau khi bản `bt` vừa đổi phiên bản (lưu, lùi,
 *  lượt chat) — vá TẠI CHỖ thay vì gọi lại `GET /ban-thao`: mỗi lượt gọi có danh
 *  tính tốn một lượt của giỏ nhịp theo IP, và lưu từng chỗ trống đã tốn một. Bản
 *  đó lên đầu (máy chủ xếp theo `cap_nhat_luc`, mà mỗi phiên bản mới đẩy nó lên).
 *  Cùng phiên bản: danh sách giữ nguyên. `null`: bản chưa có trong danh sách
 *  (vừa tạo) — nơi gọi tải lại, vì `hoi_thoai_id` của nó chỉ máy chủ biết. */
export function vaBanThaoGanDay(
  ds: BanThaoTomTat[],
  bt: Pick<BanThao, "id" | "ten" | "phien_ban">,
  luc: string,
): BanThaoTomTat[] | null {
  const cu = ds.find((x) => x.id === bt.id);
  if (cu === undefined) return null;
  if (cu.phien_ban === bt.phien_ban) return ds;
  return [
    { ...cu, ten: bt.ten, phien_ban: bt.phien_ban, cap_nhat_luc: luc },
    ...ds.filter((x) => x.id !== bt.id),
  ];
}
