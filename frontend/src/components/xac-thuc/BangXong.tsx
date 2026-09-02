import { Link } from 'react-router-dom';
import { IconDaXong } from '../../brand/icons';

/**
 * Trạng thái "đã gửi xong" của hai biểu mẫu xác thực.
 *
 * Nói ĐÚNG những gì đã xảy ra, và không hơn: cú bấm đã được ghi nhận, và
 * KHÔNG có tài khoản hay phiên đăng nhập nào được tạo — vì chưa có backend
 * xác thực nào để tạo (BUILD-SPEC §14.2). Một bảng "Đăng nhập thành công!"
 * ở đây sẽ là câu nói sai đúng nghĩa, trên đúng trang mà người dùng có lý do
 * để tin.
 *
 * KHÔNG tự chuyển tuyến. Spec §9.2 nêu `router.push('/dung-thu')` sau khi
 * thành công, nhưng KLAW dùng được mà không cần tài khoản, nên không có gì
 * phải "vào" — và một cú chuyển trang tự động sau 1,2 giây thì người dùng bàn
 * phím lẫn người đọc chậm đều không kịp đọc dòng ở trên. Lối vào là một liên
 * kết người dùng tự bấm (WCAG 3.2.5).
 */

export function BangXong({ cau }: { cau: string }) {
  return (
    <div
      role="status"
      className="mt-6 rounded-lon border p-5"
      style={{ background: 'var(--nen)', borderColor: 'var(--vien)' }}
    >
      <span
        className="flex size-10 items-center justify-center rounded-tron"
        style={{
          background:
            'radial-gradient(circle, color-mix(in srgb, var(--den-sang) 26%, transparent), transparent 72%)',
          color: 'var(--den-sang)',
        }}
      >
        <IconDaXong size={22} />
      </span>
      <p className="mat-doc mt-3 max-w-none font-medium text-phim">{cau}</p>
      <p className="mat-doc mt-2 max-w-none text-[0.9375rem] text-muc-nhat">
        Chưa có tài khoản nào được tạo và chưa có phiên đăng nhập nào được mở: backend xác thực
        chưa được nối. KLAW hiện dùng được ngay, không cần tài khoản.
      </p>
      <Link
        to="/tra-cuu"
        className="mt-4 inline-flex min-h-[var(--vung-cham-toi-thieu)] items-center rounded-vua px-4 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
      >
        Vào tra cứu
      </Link>
    </div>
  );
}
