/** Dòng "Dựa trên", bộ nhớ tài khoản, công tắc ghi nhớ phiên (spec 2026-09-09
 *  §6.6): trần lịch sử = 10, và hai guard mới không đổi hành vi lẫn nhau.
 *  Chạy: `npm run kiem-bo-nho`. */
import assert from "node:assert/strict";
import {
  TOI_DA_LUOT_LICH_SU,
  laBoNhoTaiKhoan,
  laDanhSachDaNho,
  laHoSoPhienOut,
} from "../src/lib/klaw.ts";
import { dungLichSu } from "../src/lib/lich-su.ts";

assert.equal(TOI_DA_LUOT_LICH_SU, 10);
const luot = Array.from({ length: 12 }, (_, i) => ({
  cauHoi: `c${i}`,
  ketQua: {
    result_type: "answer",
    answer: "a",
    citations: [],
    nguon: [],
    warnings: [],
    coverage_note: null,
    trace_id: "t",
    cau_hoi_day_du: null,
    bang: [],
    documents: [],
  },
}));
assert.equal(dungLichSu(luot as never).length, 10);
assert.ok(laBoNhoTaiKhoan({ ghi_nho: true, muc: [] }));
assert.ok(!laBoNhoTaiKhoan({ muc: [] }));
assert.ok(laHoSoPhienOut({ ho_so_da_dung: [] }));
// Phase 12 — /tai-khoan/da-nho: mảng rỗng qua, mục thiếu `id` (không xoá được) bị chặn.
assert.ok(laDanhSachDaNho({ muc: [] }));
assert.ok(laDanhSachDaNho({ muc: [{ id: "x", nhan: "Họ và tên", gia_tri: "Nguyễn Văn Thử" }] }));
assert.ok(!laDanhSachDaNho({ muc: [{ nhan: "Họ và tên", gia_tri: "Nguyễn Văn Thử" }] }));
console.log("kiem-bo-nho: 8/8 OK");
