/**
 * Kiểm chạy được cho ĐỊNH DẠNG CHỮ của tài liệu nguồn (`w:rPr`, quyết định
 * 2026-09-18) — đường từ máy chủ ra màn hình rồi vào tệp tải về, cho CẢ văn
 * xuôi (mục 1–5) lẫn Ô BẢNG (mục 6).
 *
 * Bốn điều được chốt ở đây, và cả bốn đều là chỗ định dạng hỏng ÂM THẦM:
 *
 * 1. **`chuHopLe` fail-closed.** Một khoảng chồng lên khoảng trước, tràn khỏi
 *    `noiDung`, hay đảo đầu-cuối sẽ cắt chữ sai chỗ. In đậm nửa từ khó đọc hơn
 *    hẳn không in đậm, nên cả khối về chữ thường chứ không về chữ sai.
 * 2. **Cắt rồi đọc lại phải ra ĐÚNG thứ đã cắt.** `catTheoChu` (màn hình vẽ
 *    gì) và `docDoanChu` (tệp đọc lại gì) đi qua CÙNG bảng tên thuộc tính
 *    `THUOC_TINH_CHU`; vòng đi–về khép kín là thứ duy nhất chứng minh tệp tải
 *    về không nói khác màn hình. Nối `text` của các đoạn phải ra đúng
 *    `noiDung`: sót một ký tự giữa hai khoảng là mất chữ của người dùng.
 * 3. **`.docx` mang đúng đậm/nghiêng/gạch/cỡ/phông của từng đoạn.** Đọc thẳng
 *    XML nội bộ của `docx` (`w:b`, `w:sz`, `w:rFonts`), không chỉ kiểm hàm
 *    NHẬN đúng tham số.
 * 4. **Phông ánh xạ về họ chữ CÓ THẬT trong kho.** Tên không nhận ra thì trả
 *    `""` (giữ phông của trang) chứ không dựng một stack `"Times New Roman",
 *    serif` — thứ cho ra kết quả khác nhau trên từng máy, tức màn hình không
 *    còn là cái mà `.docx`/PDF phải khớp nữa.
 *
 * Chạy: `npm run kiem-dinh-dang-chu` (Node 22, 0 thư viện mới).
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { inflateSync } from "node:zlib";

import {
  bangThanhTable,
  catTheoChu,
  docBangTuPhanTu,
  docDoanChu,
  dongThanhParagraph,
  mucTuBanThao,
  noiDungThanhPDF,
  phongTrenManHinh,
  THUOC_TINH_CHU,
  type DoanChu,
  type DongVanBan,
  type KhoangChu,
} from "../src/lib/xuat-tep.ts";

let dat = 0;
const dung = (ten: string, f: () => void) => {
  try {
    f();
  } catch (e) {
    console.error(`kiem-dinh-dang-chu: HỎNG — ${ten}`);
    throw e;
  }
  dat += 1;
};

const khoang = (o: Partial<KhoangChu> & { dau: number; cuoi: number }): KhoangChu => ({
  dam: false,
  nghieng: false,
  gach: false,
  co: 0,
  phong: "",
  ...o,
});

// ──────────────────────────── 1. `chuHopLe` qua `mucTuBanThao` ──────────────
//
// `chuHopLe` không xuất khẩu (nó là bộ lọc đầu vào của `khoiMotHopLe`), nên
// kiểm qua đúng cửa mà dữ liệu thật đi vào: một `clause` có khoá `chu`.
const NOI_DUNG = "Họ và tên: NGUYỄN VĂN A";
const banThao = (chu: unknown) =>
  ({
    id: "bt",
    ten: "Bản thảo tổng quát",
    document: "",
    clauses: [
      {
        key: "muc_1",
        ten: "Thân bài",
        vung: "than",
        khoi: [{ noi_dung: NOI_DUNG, bang: [], can_le: "trai", chu }],
      },
    ],
  }) as unknown as Parameters<typeof mucTuBanThao>[0];

const chuCua = (chu: unknown): KhoangChu[] => {
  const k = mucTuBanThao(banThao(chu), null)[0]?.khoi[0];
  assert.equal(k?.kind, "vanXuoi");
  return k!.kind === "vanXuoi" ? k.chu : [];
};

dung("khoảng hợp lệ đi qua nguyên vẹn", () => {
  assert.deepEqual(chuCua([{ dau: 11, cuoi: 23, dam: true, co: 26, phong: "Times New Roman" }]), [
    khoang({ dau: 11, cuoi: 23, dam: true, co: 26, phong: "Times New Roman" }),
  ]);
});

dung("vắng `chu` (khối không định dạng, clause lưu trước trường này) → rỗng", () => {
  assert.deepEqual(chuCua(undefined), []);
});

for (const [ten, xau] of [
  [
    "chồng lên khoảng trước",
    [
      { dau: 0, cuoi: 10 },
      { dau: 5, cuoi: 12 },
    ],
  ],
  ["tràn khỏi nội dung", [{ dau: 11, cuoi: NOI_DUNG.length + 1 }]],
  ["đảo đầu-cuối", [{ dau: 12, cuoi: 11 }]],
  ["rỗng (cuoi === dau)", [{ dau: 3, cuoi: 3 }]],
  ["offset không nguyên", [{ dau: 0.5, cuoi: 4 }]],
  ["cỡ chữ âm", [{ dau: 0, cuoi: 4, co: -2 }]],
  ["không phải mảng", "đậm"],
] as const) {
  dung(`fail-closed: ${ten}`, () => {
    assert.deepEqual(chuCua(xau), [], `${ten}: CẢ khối phải về chữ thường, không nhận một phần`);
  });
}

dung("một khoảng hỏng làm mất CẢ khối, không chỉ chính nó", () => {
  assert.deepEqual(
    chuCua([
      { dau: 0, cuoi: 3, dam: true },
      { dau: 2, cuoi: 9, nghieng: true },
    ]),
    [],
  );
});

// ─────────────────── 2. Cắt (màn hình vẽ) ↔ đọc lại (tệp đọc) ───────────────
const CHU_MAU: KhoangChu[] = [
  khoang({ dau: 0, cuoi: 10, dam: true }),
  khoang({ dau: 11, cuoi: 23, nghieng: true, gach: true, co: 28, phong: "Times New Roman" }),
];

/** Một `<span>` giả dựng TỪ một `DoanChu`, đúng bảng tên `THUOC_TINH_CHU` mà
 * `XemTruocA4.veChuVaoThe` ghi ra — chỉ cần `textContent`/`getAttribute`, như
 * chính `docDoanChu` đòi (repo này không có `jsdom`). */
