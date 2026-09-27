/**
 * Phase 15 ("điều chỉnh UI mượt mà") — bốn phép kiểm HÀNH VI trên chính
 * component đã biên dịch, không phải trên hằng số hay chuỗi nguồn:
 *
 *   1. khối văn xuôi gõ được mang `role="textbox"`, `aria-multiline`,
 *      `lang="vi"` và ba thuộc tính tắt tự-sửa (R4/R7);
 *   2. Escape trả khối về chữ lúc bắt đầu sửa và KHÔNG gọi lưu (R6);
 *   3. `muc` được memo — một lượt render lại vì prop không liên quan không
 *      tính lại `mucTuBanThao` (R3);
 *   4. một lượt lưu hỏng để lại dấu thấy được trên ĐÚNG khối đó và đưa tiêu
 *      điểm về đó (R5);
 *   5. bảng nguồn KHÔNG viền ra bố cục (không <th> giả, không lớp viền, căn
 *      lề và chiều cao hàng của nguồn có mặt trên DOM), bảng CÓ viền không
 *      đổi gì. Ở đây vì khung DOM giả + `runnerImport` của tệp này là chỗ
 *      DUY NHẤT trong repo render được một component thật — dựng khung thứ
 *      hai chỉ để kiểm một bảng là chép lại 250 dòng DOM giả.
 *
 * Không có `jsdom` trong repo (xem `kiem-toast.ts`) và Node không đọc `.tsx`,
 * nên script này (1) mượn `runnerImport` của Vite — cùng bộ biên dịch và alias
 * `@/` mà `vite dev` dùng — để nạp `.tsx` vào Node, và (2) dựng một DOM giả
 * vừa ĐỦ cho `react-dom/client`: cây nút, thuộc tính, `focus`/`blur`, và phát
 * sự kiện lên root (React 17+ chỉ nghe ở root container). 0 thư viện mới.
 * Chạy: `npm run kiem-ui-muot`.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import type { BanThao } from "../src/lib/klaw.ts";
import type { Muc } from "../src/lib/xuat-tep.ts";

// ───────────────────────────────────────────────── DOM giả vừa đủ cho React
const HTML_NS = "http://www.w3.org/1999/xhtml";
const SVG_NS = "http://www.w3.org/2000/svg";

type Nghe = (e: Record<string, unknown>) => void;

function taoStyle() {
  const s: Record<string, unknown> = {};
  s["setProperty"] = (k: string, v: string) => {
    s[k] = v;
  };
  s["removeProperty"] = (k: string) => {
    delete s[k];
  };
  return s;
}

class Nut {
  nodeType: number;
  nodeName: string;
  tagName: string;
  namespaceURI: string | null;
  ownerDocument: TaiLieu;
  parentNode: Nut | null = null;
  childNodes: Nut[] = [];
  nodeValue: string | null;
  thuocTinh = new Map<string, string>();
  style = taoStyle();
  nghe = new Map<string, Nghe[]>();
  onclick: unknown = null;

  constructor(
    doc: TaiLieu | null,
    nodeType: number,
    ten: string,
    ns: string | null,
    chu: string | null,
  ) {
    this.ownerDocument = doc ?? (this as unknown as TaiLieu);
    this.nodeType = nodeType;
    this.nodeName = nodeType === 1 ? ten.toUpperCase() : ten;
    this.tagName = this.nodeName;
    this.namespaceURI = ns;
    this.nodeValue = chu;
  }
  get firstChild() {
    return this.childNodes[0] ?? null;
  }
  get lastChild() {
    return this.childNodes[this.childNodes.length - 1] ?? null;
  }
  get nextSibling() {
    const anh = this.parentNode?.childNodes ?? [];
    return anh[anh.indexOf(this) + 1] ?? null;
  }
  get previousSibling() {
    const anh = this.parentNode?.childNodes ?? [];
    return anh[anh.indexOf(this) - 1] ?? null;
  }
  appendChild(con: Nut) {
    return this.insertBefore(con, null);
  }
  insertBefore(con: Nut, truoc: Nut | null) {
    con.parentNode?.removeChild(con);
    const i = truoc === null ? this.childNodes.length : this.childNodes.indexOf(truoc);
    this.childNodes.splice(i, 0, con);
    con.parentNode = this;
    return con;
  }
  removeChild(con: Nut) {
    const i = this.childNodes.indexOf(con);
    if (i >= 0) this.childNodes.splice(i, 1);
    con.parentNode = null;
    return con;
  }
  contains(n: Nut | null) {
    for (let x = n; x !== null; x = x.parentNode) if (x === this) return true;
    return false;
  }
  // HTML hạ chữ thường tên thuộc tính (`spellCheck` → `spellcheck`), SVG thì không.
  tenThuocTinh(t: string) {
    return this.namespaceURI === SVG_NS ? t : t.toLowerCase();
  }
  setAttribute(t: string, v: unknown) {
    this.thuocTinh.set(this.tenThuocTinh(t), String(v));
  }
  getAttribute(t: string) {
    return this.thuocTinh.get(this.tenThuocTinh(t)) ?? null;
  }
  removeAttribute(t: string) {
    this.thuocTinh.delete(this.tenThuocTinh(t));
  }
  hasAttribute(t: string) {
    return this.thuocTinh.has(this.tenThuocTinh(t));
  }
  get textContent(): string {
    if (this.nodeType === 3) return this.nodeValue ?? "";
    return this.childNodes.map((c) => c.textContent).join("");
  }
  set textContent(v: string) {
    if (this.nodeType === 3) {
      this.nodeValue = v;
      return;
    }
    for (const c of this.childNodes) c.parentNode = null;
    this.childNodes = [];
    if (v !== "") this.appendChild(this.ownerDocument.createTextNode(v));
  }
  get innerText() {
    return this.textContent;
  }
  set innerText(v: string) {
    this.textContent = v;
  }
  get isContentEditable(): boolean {
    return (
      this.getAttribute("contenteditable") === "true" ||
      (this.parentNode?.isContentEditable ?? false)
    );
  }
  addEventListener(type: string, fn: Nghe, opts?: boolean | { capture?: boolean }) {
    const capture = opts === true || (typeof opts === "object" && opts.capture === true);
    const k = `${type}:${capture ? "c" : "b"}`;
    this.nghe.set(k, [...(this.nghe.get(k) ?? []), fn]);
  }
  removeEventListener(type: string, fn: Nghe, opts?: boolean | { capture?: boolean }) {
    const capture = opts === true || (typeof opts === "object" && opts.capture === true);
    const k = `${type}:${capture ? "c" : "b"}`;
    this.nghe.set(
      k,
      (this.nghe.get(k) ?? []).filter((f) => f !== fn),
    );
  }
  focus() {
    const doc = this.ownerDocument;
    if (doc.activeElement === this) return;
    const truoc = doc.activeElement;
    doc.activeElement = this;
    if (truoc !== doc.body) phat(truoc, "focusout", { relatedTarget: this });
    phat(this, "focusin", { relatedTarget: truoc });
  }
  blur() {
    const doc = this.ownerDocument;
    if (doc.activeElement !== this) return;
    doc.activeElement = doc.body;
    phat(this, "focusout", { relatedTarget: null });
  }
}

class TaiLieu extends Nut {
  documentElement: Nut;
  /** `sonner` chèn một `<style>` vào `head` ngay lúc nạp module. */
  head: Nut;
  body: Nut;
  activeElement: Nut;
  defaultView: unknown = null;
  constructor() {
    super(null, 9, "#document", null, null);
    this.documentElement = this.createElement("html");
    this.head = this.createElement("head");
    this.body = this.createElement("body");
    this.appendChild(this.documentElement);
    this.documentElement.appendChild(this.head);
    this.documentElement.appendChild(this.body);
    this.activeElement = this.body;
  }
  createElement(ten: string) {
    return new Nut(this, 1, ten, HTML_NS, null);
  }
  createElementNS(ns: string, ten: string) {
    return new Nut(this, 1, ten, ns, null);
  }
  createTextNode(chu: string) {
    return new Nut(this, 3, "#text", null, chu);
  }
}

/** Phát một sự kiện giả: bắt (từ gốc xuống) rồi nổi (từ đích lên), như DOM thật. */
function phat(dich: Nut, type: string, them: Record<string, unknown> = {}) {
  let dung = false;
  const e: Record<string, unknown> = {
    type,
    target: dich,
    currentTarget: null,
    bubbles: true,
    cancelable: true,
    defaultPrevented: false,
    timeStamp: Date.now(),
    preventDefault() {
      e["defaultPrevented"] = true;
    },
    stopPropagation() {
      dung = true;
    },
    ...them,
  };
  const duong: Nut[] = [];
  for (let n: Nut | null = dich; n !== null; n = n.parentNode) duong.push(n);
  for (const n of [...duong].reverse())
    for (const f of n.nghe.get(`${type}:c`) ?? []) {
      e["currentTarget"] = n;
      f(e);
    }
  for (const n of duong) {
    if (dung) break;
    for (const f of n.nghe.get(`${type}:b`) ?? []) {
      e["currentTarget"] = n;
      f(e);
    }
  }
}

function tim(n: Nut, ok: (x: Nut) => boolean): Nut | null {
  if (ok(n)) return n;
  for (const c of n.childNodes) {
    const r = tim(c, ok);
    if (r !== null) return r;
  }
  return null;
}

const document = new TaiLieu();
const window = {
  document,
  HTMLIFrameElement: class {},
  addEventListener() {},
  removeEventListener() {},
};
document.defaultView = window;
// `react-dom` dò `"oninput" in document` lúc nạp: thiếu nó thì `onChange` của
// `<input>` đi đường polyfill IE9 (`attachEvent`), khung giả không có.
Object.assign(document, { oninput: null });
Object.assign(globalThis, { document, window, IS_REACT_ACT_ENVIRONMENT: true });

// `react-dom` chốt `canUseDOM` NGAY lúc nạp module, nên phải nạp SAU khi đã
// dựng `window`/`document` giả ở trên — vì thế mới dùng `import()` động.
const { act, createElement: h, useState } = await import("react");
const { createRoot } = await import("react-dom/client");
const { runnerImport } = await import("vite");

const goc = fileURLToPath(new URL("..", import.meta.url));
// `@/lib/api` (qua `SanKhauBanThao`) dựng Supabase client lúc nạp và ném lỗi
// nếu thiếu biến môi trường; không lượt gọi mạng nào xảy ra trong script này.
process.env["SUPABASE_URL"] ??= "http://localhost:54321";
process.env["SUPABASE_PUBLISHABLE_KEY"] ??= "sb_publishable_kiem";

// Đếm số lần `mucTuBanThao` THẬT được gọi (phép kiểm 3): bọc hàm ngay trong
// nguồn `xuat-tep.ts` lúc Vite biên dịch, để `SanKhauBanThao` gọi qua đúng
// import bình thường của nó — không sửa mã sản phẩm, không mock module.
let demMucTuBanThao = 0;
Object.assign(globalThis, {
  __demMucTuBanThao: () => {
    demMucTuBanThao += 1;
  },
});
const cauHinhVite = {
  root: goc,
  logLevel: "error" as const,
  resolve: { tsconfigPaths: true },
  plugins: [
    {
      name: "kiem-ui-muot:dem-mucTuBanThao",
      enforce: "pre" as const,
      transform(code: string, id: string) {
        if (!id.endsWith("/src/lib/xuat-tep.ts")) return null;
        const dau = "export function mucTuBanThao(";
        assert.ok(code.includes(dau), "không tìm thấy khai báo `mucTuBanThao` để đếm");
        return code.replace(
          dau,
          "export function mucTuBanThao(...a) { globalThis.__demMucTuBanThao(); return mucTuBanThaoGoc(...a); }\nfunction mucTuBanThaoGoc(",
        );
      },
    },
    {
      // Phép kiểm 13: danh sách "Bản thảo" và lời gọi lưu/lùi phải dùng CHUNG
      // một `@/lib/api` — mỗi `nap` là một đồ thị module riêng.
      name: "kiem-ui-muot:mot-do-thi",
      resolveId: (id: string) =>
        id === "kiem:ban-thao-gan-day" ? "\0kiem:ban-thao-gan-day" : null,
      load: (id: string) =>
        id === "\0kiem:ban-thao-gan-day"
          ? 'export { DanhSachBanThaoGanDay } from "/src/components/klaw/DanhSachPhien.tsx";\n' +
            'export { luiBanThao, moBanThaoKhuon, suaODien, traCuuLuong } from "/src/lib/api.ts";'
          : null,
    },
  ],
};
async function nap<T>(duong: string): Promise<T> {
  return (await runnerImport<T>(join(goc, duong), cauHinhVite)).module;
}
const { XemTruocA4 } = await nap<typeof import("../src/components/soan-thao/XemTruocA4.tsx")>(
  "src/components/soan-thao/XemTruocA4.tsx",
);
const { SanKhauBanThao } = await nap<
  typeof import("../src/components/soan-thao/SanKhauBanThao.tsx")
>("src/components/soan-thao/SanKhauBanThao.tsx");

function taoRoot() {
  const khung = document.createElement("div");
  document.body.appendChild(khung);
  return { khung, root: createRoot(khung as unknown as Element) };
}
const nhip = () => new Promise<void>((r) => setTimeout(r, 0));

// ─────────────────────────────────────────────── 1. thuộc tính khối gõ được
const CHU_GOC = "Người lao động được nghỉ hằng năm.";
const MUC: Muc[] = [
  {
    stt: 1,
    key: "nghi-hang-nam",
    ten: "Nghỉ hằng năm",
    tenThat: true,
    noiDung: CHU_GOC,
    bang: null,
    vung: "than",
    trang: 1,
    canCu: null,
    khoi: [
      { kind: "vanXuoi", noiDung: CHU_GOC, canhLe: "trai", chu: [], gianCach: null },
      {
        kind: "bang",
        hang: [
          ["Năm", "Số ngày"],
          ["2026", "12"],
        ],
        nhip: [
          [1, 1],
          [1, 1],
        ],
        tiLe: [50, 50],
        vien: true,
        cao: [],
        canLeO: [],
        chuO: [],
      },
    ],
  },
];
const goiLuu: unknown[][] = [];
let ketQuaLuu = true;
const onSuaKhoi = (...a: unknown[]) => {
  goiLuu.push(a);
  return Promise.resolve(ketQuaLuu);
};
const propsSua = {
  tieuDe: "Nội quy lao động",
  kyHieu: null,
  muc: MUC,
  thuPhong: 100,
  hienCanCu: false,
  laTongQuat: true,
  onChonMuc: () => {},
  onSuaKhoi,
  phienBan: 3,
};

const { khung: khungSua, root: rootSua } = taoRoot();
await act(() => {
  rootSua.render(h(XemTruocA4, propsSua));
});
const khoi = tim(khungSua, (n) => n.getAttribute("contenteditable") === "true");
assert.ok(khoi !== null, "phải có một khối văn xuôi contenteditable");
assert.equal(khoi.textContent, CHU_GOC);
for (const [ten, giaTri] of [
  ["role", "textbox"],
  ["aria-multiline", "true"],
  ["lang", "vi"],
  ["spellcheck", "false"],
  ["autocorrect", "off"],
  ["autocapitalize", "off"],
]) {
  assert.equal(khoi.getAttribute(ten!), giaTri, `khối gõ được phải mang ${ten}="${giaTri}"`);
}
// Khối ĐÃ hỏng lưu phải vẽ ra được từ chính `aria-invalid` (phép kiểm 4 đặt
// thuộc tính; class này là thứ biến nó thành viền thấy được).
assert.match(
  khoi.getAttribute("class") ?? "",
  /aria-invalid:/,
  "viền lỗi phải theo `aria-invalid`",
);

// Ghi chú "chưa sửa trực tiếp được" đã bị bỏ (chủ dự án, 2026-09-18) — nó
// lặp lại trên MỖI bảng và chen giữa hai khối của chính văn bản. Khoá lại là
// KHÔNG còn: một ghi chú đã bỏ mà mọc lại vẫn là lỗi.
const bang = tim(khungSua, (n) => n.tagName === "TABLE");
assert.ok(bang !== null);
assert.equal(bang.getAttribute("aria-describedby"), null, "bảng không còn trỏ tới ghi chú nào");
assert.equal(
  tim(khungSua, (n) => /chưa sửa trực tiếp được/.test(n.nodeValue ?? "")),
  null,
  "ghi chú 'bảng chưa sửa trực tiếp được' phải biến mất khỏi trang",
);

// Chỉ đọc (không `onSuaKhoi`): không khối nào gõ được, không role textbox.
const { onSuaKhoi: _boQua1, phienBan: _boQua2, ...propsDoc } = propsSua;
const { khung: khungDoc, root: rootDoc } = taoRoot();
await act(() => {
  rootDoc.render(h(XemTruocA4, propsDoc));
});
assert.equal(
  tim(khungDoc, (n) => n.getAttribute("contenteditable") === "true"),
  null,
);
assert.equal(
  tim(khungDoc, (n) => n.getAttribute("role") === "textbox"),
  null,
);
assert.equal(
  tim(khungDoc, (n) => n.hasAttribute("aria-describedby")),
  null,
  "chỉ đọc: không có ghi chú bảng",
);

// ───────────────────────────────────────────────────────── 2. Escape = huỷ
await act(() => khoi.focus());
khoi.textContent = "Gõ nhầm chỗ này";
await act(() => {
  phat(khoi, "keydown", { key: "Escape" });
});
assert.equal(khoi.textContent, CHU_GOC, "Escape phải trả khối về chữ lúc bắt đầu sửa");
assert.equal(document.activeElement, document.body, "Escape phải rời khối (blur)");
assert.equal(goiLuu.length, 0, "Escape không được gọi lưu");

// Đối chứng: blur bình thường sau khi gõ → gọi lưu ĐÚNG MỘT lần với chữ mới
// và phiên bản chụp lúc focus — chứng minh đường lưu thật sự chạy được trong
// khung này (nếu không, "không gọi lưu" ở trên là rỗng nghĩa).
await act(() => khoi.focus());
khoi.textContent = "Gõ thật";
await act(async () => {
  khoi.blur();
  await nhip();
});
assert.deepEqual(goiLuu, [["nghi-hang-nam", 0, "Gõ thật", 3]]);
assert.equal(khoi.getAttribute("aria-invalid"), null, "lưu xong không có dấu lỗi");

