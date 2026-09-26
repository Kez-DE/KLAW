/**
 * Kiểm chạy được cho DÒNG CHẢY TRANG của khung xem trước.
 *
 * Trước bản vá này, `XemTruocA4` vẽ đúng MỘT `<article aspect-[210/297]
 * overflow-y-auto>`: nội dung dài hơn một trang cuộn BÊN TRONG tờ giấy đó — không
 * có trang 2, không có khoảng cách giữa hai tờ, không có lề trang riêng cho từng
 * tờ. `.docx` thì chính Word chia trang, PDF thì `noiDungThanhPDF` đã chia thật,
 * nên MÀN HÌNH là nơi duy nhất nói sai.
 *
 * Bốn bất biến ở đây hỏng ÂM THẦM:
 *
 *   1. Số TỜ phải bằng số trang NGUỒN khai (`Muc.trang`, mang từ
 *      `doc_tai_lieu._DemTrang`), và chỗ cắt phải rơi đúng vào mục đầu của trang
 *      mới — không sớm một mục, không muộn một mục.
 *   2. Tài liệu MỘT trang vẫn phải ra ĐÚNG MỘT tờ. Đây là chỗ bản vá dễ đổi hành
 *      vi cũ nhất, và nó đổi im lặng.
 *   3. Lề NGUỒN phải nằm trên TỪNG tờ (nét vẽ) còn `data-le-*` phải ở lại trên
 *      `<article>` — thẻ mà `docNoiDungTuDOM` nhận. Lẫn hai chỗ này thì `.docx`
 *      và PDF mất lề nguồn mà màn hình vẫn trông đúng.
 *   4. NHIỀU tờ phải đọc lại thành MỘT tài liệu liền mạch. Đây là phần rủi ro
 *      nhất của cả bản vá: `docNoiDungTuDOM` duyệt một lần trên thẻ nhận được,
 *      nên một tờ bị bỏ sót hay bị đọc hai lần đi thẳng vào tệp người dùng tải
 *      về mà màn hình không lộ ra gì.
 *
 * Chạy: `npm run kiem-dong-trang`.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  chiaTrang,
  choCatTran,
  diaChiKhoi,
  docNoiDungTuDOM,
  mucTuBanThao,
  THUOC_TINH_LE,
  type BanThao,
  type Muc,
} from "../src/lib/xuat-tep.ts";

let dat = 0;
const ok = (dieu: boolean, vi: string) => {
  assert.ok(dieu, vi);
  dat += 1;
};
const bang = (a: unknown, b: unknown, vi: string) => {
  assert.deepEqual(a, b, vi);
  dat += 1;
};

// ───────────────────────────────────────────────── 1. `chiaTrang` — nửa NGUỒN

/** Chỉ đúng những trường `chiaTrang` đọc — nó cố tình generic để kiểm được mà
 *  không phải dựng cả một `Muc`. */
const m = (key: string, trang: number, soKhoi = 1) => ({
  key,
  trang,
  khoi: Array.from({ length: soKhoi }, (_, k) => k),
});

type Manh = { m: { key: string }; tu: number; den: number };
const khoa = (to: Manh[][]) => to.map((t) => t.map((x) => x.m.key));
/** Mảnh viết gọn `a[0,2)` — khối `[tu, den)` của mục `a` trên một tờ. */
const manh = (to: Manh[][]) => to.map((t) => t.map((x) => `${x.m.key}[${x.tu},${x.den})`));

bang(
  khoa(chiaTrang([m("a", 1), m("b", 1), m("c", 1)])),
  [["a", "b", "c"]],
  "tài liệu MỘT trang ra ĐÚNG MỘT tờ — hành vi trước bản vá, giữ nguyên",
);

bang(
  khoa(chiaTrang([m("a", 1), m("b", 1), m("c", 2), m("d", 2)])),
  [
    ["a", "b"],
    ["c", "d"],
  ],
  "cắt ĐÚNG chỗ `trang` tăng: `c` là mục đầu của trang 2, không phải `b`",
);

