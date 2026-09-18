/**
 * Kiểm chạy được cho VIỀN TỪNG CẠNH của bảng và LỀ TRANG nguồn (quyết định
 * 2026-09-18, mục `vien_bang_tung_canh` / `le_trang` của `eval.run_trung_thuc`).
 *
 * Ba bất biến ở đây hỏng ÂM THẦM, và cả ba hỏng về phía "KLAW vẽ thêm thứ tài
 * liệu không có" — đúng chế độ hỏng mà cờ `vien` từng sửa một lần ở mức cả
 * bảng:
 *
 *   1. Một biểu mẫu chỉ kẻ KHUNG NGOÀI (`w:tblBorders` không có `insideH`/
 *      `insideV`) không được ra màn hình/tệp thành một cái LƯỚI kẻ đủ mọi ô.
 *      Cả ba nơi vẽ phải đọc cùng một chuỗi `"trên|phải|dưới|trái"`.
 *   2. `w:sz` hỏng phải làm CẢ BẢNG lùi về nét đều, không được vẽ nửa bảng
 *      theo nguồn nửa kia theo một bề dày đoán bừa (fail closed).
 *   3. Lề trang nguồn phải ĐẨY nội dung thật trong PDF, không chỉ có mặt trong
 *      một thuộc tính `data-*` không ai đọc.
 *
 * Con số trong các ca dưới đây lấy từ biểu mẫu THẬT của chủ dự án
 * (BM.ĐT.18.05: `tblBorders` `single/6`, `tcBorders` `single/4`, `w:pgMar`
 * 1134/1134/1134/1701), không phải chuỗi bịa cho vừa bộ đọc.
 *
 * Chạy: `npm run kiem-vien-le`.
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { inflateSync } from "node:zlib";
import {
  bangThanhTable,
  docBangTuPhanTu,
  kieuNetCSS,
  leTrangTuBanThao,
  mucTuBanThao,
  netCanh,
  noiDungThanhPDF,
  type BanThao,
  type CanLe,
  type KhoiVanBan,
  type NoiDungXuat,
  type PhongChuPDF,
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

// ─────────────────────────────────────────────── 1. `netCanh` / `kieuNetCSS`

bang(netCanh(""), null, "phần rỗng = cạnh không khai ở đâu cả → không nét");
bang(netCanh("none/"), null, "`w:val=none` là tệp nói RÕ không vẽ → không nét");
bang(netCanh("nil/4"), null, "`nil` cũng vậy, kể cả khi có `w:sz`");
bang(netCanh("single/6"), { val: "single", sz: 6 }, "nét thật giữ nguyên `w:val`/`w:sz`");
bang(
  netCanh("single/"),
  { val: "single", sz: 4 },
  "thiếu `w:sz` → 4 (½pt, mặc định của Word) chứ không 0: một cạnh có kiểu phải vẽ ra được",
);
bang(
  netCanh("/4"),
  { val: "", sz: 4 },
  "thiếu `w:val` vẫn là một nét — cùng cách `doc_tai_lieu._co_net` đọc, không đoán thành `none`",
);
bang(kieuNetCSS("double"), "double", "`double` giữ kiểu riêng");
bang(kieuNetCSS("dotted"), "dotted", "`dot*` → chấm");
bang(kieuNetCSS("dashSmallGap"), "dashed", "`dash*` → gạch");
bang(kieuNetCSS("threeDEmboss"), "solid", "giá trị lạ vẫn là MỘT NÉT, vẽ liền — không bỏ qua");

// ───────────────────────────────────── 2. cửa vào `clauses` — fail closed cả bảng

const HANG = [
  ["Tuần", "Nội dung"],
  ["1", "Tìm hiểu cơ sở"],
];
/** Khung ngoài `single/6`, KHÔNG kẻ trong — đúng hình dạng một bảng bố cục
 *  của biểu mẫu Việt Nam chỉ viền quanh. */
const VIEN_KHUNG = [
  ["single/6||single/6|single/6", "single/6|single/6|single/6|"],
  ["||single/6|single/6", "|single/6|single/6|"],
];
const banThaoBang = (them: Record<string, unknown>): BanThao =>
  ({
    clauses: [{ key: "muc_1", ten: "Kế hoạch", khoi: [{ bang: HANG, vien: true, ...them }] }],
  }) as unknown as BanThao;

const khoiCua = (bt: BanThao): KhoiVanBan & { vienO?: string[][] } =>
  mucTuBanThao(bt, null)[0]!.khoi[0] as never;

