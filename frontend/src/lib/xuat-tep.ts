/**
 * Xuất bản thảo hợp đồng ra tệp thật (.docx / .pdf) từ khung xem trước A4.
 * Toàn bộ xử lý diễn ra trên trình duyệt — không gửi nội dung bản thảo lên máy chủ.
 */
import type { BanThao, CauTruc } from "./klaw";

export type KieuDong = "quocHieu" | "tieuDe" | "soHieu" | "dieu" | "thuong";

export type DongVanBan = {
  text: string;
  kieu: KieuDong;
  canhGiua: boolean;
  inDam: boolean;
  inNghieng: boolean;
  thutLe: number;
};

/**
 * Một khối nội dung theo ĐÚNG thứ tự xuất hiện trong khung A4 — hoặc một
 * đoạn/tiêu đề (`dong`), hoặc một bảng thật (`bang`, Phase 7 R3: hàng×ô nguyên
 * văn, hàng đầu là tiêu đề). Union thay vì hai mảng song song vì thứ tự CHUNG
 * giữa đoạn văn và bảng mới là thứ `xuatWord` cần để không đẩy một bảng giữa
 * tài liệu (như bảng đánh giá) xuống cuối, như `oKy` cố ý làm cho khối ký.
 */
export type KhoiVanBan = { kind: "dong"; d: DongVanBan } | { kind: "bang"; hang: string[][] };

export type NoiDungXuat = {
  khoi: KhoiVanBan[];
  /**
   * Các cột của khối ký. MỘT cột là hợp lệ, không phải hai.
   *
   * Trước đây `xuatWord` chỉ dựng bảng ký khi `oKy.length === 2`, vì bộ dựng
   * thân văn bản cũ luôn ra đúng hai bên. Nay khối ký chỉ hiện khi chính
   * `cau_truc` có mục chữ ký, và với công văn hay đơn khiếu nại thì mục ấy có
   * MỘT người ký. Giữ điều kiện `=== 2` sẽ nuốt trọn khối ký ra khỏi tệp `.docx`
   * người dùng tải về, mà trên màn hình vẫn thấy nó.
   */
  oKy: DongVanBan[][];
};

/**
 * MỘT khối nội dung của một mục, theo ĐÚNG thứ tự tài liệu (Phase 8 R1 —
 * thay "một mục là văn xuôi HOẶC bảng" của Phase 7: giờ một mục là một MẢNG
 * khối, ví dụ câu dẫn / bảng / câu kết, ba khối riêng chứ không nén về hai
 * trường cố định).
 */
export type KhoiMuc = { kind: "vanXuoi"; noiDung: string } | { kind: "bang"; hang: string[][] };

/** Một mục dựng sẵn cho `XemTruocA4`: nội dung của `clauses` ghép vào khung `cau_truc.muc`. */
export interface Muc {
  stt: number;
  key: string;
  ten: string;
  /**
   * Giữ lại CHỈ cho `DrawerSuaMuc` (bản thảo checklist — không bao giờ có
   * `khoi`/`bang`, xem `SanKhauBanThao.laTongQuat`) và cho tương thích ngược
   * với mã đã đọc hai trường này trước Phase 8. `XemTruocA4` (bản thảo tổng
   * quát) không đọc hai trường này nữa — nó render `khoi` bên dưới.
   */
  noiDung: string;
  /** @deprecated dùng `khoi` — giữ vì lý do tương thích nêu trên. */
  bang: string[][] | null;
  /**
   * Nội dung mục theo ĐÚNG THỨ TỰ khối (Phase 8 R1) — nguồn RENDER chính của
   * `XemTruocA4`. Quy về ĐÚNG MỘT hình dạng dù `clauses[i]` mang khoá `khoi`
   * (Phase 8), `noi_dung`+`bang` rời (Phase 7), hay chỉ `noi_dung` (trước cả
   * hai) — ba hình dạng đó là BA THỜI ĐIỂM khác nhau của cùng cột JSONB
   * `ban_thao.clauses`, không migration nào viết lại hàng cũ (xem
   * `khoiTuClause`).
   */
  khoi: KhoiMuc[];
  /**
   * `DonViVanBan.vung` mang qua (Phase 8 R2) — `than` (thân bài, mặc định),
   * `dau_trang`/`chan_trang` khi mục lấy từ đầu/chân trang thật của tài
   * liệu nguồn. Chỉ mô tả, `XemTruocA4` không render khác đi theo trường
   * này — skipped: kiểu dáng riêng cho đầu/chân trang, thêm khi đo thấy một
   * bản dựng lại trông sai nếu thiếu nó.
   */
  vung: "than" | "dau_trang" | "chan_trang";
  canCu: string | null;
}

/**
 * Hình dạng THẬT của một phần tử `BanThao.clauses` (kiểu `unknown[]` chưa gõ ở FE) —
 * khớp `dataclasses.asdict(DraftClause)` (`src/agents/nodes/draft_generate.py` +
 * `src/services/ban_thao.py` dòng ghi `clauses`): `key`, `ten`, `noi_dung`,
 * `can_cu_provision_id`. KHÔNG có trường `text` — chỉ `noi_dung` mang nội dung.
 * `bang` (Phase 7) và `khoi`/`vung` (Phase 8) chỉ có ở `clauses` do
 * `dung_ban_thao_tong_quat.clauses_tu` dựng — BA hình dạng cùng một cột JSONB,
 * từ ba thời điểm khác nhau, không migration nào viết lại hàng cũ.
 */
type ClauseTho = {
  key?: string;
  ten?: string;
  noi_dung?: string;
  bang?: unknown;
  khoi?: unknown;
  vung?: unknown;
};

