/**
 * Khuôn gốc ở giao diện (kế hoạch `khuon-goc-dien-tai-cho.md`, P5) — phần
 * THUẦN: cửa vào `khuon` của bản thảo, cửa vào tải trang, nhãn và phần đổi của
 * bảng ô điền, tên tệp tải về, đường dẫn và câu lỗi của khung trang.
 *
 * Vì sao đáng kiểm riêng: `khuonHopLe` quyết định giao diện vẽ trang hay A4
 * HTML, và mỗi ô nó bỏ sót là một ô người dùng không điền được; `oDaDoi` quyết
 * định lần lưu gửi ĐÚNG những ô nào — gửi thừa là một phiên bản vô ích tính vào
 * trần sửa, gửi thiếu là chữ người dùng gõ biến mất.
 *
 * Chạy: `npm run kiem-khuon-goc`.
 */
import assert from "node:assert/strict";
import { khuonHopLe, laTrangAnh, type ChoTrongKhuon } from "../src/lib/klaw.ts";
import {
  boDaGui,
  chiGiuThayDoi,
  DUONG_DAN_KHUON,
  giaTriHienThi,
  khoaO,
  loiTrang,
  nhanO,
  oDaDoi,
  tenTepTuContentDisposition,
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
kiem("khuôn hợp lệ đi qua nguyên hình dạng", () => {
  assert.deepEqual(khuonHopLe(KHUON), KHUON);
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
  assert.deepEqual(Object.keys(k ?? {}).sort(), ["cho_trong", "dinh_dang", "so_trang", "viec_id"]);
  assert.deepEqual(Object.keys(k?.cho_trong[0] ?? {}).sort(), [
    "don_vi",
    "gia_tri",
    "kieu",
    "nhan",
    "so",
  ]);
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
kiem("nhãn bỏ dấu hai chấm cuối, nhãn rỗng → 'Ô {don_vi}.{so}'", () => {
  assert.equal(nhanO(o({ nhan: "Họ và tên:" })), "Họ và tên");
  assert.equal(nhanO(o({ nhan: " Ngày :: " })), "Ngày");
  assert.equal(nhanO(o({ don_vi: 3, so: 1, nhan: "" })), "Ô 3.1");
  assert.equal(nhanO(o({ don_vi: 3, so: 1, nhan: "  :  " })), "Ô 3.1");
});
kiem("giá trị hiển thị: ô tab mang dấu cách đầu thì cắt; chưa điền → rỗng", () => {
  assert.equal(giaTriHienThi(o({ kieu: "tab", gia_tri: " Nguyễn Văn A" })), "Nguyễn Văn A");
  assert.equal(giaTriHienThi(o({ gia_tri: null })), "");
  assert.equal(khoaO(o({ don_vi: 12, so: 3 })), "12.3");
});

// ─────────────────────────────────────────────────────────────── oDaDoi
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
kiem("503 = máy chủ bận, cho thử lại; 404 = phiên bản không hiện được, không thử lại", () => {
  const ban = loiTrang({
    kind: "server_error",
    status: 503,
    message: "Máy chủ KLAW gặp lỗi khi xử lý.",
  });
  assert.equal(ban.thuLai, true);
  assert.match(ban.cau, /bận/);
  const mat = loiTrang({ kind: "not_found", status: 404, message: "Không tìm thấy tài liệu" });
  assert.equal(mat.thuLai, false);
  assert.match(mat.cau, /không hiển thị được/i);
  const hetGio = loiTrang({ kind: "timeout", message: "Máy chủ KLAW không trả lời." });
  assert.deepEqual(hetGio, { cau: "Máy chủ KLAW không trả lời.", thuLai: true });
});

console.log(`kiem-khuon-goc: ${dat}/${tong} đạt`);
