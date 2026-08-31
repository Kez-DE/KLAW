import type { ApiError } from '../lib/api';

/**
 * Lỗi hệ thống (mạng, timeout, máy chủ) — KHÔNG dùng `--do-thay`.
 *
 * Đỏ trong bảng màu này dành riêng cho luật đã bị thay thế: đó là thứ khiến
 * người dùng hành động sai (DESIGN.md). Một lỗi mạng không được mượn cùng tín
 * hiệu, nếu không nhãn đỏ mất nghĩa. Lỗi hệ thống nói bằng chữ, trên khay nổi
 * trung tính, kèm một nút thử lại.
 */

interface BaoLoiProps {
  loi: ApiError;
  onThuLai?: () => void;
}

function goiY(loi: ApiError): string | null {
  switch (loi.kind) {
    case 'timeout':
      return 'Câu hỏi có thể quá phức tạp. Thử tách thành từng ý ngắn hơn.';
    case 'network':
      return 'Kiểm tra kết nối mạng rồi thử lại.';
    case 'not_implemented':
      return 'Chức năng này đang được hoàn thiện — chưa có kết quả thật để hiển thị.';
    case 'invalid_response':
      return 'Máy chủ trả về dữ liệu không đúng định dạng nên không hiển thị được. Đây là lỗi hệ thống, không phải lỗi câu hỏi.';
    default:
      return null;
  }
}

export function BaoLoi({ loi, onThuLai }: BaoLoiProps) {
  const them = goiY(loi);
  return (
    <div
      role="alert"
      className="mt-6 rounded-lon border p-4 shadow-noi-2"
      style={{
        background: 'var(--nen-cao)',
        borderColor: 'color-mix(in srgb, var(--muc-nhat) 55%, transparent)',
      }}
    >
      <p className="mat-doc m-0 text-phim">{loi.message}</p>
      {them !== null && (
        <p className="mat-doc mt-2 mb-0 text-[0.875rem] text-muc-nhat">{them}</p>
      )}
      {onThuLai !== undefined && (
        <button
          type="button"
          onClick={onThuLai}
          className="mt-3 min-h-[var(--vung-cham-toi-thieu)] cursor-pointer rounded-vua px-4 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
          style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
        >
          Thử lại
        </button>
      )}
    </div>
  );
}
