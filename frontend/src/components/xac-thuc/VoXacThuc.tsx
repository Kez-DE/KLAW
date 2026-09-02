import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ChuHieu } from '../../brand/MaNhan';

/**
 * Vỏ chung của `/dang-nhap` và `/dang-ky` — chia 45/55 từ 1024px, một cột
 * bên dưới (BUILD-SPEC §9.2).
 *
 * THỨ TỰ DOM CÓ CHỦ ĐÍCH: thẻ biểu mẫu đứng TRƯỚC cột trái, rồi `lg:order-first`
 * đưa cột trái sang bên trái ở màn rộng. Ở 390px người vừa bấm "Đăng nhập"
 * không phải cuộn qua ba tình huống minh hoạ mới tới được ô email, và `<h1>`
 * của trang — thứ `useTieuDeTrang` đặt tiêu điểm vào sau mỗi lần chuyển tuyến —
 * là tiêu đề của thẻ biểu mẫu, không phải một tiêu đề trang trí.
 */

/**
 * Ba tình huống ở cột trái.
 *
 * KHÔNG PHẢI trích dẫn của khách hàng, và đây là một sai lệch CÓ Ý THỨC so với
 * BUILD-SPEC §9.2 (spec yêu cầu "block trích dẫn xoay vòng 3 mục ... nhân vật
 * ghi rõ (nhân vật minh họa)"). KLAW chưa có người dùng thật, nên một câu nói
 * đặt vào miệng một nhân vật bịa — dù có dán nhãn — vẫn là một khẳng định về
 * trải nghiệm sử dụng chưa từng xảy ra. Chính spec (§17) cảnh báo đừng để giao
 * diện "hứa hộ". Ba tình huống dưới đây nói cùng một điều mà không cần một
 * người bịa: đây là ba việc hệ thống được dựng để làm, và ba nhóm người dùng
 * trong DESIGN.md.
 *
 * Cũng KHÔNG xoay vòng 6 giây như spec nêu: nội dung tự đổi mỗi 6 giây mà
 * không có nút tạm dừng là lỗi WCAG 2.2.2 (mức A). Ba mục ngắn, hiện cả ba,
 * hết chuyện — rẻ hơn cả một carousel kèm nút tạm dừng, và không ai mất mục
 * nào.
 */
const TINH_HUONG = [
  {
    vai: 'Nhân sự',
    viec: 'Cần thời gian thử việc tối đa cho một chức danh quản lý — và cần dẫn được đúng Điều để đưa vào hợp đồng.',
  },
  {
    vai: 'Người lao động',
    viec: 'Bị chấm dứt hợp đồng, cần biết mình được hưởng những gì, kèm nguyên văn điều luật để tự đối chiếu.',
  },
  {
    vai: 'Sinh viên luật',
    viec: 'Cần đọc nguyên văn một Điều trong Bộ luật Lao động, không phải bản diễn giải của người khác.',
  },
];

/**
 * Ba năng lực ở cột trái — DIỄN ĐẠT NHƯ NĂNG LỰC SẢN PHẨM, không phải số liệu
 * (BUILD-SPEC §14.4).
 *
 * Hai trong ba chuỗi spec đề xuất đã bị BỎ vì sai về hệ thống này:
 *   - "Cập nhật hằng ngày" — corpus được thu thập MỘT LẦN từ cổng Bộ Tư pháp;
 *     không có pipeline cập nhật hằng ngày nào tồn tại.
 *   - "Hạ tầng đặt tại Việt Nam" — xác thực sẽ chạy qua Supabase, không đặt
 *     tại Việt Nam.
 * Hai chuỗi thay thế đều là sự thật ĐO ĐƯỢC của dự án: `abstain` là một trong
 * bốn `result_type` và được tính điểm trong đánh giá; nhãn hiệu lực nêu đích
 * danh văn bản thay thế, và bốn nghị định lương tối thiểu bị CSDL quốc gia
 * đánh sai hiệu lực đã được phát hiện và sửa.
 */
const NANG_LUC = [
  'Trích dẫn tới cấp Điểm',
  'Không trả lời khi không dẫn được nguồn',
  'Cảnh báo khi văn bản đã bị thay thế',
];

interface VoXacThucProps {
  /** Thành `<h1>` của tuyến — tiêu điểm bàn phím sau mỗi lần chuyển trang. */
  tieuDe: string;
  phuDe: ReactNode;
  children: ReactNode;
}

