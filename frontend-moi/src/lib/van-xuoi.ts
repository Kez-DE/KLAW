/**
 * Cắt văn xuôi của câu trả lời thành đoạn và danh sách.
 *
 * Backend viết theo giọng luật sư từ 2026-09-01: câu trả lời dài hơn, có xuống
 * dòng, và có danh sách gạch đầu dòng ("Dưới đây là 04 điều kiện cốt lõi:" rồi
 * liệt kê). Trước đó mọi dòng đều thành một `<p>`, nên một danh sách bốn mục
 * hiện ra thành bốn đoạn rời không thụt lề, không chấm đầu dòng — đọc được,
 * nhưng mất hẳn cấu trúc mà máy chủ cố ý tạo ra.
 *
 * ## Hai điều hàm này KHÔNG làm
 *
 * 1. **Không sửa chữ.** Nó chỉ cắt và gỡ ký tự gạch đầu dòng. Câu trả lời nay
 *    mang số Điều ngay trong lời văn — `(Điều 25, Khoản 1)` — và đó là CĂN CỨ,
 *    không phải trang trí. Mọi phép rút gọn, chuẩn hoá dấu, hay đổi nháy đều
 *    bị cấm ở đây; `scripts/kiem-van-xuoi.ts` gãy nếu ai thêm vào.
 * 2. **Không nhận danh sách ĐÁNH SỐ.** `1.` ở đầu dòng cũng là cách văn bản
 *    quy phạm mở đầu một Khoản, và nhận nhầm sẽ biến nguyên văn thành danh
 *    sách. Máy chủ hiện chỉ phát gạch đầu dòng — thêm nhánh số khi nó đổi.
 */

export type Doan = { kieu: "doan"; chu: string } | { kieu: "danh_sach"; muc: string[] };

/**
 * Ký tự mở một mục.
 *
 * Ràng buộc quan trọng nhất là `^` cộng với khoảng trắng bắt buộc phía sau:
 * "Bộ Lao động - Thương binh và Xã hội" có dấu gạch GIỮA câu, và một biểu thức
 * lỏng hơn sẽ cắt tên cơ quan làm đôi.
 */
const DAU_MUC = /^[-–—•*]\s+/;

/** Một dòng chỉ có mỗi ký tự gạch: vẫn là ý định liệt kê, nhưng rỗng ruột. */
const CHI_DAU_MUC = /^[-–—•*]\s*$/;

export function catDoan(vanXuoi: string): Doan[] {
  const ra: Doan[] = [];
  let dangGom: string[] | null = null;

  const chot = () => {
    if (dangGom === null) return;
    if (dangGom.length > 0) ra.push({ kieu: "danh_sach", muc: dangGom });
    dangGom = null;
  };

  for (const tho of vanXuoi.split("\n")) {
    const dong = tho.trim();
    if (dong === "") continue;

    if (CHI_DAU_MUC.test(dong)) {
      // Mở một danh sách (hoặc ở lại trong danh sách đang mở) nhưng không thêm
      // mục rỗng: một chấm đầu dòng không có chữ là một ô trống trên màn hình.
      dangGom ??= [];
      continue;
    }

    if (DAU_MUC.test(dong)) {
      dangGom ??= [];
      dangGom.push(dong.replace(DAU_MUC, ""));
      continue;
    }

    chot();
    ra.push({ kieu: "doan", chu: dong });
  }
  chot();
  return ra;
}
