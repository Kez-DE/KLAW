/**
 * `boQuaKhiXuat` — luật lọc phần tử của `docNoiDungTuDOM` (xuat-tep.ts).
 *
 * Dòng `Căn cứ:` trong khung xem trước A4 bật/tắt bằng công tắc "Hiển thị căn
 * cứ" và là một `<p>` y như mọi đoạn khác; trước bản vá này nó chảy thẳng vào
 * tệp `.docx` tải về, tức một công tắc XEM TRƯỚC đổi được nội dung một văn bản
 * pháp lý. Pin ở đây giữ ba nhánh của luật lọc. Chạy: `npm run kiem-xuat-tep`.
 */
import assert from "node:assert/strict";
import { Table } from "docx";
import {
  bangThanhTable,
  boQuaKhiXuat,
  coSpanHang,
  docBangTuPhanTu,
  mucTuBanThao,
  tieuDeTuBanThao,
} from "../src/lib/xuat-tep.ts";

/** Phần tử giả tối thiểu: `docNoiDungTuDOM` chỉ hỏi đúng hai thứ này. */
const el = (tagName: string, trongKhoiKhongXuat = false) => ({
  tagName,
  closest: (chon: string) =>
    chon === "[data-khong-xuat]" && trongKhoiKhongXuat ? { tagName: "SECTION" } : null,
});

// Đoạn văn thường của văn bản → VÀO tệp.
assert.equal(boQuaKhiXuat(el("P")), false);
assert.equal(boQuaKhiXuat(el("H1")), false);

// Thẻ kỹ thuật → không bao giờ vào tệp (hành vi cũ, giữ nguyên).
assert.equal(boQuaKhiXuat(el("SCRIPT")), true);
assert.equal(boQuaKhiXuat(el("STYLE")), true);

// Nằm TRONG một khối `data-khong-xuat` (dòng `Căn cứ:`) → bị loại, kể cả khi
// bản thân nó là một `<p>` hợp lệ về mọi mặt khác.
assert.equal(boQuaKhiXuat(el("P", true)), true);

// ─────────────────────────────────────────────────── Phase 7 — bảng sống sót
//
// Draft `8b008e90-d8eb-40fa-9784-a7e8def408fd` (Postgres cục bộ) là fixture
// TRƯỚC bản vá: `clauses[1].noi_dung` là chuỗi pipe Markdown improv, không có
// khoá `bang` nào. Dán nguyên văn ở đây để khoá cả hai đầu — hàng cũ vẫn phải
// render đúng NHƯ TRƯỚC (không parse `|` ra bảng, brief cấm), và một clause
// MỚI có `bang` phải ra một `Muc.bang` thật.

const CLAUSES_CU = [
  { key: "muc_1", ten: "Thông tin sinh viên", noi_dung: "Họ và tên sinh viên: […]\nMã số: […]" },
  {
    key: "muc_2",
    ten: "Đánh giá quá trình thực tập",
    noi_dung:
      "TT | Tiêu chí đánh giá | Điểm tối đa | Điểm đánh giá\n---|---|---|---\n" +
      "1 | Ý thức chấp hành nội quy, kỷ luật tại đơn vị thực tập | 2,0 | […]",
  },
  { key: "muc_3", ten: "Chữ ký", noi_dung: "GV HƯỚNG DẪN\n(Ký, ghi rõ họ tên)" },
];

const banThaoCu = {
  id: "8b008e90-d8eb-40fa-9784-a7e8def408fd",
  loai: "tong_quat",
  ten: "Bản thảo tổng quát",
  phien_ban: 1,
  document: "# PHIẾU ĐÁNH GIÁ QUÁ TRÌNH THỰC TẬP CÔNG NGHIỆP\n\n## 1. Thông tin sinh viên\n",
  clauses: CLAUSES_CU,
  audit_report: {},
  facts: {},
  doi_so_voi_truoc: [],
} as Parameters<typeof mucTuBanThao>[0];

