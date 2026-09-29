/**
 * Khuôn gốc ở giao diện (kế hoạch `khuon-goc-dien-tai-cho.md`, P5) — phần
 * THUẦN: cửa vào `khuon` của bản thảo, cửa vào tải trang và chỗ trống của nó,
 * vị trí pt → trang, thứ tự đọc, nhãn, tên tệp tải về, đường dẫn và câu lỗi.
 *
 * Vì sao đáng kiểm riêng: `khuonHopLe` quyết định giao diện vẽ trang hay A4
 * HTML, và mỗi ô nó bỏ sót là một ô người dùng không điền được; `oHopLe` và
 * `viTriO` quyết định nút điền nằm ĐÚNG trên chỗ trống nào của ảnh trang,
 * `oKeTiep` quyết định Tab đi sang chỗ nào, và `oDaDoi` quyết định chỗ nào còn
 * chữ trên trang mà tệp tải về chưa có — bỏ sót là tải về một tệp thiếu chữ
 * người dùng đang nhìn thấy.
 *
 * Chạy: `npm run kiem-khuon-goc`.
 */
import assert from "node:assert/strict";
import { khuonHopLe, laTrangAnh, oHopLe, type ChoTrongKhuon } from "../src/lib/klaw.ts";
import {
  boDaGui,
  chiGiuThayDoi,
  DUONG_DAN_KHUON,
  giaTriHienThi,
  khoaO,
  loiTrang,
  nhanNutDien,
  nhanO,
  oDaDoi,
  oKeTiep,
  phuDeKhuon,
  tenTepTuContentDisposition,
  viTriO,
} from "../src/lib/khuon-goc.ts";

let dat = 0;
let tong = 0;
function kiem(ten: string, fn: () => void) {
  tong += 1;
  try {
    fn();
    dat += 1;
  } catch (loi) {
    console.error(`✗ ${ten}`);
    throw loi;
  }
}

const o = (p: Partial<ChoTrongKhuon>): ChoTrongKhuon => ({
  don_vi: 0,
  so: 0,
  kieu: "cham",
  nhan: "Họ và tên:",
  gia_tri: null,
  ...p,
});

const KHUON = {
  viec_id: "11111111-2222-3333-4444-555555555555",
  dinh_dang: "docx",
  so_trang: 2,
  cho_trong: [
    o({ don_vi: 0, so: 0, gia_tri: "Nguyễn Văn Ánh" }),
    o({ don_vi: 1, so: 0, kieu: "tab", nhan: "Email", gia_tri: " a@b.vn" }),
    o({ don_vi: 1, so: 1, nhan: "", gia_tri: null }),
  ],
};

