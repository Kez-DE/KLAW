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
  docBangTuPhanTu,
  mucTuBanThao,
  phanHienThiMuc,
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

// Một clause MỚI (sau bản vá, `dung_ban_thao_tong_quat.clauses_tu` luôn phát
// khoá `bang`) → `Muc.bang` là hàng×ô thật, không phải `null`.
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

// `phanHienThiMuc` — review round 1 fix: một `muc` có CẢ `noiDung` (câu dẫn)
// LẪN `bang` (bảng) không được để ternary trong `XemTruocA4` nuốt mất một
// trong hai. Rule 15 của prompt chỉ XIN mô hình để `noi_dung` rỗng khi dùng
// `bang` — schema/`lam_sach_van_ban` không ép được điều đó, nên "cả hai có
// mặt" là một hình dạng THẬT phải qua được, không chỉ "chỉ noiDung"/"chỉ
// bang"/"cả hai rỗng".
assert.deepEqual(phanHienThiMuc({ noiDung: "Câu dẫn.", bang: null }), {
  coNoiDung: true,
  coBang: false,
});
assert.deepEqual(phanHienThiMuc({ noiDung: "", bang: [["TT"], ["1"]] }), {
  coNoiDung: false,
  coBang: true,
});
assert.deepEqual(
  phanHienThiMuc({ noiDung: "Câu dẫn trước bảng.", bang: [["TT"], ["1"]] }),
  { coNoiDung: true, coBang: true }, // ca bị nuốt trước bản vá — cả hai PHẢI cùng true
);
assert.deepEqual(phanHienThiMuc({ noiDung: "", bang: null }), {
  coNoiDung: false,
  coBang: false,
});

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

console.info("kiem-xuat-tep: 20/20 đạt");