bang(
  khoa(chiaTrang([m("a", 1), m("b", 2), m("c", 3)])),
  [["a"], ["b"], ["c"]],
  "ba trang nguồn → ba tờ",
);

bang(
  khoa(chiaTrang([m("a", 1), m("b", 3)])),
  [["a"], ["b"]],
  "trang nhảy 1→3 (một ngắt rơi vào chỗ không có mục nào) vẫn chỉ mở MỘT tờ mới: khung xem trước không vẽ một tờ TRẮNG mà nguồn không có mục nào để đặt lên",
);

bang(
  khoa(chiaTrang([m("a", 2), m("b", 2)])),
  [["a", "b"]],
  "mục đầu ở trang 2 (đầu tài liệu bị mô hình bỏ) không đẻ ra một tờ trắng đứng trước",
);

bang(
  khoa(chiaTrang([m("a", 1), m("b", 2), m("c", 1)])),
  [["a"], ["b", "c"]],
  "trang LÙI không cắt thêm tờ — mô hình đảo thứ tự mục không được vẽ ra một ngắt trang ngược đời",
);

bang(
  khoa(chiaTrang([m("a", 3), m("b", 1), m("c", 2)])),
  [["a", "b", "c"]],
  "sau khi đã thấy trang 3, một trang 2 KHÔNG phải trang mới: mốc so sánh là trang CAO NHẤT đã đi qua, không phải trang của mục liền trước (bỏ `Math.max` thì `c` mở oan một tờ)",
);

bang(khoa(chiaTrang([])), [[]], "không mục nào vẫn là MỘT tờ giấy trắng, không phải KHÔNG tờ nào");

bang(
  khoa(chiaTrang([m("a", 1), m("b", 1), m("c", 1)], [diaChiKhoi(2, 0)])),
  [["a", "b"], ["c"]],
  "`catThem` (chỗ TRÀN đo được trên trình duyệt) cắt thêm tờ dù nguồn không khai ngắt nào",
);

bang(
  khoa(chiaTrang([m("a", 1), m("b", 2), m("c", 2)], [diaChiKhoi(2, 0)])),
  [["a"], ["b"], ["c"]],
  "hai nửa cộng lại: ngắt NGUỒN và chỗ TRÀN cắt độc lập, không nuốt nhau",
);

bang(
  khoa(chiaTrang([m("a", 1), m("b", 1)], [diaChiKhoi(0, 0)])),
  [["a", "b"]],
  "chỗ cắt ở mục ĐẦU bị bỏ qua — cắt ở đó chỉ sinh ra một tờ rỗng",
);

// Cắt GIỮA một mục: một mục (hay một bảng dài) cao hơn phần còn lại của tờ
// phải chảy sang tờ sau theo ranh giới KHỐI, không cuộn bên trong một tờ.
bang(
  manh(chiaTrang([m("a", 1, 5)])),
  [["a[0,5)"]],
  "không chỗ cắt nào → mục là MỘT mảnh trọn, đúng hành vi trước bản vá",
);
bang(
  manh(chiaTrang([m("a", 1, 5)], [diaChiKhoi(0, 2)])),
  [["a[0,2)"], ["a[2,5)"]],
  "chỗ cắt ở khối 2 của mục ĐẦU chẻ nó thành hai mảnh trên hai tờ — mục đầu KHÔNG được miễn cắt giữa",
);
bang(
  manh(chiaTrang([m("a", 1, 5)], [diaChiKhoi(0, 4), diaChiKhoi(0, 2)])),
  [["a[0,2)"], ["a[2,4)"], ["a[4,5)"]],
  "nhiều chỗ cắt trong một mục, không theo thứ tự nhập, vẫn ra các mảnh LIỀN nhau theo thứ tự khối",
);
bang(
  manh(chiaTrang([m("a", 1, 2), m("b", 1, 3), m("c", 1, 1)], [diaChiKhoi(1, 1)])),
  [
    ["a[0,2)", "b[0,1)"],
    ["b[1,3)", "c[0,1)"],
  ],
  "mảnh đầu của `b` ở lại tờ cũ cùng `a`; mảnh sau mở tờ mới và `c` chảy tiếp trên tờ đó",
);
bang(
  manh(chiaTrang([m("a", 1, 3), m("b", 2, 2)], [diaChiKhoi(0, 1), diaChiKhoi(1, 1)])),
  [["a[0,1)"], ["a[1,3)"], ["b[0,1)"], ["b[1,2)"]],
  "chỗ cắt KHỐI và ngắt trang NGUỒN cộng dồn, không nuốt nhau",
);
bang(
  manh(chiaTrang([m("a", 1, 2)], [diaChiKhoi(0, 2), diaChiKhoi(0, 9), diaChiKhoi(3, 1)])),
  [["a[0,2)"]],
  "chỗ cắt ở/ngoài CUỐI mục hay ở một mục không tồn tại bị bỏ — không sinh mảnh rỗng",
);
bang(
  manh(chiaTrang([m("a", 1, 1), m("b", 1, 0)], [diaChiKhoi(1, 0)])),
  [["a[0,1)"], ["b[0,0)"]],
  "mục KHÔNG có khối nào vẫn là một mảnh (tên mục vẫn vẽ), và vẫn cắt được trước nó",
);