// ─────────────────────────────────────────────────────────── khuonHopLe
kiem("khuôn hợp lệ đi qua nguyên hình dạng; máy chủ cũ (không `nguon`) là tệp tải lên", () => {
  assert.deepEqual(khuonHopLe(KHUON), { ...KHUON, nguon: "tai_len", can_cu: [] });
});
kiem("không phải bản ghi → null (bản thảo HTML)", () => {
  for (const x of [null, undefined, "docx", [KHUON], 3]) assert.equal(khuonHopLe(x), null);
});
kiem("vỏ sai (định dạng lạ, thiếu viec_id, số trang không nguyên dương) → null", () => {
  assert.equal(khuonHopLe({ ...KHUON, dinh_dang: "odt" }), null);
  assert.equal(khuonHopLe({ ...KHUON, viec_id: "" }), null);
  assert.equal(khuonHopLe({ ...KHUON, viec_id: undefined }), null);
  assert.equal(khuonHopLe({ ...KHUON, so_trang: 0 }), null);
  assert.equal(khuonHopLe({ ...KHUON, so_trang: 1.5 }), null);
});
kiem("`cho_trong` vắng/sai kiểu → khuôn vẫn dựng, không ô nào", () => {
  assert.deepEqual(khuonHopLe({ ...KHUON, cho_trong: undefined })?.cho_trong, []);
  assert.deepEqual(khuonHopLe({ ...KHUON, cho_trong: "x" })?.cho_trong, []);
});
kiem("ô dị dạng bị BỎ, ô lành giữ nguyên thứ tự đọc", () => {
  const k = khuonHopLe({
    ...KHUON,
    cho_trong: [
      { don_vi: -1, so: 0, kieu: "cham", nhan: "a", gia_tri: null },
      { don_vi: 2, so: "0", kieu: "cham", nhan: "a", gia_tri: null },
      { don_vi: 2, so: 0, kieu: "cham", gia_tri: null },
      { don_vi: 2, so: 1, kieu: "cham", nhan: "a", gia_tri: 5 },
      { don_vi: 2, so: 2, nhan: "a", gia_tri: null },
      { don_vi: 2.5, so: 3, kieu: "cham", nhan: "a", gia_tri: null },
      "không phải ô",
      { don_vi: 3, so: 0, kieu: "tab", nhan: "Ngày", gia_tri: " 01/01" },
      { don_vi: 4, so: 0, kieu: "cham", nhan: "Nơi" },
    ],
  });
  assert.deepEqual(k?.cho_trong, [
    o({ don_vi: 3, so: 0, kieu: "tab", nhan: "Ngày", gia_tri: " 01/01" }),
    o({ don_vi: 4, so: 0, nhan: "Nơi", gia_tri: null }),
  ]);
});
kiem("ô trùng (don_vi, so) chỉ giữ ô ĐẦU — hai ô một khoá là hai ô một chỗ lưu", () => {
  const k = khuonHopLe({
    ...KHUON,
    cho_trong: [o({ don_vi: 5, gia_tri: "đầu" }), o({ don_vi: 5, gia_tri: "sau" })],
  });
  assert.deepEqual(
    k?.cho_trong.map((x) => x.gia_tri),
    ["đầu"],
  );
});
kiem("khoá ngoài hợp đồng không lọt ra", () => {
  const k = khuonHopLe({ ...KHUON, la: 1, cho_trong: [{ ...o({}), hop: [1, 2, 3, 4] }] });
  assert.deepEqual(Object.keys(k ?? {}).sort(), [
    "can_cu",
    "cho_trong",
    "dinh_dang",
    "nguon",
    "so_trang",
    "viec_id",
  ]);
  assert.deepEqual(Object.keys(k?.cho_trong[0] ?? {}).sort(), [
    "don_vi",
    "gia_tri",
    "kieu",
    "nhan",
    "so",
  ]);
});

