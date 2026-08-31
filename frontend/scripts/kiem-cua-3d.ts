/**
 * Tự kiểm CỬA 768px của hero 3D — bất biến chịu lực nhất của cả trang giới thiệu:
 * **chunk WebGL không bao giờ tới được máy di động.**
 *
 * Vì sao bất biến này cần một test chứ không cần một chú thích:
 * `research-zoom-3d.md` §8 loại Three.js khỏi MỌI màn hình, vì chi phí của nó
 * thuộc hạng cân khác với nhóm "điện thoại đời cũ, mạng yếu" — một trong ba nhóm
 * người dùng chính của KLAW. Chủ dự án lật quyết định đó, và cửa 768px là TOÀN BỘ
 * thứ giữ cho lựa chọn kia không thành đúng cái lỗi mà nghiên cứu đã dự đoán.
 *
 * Kiểu hồi quy phải chặn: ai đó dọn code, gỡ một điều kiện hoặc đổi một
 * `import()` động thành import tĩnh. Không lỗi nào nổ, không test nào đỏ, TypeScript
 * vẫn xanh, giao diện desktop vẫn y nguyên — và người lao động trên mạng yếu bắt
 * đầu tải 297 kB gzip. Đó là loại hồi quy im lặng nhất có thể có.
 *
 * Vì thế kiểm ARTIFACT BUILD, không kiểm mã nguồn: điều cần bảo vệ là "chunk 3D
 * không tới được máy di động", và chỉ bản build nói được điều đó. Mã nguồn trông
 * đúng mà bundler vẫn có thể gộp `three` vào chunk entry (ví dụ ai đó import một
 * type từ `hero3d/` vào một module nạp sẵn).
 *
 * Chạy:  npm run build && node frontend/scripts/kiem-cua-3d.ts
 * (Node ≥ 22.18 tự bóc kiểu; không test framework, không cài gì thêm.)
 */

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const GOC = fileURLToPath(new URL('../../', import.meta.url));
const THU_MUC_BUILD = join(GOC, 'src', 'static');
const ASSETS = join(THU_MUC_BUILD, 'assets');
const NGUON = join(GOC, 'frontend', 'src');

/** Breakpoint của cửa. Phải khớp `@media (min-width: 48rem)` trong gioi-thieu.css. */
const NGUONG = '48rem';

/**
 * Dấu vết của `three` / R3F / drei / troika trong mã đã minify.
 *
 * Đây là tên class và chuỗi ký tự sống sót qua minify (đã kiểm trên chính bản
 * build này, không đoán). Phép kiểm B dưới đây bắt buộc chúng phải CÓ trong chunk
 * 3D — nghĩa là nếu một bản nâng `three` đổi hết các chuỗi này, test sẽ ĐỎ ở B chứ
 * không lặng lẽ ĐẠT ở A. Một fingerprint chết mà vẫn xanh là cách tệ nhất để test
 * này hỏng, nên nó tự canh chính mình.
 */
const DAU_VET = [
  'WebGLRenderer',
  'MeshPhysicalMaterial',
  'BufferGeometry',
  'PMREMGenerator',
  'troika',
];

let hong = 0;

function kiem(ten: string, dung: boolean, chiTiet = ''): void {
  if (!dung) {
    hong += 1;
    process.stderr.write(`HONG: ${ten}${chiTiet === '' ? '' : ` — ${chiTiet}`}\n`);
  }
}

if (!existsSync(join(THU_MUC_BUILD, 'index.html'))) {
  process.stderr.write(
    `HONG: chua co ban build tai ${THU_MUC_BUILD}. Chay \`npm run build\` truoc.\n`,
  );
  process.exit(1);
}

const html = readFileSync(join(THU_MUC_BUILD, 'index.html'), 'utf8');
const doc = (ten: string): string => readFileSync(join(ASSETS, ten), 'utf8');
const moiChunk = readdirSync(ASSETS).filter((t) => t.endsWith('.js'));

/** Tên file js trong một href/src dạng `/assets/x-hash.js`. */
function tenTuDuongDan(d: string): string | null {
  const m = /\/assets\/([\w.-]+\.js)$/.exec(d);
  return m === null ? null : m[1];
}

// ── Đồ thị NẠP SẴN: entry + mọi thứ nó modulepreload + bao đóng import TĨNH ────
//
// Bất cứ thứ gì trong tập này đều xuống dây ở MỌI khổ màn hình, kể cả 390px.
const hatGiong = new Set<string>();
for (const m of html.matchAll(/<script[^>]*\ssrc="([^"]+)"/g)) {
  const t = tenTuDuongDan(m[1]);
  if (t !== null) hatGiong.add(t);
}
for (const m of html.matchAll(/<link[^>]*rel="modulepreload"[^>]*href="([^"]+)"/g)) {
  const t = tenTuDuongDan(m[1]);
  if (t !== null) hatGiong.add(t);
}

