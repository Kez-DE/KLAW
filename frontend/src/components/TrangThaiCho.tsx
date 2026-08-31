import { useEffect, useState } from 'react';

/**
 * Trạng thái chờ cho một lượt gọi mất 10–60 giây.
 *
 * Trên ngưỡng 10 giây, một chỉ báo KHÔNG XÁC ĐỊNH đọc như treo máy. Nên ở đây
 * có đủ bốn thứ: tên bước đang chạy, tiến trình xác định, nút huỷ thật, và một
 * đường dẫn tới lỗi thật (timeout do lib/api.ts lo, hiện qua <BaoLoi>).
 *
 * TIẾN TRÌNH LÀ ƯỚC LƯỢNG. Backend trả một lần, không stream, nên không có
 * cách nào biết bước nào đang chạy thật. Bốn bước dưới đây CÓ THẬT trong đồ
 * thị, nhưng mốc thời gian là ước lượng — và giao diện nói đúng như vậy với
 * người dùng. Hệ thống này tồn tại để chống việc trình bày phỏng đoán như dữ
 * kiện; một thanh tiến trình giả vờ là dữ liệu thật sẽ phản bội chính nó.
 * Khi backend có SSE: thay nguồn `buoc`, giữ nguyên giao diện.
 */

interface Buoc {
  /** Giây trôi qua kể từ lúc gửi, tính từ đó bước này được coi là đang chạy. */
  tuGiay: number;
  ten: string;
}

const CAC_BUOC: Buoc[] = [
  { tuGiay: 0, ten: 'Đang tìm văn bản' },
  { tuGiay: 5, ten: 'Đang mở rộng điều khoản' },
  { tuGiay: 14, ten: 'Đang kiểm chứng trích dẫn' },
  { tuGiay: 26, ten: 'Đang dựng câu trả lời' },
];

/** Hoãn trước khi hiện chỉ báo: câu trả lời nhanh không được loé rồi tắt. */
const HOAN_MS = 400;
const NHIP_MS = 250;

interface TrangThaiChoProps {
  onHuy: () => void;
}

export function TrangThaiCho({ onHuy }: TrangThaiChoProps) {
  const [giay, datGiay] = useState<number | null>(null);

  useEffect(() => {
    const batDau = Date.now();
    const hoan = setTimeout(() => {
      datGiay((Date.now() - batDau) / 1000);
    }, HOAN_MS);
    const nhip = setInterval(() => {
      datGiay((Date.now() - batDau) / 1000);
    }, NHIP_MS);
    return () => {
      clearTimeout(hoan);
      clearInterval(nhip);
    };
  }, []);

  if (giay === null) return null; // còn trong khoảng hoãn

  let chiSoBuoc = 0;
  for (let i = 0; i < CAC_BUOC.length; i += 1) {
    if (giay >= CAC_BUOC[i].tuGiay) chiSoBuoc = i;
  }
  const soBuoc = chiSoBuoc + 1;

  return (
    <div
      className="mt-6 rounded-lon border p-4 shadow-noi-2"
      style={{
        background: 'var(--nen-cao)',
        borderColor: 'color-mix(in srgb, var(--muc-nhat) 40%, transparent)',
      }}
    >
      <p className="m-0 text-[0.8125rem] leading-5 text-muc-nhat">
        Một lượt tra cứu mất 10–60 giây. Máy đang chạy.
      </p>

      <ol className="mt-3 mb-0 list-none p-0">
        {CAC_BUOC.map((buoc, i) => {
          const xong = i < chiSoBuoc;
          const dangChay = i === chiSoBuoc;
          return (
            <li
              key={buoc.ten}
              className={`flex min-h-8 items-center gap-2.5 text-[0.9375rem] leading-6 ${dangChay ? 'buoc-vao' : ''}`}
              style={{ color: dangChay ? 'var(--den-sang)' : 'var(--muc-nhat)' }}
            >
              <span
                aria-hidden="true"
                className="size-2 shrink-0 rounded-tron"
                style={{
                  background: xong || dangChay ? 'var(--den-sang)' : 'transparent',
                  border: '1px solid var(--muc-nhat)',
                  opacity: xong ? 0.5 : 1,
                }}
              />
              <span>{buoc.ten}</span>
            </li>
          );
        })}
      </ol>

      {/* Tiến trình xác định theo BƯỚC (1..4), không phải vòng tròn quay. */}
      <div
        role="progressbar"
        aria-valuemin={1}
        aria-valuemax={CAC_BUOC.length}
        aria-valuenow={soBuoc}
        aria-valuetext={`Bước ${soBuoc}/${CAC_BUOC.length} — ${CAC_BUOC[chiSoBuoc].ten} (ước lượng)`}
        className="mt-3 h-1 w-full overflow-hidden rounded-tron"
        style={{ background: 'color-mix(in srgb, var(--muc-nhat) 35%, transparent)' }}
      >
        <div
          className="h-full origin-left transition-transform duration-[var(--thoi-luong-cham)] ease-chuan"
          style={{
            background: 'var(--den-sang)',
            transform: `scaleX(${soBuoc / CAC_BUOC.length})`,
          }}
        />
      </div>

      <p role="status" className="mt-2 mb-0 text-[0.8125rem] leading-5 text-phim">
        Bước {soBuoc}/{CAC_BUOC.length}: {CAC_BUOC[chiSoBuoc].ten} — {Math.round(giay)} giây
      </p>

      <p className="mt-1 mb-0 text-[0.75rem] leading-5 text-muc-nhat">
        Bốn bước này có thật trong hệ thống, nhưng máy chủ chưa gửi tiến trình theo thời gian
        thực: bước đang hiện là <strong className="font-medium">ước lượng theo thời gian đã
        trôi</strong>, không phải trạng thái đo được.
      </p>

      <button
        type="button"
        onClick={onHuy}
        className="mt-3 min-h-[var(--vung-cham-toi-thieu)] cursor-pointer rounded-vua border px-4 text-[0.9375rem] text-phim transition-colors duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        style={{ borderColor: 'var(--muc-nhat)', background: 'transparent' }}
      >
        Huỷ lượt tra cứu
      </button>
    </div>
  );
}
