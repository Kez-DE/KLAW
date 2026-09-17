/**
 * `boQuaKhiXuat` — luật lọc phần tử của `docNoiDungTuDOM` (xuat-tep.ts).
 *
 * Dòng `Căn cứ:` trong khung xem trước A4 bật/tắt bằng công tắc "Hiển thị căn
 * cứ" và là một `<p>` y như mọi đoạn khác; trước bản vá này nó chảy thẳng vào
 * tệp `.docx` tải về, tức một công tắc XEM TRƯỚC đổi được nội dung một văn bản
 * pháp lý. Pin ở đây giữ ba nhánh của luật lọc. Chạy: `npm run kiem-xuat-tep`.
 */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { inflateSync } from "node:zlib";
import { Table } from "docx";
import {
  bangThanhTable,
  boQuaKhiXuat,
  canhLeThanhHuong,
  coSpanHang,
  docBangTuPhanTu,
  mucTuBanThao,
  nhipHangVe,
  noiDungThanhPDF,
  soCotThat,
  tiLeCotVe,
  tieuDeDaXuatHienTrongThan,
  tieuDeTuBanThao,
  type DongVanBan,
  type KhoiVanBan,
  type NoiDungXuat,
  type PhongChuPDF,
} from "../src/lib/xuat-tep.ts";
import type { CauTruc } from "../src/lib/klaw.ts";

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
assert.deepEqual(mucCu[1]?.khoi, [{ kind: "vanXuoi", noiDung: mucCu[1]!.noiDung, canhLe: "trai" }]);
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
    // Hình dạng CŨ (Phase 7, `noi_dung`+`bang` rời) chưa từng có nhịp/tỉ lệ —
    // về rỗng, `coSpanHang` suy đoán như trước Phase 11 (Phase 11 R1/R6).
    nhip: [],
    tiLe: [],
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

// ────────────────────── Phase 9 U1 — tên mục KLAW bịa không được in ra
//
// `ten_that` (mới ở `lam_sach_van_ban`/`clauses_tu` phía máy chủ) phải sống
// sót qua `mucTuBanThao` thành `Muc.tenThat`, để `XemTruocA4` biết mục nào
// đừng in tên ra trang.
const banThaoTenBia = {
  ...banThaoCu,
  clauses: [
    {
      key: "muc_1",
      ten: "Chữ ký",
      ten_that: false,
      vung: "than",
      khoi: [{ noi_dung: "x", bang: [] }],
    },
    {
      key: "muc_2",
      ten: "Bảng đánh giá",
      ten_that: true,
      vung: "than",
      khoi: [{ noi_dung: "y", bang: [] }],
    },
  ],
} as Parameters<typeof mucTuBanThao>[0];
const mucTenBia = mucTuBanThao(banThaoTenBia, null);
assert.equal(mucTenBia[0]?.tenThat, false, "tên KLAW bịa (không có trong nguồn) → tenThat=false");
assert.equal(mucTenBia[1]?.tenThat, true, "tên THẬT của tài liệu → tenThat=true");
// Clause CŨ (lưu trước Phase 9, không có khoá `ten_that`) → mặc định `true`,
// an toàn hơn ẩn oan một tiêu đề thật.
assert.equal(mucCu[0]?.tenThat, true, "clause cũ không có ten_that → mặc định giữ tên");

// Bản thảo CHECKLIST (có `cauTruc`, nhánh `khung.map`) luôn `tenThat=true` —
// tên mục ở đó đến từ chính `checklist_*.yaml`, chưa từng là mô hình bịa, bất
// kể clause của nó có mang `ten_that=false` hay không (trường đó vô nghĩa ở
// nhánh này).
const cauTrucToiThieu: CauTruc = {
  ten: "test",
  tieu_de: "Hợp đồng test",
  don_vi_muc: "Điều",
  muc_do_thieu: "thieu",
  pham_vi_soat: "noi_dung",
  chi_soat_the_thuc: false,
  la_hop_dong: false,
  khung_hop_dong: null,
  can_cu_goc: "x",
  can_cu_chi_tiet: null,
  muc: [{ stt: 1, key: "muc_1", ten: "Các bên", can_cu: "x", bat_buoc: true }],
};
const banThaoChecklistTenBia = {
  ...banThaoCu,
  clauses: [{ key: "muc_1", ten_that: false, noi_dung: "Bên A và Bên B." }],
} as Parameters<typeof mucTuBanThao>[0];
assert.equal(
  mucTuBanThao(banThaoChecklistTenBia, cauTrucToiThieu)[0]?.tenThat,
  true,
  "nhánh checklist luôn tenThat=true, không đọc ten_that của clause",
);

