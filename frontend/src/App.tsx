import { lazy, Suspense, useEffect, useState } from 'react';
import { Route, Routes } from 'react-router-dom';
import { Nav } from './components/Nav';
import { Footer } from './components/Footer';
import { ErrorBoundary } from './components/ErrorBoundary';
import { TroLy } from './components/troly/TroLy';
import { useTieuDeTrang } from './lib/useTieuDeTrang';
import GioiThieu from './pages/GioiThieu';
import TraCuu from './pages/TraCuu';
import SoanThao from './pages/SoanThao';
import Soat from './pages/Soat';

// Ba tuyến Read chia mã bằng React.lazy; "/" và "/tra-cuu" nạp ngay
// (site-spec.md, "Ràng buộc kỹ thuật"). 404 cũng lazy — không ai cần nó ở
// lần tải đầu.
const HuongDan = lazy(() => import('./pages/HuongDan'));
const PhamVi = lazy(() => import('./pages/PhamVi'));
const MienTru = lazy(() => import('./pages/MienTru'));
const KhongTimThay = lazy(() => import('./pages/KhongTimThay'));
// Mục lục một văn bản — đích của `nguon` ở nhánh `partial_coverage`. Cũng
// lazy: người dùng chỉ tới đây khi đã có một kết quả tra cứu trong tay.
const VanBan = lazy(() => import('./pages/VanBan'));
// Ba tuyến Persuade thêm sau. Cũng lazy: người tới `/tra-cuu` để hỏi một câu
// luật không cần trả tiền cho mã của trang giá và hai biểu mẫu xác thực ngay ở
// lần tải đầu.
const BangGia = lazy(() => import('./pages/BangGia'));
const DangNhap = lazy(() => import('./pages/DangNhap'));
const DangKy = lazy(() => import('./pages/DangKy'));

function DangTaiTuyen() {
  return (
    <p role="status" className="mat-doc mx-auto max-w-[46rem] px-4 py-10 text-muc-nhat">
      Đang tải…
    </p>
  );
}

/**
 * true khi trên trang có một panel khai `aria-modal="true"`.
 *
 * Khai `aria-modal` là nói với công nghệ hỗ trợ rằng PHẦN CÒN LẠI CỦA TRANG
 * KHÔNG TỒN TẠI. Panel tự bọc `inert` quanh cột nội dung của trang, nhưng
 * `Nav`, `Footer` và trợ lý là anh em của `<main>` trong file này, nằm ngoài
 * tầm với của mọi bản vá cấp trang: ở một cột, Tab vài lần là ra khỏi panel
 * vào một liên kết chân trang đang nằm khuất sau lớp phủ đặc, và Enter ở đó
 * mất trắng cả panel lẫn kết quả — trên đúng thao tác trung tâm của sản phẩm.
 *
 * Một cơ chế duy nhất ở đây, đọc thẳng lời khai trong DOM, thay vì một bản vá
 * trong mỗi panel: lời khai và việc thi hành lời khai không thể lệch nhau, và
 * panel thêm về sau tự động được phủ.
 */
function usePanelDangMo(): boolean {
  const [dangMo, datDangMo] = useState(false);

  useEffect(() => {
    const doLai = () => datDangMo(document.querySelector('[aria-modal="true"]') !== null);
    doLai();
    const quanSat = new MutationObserver(doLai);
    quanSat.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['aria-modal'],
    });
    return () => quanSat.disconnect();
  }, []);

  return dangMo;
}

export default function App() {
  // Gọi Ở ĐÂY, một lần — không trong từng trang — vì hook này còn phải phủ
  // ba màn hình Operate (TraCuu/SoanThao/Soat) mà agent này không được sửa.
  useTieuDeTrang();
  const panelMo = usePanelDangMo();

  return (
    <ErrorBoundary>
      <div className="flex min-h-svh flex-col bg-nen text-phim">
        <a href="#noi-dung-chinh" inert={panelMo} className="bo-qua-lien-ket">
          Bỏ qua để tới nội dung chính
        </a>
        {/* Thông báo chuyển tuyến cho trình đọc màn hình — điền bởi
            lib/useTieuDeTrang.ts. Nằm ngoài <main> nên không bị gỡ mỗi lần
            Routes đổi trang. KHÔNG `inert`: vùng này không nhận tiêu điểm,
            và một thông báo bị bịt miệng thì tệ hơn là không có. */}
        <div aria-live="polite" role="status" className="sr-only" id="thong-bao-chuyen-trang" />
        <Nav inert={panelMo} />
        <main id="noi-dung-chinh" className="flex-1">
          <Suspense fallback={<DangTaiTuyen />}>
            <Routes>
              <Route path="/" element={<GioiThieu />} />
              <Route path="/tra-cuu" element={<TraCuu />} />
              <Route path="/soan-thao" element={<SoanThao />} />
              <Route path="/soat" element={<Soat />} />
              <Route path="/huong-dan" element={<HuongDan />} />
              <Route path="/pham-vi" element={<PhamVi />} />
              <Route path="/mien-tru" element={<MienTru />} />
              <Route path="/bang-gia" element={<BangGia />} />
              <Route path="/dang-nhap" element={<DangNhap />} />
              <Route path="/dang-ky" element={<DangKy />} />
              <Route path="/van-ban/:docId" element={<VanBan />} />
              <Route path="*" element={<KhongTimThay />} />
            </Routes>
          </Suspense>
        </main>
        <Footer inert={panelMo} />
        {/* Trợ lý có mặt trên cả bảy tuyến, không chỉ trang giới thiệu: người
            dùng bí ở /tra-cuu hay /soat cần nó hơn người đang đọc trang giới
            thiệu. Trạng thái thu gọn vẫn nhớ trong localStorage và KHÔNG BAO
            GIỜ tự bật lại (DESIGN.md § "Trợ lý"). */}
        <TroLy inert={panelMo} />
      </div>
    </ErrorBoundary>
  );
}
