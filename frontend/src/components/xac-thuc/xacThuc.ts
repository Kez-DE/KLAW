import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Logic dùng chung của hai biểu mẫu `/dang-nhap` và `/dang-ky`.
 *
 * ĐỌC PHẦN NÀY TRƯỚC KHI SỬA — đây là ràng buộc pháp lý, không phải lựa chọn
 * kỹ thuật (BUILD-SPEC §14.2 · §14.3):
 *
 *   - KHÔNG có xác thực nào ở đây, và cố ý như vậy. `guiTam` chỉ chờ 1200ms
 *     rồi báo xong. Nó KHÔNG so mật khẩu, KHÔNG gọi mạng, KHÔNG sinh token,
 *     KHÔNG ghi cờ `isLoggedIn` vào localStorage/sessionStorage/cookie.
 *   - Một giao diện tự nhận đã đăng nhập khi phía sau không có gì xác thực là
 *     một lời khai sai về bảo mật. Người đọc mã sau này — và người dùng —
 *     phải không tìm thấy dấu vết nào của một phiên giả.
 *   - KHÔNG log dữ liệu biểu mẫu ra console ở bất kỳ nhánh nào. Người dùng sẽ
 *     nhập họ tên, email công việc và mật khẩu vào đây.
 */

/** Chuỗi hiển thị lấy nguyên văn BUILD-SPEC §15.4, cộng hai chuỗi spec không
 *  cấp cho hai trường mà spec vẫn đánh dấu bắt buộc (họ tên, vai trò). */
export const LOI = {
  hoTen: 'Vui lòng nhập họ và tên.',
  email: 'Vui lòng nhập email công việc hợp lệ.',
  vaiTro: 'Vui lòng chọn vai trò của bạn.',
  matKhau: 'Mật khẩu cần tối thiểu 8 ký tự, gồm chữ và số.',
  /** Đăng nhập chỉ đòi ô mật khẩu KHÔNG TRỐNG. Áp quy tắc "8 ký tự, gồm chữ và
   *  số" lên màn đăng nhập là công bố chính sách mật khẩu cho người chưa đăng
   *  nhập, và chặn oan mọi mật khẩu đặt trước khi chính sách đó ra đời. */
  matKhauTrong: 'Vui lòng nhập mật khẩu.',
  mang: 'Trình duyệt đang báo không có kết nối mạng, nên biểu mẫu chưa gửi được.',
} as const;

export function loiHoTen(gia: string): string | null {
  return gia.trim() === '' ? LOI.hoTen : null;
}

/**
 * Định dạng email, KHÔNG phải chính sách tên miền.
 *
 * Nhãn trường là "Email công việc" — một lời đề nghị, không phải một luật
 * chặn. Chặn gmail.com/outlook.com sẽ là một quy tắc kinh doanh mà không tài
 * liệu nào trong repo này cấp thẩm quyền, và nó khoá cửa với đúng nhóm người
 * dùng nhỏ nhất: luật sư và kế toán hành nghề độc lập.
 */
export function loiEmail(gia: string): string | null {
  const sach = gia.trim();
  if (sach === '') return LOI.email;
  // Một ký tự @ ở giữa, có tên miền, tên miền có dấu chấm, không khoảng trắng.
  return /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/.test(sach) ? null : LOI.email;
}

export function loiVaiTro(gia: string): string | null {
  return gia === '' ? LOI.vaiTro : null;
}

/** Đúng ngưỡng spec nêu: tối thiểu 8 ký tự, có cả chữ và số. */
export function loiMatKhau(gia: string): string | null {
  const duDai = gia.length >= 8;
  const coChu = /\p{L}/u.test(gia);
  const coSo = /\d/.test(gia);
  return duDai && coChu && coSo ? null : LOI.matKhau;
}

export const NHAN_DO_MANH = ['', 'yếu', 'trung bình', 'khá', 'mạnh'] as const;

/**
 * Thanh đo mật khẩu 4 đoạn (BUILD-SPEC §9.2). Trả 0–4.
 *
 * Đây là chỉ dấu cho người dùng, KHÔNG phải cổng chặn: `loiMatKhau` mới là
 * điều kiện gửi được biểu mẫu. Hai việc khác nhau và không được trộn — một
 * thanh đo tô đỏ mà vẫn gửi được thì gây hoang mang, còn một thanh đo chặn
 * người dùng ở mức "khá" thì là một quy tắc không ai yêu cầu.
 */
export function doMatKhau(gia: string): number {
  if (gia === '') return 0;
  let diem = 0;
  if (gia.length >= 8) diem += 1;
  if (/\p{L}/u.test(gia) && /\d/.test(gia)) diem += 1;
  if (gia.length >= 12) diem += 1;
  if (/[^\p{L}\d]/u.test(gia)) diem += 1;
  return diem;
}

export type TrangThaiGui = 'nghi' | 'dang-gui' | 'loi' | 'xong';

interface KetQuaGuiTam {
  trangThai: TrangThaiGui;
  gui: () => void;
  datLai: () => void;
}

const CHO_MS = 1200;

/**
 * Máy trạng thái của một lượt gửi biểu mẫu khi CHƯA CÓ backend.
 *
 * TODO(backend): replace with real authentication endpoint.
 *
 * Nhánh `loi` không phải một lỗi bịa để trưng giao diện: nó là trường hợp hỏng
 * DUY NHẤT có thật hôm nay — trình duyệt báo mất mạng thì một biểu mẫu không
 * được phép báo thành công. Ở đây cố tình KHÔNG có nhánh "email hoặc mật khẩu
 * không đúng": không có gì kiểm mật khẩu, nên một thông báo như vậy sẽ là suy
 * đoán. Chuỗi đó thuộc về backend, và sẽ vào cùng lúc với backend.
 */
export function useGuiTam(): KetQuaGuiTam {
  const [trangThai, datTrangThai] = useState<TrangThaiGui>('nghi');
  const dongHo = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (dongHo.current !== null) clearTimeout(dongHo.current);
    },
    [],
  );

  const gui = useCallback(() => {
    if (!navigator.onLine) {
      datTrangThai('loi');
      return;
    }
    datTrangThai('dang-gui');
    dongHo.current = setTimeout(() => datTrangThai('xong'), CHO_MS);
  }, []);

  const datLai = useCallback(() => {
    if (dongHo.current !== null) clearTimeout(dongHo.current);
    datTrangThai('nghi');
  }, []);

  return { trangThai, gui, datLai };
}