// ────────────────────────────────── Phase 9 U5 — căn lề sống sót qua `khoi`
//
// `can_le` (mới ở `_khoi_sach` phía máy chủ) phải sống sót qua `khoiTuClause`
// thành `KhoiMuc.canhLe`, đúng ba giá trị hợp lệ; giá trị vắng/lạ về `trai`.
const banThaoCanLe = {
  ...banThaoCu,
  clauses: [
    {
      key: "muc_1",
      ten: "Quốc hiệu",
      vung: "than",
      khoi: [
        { noi_dung: "CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM", bang: [], can_le: "giua" },
        { noi_dung: "Hà Nội, ngày ... tháng ... năm ...", bang: [], can_le: "phai" },
        { noi_dung: "Trường tự do: …", bang: [], can_le: "trai" },
        { noi_dung: "Không khai can_le", bang: [] },
        { noi_dung: "can_le lạ", bang: [], can_le: "linh_tinh" },
      ],
    },
  ],
} as Parameters<typeof mucTuBanThao>[0];
const khoiCanLe = mucTuBanThao(banThaoCanLe, null)[0]?.khoi as { canhLe: string }[];
assert.deepEqual(
  khoiCanLe.map((k) => k.canhLe),
  ["giua", "phai", "trai", "trai", "trai"],
);

// ───────────────────────────── Phase 11 R2/R8 — `trai` xuất KHÔNG phải "căn
// đều" ───────────────────────────────────────────────────────────────────
//
// Đo trực tiếp trên một `.docx` KLAW dựng thật: nguồn phần lớn không khai
// `w:jc` (→ đọc ra `trai`), nhưng tệp tải về gần như toàn bộ đoạn ra
// `w:jc="both"`. `canhLeThanhHuong` là chỗ DUY NHẤT quyết định hướng cho cả
// `.docx` (`xuatWord.para`) và PDF (`noiDungThanhPDF.veDong`) — khoá cả ba
// giá trị ở một chỗ để không lệch giữa hai nơi dùng.
assert.equal(
  canhLeThanhHuong("trai"),
  "left",
  "trai là KHÔNG XÁC ĐỊNH được căn lề, không phải căn đều",
);
assert.equal(canhLeThanhHuong("giua"), "center");
assert.equal(canhLeThanhHuong("phai"), "right");

// ────────────────────────────────────── Phase 11 R4 — bỏ tiêu đề bị lặp lại
//
// Một bản thảo TÁI HIỆN đã in tiêu đề của nó ra như chữ thân bài (quốc hiệu,
// tên biểu mẫu…) — `<h1>` của KLAW khi đó là bản sao thứ hai, phải bị bỏ.
assert.equal(
  tieuDeDaXuatHienTrongThan("GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP", [
    {
      stt: 1,
      key: "muc_1",
      ten: "x",
      tenThat: false,
      noiDung: "",
      bang: null,
      khoi: [
        {
          kind: "vanXuoi",
          noiDung: "Mẫu QT.ĐT.28-M05\nGIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP",
          canhLe: "giua",
        },
      ],
      vung: "than",
      canCu: null,
    },
  ]),
  true,
  "tiêu đề khớp một khối gộp nhiều dòng (không cần khớp NGUYÊN cả khối)",
);
// Một bản thảo KLAW soạn TỪ ĐẦU (tiêu đề không lặp lại ở đâu trong thân bài)
// → giữ `<h1>`, không để trang vô đề.
assert.equal(
  tieuDeDaXuatHienTrongThan("ĐƠN XIN NGHỈ VIỆC", [
    {
      stt: 1,
      key: "muc_1",
      ten: "x",
      tenThat: true,
      noiDung: "",
      bang: null,
      khoi: [{ kind: "vanXuoi", noiDung: "Kính gửi Ban Giám đốc,", canhLe: "trai" }],
      vung: "than",
      canCu: null,
    },
  ]),
  false,
  "tiêu đề không xuất hiện trong thân bài → giữ h1",
);
assert.equal(
  tieuDeDaXuatHienTrongThan("", []),
  false,
  "tiêu đề rỗng không bao giờ coi là đã xuất hiện",
);

// Phase 11 fix round 1 — đo được thật trên BM.M05 (conversation `b0c76517…`):
// tiêu đề THẬT ("GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP") không hề in ra thân bài
// ở đâu — nó chỉ NHẮC TỚI, như tên tài liệu, bên trong một câu khác hẳn
// ("Kèm theo Giấy tiếp nhận thực hành/thực tập số … ngày … tháng … năm …").
// `.includes()` coi câu này là "tiêu đề đã in", ẩn oan `<h1>` trên một trang
// mà tiêu đề chưa từng xuất hiện ở đâu khác — đúng lỗi round 1 báo lại.
assert.equal(
  tieuDeDaXuatHienTrongThan("GIẤY TIẾP NHẬN THỰC HÀNH/THỰC TẬP", [
    {
      stt: 1,
      key: "muc_1",
      ten: "x",
      tenThat: false,
      noiDung: "",
      bang: null,
      khoi: [
        {
          kind: "vanXuoi",
          noiDung: "(Kèm theo Giấy tiếp nhận thực hành/thực tập số … ngày … tháng … năm …)",
          canhLe: "giua",
        },
      ],
      vung: "than",
      canCu: null,
    },
  ]),
  false,
  "câu NHẮC TỚI tên tài liệu không phải câu IN LẠI tiêu đề — giữ h1",
);

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

