/**
 * Kiểm chạy được cho GIÃN CÁCH, THỤT LỀ và MỐC TAB của tài liệu nguồn
 * (`w:spacing`/`w:ind`/`w:tabs`, quyết định 2026-09-18) — đường từ máy chủ ra
 * màn hình rồi vào tệp tải về.
 *
 * Bốn điều được chốt ở đây, và cả bốn đều là chỗ bố cục hỏng ÂM THẦM:
 *
 * 1. **`gianCachHopLe` fail-closed.** Một offset tab nằm ngoài `noiDung`, một
 *    `pos` âm, một kiểu canh không vẽ được — cả ba đặt chữ và đường dẫn sai
 *    chỗ, và một bố cục sai chỗ khó đọc hơn hẳn một bố cục mặc định.
 * 2. **Cắt rồi đọc lại phải ra ĐÚNG thứ đã cắt**, kể cả đoạn TAB. Vòng đi–về
 *    khép kín là thứ duy nhất chứng minh tệp tải về không nói khác màn hình;
 *    một đoạn tab rỗng chữ mà bị phép lọc "bỏ đoạn rỗng" nuốt mất thì đường
 *    dẫn biến mất khỏi cả `.docx` lẫn PDF trong khi màn hình vẫn vẽ nó.
 * 3. **`.docx` mang đúng `w:spacing`/`w:ind`/`w:tabs` nguồn**, đọc thẳng cây
 *    XML nội bộ của `docx` — không chỉ kiểm hàm NHẬN đúng tham số.
 * 4. **PDF vẽ đường dẫn và nhảy dòng theo giãn dòng nguồn.** Đọc thẳng luồng
 *    nội dung PDF: một mẫu nét đứt phải có mặt, và cùng một nội dung phải
 *    tụt xuống thấp hơn khi nguồn khai giãn dòng đôi.
 *
 * Phần MÀN HÌNH nằm ở `kiem-ui-muot.ts` (mục 7) — chỗ duy nhất trong repo
 * render được một component thật; dựng khung DOM giả thứ hai ở đây là chép
 * lại 250 dòng.
 *
 * Chạy: `npm run kiem-gian-cach` (Node 22, 0 thư viện mới).
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  catTheoChu,
  docDoanChu,
  dongThanhParagraph,
  mucTuBanThao,
  noiDungThanhPDF,
  THUOC_TINH_CHU,
  THUOC_TINH_TAB,
  type DoanChu,
  type DongVanBan,
  type GianCachKhoi,
  type KhoangTab,
} from "../src/lib/xuat-tep.ts";

let dat = 0;
const dung = (ten: string, f: () => void) => {
  try {
    f();
  } catch (e) {
    console.error(`kiem-gian-cach: HỎNG — ${ten}`);
    throw e;
  }
  dat += 1;
};

// ───────────── 1. `gianCachHopLe` qua đúng cửa dữ liệu thật đi vào ──────────
//
// Hàm không xuất khẩu (nó là bộ lọc đầu vào của `khoiMotHopLe`), nên kiểm qua
// một `clause` có khoá `gian_cach` — đúng hình dạng máy chủ gửi xuống.
const NOI_DUNG = "Company name:";
const GC_NGUON = {
  truoc: 120,
  sau: 240,
  dong: 360,
  luat_dong: "auto",
  trai: 720,
  phai: -113,
  dau_dong: 0,
  treo: 426,
  tab: [{ o: NOI_DUNG.length, val: "right", pos: 9360, leader: "dot" }],
};

const banThao = (gc: unknown) =>
  ({
    id: "bt",
    ten: "Bản thảo tổng quát",
    document: "",
    clauses: [
      {
        key: "muc_1",
        ten: "Thân bài",
        vung: "than",
        khoi: [{ noi_dung: NOI_DUNG, bang: [], can_le: "trai", gian_cach: gc }],
      },
    ],
  }) as unknown as Parameters<typeof mucTuBanThao>[0];

const gcCua = (gc: unknown): GianCachKhoi | null => {
  const k = mucTuBanThao(banThao(gc), null)[0]?.khoi[0];
  assert.equal(k?.kind, "vanXuoi");
  return k!.kind === "vanXuoi" ? k.gianCach : null;
};

dung("nhịp hợp lệ đi qua nguyên vẹn, kể cả thụt lề ÂM", () => {
  assert.deepEqual(gcCua(GC_NGUON), {
    truoc: 120,
    sau: 240,
    dong: 360,
    luatDong: "auto",
    trai: 720,
    phai: -113,
    dauDong: 0,
    treo: 426,
    tab: [{ o: NOI_DUNG.length, val: "right", pos: 9360, leader: "dot" }],
  });
});

dung("vắng `gian_cach` (khối không tra được, clause cũ) → `null`", () => {
  assert.equal(gcCua(undefined), null);
});

for (const [ten, xau] of [
  ["offset tab tràn khỏi nội dung", { ...GC_NGUON, tab: [{ o: NOI_DUNG.length + 1, pos: 9360 }] }],
  ["offset tab âm", { ...GC_NGUON, tab: [{ o: -1, pos: 9360 }] }],
  ["offset tab không nguyên", { ...GC_NGUON, tab: [{ o: 1.5, pos: 9360 }] }],
  ["mốc ở toạ độ 0 (không tồn tại trên trang nào)", { ...GC_NGUON, tab: [{ o: 0, pos: 0 }] }],
  ["mốc ở toạ độ âm", { ...GC_NGUON, tab: [{ o: 0, pos: -720 }] }],
  ["kiểu canh không vẽ được", { ...GC_NGUON, tab: [{ o: 0, pos: 720, val: "bar" }] }],
  ["giãn dòng âm", { ...GC_NGUON, dong: -240 }],
  ["số đọc không ra", { ...GC_NGUON, trai: "bảy trăm hai mươi" }],
  ["`tab` không phải mảng", { ...GC_NGUON, tab: "một" }],
  ["không phải object", "giãn dòng đôi"],
] as const) {
  dung(`fail-closed: ${ten}`, () => {
    assert.equal(gcCua(xau), null, `${ten}: CẢ khối phải về nhịp mặc định, không nhận một phần`);
  });
}

dung("đường dẫn lạ về rỗng (không vẽ) chứ không làm hỏng cả khối", () => {
  const g = gcCua({ ...GC_NGUON, tab: [{ o: 0, pos: 720, val: "left", leader: "ngôi sao" }] });
  assert.equal(g?.tab[0]?.leader, "", "`w:leader` lạ = `none`, đúng mặc định của chính nó");
});

// ────────────── 2. Cắt (màn hình vẽ) ↔ đọc lại (tệp đọc), có TAB ────────────
const TAB_CUOI: KhoangTab[] = [{ o: NOI_DUNG.length, val: "right", pos: 9360, leader: "dot" }];
const daCat = catTheoChu(NOI_DUNG, [], TAB_CUOI);

dung("các đoạn CHỮ nối lại vẫn ra đúng chuỗi ban đầu — tab KHÔNG thêm ký tự nào", () => {
  assert.equal(daCat.map((o) => o.text).join(""), NOI_DUNG);
});

dung("mốc tab thành MỘT đoạn riêng, rỗng chữ, đúng chỗ nó đứng", () => {
  assert.equal(daCat.length, 2);
  assert.equal(daCat[0]?.text, NOI_DUNG);
  assert.equal(daCat[1]?.text, "");
  assert.deepEqual(daCat[1]?.tab, { val: "right", pos: 9360, leader: "dot" });
});

dung("tab GIỮA dòng cắt một khoảng định dạng làm đôi, không kết thúc nó", () => {
  const chia = catTheoChu(
    "AB",
    [{ dau: 0, cuoi: 2, dam: true, nghieng: false, gach: false, co: 0, phong: "" }],
    [{ o: 1, val: "left", pos: 720, leader: "" }],
  );
  assert.deepEqual(
    chia.map((o) => [o.text, o.inDam, o.tab !== null]),
    [
      ["A", true, false],
      ["", false, true],
      ["B", true, false],
    ],
  );
});

/** Một `<span>` giả dựng TỪ một `DoanChu`, đúng bảng tên `THUOC_TINH_*` mà
 * `XemTruocA4` ghi ra — chỉ cần `textContent`/`getAttribute`, như chính
 * `docDoanChu` đòi (repo này không có `jsdom`). */
