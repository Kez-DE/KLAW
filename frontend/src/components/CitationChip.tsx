import type { Citation } from '../types';
import { BadgeHieuLuc } from './BadgeHieuLuc';
import { DuongDan } from './DuongDan';

interface CitationChipProps {
  citation: Citation;
  /** Vị trí trong dải khung — cũng là số khung phim in trên mép. */
  chiSo: number;
  dangMo: boolean;
  onChon: (chiSo: number) => void;
  /** Câu cảnh báo nêu đích danh văn bản thay thế, nếu có. */
  ghiChuHieuLuc?: string;
}

/**
 * Một khung phim trong dải: câu trích in trên mặt phim, địa chỉ và nhãn hiệu
 * lực ở mép khung. Bấm vào = tiến tới khung đó và rọi sáng nguyên văn.
 *
 * `data-khung` là móc để lib/chuyenCanh.ts gán `view-transition-name` đúng lúc
 * — đừng đổi tên thuộc tính này mà không sửa file đó.
 */
export function CitationChip({
  citation,
  chiSo,
  dangMo,
  onChon,
  ghiChuHieuLuc,
}: CitationChipProps) {
  return (
    <li className="khung list-none" data-dang-mo={dangMo ? 'true' : 'false'}>
      <button
        type="button"
        data-khung={chiSo}
        aria-pressed={dangMo}
        onClick={() => onChon(chiSo)}
        className="mat-phim flex h-full w-[17rem] cursor-pointer flex-col gap-2 rounded-vua border p-3 text-left shadow-noi-2 transition-[border-color,box-shadow] duration-[var(--thoi-luong-nhanh)] ease-chuan focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang sm:w-[20rem]"
        style={{
          background: 'var(--nen-cao)',
          borderColor: dangMo ? 'var(--den-sang)' : 'color-mix(in srgb, var(--muc-nhat) 45%, transparent)',
          boxShadow: dangMo ? 'var(--shadow-tieu-diem)' : undefined,
        }}
      >
        <span className="flex items-start justify-between gap-2">
          <DuongDan
            soKyHieu={citation.so_ky_hieu}
            duongDan={citation.duong_dan}
            className="min-w-0 flex-1"
          />
          <span
            aria-hidden="true"
            className="dia-chi shrink-0 rounded-nho px-1.5 py-0.5 text-[0.6875rem] leading-4 text-muc-nhat"
            style={{ border: '1px solid color-mix(in srgb, var(--muc-nhat) 45%, transparent)' }}
          >
            {chiSo + 1}
          </span>
        </span>

        {/* Mặt phim: nền sáng, chữ serif, màu chữ KHÔNG đổi theo trạng thái. */}
        <span
          className="chu-tren-phim block rounded-nho p-2.5 text-[0.9375rem] leading-[1.6]"
          style={{ background: 'var(--phim)' }}
        >
          {citation.quote}
        </span>

        <BadgeHieuLuc hieuLuc={citation.hieu_luc} ghiChu={ghiChuHieuLuc} />

        <span className="mt-auto text-[0.75rem] leading-5 text-den-sang">
          {dangMo ? 'Đang xem nguyên văn' : 'Mở nguyên văn'}
        </span>
      </button>
    </li>
  );
}