// `nhipHangVe`/`tiLeCotVe` (Phase 11 R1/R6) — MỘT chỗ quyết định fallback,
// dùng chung cho cả ba nơi vẽ bảng (XemTruocA4, bangThanhTable, PDF).
assert.deepEqual(
  nhipHangVe(["Tổng", "10"], [2, 1], 4),
  [2, 1],
  "nhịp THẬT (khai lưới) được dùng thẳng, không suy đoán lại từ số ô",
);
assert.deepEqual(
  nhipHangVe(["Tổng", "10"], undefined, 4),
  coSpanHang(2, 4),
  "không có nhịp thật → suy đoán như coSpanHang cũ (bảng không khai lưới)",
);
assert.deepEqual(
  nhipHangVe(["Tổng", "10"], [2], 4),
  coSpanHang(2, 4),
  "nhịp thật LỆCH số ô của hàng (dữ liệu hỏng) → cũng rơi về suy đoán, không dùng nhịp sai",
);
assert.deepEqual(tiLeCotVe([7, 15, 30, 34, 15], 5), [7, 15, 30, 34, 15], "tỉ lệ thật dùng thẳng");
assert.deepEqual(
  tiLeCotVe([], 4),
  [25, 25, 25, 25],
  "không khai lưới (R1's 'falls back to equal columns') → chia đều",
);
assert.deepEqual(
  tiLeCotVe([50, 50], 3),
  [100 / 3, 100 / 3, 100 / 3],
  "tỉ lệ thật LỆCH số cột thật → cũng chia đều, không dùng tỉ lệ sai cột",
);

// `soCotThat` (Phase 11 fix round 3, reviewer I5) — số cột LƯỚI THẬT lấy từ
// `tiLe` khi có khai lưới, KHÔNG phải số ô của hàng đầu. Trước bản vá này, ba
// nơi vẽ bảng tự lấy `hang[0]?.length`; một hàng đầu có Ô GỘP (dòng tiêu đề
// toàn bảng, ít ô hơn số cột thật) khiến `tiLeCotVe`/`tiLe.length` LỆCH số
// cột đó và rơi oan về chia đều — đúng cái bảng tỉ lệ thật (R1) tồn tại để
// tránh. Assert `tiLeCotVe([50,50], 3) → chia đều` ở trên VẪN đúng như một
// hợp đồng phòng thủ của chính hàm đó (dữ liệu hỏng: khai 2 cột nhưng có 3
// ô) — điều đã sửa là CALLER không còn tự tính sai `soCot` truyền vào nữa.
assert.equal(
  soCotThat(
    [
      ["Tiêu đề", "Ghi chú"],
      ["a", "b", "c"],
    ],
    [50, 30, 20],
  ),
  3,
  "hàng đầu có ô gộp (2 ô) nhưng lưới khai 3 cột → lấy từ tỉ lệ, không lấy hàng đầu",
);
assert.equal(
  soCotThat([["A", "B", "C"]], []),
  3,
  "không khai lưới → hàng đầu vẫn là nguồn số cột duy nhất, như trước Phase 11",
);
assert.equal(soCotThat([], []), 0, "không hàng nào, không lưới nào → 0");

// ──────────────────── Review round 1 [IMPORTANT] — khối cả hai không bị nuốt
//
// Một khối thô có CẢ `noi_dung` (chú thích) LẪN `bang` (bảng) khác rỗng —
// rule 15 chỉ XIN mô hình để một trong hai, schema/backend không ép được.
// Trước bản vá này, `khoiMotHopLe` ưu tiên `bang` và ÂM THẦM bỏ `noiDung`;
// backend `_khoi_thanh_van_ban` lại ưu tiên NGƯỢC LẠI — hai phía lệch nhau
// đúng cách Phase 7 R1 fix round 1 đã bắt được một lần ở cấp mục. Từ bản vá
// này, MỘT khối thô như vậy ra HAI `KhoiMuc`, văn xuôi trước — không phía nào
// phải chọn ưu tiên và mất nội dung còn lại.
const banThaoKhoiCaHai = {
  ...banThaoCu,
  clauses: [
    {
      key: "muc_1",
      ten: "Đánh giá",
      vung: "than",
      khoi: [
        {
          noi_dung: "Chú thích bảng:",
          bang: [
            ["TT", "Điểm"],
            ["1", "2,0"],
          ],
        },
      ],
    },
  ],
} as Parameters<typeof mucTuBanThao>[0];
const mucKhoiCaHai = mucTuBanThao(banThaoKhoiCaHai, null)[0]?.khoi ?? [];
assert.equal(mucKhoiCaHai.length, 2, "một khối thô cả hai ra HAI khối sạch, không mất khối nào");
assert.deepEqual(mucKhoiCaHai[0], { kind: "vanXuoi", noiDung: "Chú thích bảng:", canhLe: "trai" });
assert.deepEqual(mucKhoiCaHai[1], {
  kind: "bang",
  hang: [
    ["TT", "Điểm"],
    ["1", "2,0"],
  ],
  nhip: [],
  tiLe: [],
});