const spanGia = (o: DoanChu) => {
  const thuoc: Record<string, string> = { [THUOC_TINH_CHU.moc]: "" };
  if (o.inDam) thuoc[THUOC_TINH_CHU.dam] = "1";
  if (o.inNghieng) thuoc[THUOC_TINH_CHU.nghieng] = "1";
  if (o.gachChan) thuoc[THUOC_TINH_CHU.gach] = "1";
  if (o.coChu > 0) thuoc[THUOC_TINH_CHU.co] = String(o.coChu);
  if (o.phong) thuoc[THUOC_TINH_CHU.phong] = o.phong;
  return { textContent: o.text, getAttribute: (t: string) => thuoc[t] ?? null };
};

const theGia = (doan: DoanChu[]) => ({
  querySelectorAll: (sel: string) =>
    sel === `span[${THUOC_TINH_CHU.moc}]` ? doan.map(spanGia) : [],
});

const daCat = catTheoChu(NOI_DUNG, CHU_MAU);

dung("các đoạn PHỦ KÍN nội dung, nối lại ra đúng chuỗi ban đầu", () => {
  assert.equal(daCat.map((o) => o.text).join(""), NOI_DUNG);
});

dung("chữ giữa hai khoảng vẫn là một đoạn, không định dạng", () => {
  assert.deepEqual(
    daCat.map((o) => [o.text, o.inDam, o.inNghieng, o.gachChan, o.coChu, o.phong]),
    [
      ["Họ và tên:", true, false, false, 0, ""],
      [" ", false, false, false, 0, ""],
      ["NGUYỄN VĂN A", false, true, true, 28, "Times New Roman"],
    ],
  );
});

dung("màn hình vẽ gì thì tệp đọc lại đúng thứ đó", () => {
  assert.deepEqual(docDoanChu(theGia(daCat)), daCat);
});