const mucCu = mucTuBanThao(banThaoCu, null);
assert.equal(mucCu.length, 3);
// Hàng cũ KHÔNG có khoá `bang` → `null`, và `noiDung` giữ NGUYÊN chuỗi pipe cũ
// (kể cả dòng `---|---|---|---`) — hành vi "vẫn render như trước" cho dữ liệu
// đã lưu trước Phase 7, không phải một cải thiện ngầm.
assert.equal(mucCu[1]?.bang, null);
assert.ok(mucCu[1]?.noiDung.includes("---|---|---|---"));
// Phase 8: hình dạng CŨ (chỉ `noi_dung`, không `khoi` không `bang`) quy về
// đúng MỘT khối văn xuôi mang nguyên chuỗi pipe — `XemTruocA4` render nó
// bằng đúng một `<p>`, không parse `|` ra bảng (brief cấm).
assert.deepEqual(mucCu[1]?.khoi, [{ kind: "vanXuoi", noiDung: mucCu[1]!.noiDung }]);
assert.equal(mucCu[1]?.vung, "than");

// Một clause kiểu Phase 7 (`noi_dung`+`bang` rời) → `Muc.bang` là hàng×ô thật
// (tương thích ngược không đổi), VÀ `Muc.khoi` là đúng MỘT khối bảng đó.
const banThaoMoi = {
  ...banThaoCu,
  clauses: [
    {
      key: "muc_2",
      ten: "Đánh giá",
      noi_dung: "",
      bang: [
        ["TT", "Tiêu chí đánh giá", "Điểm tối đa"],
        ["1", "Ý thức chấp hành nội quy", "2,0"],
      ],
    },
  ],
} as Parameters<typeof mucTuBanThao>[0];
const mucMoi = mucTuBanThao(banThaoMoi, null);
assert.deepEqual(mucMoi[0]?.bang, [
  ["TT", "Tiêu chí đánh giá", "Điểm tối đa"],
  ["1", "Ý thức chấp hành nội quy", "2,0"],
]);
assert.deepEqual(mucMoi[0]?.khoi, [
  {
    kind: "bang",
    hang: [
      ["TT", "Tiêu chí đánh giá", "Điểm tối đa"],
      ["1", "Ý thức chấp hành nội quy", "2,0"],
    ],
  },
]);

// ────────────────────────────────── Phase 8 R1 — khối nhiều phần tử, đúng thứ tự
//
// Một clause MỚI (`khoi`, `dung_ban_thao_tong_quat.clauses_tu` từ Phase 8) có
// câu dẫn, một bảng, RỒI một câu kết: BA khối, giữ NGUYÊN thứ tự — hình dạng
// Phase 7 (một noiDung + một bang) không nén được ca này.
const banThaoNhieuKhoi = {
  ...banThaoCu,
  clauses: [
    {
      key: "muc_2",
      ten: "Đánh giá",
      vung: "than",
      khoi: [
        { noi_dung: "Kết quả chấm điểm như sau:", bang: [] },
        {
          noi_dung: "",
          bang: [
            ["TT", "Tiêu chí đánh giá"],
            ["1", "Ý thức chấp hành nội quy"],
          ],
        },
        { noi_dung: "Điểm trên do hội đồng thống nhất.", bang: [] },
      ],
    },
  ],
} as Parameters<typeof mucTuBanThao>[0];
const mucNhieuKhoi = mucTuBanThao(banThaoNhieuKhoi, null);
assert.deepEqual(
  mucNhieuKhoi[0]?.khoi.map((k) => k.kind),
  ["vanXuoi", "bang", "vanXuoi"],
);
assert.equal(
  (mucNhieuKhoi[0]?.khoi[0] as { noiDung: string }).noiDung,
  "Kết quả chấm điểm như sau:",
);
assert.equal(
  (mucNhieuKhoi[0]?.khoi[2] as { noiDung: string }).noiDung,
  "Điểm trên do hội đồng thống nhất.",
);

// Phase 8 R2 — `vung` (đầu/chân trang) sống sót qua `mucTuBanThao`, mặc định
// `than` khi vắng mặt (hàng CŨ, không mang khoá này).
const banThaoChanTrang = {
  ...banThaoCu,
  clauses: [
    { key: "muc_1", ten: "Chân trang", vung: "chan_trang", khoi: [{ noi_dung: "BM.X", bang: [] }] },
  ],
} as Parameters<typeof mucTuBanThao>[0];
assert.equal(mucTuBanThao(banThaoChanTrang, null)[0]?.vung, "chan_trang");
assert.equal(mucCu[0]?.vung, "than"); // hàng CŨ không có `vung` → mặc định