// ─────────────────────────────────────── khuôn mẫu: `nguon` và `can_cu`
// Thiết kế `khuon-mau-thiet-ke.md` §3/§5: bản thảo KLAW dựng thành .docx ngồi
// trên cùng khung trang với khuôn gốc; `nguon` quyết định lời nói (không "tải
// lên") và nút "Căn cứ (N)", `can_cu` là thứ nút đó mở.
kiem("`nguon`: 'khuon_mau' giữ nguyên; vắng hay lạ → 'tai_len' (hành vi cũ)", () => {
  assert.equal(khuonHopLe({ ...KHUON, nguon: "khuon_mau" })?.nguon, "khuon_mau");
  for (const nguon of [undefined, null, "tai_len", "KHUON_MAU", 1, ""])
    assert.equal(khuonHopLe({ ...KHUON, nguon })?.nguon, "tai_len", String(nguon));
});
kiem("`can_cu`: vắng / không phải mảng → []", () => {
  for (const can_cu of [undefined, null, "x", { nhan: "a" }])
    assert.deepEqual(khuonHopLe({ ...KHUON, nguon: "khuon_mau", can_cu })?.can_cu, []);
});
kiem("`can_cu`: dòng lành giữ thứ tự; dòng khung (khop_tai_id null) và dòng điều", () => {
  const DONG_KHUNG = {
    nhan: "Căn cứ Bộ luật Dân sự số 91/2015/QH13 ngày 24 tháng 11 năm 2015;",
    doc_id: "91-2015",
    khop_tai_id: null,
    dieu: null,
  };
  const DONG_DIEU = {
    nhan: "Điều 3. Giá thuê — 91/2015/QH13 > Điều 481",
    doc_id: "91-2015",
    khop_tai_id: 4812,
    dieu: 3,
  };
  const k = khuonHopLe({
    ...KHUON,
    nguon: "khuon_mau",
    can_cu: [DONG_KHUNG, { ...DONG_DIEU, la: 1 }, { nhan: "Căn cứ X;", doc_id: "x" }],
  });
  assert.deepEqual(k?.can_cu, [
    DONG_KHUNG,
    DONG_DIEU,
    { nhan: "Căn cứ X;", doc_id: "x", khop_tai_id: null, dieu: null },
  ]);
});
kiem("`can_cu`: dòng dị dạng bị BỎ từng dòng, không cả danh sách (fail-closed)", () => {
  const lanh = { nhan: "Căn cứ;", doc_id: "d", khop_tai_id: 7, dieu: 1 };
  const k = khuonHopLe({
    ...KHUON,
    nguon: "khuon_mau",
    can_cu: [
      { ...lanh, doc_id: 91 },
      { ...lanh, doc_id: "" },
      { ...lanh, doc_id: undefined },
      { ...lanh, nhan: "" },
      { ...lanh, nhan: 3 },
      { ...lanh, khop_tai_id: "7" },
      { ...lanh, khop_tai_id: 7.5 },
      { ...lanh, khop_tai_id: -1 },
      { ...lanh, dieu: "1" },
      { ...lanh, dieu: 0 },
      "không phải dòng",
      null,
      lanh,
    ],
  });
  assert.deepEqual(k?.can_cu, [lanh]);
});
kiem("`can_cu`: dòng trùng (doc_id, dieu) giữ dòng ĐẦU — cặp đó là khoá của danh sách", () => {
  const khung = { nhan: "Căn cứ A;", doc_id: "a", khop_tai_id: null, dieu: null };
  const dieu = { nhan: "Điều 1. X — A > Điều 2", doc_id: "a", khop_tai_id: 9, dieu: 1 };
  const k = khuonHopLe({
    ...KHUON,
    nguon: "khuon_mau",
    can_cu: [khung, dieu, { ...khung, nhan: "Căn cứ A (lặp);" }, { ...dieu, khop_tai_id: 10 }],
  });
  assert.deepEqual(k?.can_cu, [khung, dieu]);
});

// ─────────────────────────────────────────────────────────── laTrangAnh
const TRANG = {
  kho: [
    [595.3, 841.9],
    [612, 792],
  ],
  trang: ["iVBORw0KGgo=", "AAAA"],
};
kiem("trang hợp lệ (A4 + Letter) được nhận", () => {
  assert.equal(laTrangAnh(TRANG), true);
});
kiem("số khổ khác số ảnh, hay rỗng → từ chối cả payload", () => {
  assert.equal(laTrangAnh({ ...TRANG, trang: ["AAAA"] }), false);
  assert.equal(laTrangAnh({ kho: [], trang: [] }), false);
  assert.equal(laTrangAnh({ kho: TRANG.kho }), false);
  assert.equal(laTrangAnh(null), false);
});
kiem("khổ ngoài (0, 14400] pt hay sai hình dạng → từ chối", () => {
  for (const kho of [[0, 842], [-1, 842], [595, 14401], ["595", 842], [595], [595, 842, 1]])
    assert.equal(laTrangAnh({ kho: [kho], trang: ["AAAA"] }), false, JSON.stringify(kho));
  assert.equal(laTrangAnh({ kho: [[14400, 14400]], trang: ["AAAA"] }), true, "biên trên nằm trong");
});
kiem("ảnh không phải base64 trần → từ chối (không gì lạ ghép được vào `data:`)", () => {
  for (const b of ["", "data:image/png;base64,AAAA", '"><img src=x>', "AA AA", 7])
    assert.equal(laTrangAnh({ kho: [[595, 842]], trang: [b] }), false, String(b));
});

