import { useEffect, useRef, useState } from 'react';
import { layVanBanQuanhDieu } from '../lib/api';
import { useGoiApi, useHaiCot } from '../lib/hooks';
import { catTheoTrichDan } from '../lib/trichDan';
import type { VanBanAroundResponse } from '../types';
import { BaoLoi } from './BaoLoi';
import { DuongDan } from './DuongDan';
import { NguyenVanDieu } from './soat/NguyenVanDieu';

/**
 * Khung rọi sáng — nguyên văn điều luật, câu trích được đánh dấu khi CÓ câu
 * trích.
 *
 * Đây LÀ click-to-verify, đóng góp trung tâm của đề tài. Ba điểm không được
 * làm sai:
 *
 * 1. Fetch bằng `khop_tai_id`, KHÔNG phải `provision_id`. `provision_id`
 *    thường chỉ là tiêu đề Điều; nội dung nằm ở Khoản con, và hai id khác nhau
 *    ở 73,6% số Điều.
 * 2. `la_tam=true` áp cho Điều tâm VÀ mọi Khoản/Điểm con của nó — rọi sáng cả
 *    VÙNG đó, không phải một dòng.
 * 3. `quote` là TUỲ CHỌN. Một `Citation` có câu trích thật; một `Finding` thì
 *    không (`can_cu` chỉ là địa chỉ điều luật). Trước đây Soát/Soạn thảo dùng
 *    một panel riêng CHỈ VÌ điểm này, và bản sao đó lệch hành vi thật: thiếu
 *    hẳn rọi sáng và khung "tiến tới". Nay chỉ còn một panel; không có quote
 *    thì nó mở đúng Điều rồi im lặng — KHÔNG báo "không định vị được câu
 *    trích: “”" về một câu trích chưa từng tồn tại.
 *
 * Panel tự lo vòng đời tải/lỗi/thử lại của chính nó, để ba màn hình gọi nó chỉ
 * cần truyền vào một địa chỉ. `inert` phần còn lại và trả tiêu điểm khi đóng
 * KHÔNG phải việc của nó: App.tsx lo vỏ chung, trang gọi lo cái nút của nó.
 */

/**
 * Cái tối thiểu để mở một khung. `Citation` khớp cấu trúc sẵn nên màn Tra cứu
 * truyền thẳng; một `Finding` chỉ điền `doc_id`, `khop_tai_id`, `duong_dan`.
 */
export interface DiaChiKhung {
  doc_id: string;
  /** Dòng khớp THẬT SỰ — xem điểm 1 ở đầu file. */
  khop_tai_id: number;
  /** Hiện ở tiêu đề TRONG LÚC nguyên văn còn đang tải. */
  duong_dan?: string | null;
  so_ky_hieu?: string;
  bo_luat?: string;
  /** Có → tô sáng trong nguyên văn. Không có → chỉ mở đúng Điều. */
  quote?: string | null;
}

/** Hai vai của cùng một panel — khác nhau ĐÚNG ở chữ, không ở hành vi. */
const VAI = {
  'trich-dan': {
    nhan: 'Nguyên văn',
    ariaLabel: 'Nguyên văn điều luật',
    chuThich:
      'Hiển thị Điều được dẫn cùng 2 Điều liền trước và liền sau. Nguyên văn lấy từ CSDL, không rút gọn, không sửa chính tả.',
  },
  'can-cu': {
    nhan: 'Căn cứ pháp lý',
    ariaLabel: 'Căn cứ pháp lý của phát hiện',
    chuThich:
      'Hiển thị Điều làm căn cứ cùng 2 Điều liền trước và liền sau. Nguyên văn lấy từ CSDL, không rút gọn, không sửa chính tả.',
  },
} as const;

interface KhungRoiSangProps {
  diaChi: DiaChiKhung;
  vai: keyof typeof VAI;
  onDong: () => void;
}

