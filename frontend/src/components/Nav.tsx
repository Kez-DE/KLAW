import { NavLink } from 'react-router-dom';

interface MucDieuHuong {
  duongDan: string;
  nhan: string;
}

// "Đổi khay phim" — ba khay của một máy, không phải ba trang riêng (DESIGN.md).
const MUC_DIEU_HUONG: MucDieuHuong[] = [
  { duongDan: '/', nhan: 'Tra cứu' },
  { duongDan: '/soan-thao', nhan: 'Soạn thảo' },
  { duongDan: '/soat', nhan: 'Soát' },
];

export function Nav() {
  return (
    <nav aria-label="Điều hướng chính" className="border-b border-nen bg-nen-cao">
      <ul className="mx-auto flex max-w-3xl list-none gap-1 px-2 font-doc">
        {MUC_DIEU_HUONG.map((muc) => (
          <li key={muc.duongDan}>
            <NavLink
              to={muc.duongDan}
              end={muc.duongDan === '/'}
              viewTransition
              className={({ isActive }) =>
                `flex min-h-[var(--vung-cham-toi-thieu)] min-w-[var(--vung-cham-toi-thieu)] items-center justify-center border-b-2 px-4 text-sm transition-colors duration-[var(--thoi-luong-nhanh)] ease-chuan ${
                  isActive
                    ? 'border-den-sang text-den-sang'
                    : 'border-transparent text-muc-nhat hover:opacity-80'
                }`
              }
            >
              {muc.nhan}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