// ──────────────────────────────────────────── 4. lưu hỏng để lại dấu + tiêu điểm
ketQuaLuu = false;
await act(() => khoi.focus());
khoi.textContent = "Lưu hỏng";
await act(async () => {
  khoi.blur();
  await nhip();
});
assert.equal(goiLuu.length, 2);
assert.equal(
  khoi.getAttribute("aria-invalid"),
  "true",
  "khối lưu hỏng phải mang `aria-invalid` (viền đỏ)",
);
assert.equal(document.activeElement, khoi, "tiêu điểm phải quay về khối lưu hỏng");
assert.equal(khoi.textContent, "Lưu hỏng", "chữ vừa gõ phải còn đó để sửa tiếp");
// Lưu lại được → dấu lỗi biến mất.
ketQuaLuu = true;
khoi.textContent = "Lưu lại được";
await act(async () => {
  khoi.blur();
  await nhip();
});
assert.equal(goiLuu.length, 3);
assert.equal(khoi.getAttribute("aria-invalid"), null, "lưu lại thành công phải gỡ dấu lỗi");

// ────────────────────────────────────────────────────── 3. `muc` được memo
const banThao: BanThao = {
  id: "b1",
  loai: "tong_quat",
  ten: "Bản thảo tổng quát",
  phien_ban: 1,
  document: "# Nội quy lao động\n",
  clauses: [],
  audit_report: {},
  facts: {},
  doi_so_voi_truoc: [],
};
const propsSanKhau = {
  banThao,
  cauTruc: null,
  truongMau: [],
  dangTai: false,
  loiKhung: null,
  onTaiLaiKhung: () => {},
  mucDangChon: null,
  onChonMuc: () => {},
  capNhatBanThao: () => {},
  onLui: async () => false,
  onDong: () => {},
  onPhimTat: () => {},
  toanMan: false,
  nhapODien: {},
  datNhapODien: () => {},
};
const { root: rootSanKhau } = taoRoot();
demMucTuBanThao = 0;
await act(() => {
  rootSanKhau.render(h(SanKhauBanThao, propsSanKhau));
});
assert.equal(demMucTuBanThao, 1, "lần dựng đầu tính `muc` đúng một lần");
// Đổi mục đang chọn — một prop KHÔNG liên quan tới `muc` (cùng loại render
// lại như kéo `TayKeo` hay một token chat đang stream).
await act(() => {
  rootSanKhau.render(h(SanKhauBanThao, { ...propsSanKhau, mucDangChon: "nghi-hang-nam" }));
});
assert.equal(demMucTuBanThao, 1, "render lại vì prop không liên quan KHÔNG được tính lại `muc`");
await act(() => {
  rootSanKhau.render(h(SanKhauBanThao, { ...propsSanKhau, banThao: { ...banThao, phien_ban: 2 } }));
});
assert.equal(demMucTuBanThao, 2, "`banThao` đổi → tính lại `muc` đúng một lần");

// ───────── 5. bảng nguồn KHÔNG viền ra bố cục, bảng CÓ viền vẫn ra bảng ────
//
// Biểu mẫu tiếng Việt xếp cột bằng bảng không viền (letterhead, khối ký). Đo
// trên BM.ĐT.18.05/BM.ĐT.18.03 (2026-09-18): hai bảng đó không khai viền nào,
// ô căn `w:jc="center"`, hàng ký khai `w:trHeight` 1499/1845 twip. Kiểm trên
// CHÍNH component đã biên dịch: thuộc tính `data-*` mà `docBangTuPhanTu` sẽ
// đọc lại khi xuất tệp phải có mặt trên DOM, nếu không thì màn hình và tệp
// tải về nói hai điều khác nhau.
function timTatNut(n: Nut, ok: (x: Nut) => boolean): Nut[] {
  const ra: Nut[] = ok(n) ? [n] : [];
  for (const c of n.childNodes) ra.push(...timTatNut(c, ok));
  return ra;
}
const mucBang = (vien: boolean): Muc[] => [
  {
    stt: 1,
    key: "ky",
    ten: "Khối ký",
    tenThat: true,
    noiDung: "",
    bang: null,
    vung: "than",
    trang: 1,
    canCu: null,
    khoi: [
      {
        kind: "bang",
        hang: [["Giảng viên hướng dẫn", "Sinh viên thực tập"]],
        nhip: [[1, 1]],
        tiLe: [50, 50],
        vien,
        cao: [1499],
        canLeO: [["giua", "giua"]],
        chuO: [],
      },
    ],
  },
];
const propsBang = {
  tieuDe: "Kế hoạch thực tập",
  kyHieu: null,
  thuPhong: 100,
  hienCanCu: false,
  laTongQuat: true,
  onChonMuc: () => {},
};

const { khung: khungKhongVien, root: rootKhongVien } = taoRoot();
await act(() => {
  rootKhongVien.render(h(XemTruocA4, { ...propsBang, muc: mucBang(false) }));
});
const bangKhongVien = tim(khungKhongVien, (n) => n.tagName === "TABLE");
assert.ok(bangKhongVien !== null, "khối bảng vẫn render ra một <table> thật");
assert.equal(
  bangKhongVien.getAttribute("data-vien"),
  "khong",
  "bảng nguồn không viền phải mang dấu `data-vien` để lúc xuất tệp đọc lại được",
);
assert.equal(
  timTatNut(khungKhongVien, (n) => n.tagName === "TH").length,
  0,
  "không có hàng tiêu đề GIẢ: bảng bố cục không có <th> nào",
);
const oKhongVien = timTatNut(khungKhongVien, (n) => n.tagName === "TD");
assert.equal(oKhongVien.length, 2, "hai cột ký đứng cạnh nhau, đủ hai ô");
for (const o of oKhongVien) {
  const lop = o.getAttribute("class") ?? "";
  assert.ok(!lop.includes("border"), `ô bảng bố cục không được có lớp viền (thấy: ${lop})`);
  assert.ok(lop.includes("text-center"), "ô giữ căn lề NGUỒN của nó (giua → text-center)");
  assert.equal(o.getAttribute("data-can-le"), "giua", "căn lề phải đọc lại được lúc xuất tệp");
}
const hangKhongVien = tim(khungKhongVien, (n) => n.tagName === "TR");
assert.equal(
  hangKhongVien?.getAttribute("data-cao"),
  "1499",
  "chiều cao khai báo của hàng ký phải đọc lại được lúc xuất tệp",
);
assert.equal(
  hangKhongVien?.style["height"],
  `${1499 / 20}pt`,
  "chiều cao khai báo phải thành chỗ trống THẬT trên trang, không chỉ một thuộc tính",
);

const { khung: khungCoVien, root: rootCoVien } = taoRoot();
await act(() => {
  rootCoVien.render(h(XemTruocA4, { ...propsBang, muc: mucBang(true) }));
});
assert.equal(
  tim(khungCoVien, (n) => n.tagName === "TABLE")?.getAttribute("data-vien"),
  null,
  "bảng CÓ viền không mang dấu nào — hành vi cũ không đổi",
);
const oTieuDeCoVien = timTatNut(khungCoVien, (n) => n.tagName === "TH");
assert.equal(oTieuDeCoVien.length, 2, "bảng có viền vẫn giữ hàng tiêu đề <th>");
assert.ok(
  (oTieuDeCoVien[0]?.getAttribute("class") ?? "").includes("border"),
  "bảng có viền vẫn kẻ khung như trước bản vá",
);

// ─────────── 6. định dạng chữ TRONG một ô bảng ra từng `<span data-chu>` ────
//
// Trước bản vá 2026-09-18 (nhánh ô bảng), ô được vẽ bằng một chuỗi trần, nên
// letterhead in đậm của biểu mẫu chủ sở hữu ra màn hình thành chữ thường —
// trong khi CÙNG chữ ấy nằm ngoài bảng thì đậm đúng. `docBangTuPhanTu` đọc
// lại chính các `<span>` này khi xuất tệp, nên thiếu chúng là cả ba nơi vẽ
// cùng sai một lúc.
const O_TRAI_CHU = "TRƯỜNG ĐẠI HỌC PHENIKAA";
const O_PHAI_CHU = "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM";
const mucBangChu: Muc[] = [
  {
    stt: 1,
    key: "dau_trang",
    ten: "Đầu trang",
    tenThat: true,
    noiDung: "",
    bang: null,
    vung: "than",
    trang: 1,
    canCu: null,
    khoi: [
      {
        kind: "bang",
        hang: [[O_TRAI_CHU, O_PHAI_CHU]],
        nhip: [[1, 1]],
        tiLe: [50, 50],
        vien: false,
        cao: [],
        canLeO: [["giua", "giua"]],
        chuO: [
          [
            [
              {
                text: "TRƯỜNG ",
                inDam: true,
                inNghieng: false,
                gachChan: false,
                coChu: 26,
                phong: "Times New Roman",
              },
              {
                text: "ĐẠI HỌC PHENIKAA",
                inDam: false,
                inNghieng: true,
                gachChan: true,
                coChu: 28,
                phong: "",
              },
            ],
            [],
          ],
        ],
      },
    ],
  },
];

const { khung: khungChuO, root: rootChuO } = taoRoot();
await act(() => {
  rootChuO.render(h(XemTruocA4, { ...propsBang, muc: mucBangChu }));
});
const oChuO = timTatNut(khungChuO, (n) => n.tagName === "TD");
assert.equal(oChuO.length, 2, "hai ô của hàng letterhead");
const spanTrai = timTatNut(oChuO[0]!, (n) => n.tagName === "SPAN");
assert.equal(spanTrai.length, 2, "ô nhiều định dạng phải vẽ MỘT span cho MỖI đoạn");
assert.equal(
  spanTrai.map((n) => n.textContent).join(""),
  O_TRAI_CHU,
  "các span phải phủ KÍN chữ của ô — sót một ký tự là mất chữ của người dùng",
);
assert.equal(spanTrai[0]?.getAttribute("data-chu"), "", "span phải mang dấu `data-chu` để đọc lại");
assert.equal(spanTrai[0]?.getAttribute("data-dam"), "1", "đoạn đậm phải khai đậm");
assert.equal(spanTrai[0]?.getAttribute("data-co"), "26");
assert.equal(spanTrai[0]?.getAttribute("data-phong"), "Times New Roman");
assert.equal(
  spanTrai[0]?.style["fontWeight"],
  "700",
  "đậm phải THẤY được, không chỉ là thuộc tính",
);
assert.equal(spanTrai[1]?.getAttribute("data-dam"), null, "đoạn không đậm không được khai đậm");
assert.equal(spanTrai[1]?.getAttribute("data-nghieng"), "1");
assert.equal(spanTrai[1]?.getAttribute("data-gach"), "1");
assert.equal(spanTrai[1]?.getAttribute("data-co"), "28");
assert.equal(
  timTatNut(oChuO[1]!, (n) => n.tagName === "SPAN").length,
  0,
  "ô nguồn không khai định dạng giữ chữ trần — không span nào, đúng đường cũ",
);
assert.equal(oChuO[1]?.textContent, O_PHAI_CHU, "ô không định dạng vẫn hiện đủ chữ");

// ──────── 7. giãn cách/thụt lề của ĐOẠN và đường dẫn của MỘT mốc tab ────────
//
// Đây là nơi duy nhất trong repo render được component thật, nên phần MÀN
// HÌNH của `w:spacing`/`w:ind`/`w:tabs` chốt ở đây; `.docx`, PDF và cửa vào
// fail-closed chốt ở `kiem-gian-cach.ts`.
//
// Hai điều dễ hỏng âm thầm: (1) nhịp chỉ vào `style` mà không vào `data-*`
// thì `docDong` đọc lại `px` đã tính và tệp tải về lệch con số nguồn; (2)
// đường dẫn vẽ bằng một hộp có BỀ RỘNG ĐẨY thật thì nó tự đẩy mình xuống một
// dòng trống của riêng nó — dòng "……" biến mất khỏi chỗ cần điền.
const NHAN_DIEN = "Company name:";
const mucDien: Muc[] = [
  {
    stt: 1,
    key: "dien",
    ten: "Dòng điền",
    tenThat: true,
    noiDung: "",
    bang: null,
    vung: "than",
    trang: 1,
    canCu: null,
    khoi: [
      {
        kind: "vanXuoi",
        noiDung: NHAN_DIEN,
        canhLe: "trai",
        chu: [],
        gianCach: {
          truoc: 120,
          sau: 240,
          dong: 360,
          luatDong: "auto",
          trai: 720,
          phai: 0,
          dauDong: 0,
          treo: 426,
          tab: [{ o: NHAN_DIEN.length, val: "right", pos: 9360, leader: "dot" }],
        },
      },
    ],
  },
];

const { khung: khungDien, root: rootDien } = taoRoot();
await act(() => {
  rootDien.render(h(XemTruocA4, { ...propsBang, muc: mucDien }));
});
const doanDien = timTatNut(
  khungDien,
  (n) => n.tagName === "P" && n.getAttribute("data-truoc") !== null,
);
assert.equal(doanDien.length, 1, "đoạn có nhịp nguồn phải mang `data-truoc` để đọc lại");
const pDien = doanDien[0]!;
assert.equal(pDien.getAttribute("data-sau"), "240");
assert.equal(pDien.getAttribute("data-dong"), "360");
assert.equal(pDien.getAttribute("data-luat-dong"), "auto");
assert.equal(pDien.getAttribute("data-thut-trai"), "720");
assert.equal(pDien.getAttribute("data-treo"), "426");
// 1 twip = 1/20 pt — cùng phép quy đổi `caoTrenTrang` đã dùng cho `w:trHeight`.
assert.equal(pDien.style["marginTop"], "6pt", "120 twip = 6pt, THẤY được chứ không chỉ khai");
assert.equal(pDien.style["marginBottom"], "12pt");
assert.equal(pDien.style["marginLeft"], "36pt");
assert.equal(pDien.style["lineHeight"], "1.5", "360/240 = một dòng rưỡi");
assert.equal(pDien.style["textIndent"], "-21.3pt", "`w:hanging` đẩy dòng đầu NGƯỢC ra");
assert.equal(pDien.style["overflow"], "hidden", "đoạn có tab phải cắt phần đường dẫn vẽ tràn");

const spanDien = timTatNut(pDien, (n) => n.tagName === "SPAN");
assert.equal(spanDien.length, 2, "một span chữ, một span mốc tab");
assert.equal(spanDien.map((n) => n.textContent).join(""), NHAN_DIEN, "tab KHÔNG thêm ký tự nào");
const spanTab = spanDien[1]!;
assert.equal(spanTab.getAttribute("data-tab"), "", "mốc tab phải mang dấu để đọc lại");
assert.equal(spanTab.getAttribute("data-tab-val"), "right");
assert.equal(spanTab.getAttribute("data-tab-pos"), "9360");
assert.equal(spanTab.getAttribute("data-tab-leader"), "dot");
assert.equal(spanTab.style["borderBottomStyle"], "dotted", "đường dẫn phải THẤY được");
assert.equal(spanTab.style["width"], "468pt", "9360 twip = 468pt, vẽ tới đúng mốc");
assert.equal(
  spanTab.style["marginRight"],
  "-468pt",
  "bề rộng ĐẨY bằng 0: đường dẫn không được tự đẩy mình xuống dòng",
);

// Mốc KHÔNG khai đường dẫn: vẫn chở đủ sự thật cho `.docx`/PDF, nhưng màn
// hình không vẽ thêm nét nào — `w:leader` mặc định là `none`.
const mucSuong: Muc[] = [
  {
    ...mucDien[0]!,
    khoi: [
      {
        ...(mucDien[0]!.khoi[0] as Extract<Muc["khoi"][number], { kind: "vanXuoi" }>),
        gianCach: {
          ...(mucDien[0]!.khoi[0] as Extract<Muc["khoi"][number], { kind: "vanXuoi" }>).gianCach!,
          tab: [{ o: NHAN_DIEN.length, val: "left", pos: 1860, leader: "" }],
        },
      },
    ],
  },
];
const { khung: khungSuong, root: rootSuong } = taoRoot();
await act(() => {
  rootSuong.render(h(XemTruocA4, { ...propsBang, muc: mucSuong }));
});
const spanSuong = timTatNut(
  khungSuong,
  (n) => n.tagName === "SPAN" && n.getAttribute("data-tab") !== null,
);
assert.equal(spanSuong.length, 1);
assert.equal(spanSuong[0]?.getAttribute("data-tab-pos"), "1860", "sự thật vẫn đi ra tệp");
assert.equal(
  spanSuong[0]?.style["borderBottomStyle"],
  undefined,
  "không khai dẫn thì không vẽ nét",
);

// Khối KHÔNG có nhịp nguồn giữ nguyên đường cũ: không thuộc tính, không style.
const { khung: khungTran, root: rootTran } = taoRoot();
await act(() => {
  rootTran.render(h(XemTruocA4, { ...propsBang, muc: MUC }));
});
const pTran = timTatNut(khungTran, (n) => n.tagName === "P" && n.textContent === CHU_GOC)[0];
assert.ok(pTran !== undefined, "khối văn xuôi không nhịp vẫn render");
assert.equal(pTran.getAttribute("data-truoc"), null);
assert.equal(pTran.style["marginTop"], undefined, "không nhịp nguồn thì không style nào bị áp");

