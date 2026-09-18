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
Object.assign(globalThis, { document, window, IS_REACT_ACT_ENVIRONMENT: true });

// `react-dom` chốt `canUseDOM` NGAY lúc nạp module, nên phải nạp SAU khi đã
// dựng `window`/`document` giả ở trên — vì thế mới dùng `import()` động.
const { act, createElement: h } = await import("react");
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
    canCu: null,
    khoi: [
      { kind: "vanXuoi", noiDung: CHU_GOC, canhLe: "trai", chu: [] },
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
  onLui: () => {},
  onDong: () => {},
  onPhimTat: () => {},
  toanMan: false,
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

console.log("kiem-ui-muot: 44/44 OK");
