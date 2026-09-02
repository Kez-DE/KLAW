import type { ButtonHTMLAttributes, ReactNode } from 'react';

/**
 * Nút hành động chính — nền `--den-sang` (brass), chữ `--muc`.
 *
 * Trước component này, đúng một chuỗi className 200 ký tự được chép ở NĂM
 * file (`TraCuu`, `SoanThao`, `Soat`, `VanBan`, `DangKy`). Vòng thẩm định bảng
 * màu đo được `disabled:opacity-45` tụt từ 3,00:1 xuống 2,33:1 sau khi đổi
 * sang brass — không vi phạm WCAG (1.4.3 miễn trừ thành phần không hoạt động)
 * nhưng là bước lùi đo được. Sửa năm bản chép là năm cơ hội bỏ sót một; gom
 * lại thì lần sau chỉnh độ mờ là chỉnh một dòng.
 *
 * `opacity-60` cho 3,26:1 — vẫn đọc được là "đang tắt", nhưng đọc được.
 */
export function NutBrass({
  children,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  return (
    <button
      className={`min-h-[var(--vung-cham-toi-thieu)] cursor-pointer rounded-vua px-5 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
      style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
      {...props}
    >
      {children}
    </button>
  );
}
