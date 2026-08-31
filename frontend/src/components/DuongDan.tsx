import { dinhDangTrichDan, soKyHieuTuDuongDan } from '../lib/trichDanVN';

interface DuongDanProps {
  /** "45/2019/QH14 > Điều 127 > Khoản 2" — địa chỉ thô từ DB, chiều lớn → nhỏ. */
  duongDan?: string;
  /** ĐỊNH DANH văn bản. Khi không truyền, lấy lại từ đoạn đầu `duongDan`. */
  soKyHieu?: string;
  /** `documents.ten` NGUYÊN VĂN; vào chuỗi trích dẫn qua `lib/trichDanVN.ts`. */
  boLuat?: string;
  /** true khi địa chỉ nằm TRÊN mặt phim (nền sáng) thay vì trên mặt máy. */
  trenPhim?: boolean;
  className?: string;
}

/**
 * Trích dẫn một điều khoản, theo thứ tự tiếng Việt (§6.2):
 *
 *   Khoản 2 Điều 127 Bộ Luật lao động 2019
 *   45/2019/QH14
 *
 * Dòng trên là VĂN XUÔI: người đọc Việt đọc trích dẫn từ đơn vị nhỏ nhất tới
 * lớn nhất, nên đó là một câu chứ không phải một địa chỉ máy — vì vậy không còn
 * dùng font mono cho nó.
 *
 * Dòng dưới giữ font địa chỉ (mono): `so_ky_hieu` là khoá định danh DUY NHẤT
 * của văn bản, thứ người dùng phải quét và so từng ký tự để tra lại. Nó không
 * bao giờ được biến mất — kể cả ở những chỗ chỉ truyền `duongDan` (Soát, Soạn
 * thảo), nơi nó được lấy lại từ đoạn đầu đường dẫn.
 *
 * MỌI trích dẫn trong sản phẩm đi qua component này. Đổi dạng hiển thị thì sửa
 * ở đây và trong `lib/trichDanVN.ts`, không rải ra từng trang.
 */
export function DuongDan({
  duongDan,
  soKyHieu,
  boLuat,
  trenPhim = false,
  className = '',
}: DuongDanProps) {
  const duong = duongDan ?? '';
  const soHieu = soKyHieu ?? soKyHieuTuDuongDan(duong);
  const trichDan = dinhDangTrichDan(duong, soHieu, boLuat ?? '');

  const mauChinh = trenPhim ? 'var(--muc)' : 'var(--phim)';
  const mauPhu = trenPhim ? 'color-mix(in srgb, var(--muc) 62%, transparent)' : 'var(--muc-nhat)';

  return (
    <span className={`block min-w-0 ${className}`}>
      {trichDan !== '' && (
        <span
          className="block text-[0.8125rem] leading-5 font-medium break-words"
          style={{ color: mauChinh }}
        >
          {trichDan}
        </span>
      )}
      {soHieu !== '' && (
        <span
          className="dia-chi mt-0.5 block text-[0.75rem] leading-5 break-all"
          style={{ color: mauPhu }}
        >
          {soHieu}
        </span>
      )}
    </span>
  );
}
