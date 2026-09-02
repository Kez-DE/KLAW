import { useId } from 'react';
import type { ReactNode } from 'react';

/**
 * Bộ biểu tượng KLAW (DESIGN.md § "Bộ biểu tượng").
 *
 * Nét đồng nhất 1.5 ở lưới 24, ĐẦU NÉT VUÔNG và mối nối nhọn — cùng họ với khung
 * phim, không phải biểu tượng bo tròn mềm. SVG inline tự vẽ, KHÔNG thư viện icon:
 * người lao động dùng mạng yếu, và một bộ icon đầy đủ tốn hơn số icon thật dùng.
 *
 * Đúng bộ trong `brand-contract.md`, không thêm biểu tượng dự phòng cho tương lai.
 *
 * RÀNG BUỘC SẢN PHẨM, không phải thẩm mỹ:
 *   - Bộ này CỐ Ý KHÔNG CÓ biểu tượng cảnh báo, lỗi, hay hiệu lực. Không phải quên.
 *     `abstain` ("không tìm thấy căn cứ") là hành vi ĐÚNG và không được mang hình
 *     cảnh báo; không có hình cảnh báo trong bộ thì không ai dán nhầm được.
 *   - DESIGN.md đo được `--do-thay` và `--xam-cho` gần như cùng độ sáng (1,07:1),
 *     nên nhãn hiệu lực phải phân biệt bằng CHỮ và HÌNH, không bao giờ chỉ bằng màu.
 *     Nhãn hiệu lực vì vậy không phải là icon — nó là chấm + câu chữ, dựng ở chỗ khác.
 *   - `aria-hidden="true"` cố định, không mở cho caller đổi: biểu tượng ở đây không
 *     bao giờ đứng một mình, nhãn luôn nằm ở phần tử cha.
 */

interface PropsBieuTuong {
  size?: number;
  className?: string;
}

