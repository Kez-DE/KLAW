/**
 * Kiểm chạy được cho bộ tách khung SSE.
 *
 * Đây là phần của pha nối backend có thể sai ÂM THẦM: một khung bị cắt sai
 * không ném lỗi, nó chỉ làm một sự kiện biến mất. Sự kiện biến mất là `ket_qua`
 * thì màn hình chờ quay mãi mãi trên một lượt tra cứu ĐÃ TỐN TIỀN — máy chủ
 * chạy graph trong task riêng nên tiền đã tiêu dù client có đọc được hay không.
 *
 * Chạy: `npm run kiem-sse` (Node 22 đọc thẳng TypeScript, 0 thư viện mới).
 */
import assert from "node:assert/strict";
import { catCacKhung, tachKhungSSE } from "../src/lib/sse-khung.ts";

// 1. Khung đủ: một `event:` + một `data:`.
{
  const khung = tachKhungSSE('event: buoc\ndata: {"buoc":"retrieve","thu_tu":4}');
  assert.notEqual(khung, null);
  assert.equal(khung?.ten, "buoc");
  assert.deepEqual(khung?.duLieu, { buoc: "retrieve", thu_tu: 4 });
}

// 2. Đúng MỘT dấu cách sau `data:` bị bỏ — không phải trim. Payload mở đầu
//    bằng `{` nên chuỗi phải parse được y hệt khi không có dấu cách nào.
{
  const a = tachKhungSSE('event: x\ndata: {"a":1}');
  const b = tachKhungSSE('event: x\ndata:{"a":1}');
  assert.deepEqual(a?.duLieu, { a: 1 });
  assert.deepEqual(b?.duLieu, { a: 1 });
}

// 3. Dòng chú thích (`: ping`, heartbeat của proxy) KHÔNG được đọc thành dữ
//    liệu. Máy chủ KLAW chưa gửi heartbeat — mối lo #5 của báo cáo Pha 2 — nên
//    một proxy chèn vào là đúng tình huống chưa ai thử.
{
  const khung = tachKhungSSE(': ping\nevent: buoc\ndata: {"buoc":"tier2"}\n: ping');
  assert.deepEqual(khung?.duLieu, { buoc: "tier2" });
}

// 4. Khung rác trả `null`, KHÔNG ném: thiếu `event`, thiếu `data`, JSON hỏng.
{
  assert.equal(tachKhungSSE('data: {"a":1}'), null);
  assert.equal(tachKhungSSE("event: buoc"), null);
  assert.equal(tachKhungSSE("event: buoc\ndata: {khong-phai-json"), null);
}

// 5. Nhiều dòng `data:` nối lại bằng `\n` theo đặc tả.
{
  const khung = tachKhungSSE('event: ket_qua\ndata: {"a":\ndata: 1}');
  assert.deepEqual(khung?.duLieu, { a: 1 });
}

// 6. Hai sự kiện về trong CÙNG một lần đọc — đúng ca 1,00s/1,02s đo được ở
//    `route` và `tien_de`. Cả hai phải ra, không phải một.
{
  const cat = catCacKhung(
    'event: buoc\ndata: {"buoc":"route"}\n\nevent: buoc\ndata: {"buoc":"tien_de"}\n\n',
  );
  assert.equal(cat.khung.length, 2);
  assert.deepEqual(
    cat.khung.map((k) => (k.duLieu as { buoc: string }).buoc),
    ["route", "tien_de"],
  );
  assert.equal(cat.con, "");
}

// 7. MỘT sự kiện bị cắt làm hai lần đọc. Phần dang dở phải được giữ lại nguyên
//    vẹn, và ghép tiếp phải ra đúng một khung — đây là ca hỏng thật của
//    `ReadableStream`: nó cắt theo gói tin, không theo ranh giới khung.
{
  const buoc1 = catCacKhung('event: ket_qua\ndata: {"result_ty');
  assert.equal(buoc1.khung.length, 0);
  const buoc2 = catCacKhung(`${buoc1.con}pe":"answer"}\n\n`);
  assert.equal(buoc2.khung.length, 1);
  assert.deepEqual(buoc2.khung[0]?.duLieu, { result_type: "answer" });
  assert.equal(buoc2.con, "");
}

// 8. Ranh giới khung dạng CRLF vẫn cắt được.
{
  const cat = catCacKhung('event: buoc\r\ndata: {"buoc":"expand"}\r\n\r\n');
  assert.equal(cat.khung.length, 1);
  assert.deepEqual(cat.khung[0]?.duLieu, { buoc: "expand" });
}

// 9. Một khung rác nằm GIỮA hai khung tốt không được giết stream: khung sau nó
//    vẫn phải ra.
{
  const cat = catCacKhung(
    'event: buoc\ndata: {"buoc":"route"}\n\nevent: buoc\ndata: {hong\n\nevent: ket_qua\ndata: {"ok":1}\n\n',
  );
  assert.equal(cat.khung.length, 2);
  assert.equal(cat.khung[1]?.ten, "ket_qua");
}

console.log("kiem-sse: 9/9 phép kiểm đạt");
