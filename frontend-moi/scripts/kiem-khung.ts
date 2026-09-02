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
  MUC_CA_BEN,
  MUC_CA_NHAN,
  MUC_CHI_TEN,
  MUC_KY,
  MUC_ND,
  NHAN_PHAM_VI,
  dungKhung,
  dungKhungHopDong,
  phamViSoatCua,
  tachCanCu,
  tieuDeMuc,
} from "../src/lib/khung-van-ban.ts";
import { LOAI_BACKEND, MAU } from "../src/lib/mau-van-ban.ts";
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
  la_hop_dong: false,
  khung_hop_dong: [],
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
// Cơ quan ban hành công văn chỉ in ĐÚNG CÁI TÊN. NĐ 30/2020 Điều 8 khoản 2
// điểm b không đòi mã số thuế, điện thoại hay người đại diện — những dòng ấy
// chỉ hợp đồng thương mại mới cần, và chúng chính là thứ vừa bị gỡ.
assert.ok(MUC_CHI_TEN.has("ten_co_quan"));
assert.ok(!MUC_CHI_TEN.has("nsdld"), "HĐLĐ vẫn cần địa chỉ và người giao kết (BLLĐ Đ21.1.a)");

// Người lao động là một THỂ NHÂN, luôn luôn. Nếu ô chọn của biểu mẫu quyết
// định được chỗ này thì mặc định "tổ chức" in ra một HĐLĐ ký với doanh nghiệp,
// kèm "Người đại diện theo pháp luật" ở đúng chỗ BLLĐ Đ21.1.b đòi ngày sinh và
// số CCCD.
assert.ok(MUC_CA_NHAN.has("nld"));
assert.ok(!MUC_CA_NHAN.has("nsdld"), "người sử dụng lao động thì có thể là tổ chức");

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

/* ── 3b. Khối hợp đồng: theo MẢNG trả về, không giả định hai phần tử ──────── */

const CAC_BEN = {
  stt: 1,
  key: "cac_ben",
  ten: "Thông tin các bên giao kết hợp đồng",
  can_cu: "91/2015/QH13 > Điều 385",
  bat_buoc: true,
};
const CHU_KY_HD = {
  stt: 2,
  key: "chu_ky",
  ten: "Chữ ký, đóng dấu của các bên",
  can_cu: "91/2015/QH13 > Điều 400 > Khoản 4",
  bat_buoc: true,
};

// `la_hop_dong=false` thì KHÔNG dựng gì thêm — công văn, đơn, quyết định, biên
// bản, nội quy, quy chế, bản tự khai, văn bản giải trình, và giấy uỷ quyền.
assert.equal(congVan.la_hop_dong, false);
assert.deepEqual(dungKhungHopDong(congVan), []);
// `null` là giá trị THẬT của máy chủ cho 15 loại không-hợp-đồng, không phải `[]`.
// Gọi `.map()` thẳng vào nó ném `TypeError` trên mọi công văn, đơn, quyết định.
assert.deepEqual(dungKhungHopDong({ ...congVan, khung_hop_dong: null }), []);

// Hợp đồng thường: hai mục, căn cứ lấy TỪ MẢNG chứ không viết cứng trong FE.
// Một `can_cu` sống trong FE không bao giờ đi qua cổng phân giải
// `provisions.duong_dan`; phục vụ từ server thì nó qua cổng.
{
  const hd = { ...hdld, la_hop_dong: true, khung_hop_dong: [CAC_BEN, CHU_KY_HD] };
  const k = dungKhungHopDong(hd);
  assert.deepEqual(
    k.map((m) => m.key),
    ["cac_ben", "chu_ky"],
  );
  assert.deepEqual(k[0]?.canCu, { soHieu: "91/2015/QH13", nhan: "Điều 385" });
  assert.deepEqual(k[1]?.canCu, { soHieu: "91/2015/QH13", nhan: "Điều 400, Khoản 4" });
  // Không đánh số: `stt` của mảng không phải số Điều của văn bản.
  assert.equal(k[0]?.tieuDe, CAC_BEN.ten);
  assert.ok(!k[0]?.tieuDe.startsWith("Điều"));
}

