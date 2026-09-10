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

export type NoiDungXuat = {
  dong: DongVanBan[];
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
  canCu: string | null;
}

/**
 * Hình dạng THẬT của một phần tử `BanThao.clauses` (kiểu `unknown[]` chưa gõ ở FE) —
 * khớp `dataclasses.asdict(DraftClause)` (`src/agents/nodes/draft_generate.py` +
 * `src/services/ban_thao.py` dòng ghi `clauses`): `key`, `ten`, `noi_dung`,
 * `can_cu_provision_id`. KHÔNG có trường `text` — chỉ `noi_dung` mang nội dung.
 */
type ClauseTho = { key?: string; ten?: string; noi_dung?: string };

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
      canCu: null,
    }));
  }
  return khung.map((m) => ({
    stt: m.stt,
    key: m.key,
    ten: m.ten,
    noiDung: theoKey.get(m.key)?.noi_dung ?? "[…]",
    canCu: m.can_cu || null,
  }));
}

const BO_QUA = new Set(["SCRIPT", "STYLE"]);

function chuanHoa(s: string) {
  return s.replace(/\s+/g, " ").trim();
}

function laCanhGiua(el: HTMLElement) {
  return getComputedStyle(el).textAlign === "center";
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
  const dong: DongVanBan[] = [];
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
        .map(docDong)
        .filter((d) => d.text !== "");
      if (dongCot.length > 0) oKy.push(dongCot);
    }
  }

  const blocks = sheet.querySelectorAll<HTMLElement>("h1, p");
  for (const el of Array.from(blocks)) {
    if (BO_QUA.has(el.tagName)) continue;
    if (khoiKy && khoiKy.contains(el)) continue;
    const d = docDong(el);
    if (d.text === "") continue;
    dong.push(d);
  }

  return { dong, oKy };
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

  const { dong, oKy } = docNoiDungTuDOM(sheet);

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
        children: [...dong.map(para), new Paragraph({ text: "" }), ...bangKy],
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
  const { dong, oKy } = docNoiDungTuDOM(sheet);
  const than = dong.map((d) => d.text).join("\n");
  const ky = oKy.map((cot) => cot.map((d) => d.text).join("\n")).join("\n\n");
  return ky ? `${than}\n\n${ky}\n` : `${than}\n`;
}