dung("dòng không có đoạn nào (khối không định dạng) → `[]`, đường cũ", () => {
  assert.deepEqual(docDoanChu(theGia([])), []);
});

// ───────────────────────────── 3. `.docx` theo đoạn ─────────────────────────
//
// Đọc `rootKey`/`root` — cây XML nội bộ của `docx`, cùng cách `kiem-xuat-tep`
// soát một `Table` mà không cần đóng gói ra tệp thật rồi mở lại.
function timTat(node: unknown, key: string): Record<string, unknown>[] {
  const ra: Record<string, unknown>[] = [];
  const di = (n: unknown) => {
    if (!n || typeof n !== "object") return;
    const r = n as Record<string, unknown>;
    if (r["rootKey"] === key) ra.push(r);
    if (Array.isArray(r["root"])) for (const c of r["root"]) di(c);
  };
  di(node);
  return ra;
}

/**
 * Một thuộc tính XML của thẻ đầu tiên mang `key` trong cây nội bộ `docx`.
 *
 * Hai hình dạng `_attr` cùng tồn tại trong thư viện (`{ val: 26 }` cho `w:sz`,
 * `{ val: { key, value } }` cho `w:jc`), nên đọc cả hai — đây là đọc RUỘT của
 * một thư viện, không phải một API có hợp đồng.
 */
function thuocTinh(the: Record<string, unknown> | undefined, ten: string): unknown {
  const attr = ((the?.["root"] as Record<string, unknown>[] | undefined)?.[0]?.["root"] ??
    {}) as Record<string, unknown>;
  const v = attr[ten];
  return v && typeof v === "object" && "value" in v ? (v as { value: unknown }).value : v;
}

/** `docx` LUÔN ghi `w:b`/`w:i`/`w:u`, và tắt bằng `w:val="false"` — đúng cái
 * bẫy mà bộ đọc phía máy chủ cũng phải né (`_TAT`). "Có thẻ" không phải "bật". */
function batTat(run: Record<string, unknown>, key: string): boolean {
  const the = timTat(run, key)[0];
  return the !== undefined && thuocTinh(the, "val") !== false;
}

const dong = (extra: Partial<DongVanBan> = {}): DongVanBan => ({
  text: NOI_DUNG,
  kieu: "thuong",
  canhLe: "trai",
  inDam: false,
  inNghieng: false,
  thutLe: 0,
  doan: [],
  ...extra,
});

const paraTheoDoan = await dongThanhParagraph(dong({ doan: daCat }));
const runs = timTat(paraTheoDoan, "w:r");

dung("ba đoạn trên màn hình ra ba `w:r` trong tệp", () => {
  assert.equal(runs.length, 3, "một `TextRun` cho MỖI đoạn, không gộp lại một");
});

dung("chữ từng `w:r` khớp từng đoạn", () => {
  const chu = runs.map(
    (r) =>
      timTat(r, "w:t").map((wt) => (wt["root"] as unknown[]).find((x) => typeof x === "string"))[0],
  );
  assert.deepEqual(
    chu,
    daCat.map((o) => o.text),
  );
});

dung("đoạn đậm BẬT `w:b`, đoạn thường TẮT nó", () => {
  assert.ok(batTat(runs[0]!, "w:b"), "đoạn nguồn khai đậm phải bật `w:b`");
  assert.ok(!batTat(runs[1]!, "w:b"), "đoạn nguồn KHÔNG khai đậm phải tắt `w:b`");
});

dung("đoạn nghiêng + gạch chân bật `w:i` và `w:u`", () => {
  assert.ok(batTat(runs[2]!, "w:i"));
  assert.equal(timTat(runs[2]!, "w:u").length, 1, "gạch chân nguồn phải vào tệp");
  assert.equal(timTat(runs[0]!, "w:u").length, 0, "đoạn không gạch chân không được có `w:u`");
});

dung("cỡ chữ NGUỒN (nửa điểm) ghi nguyên vào `w:sz`", () => {
  assert.equal(thuocTinh(timTat(runs[2]!, "w:sz")[0], "val"), 28, "28 nửa điểm = 14pt, đúng nguồn");
  assert.equal(thuocTinh(timTat(runs[0]!, "w:sz")[0], "val"), 26, "không khai cỡ → cỡ thường 26");
});

