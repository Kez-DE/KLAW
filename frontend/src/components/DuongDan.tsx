import { Fragment } from 'react';

interface DuongDanProps {
  /** "45/2019/QH14 > Điều 127 > Khoản 2" — một địa chỉ, không phải văn xuôi. */
  duongDan?: string;
  /** ĐỊNH DANH văn bản. Hiển thị cái này — không bao giờ hiển thị title/tên. */
  soKyHieu?: string;
  /** Tên đầy đủ để người đọc nhận ra văn bản; luôn đi kèm, không thay thế
   *  `soKyHieu`. */
  boLuat?: string;
  /** true khi địa chỉ nằm TRÊN mặt phim (nền sáng) thay vì trên mặt máy. */
  trenPhim?: boolean;
  className?: string;
}

/**
 * Số hiệu và đường dẫn trích dẫn hiển thị bằng font địa chỉ (mono): người dùng
 * cần quét và so từng ký tự, đây không phải văn xuôi (DESIGN.md).
 */
export function DuongDan({
  duongDan,
  soKyHieu,
  boLuat,
  trenPhim = false,
  className = '',
}: DuongDanProps) {
  // `duong_dan` mở đầu bằng chính `so_ky_hieu`. Khi hiện cả hai, bỏ đoạn đầu
  // của đường dẫn: định danh đã nằm ngay trên, lặp lại chỉ làm địa chỉ khó quét.
  const doanDayDu = duongDan ? duongDan.split(' > ') : [];
  const doan =
    soKyHieu !== undefined && doanDayDu[0] === soKyHieu ? doanDayDu.slice(1) : doanDayDu;
  const mauChinh = trenPhim ? 'var(--muc)' : 'var(--phim)';
  const mauPhu = trenPhim ? 'color-mix(in srgb, var(--muc) 62%, transparent)' : 'var(--muc-nhat)';

  return (
    <span className={`block min-w-0 ${className}`}>
      {soKyHieu !== undefined && (
        <span
          className="dia-chi block text-[0.8125rem] leading-5 font-medium break-all"
          style={{ color: mauChinh }}
        >
          {soKyHieu}
        </span>
      )}
      {duongDan !== undefined && doan.length > 0 && (
        <span
          className="dia-chi block text-[0.75rem] leading-5 break-words"
          style={{ color: mauPhu }}
        >
          {doan.map((phan, i) => (
            <Fragment key={`${phan}-${i}`}>
              {i > 0 && <span> {'>'} </span>}
              {phan}
            </Fragment>
          ))}
        </span>
      )}
      {boLuat !== undefined && boLuat !== '' && (
        <span className="mt-1 block text-[0.75rem] leading-5" style={{ color: mauPhu }}>
          {boLuat}
        </span>
      )}
    </span>
  );
}