// ───────────── 10. căn đều hai lề (`deu`) vẽ ra `text-justify` trên TRANG ───
//
// Thân bài của một văn bản KLAW tự soạn phải "được canh đều cả hai lề" (NĐ
// 30/2020/NĐ-CP, Phụ lục I mục II.6), và một ô nguồn khai `w:jc="both"` cũng
// đọc ra `deu`. Trang là NGUỒN SỰ THẬT của `.docx`/PDF (`canhLeTuStyle` đọc
// ngược `text-align` đã tính), nên thiếu lớp này thì tệp tải về mất căn đều
// dù dữ liệu vẫn đúng.
const CHU_DEU = "Tôi xin trình bày sự việc như sau và kính mong Nhà trường xem xét.";
const mucDeu: Muc[] = [
  {
    stt: 1,
    key: "than-bai",
    ten: "Nội dung",
    tenThat: true,
    noiDung: CHU_DEU,
    bang: null,
    vung: "than",
    canCu: null,
    khoi: [
      { kind: "vanXuoi", noiDung: CHU_DEU, canhLe: "deu", chu: [], gianCach: null },
      {
        kind: "bang",
        hang: [["Ô căn đều", "Ô căn giữa"]],
        nhip: [[1, 1]],
        tiLe: [50, 50],
        vien: false,
        cao: [],
        canLeO: [["deu", "giua"]],
        chuO: [],
      },
    ],
  },
];
const { khung: khungDeu, root: rootDeu } = taoRoot();
await act(() => {
  rootDeu.render(h(XemTruocA4, { ...propsBang, muc: mucDeu }));
});
const pDeu = timTatNut(khungDeu, (n) => n.tagName === "P" && n.textContent === CHU_DEU)[0];
assert.ok(pDeu !== undefined, "khối văn xuôi căn đều vẫn render");
assert.ok(
  (pDeu.getAttribute("class") ?? "").includes("text-justify"),
  "khối `deu` phải mang `text-justify` — đó là thứ `canhLeTuStyle` đọc ngược khi xuất tệp",
);
const oDeu = timTatNut(khungDeu, (n) => n.tagName === "TD");
assert.equal(oDeu.length, 2, "bảng hai ô");
assert.ok(
  (oDeu[0]?.getAttribute("class") ?? "").includes("text-justify"),
  "ô bảng `deu` cũng phải ra `text-justify`, không rơi về căn trái",
);
assert.equal(oDeu[0]?.getAttribute("data-can-le"), "deu", "căn đều phải đọc lại được lúc xuất tệp");
assert.equal(oDeu[1]?.getAttribute("data-can-le"), "giua", "ô cạnh nó KHÔNG bị kéo theo");

// ───── 8. DÒNG CHẢY TRANG: nhiều TỜ A4, cắt đúng chỗ nguồn khai ngắt ───────
// Ở đây chứ không trong `kiem-dong-trang.ts` vì đúng lý lẽ phép kiểm 5 đã ghi:
// khung DOM giả + `runnerImport` của tệp này là chỗ DUY NHẤT trong repo render
// được một component thật. `kiem-dong-trang.ts` giữ phần thuần (`chiaTrang`,
// `Muc.trang`, vòng đọc lại `docNoiDungTuDOM` qua nhiều tờ).

const mucTrang = (trang: number[]): Muc[] =>
  trang.map((t, i) => ({
    stt: i + 1,
    key: `m${i + 1}`,
    ten: `Mục ${i + 1}`,
    tenThat: true,
    noiDung: `Nội dung mục ${i + 1}`,
    bang: null,
    vung: "than" as const,
    trang: t,
    canCu: null,
    khoi: [
      {
        kind: "vanXuoi" as const,
        noiDung: `Nội dung mục ${i + 1}`,
        canhLe: "trai" as const,
        chu: [],
        gianCach: null,
      },
    ],
  }));

const LE_NGUON = { tren: 964, phai: 1134, duoi: 1134, trai: 1701, dauTrang: 720, chanTrang: 720 };

/** Các tờ A4 đã render, theo thứ tự DOM. */
const toTrong = (khung: Nut) => timTatNut(khung, (n) => n.getAttribute("data-to") !== null);

// Một trang nguồn → ĐÚNG MỘT tờ. Hành vi trước bản vá, khoá lại.
const { khung: khungMotTo, root: rootMotTo } = taoRoot();
await act(() => {
  rootMotTo.render(h(XemTruocA4, { ...propsBang, muc: mucTrang([1, 1, 1]) }));
});
assert.equal(toTrong(khungMotTo).length, 1, "tài liệu một trang vẫn ra ĐÚNG MỘT tờ");

// Hai trang nguồn (hình dạng BM.M05: ngắt cứng giữa biểu mẫu và danh sách) →
// hai tờ, và chỗ cắt rơi đúng vào mục đầu của trang 2.
const { khung: khungHaiTo, root: rootHaiTo } = taoRoot();
await act(() => {
  rootHaiTo.render(
    h(XemTruocA4, {
      ...propsBang,
      // `laTongQuat: false` để có `<h1>` và dòng số hiệu thật mà kiểm — hai
      // thứ chỉ được vẽ MỘT lần, ở tờ đầu.
      laTongQuat: false,
      kyHieu: "12/GTN",
      muc: mucTrang([1, 1, 2, 2]),
      leTrang: LE_NGUON,
    }),
  );
});
const haiTo = toTrong(khungHaiTo);
assert.equal(haiTo.length, 2, "hai trang NGUỒN → hai tờ A4");
assert.deepEqual(
  haiTo.map((t) => timTatNut(t, (n) => n.getAttribute("data-muc") !== null).length),
  [2, 2],
  "ngắt rơi đúng chỗ nguồn khai: hai mục ở tờ một, hai mục ở tờ hai",
);
assert.equal(
  timTatNut(haiTo[1]!, (n) => n.getAttribute("data-muc") === "m3").length,
  1,
  "`m3` — mục đầu của trang 2 — mở tờ thứ hai, không ở lại tờ một",
);

// Lề NGUỒN: vẽ trên TỪNG tờ, còn `data-le-*` ở lại trên `<article>` (thẻ mà
// `SanKhauBanThao` trao cho `docNoiDungTuDOM`). Lẫn hai chỗ này thì `.docx`/PDF
// mất lề nguồn trong khi màn hình vẫn trông đúng.
for (const [i, t] of haiTo.entries()) {
  assert.equal(t.style["paddingLeft"], `${(1701 / 11906) * 100}%`, `tờ ${i} mang lề trái NGUỒN`);
  assert.equal(t.style["paddingTop"], `${(964 / 11906) * 100}%`, `tờ ${i} mang lề trên NGUỒN`);
  assert.equal(t.getAttribute("data-le-trai"), null, `tờ ${i} KHÔNG giữ data-le-* (thuộc khung)`);
}
const khungA4 = tim(khungHaiTo, (n) => n.tagName === "ARTICLE")!;
assert.equal(khungA4.getAttribute("data-le-trai"), "1701", "`data-le-*` ở lại trên `<article>`");
assert.equal(
  timTatNut(khungHaiTo, (n) => n.tagName === "ARTICLE").length,
  1,
  'ĐÚNG MỘT `<article>` cho mọi tờ: `SanKhauBanThao` lấy nó bằng `querySelector("article")`, nên tách thành nhiều `<article>` anh em sẽ nuốt mọi trang sau tờ đầu ra khỏi tệp tải về',
);

// Tiêu đề và khối ký hiệu chỉ ở tờ ĐẦU — chúng là của cả tài liệu, không của
// mỗi trang; lặp chúng trên mọi tờ là nhân bản chúng trong tệp tải về.
assert.equal(timTatNut(khungHaiTo, (n) => n.tagName === "H1").length, 1, "đúng MỘT `<h1>`");
assert.equal(
  timTatNut(haiTo[0]!, (n) => n.tagName === "H1").length,
  1,
  "và nó ở tờ ĐẦU, không phải tờ cuối",
);
assert.equal(
  timTatNut(khungHaiTo, (n) => n.tagName === "P" && n.textContent.startsWith("S\u1ed1:")).length,
  1,
  "d\u00f2ng s\u1ed1 hi\u1ec7u c\u0169ng ch\u1ec9 v\u1ebd M\u1ed8T l\u1ea7n \u2014 l\u1eb7p n\u00f3 tr\u00ean m\u1ecdi t\u1edd l\u00e0 nh\u00e2n b\u1ea3n n\u00f3 trong t\u1ec7p t\u1ea3i v\u1ec1",
);

// Băng ẢNH: letterhead ở tờ ĐẦU, con dấu/chữ ký ở tờ CUỐI — mỗi ảnh nguồn ra
// ĐÚNG một thẻ. Vẽ băng trên mọi tờ thì `docNoiDungTuDOM` (đọc mọi `<img
// data-anh>`) nhân bản logo và con dấu vào tệp `.docx`/PDF người dùng tải về.
const { khung: khungAnh, root: rootAnh } = taoRoot();
await act(() => {
  rootAnh.render(
    h(XemTruocA4, {
      ...propsBang,
      muc: mucTrang([1, 2, 3]),
      anh: [
        {
          url: "data:image/gif;base64,R0lGODlhAQABAAAAACw=",
          rong: 914400,
          cao: 457200,
          vung: "dau_trang" as const,
          thuTu: 0,
        },
        {
          url: "data:image/gif;base64,R0lGODlhAQABAAAAACw=",
          rong: 914400,
          cao: 457200,
          vung: "than" as const,
          thuTu: 0,
        },
      ],
    }),
  );
});
const baTo = toTrong(khungAnh);
assert.equal(baTo.length, 3, "ba trang NGUỒN → ba tờ");
const anhTat = timTatNut(khungAnh, (n) => n.getAttribute("data-anh") !== null);
assert.equal(anhTat.length, 2, "HAI ảnh nguồn ra ĐÚNG hai thẻ, không nhân lên theo số tờ");
assert.equal(
  timTatNut(baTo[0]!, (n) => n.getAttribute("data-anh") !== null).length,
  1,
  "băng ảnh đầu trang nằm ở tờ ĐẦU",
);
assert.equal(
  timTatNut(baTo[2]!, (n) => n.getAttribute("data-anh") !== null).length,
  1,
  "băng ảnh cuối nằm ở tờ CUỐI, không rơi lại tờ đầu",
);
assert.equal(
  timTatNut(baTo[1]!, (n) => n.getAttribute("data-anh") !== null).length,
  0,
  "tờ giữa không có băng ảnh nào",
);

// Không có lề nguồn → tờ giữ lớp lề 8%/7% cũ, đúng hành vi trước bản vá.
assert.ok(
  (toTrong(khungMotTo)[0]!.getAttribute("class") ?? "").includes("px-[8%]"),
  "không lề nguồn thì tờ giữ nguyên lớp lề cũ",
);
assert.equal(
  toTrong(khungMotTo)[0]!.style["paddingLeft"],
  undefined,
  "và không bị áp một lề nguồn bịa ra",
);

// ───── 9. ẢNH NGUỒN tải CÓ xác thực, vẽ bằng object URL ────────────────────
// Endpoint ảnh (`GET /api/v1/tai-lieu/{viec}/anh/{tên}`) chỉ nhận Bearer, còn
// `url` trong `clauses` là đường dẫn TƯƠNG ĐỐI không có `/api/v1`. Một
// `<img src={a.url}>` trần vì vậy hỏng ba lần: sai gốc, thiếu `/api/v1`, thiếu
// Bearer. `fetch` thay bằng hàm giả: không một lượt gọi mạng thật nào.
//
// `tieuDeXacThuc` THẬT chạy ở đây, nên client Supabase (Proxy lười) được dựng
// lần đầu. Trong `window`/`document` giả, `GoTrueClient` tưởng mình ở trình
// duyệt và mở một `BroadcastChannel` có người nghe — thứ giữ Node sống mãi sau
// dòng tổng kết. Khung giả không có tab nào khác để phát tới: bỏ nó đi.
delete (globalThis as { BroadcastChannel?: unknown }).BroadcastChannel;
const { apiGoc } = await nap<typeof import("../src/lib/api.ts")>("src/lib/api.ts");
const GIF = Uint8Array.from(atob("R0lGODlhAQABAAAAACw="), (c) => c.charCodeAt(0));
const daGoi: { url: string; headers: Record<string, string> }[] = [];
globalThis.fetch = (async (url: string, init?: RequestInit) => {
  daGoi.push({ url: String(url), headers: (init?.headers ?? {}) as Record<string, string> });
  return new Response(GIF, { status: 200 });
}) as typeof fetch;
const daThuHoi: string[] = [];
const thuHoiThat = URL.revokeObjectURL.bind(URL);
URL.revokeObjectURL = (u: string) => {
  daThuHoi.push(u);
  thuHoiThat(u);
};
/** Chờ chuỗi `await` của lượt tải (phiên Supabase → `fetch` → `blob`) chạy xong. */
async function choDen(dieu: () => boolean) {
  for (let i = 0; i < 50 && !dieu(); i += 1) {
    await act(async () => {
      await nhip();
    });
  }
}

const DUONG_LOGO = "/tai-lieu/11111111-2222-3333-4444-555555555555/anh/logo.gif";
const DUONG_DAU = "/tai-lieu/11111111-2222-3333-4444-555555555555/anh/dau.gif";
const anhLogo = (url: string) => [
  { url, rong: 914400, cao: 457200, vung: "dau_trang" as const, thuTu: 0 },
];
const { khung: khungXacThuc, root: rootXacThuc } = taoRoot();
await act(() => {
  rootXacThuc.render(h(XemTruocA4, { ...propsBang, muc: mucTrang([1]), anh: anhLogo(DUONG_LOGO) }));
});
const theAnh = () => tim(khungXacThuc, (n) => n.getAttribute("data-anh") !== null)!;
await choDen(() => theAnh().getAttribute("src") !== null);
assert.deepEqual(
  daGoi.map((g) => g.url),
  [`${apiGoc()}${DUONG_LOGO}`],
  "ảnh tải từ `apiGoc()` + đường dẫn tương đối — đúng gốc API, có `/api/v1`, đúng MỘT lượt",
);
assert.ok(
  "Authorization" in daGoi[0]!.headers || "X-Khach-Id" in daGoi[0]!.headers,
  "lượt tải mang header danh tính của `tieuDeXacThuc` (Bearer khi đã đăng nhập)",
);
assert.match(
  theAnh().getAttribute("src") ?? "",
  /^blob:/,
  "màn hình vẽ bằng object URL của bytes đã tải",
);
assert.equal(
  theAnh().getAttribute("data-anh-url"),
  DUONG_LOGO,
  "đường dẫn TƯƠNG ĐỐI ở lại trên thẻ để tệp tải về tự tải lại có xác thực",
);
assert.ok(
  (theAnh().style["aspectRatio"] as string | undefined)?.replace(/\s/g, "") === "914400/457200",
  "khung ảnh giữ chỗ theo tỉ lệ NGUỒN trước khi bytes về — phép đo tràn trang không đo một ảnh cao 0",
);
const srcCu = theAnh().getAttribute("src")!;
// Sân khấu vẽ lại theo TỪNG token chat: mảng `anh` mới mỗi lượt, cùng đường dẫn.
await act(() => {
  rootXacThuc.render(
    h(XemTruocA4, { ...propsBang, thuPhong: 110, muc: mucTrang([1]), anh: anhLogo(DUONG_LOGO) }),
  );
});
await choDen(() => false);
assert.equal(daGoi.length, 1, "vẽ lại với CÙNG đường dẫn không tải lại ảnh");
assert.equal(theAnh().getAttribute("src"), srcCu, "và giữ nguyên object URL cũ");
// Đổi ảnh → object URL cũ bị thu hồi, ảnh mới được tải.
await act(() => {
  rootXacThuc.render(h(XemTruocA4, { ...propsBang, muc: mucTrang([1]), anh: anhLogo(DUONG_DAU) }));
});
await choDen(() => (theAnh().getAttribute("src") ?? srcCu) !== srcCu);
assert.ok(daThuHoi.includes(srcCu), "đổi đường dẫn thu hồi object URL cũ");
assert.equal(daGoi.at(-1)?.url, `${apiGoc()}${DUONG_DAU}`, "và tải đường dẫn mới");
const srcMoi = theAnh().getAttribute("src")!;
await act(() => rootXacThuc.unmount());
assert.ok(daThuHoi.includes(srcMoi), "tháo component thu hồi object URL đang dùng");
// Một `url` không phải đường dẫn ảnh tài liệu (ví dụ lọt qua nơi gọi, không
// qua `anhHopLe`) KHÔNG được mang Bearer đi đâu cả.
const soGoiTruoc = daGoi.length;
const { root: rootLa } = taoRoot();
await act(() => {
  rootLa.render(
    h(XemTruocA4, { ...propsBang, muc: mucTrang([1]), anh: anhLogo("@ke-tan-cong.example/x.gif") }),
  );
});
await choDen(() => false);
assert.equal(daGoi.length, soGoiTruoc, "đường dẫn lạ → không một lượt `fetch` nào");

// ───── 10. tràn GIỮA một mục chảy sang tờ sau theo ranh giới KHỐI ──────────
// Trước bản vá: chỉ cắt GIỮA các mục, và tờ `overflow-y-auto` — một mục (hay
// một bảng) dài hơn một tờ cuộn BÊN TRONG tờ đó, chủ dự án thấy "1 trang".
// Bố cục giả tối thiểu cho phép đo: tờ rộng 210 → cao danh nghĩa 297, mỗi khối
// cao 100 (khối có chữ "CAO" cao 400), nên một tờ vừa ĐÚNG hai khối.
const CAO_KHOI = 100;
const caoCua = (n: Nut) => (n.textContent.includes("CAO") ? 4 * CAO_KHOI : CAO_KHOI);
const coThuoc = (chon: string) => {
  const ten = /^\[([\w-]+)\]$/.exec(chon)?.[1];
  assert.ok(ten, `bộ chọn giả không hỗ trợ: ${chon}`);
  return (x: Nut) => x.nodeType === 1 && x.getAttribute(ten) !== null;
};
function dayCua(n: Nut): number {
  let to: Nut | null = n;
  while (to && to.getAttribute("data-to") === null) to = to.parentNode;
  const donVi = timTatNut(to!, coThuoc("[data-khoi]"));
  const j = donVi.indexOf(n);
  if (j >= 0) return donVi.slice(0, j + 1).reduce((s, x) => s + caoCua(x), 0);
  const cuaMuc = donVi.filter((x) => n.contains(x)); // `<section>`: đáy khối cuối của nó
  return dayCua(cuaMuc[cuaMuc.length - 1]!);
}
const ganNhat = (x: Nut | null, khop: (n: Nut) => boolean): Nut | null =>
  x === null || khop(x) ? x : ganNhat(x.parentNode, khop);
Object.assign(Nut.prototype, {
  querySelectorAll(this: Nut, chon: string) {
    return timTatNut(this, coThuoc(chon)).filter((x) => x !== this);
  },
  closest(this: Nut, chon: string) {
    return ganNhat(this, coThuoc(chon));
  },
  getBoundingClientRect(this: Nut) {
    return this.getAttribute("data-to") !== null
      ? { top: 0, width: 210, bottom: 0 }
      : { top: 0, width: 0, bottom: dayCua(this) };
  },
});
Object.assign(globalThis, {
  getComputedStyle: () => ({ paddingTop: "0px", paddingBottom: "0px" }),
});

