import { useCallback, useEffect, useRef } from 'react';
import type { KeyboardEvent as PhimReact, RefObject } from 'react';

/**
 * Ánh sáng của cỗ máy trên trang giới thiệu.
 *
 * Chuột chỉ làm MỘT việc ở đây: điều khiển đèn (DESIGN.md "Tương tác chuột").
 * Hook này ghi thẳng `--x`/`--y` vào style của một nút DOM, KHÔNG qua state
 * React — một `setState` mỗi `pointermove` là cách chắc chắn nhất để giết 60fps
 * trên máy yếu, và giá trị này không ảnh hưởng gì tới cây React.
 *
 * Hai cổng, đặt ở hai chỗ khác nhau có chủ đích:
 *   - JS chỉ nghe con trỏ khi `(hover: hover) and (pointer: fine)` và
 *     `pointerType === 'mouse'`;
 *   - còn dùng `--x`/`--y` để NGHIÊNG hay không là quyết định của media query
 *     trong styles/gioi-thieu.css (tắt hẳn dưới 1024px).
 * Nhờ vậy phím mũi tên đổi được ánh sáng ở mọi khổ màn hình mà không cần một
 * nhánh JS riêng: mọi thứ chuột làm được, bàn phím cũng làm được.
 */

const BUOC_PHIM = 6; // mỗi lần nhấn mũi tên dịch đèn 6% — 8 nhịp là hết nửa khung
const TRUY_VAN_CON_TRO = '(hover: hover) and (pointer: fine)';

function kep(gia: number): number {
  return Math.min(100, Math.max(0, gia));
}

export interface AnhSangMay {
  /** Gắn vào phần tử gốc của cỗ máy (phần tử mang class `gt-may`). */
  goc: RefObject<HTMLDivElement | null>;
  /** Gắn vào cùng phần tử đó; phần tử phải nhận được tiêu điểm bàn phím. */
  khiGoPhim: (su: PhimReact<HTMLElement>) => void;
}

export function useAnhSangMay(): AnhSangMay {
  const goc = useRef<HTMLDivElement>(null);
  /** Vị trí nghỉ do CSS đặt; đọc lại lúc gắn, không chép hằng số sang TS. */
  const nghi = useRef({ x: 50, y: 50 });
  const viTri = useRef({ x: 50, y: 50 });

  const dat = useCallback((x: number, y: number) => {
    const nut = goc.current;
    if (nut === null) return;
    viTri.current = { x, y };
    nut.style.setProperty('--x', x.toFixed(1));
    nut.style.setProperty('--y', y.toFixed(1));
  }, []);

  useEffect(() => {
    const nut = goc.current;
    if (nut === null) return;

    // Vị trí nghỉ của đèn do CSS đặt, không phải do file này đoán. Đọc lại lúc
    // gắn để nhịp mũi tên ĐẦU TIÊN đi tiếp từ chỗ đèn đang đứng, thay vì nhảy
    // về một giá trị mặc định thứ hai chép trong TS.
    const dangCo = window.getComputedStyle(nut);
    const x0 = Number.parseFloat(dangCo.getPropertyValue('--x'));
    const y0 = Number.parseFloat(dangCo.getPropertyValue('--y'));
    if (Number.isFinite(x0) && Number.isFinite(y0)) {
      nghi.current = { x: x0, y: y0 };
      viTri.current = { x: x0, y: y0 };
    }

    const truyVan = window.matchMedia(TRUY_VAN_CON_TRO);
    let khungHinh = 0;
    let cho: PointerEvent | null = null;

    // Throttle theo requestAnimationFrame, BẮT BUỘC: một handler chạy mỗi sự
    // kiện chuột là cách chắc chắn nhất để giết 60fps trên máy yếu.
    const ve = () => {
      khungHinh = 0;
      const su = cho;
      cho = null;
      if (su === null) return;
      const hop = nut.getBoundingClientRect();
      if (hop.width === 0 || hop.height === 0) return;
      dat(
        kep(((su.clientX - hop.left) / hop.width) * 100),
        kep(((su.clientY - hop.top) / hop.height) * 100),
      );
    };

    const khiDiChuyen = (su: PointerEvent) => {
      // Kiểm TẠI CHỖ thay vì gỡ/gắn lại listener theo media query: một phép so
      // sánh mỗi sự kiện rẻ hơn nhiều so với việc đồng bộ vòng đời listener.
      if (!truyVan.matches || su.pointerType !== 'mouse') return;
      cho = su;
      if (khungHinh === 0) khungHinh = window.requestAnimationFrame(ve);
    };

    const khiRoi = () => {
      cho = null;
      if (khungHinh !== 0) {
        window.cancelAnimationFrame(khungHinh);
        khungHinh = 0;
      }
      dat(nghi.current.x, nghi.current.y);
    };

    nut.addEventListener('pointermove', khiDiChuyen);
    nut.addEventListener('pointerleave', khiRoi);
    return () => {
      nut.removeEventListener('pointermove', khiDiChuyen);
      nut.removeEventListener('pointerleave', khiRoi);
      if (khungHinh !== 0) window.cancelAnimationFrame(khungHinh);
    };
  }, [dat]);

  const khiGoPhim = useCallback(
    (su: PhimReact<HTMLElement>) => {
      const { x, y } = viTri.current;
      switch (su.key) {
        case 'ArrowLeft':
          dat(kep(x - BUOC_PHIM), y);
          break;
        case 'ArrowRight':
          dat(kep(x + BUOC_PHIM), y);
          break;
        case 'ArrowUp':
          dat(x, kep(y - BUOC_PHIM));
          break;
        case 'ArrowDown':
          dat(x, kep(y + BUOC_PHIM));
          break;
        case 'Home':
          dat(nghi.current.x, nghi.current.y);
          break;
        default:
          return;
      }
      // Chỉ chặn cuộn trang khi phím THẬT SỰ được dùng để lái đèn, và chỉ khi
      // cỗ máy đang giữ tiêu điểm — mọi phím khác đi tiếp như bình thường.
      su.preventDefault();
    },
    [dat],
  );

  return { goc, khiGoPhim };
}
