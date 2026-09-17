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

/** Một mục dựng sẵn cho `XemTruocA4`: nội dung của `clauses` ghép vào khung `cau_truc.muc`. */
export interface Muc {
  stt: number;
  key: string;
  ten: string;
  noiDung: string;
  /**
   * Hàng × ô khi mục này là một BẢNG trong tài liệu nguồn (Phase 7 R1, hàng
   * đầu là tiêu đề) — `null` khi mục là văn xuôi, dùng `noiDung` như cũ. Một
   * `clauses` CŨ (trước bản vá này) không có khoá `bang` — luôn ra `null`.
   */
  bang: string[][] | null;
  canCu: string | null;
}

/**
 * Hình dạng THẬT của một phần tử `BanThao.clauses` (kiểu `unknown[]` chưa gõ ở FE) —
 * khớp `dataclasses.asdict(DraftClause)` (`src/agents/nodes/draft_generate.py` +
 * `src/services/ban_thao.py` dòng ghi `clauses`): `key`, `ten`, `noi_dung`,
 * `can_cu_provision_id`. KHÔNG có trường `text` — chỉ `noi_dung` mang nội dung.
 * `bang` chỉ có ở `clauses` do `dung_ban_thao_tong_quat.clauses_tu` dựng (Phase 7).
 */
type ClauseTho = { key?: string; ten?: string; noi_dung?: string; bang?: unknown };

/** `c.bang` thô (kiểu chưa biết, tới từ `unknown[]`) → hàng×ô hợp lệ, hoặc
 * `null` khi rỗng/vắng/sai hình dạng — một mục cũ không có khoá này phải rơi
 * đúng vào nhánh văn xuôi, không phải một bảng 0 hàng. */
function bangHopLe(bang: unknown): string[][] | null {
  if (!Array.isArray(bang) || bang.length === 0) return null;
  return bang.map((hang) => (Array.isArray(hang) ? hang.map((o) => String(o)) : []));
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
      canCu: null,
    }));
  }
  return khung.map((m) => ({
    stt: m.stt,
    key: m.key,
    ten: m.ten,
    noiDung: theoKey.get(m.key)?.noi_dung ?? "[…]",
    bang: bangHopLe(theoKey.get(m.key)?.bang),
    canCu: m.can_cu || null,
  }));
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
 * Một bảng đã đọc (`docBangTuPhanTu`/`Muc.bang`) → `Table` thật của `docx`,
 * viền thấy được và hàng đầu in đậm (Phase 7 R2/R3: khớp đúng bảng biểu mẫu
 * tiếng Việt có hàng tiêu đề trên màn hình). KHÔNG đặc cách bảng nào — cùng
 * một hàm cho MỌI `<table>` đã render, kể cả bảng đánh giá.
 *
 * Tự `import("docx")` (module đã nạp thì cache lại, không tốn thêm) thay vì
 * nhận các lớp `docx` qua tham số: hàm phải gọi được ĐỘC LẬP với `xuatWord`
 * để kiểm (`kiem-xuat-tep.ts`) mà không cần dựng cả khung DOM thật.
 */
export async function bangThanhTable(hang: string[][]) {
  const { AlignmentType, BorderStyle, Paragraph, Table, TableCell, TableRow, TextRun, WidthType } =
    await import("docx");
  const vien = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
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
    rows: hang.map(
      (o, hi) =>
        new TableRow({
          children: o.map(
            (c) =>
              new TableCell({
                borders: { top: vien, bottom: vien, left: vien, right: vien },
                // `exactOptionalPropertyTypes`: `shading` phải VẮNG MẶT ở hàng
                // thường, không gán `undefined` — spread có điều kiện, không gán.
                ...(hi === 0 ? { shading: { fill: "F0F0F0" } } : {}),
                children: [
                  new Paragraph({
                    alignment: AlignmentType.CENTER,
                    children: [
                      new TextRun({ text: c, bold: hi === 0, font: "Times New Roman", size: 24 }),
                    ],
                  }),
                ],
              }),
          ),
        }),
    ),
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

/** Nhân bản khung A4 ở tỉ lệ 100% (bỏ zoom) để chụp ảnh trung thực. */
function nhanBanKhung(sheet: HTMLElement) {
  const hoi = document.createElement("div");
  hoi.style.cssText =
    "position:fixed;left:-10000px;top:0;width:794px;background:#fff;z-index:-1;pointer-events:none;";
  const ban = sheet.cloneNode(true) as HTMLElement;
  ban.style.transform = "none";
  ban.style.boxShadow = "none";
  ban.style.margin = "0";
  // Khung xem trước là một hộp cao đúng một trang A4 (`aspect-[210/297]`) và
  // CUỘN phần thừa. `html2canvas` chụp đúng cái hộp đó, nên bản sao phải cao
  // theo nội dung — nếu không, vòng cắt trang bên dưới luôn chỉ có một trang
  // ảnh để cắt và tệp PDF cụt ở trang 1 (tệp Word không dính vì nó đọc DOM).
  ban.style.height = "auto";
  ban.style.overflow = "visible";
  hoi.appendChild(ban);
  document.body.appendChild(hoi);
  return { hoi, ban };
}

/** Xuất tệp PDF khổ A4 nhiều trang từ khung xem trước. */
export async function xuatPDF(sheet: HTMLElement, tieuDe: string) {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
    import("html2canvas-pro"),
    import("jspdf"),
  ]);

  const { hoi, ban } = nhanBanKhung(sheet);
  try {
    const canvas = await html2canvas(ban, {
      scale: 2,
      backgroundColor: "#ffffff",
      useCORS: true,
      logging: false,
    });

    const pdf = new jsPDF({ unit: "mm", format: "a4", compress: true });
    const rongTrang = 210;
    const caoTrang = 297;
    const caoAnh = (canvas.height * rongTrang) / canvas.width;

    let daVe = 0;
    let trang = 0;
    while (daVe < caoAnh - 0.5) {
      if (trang > 0) pdf.addPage();
      pdf.addImage(canvas.toDataURL("image/jpeg", 0.94), "JPEG", 0, -daVe, rongTrang, caoAnh);
      daVe += caoTrang;
      trang += 1;
      if (trang > 30) break;
    }

    pdf.setProperties({ title: tieuDe, creator: "KLAW" });
    taiBlob(pdf.output("blob"), `${tenTepAnToan(tieuDe)}.pdf`);
  } finally {
    hoi.remove();
  }
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