const mucKhoi = (key: string, chu: string[]): Muc => ({
  stt: 1,
  key,
  ten: `Tên ${key}`,
  tenThat: true,
  noiDung: chu.join(" "),
  bang: null,
  vung: "than",
  trang: 1,
  canCu: "Điều 113 BLLĐ 2019",
  khoi: chu.map((c) => ({
    kind: "vanXuoi" as const,
    noiDung: c,
    canhLe: "trai" as const,
    chu: [],
    gianCach: null,
  })),
});
const chuTheoTo = (khung: Nut) =>
  toTrong(khung).map((t) => timTatNut(t, coThuoc("[data-khoi]")).map((x) => x.textContent));

const goiSuaTran: unknown[][] = [];
const chonTran: string[] = [];
const { khung: khungTran5, root: rootTran5 } = taoRoot();
await act(() => {
  rootTran5.render(
    h(XemTruocA4, {
      ...propsBang,
      laTongQuat: false,
      hienCanCu: true,
      mucDangChon: "m1",
      onChonMuc: (k: string) => chonTran.push(k),
      muc: [mucKhoi("m1", ["Khối 1", "Khối 2", "Khối 3", "Khối 4", "Khối 5"])],
      onSuaKhoi: (...a: unknown[]) => {
        goiSuaTran.push(a);
        return Promise.resolve(true);
      },
      phienBan: 7,
    }),
  );
});
assert.deepEqual(
  chuTheoTo(khungTran5),
  [["Khối 1", "Khối 2"], ["Khối 3", "Khối 4"], ["Khối 5"]],
  "MỘT mục năm khối cao hơn một tờ chảy sang BA tờ, cắt ở ranh giới khối",
);
assert.ok(
  toTrong(khungTran5).every((t) => !(t.getAttribute("class") ?? "").includes("overflow-y-auto")),
  "không tờ nào cuộn bên trong",
);
const dauMuc = timTatNut(khungTran5, (n) => (n.getAttribute("class") ?? "").includes("dieu-head"));
assert.equal(dauMuc.length, 1, "tên mục vẽ ĐÚNG MỘT lần — ở mảnh đầu — không lặp trên mỗi tờ");
assert.ok(toTrong(khungTran5)[0]!.contains(dauMuc[0]!), "và nó ở tờ ĐẦU");
const dongCanCu = timTatNut(khungTran5, (n) => n.getAttribute("data-khong-xuat") !== null);
assert.equal(dongCanCu.length, 1, "dòng căn cứ vẽ ĐÚNG MỘT lần — ở mảnh cuối");
assert.ok(toTrong(khungTran5)[2]!.contains(dongCanCu[0]!), "và nó ở tờ CUỐI");
assert.equal(
  timTatNut(khungTran5, (n) => n.tagName === "ARTICLE").length,
  1,
  "vẫn ĐÚNG MỘT `<article>` cho mọi tờ — thẻ `docNoiDungTuDOM` nhận",
);
// Một mục chia ba mảnh vẫn là MỘT điều khiển "chọn mục": lặp role/tabindex/nhãn
// trên mỗi mảnh là bắt người dùng bàn phím/trình đọc màn hình gặp CÙNG một nút
// ba lần. Mảnh sau vẫn bấm chuột chọn được mục.
const manhMuc = timTatNut(khungTran5, (n) => n.getAttribute("data-muc") === "m1");
for (const t of ["role", "tabindex", "aria-label", "aria-current"])
  assert.deepEqual(
    manhMuc.map((n) => n.getAttribute(t) !== null),
    [true, false, false],
    `\`${t}\` chỉ ở mảnh ĐẦU của mục`,
  );
await act(() => phat(manhMuc[2]!, "click"));
assert.deepEqual(chonTran, ["m1"], "bấm vào mảnh cuối vẫn chọn đúng mục của nó");
// Chỉ số khối gửi đi khi lưu phải là chỉ số TRONG MỤC, không phải trong mảnh:
// lệch ở đây là lưu chữ người dùng gõ vào NHẦM khối.
const khoi3 = tim(
  khungTran5,
  (n) => n.getAttribute("contenteditable") === "true" && n.textContent === "Khối 3",
)!;
await act(() => khoi3.focus());
khoi3.textContent = "Khối 3 đã sửa";
await act(async () => {
  khoi3.blur();
  await nhip();
});
assert.deepEqual(
  goiSuaTran,
  [["m1", 2, "Khối 3 đã sửa", 7]],
  "sửa khối đầu của tờ 2 lưu vào khối 2 của mục",
);

// MỘT khối cao hơn cả tờ đứng đầu tờ: tờ đó tự cao thêm (không cắt ở đầu tờ —
// cắt ở đó chỉ đẻ tờ rỗng và vòng đo không bao giờ dừng), phần sau chảy tiếp.
const { khung: khungCao, root: rootCao } = taoRoot();
await act(() => {
  rootCao.render(
    h(XemTruocA4, { ...propsBang, muc: [mucKhoi("m1", ["Bảng CAO", "Sau 1", "Sau 2"])] }),
  );
});
assert.deepEqual(
  chuTheoTo(khungCao),
  [["Bảng CAO"], ["Sau 1", "Sau 2"]],
  "khối quá cao ở lại một mình trên tờ của nó; hai khối sau sang tờ kế",
);

// Hai mục, khối ĐẦU của mục sau tràn → cả mục sang tờ mới, tên mục đi CÙNG khối
// đầu của nó chứ không bị bỏ lại cuối tờ trước.
const { khung: khungHaiMuc, root: rootHaiMuc } = taoRoot();
await act(() => {
  rootHaiMuc.render(
    h(XemTruocA4, {
      ...propsBang,
      laTongQuat: false,
      muc: [mucKhoi("m1", ["A1", "A2"]), mucKhoi("m2", ["B1"])],
    }),
  );
});
assert.deepEqual(chuTheoTo(khungHaiMuc), [["A1", "A2"], ["B1"]], "mục sau sang trọn tờ mới");
assert.equal(
  timTatNut(toTrong(khungHaiMuc)[1]!, (n) => (n.getAttribute("class") ?? "").includes("dieu-head"))
    .length,
  1,
  "tên mục `m2` sang tờ mới cùng khối đầu của nó",
);

// ───── 11. KHUÔN GỐC: khung trang ảnh, điền TẠI CHỖ trên trang, bản tải lên ─
// Bản thảo trên khuôn gốc (`banThao.khuon`) vẽ ĐÚNG ảnh trang máy chủ dựng,
// không phải A4 HTML. Một lượt dựng giữ suất LibreOffice của CẢ tài khoản
// (lượt thứ hai đồng thời là 503), nên khung trang tải MỘT lần cho mỗi (id,
// phiên bản) dù sân khấu vẽ lại theo từng token chat hay từng pixel kéo.
// Chủ dự án 2026-09-27: không bảng ô điền bên cạnh — điền ngay trên trang.
const { TaiLieuDuKien } = await nap<typeof import("../src/components/klaw/TaiLieuDuKien.tsx")>(
  "src/components/klaw/TaiLieuDuKien.tsx",
);
const { KhungTrangAnh, SanKhauBanTaiLen } = await nap<
  typeof import("../src/components/soan-thao/KhungTrangAnh.tsx")
>("src/components/soan-thao/KhungTrangAnh.tsx");
const { taiXuongBanThao } = await nap<typeof import("../src/lib/api.ts")>("src/lib/api.ts");
const { ChipTaiLieu } = await nap<typeof import("../src/components/klaw/ChipTaiLieu.tsx")>(
  "src/components/klaw/ChipTaiLieu.tsx",
);
const { OSoanCauHoi } = await nap<typeof import("../src/components/klaw/OSoanCauHoi.tsx")>(
  "src/components/klaw/OSoanCauHoi.tsx",
);
const { TheKetQua } = await nap<typeof import("../src/components/klaw/TheKetQua.tsx")>(
  "src/components/klaw/TheKetQua.tsx",
);

// Mỗi `nap` là một đồ thị module riêng, nên mỗi đồ thị dựng client Supabase
// của nó ở lượt gọi đầu cần header danh tính, và GoTrue cảnh báo "Multiple
// GoTrueClient instances". Ứng dụng thật chỉ có một đồ thị: lọc ĐÚNG câu đó.
const canhBaoThat = console.warn.bind(console);
console.warn = (...a: unknown[]) => {
  if (!String(a[0]).includes("Multiple GoTrueClient instances")) canhBaoThat(...a);
};

// Ô nhập chữ giữ tiêu điểm thì `SelectEventPlugin` của React đọc
// `window.getSelection()` ở mỗi phím; khung giả chưa từng có `<input>` nào nhận
// tiêu điểm trước phần này. Một vùng chọn rỗng là đủ.
Object.assign(window, {
  getSelection: () => ({ anchorNode: null, anchorOffset: 0, focusNode: null, focusOffset: 0 }),
});

// `<select>` của React đọc `node.options`; khung giả không có — thêm đúng một
// getter, không phép kiểm cũ nào dùng `<select>`.
Object.defineProperty(Nut.prototype, "options", {
  get(this: Nut) {
    return timTatNut(this, (n) => n.tagName === "OPTION");
  },
});

const VIEC = "11111111-2222-3333-4444-555555555555";
const VIEC_CU = "99999999-2222-3333-4444-555555555555";
const TRANG_HAI = {
  kho: [
    [595, 842],
    [612, 792],
  ],
  trang: ["AAAA", "BBBB"],
};
/** Payload trang CÓ `o` (G1): hai chỗ định vị được (mỗi trang một), một chỗ
 *  không đo được vị trí. Số tròn để phần trăm kiểm được bằng mắt: 119/595 =
 *  20%, 210,5/842 = 25%; 61,2/612 = 10%, 79,2/792 = 10%, bề rộng 40%. */
const O_TRANG = [
  {
    don_vi: 0,
    so: 0,
    trang: 0,
    hop: [119, 210.5, 297.5, 227.34],
    nhan: "Họ và tên:",
    gia_tri: "Nguyễn Văn Ánh",
  },
  { don_vi: 1, so: 0, trang: 1, hop: [61.2, 79.2, 306, 95.04], nhan: "Email", gia_tri: null },
  { don_vi: 1, so: 1, trang: null, hop: null, nhan: "", gia_tri: null },
];
const TRANG_O = { ...TRANG_HAI, o: O_TRANG };
const TAI_LIEU_KHUON = {
  id: VIEC,
  hoi_thoai_id: "p1",
  trang_thai: "xong",
  so_trang: 2,
  so_don_vi: 5,
  mo_ta: null,
  ten_tep: "BM.M05.docx",
  chay_nen: false,
  ly_do_hong: null,
  thong_diep: null,
  co_ocr: false,
  loai: null,
  loai_ten: null,
  loai_tu_doan: false,
  loai_can_cu: null,
  du_kien: [],
  co_khuon_goc: true,
};
const KHUON = {
  viec_id: VIEC,
  dinh_dang: "docx",
  so_trang: 2,
  cho_trong: [
    { don_vi: 0, so: 0, kieu: "cham", nhan: "Họ và tên:", gia_tri: "Nguyễn Văn Ánh" },
    { don_vi: 1, so: 0, kieu: "tab", nhan: "Email", gia_tri: null },
    { don_vi: 1, so: 1, kieu: "cham", nhan: "", gia_tri: null },
  ],
};
const DAU_TAI_VE =
  "attachment; filename=\"BM.M05 - da dien.pdf\"; filename*=UTF-8''BM.M05%20-%20%C4%91%C3%A3%20%C4%91i%E1%BB%81n.pdf";

type GoiKhuon = { url: string; method: string; body: unknown; headers: Record<string, string> };
const goiKhuon: GoiKhuon[] = [];
const traJson = (x: unknown, status = 200) =>
  new Response(JSON.stringify(x), { status, headers: { "Content-Type": "application/json" } });
let moCongBanTaiLen: () => void = () => {};
const congBanTaiLen = new Promise<void>((r) => {
  moCongBanTaiLen = r;
});
let lan503 = 0;
const { khuonHopLe } = await nap<typeof import("../src/lib/klaw.ts")>("src/lib/klaw.ts");
const { NGHI_DUNG_TRANG_MS } =
  await nap<typeof import("../src/lib/khuon-goc.ts")>("src/lib/khuon-goc.ts");
/** Máy chủ giả của ô điền, cho mỗi bản thảo khuôn: MỌI phiên bản đã có (để
 *  `/trang?phien_ban=N` vẽ đúng giá trị của phiên bản đó) và luật phiên bản của
 *  máy chủ thật — gửi phiên bản cũ là 422, không đổi gì thì không tăng. */
const banMayChu = new Map<string, BanThao[]>();
const CAU_CU =
  "Bản thảo đã đổi (một lượt sửa khác vừa chạy) — tải lại bản thảo trước khi sửa tiếp.";
const CAU_AP =
  "Không lưu được: 1 ô không điền được vào tài liệu tải lên (“Email”) — giá trị quá dài cho ô, hoặc ô không còn khớp tài liệu. Rút gọn hay bỏ trống ô đó rồi lưu lại.";
/** Giá trị máy chủ giả từ chối (422 `CAU_AP`). */
let tuChoiO: string | null = null;
/** Cổng giữ phản hồi `PATCH …/o-dien` / `GET /ban-thao/{id}/trang` (của ĐÚNG
 *  một bản thảo): đứng giữa lúc chờ thì quan sát được "đang lưu"/"đang dựng".
 *  Mỗi lượt chờ ĐÚNG cổng đặt lúc nó tới. */
let congPatch: Promise<void> | null = null;
let congTrang: { id: string; cong: Promise<void> } | null = null;
function taoCong() {
  let mo: () => void = () => {};
  const cong = new Promise<void>((r) => {
    mo = r;
  });
  return { cong, mo };
}
type ODienTho = { don_vi: number; cho_trong: number; gia_tri: string };
function oDienGia(id: string, than: { phien_ban: number; gia_tri: ODienTho[] }): Response {
  const ds = banMayChu.get(id);
  const bt = ds?.at(-1);
  if (ds === undefined || bt === undefined) return traJson({ detail: "Không tìm thấy" }, 404);
  if (than.phien_ban !== bt.phien_ban) return traJson({ detail: CAU_CU }, 422);
  if (than.gia_tri.some((g) => g.gia_tri.trim() === tuChoiO))
    return traJson({ detail: CAU_AP }, 422);
  const k = khuonHopLe(bt.khuon)!;
  const cho_trong = k.cho_trong.map((c) => {
    const g = than.gia_tri.find((x) => x.don_vi === c.don_vi && x.cho_trong === c.so);
    return g === undefined ? c : { ...c, gia_tri: g.gia_tri.trim() === "" ? null : g.gia_tri };
  });
  if (cho_trong.every((c, i) => c.gia_tri === k.cho_trong[i]!.gia_tri)) return traJson(bt);
  const moi: BanThao = { ...bt, phien_ban: bt.phien_ban + 1, khuon: { ...k, cho_trong } };
  ds.push(moi);
  return traJson(moi);
}
/** Trang của phiên bản N mà máy chủ giả biết: `TRANG_O` mang giá trị CỦA N. */
function trangCua(id: string, pb: number) {
  const bt = banMayChu.get(id)?.find((b) => b.phien_ban === pb);
  if (bt === undefined) return TRANG_O;
  const k = khuonHopLe(bt.khuon)!;
  return {
    ...TRANG_HAI,
    o: O_TRANG.map((x) => {
      const gt = k.cho_trong.find((c) => c.don_vi === x.don_vi && c.so === x.so)?.gia_tri?.trim();
      return { ...x, gia_tri: gt ? gt : null };
    }),
  };
}
globalThis.fetch = (async (url: string, init?: RequestInit) => {
  const u = String(url).replace(apiGoc(), "");
  const method = init?.method ?? "GET";
  goiKhuon.push({
    url: u,
    method,
    body: init?.body === undefined ? undefined : JSON.parse(String(init.body)),
    headers: (init?.headers ?? {}) as Record<string, string>,
  });
  if (u === `/tai-lieu/${VIEC}/trang`) {
    await congBanTaiLen;
    return traJson(TRANG_O); // có `o` — "Bản tải lên" vẫn phải sạch
  }
  if (u === "/ban-thao/b503/trang?phien_ban=1") {
    lan503 += 1;
    return lan503 === 1 ? traJson({ detail: "qua_tai" }, 503) : traJson(TRANG_HAI);
  }
  if (u === "/ban-thao/b404/trang?phien_ban=1") return traJson({ detail: "Không tìm thấy" }, 404);
  if (u.startsWith("/ban-thao/bcu/")) return traJson(TRANG_HAI); // máy chủ cũ: không `o`
  if (u.includes("/trang")) {
    const bt = /^\/ban-thao\/([^/]+)\/trang\?phien_ban=(\d+)$/.exec(u);
    const cong = congTrang;
    if (cong !== null && bt?.[1] === cong.id) await cong.cong;
    return traJson(bt === null ? TRANG_O : trangCua(bt[1]!, Number(bt[2])));
  }
  if (u.includes("/tai-xuong"))
    return new Response(new Uint8Array([37, 80, 68, 70]), {
      status: 200,
      headers: { "Content-Disposition": DAU_TAI_VE, "Content-Type": "application/pdf" },
    });
  if (method === "PATCH") {
    const cong = congPatch;
    if (cong !== null) await cong;
    const id = /^\/ban-thao\/([^/]+)\/o-dien$/.exec(u)?.[1] ?? "";
    return oDienGia(id, JSON.parse(String(init?.body)));
  }
  if (u.endsWith("/doc-lai")) return traJson(TAI_LIEU_KHUON);
  if (u.endsWith("/don-vi"))
    return traJson({ id: VIEC, ten_tep: "BM.M05.docx", so_trang: 2, don_vi: [] });
  if (u === `/tai-lieu/${VIEC}`) return traJson(TAI_LIEU_KHUON);
  if (u === `/tai-lieu/${VIEC_CU}`)
    return traJson({ ...TAI_LIEU_KHUON, id: VIEC_CU, co_khuon_goc: false });
  return traJson({ detail: "không có" }, 404);
}) as typeof fetch;
/** So hai nút bằng DANH TÍNH, hỏng thì báo bằng một câu. `assert.equal` trên
 *  nút giả in CẢ đồ thị DOM giả khi hỏng, và Node chết vì hết bộ nhớ (thoát
 *  137) thay vì nói phép kiểm nào sai. */
