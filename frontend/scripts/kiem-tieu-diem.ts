/**
 * Trả tiêu điểm khi sân khấu đóng (WCAG 2.4.3). Ở bố cục hẹp, mở sân khấu tháo
 * CẢ cây chat — nút đã mở nó cũng rời DOM — nên "nút đã mở" không còn để trả
 * về: tìm bản dựng lại của nó (cùng `data-mo-san-khau`), không thì ô hỏi,
 * không bao giờ `<body>`. Chạy: `npm run kiem-tieu-diem`.
 */
import assert from "node:assert/strict";
import { noiTraTieuDiem } from "../src/lib/tieu-diem.ts";

let dat = 0;
let tong = 0;
function kiem(ten: string, fn: () => void) {
  tong += 1;
  try {
    fn();
    dat += 1;
  } catch (loi) {
    console.error(`✗ ${ten}`);
    throw loi;
  }
}

const nut = (isConnected: boolean, khoa: string | null = null) => ({
  isConnected,
  getAttribute: (t: string) => (t === "data-mo-san-khau" ? khoa : null),
});
const oHoi = nut(true);

kiem("nút đã mở còn trong DOM (bố cục rộng) → chính nó", () => {
  const n = nut(true, "ban_thao:b1:v2");
  assert.equal(
    noiTraTieuDiem(n, () => assert.fail("không cần tìm"), oHoi),
    n,
  );
});
kiem("nút đã rời DOM, có bản dựng lại cùng khoá → bản dựng lại", () => {
  const moi = nut(true, "ban_thao:b1:v2");
  const hoi: string[] = [];
  const ra = noiTraTieuDiem(
    nut(false, "ban_thao:b1:v2"),
    (k) => {
      hoi.push(k);
      return moi;
    },
    oHoi,
  );
  assert.equal(ra, moi);
  assert.deepEqual(hoi, ["ban_thao:b1:v2"]);
});
kiem("nút đã rời DOM, không có khoá hay không tìm thấy → ô hỏi", () => {
  assert.equal(
    noiTraTieuDiem(nut(false), () => assert.fail("không khoá thì không tìm"), oHoi),
    oHoi,
  );
  assert.equal(
    noiTraTieuDiem(nut(false, "ban_tai_len:v1"), () => null, oHoi),
    oHoi,
  );
});
kiem("mở không từ nút nào (liên kết `?ban_thao=`) → ô hỏi", () => {
  assert.equal(
    noiTraTieuDiem(null, () => null, oHoi),
    oHoi,
  );
  assert.equal(
    noiTraTieuDiem(null, () => null, null),
    null,
  );
});

console.log(`kiem-tieu-diem: ${dat}/${tong} đạt`);