const spanGia = (o: DoanChu) => {
  const thuoc: Record<string, string> = { [THUOC_TINH_CHU.moc]: "" };
  if (o.tab) {
    thuoc[THUOC_TINH_TAB.moc] = "";
    thuoc[THUOC_TINH_TAB.val] = o.tab.val;
    thuoc[THUOC_TINH_TAB.pos] = String(o.tab.pos);
    if (o.tab.leader) thuoc[THUOC_TINH_TAB.leader] = o.tab.leader;
  }
  if (o.inDam) thuoc[THUOC_TINH_CHU.dam] = "1";
  if (o.coChu > 0) thuoc[THUOC_TINH_CHU.co] = String(o.coChu);
  return { textContent: o.text, getAttribute: (t: string) => thuoc[t] ?? null };
};

const theGia = (doan: DoanChu[]) => ({
  querySelectorAll: (sel: string) =>
    sel === `span[${THUOC_TINH_CHU.moc}]` ? doan.map(spanGia) : [],
});

dung("màn hình vẽ gì thì tệp đọc lại đúng thứ đó, kể cả đoạn TAB rỗng chữ", () => {
  assert.deepEqual(docDoanChu(theGia(daCat)), daCat);
});

dung("đoạn tab mất `pos` thì bị BỎ, không nhảy tới một toạ độ không biết", () => {
  const hong = { ...daCat[1]!, tab: { val: "right", pos: 0, leader: "dot" } };
  assert.deepEqual(docDoanChu(theGia([daCat[0]!, hong])), [daCat[0]]);
});

