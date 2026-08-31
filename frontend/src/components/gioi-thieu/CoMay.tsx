import { useEffect, useState } from 'react';
import type { HieuLuc } from '../../types';
import { BadgeHieuLuc } from '../BadgeHieuLuc';
import { DuongDan } from '../DuongDan';
import { useAnhSangMay } from '../../lib/anhSangMay';

/**
 * Cỗ máy đọc vi phim TIẾN MỘT KHUNG — khoảnh khắc trọng tâm của trang giới
 * thiệu (motion-spec.md "Luận đề chuyển động"). Ống kính đẩy vào, dải phim
 * trượt ngang, một khung dừng dưới đèn và sáng lên, để lộ một Điều luật CÓ
 * THẬT kèm `duong_dan` THẬT.
 *
 * Bỏ chuyển động này đi thì mất gì? Mất luôn phần giải thích KLAW khác một
 * trợ lý biết nói ở chỗ nào. Đó là phép thử, và nó trả lời được.
 *
 * Cấu trúc 4 tầng nằm ở styles/gioi-thieu.css — đọc chú thích ở đó TRƯỚC khi
 * đổi bất cứ thuộc tính nào của .gt-canh hay .gt-doi-hinh.
 */

/** 800ms chuỗi + một nhịp dư để lớp --chay (và `will-change`) được gỡ sạch. */
const THOI_LUONG_CHUOI_MS = 900;

/**
 * Nội dung THẬT, đã tra trực tiếp cơ sở dữ liệu (không phải chữ mẫu):
 *
 *   SELECT p.duong_dan, p.tieu_de, p.noi_dung
 *     FROM provisions p JOIN documents d ON d.id = p.document_id
 *    WHERE d.so_ky_hieu = '45/2019/QH14' AND p.duong_dan LIKE '%Điều 127%';
 *
 * Nhãn hiệu lực cũng không phải chọn cho đẹp: `documents.tinh_trang` của
 * 45/2019/QH14 là `HHL1P`, và src/services/effectivity.py ánh xạ HHL1P →
 * `mot_phan_khong_xac_dinh`. Nghĩa là khung được rọi sáng trên trang giới thiệu
 * mang đúng một cảnh báo "không xác định được điều này còn hiệu lực hay không".
 * Giữ nguyên như vậy: một trang bán sự kiểm chứng được mà lại chọn ví dụ sạch
 * nhất để trưng thì đang bán thứ khác.
 */
const KHUNG_MAU = {
  soKyHieu: '45/2019/QH14',
  duongDan: '45/2019/QH14 > Điều 127 > Khoản 2',
  tieuDe: 'Điều 127. Các hành vi bị nghiêm cấm khi xử lý kỷ luật lao động',
  quote: '2. Phạt tiền, cắt lương thay việc xử lý kỷ luật lao động.',
  hieuLuc: 'mot_phan_khong_xac_dinh' as HieuLuc,
};

/** Khung chưa rọi, hai bên. Trống có chủ đích — không in nội dung không kiểm được. */
function KhungTrong() {
  return <div className="gt-o" aria-hidden="true" />;
}

export function CoMay() {
  const { goc, khiGoPhim } = useAnhSangMay();
  // Chuỗi chạy MỘT LẦN rồi nghỉ: gỡ lớp là gỡ luôn cả animation lẫn
  // `will-change`, nên không có gì còn treo trên compositor sau 900ms.
  const [dangDien, datDangDien] = useState(true);

  useEffect(() => {
    const dongHo = window.setTimeout(() => datDangDien(false), THOI_LUONG_CHUOI_MS);
    return () => window.clearTimeout(dongHo);
  }, []);

  return (
    <div
      ref={goc}
      tabIndex={0}
      role="group"
      aria-label="Cỗ máy đọc vi phim — dùng phím mũi tên để đổi hướng đèn chiếu"
      onKeyDown={khiGoPhim}
      className={`gt-may${dangDien ? ' gt-may--chay' : ''}`}
    >
      {/* TẦNG 1 — cắt. KHÔNG preserve-3d ở đây. */}
      <div className="gt-khay">
        {/* TẦNG 2 — phối cảnh. KHÔNG overflow/filter/opacity ở đây. */}
        <div className="gt-canh">
          {/* TẦNG 3 — chuỗi 3D thật. */}
          <div className="gt-doi-hinh">
            {/* TẦNG 4 — mặt lá. Chỉ ở đây mới được đặt filter/opacity. */}
            <div className="gt-mat gt-mat--sau" aria-hidden="true" />
            <div className="gt-mat gt-mat--den" aria-hidden="true" />

            <div className="gt-mat gt-mat--dai">
              <KhungTrong />
              <KhungTrong />

              <figure className="gt-o gt-o--sang">
                <DuongDan soKyHieu={KHUNG_MAU.soKyHieu} duongDan={KHUNG_MAU.duongDan} />
                <blockquote className="gt-phim m-0">
                  <span className="chu-tren-phim block text-[0.8125rem] leading-5 font-bold">
                    {KHUNG_MAU.tieuDe}
                  </span>
                  <span className="chu-tren-phim mt-1.5 block text-[0.9375rem] leading-[1.55]">
                    {KHUNG_MAU.quote}
                  </span>
                </blockquote>
                <figcaption>
                  <BadgeHieuLuc hieuLuc={KHUNG_MAU.hieuLuc} />
                </figcaption>
              </figure>

              <KhungTrong />
              <KhungTrong />
            </div>

            <div className="gt-mat gt-mat--cua" aria-hidden="true" />
          </div>
        </div>
      </div>
    </div>
  );
}