// ─────────────────────────────────────────────── nhãn và giá trị hiển thị
kiem("nhãn bỏ dấu hai chấm cuối; nhãn rỗng → 'chỗ trống', không bịa mã 'Ô 3.1'", () => {
  assert.equal(nhanO(o({ nhan: "Họ và tên:" })), "Họ và tên");
  assert.equal(nhanO(o({ nhan: " Ngày :: " })), "Ngày");
  assert.equal(nhanO(o({ don_vi: 3, so: 1, nhan: "" })), "chỗ trống");
  assert.equal(nhanO(o({ don_vi: 3, so: 1, nhan: "  :  " })), "chỗ trống");
});
kiem("giá trị hiển thị: ô tab mang dấu cách đầu thì cắt; chưa điền → rỗng", () => {
  assert.equal(giaTriHienThi(o({ kieu: "tab", gia_tri: " Nguyễn Văn A" })), "Nguyễn Văn A");
  assert.equal(giaTriHienThi(o({ gia_tri: null })), "");
  assert.equal(khoaO(o({ don_vi: 12, so: 3 })), "12.3");
});
kiem("nút phủ chỗ trống đọc lên việc, tên chỗ và giá trị đang có", () => {
  assert.equal(
    nhanNutDien(o({ nhan: "Họ và tên:", gia_tri: null })),
    "Điền: Họ và tên — còn trống",
  );
  assert.equal(
    nhanNutDien(o({ nhan: "", gia_tri: " Hà Nội" })),
    "Điền: chỗ trống — đang là “Hà Nội”",
  );
});
kiem("chữ đã gõ mà chưa lưu được đọc lên; gõ lại đúng giá trị cũ thì không", () => {
  const daDien = o({ nhan: "Email", gia_tri: " a@b.vn" });
  assert.equal(nhanNutDien(daDien, " x@y.vn "), "Điền: Email — chưa lưu “x@y.vn”");
  assert.equal(nhanNutDien(daDien, ""), "Điền: Email — chưa lưu, sẽ để trống");
  assert.equal(nhanNutDien(daDien, "a@b.vn "), "Điền: Email — đang là “a@b.vn”");
  assert.equal(nhanNutDien(daDien, undefined), "Điền: Email — đang là “a@b.vn”");
});
kiem("lượt lưu đang chờ máy chủ được đọc lên là 'đang lưu', không phải 'chưa lưu'", () => {
  const daDien = o({ nhan: "Email", gia_tri: " a@b.vn" });
  assert.equal(nhanNutDien(daDien, " x@y.vn ", true), "Điền: Email — đang lưu “x@y.vn”");
  assert.equal(nhanNutDien(daDien, "", true), "Điền: Email — đang lưu: để trống");
  assert.equal(
    nhanNutDien(daDien, "a@b.vn", true),
    "Điền: Email — đang là “a@b.vn”",
    "chữ đang lưu trùng giá trị đã lưu: không có gì đang đổi",
  );
});
kiem("dòng phụ thẻ khuôn: số trang và số chỗ ĐÃ điền (bỏ null và khoảng trắng)", () => {
  const k = khuonHopLe(KHUON)!;
  assert.equal(phuDeKhuon(k), "Biểu mẫu · 2 trang · đã điền 2 chỗ");
  assert.equal(
    phuDeKhuon({
      nguon: "tai_len",
      so_trang: 1,
      cho_trong: [o({ gia_tri: "  " }), o({ gia_tri: null })],
    }),
    "Biểu mẫu · 1 trang · đã điền 0 chỗ",
  );
});
kiem(
  "dòng phụ thẻ khuôn MẪU: 'Bản thảo', đếm chỗ CÒN trống — không 'Biểu mẫu' người dùng chưa tải lên",
  () => {
    const k = khuonHopLe({ ...KHUON, nguon: "khuon_mau" })!;
    assert.equal(phuDeKhuon(k), "Bản thảo · 2 trang · còn 1 chỗ trống");
    assert.equal(
      phuDeKhuon({
        nguon: "khuon_mau",
        so_trang: 3,
        cho_trong: [o({ gia_tri: "  " }), o({ gia_tri: null }), o({ gia_tri: "A" })],
      }),
      "Bản thảo · 3 trang · còn 2 chỗ trống",
    );
  },
);

