/** Ngăn xếp drawer xếp chồng (Task 25, spec 2026-09-09 §9.4): trần 3 tầng,
 *  trùng id thì thay tại chỗ, breadcrumb nối bằng " › ". Chạy: `npm run kiem-ngan-xep`. */
import assert from "node:assert/strict";
import { breadcrumb, dongTrenCung, moTam } from "../src/lib/ngan-xep-drawer.ts";

let ngan = moTam([], { id: "m10", tieuDe: "Mục 10", noiDung: null });
ngan = moTam(ngan, { id: "k2", tieuDe: "Khoản 2", noiDung: null });
assert.equal(breadcrumb(ngan), "Mục 10 › Khoản 2");
ngan = moTam(ngan, { id: "c3", tieuDe: "Căn cứ", noiDung: null });
ngan = moTam(ngan, { id: "qua", tieuDe: "Tầng 4", noiDung: null }); // vượt trần 3 → bỏ
assert.equal(ngan.length, 3);
assert.equal(moTam(ngan, { id: "k2", tieuDe: "Khoản 2 (lại)", noiDung: null }).length, 3); // trùng id → thay tại chỗ
ngan = dongTrenCung(ngan);
assert.equal(breadcrumb(ngan), "Mục 10 › Khoản 2");
assert.deepEqual(dongTrenCung([]), []);
console.log("kiem-ngan-xep: 6/6 OK");
