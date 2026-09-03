/**
 * Kiểm chạy được cho phần `bang` của `chuanHoaBang` + `laTraCuuKetQua` (T5,
 * vòng fix 1) — validator, KHÔNG phải `lib/bang.ts` (bộ đọc bảng trong NGUYÊN
 * VĂN điều khoản, đã có kiểm riêng ở `kiem-bang.ts`). Tên khác để không đè lên
 * script đó.
 *
 * Từ vòng fix 1: `chuanHoaBang` chuẩn hoá `bang` (THUẦN), `laTraCuuKetQua` chỉ
 * còn là predicate thuần — đúng thứ tự gọi thật ở `api.ts`. Ba bất biến ở đây
 * hỏng ÂM THẦM nếu thiếu kiểm:
 *
 *   1. Payload CŨ (dựng trước khi `bang` tồn tại, ví dụ nằm trong cache) phải
 *      vẫn đọc được — thiếu khoá này không được làm sập cả thẻ kết quả.
 *   2. Một `Bang` có `dong` lệch số cột so với `cot` phải bị loại NGUYÊN CẢ
 *      BẢNG, không được lọt xuống component: một hàng thiếu ô hiện ra thành
 *      bảng méo chứ không thành lỗi, và không ai biết.
 *   3. Cả hai hàm đều không được sửa bản ghi chúng đang đọc/kiểm.
 *
 * Chạy: `npm run kiem-bang-ket-qua` (Node đọc thẳng TypeScript, 0 thư viện mới).
 */
import assert from "node:assert/strict";

import { chuanHoaBang, laTraCuuKetQua, type TraCuuKetQua } from "../src/lib/klaw.ts";

/** Payload thô tối thiểu — đủ để qua các kiểm khác của `laTraCuuKetQua`. */
function phanHoi(them: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    result_type: "hoi_ve_kho",
    answer: "đáp",
    citations: [],
    warnings: [],
    trace_id: "t",
    ...them,
  };
}

// Luồng thật (`api.ts`) luôn gọi `chuanHoaBang` TRƯỚC `laTraCuuKetQua` — guard
// giờ là một predicate thuần, không còn tự chuẩn hoá `bang`. Mọi ca dưới đây
// mô phỏng đúng thứ tự đó.

// 1. Thiếu hẳn khoá `bang` (payload cũ, cache trước T5) — vẫn phải qua kiểm,
// và phải rơi về mảng rỗng chứ không phải `undefined`.
{
  const tho = phanHoi();
  assert.equal("bang" in tho, false, "ca này phải THIẾU khoá bang để mô phỏng đúng payload cũ");
  const chuanHoa = chuanHoaBang(tho);
  assert.equal("bang" in tho, false, "chuanHoaBang không được sửa bản ghi gốc");
  assert.ok(laTraCuuKetQua(chuanHoa), "thiếu khoá bang không được làm cả response bị từ chối");
  const kq = chuanHoa as TraCuuKetQua;
  assert.deepEqual(kq.bang, [], "bang vắng mặt phải rơi về mảng rỗng");
}

// 2. `bang` hợp lệ (mọi dong khớp số cột) phải được GIỮ NGUYÊN.
{
  const tho = phanHoi({
    bang: [
      { tieu_de: "Phân theo loại văn bản", cot: ["Loại", "Tổng"], dong: [["Nghị định", "5"]] },
    ],
  });
  const chuanHoa = chuanHoaBang(tho);
  assert.ok(laTraCuuKetQua(chuanHoa));
  const kq = chuanHoa as TraCuuKetQua;
  assert.equal(kq.bang.length, 1, "bảng hợp lệ không được bị loại");
  assert.deepEqual(kq.bang[0]?.dong, [["Nghị định", "5"]]);
}

// 3. Một `Bang` có MỘT hàng lệch số cột phải bị loại NGUYÊN CẢ BẢNG đó —
// không được cắt/độn ô cho khớp, không được đẩy nguyên bảng méo xuống dưới.
{
  const tho = phanHoi({
    bang: [
      {
        tieu_de: "Phân theo lĩnh vực",
        cot: ["Lĩnh vực", "Số văn bản", "Độ sâu"],
        dong: [
          ["Lao động", "42", "đủ luật, nghị định, thông tư"],
          ["Hàng hải", "3"], // thiếu một ô — cả bảng này phải bị loại
        ],
      },
    ],
  });
  const chuanHoa = chuanHoaBang(tho);
  assert.ok(laTraCuuKetQua(chuanHoa));
  const kq = chuanHoa as TraCuuKetQua;
  assert.deepEqual(
    kq.bang,
    [],
    "bảng có hàng lệch cột phải bị loại nguyên cả bảng, không phải một hàng",
  );
}

// 4. Bảng lệch cột và bảng hợp lệ đứng CẠNH NHAU trong cùng payload — chỉ
// bảng lệch bị loại, bảng hợp lệ còn lại phải nguyên vẹn.
{
  const tho = phanHoi({
    bang: [
      { tieu_de: "Hợp lệ", cot: ["A", "B"], dong: [["1", "2"]] },
      { tieu_de: "Méo", cot: ["A", "B"], dong: [["1", "2", "3"]] },
    ],
  });
  const chuanHoa = chuanHoaBang(tho);
  assert.ok(laTraCuuKetQua(chuanHoa));
  const kq = chuanHoa as TraCuuKetQua;
  assert.equal(kq.bang.length, 1, "chỉ bảng méo bị loại, bảng hợp lệ phải còn lại");
  assert.equal(kq.bang[0]?.tieu_de, "Hợp lệ");
}

// 5. Nhóm "lĩnh vực chưa biết" mang ô đầu là CHUỖI RỖNG (không phải thiếu ô,
// không phải null) — đây là dữ liệu kho THẬT (`linh_vuc IS NULL` gộp về `""`
// ở `dung_bang`), không phải một hàng lệch cột, nên KHÔNG được bị loại.
{
  const tho = phanHoi({
    bang: [
      {
        tieu_de: "Phân theo lĩnh vực",
        cot: ["Lĩnh vực", "Số văn bản", "Độ sâu"],
        dong: [["", "1", "chỉ số hiệu và tên"]],
      },
    ],
  });
  const chuanHoa = chuanHoaBang(tho);
  assert.ok(laTraCuuKetQua(chuanHoa));
  const kq = chuanHoa as TraCuuKetQua;
  assert.equal(
    kq.bang.length,
    1,
    "hàng có ô rỗng (đủ số cột) không phải hàng lệch cột — không bị loại",
  );
}

// 6. `laTraCuuKetQua` tự nó phải THUẦN — gọi guard trên một bản ghi ĐÃ chuẩn
// hoá không được sửa lại bản ghi đó (không có `x["bang"] = ...` bên trong).
{
  const tho = chuanHoaBang(
    phanHoi({ bang: [{ tieu_de: "T", cot: ["A"], dong: [["1"]] }] }),
  ) as Record<string, unknown>;
  const truoc = JSON.stringify(tho);
  laTraCuuKetQua(tho);
  assert.equal(JSON.stringify(tho), truoc, "laTraCuuKetQua không được sửa đối tượng nó đang kiểm");
}

console.log("kiem-bang-ket-qua: OK");