/** `c.bang` thô (kiểu chưa biết, tới từ `unknown[]`) → hàng×ô hợp lệ, hoặc
 * `null` khi rỗng/vắng/sai hình dạng — một mục cũ không có khoá này phải rơi
 * đúng vào nhánh văn xuôi, không phải một bảng 0 hàng. Hàng NGẮN hơn hàng đầu
 * (Phase 8 R4, ô gộp trong tài liệu nguồn) đi qua NGUYÊN — đây chỉ gõ kiểu,
 * không đệm/cắt; `coSpanHang` mới quyết định cách VẼ một hàng ngắn. */
function bangHopLe(bang: unknown): string[][] | null {
  if (!Array.isArray(bang) || bang.length === 0) return null;
  return bang.map((hang) => (Array.isArray(hang) ? hang.map((o) => String(o)) : []));
}

const VUNG_HOP_LE = new Set(["than", "dau_trang", "chan_trang"]);

/** `c.vung` thô → nhãn hợp lệ, mặc định `than` khi vắng/lạ (Phase 8 R2) —
 * cùng luật fail-closed với `lam_sach_van_ban` phía máy chủ. */
function vungHopLe(vung: unknown): Muc["vung"] {
  return typeof vung === "string" && VUNG_HOP_LE.has(vung) ? (vung as Muc["vung"]) : "than";
}

/**
 * MỘT khối thô (từ `khoi` mới, Phase 8) → 0, 1, hay 2 `KhoiMuc` hợp lệ, ĐÚNG
 * thứ tự văn xuôi rồi bảng.
 *
 * Trả MẢNG, không một giá trị: rule 15 XIN mô hình để mỗi khối MỘT trong hai
 * (`noi_dung` HOẶC `bang`), nhưng schema strict không ép được điều đó — một
 * khối vẫn có thể tới đây với CẢ HAI khác rỗng. Review round 1 [IMPORTANT]:
 * bản trước của hàm này ưu tiên `bang` (bỏ `noi_dung`), trong khi
 * `dung_ban_thao_tong_quat._khoi_thanh_van_ban` phía máy chủ lại ưu tiên
 * NGƯỢC LẠI — chứng tỏ luật "một khối một loại" chưa từng được ép, chỉ được
 * TIN, và hai phía đọc cùng một dữ liệu ra hai kết quả khác nhau. Trả CẢ HAI
 * làm hai khối riêng (văn xuôi trước) xoá luôn nhu cầu chọn ưu tiên — đúng
 * cách Phase 7 R1 fix round 1 đã sửa lỗi này một lần ở cấp MỤC.
 */
function khoiMotHopLe(k: unknown): KhoiMuc[] {
  if (typeof k !== "object" || k === null) return [];
  const o = k as { noi_dung?: unknown; bang?: unknown };
  const noiDung = typeof o.noi_dung === "string" ? o.noi_dung : "";
  const bang = bangHopLe(o.bang);
  const ra: KhoiMuc[] = [];
  if (noiDung !== "") ra.push({ kind: "vanXuoi", noiDung });
  if (bang) ra.push({ kind: "bang", hang: bang });
  return ra;
}

/**
 * `clauses[i]` → `KhoiMuc[]` theo ĐÚNG thứ tự — chỗ DUY NHẤT phải biết cả BA
 * hình dạng `clauses` từng có (Phase 8 `khoi`; Phase 7 `noi_dung`+`bang` rời;
 * trước đó chỉ `noi_dung`, hoặc không có clause nào cho mục này). Mọi nơi
 * khác (`XemTruocA4`, `docNoiDungTuDOM`) chỉ đọc `Muc.khoi` đã quy về một
 * hình dạng, không phải tự phân biệt phiên bản dữ liệu.
 */
function khoiTuClause(c: ClauseTho | undefined): KhoiMuc[] {
  if (Array.isArray(c?.khoi)) {
    return c.khoi.flatMap(khoiMotHopLe);
  }
  // Phase 7 trở về trước: câu dẫn (nếu có) RỒI bảng (nếu có) — đúng thứ tự
  // `XemTruocA4` từng render (fix round 1, Phase 7) trước khi có `khoi`.
  const bang = bangHopLe(c?.bang);
  const noiDung = c?.noi_dung ?? (bang ? "" : "[…]");
  const ra: KhoiMuc[] = [];
  if (noiDung !== "") ra.push({ kind: "vanXuoi", noiDung });
  if (bang) ra.push({ kind: "bang", hang: bang });
  return ra;
}

/**
 * Ghép `clauses` (nội dung LLM sinh, từ `draft_generate`) vào khung `cau_truc.muc` (thứ
 * tự và căn cứ, từ chính `checklist_*.yaml`) thành mảng `Muc[]` cho `XemTruocA4`.
 *
 * Khung quyết định thứ tự mục và `canCu`; `clauses` chỉ góp `noiDung`. Mục nào khung có
 * mà `clauses` chưa sinh (model bỏ sót, hoặc đang chờ) thì hiện "[…]" — không suy đoán
 * nội dung để lấp chỗ trống.
 */
