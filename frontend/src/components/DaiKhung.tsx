import { useCallback, useRef } from 'react';
import type { KeyboardEvent } from 'react';
import type { Citation } from '../types';
import { canhBaoChoVanBan } from '../lib/trichDan';
import { CitationChip } from './CitationChip';

interface DaiKhungProps {
  citations: Citation[];
  /** Khung đang mở trong khung rọi sáng, hoặc null. */
  chiSoDangMo: number | null;
  onChon: (chiSo: number) => void;
  /** `warnings[]` của phản hồi — dùng để gắn câu nêu đích danh văn bản thay
   *  thế vào đúng khung. Khối cảnh báo chung vẫn hiện đủ, không lọc bớt. */
  warnings?: string[];
}

/**
 * Câu nêu ĐÍCH DANH văn bản thay thế chỉ gắn vào khung khi nhãn hiệu lực là
 * "đã bị thay thế"/"hết hiệu lực" — đó là trường hợp badge một mình không nói
 * được thay bằng văn bản nào. Các nhãn khác đã có câu giải thích cố định của
 * riêng chúng, gắn thêm chỉ lặp lại nguyên văn khối cảnh báo chung ngay phía
 * trên. Không có cảnh báo nào bị giấu: khối chung vẫn hiện đủ `warnings[]`.
 */
function ghiChuThayThe(citation: Citation, warnings: string[]): string | undefined {
  if (citation.hieu_luc !== 'bi_thay_the' && citation.hieu_luc !== 'het_hieu_luc') return undefined;
  return canhBaoChoVanBan(warnings, citation.so_ky_hieu)[0];
}

/**
 * Dải khung phim: cuộn ngang, snap từng khung vào giữa, khung ở tâm phồng lên
 * bằng scroll-driven animation thuần CSS (xem styles/may-doc.css).
 *
 * Bàn phím: mọi khung đều tab tới được; thêm mũi tên trái/phải và Home/End để
 * đi dọc dải mà không phải tab qua từng khung.
 */
export function DaiKhung({ citations, chiSoDangMo, onChon, warnings = [] }: DaiKhungProps) {
  const dai = useRef<HTMLUListElement>(null);

  const dieuHuongBangPhim = useCallback((su: KeyboardEvent<HTMLUListElement>) => {
    const nut = Array.from(dai.current?.querySelectorAll<HTMLButtonElement>('[data-khung]') ?? []);
    if (nut.length === 0) return;
    const hienTai = Math.max(
      0,
      nut.findIndex((moiNut) => moiNut === document.activeElement),
    );

    let dich: number;
    switch (su.key) {
      case 'ArrowRight':
        dich = Math.min(nut.length - 1, hienTai + 1);
        break;
      case 'ArrowLeft':
        dich = Math.max(0, hienTai - 1);
        break;
      case 'Home':
        dich = 0;
        break;
      case 'End':
        dich = nut.length - 1;
        break;
      default:
        return;
    }

    su.preventDefault();
    nut[dich].focus();
  }, []);

  if (citations.length === 0) return null;

  return (
    <section aria-labelledby="nhan-dai-khung" className="mt-6">
      <h3 id="nhan-dai-khung" className="mb-2 text-[0.8125rem] leading-5 text-muc-nhat">
        Căn cứ pháp lý — {citations.length} trích dẫn. Bấm một khung để mở nguyên văn.
      </h3>
      <ul ref={dai} className="dai-khung m-0 list-none" onKeyDown={dieuHuongBangPhim}>
        {citations.map((citation, chiSo) => (
          <CitationChip
            key={`${citation.doc_id}-${citation.khop_tai_id}-${chiSo}`}
            citation={citation}
            chiSo={chiSo}
            dangMo={chiSo === chiSoDangMo}
            onChon={onChon}
            ghiChuHieuLuc={ghiChuThayThe(citation, warnings)}
          />
        ))}
      </ul>
    </section>
  );
}
