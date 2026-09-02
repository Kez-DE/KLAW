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

/**
 * Số khung hình chờ trước khi bỏ cuộc. Ô hỏi của màn Soát/Soạn thảo mang
 * `disabled` trong lúc chạy, và React bỏ cờ đó ở một lượt commit KHÁC lượt
 * huỷ — `focus()` gọi sớm một khung hình sẽ im lặng không làm gì (đã đo: tiêu
 * điểm đứng nguyên tại chỗ cũ). Có trần rõ ràng, không có vòng lặp vô hạn.
 */
const SO_KHUNG_CHO_O_HOI = 5;

/**
 * Trả tiêu điểm về ô hỏi của màn hình đang mở.
 *
 * Tra ô hỏi SAU khi DOM đã cập nhật, không bắt tham chiếu từ trước: huỷ khi
 * chưa có kết quả nào đưa màn Tra cứu về bố cục ô-hỏi-giữa-màn-hình, tức React
 * thay hẳn nút DOM của ô hỏi, và `focus()` trên nút đã rời cây im lặng không
 * làm gì. `textarea` trước `input` vì ở màn Soát các nút chọn loại văn bản
 * đứng trước ô dán văn bản trong DOM.
 */
function traTieuDiemVeOHoi(conLai = SO_KHUNG_CHO_O_HOI): void {
  requestAnimationFrame(() => {
    const chinh = document.getElementById('noi-dung-chinh');
    const oHoi =
      chinh?.querySelector<HTMLElement>('textarea') ?? chinh?.querySelector<HTMLElement>('input');
    if (oHoi == null) return;
    oHoi.focus();
    if (document.activeElement !== oHoi && conLai > 0) traTieuDiemVeOHoi(conLai - 1);
  });
}

export function TrangThaiCho({ onHuy }: TrangThaiChoProps) {
  const [giay, datGiay] = useState<number | null>(null);

  /**
   * Huỷ xong thì khay này biến mất cùng cái nút vừa được bấm, và tiêu điểm rơi
   * về `<body>` — người dùng bàn phím mất chỗ đứng, Tab tiếp lại bắt đầu từ
   * đầu trang. Đo được: sau khi bấm Huỷ, `document.activeElement` là `<body>`
   * suốt.
   *
   * Trả về Ô HỎI, không phải nút gửi: nút gửi bị `disabled` trong lúc chạy nên
   * trình duyệt đã dời tiêu điểm khỏi nó từ trước — không có gì để "nhớ rồi
   * trả lại". Ô hỏi cũng đúng chỗ hơn: huỷ là để sửa câu hỏi rồi gửi lại.
   */
  const huyVaTraTieuDiem = () => {
    onHuy();
    traTieuDiemVeOHoi();
  };

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
        onClick={huyVaTraTieuDiem}
        className="mt-3 min-h-[var(--vung-cham-toi-thieu)] cursor-pointer rounded-vua border px-4 text-[0.9375rem] text-phim transition-colors duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        style={{ borderColor: 'var(--muc-nhat)', background: 'transparent' }}
      >
        Huỷ lượt tra cứu
      </button>
    </div>
  );
}
