/**
 * Sân khấu của `/dung-thu` — bản thảo, hoặc "Bản tải lên" (khuôn gốc đúng như
 * tệp, chỉ xem). MỘT state cho cả hai nên chúng loại trừ nhau và dùng chung một
 * cửa đóng (`onDongSanKhau`). Thuần, không DOM: `scripts/kiem-ui-muot.ts` kiểm
 * được mà không dựng cả trang (router, tài khoản, vỏ ứng dụng).
 */
import { khuonHopLe, type ApiResult, type BanThao } from "./klaw";

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

/** `?…` của `/dung-thu` khi sân khấu mở bản thảo `id` (`null`: đóng). BẤT BIẾN:
 *  `?ban_thao=` LÀ bản đang mở — mọi lối mở (vỏ trang, thẻ trong chat, chuyển
 *  sang bản khác) ghi nó, cửa đóng gỡ nó — nên tải lại trang mở lại đúng bản
 *  đang xem (R6). Giữ `?q=`/`?phien=`. */
export const thamSoSanKhau = (
  q: string | undefined,
  phien: string | undefined,
  id: string | null,
): { q?: string; phien?: string; ban_thao?: string } => ({
  ...(q !== undefined ? { q } : {}),
  ...(phien !== undefined ? { phien } : {}),
  ...(id !== null ? { ban_thao: id } : {}),
});

/** Cửa đóng phải gỡ `?ban_thao=`: URL đang mang nó, HOẶC sân khấu là một bản
 *  thảo — lối mở đã ghi nó dù closure gọi đóng (một `layBanThao` hỏng về muộn)
 *  dựng từ lúc URL chưa có. "Bản tải lên" không ghi URL. */
export const urlCoBanThao = (banThaoTrenUrl: string | undefined, sk: SanKhau) =>
  banThaoTrenUrl !== undefined || sk?.loai === "ban_thao";

/** Cuộc trò chuyện đang mở vừa đổi (vỏ trang, "Phiên mới", URL): sân khấu thuộc
 *  cuộc trò chuyện đã mở nó, nên đóng qua cửa đóng — TRỪ khi chính URL mới mang
 *  `?ban_thao=`. Lối duy nhất ghi cả hai là danh sách "Bản thảo" của vỏ trang,
 *  với `?phien=` của chính bản thảo đó, và hiệu ứng đọc URL (chạy trước) đã
 *  mở/chuyển sang nó. Không đọc `sk` để so id: lúc này nó còn là bản cũ. */
export const dongKhiDoiPhien = (banThaoTrenUrl: string | undefined, sk: SanKhau) =>
  sk !== null && banThaoTrenUrl === undefined;

/** Cập nhật bản thảo đang mở CHỈ bằng chính nó (cùng `id`): một lượt lưu hay lùi
 *  về muộn của bản thảo trước không được thay bản người dùng vừa chuyển sang. */
export const apNeuCungBan = <T extends { id: string }>(cu: T | null, moi: T): T | null =>
  cu !== null && cu.id === moi.id ? moi : cu;

/** Kết quả chat MỚI mang bản thảo trên khuôn gốc (lượt điền/sửa/dựng lại, hay
 *  lượt "cho tôi xem bản đã điền"): sân khấu tự mở trên nó (chủ dự án
 *  2026-09-28, Q2) — chat vẫn giữ lời đáp và thẻ. Bản thảo HTML: không. */
export const banThaoTuMo = (bt: BanThao | null | undefined): BanThao | null =>
  bt != null && khuonHopLe(bt.khuon) !== null ? bt : null;

/** Chỉ cú bấm MỚI NHẤT được áp phản hồi của nó: bấm dòng tài liệu này rồi dòng
 *  khác (nhãn A/B, thẻ của lượt khác) trước khi GET đầu về thì phản hồi về SAU
 *  CÙNG không được mở đè lên thứ cú bấm mới hơn đã mở. Vé cũ trả `null`. */
export function chiMoiNhat() {
  let so = 0;
  return async <T>(viec: Promise<T>): Promise<T | null> => {
    const ve = ++so;
    const kq = await viec;
    return ve === so ? kq : null;
  };
}

/** Việc của một cú bấm dòng tài liệu trên thẻ chat (Q1). */
export type ViecMoTaiLieu =
  | { loai: "ban_thao"; banThao: BanThao }
  | { loai: "ban_tai_len" }
  | { loai: "du_kien" }
  | { loai: "loi"; cau: string };

/** Bấm dòng tài liệu (chủ dự án 2026-09-28, Q1): bản thảo MỚI NHẤT của tài liệu
 *  đó (bản đã sửa) nếu có, không thì "Bản tải lên". Tài liệu đã biết là không
 *  có khuôn gốc (ảnh, tệp tải lên trước khi có khuôn) không có bản tải lên nào
 *  để vẽ: mở "Dữ kiện đã đọc", không tốn lượt gọi. */
export async function viecMoTaiLieu(
  coKhuonGoc: boolean | undefined,
  lay: () => Promise<ApiResult<BanThao>>,
): Promise<ViecMoTaiLieu> {
  if (coKhuonGoc === false) return { loai: "du_kien" };
  const kq = await lay();
  if (kq.ok) return { loai: "ban_thao", banThao: kq.data };
  return kq.error.status === 404 ? { loai: "ban_tai_len" } : { loai: "loi", cau: kq.error.message };
}