// ───────────────────────── 3. `.docx` mang nhịp nguồn ──────────────────────
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

/** Một thuộc tính XML của thẻ đầu tiên mang `key` trong cây nội bộ `docx` —
 *  cùng hàm `kiem-dinh-dang-chu.ts` dùng, hai hình dạng `_attr` cùng tồn tại. */
function thuocTinh(the: Record<string, unknown> | undefined, ten: string): unknown {
  const attr = ((the?.["root"] as Record<string, unknown>[] | undefined)?.[0]?.["root"] ??
    {}) as Record<string, unknown>;
  const v = attr[ten];
  return v && typeof v === "object" && "value" in v ? (v as { value: unknown }).value : v;
}

const dong = (extra: Partial<DongVanBan> = {}): DongVanBan => ({
  text: NOI_DUNG,
  kieu: "thuong",
  canhLe: "trai",
  inDam: false,
  inNghieng: false,
  thutLe: 0,
  doan: [],
  gianCach: null,
  ...extra,
});

const GC_DONG = {
  truoc: 120,
  sau: 240,
  dong: 360,
  luatDong: "auto",
  trai: 720,
  phai: 113,
  dauDong: 0,
  treo: 426,
};
const paraNguon = await dongThanhParagraph(dong({ doan: daCat, gianCach: GC_DONG }));

dung("`w:spacing` mang đúng before/after/line/lineRule NGUỒN", () => {
  const sp = timTat(paraNguon, "w:spacing")[0];
  assert.equal(thuocTinh(sp, "before"), 120);
  assert.equal(thuocTinh(sp, "after"), 240);
  assert.equal(thuocTinh(sp, "line"), 360);
  assert.equal(thuocTinh(sp, "lineRule"), "auto");
});

dung("`w:ind` mang đúng left/right/hanging NGUỒN", () => {
  const ind = timTat(paraNguon, "w:ind")[0];
  assert.equal(thuocTinh(ind, "left"), 720);
  assert.equal(thuocTinh(ind, "right"), 113);
  assert.equal(thuocTinh(ind, "hanging"), 426);
});