// ─────────────────────────── 1b. `choCatTran` — nửa ĐO, quyết định chỗ cắt

const dv = (cat: string, day: number) => ({ cat, day });

bang(choCatTran([dv("0.0", 100), dv("0.1", 290)], 297), null, "tờ vừa chữ → không cắt");
bang(
  choCatTran([dv("0.0", 100), dv("0.1", 200), dv("0.2", 300), dv("1.0", 400)], 297),
  "0.2",
  "cắt TRƯỚC đơn vị đầu tiên vượt đáy tờ, không phải đơn vị sau nó",
);
bang(
  choCatTran([dv("0.0", 900)], 297),
  null,
  "MỘT khối cao hơn cả trang đứng đầu tờ → KHÔNG cắt (tờ tự cao thêm) — cắt ở đó chỉ đẻ tờ rỗng và quay vòng mãi",
);
bang(
  choCatTran([dv("0.0", 900), dv("0.1", 1000)], 297),
  "0.1",
  "khối quá cao đứng đầu tờ ở lại một mình; phần còn lại chảy sang tờ sau",
);
bang(
  choCatTran([dv("0.0", 100), dv("0.1", 297.4)], 297),
  null,
  "dung sai 0,5px: chiều cao dưới điểm ảnh không đáng mở hẳn một tờ mới",
);
bang(choCatTran([], 297), null, "tờ không có đơn vị nào → không cắt");

// ───────────────────────────── 2. `Muc.trang` — trang nguồn đi tới được màn hình

const banThao = (clauses: unknown[]) => ({ clauses }) as unknown as BanThao;

bang(
  mucTuBanThao(
    banThao([
      { key: "m1", ten: "Giấy tiếp nhận", noi_dung: "x", trang: 1 },
      { key: "m2", ten: "Danh sách sinh viên", noi_dung: "y", trang: 2 },
    ]),
    null,
  ).map((x: Muc) => x.trang),
  [1, 2],
  "`clauses[*].trang` (do `hieu_tai_lieu` gán từ `DonViVanBan.trang`) đi qua nguyên vẹn",
);

bang(
  mucTuBanThao(banThao([{ key: "m1", ten: "A", noi_dung: "x" }]), null).map((x: Muc) => x.trang),
  [1],
  "bản thảo lưu TRƯỚC bản vá (không có khoá `trang`) về trang 1 — fail closed, ra đúng một tờ như cũ",
);

bang(
  mucTuBanThao(
    banThao([
      { key: "m1", ten: "A", noi_dung: "x", trang: 0 },
      { key: "m2", ten: "B", noi_dung: "y", trang: "hai" },
      { key: "m3", ten: "C", noi_dung: "z", trang: -3 },
    ]),
    null,
  ).map((x: Muc) => x.trang),
  [1, 1, 1],
  "giá trị hỏng (0, chữ, âm) về 1 chứ không thành một ngắt trang bịa",
);

