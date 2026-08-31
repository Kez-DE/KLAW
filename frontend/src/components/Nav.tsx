import type { ComponentType } from 'react';
import { NavLink } from 'react-router-dom';
import { ChuHieu } from '../brand/MaNhan';
import { IconTraCuu, IconSoanThao, IconSoat } from '../brand/icons';

interface MucDieuHuong {
  duongDan: string;
  nhan: string;
  Bieu: ComponentType<{ size?: number; className?: string }>;
}

// "Đổi khay phim" — ba khay của một máy, không phải ba trang riêng (DESIGN.md).
const MUC_DIEU_HUONG: MucDieuHuong[] = [
  { duongDan: '/', nhan: 'Tra cứu', Bieu: IconTraCuu },
  { duongDan: '/soan-thao', nhan: 'Soạn thảo', Bieu: IconSoanThao },
  { duongDan: '/soat', nhan: 'Soát', Bieu: IconSoat },
];

export function Nav() {
  return (
    <nav aria-label="Điều hướng chính" className="border-b border-nen bg-nen-cao">
      <div className="mx-auto flex max-w-3xl items-center gap-3 px-2">
        {/* Chữ hiệu không phải liên kết: chưa có trang giới thiệu trong bảng
            tuyến, và một liên kết thứ hai trỏ về "/" chỉ thêm một điểm dừng
            bàn phím trùng lặp. Bọc vào <Link> khi tuyến đó có thật. */}
        <ChuHieu className="shrink-0 pl-2 text-phim" />
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