dung("`w:tabs` mang đúng val/pos/leader NGUỒN", () => {
  const tabs = timTat(paraNguon, "w:tabs");
  assert.equal(tabs.length, 1, "một `w:tabs` cho cả đoạn");
  const moc = timTat(tabs[0], "w:tab").filter((t) => thuocTinh(t, "pos") !== undefined);
  assert.equal(moc.length, 1);
  assert.equal(thuocTinh(moc[0], "val"), "right");
  assert.equal(thuocTinh(moc[0], "pos"), 9360);
  assert.equal(thuocTinh(moc[0], "leader"), "dot");
});

dung("ký tự tab ra một `w:r` RIÊNG chứa `w:tab` rỗng — Word tự vẽ đường dẫn", () => {
  const runs = timTat(paraNguon, "w:r");
  assert.equal(runs.length, 2, "một run chữ, một run tab");
  const trongRun = timTat(runs[1]!, "w:tab");
  assert.equal(trongRun.length, 1);
  assert.equal(thuocTinh(trongRun[0], "pos"), undefined, "ký tự tab không mang toạ độ nào");
  assert.equal(timTat(runs[0]!, "w:tab").length, 0, "run chữ không được mang tab");
});

const paraKhongNguon = await dongThanhParagraph(dong({ thutLe: 38 }));

dung("đoạn KHÔNG có nhịp nguồn giữ nguyên thể thức KLAW như trước bản vá", () => {
  const sp = timTat(paraKhongNguon, "w:spacing")[0];
  assert.equal(thuocTinh(sp, "after"), 120);
  assert.equal(thuocTinh(sp, "line"), 312);
  assert.equal(thuocTinh(sp, "before"), undefined);
  assert.ok(timTat(paraKhongNguon, "w:ind").length === 1, "`thutLe` màn hình vẫn còn đường chạy");
  assert.equal(timTat(paraKhongNguon, "w:tabs").length, 0);
});

// ─────────────────── 4. PDF vẽ đường dẫn và nhảy dòng theo nguồn ────────────
const PHONG_PDF = {
  thuong: (
    await readFile(new URL("../public/fonts/source-serif-4-pdf-regular.ttf", import.meta.url))
  ).toString("base64"),
  dam: (
    await readFile(new URL("../public/fonts/source-serif-4-pdf-bold.ttf", import.meta.url))
  ).toString("base64"),
};

/** Luồng nội dung của một trang PDF — mảng lệnh thô, đúng thứ jsPDF sắp ghi
 *  ra tệp. Đọc RUỘT một thư viện, không phải một API có hợp đồng; đổi lại
 *  đây là chỗ duy nhất chứng minh được đường dẫn THẬT SỰ được vẽ. */
const lenhTrang = (pdf: unknown, trang = 1): string[] =>
  (pdf as { internal: { pages: string[][] } }).internal.pages[trang] ?? [];

const pdfDan = await noiDungThanhPDF(
  { khoi: [{ kind: "dong", d: dong({ doan: daCat, gianCach: GC_DONG }) }], oKy: [] },
  "Kiểm giãn cách",
  PHONG_PDF,
);
const lenhDan = lenhTrang(pdfDan.pdf);

dung("PDF vẽ đường dẫn bằng một mẫu NÉT ĐỨT, không bằng chuỗi dấu chấm", () => {
  const i = lenhDan.findIndex((l) => /^\[[\d. ]+\] [\d.]+ d$/.test(l));
  assert.ok(i >= 0, "phải có một lệnh đặt mẫu nét đứt");
  assert.ok(/ m$/.test(lenhDan[i + 1] ?? ""), "rồi tới điểm bắt đầu đường");
  assert.ok(/ l$/.test(lenhDan[i + 2] ?? ""), "rồi tới điểm kết thúc");
  assert.equal(lenhDan[i + 3], "S", "rồi mới kẻ");
  assert.equal(lenhDan[i + 4], "[] 0. d", "và trả mẫu nét về liền ngay sau đó");
});

