import type { ReactNode } from 'react';

/**
 * Khối lưu ý — viền khung mảnh, KHÔNG phải vệt viền một bên.
 *
 * Detector của impeccable đếm được **11** chỗ dùng `border-s-2` và gọi đúng tên
 * nó: *"thick colored border on one side of a card — the most recognizable tell
 * of AI-generated UIs"*. Sáu chỗ trong đó giữ nguyên, vì ở `ResultCard` và
 * `BaoCaoSoat` vệt viền **mang trạng thái** — nó là một trong hai kênh của bất
 * biến "không trạng thái nào được truyền đạt chỉ bằng màu", gỡ nó là làm yếu
 * phần truyền đạt.
 *
 * Năm chỗ còn lại là lưu ý, và ba trong số đó còn mượn **đúng màu `--vang-mo`
 * và đúng kiểu viền** của `partial_coverage` cho câu "loại văn bản này chưa có
 * nội dung pháp lý". Hai nghĩa khác nhau dùng chung một hình: người dùng học
 * được rằng vệt vàng bên trái nghĩa là "phủ một phần", rồi gặp cùng hình đó nói
 * một chuyện hoàn toàn khác.
 *
 * Nên lưu ý mang hình của thế giới máy đọc vi phim: **khung phim** — viền mảnh
 * bao quanh — chứ không phải vệt đèn rọi một bên. Đổi lại, vệt viền còn lại có
 * nghĩa hơn vì nó thôi lặp khắp nơi.
 */
interface Props {
  children: ReactNode;
  className?: string;
  /**
   * Lưu ý cần nổi bật (ví dụ "Giá dự kiến, chưa áp dụng" ở `/bang-gia`) — viền
   * brass **bao quanh**, không phải vệt brass một bên. Vẫn hút mắt vì brass là
   * accent duy nhất của bảng màu; chỉ khác là nó không mượn hình của trạng thái.
   */
  nhanManh?: boolean;
  /** `role="note"` khi khối này là một lưu ý độc lập, không phải phần thân. */
  role?: string;
}

export function KhoiLuuY({ children, className = '', nhanManh = false, role }: Props) {
  return (
    <div
      role={role}
      className={`rounded-lon border p-4 ${className}`}
      style={{
        borderColor: nhanManh ? 'var(--den-sang)' : 'var(--vien)',
        background: 'var(--nen-cao)',
      }}
    >
      {children}
    </div>
  );
}
