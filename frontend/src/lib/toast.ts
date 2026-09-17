/**
 * Vị trí toast toàn cục (Phase 9 U3 fix round 1). `Toaster` (`__root.tsx`)
 * dùng `position="top-center"` — không đè lên ô soạn câu hỏi ở cuối cột chat
 * nữa (`bottom-right` cũ từng phủ đúng nút gửi). Nhưng `top-center` với
 * `offset` mặc định của sonner (24px, xem `assignOffset`/`VIEWPORT_OFFSET`
 * trong `node_modules/sonner`) lại nằm NGAY TRONG header dính đỉnh của
 * `AppShell` (`sticky top-0`, chứa nút "Phiên"/CTA khách) — đo trực tiếp trên
 * trang: header cao 57–69px tại `/dung-thu`, toast mặc định bắt đầu ở 24px
 * từ mép trên, tức chồng lấn ~35–45px vào chính giữa header.
 *
 * `TOAST_OFFSET_TREN` đẩy toast xuống dưới header thay vì chỉ đổi z-index —
 * chồng z-index vẫn để một cú bấm vào nút header bị toast nuốt mất trong lúc
 * toast còn hiện, đúng lỗi U3 ban đầu lặp lại ở một góc khác.
 */
export const CHIEU_CAO_HEADER_DO_DUOC = 69;
/** Chiều cao một toast một dòng, đo trực tiếp (`getBoundingClientRect().height`
 *  của `[data-sonner-toast]`) — sonner neo CẠNH DƯỚI của toast vào `offset.top`
 *  cho vị trí `top-*` (toast "mọc lên" từ đó, không phải cạnh TRÊN nằm ở
 *  `offset.top` như tên gọi khiến người đọc tưởng) nên cạnh trên thật của nó
 *  là `offset.top - CHIEU_CAO_TOAST_MOT_DONG`, không phải `offset.top`. */
export const CHIEU_CAO_TOAST_MOT_DONG = 54;
/** Phải LỚN HƠN `CHIEU_CAO_HEADER_DO_DUOC + CHIEU_CAO_TOAST_MOT_DONG` — biên
 *  an toàn cho các trạng thái header chưa đo tới (ví dụ khách + CTA rộng hơn
 *  nút "Phiên"), và cho một toast dài quấn sang dòng thứ hai. */
export const TOAST_OFFSET_TREN = 140;
