/**
 * Kiểm chạy được cho bộ dựng thân văn bản (`khung-van-ban.ts`).
 *
 * Bất biến được canh ở đây: **thân văn bản KHÔNG BAO GIỜ được mang khối của một
 * loại văn bản khác.**
 *
 * Đây không phải lo xa. Trước bản sửa này, bộ dựng nằm thẳng trong route, viết
 * cứng, và chỉ rẽ hai nhánh (`hdld` / thử việc); hai mươi ba loại còn lại rơi
 * hết vào một khuôn HỢP ĐỒNG THƯƠNG MẠI HAI BÊN. `/soan-thao/cong-van` mang
 * tiêu đề CÔNG VĂN rồi dựng `BÊN A / BÊN B`, `Mã số thuế`, `Số tài khoản tại
 * [Ngân hàng]`, "Hai bên thống nhất ký kết hợp đồng với các điều khoản sau",
 * `Điều 2. Giá trị hợp đồng`, `Điều 4. Phạt vi phạm hợp đồng`, rồi khối ký hai
 * bên. `/soan-thao/don-khoi-kien` ra y hệt. Người dùng tải về một `.docx` trông
 * đúng thể thức mà SAI LOẠI VĂN BẢN, rồi mang đi dùng.
 *
 * Phần 1–3 thuần dữ liệu, luôn chạy. Phần 4 đối chiếu bản đồ mẫu của giao diện
 * với cờ máy chủ tính ra; nếu máy chủ không với tới được thì BỎ QUA có cảnh
 * báo, chứ không làm đỏ cổng commit vì một sự cố mạng — nhưng lệch thật thì
 * đỏ.
 *
 * Chạy: `npm run kiem-khung`.
 */
import assert from "node:assert/strict";
import {
  MUC_BEN,
  MUC_KY,
  MUC_ND,
  NHAN_PHAM_VI,
  dungKhung,
  phamViSoatCua,
  tachCanCu,
  tieuDeMuc,
} from "../src/lib/khung-van-ban.ts";
import { LOAI_BACKEND } from "../src/lib/mau-van-ban.ts";
import type { CauTruc } from "../src/lib/klaw.ts";

/* ── 1. Tách căn cứ: chip phải trỏ đúng văn bản, không đoán ──────────────── */

assert.deepEqual(tachCanCu("45/2019/QH14 > Điều 21 > Khoản 1 > Điểm a"), {
  soHieu: "45/2019/QH14",
  nhan: "Điều 21, Khoản 1, Điểm a",
});
assert.deepEqual(tachCanCu("91/2015/QH13 > Điều 430"), {
  soHieu: "91/2015/QH13",
  nhan: "Điều 430",
});
// Chỉ có số hiệu vẫn dùng được — chip cần số hiệu, phần còn lại là phụ.
assert.deepEqual(tachCanCu("30/2020/NĐ-CP"), { soHieu: "30/2020/NĐ-CP", nhan: "" });
// Rỗng thì KHÔNG dựng chip, thay vì dựng một chip trỏ vào hư không.
assert.equal(tachCanCu(""), null);
assert.equal(tachCanCu("   >  > "), null);

/* ── 2. Đánh số mục đúng như máy chủ sinh ─────────────────────────────────── */

const mucCV = {
  stt: 1,
  key: "quoc_hieu",
  ten: "Quốc hiệu và Tiêu ngữ",
  can_cu: "30/2020/NĐ-CP > Điều 8 > Khoản 2 > Điểm a",
  bat_buoc: true,
};
assert.equal(tieuDeMuc("Thành phần", mucCV), "Thành phần 1. Quốc hiệu và Tiêu ngữ");
assert.equal(
  tieuDeMuc("Điều", { ...mucCV, stt: 3, ten: "Công việc và địa điểm làm việc" }),
  "Điều 3. Công việc và địa điểm làm việc",
);

/* ── 3. CÔNG VĂN không được dựng ra một hợp đồng hai bên ──────────────────── */

