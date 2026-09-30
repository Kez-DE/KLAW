/** Dòng "Dựa trên", bộ nhớ tài khoản, công tắc ghi nhớ phiên (spec 2026-09-09
 *  §6.6): trần lịch sử = 10, và hai guard mới không đổi hành vi lẫn nhau.
 *  Chạy: `npm run kiem-bo-nho`. */
import assert from "node:assert/strict";
import {
  TOI_DA_LUOT_LICH_SU,
  hoSoTrenDong,
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
// Sửa một chip: PATCH trả hồ sơ CẢ PHIÊN, kể cả nền tài khoản mà lượt đó không dùng
// (bản thảo thuê nhà). Dòng của lượt chỉ giữ khoá nó đang hiện; khoá bị xoá thì rơi.
const d = (khoa: string, gia_tri: string) => ({ khoa, nhan: khoa, gia_tri, gia_dinh: false });
const phien = [
  d("chu_the", "người thuê nhà"),
  d("vung_luong", "Ocenpark"),
  d("tham_nien", "12 tháng"),
];
assert.deepEqual(hoSoTrenDong([d("chu_the", "người cho thuê")], phien), [
  d("chu_the", "người thuê nhà"),
]);
assert.deepEqual(hoSoTrenDong([d("chu_the", "x"), d("thoi_diem", "y")], phien), [
  d("chu_the", "người thuê nhà"),
]);
console.log("kiem-bo-nho: 10/10 OK");