const cungNut = (a: Nut | null | undefined, b: Nut | null | undefined, thongDiep?: string) =>
  assert.ok(a === b, thongDiep ?? "hai nút phải là một");
const soGoi = (khop: (g: GoiKhuon) => boolean) => goiKhuon.filter(khop).length;
const soPatch = () => soGoi((g) => g.method === "PATCH");
const laTrangCua = (id: string, pb: number) => (g: GoiKhuon) =>
  g.url === `/ban-thao/${id}/trang?phien_ban=${pb}`;
const anhTrang = (khung: Nut) => timTatNut(khung, (n) => n.tagName === "IMG");
const nutChu = (khung: Nut, chu: string) =>
  tim(khung, (n) => n.tagName === "BUTTON" && n.textContent.includes(chu));
/** Nút phủ chỗ trống, theo thứ tự DOM (= thứ tự Tab). */
const nutO = (khung: Nut) =>
  timTatNut(khung, (n) => n.tagName === "BUTTON" && n.getAttribute("data-o") !== null);
const nutOKhoa = (khung: Nut, k: string) =>
  tim(khung, (n) => n.tagName === "BUTTON" && n.getAttribute("data-o") === k);
const oNhapCua = (khung: Nut) => tim(khung, (n) => n.tagName === "INPUT");
const giaTri = (n: Nut | null) => (n as unknown as { value: string } | null)?.value;
/** Lượt tải của khung trang đã về (vùng hết `aria-busy`). */
const daTaiXong = (khung: Nut) =>
  tim(khung, (n) => n.getAttribute("role") === "region")?.getAttribute("aria-busy") === "false";
const go = async (o: Nut, chu: string) => {
  await act(() => {
    (o as unknown as { value: string }).value = chu;
    phat(o, "input");
  });
};
/** Một phím, rồi một nhịp TRONG `act`: lượt lưu bất đồng bộ nó mở ra (fetch
 *  giả → state của ô nhập) cập nhật bên trong `act`, không rơi ra ngoài. */
const phim = async (o: Nut, key: string, them: Record<string, unknown> = {}) => {
  await act(async () => {
    phat(o, "keydown", { key, ...them });
    await nhip();
  });
};
const theoMoTa = (khung: Nut, o: Nut) =>
  (o.getAttribute("aria-describedby") ?? "")
    .split(" ")
    .map((id) => tim(khung, (n) => n.getAttribute("id") === id)?.textContent ?? "");
/** Nút "Lưu" gom của thanh công cụ khuôn gốc — đã bỏ; tìm để chắc nó không mọc lại. */
const nutLuu = (khung: Nut) =>
  tim(khung, (n) => n.tagName === "BUTTON" && /^(Lưu|Đang lưu)/.test(n.textContent));
/** Mọi `PATCH …/o-dien` đã gửi: [đường dẫn, thân]. */
const thanPatch = () =>
  goiKhuon.filter((g) => g.method === "PATCH").map((g) => [g.url, g.body] as const);
const cho = (ms: number) =>
  act(async () => {
    await new Promise((r) => setTimeout(r, ms));
  });
type PropsSanKhau = Parameters<typeof SanKhauBanThao>[0];
/** Trang gọi thu nhỏ — đúng hai việc `dung-thu.tsx` làm cho sân khấu: giữ chữ
 *  chưa lưu xong ở TRÊN sân khấu (`hien: false` tháo sân khấu ra như tab "Trợ
 *  lý"/đóng), và đưa bản thảo vừa lưu lên lại (`capNhatBanThao`, chỉ cùng id).
 *  Một `banThao` MỚI truyền từ ngoài (lượt chat, lùi) thay bản đang giữ. */
function VoNhap(p: Omit<PropsSanKhau, "nhapODien" | "datNhapODien"> & { hien?: boolean }) {
  const [nhap, datNhap] = useState<Record<string, string>>({});
  const [bt, datBt] = useState(p.banThao);
  const [tuNgoai, datTuNgoai] = useState(p.banThao);
  if (p.banThao !== tuNgoai) {
    datTuNgoai(p.banThao);
    datBt(p.banThao);
  }
  return p.hien === false
    ? null
    : h(SanKhauBanThao, {
        ...p,
        banThao: bt,
        capNhatBanThao: (moi: BanThao) => {
          p.capNhatBanThao(moi);
          datBt((cu) => (cu.id === moi.id ? moi : cu));
        },
        nhapODien: nhap,
        datNhapODien: datNhap,
      });
}

// (a) Khuôn DOCX: trang ảnh thay A4, đúng tỉ lệ từng trang, MỘT lượt tải.
const banThaoKhuon: BanThao = {
  ...banThao,
  id: "bk",
  phien_ban: 1,
  document: "# BM.M05\n",
  khuon: KHUON,
};
banMayChu.set("bk", [banThaoKhuon]);
const capNhatKhuon: BanThao[] = [];
const propsKhuon = {
  ...propsSanKhau,
  banThao: banThaoKhuon,
  capNhatBanThao: (bt: BanThao) => capNhatKhuon.push(bt),
};
const { khung: khungKhuon, root: rootKhuon } = taoRoot();
await act(() => {
  rootKhuon.render(h(VoNhap, propsKhuon));
});
await choDen(() => anhTrang(khungKhuon).length === 2);
cungNut(
  tim(khungKhuon, (n) => n.tagName === "ARTICLE"),
  null,
  "bản thảo trên khuôn gốc KHÔNG vẽ A4 HTML (`XemTruocA4`)",
);
assert.deepEqual(
  anhTrang(khungKhuon).map((n) => n.getAttribute("alt")),
  ["Trang 1 / 2", "Trang 2 / 2"],
);
assert.equal(anhTrang(khungKhuon)[0]?.getAttribute("src"), "data:image/png;base64,AAAA");
assert.equal(
  anhTrang(khungKhuon)[1]?.style["aspectRatio"],
  "612 / 792",
  "mỗi trang theo khổ CỦA NÓ — Letter vẫn là Letter",
);
assert.equal(soGoi(laTrangCua("bk", 1)), 1, "một lượt tải cho (bk, v1)");
// Năm lượt vẽ lại không liên quan: chọn mục, một bản thảo MỚI cùng id/phiên bản
// (đúng hình dạng mỗi token chat đang stream tạo ra).
for (let i = 0; i < 5; i += 1) {
  await act(() => {
    rootKhuon.render(
      h(VoNhap, {
        ...propsKhuon,
        mucDangChon: `m${i}`,
        banThao: { ...banThaoKhuon, khuon: { ...KHUON } },
      }),
    );
  });
}
await choDen(() => false);
assert.equal(soGoi(laTrangCua("bk", 1)), 1, "vẽ lại với CÙNG (id, phiên bản) không tải lại trang");
const banThaoKhuonV2: BanThao = { ...banThaoKhuon, phien_ban: 2 };
banMayChu.get("bk")!.push(banThaoKhuonV2); // một lượt chat vừa sửa
await act(() => {
  rootKhuon.render(h(VoNhap, { ...propsKhuon, banThao: banThaoKhuonV2 }));
});
await choDen(() => soGoi(laTrangCua("bk", 2)) === 1 && daTaiXong(khungKhuon));
assert.equal(
  soGoi(laTrangCua("bk", 2)),
  1,
  "phiên bản mới → ĐÚNG một lượt tải mới, `phien_ban` tường minh",
);
assert.ok(nutChu(khungKhuon, "Tải Word") !== null, "khuôn DOCX tải được Word");

// (b) Điền TẠI CHỖ, TỪNG chỗ (chủ dự án 2026-09-27: "để người dùng trực tiếp
// thao tác trên" trang; lưu ô điền không tính vào trần sửa): Enter lưu ngay,
// Tab lưu rồi MỞ chỗ kế, Esc huỷ, bấm sang chỗ khác lưu chỗ đang mở trước. Không
// còn bảng ô điền, không còn nút "Lưu n chỗ" gom lại.
cungNut(
  tim(khungKhuon, (n) => n.tagName === "FORM"),
  null,
  "không còn bảng ô điền",
);
assert.doesNotMatch(khungKhuon.textContent, /Ô điền|Đã điền \d+\/\d+/, "không dòng 'Ô điền · k/T'");
cungNut(nutChu(khungKhuon, "Rút gọn"), null, "khuôn gốc: không phím tắt viết lại văn bản");
cungNut(nutChu(khungKhuon, "Trang trọng hơn"), null);
cungNut(nutChu(khungKhuon, "Soát lại theo luật"), null);
cungNut(nutLuu(khungKhuon), null, "không còn nút 'Lưu n chỗ': mỗi chỗ tự lưu");
assert.deepEqual(
  nutO(khungKhuon).map((n) => n.getAttribute("data-o")),
  ["0.0", "1.0"],
  "một nút cho mỗi chỗ ĐỊNH VỊ được, theo thứ tự đọc (trang 1 rồi trang 2)",
);
const phanTram = (n: Nut, k: string) => Number.parseFloat(String(n.style[k]));
{
  const [o0, o1] = nutO(khungKhuon) as [Nut, Nut];
  assert.deepEqual(
    [phanTram(o0, "left"), phanTram(o0, "top"), phanTram(o0, "width")],
    [20, 25, 30],
    "pt → phần trăm khổ trang 1 (595×842)",
  );
  assert.ok(Math.abs(phanTram(o0, "height") - 2) < 1e-6);
  assert.deepEqual(
    [phanTram(o1, "left"), phanTram(o1, "top"), phanTram(o1, "width")],
    [10, 10, 40],
    "trang 2 dùng khổ CỦA NÓ (612×792)",
  );
  assert.ok(
    anhTrang(khungKhuon)[1]!.parentNode!.contains(o1) &&
      !anhTrang(khungKhuon)[0]!.parentNode!.contains(o1),
    "nút nằm trong khung của ĐÚNG trang nó thuộc về",
  );
  assert.equal(o0.getAttribute("aria-label"), "Điền: Họ và tên — đang là “Nguyễn Văn Ánh”");
  assert.equal(o1.getAttribute("aria-label"), "Điền: Email — còn trống");
  assert.match(o0.getAttribute("class") ?? "", /bg-brass-500\/15/, "chỗ đã điền tô nhạt");
  assert.doesNotMatch(o1.getAttribute("class") ?? "", /bg-brass-500\/15/, "chỗ trống không tô");
  assert.match(o0.getAttribute("class") ?? "", /focus-brass/, "vòng tiêu điểm thấy được");
  assert.equal(o0.textContent, "", "ảnh đã có đúng chữ: không vẽ đè");
}
// Bấm → ô nhập đè đúng chỗ đó, sẵn giá trị đang có, nhận tiêu điểm, có nhãn.
await act(() => phat(nutOKhoa(khungKhuon, "0.0")!, "click"));
const oNhap = oNhapCua(khungKhuon)!;
assert.ok(oNhap !== null, "bấm chỗ trống mở ô nhập tại chỗ");
assert.equal(giaTri(oNhap), "Nguyễn Văn Ánh");
cungNut(document.activeElement, oNhap, "ô nhập nhận tiêu điểm ngay");
assert.equal(oNhap.getAttribute("aria-label"), "Giá trị cho Họ và tên");
assert.match(
  theoMoTa(khungKhuon, oNhap).join(" "),
  /Enter lưu · Esc huỷ · Tab lưu rồi sang chỗ kế/,
);
{
  const boc = oNhap.parentNode!;
  assert.equal(
    boc.style["left"],
    "min(20%, calc(100% - max(12ch, 30%)))",
    "ô nhập không tràn mép phải tờ",
  );
  assert.equal(boc.style["width"], "max(12ch, 30%)", "ít nhất bề rộng chỗ trống, tối thiểu 12ch");
  assert.match(String(boc.style["fontSize"]), /^max\(12px, [\d.]+cqw\)$/, "cỡ chữ theo bề rộng tờ");
  assert.match(boc.getAttribute("class") ?? "", /\bz-10\b/, "ô nhập đè lên nút các chỗ phía sau");
}
// Esc: không gửi gì, chữ gõ nhầm bỏ đi, tiêu điểm về đúng nút đó.
await go(oNhap, "Gõ nhầm");
await phim(oNhap, "Escape");
await choDen(() => oNhapCua(khungKhuon) === null);
assert.equal(soPatch(), 0, "Esc không gửi gì");
assert.equal(
  nutOKhoa(khungKhuon, "0.0")?.getAttribute("aria-label"),
  "Điền: Họ và tên — đang là “Nguyễn Văn Ánh”",
  "Esc: chữ gõ nhầm bỏ đi",
);
cungNut(document.activeElement, nutOKhoa(khungKhuon, "0.0"), "Esc: tiêu điểm về nút 0.0");

// Enter: MỘT PATCH ngay — chỉ chỗ đó, phiên bản mới nhất. Đang lưu: ô chỉ đọc,
// báo "Đang lưu…", Lùi khoá. Lưu xong: ô đóng, tiêu điểm về ĐÚNG nút đó, chữ mới
// hiện ngay trên trang dù ảnh chưa dựng lại.
let cong = taoCong();
congPatch = cong.cong;
await act(() => phat(nutOKhoa(khungKhuon, "0.0")!, "click"));
await go(oNhapCua(khungKhuon)!, "Hà Nội");
await phim(oNhapCua(khungKhuon)!, "Enter");
await choDen(() => soPatch() === 1);
assert.deepEqual(
  thanPatch(),
  [
    [
      "/ban-thao/bk/o-dien",
      { phien_ban: 2, gia_tri: [{ don_vi: 0, cho_trong: 0, gia_tri: "Hà Nội" }] },
    ],
  ],
  "Enter: MỘT PATCH, chỉ chỗ đó, phiên bản đang nhìn",
);
assert.ok(oNhapCua(khungKhuon)?.getAttribute("readonly") !== null, "đang lưu: ô chỉ đọc");
assert.match(theoMoTa(khungKhuon, oNhapCua(khungKhuon)!).join(" "), /Đang lưu…/);
assert.equal(
  nutChu(khungKhuon, "Lùi")?.getAttribute("aria-disabled"),
  "true",
  "đang lưu: Lùi khoá",
);
congPatch = null;
await act(async () => {
  cong.mo();
  await nhip();
});
await choDen(() => oNhapCua(khungKhuon) === null);
cungNut(document.activeElement, nutOKhoa(khungKhuon, "0.0"), "Enter: tiêu điểm về chính chỗ đó");
assert.equal(capNhatKhuon.at(-1)?.phien_ban, 3, "lưu xong → phiên bản mới lên sân khấu");
{
  const n = nutOKhoa(khungKhuon, "0.0")!;
  assert.equal(n.getAttribute("aria-label"), "Điền: Họ và tên — đang là “Hà Nội”");
  assert.equal(n.textContent, "Hà Nội", "chữ vừa lưu hiện NGAY trên chỗ trống, đè ảnh cũ");
  assert.match(n.getAttribute("class") ?? "", /bg-white/);
  assert.doesNotMatch(
    n.getAttribute("class") ?? "",
    /outline-dashed/,
    "đã lưu: không còn viền chờ",
  );
}
assert.equal(soGoi(laTrangCua("bk", 3)), 0, "vừa lưu: chưa dựng lại — đợi người dùng dừng tay");

// Tab: lưu rồi MỞ chỗ kế (không chỉ dời tiêu điểm); Shift+Tab mở chỗ trước.
// Không đổi gì: không gửi. Mở lại chỗ vừa lưu: giá trị MỚI NHẤT của bản thảo,
// không phải chữ trên ảnh cũ.
await act(() => phat(nutOKhoa(khungKhuon, "0.0")!, "click"));
assert.equal(giaTri(oNhapCua(khungKhuon)), "Hà Nội", "mở lại: giá trị đã lưu, không phải ảnh cũ");
await phim(oNhapCua(khungKhuon)!, "Tab");
await choDen(() => oNhapCua(khungKhuon)?.getAttribute("aria-label") === "Giá trị cho Email");
assert.equal(soPatch(), 1, "Tab mà không đổi gì: không gửi");
cungNut(document.activeElement, oNhapCua(khungKhuon), "Tab: ô của chỗ kế MỞ và nhận tiêu điểm");
await go(oNhapCua(khungKhuon)!, "x@y.vn");
await phim(oNhapCua(khungKhuon)!, "Tab", { shiftKey: true });
await choDen(() => oNhapCua(khungKhuon)?.getAttribute("aria-label") === "Giá trị cho Họ và tên");
assert.deepEqual(
  thanPatch().at(-1),
  [
    "/ban-thao/bk/o-dien",
    { phien_ban: 3, gia_tri: [{ don_vi: 1, cho_trong: 0, gia_tri: "x@y.vn" }] },
  ],
  "Shift+Tab: lưu chỗ đó bằng phiên bản vừa tạo, rồi mở chỗ trước",
);
cungNut(document.activeElement, oNhapCua(khungKhuon), "Shift+Tab: ô chỗ trước nhận tiêu điểm");
assert.equal(nutOKhoa(khungKhuon, "1.0")?.textContent, "x@y.vn", "chỗ vừa lưu hiện chữ ngay");
// 422 khi Tab: ô ở lại, chữ còn nguyên, câu lỗi ngay dưới ô, KHÔNG sang chỗ kế.
tuChoiO = "Sai chỗ";
await go(oNhapCua(khungKhuon)!, "Sai chỗ");
await phim(oNhapCua(khungKhuon)!, "Tab");
await choDen(() => oNhapCua(khungKhuon)?.getAttribute("aria-invalid") === "true");
assert.equal(soPatch(), 3);
assert.equal(
  oNhapCua(khungKhuon)?.getAttribute("aria-label"),
  "Giá trị cho Họ và tên",
  "422: không sang chỗ kế",
);
assert.equal(giaTri(oNhapCua(khungKhuon)), "Sai chỗ", "422: chữ còn nguyên");
assert.ok(
  theoMoTa(khungKhuon, oNhapCua(khungKhuon)!).includes(CAU_AP),
  "422: câu lỗi gắn với ô qua aria-describedby",
);
cungNut(document.activeElement, oNhapCua(khungKhuon), "422: tiêu điểm ở lại ô");
// Gõ tiếp gỡ câu lỗi cũ; Esc bỏ chữ chưa lưu, chỗ đó về giá trị đã lưu.
await go(oNhapCua(khungKhuon)!, "Sai chỗ nữa");
assert.equal(oNhapCua(khungKhuon)?.getAttribute("aria-invalid"), null, "gõ tiếp: gỡ câu lỗi cũ");
await phim(oNhapCua(khungKhuon)!, "Escape");
await choDen(() => oNhapCua(khungKhuon) === null);
assert.equal(
  nutOKhoa(khungKhuon, "0.0")?.getAttribute("aria-label"),
  "Điền: Họ và tên — đang là “Hà Nội”",
  "Esc: bỏ chữ chưa lưu",
);
assert.equal(soPatch(), 3, "Esc không gửi gì");
tuChoiO = null;