// ──────────── Brief "Proof required" — letterhead hai cột sống sót NHƯ BẢNG
//
// Đo thật trên BM.M05 (`.sdd/phase-8-bm05-verbose.json`): letterhead không
// viền, hàng đầu đủ 2 cột (tên đơn vị chủ quản / quốc hiệu), hàng hai chỉ 1 ô
// gộp cả hai cột (tên cơ quan + số hiệu). Chưa test nào khoá riêng ca này
// trước bản vá — pin nguyên văn cấu trúc thật, không phải bịa một bảng mẫu.
const LETTERHEAD = [
  [
    "TÊN CHỦ QUẢN CỦA CƠ QUAN/ĐƠN VỊ TIẾP NHẬN (nếu có)",
    "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập – Tự do – Hạnh phúc",
  ],
  ["TÊN CƠ QUAN/ĐƠN VỊ TIẾP NHẬN Số …./…."],
];
const banThaoLetterhead = {
  ...banThaoCu,
  clauses: [
    { key: "muc_1", ten: "Đầu trang", vung: "than", khoi: [{ noi_dung: "", bang: LETTERHEAD }] },
  ],
} as Parameters<typeof mucTuBanThao>[0];
const mucLetterhead = mucTuBanThao(banThaoLetterhead, null)[0];
assert.equal(mucLetterhead?.khoi.length, 1, "letterhead là MỘT khối bảng, không bị xé lẻ");
assert.deepEqual(
  mucLetterhead?.khoi[0],
  { kind: "bang", hang: LETTERHEAD, nhip: [], tiLe: [] },
  "sống sót NGUYÊN dạng bảng hai cột, không dẹt thành dòng văn xuôi",
);

// `tieuDeTuBanThao` — dòng H1 đầu của `document` (Phase 7 R4): tiêu đề THẬT
// của văn bản, khác `BanThao.ten` ("Bản thảo tổng quát", tên LOẠI).
assert.equal(tieuDeTuBanThao(banThaoCu.document), "PHIẾU ĐÁNH GIÁ QUÁ TRÌNH THỰC TẬP CÔNG NGHIỆP");
assert.equal(tieuDeTuBanThao("Không có H1 nào ở đây"), null);

// `docBangTuPhanTu` — đọc một `<table>` đã render thành hàng×ô, nguyên văn
// từng ô (đã chuẩn hoá khoảng trắng), CỘNG `nhip` (Phase 11 R6, `colSpan` đã
// vẽ) và `tiLe` (Phase 11 R1, `data-ti-le` trên mỗi `<col>`). Đối tượng giả
// chỉ cần `querySelectorAll`/`textContent`/`getAttribute`, đúng như hàm thật
// đòi — không cần DOM thật (không có `jsdom` trong repo này).
const oCell = (text: string, colSpan?: number) => ({ textContent: text, colSpan });
const oRow = (cells: ReturnType<typeof oCell>[]) => ({
  querySelectorAll: (_sel: string) => cells,
});
const oCol = (tiLe: number) => ({
  getAttribute: (ten: string) => (ten === "data-ti-le" ? String(tiLe) : null),
});
const oTable = (rows: string[][], cols: number[] = []) => ({
  querySelectorAll: (sel: string) =>
    sel === "col" ? cols.map(oCol) : rows.map((r) => oRow(r.map((t) => oCell(t)))),
});

assert.deepEqual(
  docBangTuPhanTu(
    oTable([
      ["TT", "Tiêu chí"],
      ["1", "  Ý thức  \n"],
    ]),
  ),
  {
    hang: [
      ["TT", "Tiêu chí"],
      ["1", "Ý thức"], // khoảng trắng thừa/xuống dòng trong một ô đã được chuẩn hoá
    ],
    nhip: [
      [1, 1],
      [1, 1],
    ], // không `colSpan` nào được vẽ → mặc định 1 mỗi ô
    tiLe: [], // không `<colgroup>` nào → chia đều (R1)
  },
);

// Có `colSpan` đã vẽ (hàng gộp, Phase 11 R6) và `<colgroup>` mang tỉ lệ thật
// (Phase 11 R1) — đọc lại ĐÚNG những gì đã vẽ, không suy đoán lại.
const oTableGop = {
  querySelectorAll: (sel: string) =>
    sel === "col"
      ? [7, 15, 78].map(oCol)
      : [
          oRow([oCell("TT"), oCell("Tiêu chí"), oCell("Điểm")]),
          oRow([oCell("Tổng", 2), oCell("10")]),
        ],
};
assert.deepEqual(docBangTuPhanTu(oTableGop), {
  hang: [
    ["TT", "Tiêu chí", "Điểm"],
    ["Tổng", "10"],
  ],
  nhip: [
    [1, 1, 1],
    [2, 1],
  ],
  tiLe: [7, 15, 78],
});

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

// ─────────── Phase 11 R1/R6 — tỉ lệ cột và nhịp gộp sống sót vào `.docx` ────
//
// Brief đòi rõ: "A test that proportions survive into the .docx export, not
// only the preview." Đọc `w:tcW` (bề rộng ô THẬT trong XML nội bộ `docx`) —
// không chỉ kiểm `bangThanhTable` NHẬN đúng tham số, mà kiểm CHÍNH bề rộng
// đã ghi vào tệp. Một ô gộp (nhịp 2) phải mang bề rộng CỘNG DỒN của các cột
// nó chiếm, không phải bề rộng MỘT cột.
function rongOTuTcW(hangXmlMot: Record<string, unknown>): string[] {
  return timTat(hangXmlMot, "w:tcW").map((tcW) => {
    const attr = ((tcW["root"] as Record<string, unknown>[])[0]?.["root"] ?? {}) as Record<
      string,
      { value: string }
    >;
    return attr["size"]!.value;
  });
}

