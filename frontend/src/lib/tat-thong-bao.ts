/**
 * Nhớ những thông báo người dùng đã tắt (spec 2026-09-15e).
 *
 * Cố ý KHÔNG nhập gì: chạy được bằng `node` trần nên `scripts/kiem-tat-thong-bao.ts`
 * kiểm được mà không dựng cả ứng dụng.
 *
 * Dùng `localStorage` chứ không gọi máy chủ: đây là tiện lợi của TỪNG NGƯỜI trên
 * TỪNG MÁY, không phải trạng thái tài khoản. Mất nó thì thông báo hiện lại —
 * phiền, không hỏng.
 *
 * Mọi lần chạm `localStorage` đều bọc try/catch: cửa sổ ẩn danh, trình duyệt
 * chặn site data, hoặc iframe khác gốc đều ném NGAY Ở BƯỚC ĐỌC THUỘC TÍNH, chứ
 * không trả về null. Một thông báo không tắt được còn hơn một trang trắng.
 */

const TIEN_TO = "klaw.tat-thong-bao.";

/**
 * Khoá nhớ cho một lần hết hạn CỤ THỂ.
 *
 * Gắn ngày hết hạn vào khoá là điều quan trọng nhất của hàm này: tắt lần này
 * KHÔNG được tắt luôn lần sau. Người dùng gia hạn rồi hết hạn tiếp phải thấy
 * lại thông báo, nếu không họ mất lượt mà không biết vì sao.
 */
export function khoaHetHan(ngayHetHan: string): string {
  return `${TIEN_TO}het-han.${ngayHetHan.trim() || "khong-ro"}`;
}

export function daTat(khoa: string): boolean {
  try {
    return window.localStorage.getItem(khoa) === "1";
  } catch {
    return false; // không đọc được = coi như chưa tắt, thông báo vẫn hiện
  }
}

export function ghiNhoDaTat(khoa: string): void {
  try {
    window.localStorage.setItem(khoa, "1");
  } catch {
    // Không ghi được thì thôi: thông báo sẽ hiện lại ở lần tải sau. Phiền,
    // không hỏng — và không đáng để một trang lỗi.
  }
}
