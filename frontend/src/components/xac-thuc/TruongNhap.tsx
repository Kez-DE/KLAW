import type { ReactNode } from 'react';

/**
 * Một trường nhập của biểu mẫu xác thực: nhãn, ô nhập, lỗi inline, và dây nối
 * `aria-describedby` giữa chúng.
 *
 * Tồn tại vì có SÁU trường trên hai tuyến, và phần dễ quên nhất không phải
 * giao diện mà là dây nối: một thông báo lỗi hiện trên màn hình nhưng không
 * được `aria-describedby` trỏ tới là một lỗi mà người dùng trình đọc màn hình
 * KHÔNG BAO GIỜ nghe thấy. Gom vào một chỗ thì nó không thể lệch giữa các
 * trường.
 *
 * `aria-invalid` và `aria-describedby` đi cùng nhau, và không có đường nào
 * dựng ô nhập mà bỏ qua chúng.
 */

interface TruongNhapProps {
  id: string;
  nhan: string;
  loai?: 'text' | 'email' | 'password';
  giaTri: string;
  doiGiaTri: (gia: string) => void;
  /** null = chưa có lỗi. Chuỗi = hiện ngay dưới ô nhập, tiếng Việt. */
  loi?: string | null;
  batBuoc?: boolean;
  tuDong?: string;
  /** Ghi chú dưới nhãn (ví dụ "không bắt buộc"), cũng nằm trong vùng mô tả. */
  moTa?: string;
  /** Thanh đo mật khẩu — hiển thị dưới ô nhập và được `aria-describedby` trỏ tới. */
  children?: ReactNode;
}

const O_NHAP =
  'mat-doc min-h-[var(--vung-cham-toi-thieu)] w-full max-w-none rounded-vua border bg-nen p-3 text-phim placeholder:text-muc-nhat focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang';

export function TruongNhap({
  id,
  nhan,
  loai = 'text',
  giaTri,
  doiGiaTri,
  loi = null,
  batBuoc = false,
  tuDong,
  moTa,
  children,
}: TruongNhapProps) {
  const idLoi = `${id}-loi`;
  const idMoTa = `${id}-mo-ta`;
  const idThem = `${id}-them`;

  const vungMoTa = [
    moTa !== undefined ? idMoTa : null,
    children !== undefined ? idThem : null,
    loi !== null ? idLoi : null,
  ]
    .filter((x): x is string => x !== null)
    .join(' ');

  return (
    <div>
      <label htmlFor={id} className="mat-doc block max-w-none text-[0.9375rem] font-medium text-phim">
        {nhan}
        {batBuoc && (
          <span aria-hidden="true" className="ms-1 text-den-sang">
            *
          </span>
        )}
      </label>
      {moTa !== undefined && (
        <p id={idMoTa} className="mt-1 mb-0 text-[0.8125rem] leading-5 text-muc-nhat">
          {moTa}
        </p>
      )}
      <input
        id={id}
        name={id}
        type={loai}
        value={giaTri}
        onChange={(su) => doiGiaTri(su.target.value)}
        required={batBuoc}
        autoComplete={tuDong}
        aria-invalid={loi !== null}
        aria-describedby={vungMoTa === '' ? undefined : vungMoTa}
        className={O_NHAP}
        style={{
          borderColor:
            loi === null
              ? 'color-mix(in srgb, var(--muc-nhat) 55%, transparent)'
              : 'var(--do-thay)',
        }}
      />
      {children !== undefined && <div id={idThem}>{children}</div>}
      {/* Lỗi nói bằng CHỮ, không chỉ bằng viền đỏ — DESIGN.md đo được
          `--do-thay` và `--xam-cho` gần như cùng độ sáng, nên không trạng thái
          nào được truyền đạt chỉ bằng màu. */}
      {loi !== null && (
        <p id={idLoi} className="mt-1.5 mb-0 text-[0.8125rem] leading-5 text-do-thay">
          {loi}
        </p>
      )}
    </div>
  );
}
