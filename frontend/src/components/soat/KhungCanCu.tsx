import { useEffect, useRef } from 'react';
import { layVanBanQuanhDieu } from '../../lib/api';
import { useGoiApi, useHaiCot } from '../../lib/hooks';
import type { VanBanAroundResponse } from '../../types';
import { BaoLoi } from '../BaoLoi';
import { DuongDan } from '../DuongDan';
import { NguyenVanDieu } from './NguyenVanDieu';

/**
 * Panel đối chiếu căn cứ của một `Finding` — cùng cơ chế click-to-verify của
 * màn Tra cứu: fetch bằng `khop_tai_id`, KHÔNG phải `provision_id`.
 *
 * Vì sao không dùng thẳng `KhungRoiSang`: component đó nhận một `Citation` và
 * luôn cố định vị `Citation.quote` trong nguyên văn; một `Finding` KHÔNG có
 * câu trích nào (`dieu_khoan_lien_quan` là trích đoạn của văn bản ĐANG SOÁT,
 * không phải của luật). Truyền chuỗi rỗng vào đó làm panel in ra câu "không
 * định vị được câu trích: “”" — một lời nói dối về dữ liệu không tồn tại.
 * Panel này bỏ đúng phần đó và dùng chung mọi thứ còn lại.
 *
 * Trang gọi phải làm hai việc panel không làm được: `inert` phần còn lại khi ở
 * chế độ một cột, và trả tiêu điểm về đúng nút phát hiện khi đóng.
 */

interface KhungCanCuProps {
  docId: string;
  khopTaiId: number;
  /** `duong_dan` của căn cứ — hiện ở tiêu đề trong lúc nguyên văn đang tải. */
  canCu: string | null;
  onDong: () => void;
}

export function KhungCanCu({ docId, khopTaiId, canCu, onDong }: KhungCanCuProps) {
  const haiCot = useHaiCot();
  const { dangChay, ketQua, loi, chay } = useGoiApi<VanBanAroundResponse>();
  const tieuDe = useRef<HTMLHeadingElement>(null);
  const vungCuon = useRef<HTMLDivElement>(null);

  useEffect(() => {
    void chay((signal) => layVanBanQuanhDieu(docId, khopTaiId, signal));
  }, [chay, docId, khopTaiId]);

  // Nguyên văn về kèm 2 Điều liền trước, nên mở ra là thấy Điều LÂN CẬN chứ
  // không phải căn cứ. Kéo vùng Điều tâm lên đầu khung đọc.
  //
  // Cuộn TAY thay vì `scrollIntoView`: hàm đó cuộn cả các vùng cuộn tổ tiên,
  // tức là kéo luôn cả trang — người dùng vừa bấm một phát hiện sẽ thấy trang
  // nhảy đi chỗ khác, và panel `sticky` bị đẩy khỏi mép trên (mất nút Đóng).
  // Đợi một khung hình: đo ngay trong lượt commit thì chiều cao khối nguyên văn
  // chưa ổn định (chữ serif trên phim vừa được bố trí lại), và phép đo hụt đẩy
  // khung đọc trượt quá vùng cần xem.
  useEffect(() => {
    if (ketQua === null) return;
    const khung = requestAnimationFrame(() => {
      const boc = vungCuon.current;
      if (boc === null) return;
      const tam = boc.querySelector('[data-vung-tam]');
      if (tam === null) return;
      boc.scrollTop += tam.getBoundingClientRect().top - boc.getBoundingClientRect().top - 16;
    });
    return () => cancelAnimationFrame(khung);
  }, [ketQua]);

  // Esc đóng panel, kể cả khi tiêu điểm đã đi khỏi panel.
  useEffect(() => {
    const nghe = (su: KeyboardEvent) => {
      if (su.key === 'Escape') onDong();
    };
    window.addEventListener('keydown', nghe);
    return () => window.removeEventListener('keydown', nghe);
  }, [onDong]);

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

  return (
    <aside
      role={haiCot ? 'region' : 'dialog'}
      aria-modal={haiCot ? undefined : true}
      aria-label="Căn cứ pháp lý của phát hiện"
      className={
        haiCot
          ? 'sticky top-4 self-start'
          : 'fixed inset-0 z-[var(--z-khung-roi-sang)] flex flex-col bg-nen p-3'
      }
    >
      <div
        className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lon border shadow-noi-3"
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
            <span className="mb-1 block text-[0.75rem] text-muc-nhat">Căn cứ pháp lý</span>
            <DuongDan
              soKyHieu={ketQua?.so_ky_hieu}
              duongDan={canCu ?? undefined}
              boLuat={ketQua?.bo_luat}
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
              <NguyenVanDieu provisions={ketQua.provisions} />
              <p className="mt-3 mb-0 text-[0.75rem] leading-5 text-muc-nhat">
                Hiển thị Điều làm căn cứ cùng 2 Điều liền trước và liền sau. Nguyên văn lấy từ
                CSDL, không rút gọn, không sửa chính tả.
              </p>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
