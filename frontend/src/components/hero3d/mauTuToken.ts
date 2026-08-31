import { Color } from 'three';

/**
 * Cầu nối bảng màu: đọc token CSS → `THREE.Color`.
 *
 * DESIGN.md § Bảng màu: "Tên biến là hợp đồng FE" — mã nguồn gọi màu theo TÊN,
 * không gõ hex. WebGL thì cần số, nên chỗ duy nhất trong cảnh 3D được biết giá
 * trị thật là hàm này, và nó lấy giá trị từ chính `tokens.css` lúc chạy. Đổi
 * bảng màu ở tokens.css là cảnh 3D đổi theo, không phải đi sửa hai nơi.
 *
 * `KLAW-BUILD-SPEC` §10.1 viết bốn màu bằng hex. Ánh xạ sang token theo VAI,
 * ghi ra đây để lần sau không ai phải đoán:
 *
 *   spec #0F1F38 (thân phiến kính khói) → `--vien`      #14294A
 *       Không có token nào bằng đúng #0F1F38. `--vien` là bậc ink sáng nhất
 *       ("cạnh khay") và là token duy nhất đủ sáng để phiến còn tách được khỏi
 *       nền `--nen`; `--nen-cao` thì phiến gần như tan vào nền.
 *   spec #C8A45C (viền brass)           → `--den-sang`  khớp chính xác
 *   spec #FFE9C2 (key sáng ấm)          → `--phim`
 *       DESIGN.md: "ánh sáng là thứ rọi qua phim" — màu của ánh sáng trong thế
 *       giới này LÀ màu mặt phim, nên key light lấy `--phim`.
 *   spec #4A6FA5 (rim lạnh)             → `--muc-nhat`  #A3AFC2
 *       Token lạnh, khử bão hoà, vốn đã dành cho "trên nền tối".
 *
 * `getComputedStyle` gọi MỘT LẦN mỗi lần mount cảnh (trong `useMemo`), không
 * phải mỗi frame — đọc computed style là đồng bộ với layout, gọi trong vòng
 * render là tự tạo một reflow mỗi frame.
 */
export type TenToken = '--nen' | '--nen-cao' | '--vien' | '--phim' | '--muc-nhat' | '--den-sang';

export function docMau(ten: TenToken): Color {
  const gia = getComputedStyle(document.documentElement).getPropertyValue(ten).trim();
  // Token thiếu (CSS chưa nạp, hoặc ai đó đổi tên biến) → không im lặng vẽ đen.
  // `Color` mặc định trắng; nền tối nên trắng là thứ nhìn thấy ngay, khác hẳn
  // một phiến đen trên nền đen mà không ai phát hiện.
  if (gia === '') {
    console.warn(`[hero3d] token ${ten} rỗng — kiểm tra styles/tokens.css`);
    return new Color(0xffffff);
  }
  return new Color().setStyle(gia);
}
