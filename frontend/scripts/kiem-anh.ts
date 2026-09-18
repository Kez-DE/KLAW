/**
 * Kiểm chạy được cho ẢNH ĐÃ TÁCH của tài liệu nguồn — logo letterhead, con
 * dấu, chữ ký quét (quyết định 2026-09-18, mục `media` của
 * `eval.run_trung_thuc`).
 *
 * Bốn bất biến, và ba trong bốn hỏng ÂM THẦM:
 *
 *   1. CỬA VÀO `clauses` là một cửa AN TOÀN. `url` đi thẳng vào `src` của một
 *      `<img>`, nên một `javascript:` hay một tên miền lạ lọt vào cột JSONB
 *      `ban_thao.clauses` không được có đường nào ra tới đó. Hỏng ở đây không
 *      làm gì đỏ cả — nó chỉ mở một lỗ XSS trong trang của chính chủ tài liệu.
 *   2. MÀN HÌNH VÀ TỆP NÓI CÙNG MỘT CỠ. Màn hình vẽ bằng `data-anh-rong/cao`
 *      và `.docx`/PDF đọc lại đúng hai thuộc tính ấy — một nguồn, ba nơi
 *      dùng, đúng luật `data-cao`/`data-le-*` của bốn phase trước.
 *   3. NGUỒN KHÔNG KHAI CỠ thì lùi về cỡ THẬT của ảnh (`naturalWidth`), không
 *      về một con số bịa.
 *   4. FAIL CLOSED: ảnh không tải được thì `.docx` vẫn ra tệp và PDF vẫn ra
 *      trang — một con dấu hỏng không đáng làm hỏng cả bản tải về.
 *
 * `fetch` bị thay bằng một hàm giả ở đây: kịch bản này chạy trong Node, không
 * có máy chủ, và điều đang đo là phép DỰNG TỆP chứ không phải phép gọi mạng.
 *
 * Ảnh dùng để thử là PNG 1×1 sinh tại chỗ — không một con dấu hay chữ ký thật
 * nào vào kho mã (quyết định 2026-09-18, phần "media là dữ liệu cá nhân của
 * bên thứ ba").
 *
 * Chạy: `npm run kiem-anh`.
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  anhThanhParagraph,
  anhTuBanThao,
  docNoiDungTuDOM,
  EMU_MOI_PX,
  noiDungThanhPDF,
  THUOC_TINH_ANH,
  type AnhNguon,
  type BanThao,
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

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM" +
    "IQAAAABJRU5ErkJggg==",
  "base64",
);

/** URL ảnh HỢP LỆ duy nhất mà cửa vào chấp nhận — đường dẫn tương đối tới
 *  endpoint kiểm chủ sở hữu. */
const URL_THAT = "/tai-lieu/11111111-2222-3333-4444-555555555555/anh/logo.png";

const banThao = (anh: unknown): BanThao =>
  ({
    clauses: [
      { key: "muc_0", ten: "Không có ảnh", khoi: [] },
      { key: "muc_1", ten: "Quốc hiệu", khoi: [], anh },
    ],
  }) as unknown as BanThao;

// ──────────────────────────────────────────── 1. cửa vào `clauses`, fail closed

bang(
  anhTuBanThao(
    banThao([{ url: URL_THAT, rong: 1733550, cao: 537039, vung: "dau_trang", thu_tu: 0 }]),
  ),
  [{ url: URL_THAT, rong: 1733550, cao: 537039, vung: "dau_trang", thuTu: 0 }],
  "ảnh đọc ở clause ĐẦU TIÊN CÓ khoá, không phải clause thứ nhất",
);
bang(anhTuBanThao(banThao(undefined)), [], "bản thảo lưu TRƯỚC trường này → rỗng");
bang(anhTuBanThao(banThao([])), [], "tài liệu không có ảnh → rỗng");
bang(anhTuBanThao(banThao("logo.png")), [], "khoá sai kiểu → rỗng, không ném");

for (const xau of [
  "javascript:alert(1)",
  "data:image/svg+xml,<svg onload=alert(1)>",
  "https://ke-tan-cong.example/logo.png",
  "//ke-tan-cong.example/logo.png",
  "/tai-lieu/x/anh/../../../etc/passwd",
  "/tai-lieu/x/anh/logo.png?x=1",
  "/soan-thao/x/anh/logo.png",
]) {
  bang(
    anhTuBanThao(banThao([{ url: xau, rong: 1, cao: 1, vung: "than", thu_tu: 0 }])),
    [],
    `URL nguy hiểm/lạ bị chặn ở CỬA VÀO: ${xau}`,
  );
}

