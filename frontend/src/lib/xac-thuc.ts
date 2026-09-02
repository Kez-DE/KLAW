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
export async function ghiNhanNguoiDung(): Promise<void> {
  await goi("/nguoi-dung", (x): x is unknown => x !== undefined, { method: "POST" });
}

/** Ba provider chủ dự án chốt (2026-09-02). Tên là tên của SUPABASE, không phải
 *  tên thương hiệu: Microsoft là `azure` (Microsoft Entra ID). Dùng union thay
 *  vì `string` để `tsc` chặn một tên provider viết sai — Supabase trả
 *  "Unsupported provider" lúc CHẠY, và đó là lỗi lẽ ra bắt được lúc biên dịch. */
export type NhaCungCapOAuth = "google" | "azure" | "facebook";

/**
 * Đăng nhập bằng bên thứ ba (OAuth).
 *
 * KHÔNG gọi `ghiNhanNguoiDung()` ở đây, và đó là chỗ dễ sai nhất của luồng này:
 * `signInWithOAuth` CHUYỂN HƯỚNG cả trang, nên không một dòng nào sau nó chạy.
 * Phiên chỉ xuất hiện SAU khi browser quay về, và chỗ duy nhất thấy được lúc đó
 * là `onAuthStateChange` trong `use-auth.ts` — nơi đã móc `ghiNhanNguoiDung`.
 *
 * Thiếu móc đó thì người dùng đăng nhập THÀNH CÔNG mà KLAW không bao giờ ghi
 * nhận họ: hạn mức theo-người không áp, và không có lỗi nào hiện ra.
 *
 * `redirectTo` phải nằm trong Redirect URLs của project Supabase, nếu không
 * Supabase từ chối và người dùng thấy trang lỗi của Supabase chứ không của KLAW.
 */
export async function dangNhapOAuth(nhaCungCap: NhaCungCapOAuth): Promise<KetQuaXacThuc> {
  try {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: nhaCungCap,
      options: { redirectTo: `${window.location.origin}/dung-thu` },
    });
    if (error !== null) return { trangThai: "loi", thongDiep: error.message };
  } catch {
    return { trangThai: "chua-cau-hinh", thongDiep: CHUA_CAU_HINH };
  }
  // Tới được đây nghĩa là chuyển hướng chưa xảy ra (hiếm) — không khẳng định
  // đã có phiên, vì chưa có.
  return { trangThai: "xong", canXacNhanEmail: false };
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
