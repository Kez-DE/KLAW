/**
 * `laBanThao`/`laDanhSachBanThao` (kiểu `BanThao`/`BanThaoTomTat`, Task 21) và
 * `laTraCuuKetQua` chấp nhận `result_type: "ban_thao"`/`"soan_thao_hoi"` —
 * trước Task 21 hai guard này không tồn tại, nên script này đỏ ngay ở bước
 * biên dịch. Chạy: `npm run kiem-ban-thao`.
 */
import assert from "node:assert/strict";
import {
  laBanThao,
  laDanhSachBanThao,
  laTraCuuKetQua,
  nhanFactDoi,
  type TruongFact,
} from "../src/lib/klaw.ts";

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

// ── `nhanFactDoi`: nhãn cho `doi_so_voi_truoc` (Task 24 fix, coordinator
// review) — chốt rằng khoá của mảng này là khoá FIELD (`TruongFact.key`, từ
// `GET /mau/{loai}`), KHÔNG PHẢI khoá MỤC (`MucCauTruc.key`/`Muc.key`). Hai
// không gian khoá DO TRÙNG TÊN ở một số checklist thật (vd. "luong" vừa là
// field vừa là mục của HĐLĐ) khiến việc tô "mục vừa đổi" từng trông có vẻ
// đúng — pin này giữ cho phần chữ hiện đúng NHÃN FIELD, và bất kỳ ai nối
// nhầm hàm này với `Muc[]`/`CauTruc` sẽ bị `tsc` chặn (chữ ký chỉ nhận
// `TruongFact[]`, `Muc` thiếu `nhan`/`kieu`/`bat_buoc`/`lua_chon`).
const TRUONG: TruongFact[] = [
  { key: "luong", nhan: "Mức lương thoả thuận", kieu: "tien", bat_buoc: true, lua_chon: null },
];
assert.deepEqual(nhanFactDoi(["luong", "chua_co_nhan_field"], TRUONG), [
  "Mức lương thoả thuận", // khớp field → nhãn CỦA FIELD, không phải tên một mục nào
  "chua_co_nhan_field", // field mẫu chưa nạp/không có nhãn → giữ khoá thô, KHÔNG suy đoán
]);

console.info("kiem-ban-thao: 9/9 đạt");