dung("tên phông NGUỒN ghi nguyên vào `w:rFonts`, không phải họ chữ màn hình", () => {
  assert.equal(thuocTinh(timTat(runs[2]!, "w:rFonts")[0], "ascii"), "Times New Roman");
});

const paraDongNhat = await dongThanhParagraph(dong({ inDam: true }));

dung("dòng ĐỒNG NHẤT vẫn ra đúng MỘT `w:r` như trước bản vá", () => {
  const r = timTat(paraDongNhat, "w:r");
  assert.equal(r.length, 1);
  assert.ok(batTat(r[0]!, "w:b"), "`inDam` của cả dòng vẫn còn đường chạy");
  assert.equal(thuocTinh(timTat(r[0]!, "w:sz")[0], "val"), 26);
});

// ───────────────────────────── 4. Phông trên màn hình ──────────────────────
//
// Kho tự host đúng bốn họ (`styles.css`), không họ nào tên "Times New Roman".
const CSS = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");
for (const [nguon, mong] of [
  ["Times New Roman", "Source Serif 4"],
  ["Arial", "Be Vietnam Pro"],
  ["Courier New", "JetBrains Mono"],
  [".VnTime", "Source Serif 4"],
] as const) {
  dung(`phông "${nguon}" ánh xạ về ${mong}`, () => {
    const ho = phongTrenManHinh(nguon);
    assert.ok(ho.includes(mong), `"${nguon}" phải về ${mong}, nhận "${ho}"`);
    assert.ok(
      CSS.includes(`font-family: "${mong}"`),
      `${mong} phải có @font-face trong styles.css — ánh xạ về một họ chữ kho không nạp là một lời đề nghị, không phải một lời hứa`,
    );
  });
}

dung('phông KHÔNG nhận ra → `""` (giữ phông của trang), không dựng stack đoán', () => {
  assert.equal(phongTrenManHinh("SVN-Gilroy"), "");
  assert.equal(phongTrenManHinh(""), "");
});

// ─────────────────────── 5. PDF vẽ được dòng nhiều định dạng ────────────────
const PHONG_PDF = {
  thuong: (
    await readFile(new URL("../public/fonts/source-serif-4-pdf-regular.ttf", import.meta.url))
  ).toString("base64"),
  dam: (
    await readFile(new URL("../public/fonts/source-serif-4-pdf-bold.ttf", import.meta.url))
  ).toString("base64"),
};

const pdfDoan = await noiDungThanhPDF(
  { khoi: [{ kind: "dong", d: dong({ doan: daCat }) }], oKy: [] },
  "Kiểm định dạng chữ",
  PHONG_PDF,
);

dung("PDF vẽ một dòng nhiều định dạng trên đúng một trang", () => {
  assert.deepEqual(pdfDoan.trangCuaKhoi, [1]);
});

// Một dòng dài trộn 13pt với 14pt: phép xếp tham lam phải xuống dòng và tràn
// sang trang, không dồn hết vào một dòng vẽ đè lên nhau.
const DOAN_DAI: DoanChu[] = Array.from({ length: 120 }, (_, i) => ({
  text: `Đoạn số ${i} của một dòng rất dài để đo phép xuống dòng. `,
  inDam: i % 2 === 0,
  inNghieng: false,
  gachChan: false,
  coChu: i % 2 === 0 ? 26 : 28,
  phong: "",
}));
const pdfDai = await noiDungThanhPDF(
  { khoi: [{ kind: "dong", d: dong({ doan: DOAN_DAI }) }], oKy: [] },
  "Kiểm xuống dòng",
  PHONG_PDF,
);

dung("PDF: một dòng dài trộn cỡ chữ vẫn xuống dòng và chảy sang trang", () => {
  assert.ok(pdfDai.pdf.getNumberOfPages() > 1, "phải tràn sang trang thứ hai");
});

