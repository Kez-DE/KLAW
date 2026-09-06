/**
 * `slugCuaLoai`: mã checklist phía máy chủ → slug thẻ FE. `hdld` có HAI thẻ
 * (xác định / không xác định thời hạn); loại chưa có thẻ → [] để card rơi về
 * nút "Chọn loại văn bản". Chạy: `npm run kiem-goi-y-soan-thao`.
 */
import assert from "node:assert/strict";
import { LOAI_BACKEND, slugCuaLoai } from "../src/lib/mau-van-ban.ts";

{
  const hdld = slugCuaLoai("hdld").sort();
  assert.deepEqual(hdld, [
    "hop-dong-lao-dong-khong-xac-dinh-thoi-han",
    "hop-dong-lao-dong-xac-dinh-thoi-han",
  ]);
}
{
  assert.deepEqual(slugCuaLoai("don_xin_nghi_viec"), ["don-xin-nghi-viec"]);
  assert.deepEqual(slugCuaLoai("thoa_thuan_cham_dut_hdld"), [
    "thoa-thuan-cham-dut-hop-dong-lao-dong",
  ]);
}
{
  assert.deepEqual(slugCuaLoai("khong_co_loai_nay"), []);
}
// Mọi slug trả về phải là khoá thật của LOAI_BACKEND.
{
  for (const [, v] of Object.entries(LOAI_BACKEND)) {
    for (const s of slugCuaLoai(v.loai)) assert.ok(s in LOAI_BACKEND, s);
  }
}
console.info("kiem-goi-y-soan-thao: 4/4 đạt");
