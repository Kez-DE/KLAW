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

// ── `nhanMucKiem` (Phase 3, R3/D3) — một sửa TAY hạ cấp một bản thảo phải
// đọc ra một nhãn KHÁC "chưa từng sửa" (brief: "the two are not the same
// thing"), và một bản thảo checklist chưa hề sửa tay vẫn không có nhãn nào
// (`SoatBanThao` đã nói đủ).
assert.equal(nhanMucKiem(undefined), null);
assert.equal(nhanMucKiem({}), null, "checklist chưa sửa tay — không nhãn");
assert.equal(nhanMucKiem({ muc_kiem: "tong_quat" }), "Bản thảo tổng quát — chưa kiểm pháp lý");
assert.equal(
  nhanMucKiem({ muc_kiem: "tong_quat", sua_tay: true }),
  "Đã sửa tay — chưa kiểm pháp lý",
  "hạ cấp bằng sửa tay phải khác nhãn của một bản thảo tổng quát CHƯA sửa",
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

console.info("kiem-ban-thao: 17/17 đạt");