export function mucTuBanThao(banThao: BanThao, cauTruc: CauTruc | null): Muc[] {
  const clauses = banThao.clauses as ClauseTho[];
  const theoKey = new Map<string, ClauseTho>();
  for (const c of clauses) if (c.key) theoKey.set(c.key, c);

  const khung = cauTruc?.muc ?? [];
  if (khung.length === 0) {
    // Chưa có `cau_truc` (chưa tải xong, hoặc loại văn bản chưa có checklist) — dựng
    // tạm theo đúng thứ tự `clauses`, không có `canCu` vì khung mới là nguồn của nó.
    return clauses.map((c, i) => ({
      stt: i + 1,
      key: c.key ?? `m${i + 1}`,
      ten: c.ten ?? c.key ?? `Mục ${i + 1}`,
      noiDung: c.noi_dung ?? "[…]",
      bang: bangHopLe(c.bang),
      khoi: khoiTuClause(c),
      vung: vungHopLe(c.vung),
      canCu: null,
    }));
  }
  return khung.map((m) => {
    const c = theoKey.get(m.key);
    return {
      stt: m.stt,
      key: m.key,
      ten: m.ten,
      noiDung: c?.noi_dung ?? "[…]",
      bang: bangHopLe(c?.bang),
      khoi: khoiTuClause(c),
      vung: vungHopLe(c?.vung),
      canCu: m.can_cu || null,
    };
  });
}

/**
 * Tiêu đề THẬT của bản thảo — dòng H1 đầu tiên trong `document` (Markdown),
 * đúng cách `ban_thao._render_markdown` dựng từ `tieu_de` mô hình soạn (Phase
 * 7 R4). `BanThao.ten` KHÔNG mang tiêu đề này: nó trả lời "bản thảo này THUỘC
 * LOẠI gì" ("Bản thảo tổng quát"), một câu hỏi khác — trộn hai trường đó là
 * đúng lỗi đã sửa ở `dung_ban_thao_tong_quat.py`.
 */
export function tieuDeTuBanThao(document: string): string | null {
  const dong = document.split("\n")[0] ?? "";
  const m = /^#\s+(.+)$/.exec(dong.trim());
  return m?.[1]?.trim() ?? null;
}

const BO_QUA = new Set(["SCRIPT", "STYLE"]);

/**
 * Phần tử KHÔNG được vào tệp tải về: thẻ kỹ thuật, và mọi thứ nằm trong một
 * khối đánh dấu `data-khong-xuat`.
 *
 * Cần cái thứ hai vì khung xem trước có những dòng chỉ dành cho MÀN HÌNH —
 * dòng `Căn cứ:` bật/tắt bằng công tắc "Hiển thị căn cứ" là một `<p>` như mọi
 * đoạn khác, nên nếu không đánh dấu thì một công tắc xem trước lại đổi nội
 * dung văn bản pháp lý người dùng tải về.
 */
export function boQuaKhiXuat(el: { tagName: string; closest(chon: string): unknown }): boolean {
  return BO_QUA.has(el.tagName) || el.closest("[data-khong-xuat]") !== null;
}

function chuanHoa(s: string) {
  return s.replace(/\s+/g, " ").trim();
}

function laCanhGiua(el: HTMLElement) {
  return getComputedStyle(el).textAlign === "center";
}

/**
 * Đọc MỘT bảng đã render thành hàng×ô, nguyên văn từng ô (đã chuẩn hoá khoảng
 * trắng) — hàng đầu tiên là hàng tiêu đề, đúng quy ước `bang` phía máy chủ
 * (`hieu_tai_lieu.schema_hieu`, Phase 7 R1); không cần phân biệt `<th>`/`<td>`.
 *
 * Chữ ký hàm chỉ đòi `querySelectorAll`/`textContent` — KHÔNG `getComputedStyle`
 * như `docDong` — nên gọi được với một đối tượng giả tối thiểu, không cần DOM
 * thật (kiểm bằng `kiem-xuat-tep.ts`, không có `jsdom` trong repo này).
 */
export function docBangTuPhanTu(bang: {
  querySelectorAll(sel: string): ArrayLike<{
    querySelectorAll(sel: string): ArrayLike<{ textContent: string | null }>;
  }>;
}): string[][] {
  return Array.from(bang.querySelectorAll("tr")).map((hang) =>
    Array.from(hang.querySelectorAll("th, td")).map((o) => chuanHoa(o.textContent ?? "")),
  );
}

/** Đọc một thẻ thành dòng có định dạng, lấy đậm/nghiêng từ chính CSS đang áp. */
function docDong(el: HTMLElement): DongVanBan {
  const text = chuanHoa(el.textContent ?? "");
  const cs = getComputedStyle(el);
  const laDieu = el.classList.contains("dieu-head");
  return {
    text: cs.textTransform === "uppercase" ? text.toLocaleUpperCase("vi-VN") : text,
    kieu:
      el.tagName === "H1" ? "tieuDe" : laDieu ? "dieu" : /^Số:/.test(text) ? "soHieu" : "thuong",
    canhGiua: laCanhGiua(el),
    inDam: Number(cs.fontWeight) >= 600 || laDieu,
    inNghieng: cs.fontStyle === "italic",
    thutLe: Math.round(parseFloat(cs.marginLeft || "0")),
  };
}