// ─────────────────────── 3. đọc lại NHIỀU tờ thành MỘT tài liệu liền mạch

/**
 * DOM giả tối thiểu (repo này không có `jsdom`, xem `kiem-xuat-tep.ts`).
 *
 * Chỉ dựng đúng tính chất đang được kiểm: `querySelectorAll` trên thẻ GỐC trả
 * về mọi hậu duệ khớp, theo THỨ TỰ TÀI LIỆU, bất kể lồng sâu mấy lớp — đó
 * chính là điều `docNoiDungTuDOM` dựa vào để nhiều tờ vẫn ra một tài liệu.
 */
type TheGia = {
  tagName: string;
  thuoc: Record<string, string>;
  con: TheGia[];
  chu: string;
  cha: TheGia | null;
};

const the = (
  tagName: string,
  { thuoc = {}, con = [], chu = "" }: Partial<Omit<TheGia, "tagName" | "cha">> = {},
): TheGia => {
  const t: TheGia = { tagName, thuoc, con, chu, cha: null };
  for (const c of con) c.cha = t;
  return t;
};

const hauDue = (t: TheGia): TheGia[] => t.con.flatMap((c) => [c, ...hauDue(c)]);

/** Khớp một bộ chọn ĐƠN GIẢN: `tag`, `[thuoc]`, `[thuoc="v"]`, `tag[thuoc]`. */
const khop = (t: TheGia, chon: string): boolean =>
  chon.split(",").some((phan) => {
    const s = phan.trim();
    const i = s.indexOf("[");
    const tag = (i === -1 ? s : s.slice(0, i)).trim();
    if (tag && tag.toUpperCase() !== t.tagName) return false;
    if (i === -1) return true;
    const trong = s.slice(i + 1, s.lastIndexOf("]"));
    const [ten, gt] = trong.split("=");
    const v = t.thuoc[ten!.trim()];
    if (v === undefined) return false;
    return gt === undefined || v === gt.replace(/["']/g, "");
  });

const boc = (t: TheGia): unknown => ({
  get tagName() {
    return t.tagName;
  },
  get textContent(): string {
    return t.chu + t.con.map((c) => (boc(c) as { textContent: string }).textContent).join("");
  },
  classList: { contains: (c: string) => (t.thuoc["class"] ?? "").split(" ").includes(c) },
  getAttribute: (ten: string) => t.thuoc[ten] ?? null,
  closest: (chon: string): unknown => {
    for (let n: TheGia | null = t; n; n = n.cha) if (khop(n, chon)) return boc(n);
    return null;
  },
  querySelector: (chon: string) => {
    const x = hauDue(t).find((c) => khop(c, chon));
    return x ? boc(x) : null;
  },
  querySelectorAll: (chon: string) =>
    hauDue(t)
      .filter((c) => khop(c, chon))
      .map(boc),
});

// `docDong` hỏi CSS đang áp. Không có trình duyệt thì trả về đúng mặc định của
// một `<p>` — phép kiểm ở đây đo THỨ TỰ và SỐ LƯỢNG khối, không đo kiểu chữ
// (đã có `kiem-dinh-dang-chu`).
(globalThis as { getComputedStyle?: unknown }).getComputedStyle = () => ({
  textAlign: "start",
  textTransform: "none",
  fontWeight: "400",
  fontStyle: "normal",
  marginLeft: "0px",
});

const LE = {
  [THUOC_TINH_LE.tren]: "964",
  [THUOC_TINH_LE.phai]: "1134",
  [THUOC_TINH_LE.duoi]: "1134",
  [THUOC_TINH_LE.trai]: "1701",
  [THUOC_TINH_LE.dauTrang]: "720",
  [THUOC_TINH_LE.chanTrang]: "720",
};

/** Chín dòng — đủ để xé thành ba tờ mà vẫn đọc được bằng mắt trong thông báo lỗi. */
const DONG = Array.from({ length: 9 }, (_, i) => `Dòng số ${i + 1} của biểu mẫu`);
const p = (chu: string) => the("P", { chu });

/** Hình dạng TRƯỚC bản vá: mọi dòng nằm thẳng trong `<article>`, một tờ duy nhất. */
const motTo = the("ARTICLE", { thuoc: LE, con: DONG.map(p) });

/** Hình dạng SAU bản vá: ba tờ `data-to`, mỗi tờ ba dòng, tất cả trong CÙNG
 *  `<article>` mà `SanKhauBanThao` trao cho `docNoiDungTuDOM`. */
const baTo = the("ARTICLE", {
  thuoc: LE,
  con: [0, 1, 2].map((i) =>
    the("DIV", {
      thuoc: { "data-to": String(i) },
      con: DONG.slice(i * 3, i * 3 + 3).map(p),
    }),
  ),
});

const mot = docNoiDungTuDOM(boc(motTo) as never);
const ba = docNoiDungTuDOM(boc(baTo) as never);

bang(
  ba.khoi.map((k) => (k.kind === "dong" ? k.d.text : k.kind)),
  DONG,
  "BA tờ đọc ra ĐÚNG chín dòng, ĐÚNG thứ tự tài liệu — không sót tờ nào, không đọc tờ nào hai lần",
);
bang(
  ba.khoi,
  mot.khoi,
  "xuất từ ba tờ khớp TỪNG BYTE với xuất từ một tờ — màn hình đổi, tệp không",
);
bang(
  ba.leTrang,
  mot.leTrang,
  "lề nguồn đọc lại y hệt: `data-le-*` vẫn ở trên `<article>`, không trôi xuống tờ",
);
ok(
  ba.leTrang !== null && ba.leTrang.trai === 1701,
  "và nó là lề THẬT của nguồn, không phải mặc định",
);

// Đối chứng: nếu `data-le-*` bị dời từ `<article>` xuống từng tờ thì `.docx`/PDF
// mất sạch lề nguồn trong khi màn hình vẫn vẽ đúng — đúng chế độ hỏng âm thầm
// mà bất biến 3 tồn tại để chặn.
const leSaiCho = the("ARTICLE", {
  con: [the("DIV", { thuoc: { "data-to": "0", ...LE }, con: DONG.map(p) })],
});
bang(
  docNoiDungTuDOM(boc(leSaiCho) as never).leTrang,
  null,
  "đối chứng: lề đặt nhầm xuống tờ thì đọc lại ra `null` — phép kiểm trên KHÔNG tự đúng",
);

// ───────────────────────────────────── 4. lề NGUỒN nằm trên TỪNG tờ (nét vẽ)

const NGUON = readFileSync("src/components/soan-thao/XemTruocA4.tsx", "utf8");

ok(
  /<article ref=\{khungRef\}[\s\S]{0,120}\{\.\.\.thuocLe\}/.test(NGUON),
  "`data-le-*` ở lại trên `<article>` — thẻ `docNoiDungTuDOM` nhận",
);
ok(
  /\{\.\.\.\{ \[THUOC_TINH_TO\]: String\(ti\) \}\}[\s\S]{0,900}style=\{kieuLe\}/.test(NGUON),
  "MỖI tờ (`data-to`) mang `style={kieuLe}` — lề nguồn vẽ trên từng tờ, không chỉ trên khung",
);
ok(
  /leTrang === null && "px-\[8%\] py-\[7%\]"/.test(NGUON),
  "không có lề nguồn thì tờ giữ nguyên lớp lề 8%/7% cũ",
);
ok(
  /aspect-\[210\/297\]/.test(NGUON) && !/<article[\s\S]{0,200}aspect-\[210\/297\]/.test(NGUON),
  "khổ A4 chuyển xuống TỜ; `<article>` không còn là một tờ giấy",
);
ok(
  !/overflow-y-auto/.test(NGUON),
  "tờ KHÔNG cuộn bên trong: chữ tràn phải chảy sang tờ sau (hoặc tờ tự cao thêm), không bao giờ nằm khuất trong một tờ cuộn",
);

console.log(`kiem-dong-trang: ${dat} phép kiểm ĐẠT`);