kiem('index.html có ít nhất một script entry', hatGiong.size > 0);

/** Import TĨNH: `from"./x.js"` hoặc `import"./x.js"`. CỐ Ý không khớp `import(` —
 *  import động là đúng thứ bất biến này dựa vào, không phải thứ nó truy.
 *
 *  Nhận cả ba kiểu dấu nháy. Rolldown hiện phát ra import tĩnh bằng `"` và đường
 *  dẫn import ĐỘNG bằng backtick; nếu chỉ khớp `"` và `'` thì phép kiểm C không
 *  thấy import động nào (đã gặp thật), còn phép kiểm A thì tệ hơn — nó sẽ đi thiếu
 *  đồ thị nạp sẵn và ĐẠT một cách rỗng. */
function importTinh(ma: string): string[] {
  const ra: string[] = [];
  for (const m of ma.matchAll(/(?:\bfrom|\bimport)\s*["'`]\.\/([\w.-]+\.js)["'`]/g)) ra.push(m[1]);
  return ra;
}

const napSan = new Set<string>();
const hangDoi = [...hatGiong];
while (hangDoi.length > 0) {
  const ten = hangDoi.pop() as string;
  if (napSan.has(ten)) continue;
  napSan.add(ten);
  for (const con of importTinh(doc(ten))) if (!napSan.has(con)) hangDoi.push(con);
}

// ── A. Đồ thị nạp sẵn KHÔNG chứa three/drei/fiber/troika ──────────────────────
//
// Phép kiểm chịu lực. Nó đỏ khi ai đó đổi `lazy(() => import(...))` thành import
// tĩnh, hoặc import bất cứ gì từ `hero3d/` vào một module nạp sẵn.
const banTay: string[] = [];
for (const ten of napSan) {
  const ma = doc(ten);
  const thay = DAU_VET.filter((d) => ma.includes(d));
  if (thay.length > 0) banTay.push(`${ten} [${thay.join(', ')}]`);
}
kiem(
  'A · đồ thị nạp sẵn không chứa dấu vết 3D nào',
  banTay.length === 0,
  banTay.length === 0 ? '' : `chunk nạp sẵn có 3D: ${banTay.join(' · ')}`,
);

// ── B. Chunk 3D CÓ tồn tại và CÓ chứa dấu vết ─────────────────────────────────
//
// Không có B thì A đạt một cách rỗng: xoá hẳn cảnh 3D cũng làm A xanh. B cũng là
// chỗ canh chính bộ fingerprint — đổi three mà chuỗi đổi theo thì đỏ ở đây.
const chunk3D = moiChunk.filter((t) => DAU_VET.some((d) => doc(t).includes(d)));
kiem('B · có ít nhất một chunk chứa three/drei', chunk3D.length > 0);
for (const d of DAU_VET) {
  kiem(
    `B · fingerprint "${d}" còn sống trong bản build`,
    chunk3D.some((t) => doc(t).includes(d)),
    'fingerprint chết thì phép kiểm A mất hiệu lực mà vẫn xanh',
  );
}
kiem(
  'B · chunk 3D nằm NGOÀI đồ thị nạp sẵn',
  chunk3D.every((t) => !napSan.has(t)),
  `giao nhau: ${chunk3D.filter((t) => napSan.has(t)).join(', ')}`,
);

// ── C. Chunk 3D chỉ vào được qua `import()` ĐỘNG ──────────────────────────────
for (const muc of chunk3D) {
  const tinh: string[] = [];
  const dong: string[] = [];
  for (const ten of moiChunk) {
    if (ten === muc) continue;
    const ma = doc(ten);
    if (!ma.includes(muc)) continue;
    if (importTinh(ma).includes(muc)) tinh.push(ten);
    if (new RegExp(`import\\s*\\(\\s*["'\`]\\./${muc.replace(/\./g, '\\.')}["'\`]`).test(ma)) {
      dong.push(ten);
    }
  }
  kiem(`C · ${muc} không bị import TĨNH từ đâu cả`, tinh.length === 0, `bị import tĩnh từ: ${tinh.join(', ')}`);
  kiem(`C · ${muc} vào được qua import() động`, dong.length > 0);
}

// ── D. Cửa bề rộng chặn TRƯỚC khi `import()` chạy ─────────────────────────────
//
// Đây là phép kiểm duy nhất đọc MÃ NGUỒN, và nói thẳng vì sao: thứ tự từ vựng
// "guard đứng trước chỗ dùng" không còn khôi phục được đáng tin sau minify. A/B/C
// ở trên chặn được việc `three` lọt vào chunk entry; riêng việc "gỡ điều kiện bề
// rộng" thì chunk vẫn tách đúng, entry vẫn sạch — chỉ có trình duyệt ở 390px là
// bắt đầu tải nó. Chỗ duy nhất phát biểu được điều đó tĩnh là nguồn của cửa.
/**
 * Bỏ chú thích TRƯỚC khi khẳng định bất cứ điều gì về nguồn.
 *
 * Đây là bản sửa sau khi đột biến M3 THOÁT: đổi cửa JS xuống 40rem trong khi CSS
 * vẫn 48rem, mà test vẫn xanh — vì `includes('(min-width: 48rem)')` khớp phải câu
 * chú thích "Cùng breakpoint với @media (min-width: 48rem)" ngay phía trên hằng số
 * chứ không khớp chính hằng số. Một phép kiểm đọc văn xuôi thay vì đọc code thì
 * chỉ chứng minh rằng chú thích còn đó.
 *
 * Bỏ ở một chỗ, cho MỌI khẳng định D bên dưới, thay vì vá từng cái — cùng một cái
 * bẫy sẽ còn quay lại với mẫu khớp tiếp theo.
 *
 * `//` chỉ bị bỏ khi nó mở đầu một dòng, để không cắt mất `https://` trong chuỗi.
 */
function boComment(ma: string): string {
  return ma.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^[ \t]*\/\/.*$/gm, ' ');
}

const cua = boComment(
  readFileSync(join(NGUON, 'components', 'gioi-thieu', 'SlotBaChieu.tsx'), 'utf8'),
);

kiem('D · cửa dùng React.lazy + import() động', /lazy\(\s*\(\)\s*=>\s*import\(/.test(cua));
kiem(
  'D · cửa KHÔNG import tĩnh bất cứ gì từ hero3d/',
  !/^\s*import\s+[^(]*from\s+['"][^'"]*hero3d\//m.test(cua),
);
// Đọc ngưỡng ra khỏi CHÍNH hằng số, rồi so bằng — chứ không hỏi "48rem có xuất
// hiện ở đâu đó trong file không". Và hằng số đó phải là thứ đi vào matchMedia.
const mNguong = /const\s+(\w+)\s*=\s*['"`]\(min-width:\s*([\w.]+)\)['"`]/.exec(cua);
kiem('D · cửa khai báo một hằng số media query', mNguong !== null);
kiem(
  `D · cửa đo đúng ngưỡng ${NGUONG}`,
  mNguong !== null && mNguong[2] === NGUONG,
  mNguong === null ? 'không tìm thấy hằng số' : `đang là ${mNguong[2]}`,
);
kiem(
  'D · hằng số ngưỡng đi qua matchMedia',
  mNguong !== null && new RegExp(`matchMedia\\(\\s*${mNguong[1]}\\s*\\)`).test(cua),
);

const iGuard = cua.search(/if\s*\(\s*!\s*duRong\s*\)/);
const iDung = cua.indexOf('<KhoLuat');
kiem('D · có early-return khi chưa đủ bề rộng', iGuard !== -1);
kiem('D · <KhoLuat> có được render ở nhánh còn lại', iDung !== -1);
kiem(
  'D · guard đứng TRƯỚC chỗ render <KhoLuat>',
  iGuard !== -1 && iDung !== -1 && iGuard < iDung,
  `guard @${iGuard}, render @${iDung}`,
);

// Cửa JS và cửa CSS phải cùng một con số. Lệch nhau thì có một dải bề rộng mà
// canvas mount trên bố cục di động (hoặc ngược lại) — không bên nào báo lỗi.
const css = boComment(readFileSync(join(NGUON, 'styles', 'gioi-thieu.css'), 'utf8'));
const bpCss = [...css.matchAll(/@media\s*\(min-width:\s*([\w.]+)\)/g)].map((m) => m[1]);
kiem('D · gioi-thieu.css có ít nhất một @media min-width', bpCss.length > 0);
kiem(
  `D · mọi breakpoint min-width trong gioi-thieu.css là ${NGUONG}`,
  bpCss.every((b) => b === NGUONG),
  `thấy: ${[...new Set(bpCss)].join(', ')} — cửa JS và breakpoint CSS phải cùng một con số`,
);

if (hong > 0) {
  process.stderr.write(`${hong} phép kiểm HỎNG\n`);
  process.exit(1);
}
process.stdout.write(
  `kiem-cua-3d: tất cả phép kiểm ĐẠT ` +
    `(${napSan.size} chunk nạp sẵn, ${chunk3D.length} chunk 3D tách riêng)\n`,
);
