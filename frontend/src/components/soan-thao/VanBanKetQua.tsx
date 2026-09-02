import { useEffect, useState } from 'react';

/**
 * Văn bản do KLAW sinh ra — Markdown thuần từ `SoanThaoResponse.document`.
 *
 * KHÔNG `dangerouslySetInnerHTML`, và không thêm thư viện Markdown: định dạng
 * server sinh ra chỉ có ba dạng dòng (`# tiêu đề`, `## Điều N. Tên`, đoạn văn
 * thường), nên một phép đọc theo từng dòng là đủ và không có bề mặt tấn công
 * nào. Dòng không khớp dạng nào hiện nguyên văn thành một đoạn — không bao
 * giờ bị nuốt mất.
 *
 * Văn bản hiển thị trên MẶT PHIM (nền sáng, chữ serif): đây là văn bản pháp lý
 * để đọc và chép ra, không phải giao diện điều khiển.
 */

const CHEP_XONG_MS = 2000;

interface VanBanKetQuaProps {
  document: string;
}

export function VanBanKetQua({ document: vanBan }: VanBanKetQuaProps) {
  const [trangThaiChep, datTrangThaiChep] = useState<'nghi' | 'xong' | 'hong'>('nghi');

  useEffect(() => {
    if (trangThaiChep === 'nghi') return;
    const dong = setTimeout(() => datTrangThaiChep('nghi'), CHEP_XONG_MS);
    return () => clearTimeout(dong);
  }, [trangThaiChep]);

  const chep = async () => {
    try {
      await navigator.clipboard.writeText(vanBan);
      datTrangThaiChep('xong');
    } catch {
      // Clipboard API bị chặn (ngữ cảnh không bảo mật, quyền bị từ chối) — nói
      // thẳng thay vì im lặng giả vờ đã chép.
      datTrangThaiChep('hong');
    }
  };

  return (
    <section aria-label="Văn bản đã soạn">
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <h2 className="m-0 flex-1 text-[1rem] leading-6 font-medium text-phim">Văn bản đã soạn</h2>
        <button
          type="button"
          onClick={() => void chep()}
          className="min-h-[var(--vung-cham-toi-thieu)] cursor-pointer rounded-vua border px-4 text-[0.875rem] text-phim transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
          style={{ borderColor: 'var(--muc-nhat)' }}
        >
          Chép toàn văn
        </button>
      </div>
      <p role="status" className="sr-only">
        {trangThaiChep === 'xong' ? 'Đã chép văn bản.' : ''}
      </p>
      {trangThaiChep !== 'nghi' && (
        <p aria-hidden="true" className="mt-0 mb-3 text-[0.8125rem] leading-5 text-muc-nhat">
          {trangThaiChep === 'xong'
            ? 'Đã chép.'
            : 'Trình duyệt không cho chép tự động — hãy bôi đen văn bản rồi chép thủ công.'}
        </p>
      )}

      <div className="rounded-lon p-4" style={{ background: 'var(--phim)' }}>
        {vanBan.split('\n').map((dong, i) => {
          const khoa = `${i}-${dong.slice(0, 24)}`;
          if (dong.startsWith('## ')) {
            return (
              <h4
                key={khoa}
                className="chu-tren-phim mt-5 mb-2 text-[1.0625rem] leading-7 font-bold first:mt-0"
              >
                {dong.slice(3)}
              </h4>
            );
          }
          if (dong.startsWith('# ')) {
            return (
              <h3
                key={khoa}
                className="chu-tren-phim mt-0 mb-4 text-center text-[1.1875rem] leading-7 font-bold"
              >
                {dong.slice(2)}
              </h3>
            );
          }
          if (dong.trim() === '') return null;
          return (
            <p key={khoa} className="chu-tren-phim my-2 text-[1rem] leading-[1.75]">
              {dong}
            </p>
          );
        })}
      </div>

      <p className="mt-3 mb-0 text-[0.75rem] leading-5 text-muc-nhat">
        Bản nháp để đối chiếu và chỉnh sửa, không phải văn bản hoàn chỉnh: phần ký, ngày tháng và
        các mục hành chính khác chưa được sinh ra. Mọi chỗ trong ngoặc vuông cần bạn điền.
      </p>
    </section>
  );
}