// Phase 8 R4 — hàng ngắn hơn hàng tiêu đề (ô gộp) đi qua NGUYÊN trong `khoi`,
// `coSpanHang` bên dưới mới quyết định cách vẽ nó.
const banThaoHangNgan = {
  ...banThaoCu,
  clauses: [
    {
      key: "muc_1",
      ten: "Đánh giá",
      vung: "than",
      khoi: [
        {
          noi_dung: "",
          bang: [
            ["TT", "Tiêu chí", "Điểm tối đa", "Điểm đánh giá"],
            ["1", "Ý thức", "2,0", "2,0"],
            ["Tổng", "10"],
          ],
        },
      ],
    },
  ],
} as Parameters<typeof mucTuBanThao>[0];
const khoiHangNgan = mucTuBanThao(banThaoHangNgan, null)[0]?.khoi[0] as { hang: string[][] };
assert.deepEqual(khoiHangNgan.hang[2], ["Tổng", "10"]);

// `coSpanHang` (Phase 8 R4) — quyết định biểu diễn cho hàng ngắn hơn hàng
// tiêu đề: ô CUỐI luôn ở cột cuối, ô liền trước gánh phần cột còn thiếu.
assert.deepEqual(coSpanHang(4, 4), [1, 1, 1, 1], "hàng đủ cột không đổi gì");
assert.deepEqual(coSpanHang(2, 4), [3, 1], '"Tổng" | "10" trên 4 cột — 10 vẫn ở cột cuối');
assert.deepEqual(coSpanHang(1, 4), [4], "hàng một ô chiếm trọn cả hàng tiêu đề");
assert.deepEqual(
  coSpanHang(3, 4),
  [1, 2, 1],
  "3 ô trên 4 cột — ô liền trước ô cuối gánh phần thiếu",
);
assert.deepEqual(coSpanHang(0, 4), [], "hàng rỗng không có ô nào để vẽ");

// `tieuDeTuBanThao` — dòng H1 đầu của `document` (Phase 7 R4): tiêu đề THẬT
// của văn bản, khác `BanThao.ten` ("Bản thảo tổng quát", tên LOẠI).
assert.equal(tieuDeTuBanThao(banThaoCu.document), "PHIẾU ĐÁNH GIÁ QUÁ TRÌNH THỰC TẬP CÔNG NGHIỆP");
assert.equal(tieuDeTuBanThao("Không có H1 nào ở đây"), null);

// `docBangTuPhanTu` — đọc một `<table>` đã render thành hàng×ô, nguyên văn
// từng ô (đã chuẩn hoá khoảng trắng). Đối tượng giả chỉ cần `querySelectorAll`/
// `textContent`, đúng như hàm thật đòi — không cần DOM thật (không có `jsdom`
// trong repo này).
const oCell = (text: string) => ({ textContent: text });
const oRow = (cells: string[]) => ({ querySelectorAll: (_sel: string) => cells.map(oCell) });
const oTable = (rows: string[][]) => ({ querySelectorAll: (_sel: string) => rows.map(oRow) });

assert.deepEqual(
  docBangTuPhanTu(
    oTable([
      ["TT", "Tiêu chí"],
      ["1", "  Ý thức  \n"],
    ]),
  ),
  [
    ["TT", "Tiêu chí"],
    ["1", "Ý thức"], // khoảng trắng thừa/xuống dòng trong một ô đã được chuẩn hoá
  ],
);

// `bangThanhTable` — hàng×ô → `Table` THẬT của `docx` (Phase 7 R3), không phải
// một cấu trúc trung gian tự chế. Đọc lại bằng `rootKey`/`root` (cây XML nội
// bộ của `docx`, ổn định qua các bản — cách duy nhất soát được nội dung một
// `Table` mà không cần đóng gói ra `.docx` thật rồi mở lại).
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

const bang = await bangThanhTable([
  ["TT", "Tiêu chí"],
  ["1", "Ý thức chấp hành"],
]);
assert.ok(bang instanceof Table, "bangThanhTable phải trả về một Table thật của docx");
const hangXml = timTat(bang, "w:tr");
assert.equal(hangXml.length, 2, "2 hàng đưa vào phải ra đúng 2 <w:tr>");
const chuHangDau = timTat(hangXml[0]!, "w:t").map((wt) =>
  (wt["root"] as unknown[]).find((x) => typeof x === "string"),
);
assert.deepEqual(chuHangDau, ["TT", "Tiêu chí"]);
const chuHangHai = timTat(hangXml[1]!, "w:t").map((wt) =>
  (wt["root"] as unknown[]).find((x) => typeof x === "string"),
);
assert.deepEqual(chuHangHai, ["1", "Ý thức chấp hành"]);

console.info("kiem-xuat-tep: 30/30 đạt");
