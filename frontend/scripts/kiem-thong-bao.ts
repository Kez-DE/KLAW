/** Chuông người dùng (spec 2B §7): badge, nhóm theo ngày, đường dẫn an toàn. Chạy: `npm run kiem-thong-bao`. */
import assert from "node:assert/strict";
import { duongDanTrongApp, formatBadge, nhomTheoNgay } from "../src/lib/thong-bao.ts";

const tb = (id: number, tao_luc: string) => ({
  id,
  loai: "yeu_cau_duyet",
  tieu_de: "t",
  noi_dung: "n",
  duong_dan: "/tai-khoan",
  da_doc: false,
  tao_luc,
});
assert.equal(formatBadge(0), null);
assert.equal(formatBadge(3), "3");
assert.equal(formatBadge(120), "99+");
const now = new Date(2026, 8, 9, 12);
assert.deepEqual(
  nhomTheoNgay(
    [tb(1, new Date(2026, 8, 1).toISOString()), tb(2, new Date(2026, 8, 9, 8).toISOString())],
    now,
  ).map((n) => n.nhan),
  ["Hôm nay", "Trước đó"],
);
assert.deepEqual(
  nhomTheoNgay([tb(3, new Date(2026, 8, 8, 10).toISOString())], now).map((n) => n.nhan),
  ["Hôm qua"],
);
assert.equal(duongDanTrongApp("/tai-khoan"), "/tai-khoan");
assert.equal(duongDanTrongApp("https://x/y"), "/tai-khoan");
assert.equal(duongDanTrongApp("/dung-thu?x=1"), "/dung-thu?x=1");
console.log("kiem-thong-bao: 8/8");
