import { goi } from "@/lib/api";
import { supabase } from "@/integrations/supabase/client";

/**
 * Đăng nhập / đăng ký THẬT, qua Supabase.
 *
 * Hai màn xác thực trước đây chạy `setTimeout(1200)` rồi hiện "Xác thực thành
 * công" cho mọi mật khẩu trừ chuỗi `"sai"`. Đó là chế độ hỏng tệ hơn cả dữ liệu
 * giả: dữ liệu giả nói sai về pháp luật, còn màn này nói sai về CHÍNH NGƯỜI
 * DÙNG — bảo họ rằng họ đã đăng nhập trong khi không có phiên nào tồn tại, rồi
 * đẩy họ sang một màn hỏi mà cổng bảo vệ sẽ trả 401.
 *
 * Supabase chưa cấu hình thì `supabase.auth` NÉM. Bắt lỗi đó và nói ra, không
 * quy về "email hoặc mật khẩu không đúng" — đổ lỗi cho người dùng vì một biến
 * môi trường chưa điền là một lời nói dối nhỏ nhưng khiến họ thử lại mãi.
 */

export type KetQuaXacThuc =
  | { trangThai: "xong"; canXacNhanEmail: boolean }
  | { trangThai: "loi"; thongDiep: string }
  | { trangThai: "chua-cau-hinh"; thongDiep: string };

const CHUA_CAU_HINH =
  "Bản triển khai này chưa cấu hình đăng nhập (thiếu biến môi trường Supabase), nên chưa tạo được phiên. Tra cứu và soạn thảo vẫn dùng được mà không cần tài khoản.";

/**
 * Ghi nhận người dùng ở phía KLAW sau khi có phiên.
 *
 * `POST /nguoi-dung` idempotent và trả **501** khi máy chủ chưa cấu hình xác
 * thực. 501 KHÔNG phải lỗi đăng nhập: phiên Supabase vẫn có thật, chỉ là máy
 * chủ KLAW chưa đếm hạn mức theo tài khoản. Nuốt lặng thì cũng được, nhưng
 * không được biến nó thành một thông báo đăng nhập thất bại.
 */
async function ghiNhanNguoiDung(): Promise<void> {
  await goi("/nguoi-dung", (x): x is unknown => x !== undefined, { method: "POST" });
}

export async function dangNhap(email: string, matKhau: string): Promise<KetQuaXacThuc> {
  try {
    const { error } = await supabase.auth.signInWithPassword({ email, password: matKhau });
    if (error !== null) return { trangThai: "loi", thongDiep: error.message };
  } catch {
    return { trangThai: "chua-cau-hinh", thongDiep: CHUA_CAU_HINH };
  }
  await ghiNhanNguoiDung();
  return { trangThai: "xong", canXacNhanEmail: false };
}

export async function dangKy(
  email: string,
  matKhau: string,
  hoTen: string,
): Promise<KetQuaXacThuc> {
  try {
    const { data, error } = await supabase.auth.signUp({
      email,
      password: matKhau,
      options: { data: { ho_ten: hoTen } },
    });
    if (error !== null) return { trangThai: "loi", thongDiep: error.message };
    // Dự án Supabase bật xác nhận email sẽ trả `session: null`. Nói đúng điều
    // đó thay vì đẩy người dùng sang màn hỏi rồi để cổng bảo vệ trả 401.
    if (data.session === null) return { trangThai: "xong", canXacNhanEmail: true };
  } catch {
    return { trangThai: "chua-cau-hinh", thongDiep: CHUA_CAU_HINH };
  }
  await ghiNhanNguoiDung();
  return { trangThai: "xong", canXacNhanEmail: false };
}