export function VoXacThuc({ tieuDe, phuDe, children }: VoXacThucProps) {
  return (
    <div className="grid lg:min-h-svh lg:grid-cols-[45fr_55fr]">
      {/* ── Phải: thẻ biểu mẫu, rộng tối đa 440px ─────────────────────── */}
      <div className="flex justify-center bg-nen-cao px-4 py-10 lg:px-8">
        <div className="w-full max-w-[27.5rem]">
          <h1 className="mat-doc max-w-none text-2xl font-semibold text-phim focus:outline-2 focus:outline-den-sang focus:outline-offset-4">
            {tieuDe}
          </h1>
          <p className="mat-doc mt-2 max-w-none text-[0.9375rem] text-muc-nhat">{phuDe}</p>
          {children}
        </div>
      </div>

      {/* ── Trái: vì sao (dán trên khi cuộn ở màn rộng) ────────────────── */}
      <aside
        aria-label="Vì sao dùng KLAW"
        className="xt-trai order-last bg-nen px-4 py-10 lg:order-first lg:sticky lg:top-0 lg:self-start lg:px-8 lg:py-14"
      >
        <Link
          to="/"
          aria-label="KLAW — trang giới thiệu"
          className="inline-flex min-h-[var(--vung-cham-toi-thieu)] items-center rounded-nho focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        >
          <ChuHieu className="text-phim" />
        </Link>
        <p className="mat-doc mt-3 text-[0.9375rem] text-muc-nhat">
          Tra cứu pháp luật lao động Việt Nam, có trích dẫn kiểm chứng được.
        </p>

        <h2 className="mat-doc mt-9 max-w-none text-[0.8125rem] font-medium tracking-wide text-muc-nhat uppercase">
          Ba việc KLAW được dựng để làm
        </h2>
        <ul className="mt-4 flex list-none flex-col gap-4 p-0">
          {TINH_HUONG.map((mot) => (
            <li key={mot.vai} className="border-s ps-4" style={{ borderColor: 'var(--vien)' }}>
              <p className="mat-doc m-0 text-[0.9375rem] text-phim">{mot.viec}</p>
              <p className="m-0 mt-1 text-[0.8125rem] leading-5 text-muc-nhat">
                {mot.vai} · tình huống minh hoạ
              </p>
            </li>
          ))}
        </ul>

        <ul className="mt-9 flex list-none flex-col gap-2.5 p-0">
          {NANG_LUC.map((cau) => (
            <li key={cau} className="flex items-start gap-2.5 text-[0.8125rem] leading-5 text-phim">
              <span
                aria-hidden="true"
                className="mt-1.5 size-1.5 shrink-0 rounded-tron"
                style={{ background: 'var(--den-sang)' }}
              />
              {cau}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

/**
 * Hai nút nhà cung cấp danh tính — Google và Microsoft (BUILD-SPEC §15.4).
 *
 * `disabled` CÓ CHỦ ĐÍCH, kèm một ghi chú THẤY ĐƯỢC. Xác thực thật sẽ chạy qua
 * Supabase ở một commit sau; dựng nửa vời một luồng OAuth để "sẵn sàng" thì
 * commit đó sẽ thay hẳn, còn một nút bấm vào không làm gì là một nút hỏng. Nút
 * không dùng được thì nói ra, chứ không im lặng nuốt cú bấm.
 */
export function KhoiOAuth({ hanhDong }: { hanhDong: string }) {
  return (
    <>
      <div className="mt-6 flex flex-col gap-2.5">
        {['Google', 'Microsoft'].map((ten) => (
          <button
            key={ten}
            type="button"
            disabled
            aria-describedby="oauth-chua-mo"
            className="mat-doc min-h-[var(--vung-cham-toi-thieu)] max-w-none cursor-not-allowed rounded-vua border px-4 text-[0.9375rem] text-muc-nhat opacity-60"
            style={{ borderColor: 'var(--vien)', background: 'var(--nen)' }}
          >
            Tiếp tục với {ten}
          </button>
        ))}
      </div>
      <p id="oauth-chua-mo" className="mt-2 mb-0 text-[0.8125rem] leading-5 text-muc-nhat">
        Hai lối này mở khi backend xác thực được nối. Hiện chưa dùng được, nên chúng bị vô hiệu
        thay vì bấm vào không có gì xảy ra.
      </p>

      <div className="mt-6 flex items-center gap-3" aria-hidden="true">
        <span className="h-px flex-1" style={{ background: 'var(--vien)' }} />
        <span className="text-[0.8125rem] text-muc-nhat">hoặc {hanhDong} bằng email</span>
        <span className="h-px flex-1" style={{ background: 'var(--vien)' }} />
      </div>
    </>
  );
}