// Bấm sang chỗ khác: chỗ đang mở LƯU TRƯỚC (rời ô = blur, trình duyệt phát nó ở
// `mousedown`, trước cú click), chỗ mới mở ngay; chữ vừa gõ hiện NGAY trên chỗ cũ
// trong lúc lưu. Hai lượt lưu xếp hàng: lượt sau gửi phiên bản lượt trước vừa
// tạo. Lượt về muộn không kéo tiêu điểm khỏi chỗ đang mở.
cong = taoCong();
congPatch = cong.cong;
await act(() => phat(nutOKhoa(khungKhuon, "0.0")!, "click"));
await go(oNhapCua(khungKhuon)!, "Hải Phòng");
await act(() => oNhapCua(khungKhuon)!.blur());
await act(() => phat(nutOKhoa(khungKhuon, "1.0")!, "click"));
await choDen(() => soPatch() === 4);
assert.deepEqual(
  thanPatch().at(-1),
  [
    "/ban-thao/bk/o-dien",
    { phien_ban: 4, gia_tri: [{ don_vi: 0, cho_trong: 0, gia_tri: "Hải Phòng" }] },
  ],
  "rời ô: lưu chỗ đó",
);
assert.equal(
  oNhapCua(khungKhuon)?.getAttribute("aria-label"),
  "Giá trị cho Email",
  "chỗ vừa bấm mở ngay, không đợi lượt lưu",
);
{
  const n = nutOKhoa(khungKhuon, "0.0")!;
  assert.equal(n.textContent, "Hải Phòng", "đang lưu: chữ vừa gõ hiện ngay trên chỗ cũ");
  assert.equal(n.getAttribute("aria-label"), "Điền: Họ và tên — đang lưu “Hải Phòng”");
  assert.match(n.getAttribute("class") ?? "", /outline-dashed/, "đang lưu: viền đứt");
}
await go(oNhapCua(khungKhuon)!, "z@z.vn");
await phim(oNhapCua(khungKhuon)!, "Enter");
await choDen(() => false);
assert.equal(
  soPatch(),
  4,
  "lượt lưu thứ hai CHỜ lượt đầu — cùng gửi một phiên bản thì lượt sau 422",
);
const congDau = cong;
cong = taoCong();
congPatch = cong.cong;
await act(async () => {
  congDau.mo();
  await nhip();
});
await choDen(() => soPatch() === 5);
assert.deepEqual(
  thanPatch().at(-1),
  [
    "/ban-thao/bk/o-dien",
    { phien_ban: 5, gia_tri: [{ don_vi: 1, cho_trong: 0, gia_tri: "z@z.vn" }] },
  ],
  "lượt sau gửi phiên bản lượt trước vừa tạo",
);
assert.equal(oNhapCua(khungKhuon)?.getAttribute("aria-label"), "Giá trị cho Email");
cungNut(
  document.activeElement,
  oNhapCua(khungKhuon),
  "lượt lưu về muộn của chỗ cũ không kéo tiêu điểm",
);
assert.equal(
  nutOKhoa(khungKhuon, "0.0")?.getAttribute("aria-label"),
  "Điền: Họ và tên — đang là “Hải Phòng”",
);
congPatch = null;
await act(async () => {
  cong.mo();
  await nhip();
});
await choDen(() => oNhapCua(khungKhuon) === null);
cungNut(document.activeElement, nutOKhoa(khungKhuon, "1.0"), "Enter: tiêu điểm về chính chỗ đó");
assert.equal(nutOKhoa(khungKhuon, "1.0")?.textContent, "z@z.vn");
// 422 khi đã rời ô: câu lỗi đứng ngay dưới chỗ đó trên trang (gắn qua
// aria-describedby), chữ còn đè lên ảnh, tiêu điểm ở lại chỗ đang mở.
tuChoiO = "bị từ chối";
await act(() => phat(nutOKhoa(khungKhuon, "1.0")!, "click"));
await go(oNhapCua(khungKhuon)!, "bị từ chối");
await act(() => oNhapCua(khungKhuon)!.blur());
await act(() => phat(nutOKhoa(khungKhuon, "0.0")!, "click"));
await choDen(() => nutOKhoa(khungKhuon, "1.0")?.getAttribute("aria-describedby") != null);
{
  const n = nutOKhoa(khungKhuon, "1.0")!;
  assert.deepEqual(theoMoTa(khungKhuon, n), [CAU_AP], "câu từ chối gắn với nút của chỗ đó");
  assert.equal(n.getAttribute("aria-label"), "Điền: Email — chưa lưu “bị từ chối”");
  assert.equal(n.textContent, "bị từ chối", "chữ bị từ chối còn trên trang");
  assert.match(n.getAttribute("class") ?? "", /outline-destructive/, "viền đỏ liền");
}
assert.equal(oNhapCua(khungKhuon)?.getAttribute("aria-label"), "Giá trị cho Họ và tên");
cungNut(document.activeElement, oNhapCua(khungKhuon), "422 về muộn: tiêu điểm ở lại chỗ đang mở");
await phim(oNhapCua(khungKhuon)!, "Escape");
// Mở lại: chữ bị từ chối và câu lỗi còn đó; rời ô với ĐÚNG chữ đó không gửi lại
// một 422 y hệt; Esc bỏ nó.
await act(() => phat(nutOKhoa(khungKhuon, "1.0")!, "click"));
assert.equal(giaTri(oNhapCua(khungKhuon)), "bị từ chối");
assert.equal(oNhapCua(khungKhuon)?.getAttribute("aria-invalid"), "true");
const soTruocRoi = soPatch();
await act(() => oNhapCua(khungKhuon)!.blur());
await choDen(() => oNhapCua(khungKhuon) === null);
assert.equal(soPatch(), soTruocRoi, "rời ô với đúng chữ vừa bị từ chối: không gửi lại");
await act(() => phat(nutOKhoa(khungKhuon, "1.0")!, "click"));
await phim(oNhapCua(khungKhuon)!, "Escape");
assert.equal(
  nutOKhoa(khungKhuon, "1.0")?.getAttribute("aria-label"),
  "Điền: Email — đang là “z@z.vn”",
  "Esc: bỏ chữ bị từ chối, về giá trị đã lưu",
);
assert.equal(nutOKhoa(khungKhuon, "1.0")?.getAttribute("aria-describedby"), null);
tuChoiO = null;
// Chỗ chưa định vị: một nút nhỏ ở thanh công cụ, CÙNG ô nhập và cùng luật lưu.
const nutChuaDinhVi = nutChu(khungKhuon, "Chỗ trống chưa định vị (1)")!;
assert.ok(nutChuaDinhVi !== null, "chỗ không có vị trí: nút 'Chỗ trống chưa định vị (n)'");
assert.equal(nutChuaDinhVi.getAttribute("aria-expanded"), "false");
await act(() => phat(nutChuaDinhVi, "click"));
const dsChuaDinhVi = () =>
  tim(khungKhuon, (n) => n.getAttribute("aria-label") === "Chỗ trống chưa định vị")!;
assert.equal(nutChuaDinhVi.getAttribute("aria-expanded"), "true");
assert.deepEqual(
  nutO(dsChuaDinhVi()).map((n) => n.getAttribute("aria-label")),
  ["Điền: chỗ trống — còn trống"],
  "danh sách chỉ gồm chỗ chưa định vị; nhãn rỗng đọc là 'chỗ trống', không 'Ô 1.1'",
);
await act(() => phat(nutO(dsChuaDinhVi())[0]!, "click"));
await go(oNhapCua(dsChuaDinhVi())!, "Hà Nội");
await phim(oNhapCua(dsChuaDinhVi())!, "Enter");
await choDen(() => oNhapCua(dsChuaDinhVi()) === null);
assert.deepEqual(
  thanPatch().at(-1),
  [
    "/ban-thao/bk/o-dien",
    { phien_ban: 6, gia_tri: [{ don_vi: 1, cho_trong: 1, gia_tri: "Hà Nội" }] },
  ],
  "danh sách chưa định vị: Enter cũng lưu ngay",
);
cungNut(document.activeElement, nutO(dsChuaDinhVi())[0], "Enter: tiêu điểm về mục đó");
assert.equal(
  nutO(dsChuaDinhVi())[0]?.getAttribute("aria-label"),
  "Điền: chỗ trống — đang là “Hà Nội”",
);
// Gõ dở rồi bấm ra ngoài (kể cả một chỗ trên trang): ô trong danh sách LƯU trước
// khi danh sách đóng ở `mousedown`.
await act(() => phat(nutO(dsChuaDinhVi())[0]!, "click"));
await go(oNhapCua(dsChuaDinhVi())!, "Hải Phòng");
await act(() => phat(khungKhuon, "mousedown"));
assert.equal(nutChuaDinhVi.getAttribute("aria-expanded"), "false", "bấm ra ngoài: danh sách đóng");
await choDen(() => soPatch() === 8);
assert.deepEqual(
  thanPatch().at(-1),
  [
    "/ban-thao/bk/o-dien",
    { phien_ban: 7, gia_tri: [{ don_vi: 1, cho_trong: 1, gia_tri: "Hải Phòng" }] },
  ],
  "bấm ra ngoài: chữ gõ dở trong danh sách được lưu, không chỉ 'chưa lưu'",
);
await choDen(() => capNhatKhuon.at(-1)?.phien_ban === 8);
await act(() => phat(nutChuaDinhVi, "click"));
cungNut(oNhapCua(dsChuaDinhVi()), null, "mở lại danh sách: không bật lại ô nhập còn dở");
assert.match(dsChuaDinhVi().textContent, /Hải Phòng/);
assert.doesNotMatch(dsChuaDinhVi().textContent, /chưa lưu/);
await act(() => phat(nutO(dsChuaDinhVi())[0]!, "keydown", { key: "Escape" }));
assert.equal(nutChuaDinhVi.getAttribute("aria-expanded"), "false", "Esc đóng danh sách");
cungNut(document.activeElement, nutChuaDinhVi, "Esc: tiêu điểm về nút mở danh sách");

// (b2) Máy chủ cũ (payload không có `o`): không nút phủ nào, và MỌI chỗ của
// `khuon` thành "chưa định vị" — vẫn điền được, không ngõ cụt.
const { khung: khungCu2, root: rootCu2 } = taoRoot();
await act(() => {
  rootCu2.render(h(SanKhauBanThao, { ...propsKhuon, banThao: { ...banThaoKhuon, id: "bcu" } }));
});
await choDen(() => daTaiXong(khungCu2) && anhTrang(khungCu2).length === 2);
assert.equal(nutO(khungCu2).length, 0, "không `o`: không nút phủ nào trên trang");
assert.ok(nutChu(khungCu2, "Chỗ trống chưa định vị (3)") !== null, "mọi chỗ vào danh sách");

// (b3) Trang dựng lại MỘT lần, lúc người dùng dừng tay (`NGHI_DUNG_TRANG_MS`
// sau lần lưu cuối) — không lần nào cho mỗi lần lưu: mỗi lượt dựng giữ suất
// LibreOffice của cả tài khoản. Trong lúc dựng, ảnh cũ đứng yên (mờ), chỗ trống
// vẫn điền được, nút giữ tiêu điểm không bị tháo; ảnh mới về thì chữ vẽ đè
// nhường chỗ cho chữ thật trên ảnh.
const btD: BanThao = { ...banThaoKhuon, id: "bd", phien_ban: 1 };
banMayChu.set("bd", [btD]);
const { khung: khungD, root: rootD } = taoRoot();
await act(() => {
  rootD.render(h(VoNhap, { ...propsKhuon, banThao: btD }));
});
await choDen(() => daTaiXong(khungD) && nutO(khungD).length === 2);
await act(() => phat(nutOKhoa(khungD, "0.0")!, "click"));
await go(oNhapCua(khungD)!, "A");
await phim(oNhapCua(khungD)!, "Tab");
await choDen(() => oNhapCua(khungD)?.getAttribute("aria-label") === "Giá trị cho Email");
await go(oNhapCua(khungD)!, "B");
await phim(oNhapCua(khungD)!, "Enter");
await choDen(() => oNhapCua(khungD) === null);
assert.deepEqual(
  [2, 3].map((pb) => soGoi(laTrangCua("bd", pb))),
  [0, 0],
  "vừa lưu hai chỗ liền tay: chưa dựng lại lần nào",
);
assert.deepEqual(
  ["0.0", "1.0"].map((k) => nutOKhoa(khungD, k)?.textContent),
  ["A", "B"],
  "chữ vừa lưu đè lên ảnh cũ trong lúc chờ",
);
const congD = taoCong();
congTrang = { id: "bd", cong: congD.cong };
await cho(NGHI_DUNG_TRANG_MS + 150);
await choDen(() => soGoi(laTrangCua("bd", 3)) === 1);
assert.equal(soGoi(laTrangCua("bd", 2)), 0, "phiên bản giữa không bao giờ được dựng");
assert.equal(soGoi(laTrangCua("bd", 3)), 1, "dừng tay: ĐÚNG một lượt dựng, bản mới nhất");
assert.equal(anhTrang(khungD).length, 2, "đang dựng: trang cũ còn đó, không chớp khung chờ");
assert.equal(daTaiXong(khungD), false, "đang dựng: vùng trang `aria-busy`");
assert.match(anhTrang(khungD)[0]!.getAttribute("class") ?? "", /opacity-60/, "ảnh cũ mờ");
assert.equal(nutOKhoa(khungD, "1.0")?.getAttribute("aria-disabled"), null);
await act(() => phat(nutOKhoa(khungD, "1.0")!, "click"));
assert.ok(oNhapCua(khungD) !== null, "trang đang dựng lại vẫn điền được");
await phim(oNhapCua(khungD)!, "Escape");
await act(() => nutOKhoa(khungD, "0.0")!.focus());
const nutTruocKhiDung = nutOKhoa(khungD, "0.0");
congTrang = null;
await act(async () => {
  congD.mo();
  await nhip();
});
await choDen(() => daTaiXong(khungD));
cungNut(nutOKhoa(khungD, "0.0"), nutTruocKhiDung, "cùng một nút qua lượt dựng lại");
cungNut(document.activeElement, nutTruocKhiDung, "không mất tiêu điểm khi trang dựng lại");
assert.equal(nutOKhoa(khungD, "0.0")?.textContent, "", "ảnh mới đã có chữ: không vẽ đè nữa");
assert.equal(nutOKhoa(khungD, "0.0")?.getAttribute("aria-label"), "Điền: Họ và tên — đang là “A”");
assert.doesNotMatch(anhTrang(khungD)[0]!.getAttribute("class") ?? "", /opacity-60/);

// (b4) MỘT lượt dựng một lúc cho cả tab: đổi đường dẫn giữa lúc dựng thì lượt
// mới CHỜ lượt cũ xong (máy chủ vẫn dựng lượt cũ tới cùng và giữ suất — gọi ngay
// là 503), và lượt bị thay trước khi tới lượt thì không bao giờ gửi.
const congQ = taoCong();
congTrang = { id: "bq", cong: congQ.cong };
const { khung: khungQ, root: rootQ } = taoRoot();
const veQ = (pb: number) =>
  act(() => {
    rootQ.render(
      h(KhungTrangAnh, {
        duongDan: `/ban-thao/bq/trang?phien_ban=${pb}`,
        soTrang: 2,
        thuPhong: 100,
        nhan: "Trang",
      }),
    );
  });
await veQ(1);
await choDen(() => soGoi(laTrangCua("bq", 1)) === 1);
await veQ(2);
await veQ(3);
await choDen(() => false);
assert.deepEqual(
  [2, 3].map((pb) => soGoi(laTrangCua("bq", pb))),
  [0, 0],
  "lượt đang dựng chưa xong: không gửi lượt mới",
);
congTrang = null;
await act(async () => {
  congQ.mo();
  await nhip();
});
await choDen(() => daTaiXong(khungQ));
assert.deepEqual(
  [2, 3].map((pb) => soGoi(laTrangCua("bq", pb))),
  [0, 1],
  "xong: gửi ĐÚNG lượt mới nhất; lượt bị thay trước khi tới lượt không đi",
);

// (c) Khuôn PDF: không có Word; tải PDF đọc tên từ Content-Disposition.
await act(() => {
  rootKhuon.render(
    h(VoNhap, {
      ...propsKhuon,
      banThao: { ...banThaoKhuonV2, phien_ban: 3, khuon: { ...KHUON, dinh_dang: "pdf" } },
    }),
  );
});
cungNut(nutChu(khungKhuon, "Tải Word"), null, "khuôn PDF chỉ tải được PDF");
const taiVe = await taiXuongBanThao("bk", "pdf", 2);
assert.ok(taiVe.ok && taiVe.data.ten === "BM.M05 - đã điền.pdf", "tên tệp lấy từ filename*");
assert.equal(
  goiKhuon.at(-1)?.url,
  "/ban-thao/bk/tai-xuong?dang=pdf&phien_ban=2",
  "tải đúng phiên bản đang nhìn",
);
assert.ok(
  "Authorization" in (goiKhuon.at(-1)?.headers ?? {}) ||
    "X-Khach-Id" in (goiKhuon.at(-1)?.headers ?? {}),
  "tải tệp mang header danh tính",
);
// Hẹn dựng lại trang của các sân khấu trên đã tới giờ: không để nó chạy giữa
// những phép đếm lượt tải ở dưới.
await cho(NGHI_DUNG_TRANG_MS + 200);