export function KhungRoiSang({ diaChi, vai, onDong }: KhungRoiSangProps) {
  const haiCot = useHaiCot();
  const { dangChay, ketQua, loi, chay } = useGoiApi<VanBanAroundResponse>();
  const tieuDe = useRef<HTMLHeadingElement>(null);
  const vungCuon = useRef<HTMLDivElement>(null);
  // Giữ CHÍNH phản hồi đã được rọi sáng, thay vì một cờ boolean phải tay reset:
  // phản hồi mới là một object mới, nên quầng đèn tự tắt rồi sáng lại.
  const [ketQuaDaRoi, datKetQuaDaRoi] = useState<VanBanAroundResponse | null>(null);

  const { doc_id: docId, khop_tai_id: khopTaiId } = diaChi;
  // Chuỗi rỗng KHÔNG phải một câu trích. Quy về null ngay ở đây, một lần, để
  // không nhánh nào bên dưới phải tự nhớ phân biệt.
  const quote = diaChi.quote?.trim() ? diaChi.quote : null;
  const { nhan, ariaLabel, chuThich } = VAI[vai];

  useEffect(() => {
    // khop_tai_id, KHÔNG phải provision_id — xem ghi chú đầu file.
    void chay((signal) => layVanBanQuanhDieu(docId, khopTaiId, signal));
  }, [chay, docId, khopTaiId]);

  // Esc đóng panel, kể cả khi tiêu điểm đã đi khỏi panel.
  useEffect(() => {
    const nghe = (su: KeyboardEvent) => {
      if (su.key === 'Escape') onDong();
    };
    window.addEventListener('keydown', nghe);
    return () => window.removeEventListener('keydown', nghe);
  }, [onDong]);

  // Mở panel: đưa tiêu điểm vào tiêu đề của nó. Trả tiêu điểm về chip khi đóng
  // là việc của trang gọi — chỉ trang đó biết chip nào.
  useEffect(() => {
    tieuDe.current?.focus();
  }, []);

  // Một cột: panel phủ toàn màn hình, khoá cuộn nền phía sau.
  useEffect(() => {
    if (haiCot) return;
    const cu = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = cu;
    };
  }, [haiCot]);

  // Nguyên văn về kèm 2 Điều liền trước, nên mở ra là thấy Điều LÂN CẬN chứ
  // không phải điều đang được kiểm chứng. Kéo vùng Điều tâm lên đầu khung đọc,
  // và bật rọi sáng ở khung hình kế tiếp để `opacity` có cái để chuyển từ 0 lên
  // 1 — câu trích sáng DẦN, không bật sẵn.
  //
  // Cuộn TAY thay vì `scrollIntoView`: hàm đó cuộn cả các vùng cuộn tổ tiên,
  // tức là kéo luôn cả trang — người dùng vừa bấm một trích dẫn sẽ thấy trang
  // nhảy đi chỗ khác, và panel `sticky` bị đẩy khỏi mép trên (mất nút Đóng).
  // Đợi một khung hình: đo ngay trong lượt commit thì chiều cao khối nguyên văn
  // chưa ổn định (chữ serif trên phim vừa được bố trí lại), và phép đo hụt đẩy
  // khung đọc trượt quá vùng cần xem.
  useEffect(() => {
    if (ketQua === null) return;
    const khung = requestAnimationFrame(() => {
      datKetQuaDaRoi(ketQua);
      const boc = vungCuon.current;
      if (boc === null) return;
      const tam = boc.querySelector('[data-vung-tam]');
      if (tam === null) return;
      boc.scrollTop += tam.getBoundingClientRect().top - boc.getBoundingClientRect().top - 16;
    });
    return () => cancelAnimationFrame(khung);
  }, [ketQua]);

  const daRoi = ketQua !== null && ketQuaDaRoi === ketQua;
  const dongKhop = ketQua?.provisions.find((dieuKhoan) => dieuKhoan.id === khopTaiId) ?? null;
  // Chỉ nói "không định vị được" khi CÓ một câu trích để định vị.
  const khongDinhVi =
    quote !== null && dongKhop !== null && !catTheoTrichDan(dongKhop.noi_dung, quote).timThay;

  return (
    <aside
      role={haiCot ? 'region' : 'dialog'}
      aria-modal={haiCot ? undefined : true}
      aria-label={ariaLabel}
      className={
        haiCot
          ? 'sticky top-4 self-start'
          : 'fixed inset-0 z-[var(--z-khung-roi-sang)] flex flex-col bg-nen p-3'
      }
    >
      <div
        className="khung-nguyen-van flex min-h-0 flex-1 flex-col overflow-hidden rounded-lon border shadow-noi-3"
        style={{ background: 'var(--nen-cao)', borderColor: 'var(--den-sang)' }}
      >
        <header
          className="flex items-start gap-3 border-b p-3"
          style={{ borderColor: 'color-mix(in srgb, var(--muc-nhat) 40%, transparent)' }}
        >
          <h2
            ref={tieuDe}
            tabIndex={-1}
            className="m-0 min-w-0 flex-1 text-[0.9375rem] leading-6 font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
          >
            <span className="mb-1 block text-[0.75rem] text-muc-nhat">{nhan}</span>
            <DuongDan
              soKyHieu={ketQua?.so_ky_hieu ?? diaChi.so_ky_hieu}
              duongDan={diaChi.duong_dan ?? undefined}
              boLuat={ketQua?.bo_luat ?? diaChi.bo_luat}
            />
          </h2>
          <button
            type="button"
            onClick={onDong}
            className="min-h-[var(--vung-cham-toi-thieu)] min-w-[var(--vung-cham-toi-thieu)] shrink-0 cursor-pointer rounded-vua border text-[0.875rem] text-phim transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
            style={{ borderColor: 'var(--muc-nhat)' }}
          >
            Đóng
          </button>
        </header>

        <div
          ref={vungCuon}
          className={`min-h-0 flex-1 overflow-y-auto p-3 ${haiCot ? 'max-h-[calc(100svh-9rem)]' : ''}`}
        >
          {dangChay && (
            <p role="status" className="m-0 text-[0.9375rem] text-muc-nhat">
              Đang mở nguyên văn…
            </p>
          )}

          {loi !== null && (
            <BaoLoi
              loi={loi}
              onThuLai={() => {
                void chay((signal) => layVanBanQuanhDieu(docId, khopTaiId, signal));
              }}
            />
          )}

          {ketQua !== null && (
            <>
              {khongDinhVi && (
                <p className="mt-0 mb-3 text-[0.8125rem] leading-5 text-muc-nhat">
                  Không định vị được câu trích trong nguyên văn bên dưới, nên chưa đánh dấu. Câu
                  trích hệ thống dẫn: “{quote}”
                </p>
              )}

              {/* Mặt phim: nền sáng, chữ serif, nguyên văn không rút gọn. */}
              <NguyenVanDieu
                provisions={ketQua.provisions}
                quote={quote}
                khopTaiId={khopTaiId}
                daRoi={daRoi}
              />

              <p className="mt-3 mb-0 text-[0.75rem] leading-5 text-muc-nhat">{chuThich}</p>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
