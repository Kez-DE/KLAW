/**
 * Xuất bản thảo hợp đồng ra tệp thật (.docx / .pdf) từ khung xem trước A4.
 * Toàn bộ xử lý diễn ra trên trình duyệt — không gửi nội dung bản thảo lên máy chủ.
 */

export type KieuDong = "quocHieu" | "tieuDe" | "soHieu" | "dieu" | "thuong";

export type DongVanBan = {
  text: string;
  kieu: KieuDong;
  canhGiua: boolean;
  inDam: boolean;
  inNghieng: boolean;
  thutLe: number;
};

export type OKy = { ben: string[] };

export type NoiDungXuat = {
  dong: DongVanBan[];
  oKy: string[][];
};

const BO_QUA = new Set(["SCRIPT", "STYLE"]);

function chuanHoa(s: string) {
  return s.replace(/\s+/g, " ").trim();
}

function laCanhGiua(el: HTMLElement) {
  return getComputedStyle(el).textAlign === "center";
}

/** Đọc nội dung hiển thị của khung A4 thành danh sách dòng có định dạng. */
export function docNoiDungTuDOM(sheet: HTMLElement): NoiDungXuat {
  const dong: DongVanBan[] = [];
  const oKy: string[][] = [];

  const khoiKy = sheet.querySelector<HTMLElement>('[data-xuat="ky"]');
  if (khoiKy) {
    for (const cot of Array.from(khoiKy.children) as HTMLElement[]) {
      const dongCot = Array.from(cot.querySelectorAll("p"))
        .map((p) => chuanHoa(p.textContent ?? ""))
        .filter(Boolean);
      oKy.push(dongCot);
    }
  }

  const blocks = sheet.querySelectorAll<HTMLElement>("h1, p");
  for (const el of Array.from(blocks)) {
    if (BO_QUA.has(el.tagName)) continue;
    if (khoiKy && khoiKy.contains(el)) continue;
    const text = chuanHoa(el.textContent ?? "");
    if (!text) continue;

    const cs = getComputedStyle(el);
    const laDieu = el.classList.contains("dieu-head");
    const kieu: KieuDong =
      el.tagName === "H1" ? "tieuDe" : laDieu ? "dieu" : /^Số:/.test(text) ? "soHieu" : "thuong";

    dong.push({
      text: cs.textTransform === "uppercase" ? text.toLocaleUpperCase("vi-VN") : text,
      kieu,
      canhGiua: laCanhGiua(el),
      inDam: Number(cs.fontWeight) >= 600 || laDieu,
      inNghieng: cs.fontStyle === "italic",
      thutLe: Math.round(parseFloat(cs.marginLeft || "0")),
    });
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
    oKy.length === 2
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
                      width: { size: 50, type: WidthType.PERCENTAGE },
                      borders: { top: khong, bottom: khong, left: khong, right: khong },
                      children: cot.map(
                        (t, i) =>
                          new Paragraph({
                            alignment: AlignmentType.CENTER,
                            spacing: { before: i === cot.length - 1 ? 1200 : 0, after: 80 },
                            children: [
                              new TextRun({
                                text: t,
                                bold: i === 0 || i === cot.length - 1,
                                italics: i === 1,
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
  const ky = oKy.map((cot) => cot.join("\n")).join("\n\n");
  return ky ? `${than}\n\n${ky}\n` : `${than}\n`;
}
