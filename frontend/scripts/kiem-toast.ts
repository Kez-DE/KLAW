/**
 * Vị trí toast (Phase 9 U3 fix round 1) — không đè lên header dính đỉnh của
 * `AppShell` (nút "Phiên"/CTA khách) lẫn ô soạn câu hỏi cuối cột chat.
 *
 * Không có `jsdom` trong repo này (xem `kiem-xuat-tep.ts`), nên đây là phép
 * kiểm HÌNH HỌC thuần trên các hằng số đã đo trực tiếp trên trang thật
 * (`lib/toast.ts`), không phải một bản dựng DOM giả — nếu ai đó hạ
 * `TOAST_OFFSET_TREN` hay header cao thêm mà không cập nhật hằng số kia,
 * phép kiểm này báo ngay, thay vì phải đo lại bằng tay lần nữa. Chạy:
 * `npm run kiem-toast`.
 */
import assert from "node:assert/strict";
import {
  CHIEU_CAO_HEADER_DO_DUOC,
  CHIEU_CAO_TOAST_MOT_DONG,
  TOAST_OFFSET_TREN,
} from "../src/lib/toast.ts";

// sonner neo CẠNH DƯỚI của một toast `top-*` vào `offset.top` (đo trực tiếp:
// `offset.top = 80` từng cho `toastRect.bottom = 80`, không phải `.top`), nên
// cạnh TRÊN thật của toast là `TOAST_OFFSET_TREN - CHIEU_CAO_TOAST_MOT_DONG`.
const canhTrenThatCuaToast = TOAST_OFFSET_TREN - CHIEU_CAO_TOAST_MOT_DONG;

assert.ok(
  canhTrenThatCuaToast > CHIEU_CAO_HEADER_DO_DUOC,
  `toast (cạnh trên ${canhTrenThatCuaToast}px) phải nằm HẲN dưới header (cao ${CHIEU_CAO_HEADER_DO_DUOC}px)`,
);

// Biên an toàn tối thiểu 10px — không chỉ "vừa đủ", vì các trạng thái header
// chưa đo tới (CTA khách dài hơn nút "Phiên") có thể cao hơn 1-2px so với
// giá trị đã ghim.
assert.ok(
  canhTrenThatCuaToast - CHIEU_CAO_HEADER_DO_DUOC >= 10,
  "biên an toàn giữa toast và header phải còn ít nhất 10px",
);

console.log("kiem-toast: 2/2 OK");
