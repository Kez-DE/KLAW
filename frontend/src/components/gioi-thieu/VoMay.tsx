import type { ReactNode } from 'react';

/**
 * Vỏ máy — cái khay có viền, bo góc và tấm nền phía sau, KHÔNG có nội dung.
 *
 * Tồn tại để làm `fallback` của `Suspense` trong lúc chunk `three` đang tải:
 * nó dùng đúng `.gt-khay` của cỗ máy CSS, tức đúng `min-height` (22rem, 25rem
 * từ 768px), nên khi cảnh 3D vào chỗ KHÔNG có dịch chuyển bố cục — yêu cầu
 * §10.4. Cùng lý do, nó không được có nội dung riêng: một placeholder có chữ là
 * một placeholder người dùng thấy nhấp nháy.
 */
export function VoMay({ children }: { children?: ReactNode }) {
  return (
    <div className="gt-khay">
      <div className="h3-nen" aria-hidden="true" />
      {children}
    </div>
  );
}