// ─────────────────────────────────────────────────────────────── oDaDoi
// Chữ gõ trên trang mà chưa lưu xong (bị từ chối, hay còn đang gõ): tải tệp lúc
// đó là tải một tệp thiếu chữ ấy, nên nơi gọi chặn tải theo đúng danh sách này.
const CT = khuonHopLe(KHUON)!.cho_trong;
kiem("không gõ gì → không gửi gì", () => {
  assert.deepEqual(oDaDoi(CT, {}), []);
});
kiem("chỉ ô đổi được gửi, giá trị NGUYÊN chữ người dùng gõ", () => {
  assert.deepEqual(oDaDoi(CT, { "1.1": "  Hà Nội ", "0.0": "Nguyễn Văn Ánh" }), [
    { don_vi: 1, cho_trong: 1, gia_tri: "  Hà Nội " },
  ]);
});
kiem("gõ lại đúng giá trị đang có (ô tab không dấu cách đầu) → không đổi", () => {
  assert.deepEqual(oDaDoi(CT, { "1.0": "a@b.vn" }), []);
  assert.deepEqual(oDaDoi(CT, { "0.0": " Nguyễn Văn Ánh  " }), []);
});
kiem("xoá trắng một ô đã điền gửi '' (gỡ ô); ô chưa điền để trống → không đổi", () => {
  assert.deepEqual(oDaDoi(CT, { "0.0": "", "1.1": "   " }), [
    { don_vi: 0, cho_trong: 0, gia_tri: "" },
  ]);
});
kiem("khoá không phải ô của phiên bản này bị bỏ; thứ tự là thứ tự ĐỌC", () => {
  assert.deepEqual(oDaDoi(CT, { "9.9": "lạ", "1.1": "B", "0.0": "A" }), [
    { don_vi: 0, cho_trong: 0, gia_tri: "A" },
    { don_vi: 1, cho_trong: 1, gia_tri: "B" },
  ]);
});

// ──────────────────────────────────────────── chiGiuThayDoi / boDaGui
kiem("Lùi: ô đã chạm mà KHÔNG đổi so với bản bị bỏ rơi khỏi chữ đang gõ", () => {
  // "0.0" gõ lại đúng giá trị của bản sắp bị bỏ: giữ lại thì sau khi lùi nó
  // thành "đổi" và một lần Lưu áp lại chữ của bản đã bỏ.
  assert.deepEqual(chiGiuThayDoi(CT, { "0.0": "Nguyễn Văn Ánh ", "1.1": " Hà Nội" }), {
    "1.1": " Hà Nội",
  });
  assert.deepEqual(chiGiuThayDoi(CT, { "9.9": "lạ" }), {}, "khoá không phải ô của bản này bị bỏ");
  assert.deepEqual(chiGiuThayDoi(CT, {}), {});
});
kiem("lưu xong: chỉ bỏ ô đã gửi ĐÚNG chữ đó; ô gõ tiếp trong lúc lưu còn nguyên", () => {
  const gui = [
    { don_vi: 0, cho_trong: 0, gia_tri: "A" },
    { don_vi: 1, cho_trong: 1, gia_tri: "B" },
  ];
  assert.deepEqual(boDaGui({ "0.0": "A", "1.1": "B2", "1.0": "x" }, gui), {
    "1.1": "B2",
    "1.0": "x",
  });
  assert.deepEqual(boDaGui({ "0.0": "A", "1.1": "B" }, gui), {});
});

