import { Route, Routes } from 'react-router-dom';
import { Nav } from './components/Nav';
import TraCuu from './pages/TraCuu';
import SoanThao from './pages/SoanThao';
import Soat from './pages/Soat';

export default function App() {
  return (
    <div className="min-h-svh bg-nen text-phim">
      <a href="#noi-dung-chinh" className="bo-qua-lien-ket">
        Bỏ qua để tới nội dung chính
      </a>
      <Nav />
      <main id="noi-dung-chinh">
        <Routes>
          <Route path="/" element={<TraCuu />} />
          <Route path="/soan-thao" element={<SoanThao />} />
          <Route path="/soat" element={<Soat />} />
        </Routes>
      </main>
    </div>
  );
}
