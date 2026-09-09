/** Giá và chữ hạn mức của gói (spec quota v3, Task 1 backend 211e239): giá Cá
 *  nhân 69.000đ/30 ngày, Miễn phí 100 lượt/ngày + 30 lượt/phiên, Cá nhân 500
 *  lượt/ngày + không giới hạn phiên. Chạy: `npm run kiem-goi`. */
import assert from "node:assert/strict";
import { GIA_PRO, GOI_CARD } from "../src/lib/goi.ts";

assert.equal(GIA_PRO, 69_000);
assert.equal(GOI_CARD.pro.gia, "₫69.000 / 30 ngày");
assert.equal(GOI_CARD.free.danhSach[0]?.chu, "100 lượt hỏi đáp mỗi ngày");
assert.equal(GOI_CARD.free.danhSach[1]?.chu, "30 lượt mỗi phiên");
assert.equal(GOI_CARD.pro.danhSach[0]?.chu, "500 lượt hỏi đáp mỗi ngày");
assert.equal(GOI_CARD.pro.danhSach[1]?.chu, "Không giới hạn lượt mỗi phiên");
assert.equal(GOI_CARD.pro.danhSach[3]?.chu, "Trí nhớ hoàn cảnh xuyên phiên");
for (const goi of Object.values(GOI_CARD)) {
  for (const d of goi.danhSach) assert.ok(!d.chu.includes("*"), `còn dấu sao: ${d.chu}`);
}
console.log("kiem-goi: 8/8 OK");