bang(
  anhTuBanThao(
    banThao([
      { url: URL_THAT, rong: 1, cao: 1, vung: "chan_trang", thu_tu: 0 },
      { url: "javascript:alert(1)", rong: 1, cao: 1, vung: "than", thu_tu: 0 },
      { url: URL_THAT, rong: 1, cao: 1, vung: "dau_trang", thu_tu: 0 },
      { url: URL_THAT, rong: 1, cao: 1, vung: "than", thu_tu: 1 },
    ]),
  ).map((a) => `${a.vung}${a.thuTu}`),
  ["dau_trang0", "than1", "chan_trang0"],
  "một ảnh hỏng bỏ RIÊNG nó (khác lề trang, vốn fail-closed cả bộ); còn lại xếp theo VÙNG rồi thứ tự nguồn",
);

// ─────────────────────────────── 2. đọc lại từ DOM — màn hình và tệp cùng cỡ

/** Thẻ `<img>` giả: `docNoiDungTuDOM` chỉ hỏi đúng những thứ dưới đây (repo
 *  này không có `jsdom`, xem `kiem-xuat-tep.ts`). */
const imgGia = (thuoc: Record<string, string>, tuNhien = { w: 0, h: 0 }) => ({
  tagName: "IMG",
  naturalWidth: tuNhien.w,
  naturalHeight: tuNhien.h,
  getAttribute: (t: string) => thuoc[t] ?? null,
  closest: () => null,
  querySelectorAll: () => [],
});

const toGia = (con: unknown[]) =>
  ({
    querySelector: () => null,
    querySelectorAll: (sel: string) => (sel.includes("img") ? con : []),
    getAttribute: () => null,
  }) as never;

const docKhoi = (con: unknown[]) => docNoiDungTuDOM(toGia(con)).khoi;

bang(
  docKhoi([
    imgGia({
      src: URL_THAT,
      [THUOC_TINH_ANH.moc]: "",
      [THUOC_TINH_ANH.rong]: "1733550",
      [THUOC_TINH_ANH.cao]: "537039",
    }),
  ]),
  [{ kind: "anh", a: { url: URL_THAT, rong: 1733550, cao: 537039, vung: "than", thuTu: 0 } }],
  "cỡ NGUỒN (EMU) đi thẳng từ `data-*` màn hình đã vẽ vào tệp — không đọc `px` đã tính rồi quy ngược",
);

bang(
  docKhoi([imgGia({ src: URL_THAT, [THUOC_TINH_ANH.moc]: "" }, { w: 96, h: 48 })]),
  [
    {
      kind: "anh",
      a: { url: URL_THAT, rong: 96 * EMU_MOI_PX, cao: 48 * EMU_MOI_PX, vung: "than", thuTu: 0 },
    },
  ],
  "nguồn KHÔNG khai cỡ → lùi về cỡ THẬT của ảnh, không về một con số bịa",
);

bang(
  docKhoi([imgGia({ src: URL_THAT, [THUOC_TINH_ANH.moc]: "" })]),
  [],
  "ảnh chưa tải được (cỡ nguồn 0 và cỡ thật 0) bị BỎ — chừa chỗ cho thứ không vẽ ra sẽ đẩy lệch mọi khối sau",
);
bang(
  docKhoi([imgGia({ [THUOC_TINH_ANH.moc]: "", [THUOC_TINH_ANH.rong]: "100" }, { w: 1, h: 1 })]),
  [],
  "thẻ không có `src` bị bỏ",
);

// ───────────────────────────────────────────────────── 3. `.docx` — ImageRun

const fetchThat = globalThis.fetch;
const datFetch = (tra: () => Promise<Response>) => {
  globalThis.fetch = tra as typeof fetch;
};
const fetchOk = () => datFetch(async () => new Response(new Uint8Array(PNG), { status: 200 }));

const anhMau: AnhNguon = {
  url: URL_THAT,
  // 1733550 EMU = 182px; 537039 EMU = 56,4px → 56.
  rong: 1733550,
  cao: 537039,
  vung: "dau_trang",
  thuTu: 0,
};

/** Duyệt cây XML `docx` tìm mọi nút mang tên `ten` — cùng phép `kiem-vien-le`
 *  dùng, chỉ khác chỗ nó tra. */
function timNut(nut: unknown, ten: string): Record<string, unknown>[] {
  const ra: Record<string, unknown>[] = [];
  const di = (n: unknown) => {
    if (Array.isArray(n)) return n.forEach(di);
    if (!n || typeof n !== "object") return;
    const o = n as Record<string, unknown>;
    if (o["rootKey"] === ten) ra.push(o);
    for (const v of Object.values(o)) di(v);
  };
  di(nut);
  return ra;
}