// ───────────────────────── 6. Ô BẢNG: cùng bốn điều trên, trong một ô ───────
//
// Trước bản vá này cả ba nơi vẽ tô CẢ ô một kiểu, nên letterhead in đậm của
// biểu mẫu chủ sở hữu ("TRƯỜNG ĐẠI HỌC PHENIKAA TRƯỜNG CÔNG NGHỆ THÔNG TIN")
// ra màn hình thành chữ thường — trong khi CÙNG chữ ấy nằm ngoài bảng thì đậm
// đúng. Bốn chỗ được chốt: cửa vào fail-closed, vòng vẽ↔đọc lại, `.docx` theo
// run, và chiều cao HÀNG trong PDF khi một ô có run to hơn cỡ nền của bảng.
const O_TRAI = "TRƯỜNG ĐẠI HỌC PHENIKAA TRƯỜNG CÔNG NGHỆ THÔNG TIN";
const O_PHAI = "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM";
const CHU_O_NGUON = [
  [
    [
      { dau: 0, cuoi: 23, dam: true, co: 26, phong: "Times New Roman" },
      { dau: 24, cuoi: O_TRAI.length, nghieng: true, gach: true, co: 28 },
    ],
    [],
  ],
];

const banThaoBang = (chuO: unknown) =>
  ({
    id: "bt",
    ten: "Bản thảo tổng quát",
    document: "",
    clauses: [
      {
        key: "muc_1",
        ten: "Đầu trang",
        vung: "than",
        khoi: [{ noi_dung: "", bang: [[O_TRAI, O_PHAI]], chu_o: chuO }],
      },
    ],
  }) as unknown as Parameters<typeof mucTuBanThao>[0];

const chuOCua = (chuO: unknown): DoanChu[][][] => {
  const k = mucTuBanThao(banThaoBang(chuO), null)[0]?.khoi[0];
  assert.equal(k?.kind, "bang");
  return k!.kind === "bang" ? k.chuO : [];
};

const chuODung = chuOCua(CHU_O_NGUON);

dung("ô nhiều định dạng cắt thành các đoạn PHỦ KÍN chữ của ĐÚNG ô đó", () => {
  assert.equal(chuODung[0]![0]!.map((o) => o.text).join(""), O_TRAI);
  assert.deepEqual(
    chuODung[0]![0]!.map((o) => [o.text, o.inDam, o.inNghieng, o.gachChan, o.coChu, o.phong]),
    [
      ["TRƯỜNG ĐẠI HỌC PHENIKAA", true, false, false, 26, "Times New Roman"],
      [" ", false, false, false, 0, ""],
      ["TRƯỜNG CÔNG NGHỆ THÔNG TIN", false, true, true, 28, ""],
    ],
  );
});

dung("ô nguồn KHÔNG khai gì giữ `[]` (đồng nhất), không phải một đoạn phủ kín", () => {
  assert.deepEqual(chuODung[0]![1], []);
});

dung("vắng `chu_o` (bảng mô hình tự gõ, clause cũ) → `[]`, đường cũ", () => {
  assert.deepEqual(chuOCua(undefined), []);
});

dung("lệch HÌNH DẠNG (thiếu ô) làm CẢ bảng về chữ thường", () => {
  assert.deepEqual(chuOCua([[[{ dau: 0, cuoi: 5, dam: true }]]]), []);
});

dung("một Ô có khoảng hỏng chỉ mất định dạng của CHÍNH nó, không kéo theo ô khác", () => {
  const ra = chuOCua([
    [
      [{ dau: 0, cuoi: O_TRAI.length + 9, dam: true }], // tràn khỏi chữ của ô
      [{ dau: 0, cuoi: 8, dam: true }],
    ],
  ]);
  assert.deepEqual(ra[0]![0], [], "ô hỏng về chữ thường");
  assert.equal(ra[0]![1]![0]!.inDam, true, "ô lành vẫn giữ định dạng của nó");
});

// Vòng đi–về: màn hình vẽ `<span data-chu>` TRONG ô, `docBangTuPhanTu` đọc lại
// đúng thứ đã vẽ — cùng khuôn `spanGia`/`theGia` mục 2 đã dùng cho một dòng.
const oGia = (doan: DoanChu[], text: string) => ({
  textContent: text,
  colSpan: 1,
  getAttribute: (_t: string) => null,
  querySelectorAll: (sel: string) =>
    sel === `span[${THUOC_TINH_CHU.moc}]` ? doan.map(spanGia) : [],
});
const bangGia = {
  getAttribute: (_t: string) => null,
  querySelectorAll: (sel: string) =>
    sel === "col"
      ? []
      : [
          {
            getAttribute: (_t: string) => null,
            querySelectorAll: (_s: string) => [oGia(chuODung[0]![0]!, O_TRAI), oGia([], O_PHAI)],
          },
        ],
};
const docLaiBang = docBangTuPhanTu(bangGia);

