import type { User } from "@supabase/supabase-js";

/**
 * `user_metadata` là bản đồ tự do của Supabase — người dùng tự điền, và một
 * trường có thể vắng, rỗng hoặc không phải chuỗi. Lọc một lần ở đây để không
 * chỗ nào vẽ ra một vòng đại diện rỗng hay một cái tên là `undefined`.
 */
function chuoi(tho: unknown): string | undefined {
  if (typeof tho !== "string") return undefined;
  const sach = tho.trim();
  return sach === "" ? undefined : sach;
}

/** Tên hiện trên thẻ tài khoản: tên tự đặt → họ tên → email → rỗng. */
export function tenHienThi(user: User | null): string {
  if (user === null) return "";
  const mo: Record<string, unknown> = user.user_metadata;
  return chuoi(mo["ten_hien_thi"]) ?? chuoi(mo["ho_ten"]) ?? chuoi(user.email) ?? "";
}

/** Chữ cái đầu cho vòng đại diện; tên rỗng thì vòng để trống, không vẽ bừa. */
export function chuCaiDau(ten: string): string {
  return ten === "" ? "" : (ten[0] ?? "").toLocaleUpperCase("vi-VN");
}