/** Đọc nội dung hiển thị của khung A4 thành danh sách dòng có định dạng. */
export function docNoiDungTuDOM(sheet: HTMLElement): NoiDungXuat {
  const khoi: KhoiVanBan[] = [];
  const oKy: DongVanBan[][] = [];

  /**
   * Khối ký chỉ tách ra thành BẢNG khi nó thật sự có hai cột cạnh nhau.
   *
   * Bảng ấy được ghép vào CUỐI tệp, nên tách một khối ký MỘT cột ra là đẩy nó
   * xuống dưới cùng: công văn có chữ ký ở Thành phần 7 trên màn hình lại ký sau
   * Thành phần 9 trong tệp `.docx` tải về. Một cột thì để nó chảy theo đúng thứ
   * tự văn bản như mọi đoạn khác.
   */
  const khoiHaiCot = sheet.querySelector<HTMLElement>('[data-xuat="ky"]');
  const khoiKy = khoiHaiCot && khoiHaiCot.children.length >= 2 ? khoiHaiCot : null;
  if (khoiKy) {
    for (const cot of Array.from(khoiKy.children) as HTMLElement[]) {
      const dongCot = Array.from(cot.querySelectorAll("p"))
        .filter((el) => !boQuaKhiXuat(el))
        .map(docDong)
        .filter((d) => d.text !== "");
      if (dongCot.length > 0) oKy.push(dongCot);
    }
  }

  // Một truy vấn CHUNG cho cả ba thẻ giữ đúng THỨ TỰ xuất hiện trong tài liệu
  // (`querySelectorAll` luôn trả theo thứ tự DOM, bất kể nhóm nào trong bộ
  // chọn khớp) — một bảng đứng giữa hai đoạn văn (như bảng đánh giá) phải ở
  // ĐÚNG chỗ đó trong tệp `.docx`, không bị dồn hết xuống cuối như `oKy`.
  const blocks = sheet.querySelectorAll<HTMLElement>("h1, p, table");
  for (const el of Array.from(blocks)) {
    if (boQuaKhiXuat(el)) continue;
    if (khoiKy && khoiKy.contains(el)) continue;
    if (el.tagName === "TABLE") {
      const hang = docBangTuPhanTu(el);
      if (hang.length > 0) khoi.push({ kind: "bang", hang });
      continue;
    }
    const d = docDong(el);
    if (d.text === "") continue;
    khoi.push({ kind: "dong", d });
  }

  return { khoi, oKy };
}

