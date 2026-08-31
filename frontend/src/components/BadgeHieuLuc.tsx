import type { HieuLuc } from '../types';

/**
 * Nhãn hiệu lực của một trích dẫn. LUÔN THẤY ĐƯỢC — không bao giờ nằm trong
 * tooltip hay metadata (fe-contract.md).
 *
 * Đỏ (`--do-thay`) dành riêng cho luật đã bị thay thế: đó mới là thứ khiến
 * người dùng hành động sai. Không dùng đỏ cho bất cứ trạng thái nào khác.
 */

type KieuNhan = 'cham' | 'vien';

interface Nhan {
  kieu: KieuNhan;
  mau: string;
  /** Chữ hiển thị; rỗng nghĩa là chỉ một chấm màu (kèm nhãn cho trình đọc). */
  chu: string;
  /** Luôn đọc được bằng trình đọc màn hình, kể cả khi chỉ hiện chấm. */
  nhanDayDu: string;
}

// Switch trên `string` chứ không trên union: type guard ở lib/api.ts chỉ bảo
// đảm `string | null`, nên một nhãn backend thêm sau phải rơi vào nhánh
// default một cách an toàn thay vì làm sập cả thẻ.
function docNhan(hieuLuc: string): Nhan {
  switch (hieuLuc) {
    case 'con_hieu_luc':
      return { kieu: 'cham', mau: 'var(--xanh-that)', chu: '', nhanDayDu: 'Còn hiệu lực' };
    case 'bi_thay_the':
      return {
        kieu: 'vien',
        mau: 'var(--do-thay)',
        chu: 'Đã bị thay thế',
        nhanDayDu: 'Đã bị thay thế',
      };
    case 'het_hieu_luc':
      return {
        kieu: 'vien',
        mau: 'var(--do-thay)',
        chu: 'Hết hiệu lực',
        nhanDayDu: 'Hết hiệu lực',
      };
    case 'mot_phan_khong_xac_dinh':
      return {
        kieu: 'vien',
        mau: 'var(--vang-mo)',
        chu: 'Một phần không xác định',
        nhanDayDu: 'Một phần không xác định',
      };
    case 'can_doi_chieu_tay':
      return {
        kieu: 'cham',
        mau: 'var(--xam-cho)',
        chu: 'Cần đối chiếu tay',
        nhanDayDu: 'Cần đối chiếu tay',
      };
    default:
      return { kieu: 'cham', mau: 'var(--xam-cho)', chu: hieuLuc, nhanDayDu: hieuLuc };
  }
}

const GIAI_THICH: Record<string, string | undefined> = {
  mot_phan_khong_xac_dinh: 'CSDL quốc gia không công bố dữ liệu cấp điều khoản',
};

interface BadgeHieuLucProps {
  hieuLuc: HieuLuc | null;
  /** Câu nêu ĐÍCH DANH văn bản thay thế, lấy từ `warnings[]` của cùng văn bản.
   *  Hiện ngay dưới nhãn, không giấu vào tooltip. */
  ghiChu?: string;
}

export function BadgeHieuLuc({ hieuLuc, ghiChu }: BadgeHieuLucProps) {
  if (hieuLuc === null) return null;
  const nhan = docNhan(hieuLuc);
  const giaiThich = GIAI_THICH[hieuLuc];

  return (
    <span className="block">
      <span
        className="inline-flex min-h-6 items-center gap-1.5 rounded-tron px-2 py-0.5 text-[0.75rem] leading-5"
        style={
          nhan.kieu === 'vien'
            ? { border: `1px solid ${nhan.mau}`, color: nhan.mau }
            : { color: 'var(--muc-nhat)' }
        }
      >
        <span
          aria-hidden="true"
          className="size-2 shrink-0 rounded-tron"
          style={{ background: nhan.mau }}
        />
        {nhan.chu === '' ? (
          <span className="sr-only">{nhan.nhanDayDu}</span>
        ) : (
          <span>{nhan.chu}</span>
        )}
      </span>
      {giaiThich !== undefined && (
        <span className="mt-1 block text-[0.75rem] leading-5 text-muc-nhat">{giaiThich}</span>
      )}
      {ghiChu !== undefined && ghiChu !== '' && (
        <span className="mt-1 block text-[0.75rem] leading-5" style={{ color: 'var(--do-thay)' }}>
          {ghiChu}
        </span>
      )}
    </span>
  );
}