// CA MỘT PHẦN TỬ — `hop_dong_hop_tac`. Checklist ĐÃ CÓ `cac_ben` riêng (BLDS
// Đ505.2) và mục đó nằm trong mẫu số completeness, nên máy chủ chỉ gửi `chu_ky`
// kèm `stt=1`. Giả định hai phần tử sẽ vẽ "các bên" hai lần: một lần được tính
// vào tỷ lệ, một lần không.
{
  const hopTac = {
    ...hdld,
    la_hop_dong: true,
    muc: [
      {
        stt: 1,
        key: "muc_dich_thoi_han",
        ten: "Mục đích, thời hạn",
        can_cu: "91/2015/QH13 > Điều 504",
        bat_buoc: true,
      },
      {
        stt: 2,
        key: "cac_ben",
        ten: "Các bên hợp tác",
        can_cu: "91/2015/QH13 > Điều 505 > Khoản 2",
        bat_buoc: true,
      },
    ],
    khung_hop_dong: [{ ...CHU_KY_HD, stt: 1 }],
  };
  const k = dungKhungHopDong(hopTac);
  assert.equal(k.length, 1);
  assert.equal(k[0]?.key, "chu_ky");
  assert.ok(
    !k.some((m) => MUC_CA_BEN.has(m.key)),
    "khung KHÔNG được mang cac_ben khi checklist đã tự có",
  );
  // Mục `cac_ben` của checklist phải tự dựng được khối hai bên, nếu không thì
  // hợp đồng hợp tác mất hẳn phần các bên.
  const tuChecklist = dungKhung(hopTac).filter((m) => MUC_CA_BEN.has(m.key));
  assert.equal(tuChecklist.length, 1);
  assert.deepEqual(tuChecklist[0]?.canCu, { soHieu: "91/2015/QH13", nhan: "Điều 505, Khoản 2" });
  // Đúng MỘT nguồn dựng khối các bên — không đường nào vẽ hai lần.
  assert.equal(tuChecklist.length + k.filter((m) => MUC_CA_BEN.has(m.key)).length, 1);
}

// Khung KHÔNG được cộng vào số mục của checklist — mẫu số completeness là
// `cau_truc.muc`, và tỷ lệ giao diện phải khớp thứ `/soat` trả về.
{
  const hd = { ...hdld, la_hop_dong: true, khung_hop_dong: [CAC_BEN, CHU_KY_HD] };
  assert.equal(dungKhung(hd).length, hd.muc.length);
}

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

/* ── 4b. Mọi thẻ đều bấm tới được, và hai cặp dễ gộp phải tách ───────────── */

// Thẻ không có ánh xạ = mẫu bấm vào thì không soạn được. Ánh xạ không có thẻ =
// mẫu backend dựng được, soát được, mà KHÔNG AI BẤM TỚI ĐƯỢC — đúng chỗ
// `quy_che_dan_chu` và `hop_dong_uy_quyen` đã nằm im cho tới 2026-09-02.
{
  const idThe = new Set(MAU.map((m) => m.id));
  const idAnhXa = new Set(Object.keys(LOAI_BACKEND));
  assert.deepEqual(
    [...idAnhXa].filter((id) => !idThe.has(id)),
    [],
    "ánh xạ mồ côi: có ánh xạ mà không có thẻ",
  );
  assert.deepEqual(
    [...idThe].filter((id) => !idAnhXa.has(id)),
    [],
    "thẻ chưa nối: bấm vào sẽ không soạn được",
  );
  assert.equal(MAU.length, 27);
}

// HAI CẶP dễ gộp nhầm, và gộp là soát văn bản này bằng checklist văn bản kia.
//
// Quy chế nội bộ (nghĩa chung, thể thức NĐ 30/2020) ≠ quy chế dân chủ ở cơ sở
// (nội dung bắt buộc riêng, NĐ 145/2020 Đ37.2 a–g).
assert.notEqual(LOAI_BACKEND["quy-che-noi-bo"]?.loai, LOAI_BACKEND["quy-che-dan-chu-co-so"]?.loai);
assert.equal(LOAI_BACKEND["quy-che-noi-bo"]?.loai, "quy_che_noi_bo");
assert.equal(LOAI_BACKEND["quy-che-dan-chu-co-so"]?.loai, "quy_che_dan_chu");

// Giấy uỷ quyền là hành vi MỘT BÊN; hợp đồng uỷ quyền là thoả thuận HAI BÊN
// (BLDS Đ562). Backend trả `la_hop_dong=false` / `true` tương ứng, nên gộp
// chúng là dựng khối các bên và bảng ký hai cột lên một văn bản một bên.
assert.notEqual(LOAI_BACKEND["giay-uy-quyen"]?.loai, LOAI_BACKEND["hop-dong-uy-quyen"]?.loai);
assert.equal(LOAI_BACKEND["giay-uy-quyen"]?.loai, "giay_uy_quyen");
assert.equal(LOAI_BACKEND["hop-dong-uy-quyen"]?.loai, "hop_dong_uy_quyen");

/* ── 5. Bản đồ mẫu phải khớp cờ máy chủ tính ra ───────────────────────────── */

const GOC = process.env["KLAW_API"] ?? "http://localhost:8000/api/v1";

