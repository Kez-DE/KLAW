/**
 * Kiểm chạy được cho phần nhớ thông báo đã tắt (spec 2026-09-15e).
 *
 * Vì sao mấy hàm ngắn này đáng có kiểm: khoá nhớ mà không gắn ngày hết hạn thì
 * người dùng tắt MỘT LẦN là không bao giờ thấy lại — kể cả sau khi gia hạn rồi
 * hết hạn tiếp. Họ mất lượt mà không biết vì sao, và không ai truy ra được.
 *
 * Chạy: `npm run kiem-tat-thong-bao`.
 */
import assert from "node:assert/strict";
import { daTat, ghiNhoDaTat, khoaHetHan } from "../src/lib/tat-thong-bao.ts";

// 1. Hai lần hết hạn KHÁC NHAU cho hai khoá khác nhau. Đây là dòng quan trọng
//    nhất file này.
assert.notEqual(khoaHetHan("09/09/2026"), khoaHetHan("09/10/2026"));

// 2. Cùng một ngày luôn cho cùng một khoá, kể cả khi có khoảng trắng thừa.
assert.equal(khoaHetHan("09/09/2026"), khoaHetHan("  09/09/2026  "));

// 3. Ngày rỗng vẫn ra một khoá dùng được, không ra khoá rỗng.
assert.ok(khoaHetHan("").length > "klaw.tat-thong-bao.het-han.".length);

// 4. Khoá có tiền tố chung để dọn được hàng loạt sau này.
assert.ok(khoaHetHan("09/09/2026").startsWith("klaw.tat-thong-bao."));

// 5. KHÔNG có `localStorage` (đúng môi trường node này) thì `daTat` trả false
//    chứ không ném. Cửa sổ ẩn danh và trình duyệt chặn site data hỏng y hệt,
//    và một thông báo không tắt được vẫn hơn một trang trắng.
assert.equal(typeof globalThis.window, "undefined");
assert.equal(daTat(khoaHetHan("09/09/2026")), false);
ghiNhoDaTat(khoaHetHan("09/09/2026")); // không được ném

// 6. Có `localStorage` thì ghi rồi đọc lại phải khớp.
{
  const kho = new Map<string, string>();
  (globalThis as { window?: unknown }).window = {
    localStorage: {
      getItem: (k: string) => kho.get(k) ?? null,
      setItem: (k: string, v: string) => void kho.set(k, v),
    },
  };
  const k = khoaHetHan("09/09/2026");
  assert.equal(daTat(k), false);
  ghiNhoDaTat(k);
  assert.equal(daTat(k), true);
  assert.equal(daTat(khoaHetHan("09/10/2026")), false, "lần hết hạn SAU phải hiện lại");
}

// 7. `localStorage` ném (site data bị chặn) thì cả hai hàm vẫn im lặng.
{
  (globalThis as { window?: unknown }).window = {
    get localStorage(): never {
      throw new DOMException("bị chặn");
    },
  };
  assert.equal(daTat(khoaHetHan("09/09/2026")), false);
  ghiNhoDaTat(khoaHetHan("09/09/2026"));
}

console.log("kiem-tat-thong-bao: OK");
