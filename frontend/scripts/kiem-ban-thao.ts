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
  LOI_PHIEN_BAN_DA_DOI,
  neenGuiLaiPhienBan,
  nhanFactDoi,
  nhanMucKiem,
  type TruongFact,
} from "../src/lib/klaw.ts";
import { canCuTuBanThao } from "../src/lib/xuat-tep.ts";

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

// ── `nhanMucKiem` — Phase 14 (owner D14-A) bỏ nhãn của bản thảo soạn trong
// chat; Phase 3 (R3/D3) giữ nhãn của một bản thảo CHECKLIST bị sửa tay hạ cấp,
// vì đó là một sự thật khác ("đã bị viết đè SAU khi kiểm") về một bản thảo
// khác. Bản thảo checklist chưa hề sửa tay vẫn không có nhãn (`SoatBanThao`
// đã nói đủ).
assert.equal(nhanMucKiem(undefined, "hdld"), null);
assert.equal(nhanMucKiem({}, "hdld"), null, "checklist chưa sửa tay — không nhãn");
assert.equal(
  nhanMucKiem({ muc_kiem: "tong_quat", sua_tay: true }, "tong_quat"),
  null,
  "D14-A: bản thảo soạn trong chat không đeo nhãn nào, kể cả sau khi sửa tay",
);
assert.equal(
  nhanMucKiem({ muc_kiem: "tong_quat", sua_tay: true }, "hdld"),
  "Đã sửa tay — chưa kiểm pháp lý",
  "hạ cấp một bản thảo CHECKLIST vẫn phải nói ra — D14-A không chạm tới nó",
);

// ── `neenGuiLaiPhienBan` (fix round 2, re-review N1/N2) — retry MỘT lần một
// PATCH bị từ chối vì lệch phiên bản CHỈ khi chênh lệch đó tự client này gây
// ra (một khối khác vừa lưu xong), KHÔNG khi đến từ nơi khác (một lượt sửa
// bằng lời — N1b, `muc_key` đã bị cấp lại, retry sẽ ghi sai mục).
const loiPhienBan = { message: LOI_PHIEN_BAN_DA_DOI };
const loiKhac = { message: "Bản thảo này đã sửa 10 lần. Mở bản mới để tiếp tục." };

// N2: khối khác của CHÍNH client này vừa lưu xong (đã gửi 3, giờ là 4, và 4
// khớp đúng bản do client này tạo ra) → an toàn để tự gửi lại.
assert.equal(neenGuiLaiPhienBan(loiPhienBan, 3, 4, 4), true, "N2: tự gây ra → retry");
// N1b: phiên bản nhảy lên do một lượt sửa bằng lời (không khớp gì client này
// tự lưu) → KHÔNG được tự gửi lại.
assert.equal(neenGuiLaiPhienBan(loiPhienBan, 3, 5, 3), false, "N1b: từ nơi khác → không retry");
// Một lỗi 422 KHÁC (hết trần sửa) dù số có khớp cũng không phải lỗi lệch
// phiên bản — không retry.
assert.equal(neenGuiLaiPhienBan(loiKhac, 3, 4, 4), false, "lỗi khác lệch phiên bản → không retry");
// Không có lỗi (đã thành công) → không áp dụng.
assert.equal(neenGuiLaiPhienBan(null, 3, 4, 4), false, "không lỗi → không retry");

// ── `canCuTuBanThao` (quyết định 2026-09-28, mục 5) — khối "Căn cứ" của máy
// chủ đi vào tờ A4, tức vào tệp tải về. Bản lưu trước trường này, khuôn gốc
// và bản tổng quát không có khối; khoá sai kiểu không ném, không vẽ rác.
const canCu = [
  "Căn cứ Bộ luật Lao động số 45/2019/QH14 ngày 20 tháng 11 năm 2019;",
  "Căn cứ Nghị định số 145/2020/NĐ-CP ngày 14 tháng 12 năm 2020 của Chính phủ.",
];
assert.deepEqual(
  canCuTuBanThao({ ...hopLe, can_cu_van_ban: canCu }),
  canCu,
  "giữ đúng thứ tự máy chủ",
);
assert.deepEqual(canCuTuBanThao(hopLe), [], "bản lưu trước trường này → rỗng");
assert.deepEqual(canCuTuBanThao({ ...hopLe, can_cu_van_ban: "Căn cứ …" }), [], "sai kiểu → rỗng");
assert.deepEqual(
  canCuTuBanThao({ ...hopLe, can_cu_van_ban: [canCu[0], 7, null, "  "] }),
  [canCu[0]],
  "phần tử không phải chữ hoặc rỗng bị bỏ",
);

console.info("kiem-ban-thao: 21/21 đạt");