async function doiChieuMayChu() {
  const dong = Object.entries(LOAI_BACKEND);
  let lech = 0;
  let tongMuc = 0;
  let mucCoChiTiet = 0;
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
    // `la_hop_dong=false` PHẢI đi kèm khung rỗng, và ngược lại khung chỉ được
    // chứa hai khoá đã biết. `giay_uy_quyen` là ca canh chừng: nó có mục
    // `ben_*` nên mọi heuristic đều nhận nhầm là hợp đồng.
    // `null` là hợp lệ và là giá trị THẬT của 15 loại không-hợp-đồng; chỉ hợp
    // đồng mới bắt buộc có mảng.
    const kh = body.cau_truc.khung_hop_dong ?? [];
    if (!body.cau_truc.la_hop_dong) {
      assert.equal(kh.length, 0, `/mau/${loai} không phải hợp đồng mà vẫn có khung`);
    } else {
      assert.ok(
        Array.isArray(body.cau_truc.khung_hop_dong),
        `/mau/${loai} là hợp đồng mà khung không phải mảng`,
      );
      assert.ok(kh.length >= 1 && kh.length <= 2, `/mau/${loai} khung dài ${kh.length}`);
      for (const x of kh) {
        assert.ok(["cac_ben", "chu_ky"].includes(x.key), `khung lạ: ${x.key}`);
        assert.ok(tachCanCu(x.can_cu), `khung ${x.key} của ${loai} thiếu căn cứ`);
      }
      const khoaMuc = new Set(body.cau_truc.muc.map((m) => m.key));
      for (const x of kh) {
        assert.ok(!khoaMuc.has(x.key), `${loai}: "${x.key}" có ở CẢ checklist lẫn khung`);
      }
    }

    // Khung rỗng nghĩa là thân văn bản sẽ rỗng — mẫu đó không dùng được.
    assert.ok(body.cau_truc.muc.length > 0, `/mau/${loai} có cau_truc nhưng KHÔNG có mục nào`);

    for (const m of body.cau_truc.muc) {
      tongMuc += 1;
      if (m.can_cu_chi_tiet) mucCoChiTiet += 1;
    }
  }
  assert.equal(lech, 0, `${lech} mẫu lệch phạm vi soát so với máy chủ`);

  // Mốc cho câu cảnh báo "Căn cứ pháp lý chưa được đối chiếu" (LegalBits.tsx).
  // Đo 2026-09-02: mọi mục đều có `can_cu` dạng chuỗi, KHÔNG mục nào có
  // `can_cu_chi_tiet` — nên chú thích dưới từng điều vẫn là tham chiếu chưa
  // phân giải, và cảnh báo phải phủ cả thân văn bản chứ không riêng cấp thẻ.
  // Phép kiểm này đỏ = máy chủ đã bắt đầu phân giải căn cứ từng mục; lúc đó
  // thu hẹp câu cảnh báo lại cho đúng, đừng tắt phép kiểm.
  assert.equal(
    mucCoChiTiet,
    0,
    `${mucCoChiTiet}/${tongMuc} mục nay có can_cu_chi_tiet — máy chủ đã phân giải căn cứ, hãy sửa CanCuChuaKiemBanner cho khớp`,
  );
  return dong.length;
}

/**
 * CHỈ phép thăm dò mới được bọc try/catch.
 *
 * Bọc cả `doiChieuMayChu()` là biến một sai lệch THẬT thành dòng chữ "máy chủ
 * không với tới được" — cổng vẫn xanh, drift vẫn lọt, đúng kiểu thất bại thầm
 * lặng mà kiểm này sinh ra để chặn. Đã dính đúng một lần khi viết.
 */
let mayChuSong = false;
try {
  const res = await fetch(`${GOC.replace(/\/api\/v1$/, "")}/health`, {
    signal: AbortSignal.timeout(2500),
  });
  mayChuSong = res.ok;
} catch {
  mayChuSong = false;
}

let daDoiChieu = 0;
if (mayChuSong) {
  daDoiChieu = await doiChieuMayChu();
} else {
  console.warn(
    `kiem-khung: BỎ QUA phần đối chiếu máy chủ (${GOC} không với tới được). ` +
      `Phần thuần dữ liệu đã chạy đủ. Chạy lại khi backend lên để canh bản đồ mẫu.`,
  );
}

console.info(
  daDoiChieu > 0
    ? `kiem-khung: đạt · 25 phép kiểm khung + ${daDoiChieu}/${MAU.length} mẫu khớp cờ máy chủ`
    : "kiem-khung: đạt · 25 phép kiểm khung (chưa đối chiếu máy chủ)",
);
