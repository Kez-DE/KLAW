/**
 * `boQuaKhiXuat` — luật lọc phần tử của `docNoiDungTuDOM` (xuat-tep.ts).
 *
 * Dòng `Căn cứ:` trong khung xem trước A4 bật/tắt bằng công tắc "Hiển thị căn
 * cứ" và là một `<p>` y như mọi đoạn khác; trước bản vá này nó chảy thẳng vào
 * tệp `.docx` tải về, tức một công tắc XEM TRƯỚC đổi được nội dung một văn bản
 * pháp lý. Pin ở đây giữ ba nhánh của luật lọc. Chạy: `npm run kiem-xuat-tep`.
 */
import assert from "node:assert/strict";
import { boQuaKhiXuat } from "../src/lib/xuat-tep.ts";

/** Phần tử giả tối thiểu: `docNoiDungTuDOM` chỉ hỏi đúng hai thứ này. */
const el = (tagName: string, trongKhoiKhongXuat = false) => ({
  tagName,
  closest: (chon: string) =>
    chon === "[data-khong-xuat]" && trongKhoiKhongXuat ? { tagName: "SECTION" } : null,
});

// Đoạn văn thường của văn bản → VÀO tệp.
assert.equal(boQuaKhiXuat(el("P")), false);
assert.equal(boQuaKhiXuat(el("H1")), false);

// Thẻ kỹ thuật → không bao giờ vào tệp (hành vi cũ, giữ nguyên).
assert.equal(boQuaKhiXuat(el("SCRIPT")), true);
assert.equal(boQuaKhiXuat(el("STYLE")), true);

// Nằm TRONG một khối `data-khong-xuat` (dòng `Căn cứ:`) → bị loại, kể cả khi
// bản thân nó là một `<p>` hợp lệ về mọi mặt khác.
assert.equal(boQuaKhiXuat(el("P", true)), true);

console.info("kiem-xuat-tep: 5/5 đạt");
