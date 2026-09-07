/**
 * `dungLuoiHoatDong`/`mucCua`/`hangDuongTinh` (`lib/lich-hoat-dong.ts`): lệch
 * thứ Monday-start, xếp hạng tô mức, và lọc cửa sổ 365 ngày. `TZ=UTC` ép
 * trước MỌI thứ khác — bộ kiểm dùng getter GIỜ MÁY (`getFullYear`/`getMonth`/
 * `getDate`) trên một `homNay` cố định nên phải chạy dưới múi giờ cố định để
 * không lệ thuộc múi giờ của máy đang chạy `npm run kiem-lich-hoat-dong`.
 * Chạy: `npm run kiem-lich-hoat-dong`.
 */
process.env.TZ = "UTC";

import assert from "node:assert/strict";
import { dungLuoiHoatDong, mucCua, hangDuongTinh, SO_TUAN } from "../src/lib/lich-hoat-dong.ts";

// 2026-09-10 — thứ Năm (mondayStart = 3). Mốc CỐ ĐỊNH, không đọc đồng hồ.
const HOM_NAY = new Date(Date.UTC(2026, 8, 10));

// 1) Lưới luôn đúng 53×7 ô, kể cả không có dữ liệu.
{
  const { oLuoi } = dungLuoiHoatDong([], HOM_NAY);
  assert.equal(oLuoi.length, SO_TUAN * 7);
}

// 2) Ô "hôm nay" luôn rơi vào CỘT CUỐI (52), hàng đúng thứ Monday-start (3 =
//    thứ Năm) — 364 ngày = đúng 52 tuần nên ngày cũ nhất và hôm nay LUÔN cùng
//    thứ, và hôm nay luôn là ô cuối của cột cuối cùng.
{
  const { oLuoi } = dungLuoiHoatDong([], HOM_NAY);
  const idx = oLuoi.findIndex((o) => o !== null && o.ngay === "2026-09-10");
  assert.notEqual(idx, -1);
  assert.equal(Math.floor(idx / 7), SO_TUAN - 1);
  assert.equal(idx % 7, 3);
}

// 3) Lệch thứ Monday-start đúng qua một mốc đổi tháng: 2026-08-01 là thứ Bảy
//    → hàng 5. Nhãn "Tháng 8" xuất hiện ĐÚNG MỘT LẦN trong `nhanThang` (không
//    lặp lại ở mọi cột của cùng một tháng).
{
  const { oLuoi, nhanThang } = dungLuoiHoatDong([], HOM_NAY);
  const idx = oLuoi.findIndex((o) => o !== null && o.ngay === "2026-08-01");
  assert.notEqual(idx, -1);
  assert.equal(idx % 7, 5);
  const nhanThang8 = new Intl.DateTimeFormat("vi-VN", {
    month: "short",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(2000, 7, 1)));
  assert.equal(nhanThang.filter((n) => n === nhanThang8).length, 1);
}

// 4) Một ngày có mặt trong `hoat_dong` với `so_luot: 0` tô mức 0 — có mặt
//    trong dữ liệu không đồng nghĩa có hoạt động.
{
  const { oLuoi } = dungLuoiHoatDong([{ ngay: "2026-09-10", so_luot: 0 }], HOM_NAY);
  const o = oLuoi.find((x) => x !== null && x.ngay === "2026-09-10");
  assert.equal(o?.muc, 0);
}

// 5) Mọi `so_luot` dương BẰNG NHAU → CHỈ MỘT giá trị khác nhau trong cửa sổ
//    (`hangDuongTinh` trả mảng 1 phần tử) → mọi ngày dương chạm mức 4. "Hoạt
//    động đều mỗi ngày" phải trông ĐẦY, không phải "vừa chạm đáy".
{
  assert.equal(mucCua(7, hangDuongTinh([7, 7, 7])), 4);
  const hoatDong = [
    { ngay: "2026-09-01", so_luot: 7 },
    { ngay: "2026-09-02", so_luot: 7 },
    { ngay: "2026-09-03", so_luot: 7 },
  ];
  const { oLuoi } = dungLuoiHoatDong(hoatDong, HOM_NAY);
  const oi = (ngay: string) => oLuoi.find((x) => x !== null && x.ngay === ngay);
  assert.equal(oi("2026-09-01")?.muc, 4);
  assert.equal(oi("2026-09-02")?.muc, 4);
  assert.equal(oi("2026-09-03")?.muc, 4);
}

// 6) Dữ liệu LỆCH — mười ngày `so_luot: 1` và một ngày đột biến `so_luot:
//    50` — phải VẪN PHÂN BIỆT ĐƯỢC: mười ngày yên ắng ở mức 1 (giá trị nhỏ
//    nhất trong cửa sổ), ngày đột biến ở mức 4 (giá trị lớn nhất). Xếp hạng
//    theo THỨ TỰ giữa hai giá trị khác nhau (1 và 50), không phải ngưỡng
//    theo tứ phân vị — tứ phân vị của mẫu này sụp về [1,1,1] và từng làm mọi
//    ngày dương (kể cả mười ngày yên ắng) cùng chạm mức 4, không phân biệt
//    được với ngày đột biến.
{
  const ngayYen = Array.from({ length: 10 }, (_, i) => ({
    ngay: `2026-08-${String(i + 1).padStart(2, "0")}`,
    so_luot: 1,
  }));
  const hoatDong = [...ngayYen, { ngay: "2026-08-11", so_luot: 50 }];
  const { oLuoi } = dungLuoiHoatDong(hoatDong, HOM_NAY);
  const oi = (ngay: string) => oLuoi.find((x) => x !== null && x.ngay === ngay);
  const mucYen = oi("2026-08-01")?.muc;
  const mucDotBien = oi("2026-08-11")?.muc;
  assert.equal(mucYen, 1);
  assert.equal(mucDotBien, 4);
  assert.notEqual(mucYen, mucDotBien);
}

// 7) Bốn giá trị dương khác nhau trải đều 1→4, không nén cụm dưới vào một
//    mức hay bỏ trống mức 1 như bản ngưỡng-giá-trị cũ làm với ≤4 giá trị
//    khác nhau.
{
  assert.deepEqual(
    [1, 2, 3, 4].map((v) => mucCua(v, hangDuongTinh([1, 2, 3, 4]))),
    [1, 2, 3, 4],
  );
}

// 8) Một `ngay` NGOÀI cửa sổ 365 ngày bị BỎ HẲN: không hiện lên lưới, và
//    KHÔNG được tính vào xếp hạng của các ngày đang hiển thị — thêm nó vào
//    (dù với `so_luot` cực lớn) không được đổi kết quả một chút nào.
{
  const a = dungLuoiHoatDong([{ ngay: "2026-09-05", so_luot: 3 }], HOM_NAY);
  const b = dungLuoiHoatDong(
    [
      { ngay: "2026-09-05", so_luot: 3 },
      { ngay: "2020-01-01", so_luot: 999_999 },
    ],
    HOM_NAY,
  );
  assert.deepEqual(a, b);
  assert.ok(b.oLuoi.every((o) => o === null || o.ngay !== "2020-01-01"));
}

console.info("kiem-lich-hoat-dong: 18/18 đạt");
