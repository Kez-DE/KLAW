import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';
import { Nav } from './components/Nav';
import { Footer } from './components/Footer';
import { ErrorBoundary } from './components/ErrorBoundary';
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

function DangTaiTuyen() {
  return (
    <p role="status" className="mat-doc mx-auto max-w-[46rem] px-4 py-10 text-muc-nhat">
      Đang tải…
    </p>
  );
}

export default function App() {
  // Gọi Ở ĐÂY, một lần — không trong từng trang — vì hook này còn phải phủ
  // ba màn hình Operate (TraCuu/SoanThao/Soat) mà agent này không được sửa.
  useTieuDeTrang();

  return (
    <ErrorBoundary>
      <div className="flex min-h-svh flex-col bg-nen text-phim">
        <a href="#noi-dung-chinh" className="bo-qua-lien-ket">
          Bỏ qua để tới nội dung chính
        </a>
        {/* Thông báo chuyển tuyến cho trình đọc màn hình — điền bởi
            lib/useTieuDeTrang.ts. Nằm ngoài <main> nên không bị gỡ mỗi lần
            Routes đổi trang. */}
        <div aria-live="polite" role="status" className="sr-only" id="thong-bao-chuyen-trang" />
        <Nav />
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
              <Route path="*" element={<KhongTimThay />} />
            </Routes>
          </Suspense>
        </main>
        <Footer />
      </div>
    </ErrorBoundary>
  );
}