fetchOk();
const doanAnh = await anhThanhParagraph(anhMau);
ok(timNut(doanAnh, "w:drawing").length === 1, "`.docx` có ĐÚNG một `w:drawing` cho một ảnh");
const ext = timNut(doanAnh, "wp:extent")[0] as { root?: Record<string, unknown> } | undefined;
const thuoc = (ext?.root as Record<string, unknown> | undefined) ?? {};
const cx = JSON.stringify(thuoc);
ok(
  cx.includes(String(Math.round(anhMau.rong / EMU_MOI_PX) * EMU_MOI_PX)),
  `cỡ trong .docx đúng bằng cỡ NGUỒN khai, không qua một phép làm tròn nào của mình (${cx.slice(0, 200)})`,
);

datFetch(async () => new Response(null, { status: 404 }));
const doanHong = await anhThanhParagraph(anhMau);
bang(
  timNut(doanHong, "w:drawing").length,
  0,
  "ảnh không tải được → đoạn RỖNG, không ném: cả tệp vẫn tải về được",
);

datFetch(async () => new Response(new Uint8Array([0x3c, 0x73, 0x76, 0x67]), { status: 200 }));
bang(
  timNut(await anhThanhParagraph(anhMau), "w:drawing").length,
  0,
  "bytes KHÔNG phải png/jpg/gif/bmp bị từ chối ở phía tệp nữa, kể cả khi máy chủ phát ra",
);

// ─────────────────────────────────────────────────────────── 4. PDF — vẽ thật

const phongChuPDF: PhongChuPDF = {
  thuong: (
    await readFile(new URL("../public/fonts/source-serif-4-pdf-regular.ttf", import.meta.url))
  ).toString("base64"),
  dam: (
    await readFile(new URL("../public/fonts/source-serif-4-pdf-bold.ttf", import.meta.url))
  ).toString("base64"),
};

const noiDungAnh = (a: AnhNguon | null): NoiDungXuat => ({
  khoi: a ? [{ kind: "anh", a }] : [],
  oKy: [],
  leTrang: null,
});

fetchOk();
const { pdf: pdfCoAnh } = await noiDungThanhPDF(noiDungAnh(anhMau), "Có ảnh", phongChuPDF);
const { pdf: pdfKhongAnh } = await noiDungThanhPDF(noiDungAnh(null), "Không ảnh", phongChuPDF);
/** Số XObject ẢNH thật trong tệp. `"/Image"` trần trụi KHÔNG dùng được: jsPDF
 *  luôn ghi sẵn một bảng `/XObject` và chuỗi `ImageI` vào mọi tệp, kể cả tệp
 *  không có ảnh nào — đếm nó sẽ xanh cả khi ảnh không được vẽ. */
const demAnh = (s: string) => s.split("/Subtype /Image").length - 1;
const thoCo = Buffer.from(pdfCoAnh.output("arraybuffer")).toString("latin1");
const thoKhong = Buffer.from(pdfKhongAnh.output("arraybuffer")).toString("latin1");
ok(
  demAnh(thoCo) > 0 && demAnh(thoKhong) === 0,
  `PDF có ảnh mang XObject ảnh THẬT, PDF không ảnh thì không — ảnh được VẼ, không chỉ nằm trong một thuộc tính (${demAnh(thoCo)} vs ${demAnh(thoKhong)})`,
);

// Một ảnh CAO hơn cả trang phải sang trang mới chứ không lặp vô hạn, và một
// dãy ảnh phải đẩy sang trang thứ hai — luật "không chẻ khối" của khối ký.
const anhCao: AnhNguon = { ...anhMau, rong: 2_000_000, cao: 5_000_000 };
const { pdf: pdfNhieu } = await noiDungThanhPDF(
  {
    khoi: Array.from({ length: 3 }, () => ({ kind: "anh" as const, a: anhCao })),
    oKy: [],
    leTrang: null,
  },
  "Ba ảnh cao",
  phongChuPDF,
);
ok(
  pdfNhieu.getNumberOfPages() > 1,
  `ba tấm ảnh cao 5,47cm mỗi tấm phải tràn sang trang mới (${pdfNhieu.getNumberOfPages()} trang)`,
);

datFetch(async () => new Response(null, { status: 404 }));
const { pdf: pdfAnhHong } = await noiDungThanhPDF(noiDungAnh(anhMau), "Ảnh hỏng", phongChuPDF);
ok(
  pdfAnhHong.getNumberOfPages() === 1 &&
    demAnh(Buffer.from(pdfAnhHong.output("arraybuffer")).toString("latin1")) === 0,
  "ảnh không tải được → PDF vẫn ra trang, không ném và không chừa chỗ trống",
);

globalThis.fetch = fetchThat;
console.info(`kiem-anh: ${dat}/${dat} đạt`);
