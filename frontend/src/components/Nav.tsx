import type { ComponentType } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { ChuHieu } from '../brand/MaNhan';
import { IconTraCuu, IconSoanThao, IconSoat } from '../brand/icons';

interface MucDieuHuong {
  duongDan: string;
  nhan: string;
  Bieu: ComponentType<{ size?: number; className?: string }>;
}

// "Đổi khay phim" — ba khay của một máy, không phải ba trang riêng (DESIGN.md).
const MUC_DIEU_HUONG: MucDieuHuong[] = [
  { duongDan: '/tra-cuu', nhan: 'Tra cứu', Bieu: IconTraCuu },
  { duongDan: '/soan-thao', nhan: 'Soạn thảo', Bieu: IconSoanThao },
  { duongDan: '/soat', nhan: 'Soát', Bieu: IconSoat },
];

interface NavProps {
  /** Bật khi có panel modal đang mở. App.tsx là nơi DUY NHẤT quyết định điều
   *  này (xem `usePanelDangMo` ở đó): vỏ chung phải ngừng nhận tiêu điểm, nếu
   *  không lời khai `aria-modal` của panel là một lời khai sai. */
  inert?: boolean;
}

export function Nav({ inert = false }: NavProps) {
  return (
    <nav inert={inert} aria-label="Điều hướng chính" className="border-b border-nen bg-nen-cao">
      <div className="mx-auto flex max-w-3xl items-center gap-3 px-2">
        {/* Tuyến "/" giờ là trang giới thiệu (site-spec.md), nên chữ hiệu dẫn
            về đó — không còn trùng đích với tab nào trong bảng tuyến. */}
        <Link to="/" aria-label="KLAW — trang giới thiệu" className="shrink-0 rounded-nho pl-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang">
          <ChuHieu className="text-phim" />
        </Link>
        <ul className="flex list-none gap-1 font-doc">
          {MUC_DIEU_HUONG.map((muc) => (
            <li key={muc.duongDan}>
              <NavLink
                to={muc.duongDan}
                end={muc.duongDan === '/'}
                viewTransition
                className={({ isActive }) =>
                  `flex min-h-[var(--vung-cham-toi-thieu)] min-w-[var(--vung-cham-toi-thieu)] items-center justify-center gap-2 border-b-2 px-3 text-sm transition-colors duration-[var(--thoi-luong-nhanh)] ease-chuan ${
                    isActive
                      ? 'border-den-sang text-den-sang'
                      : 'border-transparent text-muc-nhat hover:opacity-80'
                  }`
                }
              >
                {/* Biểu tượng không bao giờ đứng một mình — nhãn chữ luôn đi kèm,
                    và trạng thái "đang ở khay này" đọc được bằng viền dưới chứ
                    không chỉ bằng màu. */}
                <muc.Bieu size={18} />
                {muc.nhan}
              </NavLink>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