// ─────────────────────────────────────────── oHopLe — chỗ trống trên ảnh trang
const KHO: [number, number][] = [
  [595, 842],
  [612, 792],
];
const oTho = (p: Record<string, unknown>) => ({
  don_vi: 0,
  so: 0,
  trang: 0,
  hop: [100, 200, 300, 214],
  nhan: "Họ và tên",
  gia_tri: null,
  ...p,
});
kiem("payload không mang `o` (máy chủ cũ) → null; mảng rỗng → []", () => {
  assert.equal(oHopLe(undefined, KHO), null);
  assert.equal(oHopLe({ a: 1 }, KHO), null);
  assert.deepEqual(oHopLe([], KHO), []);
});
kiem("ô lành đi qua đúng hình dạng, giữ thứ tự đọc, khoá lạ không lọt", () => {
  const ra = oHopLe(
    [oTho({ la: 1 }), oTho({ don_vi: 1, trang: 1, hop: [10, 20, 30, 40], gia_tri: " x" })],
    KHO,
  );
  assert.deepEqual(ra, [
    { don_vi: 0, so: 0, trang: 0, hop: [100, 200, 300, 214], nhan: "Họ và tên", gia_tri: null },
    { don_vi: 1, so: 0, trang: 1, hop: [10, 20, 30, 40], nhan: "Họ và tên", gia_tri: " x" },
  ]);
});
kiem("ô dị dạng bị BỎ; ô trùng (don_vi, so) giữ ô ĐẦU", () => {
  const ra = oHopLe(
    [
      oTho({ don_vi: -1 }),
      oTho({ so: "0" }),
      oTho({ nhan: 3 }),
      oTho({ gia_tri: 5 }),
      "lạ",
      oTho({ don_vi: 2, gia_tri: "đầu" }),
      oTho({ don_vi: 2, gia_tri: "sau" }),
    ],
    KHO,
  );
  assert.deepEqual(
    ra?.map((x) => [x.don_vi, x.gia_tri]),
    [[2, "đầu"]],
  );
});
kiem("vị trí không tin được → ô vẫn điền được, chỉ 'chưa định vị' (trang/hop null)", () => {
  const hong = [
    oTho({ trang: null, hop: null }),
    oTho({ so: 1, trang: 2 }), // ngoài `kho`
    oTho({ so: 2, trang: 0.5 }),
    oTho({ so: 3, hop: [300, 200, 100, 214] }), // hộp ngược
    oTho({ so: 4, hop: [100, 200, 600, 214] }), // tràn bề rộng trang 0 (595)
    oTho({ so: 5, hop: [100, 200, 300] }),
    oTho({ so: 6, hop: [100, 200, 300, Number.NaN] }),
    oTho({ so: 7, hop: null }),
    oTho({ so: 8, trang: 1, hop: [-1, 0, 10, 10] }),
  ];
  const ra = oHopLe(hong, KHO)!;
  assert.equal(ra.length, hong.length, "không ô nào bị bỏ vì vị trí");
  for (const x of ra) assert.deepEqual([x.trang, x.hop], [null, null], `so ${x.so}`);
  assert.deepEqual(oHopLe([oTho({ trang: 1, hop: [0, 0, 612, 792] })], KHO)?.[0]?.trang, 1);
});