bang(
  khoiCua(banThaoBang({ vien_o: VIEN_KHUNG })).vienO,
  VIEN_KHUNG,
  "viền từng cạnh hợp lệ đi NGUYÊN qua cửa vào",
);
bang(
  khoiCua(banThaoBang({ vien_o: [["single/6|||", "single/6|||"], ["x|y|z|w"]] })).vienO,
  [],
  "một hàng lệch SỐ Ô làm cả bảng về nét đều, không ghép bừa",
);
bang(
  khoiCua(
    banThaoBang({
      vien_o: [
        ["single/6|||", "single/abc|||"],
        ["|||", "|||"],
      ],
    }),
  ).vienO,
  [],
  "`w:sz` không phải số làm CẢ BẢNG lùi về nét đều (fail closed), không đoán bề dày",
);
bang(
  khoiCua(banThaoBang({ vien_o: [["single/6|||"], ["|||"]] })).vienO,
  [],
  "thiếu ô so với `hang` cũng fail closed",
);
bang(khoiCua(banThaoBang({})).vienO, [], "bảng KHÔNG khai gì → rỗng, đường cũ nguyên vẹn");
bang(
  (khoiCua(banThaoBang({ cao_luat: ["exact", "auto"] })) as { caoLuat?: string[] }).caoLuat,
  ["exact", "auto"],
  "`@w:hRule` từng hàng đi qua cửa vào",
);
bang(
  (khoiCua(banThaoBang({ cao_luat: ["exact"] })) as { caoLuat?: string[] }).caoLuat,
  [],
  "`cao_luat` lệch số hàng → cả bảng về rỗng, cùng luật `caoHopLe`",
);

// ─────────────────────────────────────────── 3. lề trang qua cửa vào `clauses`

const LE_THAT: [string, number][] = [
  ["top", 1134],
  ["right", 1134],
  ["bottom", 1134],
  ["left", 1701],
  ["header", 709],
  ["footer", 709],
];
const banThaoLe = (le: unknown): BanThao =>
  ({ clauses: [{ key: "muc_1", ten: "A", khoi: [], le_trang: le }] }) as unknown as BanThao;

bang(
  leTrangTuBanThao(banThaoLe(LE_THAT)),
  { tren: 1134, phai: 1134, duoi: 1134, trai: 1701, dauTrang: 709, chanTrang: 709 },
  "lề trang thật của BM.ĐT.18.05 đọc ra đủ sáu số",
);
bang(
  leTrangTuBanThao(
    banThaoLe([
      ["top", 1134],
      ["right", 1134],
      ["bottom", 1134],
    ]),
  ),
  null,
  "thiếu lề TRÁI → null cả bộ: `0` là một khẳng định, không phải 'không biết'",
);
bang(
  leTrangTuBanThao(banThaoLe(LE_THAT.slice(0, 3).concat([["left", "x" as never]]))),
  null,
  "lề đọc không ra số cũng về null, không lấp 0",
);
bang(leTrangTuBanThao(banThaoLe(undefined)), null, "clause lưu TRƯỚC trường này → null");
bang(
  leTrangTuBanThao({
    clauses: [{ key: "muc_1" }, { key: "muc_2", le_trang: LE_THAT }],
  } as unknown as BanThao)?.trai,
  1701,
  "đọc ở clause ĐẦU TIÊN CÓ khoá, không bỏ cuộc ở clause đầu",
);

// ─────────────────────────────────── 4. DOM đã vẽ → đọc lại (một nguồn, ba nơi)

const oCell = (text: string, vienO?: string, canLe?: CanLe) => ({
  textContent: text,
  colSpan: 1,
  getAttribute: (ten: string) =>
    ten === "data-can-le" ? (canLe ?? null) : ten === "data-vien-o" ? (vienO ?? null) : null,
  querySelectorAll: (_s: string) =>
    [] as { textContent: string | null; getAttribute(t: string): string | null }[],
});
const oRow = (cells: ReturnType<typeof oCell>[], caoLuat?: string) => ({
  getAttribute: (ten: string) => (ten === "data-cao-luat" ? (caoLuat ?? null) : null),
  querySelectorAll: (_s: string) => cells,
});
const oTable = (rows: ReturnType<typeof oRow>[]) => ({
  getAttribute: (_t: string) => null,
  querySelectorAll: (sel: string) => (sel === "col" ? [] : rows),
});

const docLai = docBangTuPhanTu(
  oTable([
    oRow([oCell("Tuần", VIEN_KHUNG[0]![0]), oCell("Nội dung", VIEN_KHUNG[0]![1])], "exact"),
    oRow([oCell("1", VIEN_KHUNG[1]![0]), oCell("Tìm hiểu cơ sở", VIEN_KHUNG[1]![1])]),
  ]),
);
bang(docLai.vienO, VIEN_KHUNG, "`.docx`/PDF đọc lại ĐÚNG chuỗi cạnh màn hình đã vẽ");
bang(docLai.caoLuat, ["exact", ""], "`@w:hRule` cũng đọc lại từ chính `<tr>` đã vẽ");
bang(
  docBangTuPhanTu(oTable([oRow([oCell("a", "single/6|||"), oCell("b")])])).vienO,
  [],
  "một ô THIẾU `data-vien-o` làm cả bảng về nét đều — không kẻ nửa bảng",
);