export function tenTepAnToan(ten: string) {
  const slug = ten
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/gi, "d")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${slug || "van-ban"}-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}`;
}

function taiBlob(blob: Blob, tenTep: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = tenTep;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/**
 * Số cột mỗi ô của một hàng phải chiếm, khi hàng đó NGẮN hơn hàng tiêu đề
 * (Phase 8 R4 — tài liệu nguồn dùng Ô GỘP, ví dụ hàng "Tổng | 10" chỉ có 2 ô
 * thật trong khi hàng tiêu đề có 4). Quyết định biểu diễn: hàng vẫn lưu ĐÚNG
 * số ô thật (`bang`/`hang` không đệm rỗng, xem `_bang_sach` phía máy chủ);
 * hàm này chỉ quyết định cách VẼ nó, theo MỘT quy ước cố định — ô CUỐI luôn ở
 * CỘT CUỐI của bảng (không bao giờ trôi sang trái, "10" không lẫn sang cột
 * khác), ô ngay TRƯỚC nó gánh phần cột còn thiếu bằng colSpan, các ô còn lại
 * giữ nguyên 1 cột. Đúng cách một nhãn gộp ("Tổng") đứng ngay trước ô giá trị
 * trong một biểu mẫu thật; hàng đủ cột (`soO >= soCotTieuDe`) không đổi gì.
 */
export function coSpanHang(soO: number, soCotTieuDe: number): number[] {
  if (soO <= 0) return [];
  if (soO >= soCotTieuDe) return Array(soO).fill(1) as number[];
  if (soO === 1) return [soCotTieuDe];
  const thieu = soCotTieuDe - soO;
  return [...Array(soO - 2).fill(1), 1 + thieu, 1] as number[];
}

/**
 * Một bảng đã đọc (`docBangTuPhanTu`/`Muc.bang`) → `Table` thật của `docx`,
 * viền thấy được và hàng đầu in đậm (Phase 7 R2/R3: khớp đúng bảng biểu mẫu
 * tiếng Việt có hàng tiêu đề trên màn hình). KHÔNG đặc cách bảng nào — cùng
 * một hàm cho MỌI `<table>` đã render, kể cả bảng đánh giá. Hàng ngắn hơn
 * hàng tiêu đề (Phase 8 R4, ô gộp) dùng `columnSpan` qua `coSpanHang`, cùng
 * quy ước `XemTruocA4` dùng để vẽ trên màn hình — một hàng không "trôi" cột
 * giữa xem trước và tệp tải về.
 *
 * Tự `import("docx")` (module đã nạp thì cache lại, không tốn thêm) thay vì
 * nhận các lớp `docx` qua tham số: hàm phải gọi được ĐỘC LẬP với `xuatWord`
 * để kiểm (`kiem-xuat-tep.ts`) mà không cần dựng cả khung DOM thật.
 */
export async function bangThanhTable(hang: string[][]) {
  const { AlignmentType, BorderStyle, Paragraph, Table, TableCell, TableRow, TextRun, WidthType } =
    await import("docx");
  const vien = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
  const soCotTieuDe = hang[0]?.length ?? 0;
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: vien,
      bottom: vien,
      left: vien,
      right: vien,
      insideHorizontal: vien,
      insideVertical: vien,
    },
    rows: hang.map((o, hi) => {
      const span = coSpanHang(o.length, soCotTieuDe);
      return new TableRow({
        children: o.map((c, oi) => {
          const cot = span[oi] ?? 1;
          return new TableCell({
            borders: { top: vien, bottom: vien, left: vien, right: vien },
            // `exactOptionalPropertyTypes`: `shading`/`columnSpan` phải VẮNG
            // MẶT khi không dùng, không gán `undefined` — spread có điều
            // kiện, không gán.
            ...(hi === 0 ? { shading: { fill: "F0F0F0" } } : {}),
            ...(cot > 1 ? { columnSpan: cot } : {}),
            children: [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [
                  new TextRun({ text: c, bold: hi === 0, font: "Times New Roman", size: 24 }),
                ],
              }),
            ],
          });
        }),
      });
    }),
  });
}

/** Xuất tệp Word (.docx) đúng thể thức: Times New Roman 13pt, lề 2cm/3cm. */
export async function xuatWord(sheet: HTMLElement, tieuDe: string) {
  const {
    AlignmentType,
    Document,
    HeadingLevel,
    Packer,
    Paragraph,
    Table,
    TableCell,
    TableRow,
    TextRun,
    WidthType,
    BorderStyle,
    convertMillimetersToTwip,
  } = await import("docx");

  const { khoi, oKy } = docNoiDungTuDOM(sheet);

  const para = (d: DongVanBan) =>
    new Paragraph({
      alignment: d.canhGiua ? AlignmentType.CENTER : AlignmentType.JUSTIFIED,
      ...(d.kieu === "tieuDe" ? { heading: HeadingLevel.HEADING_1 } : {}),
      spacing: { after: 120, line: 312 },
      ...(d.thutLe > 0 ? { indent: { left: convertMillimetersToTwip(d.thutLe / 3.78) } } : {}),
      children: [
        new TextRun({
          text: d.text,
          bold: d.inDam,
          italics: d.inNghieng,
          size: d.kieu === "tieuDe" ? 32 : d.kieu === "dieu" ? 28 : 26,
          font: "Times New Roman",
        }),
      ],
    });

  const khong = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const bangKy =
    oKy.length > 0
      ? [
          new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            borders: {
              top: khong,
              bottom: khong,
              left: khong,
              right: khong,
              insideHorizontal: khong,
              insideVertical: khong,
            },
            rows: [
              new TableRow({
                children: oKy.map(
                  (cot) =>
                    new TableCell({
                      width: { size: 100 / oKy.length, type: WidthType.PERCENTAGE },
                      borders: { top: khong, bottom: khong, left: khong, right: khong },
                      children: cot.map(
                        (d, i) =>
                          new Paragraph({
                            alignment: AlignmentType.CENTER,
                            spacing: { before: i === cot.length - 1 ? 1200 : 0, after: 80 },
                            children: [
                              new TextRun({
                                text: d.text,
                                bold: d.inDam,
                                italics: d.inNghieng,
                                size: 26,
                                font: "Times New Roman",
                              }),
                            ],
                          }),
                      ),
                    }),
                ),
              }),
            ],
          }),
        ]
      : [];

  // Đoạn văn dựng NGAY (đồng bộ); bảng dựng bất đồng bộ (`bangThanhTable` tự
  // `import("docx")`) — `Promise.all` giữ ĐÚNG thứ tự `khoi` đã đọc từ DOM.
  const noiDungThan = await Promise.all(
    khoi.map((k) => (k.kind === "dong" ? Promise.resolve(para(k.d)) : bangThanhTable(k.hang))),
  );

  const doc = new Document({
    creator: "KLAW",
    title: tieuDe,
    description: "Bản thảo văn bản pháp lý do KLAW tạo — cần rà soát pháp chế trước khi ký kết.",
    styles: {
      default: {
        document: { run: { font: "Times New Roman", size: 26 } },
      },
    },
    sections: [
      {
        properties: {
          page: {
            margin: {
              top: convertMillimetersToTwip(20),
              bottom: convertMillimetersToTwip(20),
              left: convertMillimetersToTwip(30),
              right: convertMillimetersToTwip(20),
            },
          },
        },
        children: [...noiDungThan, new Paragraph({ text: "" }), ...bangKy],
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  taiBlob(blob, `${tenTepAnToan(tieuDe)}.docx`);
}

/**
 * Phase 5 — PDF vẽ bằng API văn bản của jsPDF (`text`/`splitTextToSize`),
 * không còn `html2canvas` chụp khung xem trước ra ảnh: chữ trong tệp tải về
 * giờ CHỌN/COPY/TÌM được, và không còn trần 30 trang giả (`nhanBanKhung` +
 * vòng cắt ảnh cũ đã bỏ hẳn). `noiDungThanhPDF` vẽ từ ĐÚNG `docNoiDungTuDOM`
 * đọc được — nguồn sự thật DUY NHẤT, giống `.docx` (`xuatWord`) đã dùng.
 */

/** 1pt = 25.4/72 mm — đổi cỡ chữ (pt, đơn vị `setFontSize` của jsPDF) sang mm
 * (đơn vị tài liệu, `unit: "mm"`). */
const MM_MOI_PT = 25.4 / 72;

/** Lề trang PDF — khớp NGUYÊN `xuatWord` (trên/dưới 20mm, trái 30mm, phải
 * 20mm): R4 nói hai tệp chỉ nên khác nhau ở font, không khác ở bố cục. */
const LE_PDF = { tren: 20, duoi: 20, trai: 30, phai: 20 };
const RONG_A4 = 210;
const CAO_A4 = 297;
const RONG_NOI_DUNG_PDF = RONG_A4 - LE_PDF.trai - LE_PDF.phai;

/**
 * Hệ số giãn dòng, truyền NGUYÊN vào `options.lineHeightFactor` của mọi lệnh
 * `text()` đa dòng bên dưới — jsPDF tự tính bước nhảy dòng nội bộ là
 * `activeFontSize * lineHeightFactor` với `activeFontSize` đã quy đổi sang mm
 * (xem `setFontSize` trong `jspdf`), tức CÙNG công thức `coChuPt(...) *
 * MM_MOI_PT * HE_SO_DONG_PDF` mà `caoDongPt` dùng để cộng dồn `y` thủ công.
 * Lệch hệ số này ở một trong hai chỗ là chữ dòng sau đè lên dòng trước.
 */
const HE_SO_DONG_PDF = 1.3;

/** Khoảng cách sau một đoạn — khớp `xuatWord`: `spacing.after: 120` (twip,
 * 1/20pt) = 6pt. */
const SAU_DOAN_PDF = 6 * MM_MOI_PT;

/** Cỡ chữ (pt) theo loại dòng — khớp NGUYÊN bảng size của `xuatWord.para`
 * (32/28/26 nửa-điểm = 16/14/13pt): ba định dạng (màn hình, .docx, .pdf) giữ
 * cùng phân cấp tiêu đề/điều/thường, chỉ khác font (R4). */
function coChuPt(kieu: KieuDong): number {
  return kieu === "tieuDe" ? 16 : kieu === "dieu" ? 14 : 13;
}

function caoDongPt(kieu: KieuDong): number {
  return coChuPt(kieu) * MM_MOI_PT * HE_SO_DONG_PDF;
}

/** Kiểu chữ (một trong bốn tên `setFont` chấp nhận) từ cờ đậm/nghiêng của một
 * dòng đã đọc từ DOM. */
function kieuChuPDF(d: DongVanBan): "normal" | "bold" | "italic" | "bolditalic" {
  if (d.inDam && d.inNghieng) return "bolditalic";
  if (d.inDam) return "bold";
  if (d.inNghieng) return "italic";
  return "normal";
}

const HO_CHU_PDF = "SourceSerif4";

/**
 * Bytes base64 của hai tệp TTF nhúng cho PDF (thường/đậm) — xem
 * `taiPhongChuPDF` (đường trình duyệt, `fetch` từ `public/fonts/`) và
 * `kiem-xuat-tep.ts` (đường Node, đọc thẳng từ đĩa). Cả hai đổ vào MỘT hàm
 * dựng PDF thuần (`noiDungThanhPDF`, không đụng DOM/`fetch`) để kiểm được từ
 * Node — không cần trình duyệt hay `jsdom`.
 *
 * Nguồn (Phase 5 R2): hai tệp `.ttf` này KHÔNG tải font mới nào — chúng được
 * đúc lại từ CHÍNH ba tệp webfont đã tự host, đã có trong kho TRƯỚC Phase 5:
 * `public/fonts/source-serif-4-var-{latin,latin-ext,vietnamese}.woff2`
 * (Source Serif 4, biến thiên, cấp phép OFL 1.1 — SIL Open Font License).
 * jsPDF (`addFileToVFS`/`addFont`) chỉ nhận TTF tĩnh, không nhận woff2 biến
 * thiên, nên ba tệp trên được, ngoại tuyến, một lần: (1) giải nén woff2→ttf
 * bằng `fontTools`, (2) đúc mỗi tệp thành hai lát cắt TĨNH 400/700 bằng
 * `fontTools.varLib.instancer` (font nguồn chỉ có trục `wght`), (3) GỘP ba
 * tập ký tự la-tinh cơ bản + la-tinh mở rộng + tiếng Việt mỗi lát cắt bằng
 * `fontTools.merge` — vì tệp con `-vietnamese.woff2` một mình CHỈ có 115 mã,
 * thiếu gần hết chữ cái/số/dấu câu cơ bản (đã đo: chỉ 'A'/'B' sống sót làm
 * .notdef dự phòng). Không có bước nào lấy nội dung font từ nguồn ngoài kho.
 * Font nguồn không có lát cắt nghiêng — xem ghi chú tại `dangKyPhongChuPDF`.
 */
export type PhongChuPDF = { thuong: string; dam: string };

type JsPDFModule = typeof import("jspdf");
type JsPDF = InstanceType<JsPDFModule["jsPDF"]>;

function dangKyPhongChuPDF(pdf: JsPDF, phongChu: PhongChuPDF) {
  pdf.addFileToVFS("SourceSerif4-Regular.ttf", phongChu.thuong);
  pdf.addFont("SourceSerif4-Regular.ttf", HO_CHU_PDF, "normal");
  pdf.addFileToVFS("SourceSerif4-Bold.ttf", phongChu.dam);
  pdf.addFont("SourceSerif4-Bold.ttf", HO_CHU_PDF, "bold");
  // Font nguồn chỉ đúc từ trục wght, không có trục nghiêng — đăng ký
  // "italic"/"bolditalic" TRỎ VÀO tệp đứng, để jsPDF không rơi về font mặc
  // định (Helvetica, không có dấu tiếng Việt) khi gặp một dòng nghiêng như
  // chú thích chữ ký "(Ký, ghi rõ họ tên, đóng dấu)". Đổi lại dòng đó hiện
  // THẲNG ĐỨNG thay vì nghiêng — mất dấu tiếng Việt là lỗi brief cấm (R2),
  // mất độ nghiêng thì không.
  pdf.addFont("SourceSerif4-Regular.ttf", HO_CHU_PDF, "italic");
  pdf.addFont("SourceSerif4-Bold.ttf", HO_CHU_PDF, "bolditalic");
  pdf.setFont(HO_CHU_PDF, "normal");
}

/**
 * Dựng PDF THẬT từ `{ khoi, oKy }` (Phase 5 R1) — hàm THUẦN: không đụng DOM,
 * không `fetch`, nhận bytes phông chữ qua tham số, để `kiem-xuat-tep.ts` gọi
 * được thẳng từ Node.
 *
 * Trả thêm `trangCuaKhoi`/`trangCuaKy` — số trang (1-based, tính từ lúc BẮT
 * ĐẦU vẽ khối đó) — CHỈ để kiểm luật phân trang (R3) mà không phải bóc PDF
 * nhị phân ra suy ngược trang của một khối.
 */
export async function noiDungThanhPDF(
  noiDung: NoiDungXuat,
  tieuDe: string,
  phongChu: PhongChuPDF,
): Promise<{ pdf: JsPDF; trangCuaKhoi: number[]; trangCuaKy: number | null }> {
  const { jsPDF } = await import("jspdf");
  const pdf = new jsPDF({ unit: "mm", format: "a4", compress: true });
  dangKyPhongChuPDF(pdf, phongChu);

  let y = LE_PDF.tren;
  let trang = 1;

  const conCho = (can: number) => y + can <= CAO_A4 - LE_PDF.duoi;
  const trangMoi = () => {
    pdf.addPage();
    trang += 1;
    y = LE_PDF.tren;
  };

  /** Một dòng (đoạn/tiêu đề) — trả về số trang đã vẽ lên. */
  const veDong = (d: DongVanBan, conKhoiSau: boolean): number => {
    pdf.setFont(HO_CHU_PDF, kieuChuPDF(d));
    pdf.setFontSize(coChuPt(d.kieu));
    const thutLeMm = d.canhGiua || d.thutLe <= 0 ? 0 : d.thutLe / 3.78;
    const rong = RONG_NOI_DUNG_PDF - thutLeMm;
    const dong = pdf.splitTextToSize(d.text, rong) as string[];
    const cao = dong.length * caoDongPt(d.kieu);

    // Luật mồ côi (R3): một tiêu đề (kieu tieuDe/dieu) không bao giờ là thứ
    // CUỐI CÙNG trên trang. Còn khối nào sau nó (kể cả khối ký) thì phải còn
    // đủ chỗ cho tiêu đề VÀ ít nhất một dòng thường nữa mới vẽ tại đây; không
    // thì sang trang mới rồi vẽ tiêu đề ở đầu trang đó.
    const laTieuDe = d.kieu === "tieuDe" || d.kieu === "dieu";
    const canThem = laTieuDe && conKhoiSau ? cao + caoDongPt("thuong") : cao;
    if (!conCho(canThem)) trangMoi();

    const x = d.canhGiua ? LE_PDF.trai + RONG_NOI_DUNG_PDF / 2 : LE_PDF.trai + thutLeMm;
    pdf.text(dong, x, y + coChuPt(d.kieu) * MM_MOI_PT, {
      align: d.canhGiua ? "center" : "justify",
      maxWidth: rong,
      lineHeightFactor: HE_SO_DONG_PDF,
    });
    y += cao + SAU_DOAN_PDF;
    return trang;
  };

  const DEM_O_PDF = 1.5; // mm, đệm trong một ô bảng
  const CO_CHU_BANG_PDF = 12; // pt, khớp `bangThanhTable` (`size: 24` nửa-điểm)

  /** Một bảng — trả về số trang đã BẮT ĐẦU vẽ (hàng tiêu đề của nó). */
  const veBang = (hang: string[][]): number => {
    const soCotTieuDe = hang[0]?.length ?? 0;
    if (soCotTieuDe === 0) return trang;
    const rongCot = RONG_NOI_DUNG_PDF / soCotTieuDe;
    let trangBatDau: number | null = null;

    for (let hi = 0; hi < hang.length; hi++) {
      const o = hang[hi]!;
      // `coSpanHang` — CÙNG luật ô gộp dùng cho màn hình (`XemTruocA4`) và
      // `.docx` (`bangThanhTable`): ô cuối luôn ở cột cuối, ô liền trước gánh
      // phần cột còn thiếu. Ba nơi vẽ bảng, MỘT luật đặt cột.
      const span = coSpanHang(o.length, soCotTieuDe);
      pdf.setFont(HO_CHU_PDF, hi === 0 ? "bold" : "normal");
      pdf.setFontSize(CO_CHU_BANG_PDF);
      const dongO = o.map((c, oi) => {
        const cot = span[oi] ?? 1;
        return pdf.splitTextToSize(c, rongCot * cot - 2 * DEM_O_PDF) as string[];
      });
      const soDongToiDa = dongO.reduce((max, d) => Math.max(max, d.length), 1);
      const caoHang = soDongToiDa * (CO_CHU_BANG_PDF * MM_MOI_PT * HE_SO_DONG_PDF) + 2 * DEM_O_PDF;

      if (!conCho(caoHang)) trangMoi();
      trangBatDau ??= trang;

      if (hi === 0) {
        pdf.setFillColor(240, 240, 240);
        pdf.rect(LE_PDF.trai, y, RONG_NOI_DUNG_PDF, caoHang, "F");
      }
      pdf.setDrawColor(153, 153, 153);
      let xO = LE_PDF.trai;
      for (let oi = 0; oi < o.length; oi++) {
        const cot = span[oi] ?? 1;
        const rongO = rongCot * cot;
        pdf.rect(xO, y, rongO, caoHang);
        pdf.text(dongO[oi]!, xO + rongO / 2, y + DEM_O_PDF + CO_CHU_BANG_PDF * MM_MOI_PT, {
          align: "center",
          maxWidth: rongO - 2 * DEM_O_PDF,
          lineHeightFactor: HE_SO_DONG_PDF,
        });
        xO += rongO;
      }
      y += caoHang;
    }
    y += SAU_DOAN_PDF;
    return trangBatDau ?? trang;
  };

  const trangCuaKhoi: number[] = noiDung.khoi.map((k, i) => {
    const conKhoiSau = i < noiDung.khoi.length - 1 || noiDung.oKy.length > 0;
    return k.kind === "dong" ? veDong(k.d, conKhoiSau) : veBang(k.hang);
  });

  let trangCuaKy: number | null = null;
  if (noiDung.oKy.length > 0) {
    const soCot = noiDung.oKy.length;
    const rongCot = RONG_NOI_DUNG_PDF / soCot;
    // Khớp `xuatWord`: `spacing.before: 1200` twip trước dòng ký cuối (chỗ
    // trống để ký tay), `spacing.after: 80` twip giữa các dòng còn lại.
    const KHOANG_KY = (1200 / 20) * MM_MOI_PT;
    const SAU_DONG_KY = (80 / 20) * MM_MOI_PT;

    const caoCot = (cot: DongVanBan[]) => {
      let cao = 0;
      cot.forEach((d, i) => {
        pdf.setFontSize(coChuPt(d.kieu));
        const dong = pdf.splitTextToSize(d.text, rongCot) as string[];
        if (i === cot.length - 1) cao += KHOANG_KY;
        cao += dong.length * caoDongPt(d.kieu);
        if (i < cot.length - 1) cao += SAU_DONG_KY;
      });
      return cao;
    };
    const caoKhoiKy = noiDung.oKy.reduce((max, cot) => Math.max(max, caoCot(cot)), 0);

    // Luật khối ký nguyên vẹn (R3): không đủ chỗ cho CẢ khối trên trang hiện
    // tại thì sang trang MỚI rồi vẽ trọn — không chẻ khối ký như một khối
    // văn bản thường.
    if (!conCho(caoKhoiKy)) trangMoi();
    trangCuaKy = trang;

    const yBatDau = y;
    noiDung.oKy.forEach((cot, ci) => {
      let yc = yBatDau;
      const xTam = LE_PDF.trai + rongCot * ci + rongCot / 2;
      cot.forEach((d, i) => {
        pdf.setFont(HO_CHU_PDF, kieuChuPDF(d));
        pdf.setFontSize(coChuPt(d.kieu));
        if (i === cot.length - 1) yc += KHOANG_KY;
        const dong = pdf.splitTextToSize(d.text, rongCot) as string[];
        pdf.text(dong, xTam, yc + coChuPt(d.kieu) * MM_MOI_PT, {
          align: "center",
          maxWidth: rongCot,
          lineHeightFactor: HE_SO_DONG_PDF,
        });
        yc += dong.length * caoDongPt(d.kieu);
        if (i < cot.length - 1) yc += SAU_DONG_KY;
      });
    });
    y = yBatDau + caoKhoiKy;
  }

  return { pdf, trangCuaKhoi, trangCuaKy };
}

const TEP_PHONG_CHU_PDF = {
  thuong: "/fonts/source-serif-4-pdf-regular.ttf",
  dam: "/fonts/source-serif-4-pdf-bold.ttf",
};

/** `ArrayBuffer` → base64 — định dạng `addFileToVFS` của jsPDF đòi (nó tự
 * `atob()` chuỗi này rồi mới đọc TTF, xem module `ttfsupport` trong `jspdf`). */
function base64TuBytes(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let nhiPhan = "";
  for (const b of bytes) nhiPhan += String.fromCharCode(b);
  return btoa(nhiPhan);
}

/** Tải hai tệp TTF nhúng (Phase 5 R2) từ `public/fonts/` — CHỈ gọi bên trong
 * `xuatPDF`, không import tĩnh, để hai tệp ~105KB này không vào bundle chính. */
async function taiPhongChuPDF(): Promise<PhongChuPDF> {
  const [thuong, dam] = await Promise.all([
    fetch(TEP_PHONG_CHU_PDF.thuong).then((r) => r.arrayBuffer()),
    fetch(TEP_PHONG_CHU_PDF.dam).then((r) => r.arrayBuffer()),
  ]);
  return { thuong: base64TuBytes(thuong), dam: base64TuBytes(dam) };
}

/**
 * Xuất tệp PDF khổ A4 nhiều trang có LỚP CHỮ THẬT (Phase 5) — chọn/copy/tìm
 * được, đọc được bằng trình đọc màn hình. Không còn chụp ảnh khung xem trước
 * (`html2canvas`) và không còn trần trang giả — một tài liệu dài ra bao
 * nhiêu trang thì cần bấy nhiêu (R3).
 */
export async function xuatPDF(sheet: HTMLElement, tieuDe: string) {
  const noiDung = docNoiDungTuDOM(sheet);
  const phongChu = await taiPhongChuPDF();
  const { pdf } = await noiDungThanhPDF(noiDung, tieuDe, phongChu);
  pdf.setProperties({ title: tieuDe, creator: "KLAW" });
  taiBlob(pdf.output("blob"), `${tenTepAnToan(tieuDe)}.pdf`);
}

/** Toàn văn dạng text thuần, dùng cho chức năng sao chép. */
export function toanVan(sheet: HTMLElement) {
  const { khoi, oKy } = docNoiDungTuDOM(sheet);
  const than = khoi
    .map((k) => (k.kind === "dong" ? k.d.text : k.hang.map((o) => o.join(" | ")).join("\n")))
    .join("\n");
  const ky = oKy.map((cot) => cot.map((d) => d.text).join("\n")).join("\n\n");
  return ky ? `${than}\n\n${ky}\n` : `${than}\n`;
}