const bangTiLe = await bangThanhTable(
  [
    ["TT", "Tiêu chí", "Điểm"],
    ["Tổng", "10"],
  ],
  [
    [1, 1, 1],
    [2, 1],
  ],
  [30, 40, 30],
);
const hangTiLeXml = timTat(bangTiLe, "w:tr");
assert.deepEqual(
  rongOTuTcW(hangTiLeXml[0]!),
  ["30%", "40%", "30%"],
  "hàng tiêu đề: mỗi ô đúng % cột của nó",
);
assert.deepEqual(
  rongOTuTcW(hangTiLeXml[1]!),
  ["70%", "30%"],
  "hàng gộp: ô đầu (nhịp 2) mang bề rộng CỘNG DỒN 30+40=70%, ô sau 30%",
);

// Bảng KHÔNG khai lưới (mô hình tự soạn, `tiLe` rỗng) → chia đều — không
// suy đoán tỉ lệ (R1's "table with no declared grid falls back to equal
// columns").
const bangKhongLuoi = await bangThanhTable([["A", "B", "C"]]);
assert.deepEqual(
  rongOTuTcW(timTat(bangKhongLuoi, "w:tr")[0]!),
  [`${100 / 3}%`, `${100 / 3}%`, `${100 / 3}%`],
  "không khai lưới → chia đều 3 cột",
);

// ──── Phase 11 fix round 3 (reviewer I5) — hàng ĐẦU có ô gộp vẫn giữ tỉ lệ
// thật, không rơi về chia đều
//
// Lưới 3 cột [40, 30, 30]; hàng tiêu đề chỉ có 2 Ô THẬT (ô đầu gộp 2 cột,
// "Thông tin chung"), hàng thân đủ 3 ô. Trước bản vá này, `bangThanhTable` tự
// lấy `hang[0].length` (2) làm số cột, LỆCH với `tiLe.length` (3) — cả hàng
// tiêu đề LẪN hàng thân đều rơi về chia đều, R1 mất tác dụng đúng lúc bảng có
// một dòng tiêu đề gộp (hình dạng biểu mẫu tiếng Việt bình thường).
const bangTieuDeGop = await bangThanhTable(
  [
    ["Thông tin chung", "Ghi chú"],
    ["a", "b", "c"],
  ],
  [
    [2, 1],
    [1, 1, 1],
  ],
  [40, 30, 30],
);
const hangTieuDeGopXml = timTat(bangTieuDeGop, "w:tr");
assert.deepEqual(
  rongOTuTcW(hangTieuDeGopXml[0]!),
  ["70%", "30%"],
  "hàng tiêu đề: ô gộp (nhịp 2) mang bề rộng CỘNG DỒN 40+30=70%, không chia đều 50/50",
);
assert.deepEqual(
  rongOTuTcW(hangTieuDeGopXml[1]!),
  ["40%", "30%", "30%"],
  "hàng thân đủ 3 ô: đúng tỉ lệ thật của từng cột, không chia đều 33/33/33",
);

// ══════════════════════════ Phase 5 — PDF có lớp chữ THẬT ══════════════════
//
// `noiDungThanhPDF` là hàm THUẦN (không đụng DOM/`fetch`) đúng để việc này:
// đọc phông chữ thẳng từ đĩa (bytes base64 y hệt trình duyệt sẽ `fetch` từ
// `public/fonts/`), dựng PDF, rồi soát NGAY trên bytes PDF thô — không dừng
// ở "tệp không rỗng" (bản raster cũ cũng qua được phép thử đó).

const phongChuPDF: PhongChuPDF = {
  thuong: (
    await readFile(new URL("../public/fonts/source-serif-4-pdf-regular.ttf", import.meta.url))
  ).toString("base64"),
  dam: (
    await readFile(new URL("../public/fonts/source-serif-4-pdf-bold.ttf", import.meta.url))
  ).toString("base64"),
};

const dong = (
  text: string,
  kieu: DongVanBan["kieu"],
  extra: Partial<DongVanBan> = {},
): DongVanBan => ({
  text,
  kieu,
  canhLe: "trai",
  inDam: false,
  inNghieng: false,
  thutLe: 0,
  ...extra,
});

