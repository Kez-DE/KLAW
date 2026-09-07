/** Thanh đo hạn mức (spec 2A §7.2): phần trăm, ngưỡng màu, "Không giới hạn", mốc theo VN,
 *  câu chip. Chạy: `npm run kiem-han-muc`. */
import assert from "node:assert/strict";
import { tenGoi } from "../src/lib/goi.ts";
import {
  cauChip,
  dinhDangMoc,
  laKhongGioiHan,
  mucMau,
  mucRangBuoc,
  phanTram,
  soNgayCon,
} from "../src/lib/han-muc.ts";

const m = (khoa: string, da: number, han: number) => ({
  khoa,
  nhan: khoa,
  da_dung: da,
  han_muc: han,
  dat_lai_luc: "2026-09-07T17:00:00Z",
});
{
  assert.equal(phanTram(m("hoi_dap_ngay", 128, 200)), 64);
  assert.equal(phanTram(m("hoi_dap_ngay", 5, 100000)), 0);
  assert.equal(laKhongGioiHan(100000), true);
  assert.equal(laKhongGioiHan(200), false);
  assert.deepEqual(
    [mucMau(0), mucMau(79), mucMau(80), mucMau(99), mucMau(100)],
    ["brass", "brass", "amber", "amber", "do"],
  );
}
{
  assert.equal(dinhDangMoc("2026-09-07T17:00:00Z", "Asia/Ho_Chi_Minh"), "00:00 08/09");
  assert.equal(dinhDangMoc(null, "Asia/Ho_Chi_Minh"), "");
}
{
  assert.equal(cauChip(m("hoi_dap_ngay", 194, 200)), "Còn 6 lượt hôm nay");
  assert.equal(cauChip(m("khach_24h", 3, 10)), "Còn 7/10 lượt thử");
  assert.equal(cauChip(m("soan_thao_ngay", 1, 3)), "Còn 2 bản thảo hôm nay");
  assert.equal(cauChip(m("hoi_dap_ngay", 200, 200)), "Hết lượt hôm nay");
}
{
  const hm = {
    ap_dung: true,
    plan: "pro",
    ten_goi: "Cá nhân",
    mui_gio: "Asia/Ho_Chi_Minh",
    het_han_luc: null,
    ghi_chu: "",
    phien: { luot_toi_da: 50 },
    muc: [m("hoi_dap_ngay", 3, 100000), m("soan_thao_ngay", 1, 20)],
  };
  assert.equal(mucRangBuoc(hm)?.khoa, "soan_thao_ngay");
  assert.equal(mucRangBuoc(null), null);
  assert.equal(tenGoi("pro"), "Cá nhân");
  assert.equal(tenGoi("khach"), "Dùng thử");
  assert.equal(soNgayCon(null), null);
}
console.info("kiem-han-muc: 4/4 đạt");