// ──────────────────────────── 5. `.docx` — mỗi ô đúng bốn cạnh, tblBorders tắt

/**
 * Cây XML nội bộ của `docx`: tìm mọi nút mang tên `ten`. Đọc bằng
 * `rootKey`/`root` (ổn định qua các bản `docx`) — cách duy nhất soát được nội
 * dung một `Table` mà không phải đóng gói ra `.docx` thật rồi mở lại, đúng
 * khuôn `kiem-xuat-tep.ts` đã dùng.
 */
type NutDocx = { rootKey?: string; root?: unknown };
function timNut(nut: unknown, ten: string, ra: NutDocx[] = []): NutDocx[] {
  if (Array.isArray(nut)) {
    for (const c of nut) timNut(c, ten, ra);
    return ra;
  }
  if (typeof nut !== "object" || nut === null) return ra;
  const n = nut as NutDocx;
  if (n.rootKey === ten) ra.push(n);
  timNut(n.root, ten, ra);
  return ra;
}
/** Thuộc tính XML của một nút — `docx` cất chúng trong một nút con `_attr`
 *  mang `{<tên nội bộ>: {key: "w:val", value}}`. */
function thuocXml(nut: NutDocx | undefined, ten: string): unknown {
  const attr = timNut(nut?.root, "_attr")[0]?.root as Record<
    string,
    { key?: string; value?: unknown }
  >;
  return Object.values(attr ?? {}).find((c) => c.key === ten)?.value;
}
/** `w:val` của MỘT cạnh trong một nhóm viền. */
const valCanh = (nhom: NutDocx | undefined, canh: string): unknown =>
  thuocXml(timNut(nhom?.root, canh)[0], "w:val");

const tblKhung = await bangThanhTable(HANG, [], [], true, [0, 0], [], [], VIEN_KHUNG, [
  "exact",
  "",
]);
const oDocx = timNut(tblKhung as unknown, "w:tcBorders");
ok(oDocx.length === 4, `mỗi ô một nhóm w:tcBorders (thấy ${oDocx.length})`);
// Ô (0,0) của khung ngoài: trên + dưới + trái có nét, PHẢI thì không.
bang(valCanh(oDocx[0], "w:top"), "single", "ô góc trên-trái giữ cạnh TRÊN của khung");
bang(valCanh(oDocx[0], "w:left"), "single", "và cạnh TRÁI");
bang(valCanh(oDocx[0], "w:right"), "none", "nhưng KHÔNG mọc cạnh phải — nguồn không kẻ trong");
bang(
  thuocXml(timNut(oDocx[0]?.root, "w:top")[0], "w:sz"),
  6,
  "bề dày đi thẳng từ `w:sz` nguồn (⅛pt), không quy đổi",
);
bang(
  valCanh(timNut(tblKhung as unknown, "w:tblBorders")[0], "w:top"),
  "none",
  "viền CẤP BẢNG tắt khi mọi ô đã tự khai — hai khai báo cùng nói một nét là chỗ để lệch",
);
bang(
  timNut(tblKhung as unknown, "w:trHeight").length,
  0,
  "hàng khai `exact` mà `cao` = 0 thì không sinh `w:trHeight` nào",
);

const tblCao = await bangThanhTable(HANG, [], [], true, [1499, 0], [], [], [], ["exact", ""]);
const caoDocx = timNut(tblCao as unknown, "w:trHeight")[0];
bang(thuocXml(caoDocx, "w:val"), 1499, "chiều cao khai báo vẫn vào tệp");
bang(
  thuocXml(caoDocx, "w:hRule"),
  "atLeast",
  "nguồn khai `exact` vẫn ghi `atLeast`: cắt mất chữ người dùng hỏng hơn một hàng cao dôi",
);
const tblAuto = await bangThanhTable(HANG, [], [], true, [1499, 0], [], [], [], ["auto", ""]);
bang(
  timNut(tblAuto as unknown, "w:trHeight").length,
  0,
  "`hRule=auto` BỎ con số — Word bỏ nó ở đó, ép chiều cao là vẽ thứ tệp không nói",
);

// ─────────────────────────────── 6. PDF — cạnh thật, và lề nguồn đẩy nội dung