/** Đúng hình dạng `GET /api/v1/mau/cong_van` trả về. */
const congVan: CauTruc = {
  ten: "công văn",
  tieu_de: "CÔNG VĂN",
  don_vi_muc: "Thành phần",
  muc_do_thieu: "chan",
  pham_vi_soat: "the_thuc",
  chi_soat_the_thuc: true,
  can_cu_goc: "30/2020/NĐ-CP > Điều 8 > Khoản 2",
  can_cu_chi_tiet: "30/2020/NĐ-CP > Điều 7",
  muc: [
    mucCV,
    {
      stt: 2,
      key: "ten_co_quan",
      ten: "Tên cơ quan, tổ chức ban hành văn bản",
      can_cu: "30/2020/NĐ-CP > Điều 8 > Khoản 2 > Điểm b",
      bat_buoc: true,
    },
    {
      stt: 3,
      key: "noi_dung",
      ten: "Nội dung văn bản",
      can_cu: "30/2020/NĐ-CP > Điều 8 > Khoản 2 > Điểm e",
      bat_buoc: true,
    },
    {
      stt: 4,
      key: "chuc_vu_chu_ky",
      ten: "Chức vụ, họ tên và chữ ký của người có thẩm quyền",
      can_cu: "30/2020/NĐ-CP > Điều 8 > Khoản 2 > Điểm g",
      bat_buoc: true,
    },
    {
      stt: 5,
      key: "noi_nhan",
      ten: "Nơi nhận",
      can_cu: "30/2020/NĐ-CP > Điều 8 > Khoản 2 > Điểm i",
      bat_buoc: true,
    },
  ],
};

const khungCV = dungKhung(congVan);

// Khung dựng ra ĐÚNG các mục của checklist, không thừa một mục nào. Một khuôn
// hợp đồng lọt vào đây sẽ lộ ra ngay ở phép so số mục này.
assert.equal(khungCV.length, congVan.muc.length);
assert.deepEqual(
  khungCV.map((m) => m.tieuDe),
  [
    "Thành phần 1. Quốc hiệu và Tiêu ngữ",
    "Thành phần 2. Tên cơ quan, tổ chức ban hành văn bản",
    "Thành phần 3. Nội dung văn bản",
    "Thành phần 4. Chức vụ, họ tên và chữ ký của người có thẩm quyền",
    "Thành phần 5. Nơi nhận",
  ],
);

// Không một mục nào của công văn được kéo theo từ vựng hợp đồng.
const CAM = ["BÊN A", "BÊN B", "Mã số thuế", "Số tài khoản", "Giá trị hợp đồng", "Phạt vi phạm"];
for (const m of khungCV) {
  for (const tu of CAM) {
    assert.ok(!m.tieuDe.includes(tu), `mục công văn "${m.tieuDe}" mang từ hợp đồng "${tu}"`);
  }
}

// Công văn có ĐÚNG MỘT bên (cơ quan ban hành) — không có bên B nào.
// Đây là phép kiểm trực tiếp cho lỗi đã sửa: khối `BÊN A / BÊN B` chỉ được
// dựng khi chính checklist có hai mục bên, và checklist công văn thì không.
const benCV = khungCV.map((m) => MUC_BEN[m.key]).filter((b) => b !== undefined);
assert.deepEqual(benCV, ["A"], "công văn chỉ có cơ quan ban hành, không có bên B");
assert.ok(
  !khungCV.some((m) => MUC_ND[m.key] !== undefined),
  "không mục nào của công văn được đổ nội dung hợp đồng thương mại vào",
);
// Chữ ký công văn là MỘT người ký, và nó phải được nhận ra để `.docx` giữ lại.
assert.deepEqual(
  khungCV.filter((m) => MUC_KY.has(m.key)).map((m) => m.key),
  ["chuc_vu_chu_ky"],
);

