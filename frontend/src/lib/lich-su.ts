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

/** Trần `duong_dan` mỗi lượt — `LuotTruoc.duong_dan` có `max_length=50` ở
 *  phía pydantic, quá trần cũng là 422 (không truncate), y hệt hai trần kia.
 *  Đo trên `traces` thật: `claims_after_tier2` tối đa 154, một lượt `answer`
 *  từng có 71 trích dẫn — vượt trần này chứ không phải chuyện lý thuyết.
 *  Khai TẠI ĐÂY thay vì cạnh `TOI_DA_LUOT_LICH_SU`/`TOI_DA_TRA_LOI_LICH_SU`
 *  trong `klaw.ts`: `klaw.ts` đang có một phiên Claude khác sửa song song
 *  trong cùng worktree, hai phiên cùng ghi một file sẽ hỏng file đó. */
export const TOI_DA_DUONG_DAN_LICH_SU = 50;

/**
 * `LuotDaXong[]` của giao diện → `LuotTruoc[]` của hợp đồng API.
 *
 * Bốn việc, mỗi việc vì một lý do đo được:
 *
 * - **Chỉ `TOI_DA_LUOT_LICH_SU` lượt CUỐI.** Quá trần là **422** từ pydantic,
 *   không truncate — gửi cả hội thoại dài là làm chết đúng lượt hỏi nối tiếp.
 * - **Cắt `tra_loi` còn `TOI_DA_TRA_LOI_LICH_SU`.** Máy chủ cắt lại đúng bấy
 *   nhiêu khi dựng prompt, và một câu trả lời ba tầng dễ dài hơn trần 2.000 ký
 *   tự của biên HTTP — không cắt thì cả lượt bị 422 vì câu trả lời TRƯỚC quá dài.
 * - **`duong_dan` từ citations, khử trùng lặp rồi mới cắt còn
 *   `TOI_DA_DUONG_DAN_LICH_SU`.** Đó là thứ định danh chính xác điều khoản
 *   lượt trước đã dẫn, và là cách "liệt kê bảng cho tôi" biết cái bảng nằm ở
 *   đâu. Nhiều claim cùng dẫn một điều khoản, nên khử trùng (giữ thứ tự xuất
 *   hiện ĐẦU TIÊN) thường đã đưa danh sách xuống dưới trần mà không mất
 *   `duong_dan` PHÂN BIỆT nào; chỉ cắt phần còn dư sau khi đã khử trùng.
 *
 * Thuần, không state — kiểm được mà không cần dựng cả trang.
 */
export function dungLichSu(luot: readonly LuotDaXong[]): LuotTruoc[] {
  return luot.slice(-TOI_DA_LUOT_LICH_SU).map((l) => ({
    cau_hoi: l.cauHoi,
    tra_loi: (l.ketQua.answer ?? "").slice(0, TOI_DA_TRA_LOI_LICH_SU),
    duong_dan: Array.from(new Set(l.ketQua.citations.map((t) => t.duong_dan))).slice(
      0,
      TOI_DA_DUONG_DAN_LICH_SU,
    ),
  }));
}