// ─────────────────────────────────────── viTriO — pt → vị trí trên ảnh trang
kiem("pt → phần trăm khổ trang; nhân bề rộng ảnh đang vẽ ra đúng pt × (W / kho[0]) px", () => {
  const v = viTriO([119, 210.5, 297.5, 227.34], [595, 842]);
  assert.ok(Math.abs(v.trai - 20) < 1e-9 && Math.abs(v.rong - 30) < 1e-9);
  assert.ok(Math.abs(v.tren - 25) < 1e-9 && Math.abs(v.cao - 2) < 1e-9);
  for (const W of [793.33, 400, 1190]) {
    const tiLe = W / 595;
    const H = W * (842 / 595); // ảnh giữ đúng tỉ lệ khổ trang
    const px = (phanTram: number, canh: number) => (phanTram / 100) * canh;
    assert.ok(Math.abs(px(v.trai, W) - 119 * tiLe) < 1e-6, `left @${W}`);
    assert.ok(Math.abs(px(v.rong, W) - 178.5 * tiLe) < 1e-6, `width @${W}`);
    assert.ok(Math.abs(px(v.tren, H) - 210.5 * tiLe) < 1e-6, `top @${W}`);
    assert.ok(Math.abs(px(v.cao, H) - 16.84 * tiLe) < 1e-6, `height @${W}`);
    // cqw = 1% bề rộng trang: cỡ chữ = 80% chiều cao hộp, theo cùng tỉ lệ.
    assert.ok(Math.abs(px(v.coChu, W) - 16.84 * 0.8 * tiLe) < 1e-6, `font @${W}`);
  }
});

// ──────────────────────────────────────────── oKeTiep — Tab theo thứ tự đọc
kiem("Tab/Shift+Tab: chỗ kế/trước theo thứ tự đọc; hai đầu và khoá lạ → null", () => {
  const ds = [o({ don_vi: 0, so: 0 }), o({ don_vi: 0, so: 1 }), o({ don_vi: 3, so: 0 })];
  assert.equal(oKeTiep(ds, "0.0", 1), "0.1");
  assert.equal(oKeTiep(ds, "0.1", 1), "3.0");
  assert.equal(oKeTiep(ds, "3.0", -1), "0.1");
  assert.equal(oKeTiep(ds, "3.0", 1), null);
  assert.equal(oKeTiep(ds, "0.0", -1), null);
  assert.equal(oKeTiep(ds, "9.9", 1), null);
  assert.equal(oKeTiep([], "0.0", 1), null);
});

// ─────────────────────────────────────────── tên tệp từ Content-Disposition
const DAU_MAY_CHU =
  "attachment; filename=\"BM.M05. Giay tiep nhan - da dien.docx\"; filename*=UTF-8''BM.M05.%20Gi%E1%BA%A5y%20ti%E1%BA%BFp%20nh%E1%BA%ADn%20%281%29%20-%20%C4%91%C3%A3%20%C4%91i%E1%BB%81n.docx";
kiem("filename* (RFC 5987, UTF-8) thắng filename ASCII", () => {
  assert.equal(
    tenTepTuContentDisposition(DAU_MAY_CHU),
    "BM.M05. Giấy tiếp nhận (1) - đã điền.docx",
  );
  assert.equal(tenTepTuContentDisposition("attachment; FILENAME*=utf-8''x%20y.pdf"), "x y.pdf");
});
kiem("không có filename* (hay hỏng / không phải UTF-8) → filename", () => {
  assert.equal(tenTepTuContentDisposition('attachment; filename="a b.pdf"'), "a b.pdf");
  assert.equal(tenTepTuContentDisposition("attachment; filename=ab.pdf"), "ab.pdf");
  assert.equal(
    tenTepTuContentDisposition("attachment; filename=\"du.pdf\"; filename*=UTF-8''%E0%A4%A"),
    "du.pdf",
  );
  assert.equal(
    tenTepTuContentDisposition("attachment; filename=\"du.pdf\"; filename*=ISO-8859-1''%E9.pdf"),
    "du.pdf",
  );
  assert.equal(tenTepTuContentDisposition('attachment; filename="a\\"b.pdf"'), 'a"b.pdf');
});
kiem("không đường dẫn, không ký tự điều khiển; không có tên → null", () => {
  assert.equal(
    tenTepTuContentDisposition("attachment; filename*=UTF-8''..%2F..%2Fetc%2Fpasswd"),
    "passwd",
  );
  assert.equal(tenTepTuContentDisposition('attachment; filename="a\\\\b.docx"'), "b.docx");
  assert.equal(tenTepTuContentDisposition("attachment; filename*=UTF-8''a%0D%0Ab.pdf"), "ab.pdf");
  for (const h of [
    null,
    "",
    "attachment",
    'inline; filename=""',
    "attachment; filename*=UTF-8''%2F",
  ])
    assert.equal(tenTepTuContentDisposition(h), null, String(h));
});