// (d) Bản thảo HTML: vẫn A4, không một lượt tải trang, không nút phủ, còn phím tắt.
const soTrangTruoc = soGoi((g) => g.url.startsWith("/ban-thao/b1/"));
const { khung: khungHtml, root: rootHtml } = taoRoot();
await act(() => {
  rootHtml.render(h(SanKhauBanThao, propsSanKhau));
});
await choDen(() => false);
assert.ok(tim(khungHtml, (n) => n.tagName === "ARTICLE") !== null, "bản thảo HTML vẫn là A4");
assert.equal(
  soGoi((g) => g.url.startsWith("/ban-thao/b1/")),
  soTrangTruoc,
  "không tải trang ảnh nào",
);
cungNut(
  tim(khungHtml, (n) => n.tagName === "INPUT"),
  null,
  "không có ô điền",
);
assert.equal(nutO(khungHtml).length, 0, "không nút phủ");
for (const chu of ["Rút gọn", "Trang trọng hơn", "Soát lại theo luật"])
  assert.ok(nutChu(khungHtml, chu) !== null, `HTML giữ phím tắt '${chu}'`);
cungNut(nutChu(khungHtml, "Chỗ trống chưa định vị"), null);

// (e) Khung trang: 503 nói máy chủ bận + Thử lại; 404 không Thử lại.
const { khung: khung503, root: root503 } = taoRoot();
await act(() => {
  root503.render(
    h(KhungTrangAnh, {
      duongDan: "/ban-thao/b503/trang?phien_ban=1",
      soTrang: 2,
      thuPhong: 100,
      nhan: "Trang",
    }),
  );
});
await choDen(() => tim(khung503, (n) => n.getAttribute("role") === "alert") !== null);
assert.match(
  tim(khung503, (n) => n.getAttribute("role") === "alert")?.textContent ?? "",
  /bận/,
  "503: nói máy chủ đang bận",
);
await act(() => phat(nutChu(khung503, "Thử lại")!, "click"));
await choDen(() => anhTrang(khung503).length === 2);
assert.equal(lan503, 2, "Thử lại tải lại ĐÚNG một lần");
const { khung: khung404, root: root404 } = taoRoot();
await act(() => {
  root404.render(
    h(KhungTrangAnh, {
      duongDan: "/ban-thao/b404/trang?phien_ban=1",
      soTrang: 1,
      thuPhong: 100,
      nhan: "Trang",
    }),
  );
});
await choDen(() => tim(khung404, (n) => n.getAttribute("role") === "alert") !== null);
cungNut(nutChu(khung404, "Thử lại"), null, "404 không tự hết: không mời thử lại");

// (f) Sân khấu "Bản tải lên": chỉ đọc, SẠCH (payload có `o` cũng không phủ gì),
// chờ có thông báo, tiêu đề nhận tiêu điểm, nút đóng đi qua ĐÚNG `onDong`.
const dongBanTaiLen: number[] = [];
const dienTuBanTaiLen: number[] = [];
const { khung: khungBtl, root: rootBtl } = taoRoot();
await act(() => {
  rootBtl.render(
    h(SanKhauBanTaiLen, {
      viecId: VIEC,
      tenTep: "BM.M05.docx",
      soTrang: 2,
      onDong: () => dongBanTaiLen.push(1),
      onDienBieuMau: () => dienTuBanTaiLen.push(1),
    }),
  );
});
assert.match(
  tim(khungBtl, (n) => n.getAttribute("role") === "status")?.textContent ?? "",
  /Đang dựng trang/,
  "đang tải: vùng trạng thái đọc lên lịch sự",
);
{
  let n = tim(khungBtl, (x) => x.getAttribute("role") === "status")?.parentNode ?? null;
  while (n !== null && n.getAttribute("aria-busy") !== "true") n = n.parentNode;
  assert.ok(
    n === null,
    "vùng trạng thái NGOÀI cây aria-busy: trong đó trình đọc màn hình hoãn đọc",
  );
}
assert.equal(
  timTatNut(khungBtl, (n) => n.getAttribute("data-khung-cho") !== null).length,
  2,
  "khung chờ theo số trang",
);
moCongBanTaiLen();
await choDen(() => anhTrang(khungBtl).length === 2);
assert.equal(
  soGoi((g) => g.url === `/tai-lieu/${VIEC}/trang`),
  1,
  "bản tải lên: một lượt tải",
);
const tieuDeBtl = tim(khungBtl, (n) => n.getAttribute("data-tieu-de-san-khau") !== null);
assert.equal(tieuDeBtl?.textContent, "BM.M05.docx");
assert.equal(tieuDeBtl?.getAttribute("tabindex"), "-1", "tiêu đề nhận tiêu điểm khi sân khấu mở");
cungNut(
  tim(khungBtl, (n) => n.tagName === "INPUT"),
  null,
  "bản tải lên chỉ đọc",
);
assert.equal(nutO(khungBtl).length, 0, "bản tải lên: không nút phủ nào dù payload có `o`");
cungNut(nutChu(khungBtl, "Chỗ trống chưa định vị"), null);
await act(() => phat(nutChu(khungBtl, "Điền biểu mẫu")!, "click"));
await act(() =>
  phat(
    tim(khungBtl, (n) => n.getAttribute("aria-label") === "Đóng bản tải lên")!,
    "click",
  ),
);
assert.deepEqual([dienTuBanTaiLen.length, dongBanTaiLen.length], [1, 1]);

// (g) Khung tài liệu: nút "Bản tải lên"/"Điền biểu mẫu" chỉ khi có khuôn gốc;
// chọn loại rút lại TRÊN việc đã lưu (`doc-lai`), không tải tệp lên lần hai.
const moBtl: unknown[] = [];
const dienBm: string[] = [];
const { khung: khungTl, root: rootTl } = taoRoot();
await act(() => {
  rootTl.render(
    h(TaiLieuDuKien, {
      hoiThoaiId: "p1",
      loai: null,
      donViDangMo: { taiLieuId: VIEC, chiSo: null },
      onMoBanTaiLen: (t: unknown) => moBtl.push(t),
      onDienBieuMau: (id: string) => dienBm.push(id),
    }),
  );
});
await choDen(() => nutChu(khungTl, "Bản tải lên") !== null);
assert.doesNotMatch(
  khungTl.textContent,
  /Đọc dữ kiện từ tài liệu/,
  "trong drawer (không `onDong`): không lặp tiêu đề và nút đóng của khung",
);
await act(() => phat(nutChu(khungTl, "Bản tải lên")!, "click"));
await act(() => phat(nutChu(khungTl, "Điền biểu mẫu")!, "click"));
assert.deepEqual(moBtl, [{ id: VIEC, ten_tep: "BM.M05.docx", so_trang: 2 }]);
assert.deepEqual(dienBm, [VIEC]);
const chonLoai = tim(khungTl, (n) => n.tagName === "SELECT")!;
const loaiDau = timTatNut(chonLoai, (n) => n.tagName === "OPTION")[1]!.getAttribute("value")!;
await act(() => {
  (chonLoai as unknown as { value: string }).value = loaiDau;
  phat(chonLoai, "change");
});
await choDen(() => soGoi((g) => g.url.endsWith("/doc-lai")) === 1);
assert.deepEqual(
  goiKhuon.filter((g) => g.url.endsWith("/doc-lai")).map((g) => [g.url, g.method, g.body]),
  [[`/tai-lieu/${VIEC}/doc-lai`, "POST", { loai: loaiDau }]],
  "đổi loại = POST doc-lai trên chính việc đó",
);
assert.equal(
  soGoi((g) => g.url === "/tai-lieu" && g.method === "POST"),
  0,
  "không tải tệp lên lại",
);
const { khung: khungCu, root: rootCu } = taoRoot();
await act(() => {
  rootCu.render(
    h(TaiLieuDuKien, {
      hoiThoaiId: "p1",
      loai: null,
      donViDangMo: { taiLieuId: VIEC_CU, chiSo: null },
      onMoBanTaiLen: () => {},
      onDienBieuMau: () => {},
    }),
  );
});
await choDen(
  () => /Đã đọc/.test(khungCu.textContent) && soGoi((g) => g.url === `/tai-lieu/${VIEC_CU}`) === 1,
);
await choDen(() => false);
cungNut(nutChu(khungCu, "Bản tải lên"), null, "tài liệu không có khuôn gốc: không có nút");

// (h) Lùi và lưu là hai lượt ghi phiên bản, không chạy đua nhau; chữ bị từ chối
// sống TRÊN sân khấu (WCAG 3.3.7) và chặn tải tệp; lùi xong, chữ của bản vừa bỏ
// không quay lại qua một chỗ đã chạm mà không đổi.
const KHUON_V1 = {
  ...KHUON,
  cho_trong: KHUON.cho_trong.map((c) => (c.don_vi === 0 ? { ...c, gia_tri: "Trần Thị B" } : c)),
};
const btLuiV1: BanThao = { ...banThaoKhuon, id: "bl", phien_ban: 1, khuon: KHUON_V1 };
const btLuiV2: BanThao = { ...banThaoKhuon, id: "bl", phien_ban: 2 };
banMayChu.set("bl", [btLuiV1, btLuiV2]);
let btL: BanThao = btLuiV2;
let hienL = true;
let moCongLui: () => void = () => {};
const soLui: number[] = [];
const { khung: khungL, root: rootL } = taoRoot();
function veL() {
  rootL.render(h(VoNhap, { ...propsSanKhau, banThao: btL, hien: hienL, onLui: luiL }));
}
async function luiL() {
  soLui.push(1);
  await new Promise<void>((r) => {
    moCongLui = r;
  });
  banMayChu.get("bl")!.pop(); // máy chủ bỏ hẳn bản đang đứng
  btL = btLuiV1;
  veL();
  return true;
}
await act(() => veL());
await choDen(() => daTaiXong(khungL) && nutO(khungL).length === 2);
const nutLui = () => nutChu(khungL, "Lùi")!;
// Chạm mà không đổi (gõ lại đúng giá trị đang có): không gửi, không giữ gì.
await act(() => phat(nutOKhoa(khungL, "0.0")!, "click"));
await go(oNhapCua(khungL)!, "Nguyễn Văn Ánh ");
await phim(oNhapCua(khungL)!, "Enter");
await choDen(() => oNhapCua(khungL) === null);
const soPatchL = () => soGoi((g) => g.method === "PATCH" && g.url === "/ban-thao/bl/o-dien");
assert.equal(soPatchL(), 0, "gõ lại đúng giá trị đã lưu: không gửi");
// Một lượt lưu chưa về khoá Lùi và tải tệp; 422 thì Lùi mở lại, câu lỗi ngay dưới ô.
const congL = taoCong();
congPatch = congL.cong;
tuChoiO = "x@y.vn";
await act(() => phat(nutOKhoa(khungL, "1.0")!, "click"));
await go(oNhapCua(khungL)!, "x@y.vn");
await phim(oNhapCua(khungL)!, "Enter");
await choDen(() => soPatchL() === 1);
assert.equal(nutLui().getAttribute("aria-disabled"), "true", "lượt lưu chưa về: Lùi bị khoá");
assert.ok(
  nutChu(khungL, "Tải PDF")?.getAttribute("disabled") !== null,
  "lượt lưu chưa về: không tải tệp",
);
congPatch = null;
await act(async () => {
  congL.mo();
  await nhip();
});
await choDen(() => oNhapCua(khungL)?.getAttribute("aria-invalid") === "true");
assert.equal(nutLui().getAttribute("aria-disabled"), "false", "lưu đã về: Lùi mở lại");
assert.ok(theoMoTa(khungL, oNhapCua(khungL)!).includes(CAU_AP), "422: câu lỗi ngay dưới ô");
// Rời ô: chữ bị từ chối ở lại trên trang; tháo rồi lắp lại sân khấu (tab "Trợ
// lý", đóng) không mất nó.
await act(() => oNhapCua(khungL)!.blur());
await choDen(() => oNhapCua(khungL) === null);
assert.equal(nutOKhoa(khungL, "1.0")?.textContent, "x@y.vn");
hienL = false;
await act(() => veL());
assert.equal(nutO(khungL).length, 0, "sân khấu đã tháo (tab 'Trợ lý', đóng)");
hienL = true;
await act(() => veL());
await choDen(() => daTaiXong(khungL) && nutO(khungL).length === 2);
assert.equal(
  nutOKhoa(khungL, "1.0")?.textContent,
  "x@y.vn",
  "tháo rồi lắp lại sân khấu: chữ chưa lưu còn nguyên, không phải gõ lại",
);
assert.equal(
  nutOKhoa(khungL, "1.0")?.getAttribute("aria-label"),
  "Điền: Email — chưa lưu “x@y.vn”",
);
// Trang đang HIỆN chữ chưa lưu: tải tệp lúc đó là tải một tệp thiếu chữ ấy.
const soTaiTruoc = soGoi((g) => g.url.includes("/tai-xuong"));
await act(async () => {
  phat(nutChu(khungL, "Tải PDF")!, "click");
  await nhip();
});
assert.equal(
  soGoi((g) => g.url.includes("/tai-xuong")),
  soTaiTruoc,
  "còn chỗ chưa lưu: không tải",
);
// Lùi đang chạy: không bấm được lần hai (lùi hai bậc), và lưu một chỗ bị từ chối
// NGAY tại chỗ đó, không gửi gì.
await act(() => phat(nutLui(), "click"));
await choDen(() => soLui.length === 1);
assert.equal(nutLui().getAttribute("aria-disabled"), "true", "Lùi đang chạy: nút Lùi khoá");
await act(() => phat(nutLui(), "click"));
await choDen(() => false);
assert.equal(soLui.length, 1, "bấm Lùi lần hai trong lúc lùi: không lùi hai bậc");
const soPatchTruocLui = soPatchL();
await act(() => phat(nutOKhoa(khungL, "0.0")!, "click"));
await go(oNhapCua(khungL)!, "Mới");
await phim(oNhapCua(khungL)!, "Enter");
await choDen(() => oNhapCua(khungL)?.getAttribute("aria-invalid") === "true");
assert.equal(soPatchL(), soPatchTruocLui, "Lùi đang chạy: không gửi lượt lưu nào");
assert.match(theoMoTa(khungL, oNhapCua(khungL)!).join(" "), /Đang lùi/, "và nói lý do ngay dưới ô");
await phim(oNhapCua(khungL)!, "Escape");
await act(async () => {
  moCongLui();
  await nhip();
});
await choDen(() => nutChu(khungL, "Lùi") === null && daTaiXong(khungL));
assert.equal(
  nutOKhoa(khungL, "1.0")?.textContent,
  "x@y.vn",
  "lùi xong: chỗ đổi thật so với bản vừa bỏ giữ chữ chưa lưu",
);
assert.equal(
  nutOKhoa(khungL, "0.0")?.getAttribute("aria-label"),
  "Điền: Họ và tên — đang là “Trần Thị B”",
  "lùi xong: chỗ chỉ chạm mà không đổi đọc lại bản lùi về",
);
tuChoiO = null;

// (h2) Chỉ bản do CHÍNH lượt lưu tạo ra mới đợi người dùng dừng tay: Lùi ngay
// sau hai lần lưu thì trang của bản lùi về dựng NGAY, không đợi nốt
// `NGHI_DUNG_TRANG_MS` của lần lưu vừa rồi.
const btM: BanThao = { ...banThaoKhuon, id: "bm", phien_ban: 1 };
banMayChu.set("bm", [btM]);
let btMNgoai = btM;
const { khung: khungM, root: rootM } = taoRoot();
const veM = () => rootM.render(h(VoNhap, { ...propsKhuon, banThao: btMNgoai, onLui: luiM }));
async function luiM() {
  const ds = banMayChu.get("bm")!;
  ds.pop();
  btMNgoai = ds.at(-1)!;
  veM();
  return true;
}
await act(() => veM());
await choDen(() => daTaiXong(khungM) && nutO(khungM).length === 2);
await act(() => phat(nutOKhoa(khungM, "0.0")!, "click"));
await go(oNhapCua(khungM)!, "A");
await phim(oNhapCua(khungM)!, "Tab");
await choDen(() => oNhapCua(khungM)?.getAttribute("aria-label") === "Giá trị cho Email");
await go(oNhapCua(khungM)!, "B");
await phim(oNhapCua(khungM)!, "Enter");
await choDen(
  () =>
    oNhapCua(khungM) === null && nutChu(khungM, "Lùi")?.getAttribute("aria-disabled") === "false",
);
assert.equal(soGoi(laTrangCua("bm", 3)), 0, "vừa lưu: trang chưa dựng lại");
await act(async () => {
  phat(nutChu(khungM, "Lùi")!, "click");
  await nhip();
});
await choDen(() => soGoi(laTrangCua("bm", 2)) === 1);
assert.equal(
  soGoi(laTrangCua("bm", 2)),
  1,
  "Lùi ngay sau lần lưu: trang của bản lùi về dựng NGAY, không đợi hết lúc dừng tay",
);
assert.equal(soGoi(laTrangCua("bm", 3)), 0, "bản đã bỏ không bao giờ được dựng");
await choDen(() => daTaiXong(khungM));

// (i) Tài liệu đọc DƯỚI NỀN: con chip là lối vào duy nhất, menu nhỏ của nó mở
// bản tải lên / điền / dữ kiện theo yêu cầu. Ô soạn không bung bảng dữ kiện nào.
const viec: string[] = [];
const hanhDong = {
  onXemBanTaiLen: (t: { id: string; ten_tep: string; so_trang: number | null }) =>
    viec.push(`xem:${t.id}:${t.ten_tep}:${t.so_trang}`),
  onDienBieuMau: (id: string) => viec.push(`dien:${id}`),
  onDuKien: (id: string) => viec.push(`du-kien:${id}`),
};
const boDi: string[] = [];
const { khung: khungSoan, root: rootSoan } = taoRoot();
await act(() => {
  rootSoan.render(
    h(OSoanCauHoi, {
      oHoi: { current: null },
      nhap: "",
      datNhap: () => {},
      khoa: false,
      onGui: () => {},
      mucChip: null,
      dangCho: false,
      onChonTep: () => {},
      tepDaDinhKem: [
        { id: VIEC, ten_tep: "BM.M05.docx", co_khuon_goc: true, so_trang: 2 },
        { id: VIEC_CU, ten_tep: "cu.pdf" },
      ],
      hanhDongTep: hanhDong,
      onBoDinhKem: (id: string) => boDi.push(id),
    }),
  );
});
assert.doesNotMatch(
  khungSoan.textContent,
  /Đọc dữ kiện|Đã đọc \d+ đơn vị/,
  "đính kèm không bung bảng dữ kiện, không đếm đơn vị",
);
const chip = (ten: string) =>
  tim(khungSoan, (n) => n.getAttribute("aria-label") === `Tài liệu ${ten}`)!;
