import type { LuotTruoc, TraCuuKetQua } from "./klaw";
// Đuôi `.ts` TƯỜNG MINH: đây là import GIÁ TRỊ (hai hằng số runtime), và
// `npm run kiem-lich-su` chạy bằng Node — Node phân giải đường dẫn thật nên
// cần đuôi. `bang.ts` cạnh đây dùng `./klaw` không đuôi được vì nó chỉ import
// TYPE, thứ Node bỏ hẳn trước khi phân giải.
import { TOI_DA_LUOT_LICH_SU, TOI_DA_TRA_LOI_LICH_SU } from "./klaw.ts";

/** Một lượt hỏi–đáp ĐÃ XONG trong dòng hội thoại. Hình dạng dữ liệu, nên nó ở
 *  `lib/` — `lib` import từ `routes/` là ngược tầng. */
export interface LuotDaXong {
  cauHoi: string;
  ketQua: TraCuuKetQua;
}

/**
 * `LuotDaXong[]` của giao diện → `LuotTruoc[]` của hợp đồng API.
 *
 * Ba việc, mỗi việc vì một lý do đo được:
 *
 * - **Chỉ `TOI_DA_LUOT_LICH_SU` lượt CUỐI.** Quá trần là **422** từ pydantic,
 *   không truncate — gửi cả hội thoại dài là làm chết đúng lượt hỏi nối tiếp.
 * - **Cắt `tra_loi` còn `TOI_DA_TRA_LOI_LICH_SU`.** Máy chủ cắt lại đúng bấy
 *   nhiêu khi dựng prompt, và một câu trả lời ba tầng dễ dài hơn trần 2.000 ký
 *   tự của biên HTTP — không cắt thì cả lượt bị 422 vì câu trả lời TRƯỚC quá dài.
 * - **`duong_dan` từ citations.** Đó là thứ định danh chính xác điều khoản lượt
 *   trước đã dẫn, và là cách "liệt kê bảng cho tôi" biết cái bảng nằm ở đâu.
 *
 * Thuần, không state — kiểm được mà không cần dựng cả trang.
 */
export function dungLichSu(luot: readonly LuotDaXong[]): LuotTruoc[] {
  return luot.slice(-TOI_DA_LUOT_LICH_SU).map((l) => ({
    cau_hoi: l.cauHoi,
    tra_loi: (l.ketQua.answer ?? "").slice(0, TOI_DA_TRA_LOI_LICH_SU),
    duong_dan: l.ketQua.citations.map((t) => t.duong_dan),
  }));
}
