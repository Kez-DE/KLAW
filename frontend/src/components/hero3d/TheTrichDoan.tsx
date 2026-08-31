import { BadgeHieuLuc } from '../BadgeHieuLuc';
import { DuongDan } from '../DuongDan';
import type { Phien } from './duLieuPhien';

/**
 * Nội dung DOM của hai lớp phủ trên cảnh 3D. `<Html>` của drei chỉ là cái cổng
 * chiếu — thứ nằm trong nó là DOM THẬT, nên trình đọc màn hình đọc được và
 * `DuongDan`/`BadgeHieuLuc` dùng lại y nguyên, không vẽ lại bằng WebGL.
 *
 * Vì sao không dùng `<Link>` của react-router: cây React bên trong `<Canvas>`
 * chạy qua reconciler riêng của R3F, và việc context có xuyên qua ranh giới đó
 * hay không phụ thuộc phiên bản. Một liên kết "Mở trong Tra cứu" hỏng lặng lẽ
 * thì phá đúng lời hứa của trang, nên chỗ này nhận `moTraCuu` từ ngoài Canvas —
 * `href` thật vẫn còn cho chuột giữa và cho menu ngữ cảnh, còn click thường thì
 * điều hướng bằng router.
 */

/** Tooltip khi trỏ vào một phiến: tên văn bản tiếng Việt + nhãn hiệu lực. */
export function TenPhien({ phien }: { phien: Phien }) {
  return (
    <div
      className="pointer-events-none w-max max-w-[15rem] rounded-vua border p-2"
      style={{
        background: 'var(--nen-cao)',
        borderColor: 'color-mix(in srgb, var(--den-sang) 45%, transparent)',
        boxShadow: 'var(--shadow-tieu-diem)',
      }}
    >
      <span className="dia-chi block text-[0.75rem] leading-4 text-den-sang">
        {phien.soKyHieu}
      </span>
      <span className="mat-doc mt-1 block text-[0.8125rem] leading-4 text-phim">{phien.ten}</span>
      <span className="mt-1.5 block">
        <BadgeHieuLuc hieuLuc={phien.hieuLuc} />
      </span>
    </div>
  );
}

interface TheProps {
  phien: Phien;
  moTraCuu: (docId: string) => void;
  dong: () => void;
}

/**
 * Thẻ trích đoạn khi bấm một phiến. Trích đoạn là NGUYÊN VĂN một Khoản trong
 * corpus (xem chú thích đầu `duLieuPhien.ts`), không phải chữ mẫu — nên nó nằm
 * trong `<blockquote>` trên nền `--phim`, đúng chỗ văn bản luật thuộc về.
 */
export function TheTrichDoan({ phien, moTraCuu, dong }: TheProps) {
  return (
    <div
      id="h3-the"
      role="group"
      aria-label={`Trích đoạn ${phien.soKyHieu}`}
      className="flex w-[min(21rem,72vw)] flex-col gap-2 rounded-vua border p-3"
      style={{
        background: 'var(--nen-cao)',
        borderColor: 'var(--den-sang)',
        boxShadow: 'var(--shadow-tieu-diem)',
      }}
    >
      <DuongDan duongDan={phien.duongDan} soKyHieu={phien.soKyHieu} boLuat={phien.ten} />

      <blockquote
        className="m-0 rounded-nho px-2.5 py-2"
        style={{ background: 'var(--phim)' }}
        cite={phien.duongDan}
      >
        <span className="chu-tren-phim block text-[0.875rem] leading-[1.5]">{phien.trichDoan}</span>
      </blockquote>

      <BadgeHieuLuc hieuLuc={phien.hieuLuc} />

      <span className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <a
          href={`/van-ban/${phien.docId}`}
          onClick={(su) => {
            // Chuột giữa / Cmd-click / Ctrl-click phải giữ hành vi mở tab mới của
            // trình duyệt; chỉ click thường mới đưa cho router.
            if (su.metaKey || su.ctrlKey || su.shiftKey || su.button !== 0) return;
            su.preventDefault();
            moTraCuu(phien.docId);
          }}
          className="mat-doc inline-flex min-h-[var(--vung-cham-toi-thieu)] items-center text-[0.875rem] text-den-sang underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        >
          Mở trong Tra cứu
        </a>
        <button
          type="button"
          onClick={dong}
          className="mat-doc inline-flex min-h-[var(--vung-cham-toi-thieu)] cursor-pointer items-center text-[0.875rem] text-muc-nhat underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        >
          Đóng
        </button>
      </span>
    </div>
  );
}
