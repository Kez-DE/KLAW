/** Tay kéo theo W3C Window Splitter (spec 2026-09-09 §9.1): kẹp bề rộng, tính
 *  phần trăm cho `aria-valuenow`, và biên panel đối chiếu theo bề rộng cửa sổ.
 *  Chạy: `npm run kiem-keo-dan`. */
import assert from "node:assert/strict";
import {
  BUOC_PHIM,
  RONG_DOI_CHIEU_MAC_DINH,
  bienPanelDoiChieu,
  kepRong,
  phanTram,
} from "../src/lib/keo-dan.ts";

assert.equal(RONG_DOI_CHIEU_MAC_DINH, 420);
assert.deepEqual(bienPanelDoiChieu(1440), { min: 320, max: 864 });
assert.deepEqual(bienPanelDoiChieu(1000), { min: 320, max: 520 }); // 1000 - 480 chat tối thiểu
assert.deepEqual(bienPanelDoiChieu(700), { min: 320, max: 320 });
assert.equal(kepRong(100, { min: 320, max: 864 }), 320);
assert.equal(kepRong(900, { min: 320, max: 864 }), 864);
assert.equal(kepRong(500, { min: 320, max: 864 }), 500);
assert.equal(phanTram(320, { min: 320, max: 864 }), 0);
assert.equal(phanTram(864, { min: 320, max: 864 }), 100);
assert.equal(phanTram(592, { min: 320, max: 864 }), 50);
assert.equal(BUOC_PHIM, 24);
console.log("kiem-keo-dan: 11/11 OK");
