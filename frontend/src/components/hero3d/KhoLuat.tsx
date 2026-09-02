import { Canvas } from '@react-three/fiber';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BadgeHieuLuc } from '../BadgeHieuLuc';
import { VoMay } from '../gioi-thieu/VoMay';
import { PHIEN } from './duLieuPhien';
import { Kho } from './Kho';
import { TenPhien } from './TheTrichDoan';

/**
 * Tầng mount của hero 3D. Đây là module ĐƯỢC TẢI ĐỘNG — nó và mọi thứ nó import
 * (`three`, `@react-three/*`) nằm trong một chunk riêng, và chunk đó chỉ được
 * yêu cầu khi `SlotBaChieu` thật sự render component này. Cửa chặn theo bề rộng
 * nằm ở SlotBaChieu, TRƯỚC lúc render, nên dưới 768px `import()` không bao giờ
 * chạy và `three` không bao giờ xuống dây.
 *
 * Bốn ràng buộc §10.4 được thi hành ở đây:
 *
 *   - `dpr={[1, 1.75]}`, `antialias: false`, `powerPreference` — nguyên văn spec.
 *   - `frameloop` ba trạng thái. Đây là cửa THẬT SỰ dừng render: spec chỉ nói
 *     "early-return trong useFrame", nhưng early-return KHÔNG dừng vòng lặp —
 *     R3F vẫn gọi `gl.render()` mỗi frame, GPU vẫn vẽ. `frameloop="never"` tắt
 *     hẳn vòng lặp. Early-return vẫn giữ (trong Kho.tsx) làm cửa thứ hai cho
 *     frame đang bay dở lúc trạng thái vừa đổi.
 *   - Tiến trình cuộn vào MỘT `useRef`, đọc trong `useFrame`. Không `setState`
 *     mỗi frame — `setState` ở 60fps là 60 lần render cây React mỗi giây.
 *
 * Không dùng GSAP ScrollTrigger như §10.3 đề: toàn bộ việc cần làm là ghi một số
 * 0→1 vào một ref khi cuộn, và một listener `passive` làm đúng thế trong bốn
 * dòng. Thêm ~70KB để lấy bốn dòng là đi ngược chính ngân sách §10.4 đặt ra.
 */