const menu = () => tim(khungSoan, (n) => n.getAttribute("role") === "menu");
const mucMenu = () => timTatNut(menu()!, (n) => n.getAttribute("role") === "menuitem");
assert.equal(chip("BM.M05.docx").getAttribute("aria-haspopup"), "menu");
cungNut(menu(), null, "menu đóng cho tới khi bấm");
await act(() => phat(chip("BM.M05.docx"), "click"));
assert.equal(chip("BM.M05.docx").getAttribute("aria-expanded"), "true");
assert.deepEqual(
  mucMenu().map((n) => n.textContent),
  ["Xem bản tải lên", "Điền biểu mẫu", "Dữ kiện đã đọc"],
  "có khuôn gốc: đủ ba việc",
);
cungNut(document.activeElement, mucMenu()[0], "mở menu: tiêu điểm vào mục đầu");
await act(() => phat(mucMenu()[2]!, "click"));
cungNut(menu(), null, "chọn xong: menu đóng");
cungNut(document.activeElement, chip("BM.M05.docx"), "tiêu điểm về con chip (nơi mở)");
await act(() => phat(chip("BM.M05.docx"), "click"));
await act(() => phat(mucMenu()[0]!, "click"));
await act(() => phat(chip("BM.M05.docx"), "click"));
await act(() => phat(mucMenu()[1]!, "click"));
assert.deepEqual(viec, [`du-kien:${VIEC}`, `xem:${VIEC}:BM.M05.docx:2`, `dien:${VIEC}`]);
await act(() => phat(chip("BM.M05.docx"), "click"));
await act(() => phat(mucMenu()[0]!, "keydown", { key: "Escape" }));
cungNut(menu(), null, "Esc đóng menu");
cungNut(document.activeElement, chip("BM.M05.docx"), "Esc: tiêu điểm về con chip");
await act(() => phat(chip("cu.pdf"), "click"));
assert.deepEqual(
  mucMenu().map((n) => n.textContent),
  ["Dữ kiện đã đọc"],
  "chưa biết có khuôn gốc: chỉ 'Dữ kiện đã đọc'",
);
await act(() => phat(khungSoan, "mousedown"));
cungNut(menu(), null, "bấm ra ngoài: menu đóng");
await act(() =>
  phat(
    tim(khungSoan, (n) => n.getAttribute("aria-label") === "Bỏ đính kèm cu.pdf")!,
    "click",
  ),
);
assert.deepEqual(boDi, [VIEC_CU], "nút bỏ đính kèm giữ nguyên");
// Tải tệp bị từ chối: câu của máy chủ (tên tệp, số trang thật) ở lại cạnh chỗ
// đính kèm sau khi toast tắt — nơi gọi giữ nó tới lần tải kế tiếp.
const CAU_TU_CHOI = "Tệp “BM dài.docx” có 11 trang — KLAW nhận tối đa 10 trang.";
const propsSoan = {
  oHoi: { current: null },
  nhap: "",
  datNhap: () => {},
  khoa: false,
  onGui: () => {},
  mucChip: null,
  dangCho: false,
  onChonTep: () => {},
  hanhDongTep: hanhDong,
};
const { khung: khungTuChoi, root: rootTuChoi } = taoRoot();
await act(() => rootTuChoi.render(h(OSoanCauHoi, { ...propsSoan, loiTaiLen: CAU_TU_CHOI })));
assert.ok(
  tim(khungTuChoi, (n) => n.tagName === "P" && n.textContent === CAU_TU_CHOI) !== null,
  "câu từ chối đứng cạnh chỗ đính kèm",
);
await act(() => rootTuChoi.render(h(OSoanCauHoi, { ...propsSoan, loiTaiLen: null })));
assert.doesNotMatch(khungTuChoi.textContent, /11 trang/, "lần tải kế: câu cũ đi");
// Chip trên lượt đã gửi: cùng menu, KHÔNG có nút bỏ.
const { khung: khungChip, root: rootChip } = taoRoot();
await act(() => {
  rootChip.render(
    h(ChipTaiLieu, {
      tep: { id: VIEC, ten_tep: "BM.M05.docx", co_khuon_goc: true, so_trang: 2 },
      hanhDong,
      moLen: false,
    }),
  );
});
cungNut(
  tim(khungChip, (n) => /^Bỏ đính kèm/.test(n.getAttribute("aria-label") ?? "")),
  null,
  "lượt đã gửi: không bỏ đính kèm được",
);

// (j) Lượt dựng bản thảo trên khuôn gốc: chat hiện LỜI ĐÁP (đã điền gì, còn
// trống chỗ nào) và thẻ nói "Biểu mẫu · n trang · đã điền k chỗ"; bản thảo
// HTML giữ nguyên thẻ cũ.
const LOI_KHUON =
  "Bản thảo phiên bản 2 là chính biểu mẫu bạn tải lên: đã điền 2/3 chỗ trống. Còn trống: «chỗ trống».";
const ketQuaBanThao = (bt: BanThao) =>
  ({
    result_type: "ban_thao",
    answer: LOI_KHUON,
    citations: [],
    nguon: [],
    warnings: [],
    coverage_note: "Không áp 1 thay đổi (thiếu nguồn hoặc sai chỗ): «Email».",
    trace_id: "t-bt",
    cau_hoi_day_du: null,
    bang: [],
    documents: [],
    ban_thao: bt,
  }) as unknown as Parameters<typeof TheKetQua>[0]["ketQua"];
const { khung: khungTraLoi, root: rootTraLoi } = taoRoot();
await act(() => {
  rootTraLoi.render(
    h(TheKetQua, {
      ketQua: ketQuaBanThao({ ...banThaoKhuon, phien_ban: 2, doi_so_voi_truoc: ["a", "b"] }),
    }),
  );
});
assert.match(khungTraLoi.textContent, /đã điền 2\/3 chỗ trống/, "lời đáp khuôn gốc hiện ra");
assert.match(khungTraLoi.textContent, /Không áp 1 thay đổi/, "và thay đổi không áp được");
assert.match(khungTraLoi.textContent, /Biểu mẫu · 2 trang · đã điền 1 chỗ/);
assert.doesNotMatch(khungTraLoi.textContent, /dữ kiện|\d+ mục/, "không '… dữ kiện · 0 mục'");
await act(() => {
  rootTraLoi.render(h(TheKetQua, { ketQua: ketQuaBanThao({ ...banThao, phien_ban: 2 }) }));
});
assert.doesNotMatch(khungTraLoi.textContent, /đã điền 2\/3/, "bản thảo HTML: thẻ như cũ");
assert.match(khungTraLoi.textContent, /Phiên bản 2 · 0 mục/);

// ───── 12. SÂN KHẤU: mở bản khác lúc đang mở, "Phiên mới" đi qua cửa đóng ───
// `dung-thu.tsx` không dựng được trong khung giả này (router, tài khoản, vỏ ứng
// dụng), nên các quyết định của nó là hàm thuần `lib/san-khau.ts` — kiểm ở đây
// — và phần nối dây kiểm trên chính nguồn: MỘT cửa đóng, mọi lối vào đi qua nó.
const { apNeuCungBan, dongKhiDoiPhien, thamSoSanKhau, urlCoBanThao, urlTroBanKhac, vanNham } =
  await nap<typeof import("../src/lib/san-khau.ts")>("src/lib/san-khau.ts");
{
  const BT = { loai: "ban_thao", banThaoId: "x" } as const;
  const BTL = { loai: "ban_tai_len", viecId: "v", tenTep: "t", soTrang: 1 } as const;
  assert.equal(
    dongKhiDoiPhien(undefined, BT),
    true,
    "chọn cuộc trò chuyện khác ở vỏ trang (`?phien=B`, không `?ban_thao=`): bản thảo của cuộc cũ đóng",
  );
  assert.equal(dongKhiDoiPhien(undefined, BTL), true, "'Bản tải lên' của cuộc cũ cũng đóng");
  assert.equal(
    dongKhiDoiPhien("y", BT),
    false,
    "URL mới mang `?ban_thao=` (danh sách 'Bản thảo' của vỏ trang): lối mở qua URL lo, không đóng",
  );
  assert.equal(dongKhiDoiPhien(undefined, null), false, "sân khấu đã đóng: không điều hướng thêm");
}
assert.deepEqual(
  thamSoSanKhau(undefined, "p", "b"),
  { phien: "p", ban_thao: "b" },
  "mở (thẻ trong chat) hay chuyển sang bản b: `?ban_thao=` là b — tải lại mở lại đúng b",
);
assert.deepEqual(
  thamSoSanKhau("x", "p", null),
  { q: "x", phien: "p" },
  "đóng: gỡ `?ban_thao=`, giữ `?q=`/`?phien=`",
);
assert.equal(
  urlCoBanThao(undefined, { loai: "ban_thao", banThaoId: "b" }),
  true,
  "mở từ thẻ rồi `layBanThao` hỏng về muộn: closure cũ chưa thấy `?ban_thao=` vừa ghi, vẫn gỡ",
);
assert.equal(urlCoBanThao("a", null), true);
assert.equal(
  urlCoBanThao(undefined, { loai: "ban_tai_len", viecId: "a", tenTep: "x", soTrang: 1 }),
  false,
  "'Bản tải lên' không ghi URL: đóng không điều hướng",
);
assert.equal(urlCoBanThao(undefined, null), false);
assert.equal(vanNham({ loai: "ban_thao", banThaoId: "a" }, "a"), true);
assert.equal(
  vanNham({ loai: "ban_thao", banThaoId: "b" }, "a"),
  false,
  "đã chuyển sang bản b: phản hồi của bản a về muộn bị bỏ, sân khấu không kẹt ở 'Đang mở'",
);
assert.equal(vanNham(null, "a"), false, "đã đóng: lỗi về muộn của bản a không đóng gì thêm");
assert.equal(vanNham({ loai: "ban_tai_len", viecId: "a", tenTep: "x", soTrang: 1 }, "a"), false);
assert.equal(urlTroBanKhac("a", "b"), true, "URL còn bản a, bấm mở bản b: gỡ URL cũ");
assert.equal(urlTroBanKhac("b", "b"), false, "mở ĐÚNG bản trên URL (vỏ trang, tải lại): giữ");
assert.equal(urlTroBanKhac(undefined, "b"), false);
{
  const a1 = { id: "a", v: 1 };
  const a2 = { id: "a", v: 2 };
  const b1 = { id: "b", v: 1 };
  assert.equal(apNeuCungBan(a1, a2), a2, "cùng bản: nhận phiên bản mới");
  assert.equal(apNeuCungBan(b1, a2), b1, "lượt lưu về muộn của bản a không thay bản b đang mở");
  assert.equal(apNeuCungBan(null, a2), null, "sân khấu đã đóng: không mở lại");
}
{
  const NGUON = readFileSync(join(goc, "src/routes/dung-thu.tsx"), "utf8");
  /** Thân của `const ten = …` tới dấu đóng khối đầu tiên ở đúng thụt lề đó. */
  const than = (ten: string) => {
    const i = NGUON.indexOf(`  const ${ten} = `);
    assert.ok(i >= 0, `không thấy \`${ten}\` trong dung-thu.tsx`);
    const j = NGUON.indexOf("\n  }", i);
    return NGUON.slice(i, j);
  };
  // Câu lệnh (có `;`), không phải chú thích nhắc tên nó.
  assert.equal(NGUON.split("datSanKhau(null);").length - 1, 1, "đóng sân khấu ở ĐÚNG một chỗ");
  assert.match(than("onDongSanKhau"), /datSanKhau\(null\)/, "chỗ đó là cửa đóng `onDongSanKhau`");
  assert.match(than("phienMoi"), /onDongSanKhau\(\)/, "'Phiên mới' đóng sân khấu qua cửa đóng");
  {
    // Hiệu ứng đổi phiên (MỌI lối: vỏ trang, "Phiên mới", URL) đóng sân khấu
    // qua cửa đóng, sau hai lối ra sớm (cùng phiên; phiên vừa `bat_dau`).
    const i = NGUON.indexOf("phienDangHien.current = phienId;");
    assert.ok(i >= 0, "không thấy hiệu ứng đổi phiên");
    assert.match(
      NGUON.slice(i, NGUON.indexOf("\n  }, [", i)),
      /return;\s*if \(dongKhiDoiPhien\(banThaoTrenUrl, sanKhauRef\.current\)\) onDongSanKhau\(\);/,
      "đổi phiên: sân khấu của cuộc cũ đóng qua `onDongSanKhau`",
    );
  }
  // Mốc cuộn cuối chat nằm SAU ô soạn (sticky bottom-0): cuộn tới nó là tới đáy
  // thật, ô soạn về chỗ tĩnh và không đè lên thẻ cuối — nút "Mở bản thảo" của
  // lượt vừa xong từng nằm dưới ô soạn, một cú bấm vào tâm nút rơi vào ô soạn.
  assert.ok(
    NGUON.indexOf("<OSoanCauHoi") > 0 &&
      NGUON.indexOf("ref={cuoi}") > NGUON.indexOf("<OSoanCauHoi"),
    "mốc cuộn `cuoi` đứng sau `<OSoanCauHoi`",
  );
  assert.match(
    than("moSanKhau"),
    /if \(urlTroBanKhac\(banThaoTrenUrl, id\)\) onDongSanKhau\(\);/,
    "mở bản khác: `?ban_thao=` cũ rời URL qua cửa đóng",
  );
  assert.match(
    than("moSanKhau"),
    /if \(!vanNham\(sanKhauRef\.current, id\)\) return;/,
    "mở bản khác: phản hồi của bản cũ về muộn không đè bản mới",
  );
  assert.match(
    than("moSanKhau"),
    /if \(banThaoTrenUrl !== id\) \{\s*daMoTuUrl\.current = id;[^\n]*\s*void navigate\(\{\s*to: "\/dung-thu",\s*search: thamSoSanKhau\(cauHoiTrenUrl, phienId, id\),\s*replace: true,/,
    "mọi lối mở ghi `?ban_thao=` của bản đang mở (không thêm mục lịch sử), và hiệu ứng đọc URL không mở nó lần hai",
  );
  assert.match(
    than("onDongSanKhau"),
    /if \(urlCoBanThao\(banThaoTrenUrl, sanKhauRef\.current\)\) \{\s*void navigate\(\{\s*to: "\/dung-thu",\s*search: thamSoSanKhau\(cauHoiTrenUrl, phienId, null\),/,
    "cửa đóng gỡ `?ban_thao=` cả khi closure chưa thấy nó (mở từ thẻ, lỗi về muộn)",
  );
  assert.match(
    than("moBanTaiLen"),
    /onDongSanKhau\(\)/,
    "'Xem bản tải lên' của tệp khác chuyển sân khấu",
  );
  assert.match(
    NGUON,
    /capNhatBanThao=\{capNhatBanThaoMo\}/,
    "sân khấu cập nhật qua `apNeuCungBan`",
  );
  assert.match(NGUON, /key=\{banThaoDangTaiXong\.id\}/, "bản thảo khác = sân khấu mới");
}

// ───── 13. "Bản thảo" của vỏ trang theo kịp phiên bản (lưu, lùi, lượt chat) ──
// Owner thấy "Phiên bản 1" đứng lì sau khi lưu trên trang đã lên v2/v3.
{
  type DoThi = typeof import("../src/components/klaw/DanhSachPhien.tsx") &
    typeof import("../src/lib/api.ts");
  const { DanhSachBanThaoGanDay, luiBanThao, moBanThaoKhuon, suaODien, traCuuLuong } = (
    await runnerImport<DoThi>("kiem:ban-thao-gan-day", cauHinhVite)
  ).module;
  const tomTat = (id: string, phien_ban: number) => ({
    id,
    loai: "tong_quat",
    ten: `Bản ${id}`,
    phien_ban,
    cap_nhat_luc: new Date(Date.now() - 3_600_000).toISOString(),
    hoi_thoai_id: null,
  });
  let dsMayChu = [tomTat("bk", 1)];
  let soGoiDs = 0;
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    const u = String(url).replace(apiGoc(), "");
    if (u.startsWith("/ban-thao?")) {
      soGoiDs += 1;
      return traJson({ tong: dsMayChu.length, items: dsMayChu });
    }
    if (init?.method === "PATCH") return traJson({ ...banThaoKhuon, phien_ban: 3 });
    if (u === "/ban-thao/bk/lui") return traJson({ ...banThaoKhuon, phien_ban: 2 });
    if (u === "/tai-lieu/v-moi/ban-thao") return traJson({ ...banThaoKhuon, id: "moi" }, 201);
    if (u === "/tra-cuu/luong")
      return new Response(
        `event: ket_qua\ndata: ${JSON.stringify(ketQuaBanThao({ ...banThaoKhuon, phien_ban: 4 }))}\n\n`,
      );
    return traJson({ detail: "không có" }, 404);
  }) as typeof fetch;
  const { khung: khungDs, root: rootDs } = taoRoot();
  await act(() => rootDs.render(h(DanhSachBanThaoGanDay, { onMo: () => {} })));
  await choDen(() => /Phiên bản 1/.test(khungDs.textContent));
  assert.match(khungDs.textContent, /Phiên bản 1 · 1 giờ trước/);
  await act(async () => {
    await suaODien("bk", 1, [{ don_vi: 0, cho_trong: 0, gia_tri: "x" }]);
  });
  assert.match(khungDs.textContent, /Phiên bản 3 · vừa xong/, "lưu một chỗ trống trên trang: v3");
  await act(async () => {
    await luiBanThao("bk");
  });
  assert.match(khungDs.textContent, /Phiên bản 2/, "Lùi: v2");
  await act(async () => {
    await traCuuLuong({ query: "điền giúp tôi" });
  });
  assert.match(khungDs.textContent, /Phiên bản 4/, "lượt chat ra phiên bản mới: v4");
  assert.equal(soGoiDs, 1, "vá tại chỗ: không gọi lại `GET /ban-thao` (giỏ nhịp theo IP)");
  dsMayChu = [tomTat("moi", 1), tomTat("bk", 4)];
  await act(async () => {
    await moBanThaoKhuon("v-moi");
  });
  await choDen(() => /Bản moi/.test(khungDs.textContent));
  assert.equal(soGoiDs, 2, "bản vừa tạo (chưa có trong danh sách): tải lại đúng một lần");
  await act(() => rootDs.unmount());
}

console.log("kiem-ui-muot: OK");