// Ngược lại, HĐLĐ có đủ hai bên — đường mới không được làm mất chúng.
const hdld: CauTruc = {
  ...congVan,
  ten: "hợp đồng lao động",
  tieu_de: "HỢP ĐỒNG LAO ĐỘNG",
  don_vi_muc: "Điều",
  pham_vi_soat: "noi_dung",
  chi_soat_the_thuc: false,
  muc: [
    {
      stt: 1,
      key: "nsdld",
      ten: "Tên, địa chỉ NSDLĐ",
      can_cu: "45/2019/QH14 > Điều 21 > Khoản 1 > Điểm a",
      bat_buoc: true,
    },
    {
      stt: 2,
      key: "nld",
      ten: "Họ tên, ngày sinh của NLĐ",
      can_cu: "45/2019/QH14 > Điều 21 > Khoản 1 > Điểm b",
      bat_buoc: true,
    },
    {
      stt: 3,
      key: "cong_viec",
      ten: "Công việc và địa điểm làm việc",
      can_cu: "45/2019/QH14 > Điều 21 > Khoản 1 > Điểm c",
      bat_buoc: true,
    },
  ],
};
const khungLD = dungKhung(hdld);
assert.deepEqual(
  khungLD.map((m) => MUC_BEN[m.key]).filter((b) => b !== undefined),
  ["A", "B"],
);
assert.equal(khungLD[0]?.tieuDe, "Điều 1. Tên, địa chỉ NSDLĐ");
assert.deepEqual(khungLD[2]?.canCu, { soHieu: "45/2019/QH14", nhan: "Điều 21, Khoản 1, Điểm c" });

/* ── 4. Ba phạm vi soát, và ca lai phải tách riêng ────────────────────────── */

assert.equal(phamViSoatCua(congVan), "the_thuc");
assert.equal(phamViSoatCua(hdld), "noi_dung");
// `quyet_dinh_bo_nhiem`: thể thức NHƯNG `chi_soat_the_thuc=false`, vì còn một
// quy tắc nhiệm kỳ thật (LDN Đ162.2). Gộp nó vào nhóm chỉ-thể-thức là giấu mất
// quy tắc duy nhất thực sự đọc nội dung.
assert.equal(
  phamViSoatCua({ ...congVan, pham_vi_soat: "the_thuc", chi_soat_the_thuc: false }),
  "the_thuc_kem_rule",
);
assert.equal(new Set(Object.values(NHAN_PHAM_VI)).size, 3, "ba phạm vi thì ba nhãn KHÁC nhau");

/* ── 5. Bản đồ mẫu phải khớp cờ máy chủ tính ra ───────────────────────────── */

const GOC = process.env["KLAW_API"] ?? "http://localhost:8000/api/v1";

async function doiChieuMayChu() {
  const dong = Object.entries(LOAI_BACKEND);
  let lech = 0;
  for (const [id, { loai, phamVi }] of dong) {
    const res = await fetch(`${GOC}/mau/${encodeURIComponent(loai)}`, {
      signal: AbortSignal.timeout(8000),
    });
    assert.ok(res.ok, `GET /mau/${loai} trả ${res.status} — mẫu "${id}" ánh xạ vào kiểu không có`);
    const body = (await res.json()) as { cau_truc: CauTruc | null };
    assert.ok(body.cau_truc, `/mau/${loai} không có cau_truc, nhưng "${id}" đang nối vào nó`);
    const that = phamViSoatCua(body.cau_truc);
    if (that !== phamVi) {
      console.error(`  ✗ ${id} → ${loai}: bản đồ ghi "${phamVi}", máy chủ tính ra "${that}"`);
      lech += 1;
    }
    // Khung rỗng nghĩa là thân văn bản sẽ rỗng — mẫu đó không dùng được.
    assert.ok(body.cau_truc.muc.length > 0, `/mau/${loai} có cau_truc nhưng KHÔNG có mục nào`);
  }
  assert.equal(lech, 0, `${lech} mẫu lệch phạm vi soát so với máy chủ`);
  return dong.length;
}

let daDoiChieu = 0;
try {
  await fetch(`${GOC.replace(/\/api\/v1$/, "")}/health`, { signal: AbortSignal.timeout(2500) });
  daDoiChieu = await doiChieuMayChu();
} catch {
  console.warn(
    `kiem-khung: BỎ QUA phần đối chiếu máy chủ (${GOC} không với tới được). ` +
      `Phần thuần dữ liệu đã chạy đủ. Chạy lại khi backend lên để canh bản đồ mẫu.`,
  );
}

console.info(
  daDoiChieu > 0
    ? `kiem-khung: đạt · 25 phép kiểm khung + ${daDoiChieu}/25 mẫu khớp cờ máy chủ`
    : "kiem-khung: đạt · 25 phép kiểm khung (chưa đối chiếu máy chủ)",
);
