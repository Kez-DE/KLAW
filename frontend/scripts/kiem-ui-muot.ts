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

console.log("kiem-ui-muot: 128/128 OK");