// Một khối cho MỖI loại `docNoiDungTuDOM` có thể trả — không loại nào bị vẽ
// âm thầm bỏ qua (R1): quốc hiệu, tiêu đề (căn giữa), số hiệu, một điều
// (heading), một đoạn thường có thụt lề, RỒI một bảng có hàng ngắn hơn hàng
// tiêu đề (Phase 8 R4, qua `coSpanHang`).
const KHOI_MAU: KhoiVanBan[] = [
  { kind: "dong", d: dong("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "quocHieu", { canhLe: "giua" }) },
  { kind: "dong", d: dong("HỢP ĐỒNG LAO ĐỘNG", "tieuDe", { canhLe: "giua", inDam: true }) },
  { kind: "dong", d: dong("Số: 90/2019/HĐLĐ", "soHieu") },
  { kind: "dong", d: dong("Điều 1. Nghĩa vụ các bên", "dieu", { inDam: true }) },
  {
    kind: "dong",
    d: dong("Người lao động cam kết thực hiện đúng nội quy.", "thuong", { thutLe: 12 }),
  },
  {
    kind: "bang",
    hang: [
      ["TT", "Tiêu chí", "Điểm tối đa", "Điểm đánh giá"],
      ["1", "Ý thức chấp hành nội quy, kỷ luật lao động", "2,0", "2,0"],
      ["Tổng", "10"], // ngắn hơn hàng tiêu đề — bắt buộc qua `coSpanHang`
    ],
    // Không nhịp/tỉ lệ thật (bảng mô hình tự soạn) — `nhipHangVe`/`tiLeCotVe`
    // phải rơi về suy đoán cũ (Phase 11 R1/R6), đúng ý chú thích trên.
    nhip: [],
    tiLe: [],
  },
];

// Khối ký hai cột, MỘT cột có dòng nghiêng (chú thích chữ ký, luôn nghiêng
// thật trong tài liệu — xem `KhongGianSoanThao.tsx`) mang dấu tiếng Việt cần
// khoá lại (R2): "ệ ằ ỗ ữ ơ Đ" hiện đúng, không phải ô vuông.
const OKY_MAU: DongVanBan[][] = [
  [
    dong("NGƯỜI SỬ DỤNG LAO ĐỘNG", "thuong", { canhLe: "giua", inDam: true }),
    dong("(Ký, ghi rõ họ tên, đóng dấu)", "thuong", { canhLe: "giua", inNghieng: true }),
    dong("Đặng Văn Sỹ", "thuong", { canhLe: "giua", inDam: true }),
  ],
  [
    dong("NGƯỜI LAO ĐỘNG", "thuong", { canhLe: "giua", inDam: true }),
    dong("(Ký, ghi rõ họ tên)", "thuong", { canhLe: "giua", inNghieng: true }),
    dong("Vũ Thị Ệ Ằ Ỗ Ữ Ơ", "thuong", { canhLe: "giua", inDam: true }),
  ],
];

const noiDungMau: NoiDungXuat = { khoi: KHOI_MAU, oKy: OKY_MAU };
const { pdf: pdfMau } = await noiDungThanhPDF(noiDungMau, "Kiểm PDF", phongChuPDF);
const bytesMau = Buffer.from(pdfMau.output("arraybuffer"));

/**
 * Bóc TẤT CẢ luồng `stream…endstream` nén Flate ra khỏi một tệp PDF, giải nén
 * từng luồng, nối lại thành một chuỗi để soát nội dung thật (thao tác vẽ chữ,
 * bảng ánh xạ Unicode) — jsPDF (`compress: true`) nén flate mọi luồng, kể cả
 * luồng `ToUnicode`, nên không thể `grep` thẳng trên bytes thô cho phần này.
 * Luồng nào không giải nén được (không phải Flate, ví dụ dữ liệu nhị phân
 * khác) bị bỏ qua thay vì làm hỏng cả phép kiểm.
 */
function noiDungGiaiNen(bytes: Buffer): string {
  const tho = bytes.toString("latin1");
  const ra: string[] = [];
  const re = /stream\r?\n([\s\S]*?)\r?\nendstream/g;
  for (const m of tho.matchAll(re)) {
    try {
      ra.push(inflateSync(Buffer.from(m[1]!, "latin1")).toString("latin1"));
    } catch {
      // không phải luồng Flate (ví dụ nhị phân font) — bỏ qua, không phải lỗi.
    }
  }
  return ra.join("\n");
}

const thoMau = bytesMau.toString("latin1");
const giaiNenMau = noiDungGiaiNen(bytesMau);

// Có thao tác vẽ CHỮ thật (Tj/TJ) trong nội dung trang — không phải "tệp
// không rỗng" (bản `html2canvas` cũ cũng qua được phép thử yếu đó).
assert.ok(/\bT[jJ]\b/.test(giaiNenMau), "phải có toán tử vẽ chữ Tj/TJ trong luồng nội dung trang");

// Có font nhúng thật (FontFile2 — TTF nhúng nguyên khối) mang đúng tên họ
// chữ đã đăng ký, không phải font chuẩn của jsPDF (Helvetica, không có dấu
// tiếng Việt).
assert.ok(
  thoMau.includes("/FontFile2"),
  "phải nhúng font thật (/FontFile2), không dùng font chuẩn",
);
assert.ok(
  thoMau.includes("SourceSerif4"),
  "font nhúng phải là SourceSerif4, không phải font mặc định",
);

// KHÔNG có XObject ảnh nào — đúng điều R1 đòi: chữ vẽ bằng API văn bản, không
// còn `html2canvas`/`addImage`. Đây là phép thử phân biệt chính giữa bản vá
// này và bản raster cũ (bản cũ CHỈ có một `/Subtype /Image` to đúng một
// trang).
assert.ok(!/\/Subtype\s*\/Image\b/.test(thoMau), "không được có XObject ảnh nào trong tệp PDF");

// Dấu tiếng Việt round-trip vào bảng ToUnicode: "ệ" (U+1EC7) phải có một mục
// ánh xạ CID→Unicode thật (`<mã CID><1ec7>`), không phải ô vuông không tra
// ngược được về Unicode.
assert.ok(
  /<[0-9a-f]{4}><1ec7>/.test(giaiNenMau),
  '"ệ" (U+1EC7) phải có mục ToUnicode thật, không bị mất khi nhúng font',
);

// ─────────────────────── R3 — tiêu đề không mồ côi cuối trang ───────────────
//
// Điền một số đoạn "thường" TRƯỚC một tiêu đề (`dieu`) rồi một đoạn ngắn sau
// nó, tăng dần số đoạn điền cho tới khi tiêu đề bị đẩy sang trang 2 — đúng
// chỗ một thuật toán ngắt trang ngây thơ (không có luật mồ côi) sẽ để tiêu đề
// đứng MỘT MÌNH ở cuối trang 1, còn đoạn theo sau rơi sang trang 2. Không
// hard-code hằng số bố cục nội bộ (`LE_PDF`, `HE_SO_DONG_PDF`…) — tự dò biên
// bằng chính hàm thật, nên phép thử không rã nếu các hằng số đó đổi sau này.
function taiLieuMoCoi(soDoanDien: number): NoiDungXuat {
  const dien: KhoiVanBan[] = Array.from({ length: soDoanDien }, (_, i) => ({
    kind: "dong" as const,
    d: dong(`Đoạn điền chỗ trống số ${i + 1} để đẩy dần xuống cuối trang.`, "thuong"),
  }));
  return {
    khoi: [
      ...dien,
      { kind: "dong", d: dong("Điều 9. Điều khoản dễ mồ côi", "dieu", { inDam: true }) },
      { kind: "dong", d: dong("Đoạn theo ngay sau tiêu đề.", "thuong") },
    ],
    oKy: [],
  };
}

let bienMoCoi = -1;
for (let n = 0; n <= 80; n++) {
  const { trangCuaKhoi } = await noiDungThanhPDF(taiLieuMoCoi(n), "Kiểm mồ côi", phongChuPDF);
  const trangTieuDe = trangCuaKhoi[n]!;
  if (trangTieuDe === 2) {
    bienMoCoi = n;
    break;
  }
}
assert.ok(
  bienMoCoi >= 0,
  "phải dò được số đoạn điền đẩy tiêu đề sang trang 2 (tài liệu mẫu chưa đủ dài)",
);

// Tại ĐÚNG biên (và lân cận), tiêu đề và đoạn theo sau nó luôn cùng một
// trang — luật mồ côi chủ động đẩy CẢ HAI sang trang mới, không để tiêu đề
// đứng một mình ở cuối trang trước.
for (const n of [bienMoCoi - 1, bienMoCoi, bienMoCoi + 1]) {
  const { trangCuaKhoi } = await noiDungThanhPDF(taiLieuMoCoi(n), "Kiểm mồ côi", phongChuPDF);
  assert.equal(
    trangCuaKhoi[n],
    trangCuaKhoi[n + 1],
    `n=${n}: tiêu đề (khối ${n}) và đoạn theo sau (khối ${n + 1}) phải cùng trang`,
  );
}

// ─────────────────────── R3 — khối ký nguyên vẹn một trang ─────────────────
//
// Cùng cách dò biên: điền đoạn cho tới khi khối ký (`oKy`) bị đẩy sang trang
// 2 — đúng chỗ một khối ký bị TRÀN qua trang (chẻ đôi) nếu không có luật này.
function taiLieuKy(soDoanDien: number): NoiDungXuat {
  const dien: KhoiVanBan[] = Array.from({ length: soDoanDien }, (_, i) => ({
    kind: "dong" as const,
    d: dong(`Đoạn điền chỗ trống số ${i + 1} trước khối ký.`, "thuong"),
  }));
  return { khoi: dien, oKy: OKY_MAU };
}

let bienKy = -1;
for (let n = 0; n <= 80; n++) {
  const { trangCuaKy } = await noiDungThanhPDF(taiLieuKy(n), "Kiểm khối ký", phongChuPDF);
  if (trangCuaKy === 2) {
    bienKy = n;
    break;
  }
}
assert.ok(
  bienKy >= 0,
  "phải dò được số đoạn điền đẩy khối ký sang trang 2 (tài liệu mẫu chưa đủ dài)",
);

// Ngay tại biên, khối ký chỉ NHẢY nguyên khối sang trang mới — không có giá
// trị trang nào khác 1 hoặc 2 (tức không "chẻ" nó thành nhiều mảnh rải trên
// nhiều trang, điều `trangCuaKy: number | null` — một số DUY NHẤT — vốn
// không biểu diễn nổi nếu nó bị chẻ).
for (const n of [bienKy - 1, bienKy, bienKy + 1]) {
  const { trangCuaKy } = await noiDungThanhPDF(taiLieuKy(n), "Kiểm khối ký", phongChuPDF);
  assert.ok(
    trangCuaKy === 1 || trangCuaKy === 2,
    `n=${n}: khối ký phải nằm gọn trên đúng một trang`,
  );
}

// ─────────────────── Fix round 1 #1 — mồ côi khi khối sau là BẢNG ──────────
//
// Cùng cách dò biên, nhưng khối theo NGAY sau tiêu đề giờ là một BẢNG, không
// phải một đoạn văn — hình dạng phổ biến nhất của biểu mẫu này (tiêu đề mục
// dẫn thẳng vào bảng chấm điểm, không câu dẫn). Trước bản vá này, buffer mồ
// côi là một hằng số một-dòng "thuong" bất kể khối sau là gì, nên tiêu đề có
// thể vẫn bị bỏ lại một mình cuối trang trong khi hàng tiêu đề THẬT của bảng
// (cao hơn một dòng thường) nhảy sang trang sau theo luật phân trang riêng
// của chính bảng — đúng lỗi mồ côi luật này tồn tại để chặn, mà phép thử
// heading→heading ở trên không bắt được.
function taiLieuMoCoiBang(soDoanDien: number): NoiDungXuat {
  const dien: KhoiVanBan[] = Array.from({ length: soDoanDien }, (_, i) => ({
    kind: "dong" as const,
    d: dong(`Đoạn điền chỗ trống số ${i + 1} để đẩy dần xuống cuối trang.`, "thuong"),
  }));
  return {
    khoi: [
      ...dien,
      { kind: "dong", d: dong("Điều 9. Bảng chấm điểm", "dieu", { inDam: true }) },
      {
        kind: "bang",
        hang: [
          ["TT", "Tiêu chí", "Điểm tối đa", "Điểm đánh giá"],
          ["1", "Ý thức chấp hành nội quy, kỷ luật lao động", "2,0", "2,0"],
        ],
        nhip: [],
        tiLe: [],
      },
    ],
    oKy: [],
  };
}

let bienMoCoiBang = -1;
for (let n = 0; n <= 80; n++) {
  const { trangCuaKhoi } = await noiDungThanhPDF(
    taiLieuMoCoiBang(n),
    "Kiểm mồ côi bảng",
    phongChuPDF,
  );
  if (trangCuaKhoi[n] === 2) {
    bienMoCoiBang = n;
    break;
  }
}
assert.ok(
  bienMoCoiBang >= 0,
  "phải dò được số đoạn điền đẩy tiêu đề (đứng trước bảng) sang trang 2",
);

for (const n of [bienMoCoiBang - 1, bienMoCoiBang, bienMoCoiBang + 1]) {
  const { trangCuaKhoi } = await noiDungThanhPDF(
    taiLieuMoCoiBang(n),
    "Kiểm mồ côi bảng",
    phongChuPDF,
  );
  assert.equal(
    trangCuaKhoi[n],
    trangCuaKhoi[n + 1],
    `n=${n}: tiêu đề (khối ${n}) và bảng theo ngay sau (khối ${n + 1}) phải cùng trang`,
  );
}

// ──────────────── Fix round 1 #2 — bảng dài lặp lại hàng tiêu đề ───────────
//
// Một bảng đủ dài để tràn qua nhiều trang: hàng tiêu đề phải được VẼ LẠI ở
// đầu MỖI trang tiếp theo — thiếu bước đó thì trang sau mất tên cột, không
// đọc được cột nào là "Điểm tối đa", cột nào là "Điểm đánh giá" (đúng lỗi
// khả dụng thật cho một biểu mẫu đánh giá, không giả định "bảng luôn ngắn").
// Đếm số lần hình chữ nhật tô xám của hàng tiêu đề xuất hiện trong nội dung
// đã giải nén: `0.94 g` (jsPDF chọn DeviceGray cho `setFillColor(240,240,
// 240)`, RGB bằng nhau) rồi một `re`/`f` — đo cấu trúc PDF thật, không phải
// đếm chữ (chữ trong luồng nội dung là mã CID Identity-H, không phải văn bản
// đọc được). Xác nhận số lần tô KHỚP ĐÚNG số trang — không phải một lần duy
// nhất bất kể bảng dài bao nhiêu.
function bangDaiHang(soHang: number): NoiDungXuat {
  const tieuDeBang = ["TT", "Tiêu chí", "Điểm tối đa", "Điểm đánh giá"];
  const hang: string[][] = [tieuDeBang];
  for (let i = 1; i <= soHang; i++) {
    hang.push([String(i), `Tiêu chí đánh giá số ${i}`, "2,0", "2,0"]);
  }
  return { khoi: [{ kind: "bang", hang, nhip: [], tiLe: [] }], oKy: [] };
}

function demLanToTieuDeBang(bytes: Buffer): number {
  return [...noiDungGiaiNen(bytes).matchAll(/0\.94 g\n[\d.-]+ [\d.-]+ [\d.-]+ [\d.-]+ re\nf/g)]
    .length;
}

let soHangTran = -1;
for (let soHang = 5; soHang <= 100; soHang += 5) {
  const { pdf: pdfBang } = await noiDungThanhPDF(bangDaiHang(soHang), "Kiểm bảng dài", phongChuPDF);
  if (pdfBang.getNumberOfPages() >= 2) {
    soHangTran = soHang;
    break;
  }
}
assert.ok(soHangTran >= 0, "phải dò được số hàng đẩy bảng tràn qua ít nhất 2 trang");

const { pdf: pdfBangTran } = await noiDungThanhPDF(
  bangDaiHang(soHangTran),
  "Kiểm bảng dài",
  phongChuPDF,
);
const soTrangBangTran = pdfBangTran.getNumberOfPages();
assert.equal(
  demLanToTieuDeBang(Buffer.from(pdfBangTran.output("arraybuffer"))),
  soTrangBangTran,
  "hàng tiêu đề (tô xám) phải được vẽ lại ở đầu MỖI trang, không chỉ trang đầu",
);

console.info("kiem-xuat-tep: 75/75 đạt");