function KhungSvg({
  size = 24,
  className,
  children,
}: PropsBieuTuong & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="square"
      strokeLinejoin="miter"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

/** Tra cứu — kính lúp có THẤU KÍNH HÌNH KHUNG PHIM, không phải vòng tròn. */
export function IconTraCuu(props: PropsBieuTuong) {
  return (
    <KhungSvg {...props}>
      <rect x="3" y="3" width="13" height="13" rx="2.5" />
      <path d="M15.3 15.3 20.5 20.5" />
    </KhungSvg>
  );
}

/** Soạn thảo — tờ văn bản đang được viết: dòng cuối ngắn, còn con trỏ nhấp nháy. */
export function IconSoanThao(props: PropsBieuTuong) {
  return (
    <KhungSvg {...props}>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M7.5 8H16.5" />
      <path d="M7.5 12H16.5" />
      <path d="M7.5 16H12" />
      <path d="M13.8 14.2V17.8" />
    </KhungSvg>
  );
}

/** Soát — tờ văn bản đi qua VẠCH QUÉT của máy. Không dùng dấu tích: soát trả về
    phát hiện, không trả về lời khen, và một dấu tích dễ bị đọc thành "đạt". */
export function IconSoat(props: PropsBieuTuong) {
  return (
    <KhungSvg {...props}>
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M7.5 8H16.5" />
      <path d="M7.5 16H16.5" />
      <path d="M2 12H22" />
    </KhungSvg>
  );
}

/** Khung phim — vật thể trung tâm của sản phẩm: một ô trích dẫn. Cùng hình học
    với mã nhãn nhưng KHÔNG có đèn; đèn là thứ chỉ mã nhãn được mang. */
export function IconKhungPhim({ size = 24, className }: PropsBieuTuong) {
  const idKhia = `klaw-khia-icon-${useId().replace(/:/g, '')}`;
  return (
    <KhungSvg size={size} className={className}>
      <defs>
        <mask id={idKhia} maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24">
          <rect width="24" height="24" fill="#fff" />
          <rect x="2.5" y="8.4" width="3" height="2.4" rx="0.6" fill="#000" />
          <rect x="2.5" y="13.2" width="3" height="2.4" rx="0.6" fill="#000" />
          <rect x="18.5" y="8.4" width="3" height="2.4" rx="0.6" fill="#000" />
          <rect x="18.5" y="13.2" width="3" height="2.4" rx="0.6" fill="#000" />
        </mask>
      </defs>
      <rect x="4" y="4" width="16" height="16" rx="3" mask={`url(#${idKhia})`} />
    </KhungSvg>
  );
}

/** Mở rộng — bốn góc ngắm bung ra, đúng động tác "mở khung ra toàn màn hình". */
export function IconMoRong(props: PropsBieuTuong) {
  return (
    <KhungSvg {...props}>
      <path d="M4 9V4h5" />
      <path d="M15 4h5v5" />
      <path d="M20 15v5h-5" />
      <path d="M9 20H4v-5" />
    </KhungSvg>
  );
}

/** Đóng. */
export function IconDong(props: PropsBieuTuong) {
  return (
    <KhungSvg {...props}>
      <path d="M5.5 5.5 18.5 18.5" />
      <path d="M18.5 5.5 5.5 18.5" />
    </KhungSvg>
  );
}

/** Chép lại — dùng cho `so_ky_hieu` và đường dẫn trích dẫn, thứ người ta cần
    dán nguyên vẹn sang chỗ khác. */
export function IconChepLai(props: PropsBieuTuong) {
  return (
    <KhungSvg {...props}>
      <rect x="3" y="8" width="13" height="13" rx="2.5" />
      <path d="M8 8V5.5A2.5 2.5 0 0 1 10.5 3h8A2.5 2.5 0 0 1 21 5.5v8a2.5 2.5 0 0 1-2.5 2.5H16" />
    </KhungSvg>
  );
}

/** Mũi tên phải — "tiến tới khung": đi tới nguyên văn điều luật. */
export function IconMuiTenPhai(props: PropsBieuTuong) {
  return (
    <KhungSvg {...props}>
      <path d="M3.5 12H19.5" />
      <path d="M13.5 6 19.5 12 13.5 18" />
    </KhungSvg>
  );
}

/** Mục lục — cây điều khoản của một văn bản. */
export function IconMucLuc(props: PropsBieuTuong) {
  return (
    <KhungSvg {...props}>
      <path d="M3.5 6.5H6" />
      <path d="M9 6.5H20.5" />
      <path d="M3.5 12H6" />
      <path d="M9 12H20.5" />
      <path d="M3.5 17.5H6" />
      <path d="M9 17.5H20.5" />
    </KhungSvg>
  );
}

/** Đèn máy — sự hiện diện của trợ lý: một VÒNG SÁNG quanh lỗ đèn, thở nhẹ khi
    rảnh. Không mặt người, không nhân vật hoạt hình, không tia lửa AI. */
export function IconDenMay(props: PropsBieuTuong) {
  return (
    <KhungSvg {...props}>
      <circle cx="12" cy="12" r="8.25" />
      <circle cx="12" cy="12" r="3" />
    </KhungSvg>
  );
}

/**
 * Dấu tích — CHỈ dùng cho phản hồi "biểu mẫu đã gửi xong" trên hai tuyến xác
 * thực (BUILD-SPEC §9.2 yêu cầu một dấu tích brass ở trạng thái thành công).
 *
 * GIỚI HẠN SỬ DỤNG, đọc trước khi tái dùng: biểu tượng này KHÔNG BAO GIỜ được
 * dùng cho hiệu lực văn bản, cho kết quả soát, hay cho bất cứ thứ gì có thể bị
 * đọc thành "văn bản này đạt". Đó chính là lý do `IconSoat` cố ý không có dấu
 * tích. Ở đây nó chỉ nói một việc rất nhỏ: cú bấm gửi đã được ghi nhận.
 */
export function IconDaXong(props: PropsBieuTuong) {
  return (
    <KhungSvg {...props}>
      <path d="M4.5 12.5 9.5 17.5 19.5 6.5" />
    </KhungSvg>
  );
}