const phongChuPDF: PhongChuPDF = {
  thuong: (
    await readFile(new URL("../public/fonts/source-serif-4-pdf-regular.ttf", import.meta.url))
  ).toString("base64"),
  dam: (
    await readFile(new URL("../public/fonts/source-serif-4-pdf-bold.ttf", import.meta.url))
  ).toString("base64"),
};
function giaiNen(bytes: Buffer): string {
  const tho = bytes.toString("latin1");
  const ra: string[] = [];
  for (const m of tho.matchAll(/stream\r?\n([\s\S]*?)\r?\nendstream/g)) {
    try {
      ra.push(inflateSync(Buffer.from(m[1]!, "latin1")).toString("latin1"));
    } catch {
      // không phải luồng Flate (bytes font) — bỏ qua.
    }
  }
  return ra.join("\n");
}
const noiDungBang = (vienO: string[][], leTrang: NoiDungXuat["leTrang"] = null): NoiDungXuat => ({
  khoi: [
    {
      kind: "bang",
      hang: HANG,
      nhip: [],
      tiLe: [50, 50],
      vien: true,
      vienO,
      cao: [0, 0],
      caoLuat: [],
      canLeO: [],
      chuO: [],
    },
  ],
  oKy: [],
  leTrang,
});
/** Số lệnh vẽ ĐOẠN THẲNG (`x y l`) trong luồng nội dung — `\bl\b` trần trụi
 *  đếm cả chữ `l` trong chuỗi chữ đã mã hoá, nên phải neo vào hai toạ độ. */
const demNet = (s: string) => (s.match(/[\d.-]+ [\d.-]+ l\b/g) ?? []).length;
const demRe = (s: string) => (s.match(/\bre\b/g) ?? []).length;

const { pdf: pdfDeu } = await noiDungThanhPDF(noiDungBang([]), "Đều", phongChuPDF);
const { pdf: pdfKhung } = await noiDungThanhPDF(noiDungBang(VIEN_KHUNG), "Khung", phongChuPDF);
const sDeu = giaiNen(Buffer.from(pdfDeu.output("arraybuffer")));
const sKhung = giaiNen(Buffer.from(pdfKhung.output("arraybuffer")));
// `re` là toán tử hình chữ nhật của PDF — bảng nét đều kẻ MỘT `re` mỗi ô (cộng
// một `re` tô nền hàng tiêu đề, có ở cả hai bên). Bảng có chi tiết cạnh không
// kẻ khung ô nào: nó kẻ từng NÉT (`l`).
ok(demRe(sDeu) >= 4, "bảng không có chi tiết cạnh vẫn kẻ khung chữ nhật từng ô như trước");
ok(
  demRe(sKhung) < demRe(sDeu),
  `bảng có chi tiết cạnh KHÔNG kẻ khung ô nào (${demRe(sKhung)} vs ${demRe(sDeu)} hình chữ nhật)`,
);
// Cùng bảng ấy kẻ ĐỦ bốn cạnh mọi ô cần 16 nét; khung ngoài chỉ cần 10 (bốn ô,
// ô góc 3 cạnh, ô trong 2). Chặn TRÊN mới là phép thử thật: nó đỏ đúng lúc mã
// quay về kẻ mọi cạnh cho mọi ô — thứ bản vá này tồn tại để chặn.
const LUOI_DU = VIEN_KHUNG.map((h) => h.map(() => "single/6|single/6|single/6|single/6"));
const { pdf: pdfLuoi } = await noiDungThanhPDF(noiDungBang(LUOI_DU), "Lưới", phongChuPDF);
const netLuoi = demNet(giaiNen(Buffer.from(pdfLuoi.output("arraybuffer"))));
ok(
  demNet(sKhung) > 0 && demNet(sKhung) < netLuoi,
  `khung ngoài kẻ ÍT nét hơn một lưới đủ ô (${demNet(sKhung)} vs ${netLuoi} nét)`,
);

const dongDai = Array.from({ length: 40 }, () => ({
  kind: "dong" as const,
  d: {
    text: "Sinh viên thực hiện nội dung công việc theo kế hoạch đã được phê duyệt.",
    kieu: "thuong" as const,
    canhLe: "trai" as CanLe,
    inDam: false,
    inNghieng: false,
    thutLe: 0,
    doan: [],
    gianCach: null,
  },
}));
const heLe = (leTrang: NoiDungXuat["leTrang"]): NoiDungXuat => ({
  khoi: dongDai,
  oKy: [],
  leTrang,
});
const { pdf: pdfLeRong } = await noiDungThanhPDF(heLe(null), "Mặc định", phongChuPDF);
const { pdf: pdfLeDay } = await noiDungThanhPDF(
  heLe({ tren: 3402, phai: 3402, duoi: 3402, trai: 3402, dauTrang: 0, chanTrang: 0 }),
  "Lề dày",
  phongChuPDF,
);
ok(
  pdfLeDay.getNumberOfPages() > pdfLeRong.getNumberOfPages(),
  "lề trang NGUỒN phải đẩy nội dung thật trong PDF, không chỉ nằm trong một thuộc tính",
);

console.info(`kiem-vien-le: ${dat}/${dat} đạt`);
