import { Link } from 'react-router-dom';

interface MucChan {
  duongDan: string;
  nhan: string;
}

/**
 * Có mặt trên mọi tuyến (site-spec.md, "Vỏ chung mọi trang"). Đây là tuyến
 * Read, không phải màn hình công cụ — link ở đây dùng <Link> thường, KHÔNG
 * gắn `viewTransition` như Nav.tsx: hiệu ứng "đổi khay" là cho ba màn hình
 * Operate, không phải cho vỏ chung mọi trang.
 */
const MUC_CHAN: MucChan[] = [
  { duongDan: '/', nhan: 'Giới thiệu' },
  { duongDan: '/huong-dan', nhan: 'Hướng dẫn' },
  { duongDan: '/pham-vi', nhan: 'Phạm vi dữ liệu' },
  { duongDan: '/bang-gia', nhan: 'Bảng giá' },
  { duongDan: '/mien-tru', nhan: 'Miễn trừ trách nhiệm' },
];
// `/dang-nhap` và `/dang-ky` CỐ Ý không có ở đây. Chưa có backend xác thực,
// nên một mục "Đăng nhập" trên vỏ chung mọi trang sẽ mời người dùng đi vào một
// cửa chưa mở. Hai tuyến đó tới được từ `/bang-gia` và từ chính nhau.

interface FooterProps {
  /** Bật khi có panel modal đang mở — xem `usePanelDangMo` trong App.tsx.
   *  Chân trang nằm NGAY DƯỚI lớp phủ của panel ở bố cục một cột; để nó nhận
   *  tiêu điểm là mở đường cho một cú Enter làm mất trắng cả lượt tra cứu. */
  inert?: boolean;
}

export function Footer({ inert = false }: FooterProps) {
  return (
    <footer inert={inert} className="border-t border-vien bg-nen-cao">
      <div className="mat-doc mx-auto flex max-w-[64rem] flex-col gap-4 px-4 py-6 text-muc-nhat sm:flex-row sm:items-center sm:justify-between">
        <p className="m-0 max-w-[38ch] text-[0.875rem]">
          KLAW tra cứu pháp luật lao động Việt Nam — mọi câu trả lời đều neo vào một trích dẫn
          nguyên văn kiểm chứng được, không phải suy luận của mô hình.
        </p>
        <nav aria-label="Điều hướng chân trang">
          <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-2 p-0 text-[0.875rem]">
            {MUC_CHAN.map((muc) => (
              <li key={muc.duongDan}>
                <Link
                  to={muc.duongDan}
                  className="inline-flex min-h-[var(--vung-cham-toi-thieu)] items-center underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
                >
                  {muc.nhan}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