dung("đường dẫn chạy TỚI mốc, cắt ở mép phải cột chữ khi mốc vượt khổ giấy", () => {
  const i = lenhDan.findIndex((l) => /^\[[\d. ]+\] [\d.]+ d$/.test(l));
  const x1 = Number(lenhDan[i + 1]!.split(" ")[0]);
  const x2 = Number(lenhDan[i + 2]!.split(" ")[0]);
  // Mốc 9360 twip = 165mm, rộng hơn cột chữ A4 lề 30/20mm (160mm), nên đường
  // dẫn dừng ở MÉP PHẢI của chính đoạn: 210 − 20 mm, lùi thêm đúng `w:ind/
  // @w:right` (113 twip) mà đoạn này khai.
  const mepPhai = 210 - 20 - (GC_DONG.phai / 20) * (25.4 / 72);
  assert.ok(x2 > x1, "đường dẫn phải chạy sang phải");
  assert.ok(Math.abs(x2 - (mepPhai / 25.4) * 72) < 0.5, `mép phải cột chữ, nhận ${x2}`);
});

/** `y` của lệnh đặt chữ đầu tiên trong một luồng trang — càng NHỎ càng thấp
 *  trên giấy (gốc toạ độ PDF nằm ở đáy trang). */
const yChuDau = (lenh: string[], bo: number): number => {
  const td = lenh.filter((l) => l.includes(" Td\n"));
  return Number(td[bo]!.match(/\n([\d.]+) ([\d.]+) Td/)![2]);
};

const haiDoan = (gc: DongVanBan["gianCach"]) => ({
  khoi: [
    { kind: "dong" as const, d: dong({ text: "Dòng thứ nhất của đoạn.", gianCach: gc }) },
    { kind: "dong" as const, d: dong({ text: "Dòng thứ hai của đoạn.", gianCach: gc }) },
  ],
  oKy: [],
});
const MOT_DONG = { ...GC_DONG, truoc: 0, sau: 0, trai: 0, phai: 0, treo: 0, dong: 240 };
const yMot = yChuDau(
  lenhTrang((await noiDungThanhPDF(haiDoan(MOT_DONG), "Một dòng", PHONG_PDF)).pdf),
  1,
);
const yDoi = yChuDau(
  lenhTrang((await noiDungThanhPDF(haiDoan({ ...MOT_DONG, dong: 480 }), "Đôi", PHONG_PDF)).pdf),
  1,
);
const yMacDinh = yChuDau(
  lenhTrang((await noiDungThanhPDF(haiDoan(null), "Mặc định", PHONG_PDF)).pdf),
  1,
);

dung("bước nhảy dòng ĐI THEO `w:line` nguồn, cả khi giãn hơn lẫn khi chặt hơn", () => {
  assert.ok(
    yMot > yMacDinh,
    `giãn dòng đơn nguồn (240) phải CHẶT hơn hệ số mặc định 1,3 của KLAW: ${yMot} vs ${yMacDinh}`,
  );
  assert.ok(
    yMacDinh > yDoi,
    `giãn dòng đôi nguồn (480) phải THƯA hơn mặc định: ${yDoi} vs ${yMacDinh}`,
  );
  // 240 → 480 là gấp đôi đúng một dòng 13pt: đoạn sau tụt thêm đúng 13pt.
  assert.ok(Math.abs(yMot - yDoi - 13) < 0.5, `đúng một dòng 13pt, nhận ${yMot - yDoi}`);
});

const yKhongTruoc = yChuDau(
  lenhTrang((await noiDungThanhPDF(haiDoan(MOT_DONG), "Không trước", PHONG_PDF)).pdf),
  0,
);
const yCoTruoc = yChuDau(
  lenhTrang(
    (await noiDungThanhPDF(haiDoan({ ...MOT_DONG, truoc: 240 }), "Có trước", PHONG_PDF)).pdf,
  ),
  0,
);

dung("`w:spacing/@w:before` đẩy đoạn xuống đúng số twip nó khai", () => {
  assert.ok(
    Math.abs(yKhongTruoc - yCoTruoc - 12) < 0.5,
    `240 twip = 12pt, nhận ${yKhongTruoc - yCoTruoc}`,
  );
});

console.log(`kiem-gian-cach: ${dat}/${dat} đạt`);
