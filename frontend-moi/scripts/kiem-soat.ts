/**
 * Kiểm chạy được cho `trangThaiSoat` — bảo đảm #11.
 *
 * Bất biến được canh ở đây: **"đã soát và không sao" và "không soát được"
 * KHÔNG BAO GIỜ được trông giống nhau.**
 *
 * Đây không phải một lo xa. ĐO TRÊN MÁY CHỦ ĐANG CHẠY, `POST /soat` với một
 * bản hợp đồng đủ 10 nội dung bắt buộc trả về:
 *
 *     dat = true · completeness = 1.0 · findings = 5, CẢ NĂM `khong_kiem_duoc`
 *
 * Năm rule không chạy được đó gồm `luong_toi_thieu_vung` (lương thấp hơn lương
 * tối thiểu vùng) và `cam_phat_tien_nld` (điều khoản phạt tiền người lao
 * động). Một khay xanh lá kèm dấu tích ở trạng thái này nói với người dùng
 * rằng hợp đồng của họ sạch, trong khi máy chưa hề kiểm hai điều nguy hiểm
 * nhất. Sai theo hướng đó là sai kiểu tệ nhất mà sản phẩm này có thể sai.
 *
 * Chạy: `npm run kiem-soat`.
 */
import assert from "node:assert/strict";
import { trangThaiSoat } from "../src/lib/soat.ts";

// 1. Sạch THẬT: không vi phạm, và mọi rule đều đã chạy.
assert.equal(trangThaiSoat(true, 0), "dat");

// 2. Ca nguy hiểm, đo được ở trên: không vi phạm NHƯNG còn rule chưa chạy.
//    Phải KHÁC ca 1 — nếu hai ca này trả về cùng một trạng thái thì giao diện
//    không còn cách nào phân biệt chúng.
assert.equal(trangThaiSoat(true, 5), "dat_mot_phan");
assert.notEqual(trangThaiSoat(true, 5), trangThaiSoat(true, 0));

// 3. Một rule chưa kiểm được cũng đã đủ. Không có ngưỡng "ít thì bỏ qua":
//    rule chưa chạy duy nhất ấy có thể chính là rule lương tối thiểu vùng.
assert.equal(trangThaiSoat(true, 1), "dat_mot_phan");

// 4. Có vi phạm thì luôn là không đạt, dù còn bao nhiêu rule chưa kiểm.
assert.equal(trangThaiSoat(false, 0), "khong_dat");
assert.equal(trangThaiSoat(false, 5), "khong_dat");

// 5. Chỉ ba trạng thái, và trạng thái "sạch" chỉ đến từ ĐÚNG một tổ hợp.
{
  const thay = new Set<string>();
  for (const dat of [true, false]) {
    for (let n = 0; n <= 20; n += 1) thay.add(trangThaiSoat(dat, n));
  }
  assert.deepEqual([...thay].sort(), ["dat", "dat_mot_phan", "khong_dat"]);

  let soLanSach = 0;
  for (const dat of [true, false]) {
    for (let n = 0; n <= 20; n += 1) if (trangThaiSoat(dat, n) === "dat") soLanSach += 1;
  }
  assert.equal(soLanSach, 1, "chỉ (dat=true, chưa kiểm=0) mới được là 'dat'");
}

console.info("kiem-soat: 5/5 đạt");
