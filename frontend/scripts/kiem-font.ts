/**
 * Kiểm chạy được cho chữ TỰ HOST.
 *
 * Font là chỗ hỏng ÂM THẦM nhất trong toàn bộ giao diện: một `@font-face` trỏ
 * vào tệp không tồn tại không ném lỗi, không hiện cảnh báo, không làm gãy
 * build — trình duyệt lặng lẽ tụt xuống `serif` của hệ điều hành và trang vẫn
 * đọc được, chỉ là không còn ra dáng gì nữa. Không ai phát hiện cho tới khi có
 * người nhìn ảnh chụp cũ.
 *
 * Ba điều được chốt ở đây:
 *
 * 1. **Không host bên thứ ba.** Một dòng `fonts.googleapis.com` sót lại biến
 *    mỗi lượt tải trang thành một lượt gọi ra ngoài — chuyện riêng của người
 *    đọc luật lao động gửi sang máy chủ của bên khác, và một điểm chết khi
 *    mạng chặn.
 * 2. **Mọi họ chữ được dùng đều có `@font-face`.** Khai `font-family:
 *    "Source Serif 4"` mà không nạp nó thì đó là một câu đề nghị, không phải
 *    một lời hứa.
 * 3. **Mọi `src: url()` trỏ vào tệp CÓ THẬT trên đĩa.**
 *
 * Chạy: `npm run kiem-font` (Node 22, 0 thư viện mới).
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const GOC = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CSS = readFileSync(join(GOC, "src/styles.css"), "utf8");

/** Mọi tệp nguồn — CSS lẫn TSX — vì thẻ `<link>` sống trong `__root.tsx`. */
function moiTepNguon(thuMuc: string, gom: string[] = []): string[] {
  for (const ten of readdirSync(thuMuc)) {
    const duong = join(thuMuc, ten);
    if (statSync(duong).isDirectory()) moiTepNguon(duong, gom);
    else if (/\.(tsx?|css|html)$/.test(ten)) gom.push(duong);
  }
  return gom;
}

// 1. Không một tham chiếu nào tới host chữ bên thứ ba, ở bất kỳ tệp nguồn nào.
{
  const CAM = ["fonts.googleapis.com", "fonts.gstatic.com", "fonts.bunny.net", "use.typekit.net"];
  const pham: string[] = [];
  for (const tep of moiTepNguon(join(GOC, "src"))) {
    const noiDung = readFileSync(tep, "utf8");
    for (const host of CAM) {
      if (noiDung.includes(host)) pham.push(`${tep.slice(GOC.length + 1)} → ${host}`);
    }
  }
  assert.deepEqual(pham, [], `còn tham chiếu host chữ bên thứ ba:\n  ${pham.join("\n  ")}`);
}

// 2. Mọi họ chữ ĐƯỢC DÙNG làm lựa chọn đầu tiên đều có `@font-face`.
//    Chỉ xét lựa chọn đầu: `Georgia` và `ui-monospace` là dự phòng của hệ
//    điều hành, không phải thứ ta phải nạp.
{
  const daKhai = new Set(
    [...CSS.matchAll(/@font-face\s*\{[^}]*?font-family:\s*"([^"]+)"/g)].map((m) => m[1]),
  );
  const dungDen = new Set(
    [...CSS.matchAll(/font-family:\s*"([^"]+)"/g)]
      .map((m) => m[1])
      .filter((ten) => ten !== undefined),
  );
  // Tên trong `@theme inline` (`--font-sans: "Be Vietnam Pro", …`) cũng tính.
  for (const khop of CSS.matchAll(/--font-[a-z]+:\s*"([^"]+)"/g)) dungDen.add(khop[1] as string);

  const thieu = [...dungDen].filter((ten) => !daKhai.has(ten));
  assert.deepEqual(thieu, [], `dùng họ chữ chưa có @font-face: ${thieu.join(", ")}`);
  assert.ok(daKhai.size >= 4, `mới khai ${daKhai.size} họ chữ, cần đủ 4`);
}

// 3. Mọi `src: url()` trỏ vào một tệp CÓ THẬT trong `public/`.
{
  const duongDan = [...CSS.matchAll(/url\(["']?(\/fonts\/[^"')]+)["']?\)/g)].map(
    (m) => m[1] as string,
  );
  assert.ok(duongDan.length >= 4, `mới có ${duongDan.length} tệp chữ, cần ít nhất 4`);
  const mat = duongDan.filter((d) => !existsSync(join(GOC, "public", d)));
  assert.deepEqual(mat, [], `@font-face trỏ vào tệp không tồn tại: ${mat.join(", ")}`);
}

// 4. Chữ Việt phải nằm TRONG tệp, không phải trong lời hứa. Bảng `unicode-range`
//    của Google tách riêng dải Việt (U+1EA0–1EF9); nếu ta cắt tập ký tự mà quên
//    dải đó thì mọi dấu tiếng Việt tụt xuống font dự phòng — và toàn bộ sản
//    phẩm này viết bằng tiếng Việt.
{
  const coDaiViet = /U\+1EA0-1EF9/i.test(CSS) || /U\+1ea0/i.test(CSS);
  assert.ok(coDaiViet, "không thấy dải Unicode tiếng Việt (U+1EA0–1EF9) trong bảng @font-face");
}

console.info("kiem-font: 4/4 đạt");
