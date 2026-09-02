/**
 * Kiểm chạy được cho `ngayVietNam` — đổi ngày ISO của máy chủ sang cách viết
 * Việt Nam.
 *
 * Vì sao một hàm bốn dòng đáng có kiểm riêng: nó in NGÀY TRONG VĂN BẢN PHÁP
 * LÝ — ngày bắt đầu và kết thúc hợp đồng, ngày sinh, ngày cấp giấy tờ
 * (`soan-thao.$loaiVanBan.tsx`). Lệch một ngày ở đó là một hợp đồng sai, và
 * cái sai đó đi thẳng vào bản thảo người dùng tải về.
 *
 * Lý do ban đầu là ô chọn `as_of_date` — ô đó đã gỡ theo quyết định của chủ
 * dự án, nhưng hàm và kiểm này thì không mất giá trị: chỗ dùng thật đã đổi,
 * hệ quả của việc in sai thì không.
 *
 * Chạy: `npm run kiem-ngay`.
 */
import assert from "node:assert/strict";
import { ngayVietNam } from "../src/lib/utils.ts";

// 1. Ca thường.
assert.equal(ngayVietNam("2026-01-01"), "01/01/2026");
assert.equal(ngayVietNam("2019-06-01"), "01/06/2019");

// 2. Giữ số 0 đứng đầu. "1/6/2019" là một cách viết khác, không phải cách viết
//    này, và trộn hai cách trong cùng một màn hình làm người đọc phải đoán.
assert.equal(ngayVietNam("2026-09-07"), "07/09/2026");

// 3. KHÔNG đi qua `Date`. Đây là lý do hàm này tồn tại: `new Date("2026-01-01")`
//    phân giải là nửa đêm UTC, và `toLocaleDateString` in theo múi giờ của MÁY
//    người dùng — ở UTC−5 sẽ ra 31/12/2025. Kiểm bằng cách chạy 366 ngày liên
//    tiếp: mọi ngày phải in lại đúng chính nó, không lệch một ngày nào.
{
  let ngay = Date.UTC(2024, 0, 1); // 2024 là năm nhuận — có 29/02
  for (let i = 0; i < 366; i += 1) {
    const iso = new Date(ngay).toISOString().slice(0, 10);
    const parts = iso.split("-");
    assert.equal(ngayVietNam(iso), `${parts[2]}/${parts[1]}/${parts[0]}`, `lệch tại ${iso}`);
    ngay += 86_400_000;
  }
  assert.equal(ngayVietNam("2024-02-29"), "29/02/2024");
}

// 4. Chuỗi KHÔNG đúng dạng trả về nguyên văn. Thà hiện thứ máy chủ gửi còn hơn
//    hiện "NaN/NaN/NaN" hoặc — tệ hơn — một ngày trông hợp lệ mà sai.
for (const rac of ["", "hôm nay", "2026", "2026-01", "01/01/2026", "2026-1-1", "abcd-ef-gh"]) {
  assert.equal(ngayVietNam(rac), rac, `${JSON.stringify(rac)} phải trả nguyên văn`);
}

// 5. Dạng ngày-giờ đầy đủ cũng KHÔNG đúng dạng. Cắt chuỗi ngây thơ bằng
//    `split("-")` sẽ cho "01T00:00:00Z/01/2026" — một chuỗi vô nghĩa hiện ra
//    đúng chỗ mà người đọc đang tìm ngày để tin.
assert.equal(ngayVietNam("2026-01-01T00:00:00Z"), "2026-01-01T00:00:00Z");

console.info("kiem-ngay: 5/5 đạt");