// ──────────────────────────────────────────────── đường dẫn và câu lỗi
kiem("đường dẫn tính từ gốc API (không lặp /api/v1), mã hoá id, phien_ban tường minh", () => {
  assert.equal(DUONG_DAN_KHUON.trangTaiLieu("a b"), "/tai-lieu/a%20b/trang");
  assert.equal(DUONG_DAN_KHUON.trangBanThao("x/y", 3), "/ban-thao/x%2Fy/trang?phien_ban=3");
  assert.equal(
    DUONG_DAN_KHUON.taiXuong("b1", "pdf", 4),
    "/ban-thao/b1/tai-xuong?dang=pdf&phien_ban=4",
  );
  assert.equal(DUONG_DAN_KHUON.oDien("b1"), "/ban-thao/b1/o-dien");
  assert.equal(DUONG_DAN_KHUON.moBanThao("v1"), "/tai-lieu/v1/ban-thao");
  assert.equal(DUONG_DAN_KHUON.docLai("v1"), "/tai-lieu/v1/doc-lai");
  for (const d of [
    DUONG_DAN_KHUON.trangTaiLieu("v"),
    DUONG_DAN_KHUON.trangBanThao("b", 1),
    DUONG_DAN_KHUON.taiXuong("b", "docx", 1),
  ])
    assert.ok(!d.startsWith("/api/v1"), d);
});
kiem("503 = máy chủ bận, cho thử lại; 404 = không hiện được, không thử lại", () => {
  const banThao = DUONG_DAN_KHUON.trangBanThao("b", 2);
  const banTaiLen = DUONG_DAN_KHUON.trangTaiLieu("v");
  const ban = loiTrang(
    { kind: "server_error", status: 503, message: "Máy chủ KLAW gặp lỗi khi xử lý." },
    banThao,
  );
  assert.equal(ban.thuLai, true);
  assert.match(ban.cau, /bận/);
  const mat = loiTrang({ kind: "not_found", status: 404, message: "Không tìm thấy" }, banThao);
  assert.equal(mat.thuLai, false);
  assert.match(mat.cau, /không hiển thị được phiên bản này/i);
  // Cùng khung trang vẽ bản thảo KLAW dựng (khuôn mẫu): câu không được nói về
  // một tệp người dùng chưa từng tải lên.
  assert.doesNotMatch(mat.cau, /tải lên/i);
  // Khung "Bản tải lên" không có phiên bản nào: câu 404 của nó không được nhắc tới phiên bản.
  const matTaiLen = loiTrang(
    { kind: "not_found", status: 404, message: "Không tìm thấy" },
    banTaiLen,
  );
  assert.equal(matTaiLen.thuLai, false);
  assert.match(matTaiLen.cau, /bản tải lên/i);
  assert.doesNotMatch(matTaiLen.cau, /phiên bản|dựng/i);
  for (const c of [mat.cau, matTaiLen.cau]) assert.doesNotMatch(c, /bản gốc|tài liệu gốc/i);
  const hetGio = loiTrang({ kind: "timeout", message: "Máy chủ KLAW không trả lời." }, banTaiLen);
  assert.deepEqual(hetGio, { cau: "Máy chủ KLAW không trả lời.", thuLai: true });
});

console.log(`kiem-khuon-goc: ${dat}/${tong} đạt`);
