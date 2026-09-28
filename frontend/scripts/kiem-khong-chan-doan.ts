/**
 * Quyết định 2026-09-28 (`docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md`),
 * mục 8 và 10 — luật của chủ dự án: "Chưa xác định" không bao giờ xuất hiện;
 * không hiện dòng chẩn đoán (mã tình trạng nội bộ, "độ tin cậy", "đánh giá tại
 * ngày"). Chỉ nhãn hiệu lực, và khi có, một câu thường nêu văn bản sửa đổi hoặc
 * thay thế kèm link.
 *
 * Hai vế, cùng phạm vi — `src/components/` và `src/routes/`, nơi dựng mặt
 * người đọc:
 *
 * 1. **Chữ cho người đọc** (chuỗi, template, chữ JSX — KHÔNG chú thích, đọc
 *    bằng chính bộ phân tích của TypeScript nên "https://" trong một chuỗi
 *    không nuốt phần còn lại của dòng) không chứa các cụm cấm dưới đây.
 * 2. **Trường chẩn đoán không được đọc ra** để hiển thị: `ly_do`, `tin_cay`,
 *    `do_tin_cay`, `as_of` của API hiệu lực. API vẫn trả chúng cho đo đạc và
 *    eval; giao diện đọc `verdict` (nhãn) và `mo_ta` (câu thường).
 *
 * Ngoại lệ chỉ đúng những chỗ ghi dưới, mỗi chỗ một lý do.
 *
 * Chạy: `npm run kiem-khong-chan-doan`.
 */
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const GOC = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const QUYET_DINH = "docs/decisions/2026-09-28-trich-dan-day-du-va-lien-ket-nguon.md, mục 8/10";

const CUM_CAM: { re: RegExp; ten: string; mienTru?: Record<string, string> }[] = [
  {
    re: /độ tin cậy/iu,
    ten: "độ tin cậy",
    mienTru: {
      // Trang miễn trừ nói về độ tin cậy của CẢ sản phẩm, không phải một dòng
      // chẩn đoán gắn vào văn bản nào.
      "src/routes/mien-tru.tsx": "lời miễn trừ chung",
    },
  },
  // Cả "không xác định": nhãn cũ "Một phần không xác định" là cùng câu nói.
  { re: /(?:chưa|không) xác định/iu, ten: "chưa/không xác định" },
  { re: /không rõ/iu, ten: "không rõ" },
  { re: /đánh giá tại ngày/iu, ten: "đánh giá tại ngày" },
  { re: /(?<![\p{L}\p{N}])MOJ(?![\p{L}\p{N}])/u, ten: "MOJ (tình trạng MOJ)" },
];

const TRUONG_CAM: Record<string, Record<string, string>> = {
  ly_do: {
    // `YeuCauNangGoi.ly_do` — lý do từ chối một yêu cầu nâng gói, không dính
    // tới hiệu lực văn bản.
    "src/components/tai-khoan/ModalNangGoi.tsx": "lý do từ chối nâng gói",
  },
  tin_cay: {},
  do_tin_cay: {},
  as_of: {},
};

