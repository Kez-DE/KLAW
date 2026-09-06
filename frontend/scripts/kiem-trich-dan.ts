/**
 * Kiểm chạy được cho `catTheoTrichDan` — phần định vị câu trích trong nguyên
 * văn. Đây là logic duy nhất trong pha 5 có thể sai âm thầm: nó cắt chuỗi bằng
 * chỉ số, và một chỉ số lệch một ký tự sẽ tô sáng sai chỗ mà không ai nhận ra
 * cho tới khi có người đối chiếu tay.
 *
 * Chạy: `npm run kiem-trich-dan` (Node 22 đọc thẳng TypeScript, không cần
 * thêm thư viện nào).
 */
import assert from "node:assert/strict";
import { catTheoTrichDan, chiSoDauCuaVanBan } from "../src/lib/trich-dan.ts";

// 1. Khớp thẳng: ba mảnh ghép lại phải bằng đúng nguyên văn.
{
  const noiDung = "Người lao động có quyền đơn phương chấm dứt hợp đồng lao động.";
  const lat = catTheoTrichDan(noiDung, "đơn phương chấm dứt hợp đồng lao động");
  assert.equal(lat.timThay, true);
  assert.equal(lat.trung, "đơn phương chấm dứt hợp đồng lao động");
  assert.equal(lat.truoc + lat.trung + lat.sau, noiDung.normalize("NFC"));
}

// 2. Khoảng trắng lệch: nguyên văn xuống dòng và có khoảng trắng kép, quote thì
//    một dòng. Phần cắt ra phải là NGUYÊN VĂN (giữ xuống dòng), không phải
//    chuỗi đã bị chuẩn hoá.
{
  const noiDung = "Thời giờ làm việc bình thường\nkhông  quá 08 giờ trong 01 ngày.";
  const lat = catTheoTrichDan(noiDung, "bình thường không quá 08 giờ");
  assert.equal(lat.timThay, true);
  assert.equal(lat.trung, "bình thường\nkhông  quá 08 giờ");
  assert.equal(lat.truoc + lat.trung + lat.sau, noiDung.normalize("NFC"));
}

// 3. Dấu tiếng Việt dạng tổ hợp (NFD) một bên, dựng sẵn (NFC) bên kia.
{
  const noiDung = "Hợp đồng lao động phải được giao kết bằng văn bản.".normalize("NFD");
  const lat = catTheoTrichDan(noiDung, "giao kết bằng văn bản".normalize("NFC"));
  assert.equal(lat.timThay, true);
  assert.equal(lat.trung.normalize("NFC"), "giao kết bằng văn bản");
}

// 4. Không tìm thấy: phải nói ra, và phải trả nguyên văn nguyên vẹn để nơi gọi
//    vẫn hiển thị được điều luật.
{
  const noiDung = "Người sử dụng lao động phải trả lương đúng hạn.";
  const lat = catTheoTrichDan(noiDung, "câu trích không có trong điều này");
  assert.equal(lat.timThay, false);
  assert.equal(lat.trung, "");
  assert.equal(lat.truoc, noiDung.normalize("NFC"));
}

// 5. Quote rỗng hoặc chỉ khoảng trắng KHÔNG phải một câu trích: không được tô
//    sáng ký tự đầu tiên rồi báo là đã định vị được.
for (const rong of ["", "   ", "\n\t"]) {
  const lat = catTheoTrichDan("Nguyên văn bất kỳ.", rong);
  assert.equal(lat.timThay, false, `quote ${JSON.stringify(rong)} phải không định vị được`);
}

// 6. Câu trích nằm ở đúng cuối nguyên văn — biên hay lệch một ký tự nhất.
{
  const noiDung = "Mức lương tối thiểu được điều chỉnh theo vùng.";
  const lat = catTheoTrichDan(noiDung, "theo vùng.");
  assert.equal(lat.timThay, true);
  assert.equal(lat.sau, "");
  assert.equal(lat.trung, "theo vùng.");
}

// 7. Thẻ `doc:ID` mở điều khoản ĐẦU của văn bản đó theo `k` (Q5, spec §7.2).
{
  const cit = [
    { doc_id: "152668", k: 3 },
    { doc_id: "139264", k: 2 },
    { doc_id: "139264", k: 1 },
    { doc_id: "139264", k: null },
  ] as unknown as import("../src/lib/klaw.ts").Citation[];
  assert.equal(
    chiSoDauCuaVanBan(cit, "139264"),
    2,
    "k nhỏ nhất của văn bản, không phải vị trí đầu",
  );
  assert.equal(chiSoDauCuaVanBan(cit, "152668"), 0);
  assert.equal(chiSoDauCuaVanBan(cit, "000"), -1);
  // Không có k nào (payload cũ) → trích dẫn đầu tiên của văn bản.
  const cu = [
    { doc_id: "1" },
    { doc_id: "2" },
  ] as unknown as import("../src/lib/klaw.ts").Citation[];
  assert.equal(chiSoDauCuaVanBan(cu, "2"), 1);
}

console.info("kiem-trich-dan: 7/7 đạt");