export default function KhoLuat() {
  const boc = useRef<HTMLDivElement>(null);
  const tienRef = useRef(0);
  const tamDungRef = useRef(false);
  const [tamDung, datTamDung] = useState(false);
  const [dongBang, datDongBang] = useState(false);
  const [chiSoChon, datChiSoChon] = useState<number | null>(null);
  const [chiSoHover, datChiSoHover] = useState<number | null>(null);
  const dieuHuong = useNavigate();

  useEffect(() => {
    const truyVan = window.matchMedia('(prefers-reduced-motion: reduce)');
    const doi = () => datDongBang(truyVan.matches);
    doi();
    truyVan.addEventListener('change', doi);
    return () => truyVan.removeEventListener('change', doi);
  }, []);

  // Dừng render khi hero ra khỏi viewport HOẶC khi tab bị ẩn (§10.4). Hai nguồn
  // độc lập nên phải hợp lại rồi mới quyết định, không ghi đè lẫn nhau.
  useEffect(() => {
    const nut = boc.current;
    if (nut === null) return;
    let trongKhung = true;
    const capNhat = () => {
      const dung = !trongKhung || document.hidden;
      tamDungRef.current = dung;
      datTamDung(dung);
    };
    const quanSat = new IntersectionObserver(
      (ghis) => {
        trongKhung = ghis[ghis.length - 1].isIntersecting;
        capNhat();
      },
      // Nới 80px để cảnh đã chạy sẵn trước khi mép hero vào khung nhìn, thay vì
      // người dùng thấy nó "khởi động" ngay lúc cuộn tới.
      { rootMargin: '80px' },
    );
    quanSat.observe(nut);
    document.addEventListener('visibilitychange', capNhat);
    return () => {
      quanSat.disconnect();
      document.removeEventListener('visibilitychange', capNhat);
    };
  }, []);

  // Tiến trình cuộn: 0 khi mép trên khay ở mép trên viewport, 1 khi khay đã ra
  // hết phía trên. `getBoundingClientRect` mỗi lần cuộn (không mỗi frame).
  useEffect(() => {
    const nut = boc.current;
    if (nut === null) return;
    const doc = () => {
      const hop = nut.getBoundingClientRect();
      tienRef.current = Math.min(1, Math.max(0, -hop.top / Math.max(1, hop.height)));
    };
    doc();
    window.addEventListener('scroll', doc, { passive: true });
    window.addEventListener('resize', doc);
    return () => {
      window.removeEventListener('scroll', doc);
      window.removeEventListener('resize', doc);
    };
  }, []);

  const nhip = tamDung ? 'never' : dongBang ? 'demand' : 'always';

  return (
    <div
      ref={boc}
      onKeyDown={(su) => {
        if (su.key === 'Escape' && chiSoChon !== null) {
          su.stopPropagation();
          datChiSoChon(null);
        }
      }}
    >
      <VoMay>
        <div className="h3-canh">
          <Canvas
            dpr={[1, 1.75]}
            gl={{ antialias: false, powerPreference: 'high-performance' }}
            // fov KHÔNG có trong spec, và nó là con số quyết định cảnh có bị cắt
            // hay không: khay hero rộng 798 cao 398 (tỉ lệ ~2:1), nên chiều dọc
            // là chiều hẹp. Ở fov 42 tầm nhìn dọc tại z=8 chỉ ~6.1 đơn vị, mà
            // xoắn cao 4.2 cộng phiến 2.0 là ~6.2 — hai đầu bị cắt. 55 cho ~8.3
            // đơn vị, đủ chỗ cho cả xoắn và một vành khoảng trống quanh nó.
            camera={{ position: [0, 0, 8], fov: 55 }}
            frameloop={nhip}
            onPointerMissed={() => datChiSoChon(null)}
          >
            <Kho
              tienRef={tienRef}
              tamDungRef={tamDungRef}
              dongBang={dongBang}
              chiSoChon={chiSoChon}
              datChiSoChon={datChiSoChon}
              chiSoHover={chiSoHover}
              datChiSoHover={datChiSoHover}
              moTraCuu={(docId) => dieuHuong(`/van-ban/${docId}`)}
            />
          </Canvas>
        </div>

        {/*
         * Bảng đọc tên văn bản đang ở dưới con trỏ. CỐ Ý không phải `<Html>` gắn
         * vào phiến như §10.2 mô tả, và lý do là đo được: `.gt-khay` cắt cứng ở
         * 398px, còn thẻ này cao 95–147px tuỳ độ dài `documents.ten` và tuỳ nhãn
         * hiệu lực (nhãn "một phần không xác định" mang cả một câu giải thích).
         * Neo nó vào một vật thể đang bay trong khay đó thì mọi lần chỉnh lệch
         * chỉ đổi chỗ bị cắt: đo lần lượt 109px → 52px → 73px tràn. Một bảng đọc
         * ĐỨNG YÊN trong khay thì không bao giờ tràn, luôn đọc đủ, và đúng ẩn dụ
         * máy đọc vi phim — máy cho biết khung nào đang ở dưới ống kính.
         *
         * Liên kết giữa con trỏ và phiến KHÔNG mất: phiến được trỏ vào nâng lên
         * 0.15 và viền brass của nó sáng lên (§10.2) — đó mới là chỗ spec đặt
         * phản hồi thị giác, còn thẻ chỉ mang chữ.
         */}
        {chiSoHover !== null && chiSoChon === null && (
          <div className="h3-doc-nhan">
            <TenPhien phien={PHIEN[chiSoHover]} />
          </div>
        )}

        {/*
         * Đường bàn phím vào chính NỘI DUNG của cảnh. Một `<canvas>` không tab
         * tới được và không có gì để trình đọc màn hình đọc, nên mười lăm phiến
         * sẽ vô hình với bàn phím nếu chỉ có raycast chuột — trượt WCAG 2.1.1.
         *
         * Danh sách ẩn về mặt thị giác nhưng nút ĐANG NHẬN TIÊU ĐIỂM thì hiện ra
         * (`focus:not-sr-only`): vòng tiêu điểm phải thấy được (2.4.7), và chỉ
         * một nút hiện tại một thời điểm nên nó không chiếm chỗ bố cục.
         */}
        <ul className="h3-ban-phim">
          <li>
            <p className="sr-only">
              Kho luật lơ lửng: {PHIEN.length} văn bản trong corpus. Chọn một văn bản để mở trích
              đoạn nguyên văn kèm liên kết tới bản đầy đủ.
            </p>
          </li>
          {PHIEN.map((p, i) => (
            <li key={p.docId + p.duongDan}>
              <button
                type="button"
                aria-expanded={chiSoChon === i}
                aria-controls="h3-the"
                onClick={() => datChiSoChon(chiSoChon === i ? null : i)}
                className="h3-nut-phien"
              >
                <span className="dia-chi">{p.soKyHieu}</span>
                <span className="sr-only"> — {p.ten} — </span>
                <BadgeHieuLuc hieuLuc={p.hieuLuc} />
              </button>
            </li>
          ))}
        </ul>
      </VoMay>
    </div>
  );
}
