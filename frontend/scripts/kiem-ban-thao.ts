/**
 * `laBanThao`/`laDanhSachBanThao` (kiểu `BanThao`/`BanThaoTomTat`, Task 21) và
 * `laTraCuuKetQua` chấp nhận `result_type: "ban_thao"`/`"soan_thao_hoi"` —
 * trước Task 21 hai guard này không tồn tại, nên script này đỏ ngay ở bước
 * biên dịch. Chạy: `npm run kiem-ban-thao`.
 */
import assert from "node:assert/strict";
import { laBanThao, laDanhSachBanThao, laTraCuuKetQua } from "../src/lib/klaw.ts";

/** Ba mẫu: hợp lệ, thiếu trường bắt buộc, và không phải bản ghi. */
const hopLe = {
  id: "b1",
  loai: "hdld",
  ten: "Hợp đồng lao động",
  phien_ban: 2,
  document: "# Hợp đồng…",
  clauses: [],
  audit_report: {},
  facts: {},
  doi_so_voi_truoc: ["luong"],
};
const thieuTruong = { ...hopLe, document: undefined };
const khongPhaiBanGhi = [hopLe];

assert.equal(laBanThao(hopLe), true);
assert.equal(laBanThao(thieuTruong), false);
assert.equal(laBanThao(khongPhaiBanGhi), false);

assert.equal(laDanhSachBanThao({ tong: 1, items: [hopLe] }), true);
assert.equal(laDanhSachBanThao({ tong: 1 }), false); // thiếu `items`
assert.equal(laDanhSachBanThao(null), false);

const NEN = { citations: [], warnings: [], trace_id: "t1" };
assert.equal(laTraCuuKetQua({ ...NEN, result_type: "ban_thao" }), true);
assert.equal(laTraCuuKetQua({ ...NEN, result_type: "soan_thao_hoi" }), true);

console.info("kiem-ban-thao: 8/8 đạt");