dung("màn hình vẽ gì TRONG ô thì tệp đọc lại đúng thứ đó", () => {
  assert.deepEqual(docLaiBang.chuO, [[chuODung[0]![0]!, []]]);
  assert.deepEqual(docLaiBang.hang, [[O_TRAI, O_PHAI]]);
});

// `.docx`: mỗi đoạn một `w:r` trong CHÍNH ô đó, đọc giá trị `w:b`/`w:i`/`w:u`/
// `w:sz`/`w:rFonts` chứ không chỉ sự có mặt của thẻ (docx LUÔN ghi `w:b` và
// tắt bằng `w:val="false"`).
const bangDocx = await bangThanhTable(
  docLaiBang.hang,
  docLaiBang.nhip,
  docLaiBang.tiLe,
  false, // bảng bố cục: không viền, nên không có hàng tiêu đề tô đậm cả ô
  docLaiBang.cao,
  docLaiBang.canLeO,
  docLaiBang.chuO,
);
const oDocx = timTat(bangDocx, "w:tc");
const runTrai = timTat(oDocx[0]!, "w:r");
const runPhai = timTat(oDocx[1]!, "w:r");

dung("ba đoạn trong một ô ra BA `w:r`, ô đồng nhất vẫn ra MỘT", () => {
  assert.equal(runTrai.length, 3, "ô nhiều định dạng không được gộp lại một run");
  assert.equal(runPhai.length, 1, "ô không khai gì giữ đúng một run như trước bản vá");
});

dung("chữ từng `w:r` của ô khớp từng đoạn, nối lại ra đúng chữ của ô", () => {
  const chu = runTrai.map(
    (r) =>
      timTat(r, "w:t").map((wt) => (wt["root"] as unknown[]).find((x) => typeof x === "string"))[0],
  );
  assert.deepEqual(
    chu,
    chuODung[0]![0]!.map((o) => o.text),
  );
  assert.equal(chu.join(""), O_TRAI);
});

dung("từng `w:r` của ô mang đúng GIÁ TRỊ đậm/nghiêng/gạch/cỡ/phông của nguồn", () => {
  assert.ok(batTat(runTrai[0]!, "w:b"), "đoạn nguồn khai đậm phải bật `w:b`");
  assert.ok(!batTat(runTrai[1]!, "w:b"), "đoạn giữa không khai đậm phải TẮT `w:b`");
  assert.ok(!batTat(runTrai[2]!, "w:b"));
  assert.ok(batTat(runTrai[2]!, "w:i"), "đoạn nghiêng phải bật `w:i`");
  assert.ok(!batTat(runTrai[0]!, "w:i"));
  assert.equal(timTat(runTrai[2]!, "w:u").length, 1, "gạch chân nguồn phải vào tệp");
  assert.equal(timTat(runTrai[0]!, "w:u").length, 0);
  assert.equal(thuocTinh(timTat(runTrai[0]!, "w:sz")[0], "val"), 26);
  assert.equal(thuocTinh(timTat(runTrai[2]!, "w:sz")[0], "val"), 28);
  assert.equal(thuocTinh(timTat(runTrai[1]!, "w:sz")[0], "val"), 24, "không khai cỡ → cỡ bảng 24");
  assert.equal(thuocTinh(timTat(runTrai[0]!, "w:rFonts")[0], "ascii"), "Times New Roman");
  assert.equal(thuocTinh(timTat(runPhai[0]!, "w:rFonts")[0], "ascii"), "Times New Roman");
});

// PDF: chiều cao HÀNG phải tính theo run LỚN NHẤT của ô, không theo cỡ nền
// của bảng. Đo THẲNG trên hình vẽ ra: khung mỗi ô là một toán tử `re` trong
// luồng nội dung, và tham số thứ tư của nó CHÍNH LÀ chiều cao hàng (điểm, âm
// vì vẽ xuống) — không phải một phép đếm trang gián tiếp.
const LE_DUOI_PT = (20 / 25.4) * 72; // lề dưới 20mm, khớp `LE_PDF.duoi`
const HE_SO_DONG = 1.3; // khớp `HE_SO_DONG_PDF`