/** Mọi vi phạm của MỘT tệp nguồn. Tách riêng để chứng minh cả hai chiều. */
export function viPham(tenTep: string, ma: string): string[] {
  const sf = ts.createSourceFile(
    tenTep,
    ma,
    ts.ScriptTarget.Latest,
    true,
    tenTep.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const ra: string[] = [];
  const dong = (n: ts.Node) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1;
  const di = (n: ts.Node): void => {
    const laChu =
      ts.isStringLiteralLike(n) ||
      ts.isJsxText(n) ||
      ts.isTemplateHead(n) ||
      ts.isTemplateMiddle(n) ||
      ts.isTemplateTail(n);
    if (laChu && !ts.isImportDeclaration(n.parent)) {
      const chu = n.text.replace(/\s+/g, " ");
      for (const cam of CUM_CAM) {
        if (cam.re.test(chu) && cam.mienTru?.[tenTep] === undefined) {
          ra.push(`${tenTep}:${dong(n)}: chữ cho người đọc chứa "${cam.ten}": ${chu.trim()}`);
        }
      }
    }
    const truong = ts.isPropertyAccessExpression(n)
      ? n.name.text
      : ts.isElementAccessExpression(n) && ts.isStringLiteralLike(n.argumentExpression)
        ? n.argumentExpression.text
        : null;
    // `hasOwn`, không `TRUONG_CAM[truong]`: `.constructor` không được tra ra một hàm.
    if (truong !== null && Object.hasOwn(TRUONG_CAM, truong) && !TRUONG_CAM[truong]?.[tenTep]) {
      ra.push(`${tenTep}:${dong(n)}: đọc trường chẩn đoán \`${truong}\` ở mặt người đọc`);
    }
    ts.forEachChild(n, di);
  };
  di(sf);
  return ra;
}

// Chứng minh hai chiều trước khi quét thật: một phép quét không bắt được gì
// thì "sạch" chẳng nói lên điều gì.
{
  const xau = [
    "export const A = () => <p>Chưa xác định</p>;",
    'export const A2 = { chu: "Một phần không xác định" };',
    "export const B = (h: { tin_cay: string }) => <span>{h.tin_cay}</span>;",
    "export const C = `Đánh giá tại ngày ${x} · độ tin cậy: thấp`;",
    'export const D = (v: { ly_do: string }) => v["ly_do"];',
    'export const E = "tình trạng MOJ = CHL";',
    'export const F = <dd>{x ?? "Không rõ"}</dd>;',
  ];
  xau.forEach((ma, i) =>
    assert.ok(viPham("src/routes/xau.tsx", ma).length > 0, `phép quét để lọt mẫu xấu #${i}: ${ma}`),
  );
  const sach = [
    "// Chưa xác định — chú thích thì được\nexport const A = () => <p>Còn hiệu lực một phần</p>;",
    "/* độ tin cậy */ export const B = { tin_cay: null };",
    'export const C = <a href="https://vbpl.vn/van-ban/chi-tiet/1">Xem trên CSDL quốc gia</a>;',
    'export const D = "chua_xac_dinh";',
  ];
  sach.forEach((ma, i) =>
    assert.deepEqual(viPham("src/routes/sach.tsx", ma), [], `phép quét bắt nhầm mẫu sạch #${i}`),
  );
  assert.deepEqual(
    viPham("src/routes/mien-tru.tsx", "export const M = <p>mức độ tin cậy</p>;"),
    [],
    "miễn trừ của trang miễn trừ",
  );
  assert.ok(
    viPham("src/routes/mien-tru.tsx", "export const M = <p>Chưa xác định</p>;").length > 0,
    "miễn trừ chỉ cho ĐÚNG cụm đã ghi",
  );
}

function moiTep(thuMuc: string): string[] {
  return readdirSync(thuMuc).flatMap((ten) => {
    const p = join(thuMuc, ten);
    if (statSync(p).isDirectory()) return moiTep(p);
    return /\.tsx?$/.test(p) ? [p] : [];
  });
}

const tep = ["src/components", "src/routes"].flatMap((d) => moiTep(join(GOC, d)));
assert.ok(tep.length > 40, "không quét được tệp nào — sai đường dẫn?");
const vuong = tep.flatMap((p) => {
  const ten = relative(GOC, p).split("\\").join("/");
  return viPham(ten, readFileSync(p, "utf8"));
});
assert.deepEqual(
  vuong,
  [],
  `mặt người đọc còn dòng chẩn đoán (${QUYET_DINH}):\n${vuong.join("\n")}\n` +
    "Hiện nhãn (`BadgeHieuLuc`) và câu `mo_ta` (`MoTaHieuLuc`); bỏ dòng thiếu dữ liệu thay vì in chỗ giữ chỗ.",
);

console.info(`kiem-khong-chan-doan: ${tep.length} tệp sạch`);
