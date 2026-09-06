/**
 * `locNext`: đích quay lại sau đăng nhập chỉ nhận hai trang bị khoá. Một chuỗi
 * ngoài danh sách (URL ngoài, `//evil`, đường con) bị bỏ — không open redirect.
 * Chạy: `npm run kiem-quay-lai`.
 */
import assert from "node:assert/strict";
import { DICH_QUAY_LAI, locNext } from "../src/lib/quay-lai.ts";

assert.deepEqual([...DICH_QUAY_LAI], ["/dung-thu", "/soan-thao"]);
assert.equal(locNext("/dung-thu"), "/dung-thu");
assert.equal(locNext("/soan-thao"), "/soan-thao");
assert.equal(locNext("/soan-thao/don-xin-nghi-viec"), undefined);
assert.equal(locNext("//evil.example"), undefined);
assert.equal(locNext("https://evil.example/dung-thu"), undefined);
assert.equal(locNext(""), undefined);
assert.equal(locNext(undefined), undefined);
assert.equal(locNext(["/dung-thu"]), undefined);
console.info("kiem-quay-lai: 9/9 đạt");