function khungOPDF(pdf: { output(k: "arraybuffer"): ArrayBuffer }): { cao: number; day: number }[] {
  const tho = Buffer.from(pdf.output("arraybuffer")).toString("latin1");
  const luong: string[] = [];
  for (const m of tho.matchAll(/stream\r?\n([\s\S]*?)\r?\nendstream/g)) {
    try {
      luong.push(inflateSync(Buffer.from(m[1]!, "latin1")).toString("latin1"));
    } catch {
      // không phải luồng Flate (nhị phân font) — bỏ qua, không phải lỗi.
    }
  }
  return [...luong.join("\n").matchAll(/([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+) re/g)].map((m) => ({
    cao: Math.abs(Number(m[4])),
    day: Number(m[2]) + Number(m[4]),
  }));
}

const O_NGAN = "PHENIKAA";
const CHU_O_TO: DoanChu[][][] = [
  [[{ text: O_NGAN, inDam: true, inNghieng: false, gachChan: false, coChu: 96, phong: "" }], []],
];
const bangMotHang = (chuO: DoanChu[][][]) => ({
  kind: "bang" as const,
  hang: [[O_NGAN, O_PHAI]],
  nhip: [],
  tiLe: [50, 50],
  vien: true, // CÓ viền: khung ô là thứ đo được chiều cao hàng
  cao: [],
  canLeO: [],
  chuO,
});
const { pdf: pdfONen } = await noiDungThanhPDF(
  { khoi: [bangMotHang([])], oKy: [] },
  "Ô cỡ nền",
  PHONG_PDF,
);
const { pdf: pdfORunTo } = await noiDungThanhPDF(
  { khoi: [bangMotHang(CHU_O_TO)], oKy: [] },
  "Ô run 48pt",
  PHONG_PDF,
);

dung("PDF: hàng cao ĐỦ cho run lớn nhất của ô, không theo cỡ nền của bảng", () => {
  const nen = Math.max(...khungOPDF(pdfONen).map((k) => k.cao));
  const to = Math.max(...khungOPDF(pdfORunTo).map((k) => k.cao));
  assert.ok(
    to >= 48 * HE_SO_DONG,
    `hàng phải cao ít nhất một dòng 48pt (${48 * HE_SO_DONG}pt), đo được ${to}pt`,
  );
  assert.ok(to > nen, `cùng chữ, run 48pt phải cho hàng cao hơn cỡ nền (${to} vs ${nen})`);
});

// Chiều cao VẼ RA đúng vẫn chưa đủ: `veBang` hỏi `chieuCaoHangBang` TRƯỚC khi
// vẽ để quyết định có sang trang không. Đo hàng đó bằng cỡ nền thay vì run
// thật thì phép đo nói "còn chỗ" trong khi hàng thật không vừa — hàng bị vẽ
// TRÀN xuống dưới lề. Quét mọi vị trí rơi của bảng thay vì đoán một vị trí
// "khó": chỉ một dải hẹp của chỗ trống còn lại mới lộ ra lỗi này.
let quetTran = 0;
let dayThapNhat = Number.POSITIVE_INFINITY;
for (let n = 0; n <= 45; n++) {
  const { pdf } = await noiDungThanhPDF(
    {
      khoi: [
        ...Array.from({ length: n }, (_, i) => ({
          kind: "dong" as const,
          d: dong({ text: `Dòng nền số ${i} của phần trước bảng.` }),
        })),
        bangMotHang(CHU_O_TO),
      ],
      oKy: [],
    },
    "Tràn lề",
    PHONG_PDF,
  );
  dayThapNhat = Math.min(dayThapNhat, ...khungOPDF(pdf).map((k) => k.day));
  quetTran += 1;
}

dung(`PDF: không hàng nào bị vẽ tràn xuống dưới lề (${quetTran} vị trí)`, () => {
  assert.ok(
    dayThapNhat >= LE_DUOI_PT - 1,
    `đáy thấp nhất ${dayThapNhat}pt phải còn trên lề dưới ${LE_DUOI_PT}pt — ` +
      "phép đo trước khi vẽ phải tính cỡ run của ô",
  );
});

console.log(`kiem-dinh-dang-chu: ${dat}/${dat} đạt`);
