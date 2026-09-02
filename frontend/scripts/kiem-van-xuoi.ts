/**
 * Kiểm chạy được cho `catDoan` — phần cắt văn xuôi của câu trả lời thành đoạn
 * và danh sách.
 *
 * Vì sao phần này cần một kiểm: nó là thứ DUY NHẤT trong đường hiển thị câu
 * trả lời có đụng vào chuỗi máy chủ gửi về. Backend nay viết theo giọng luật
 * sư, tức là câu trả lời mang số Điều NGAY TRONG lời văn —
 * `(Điều 25, Khoản 1)` — và mang danh sách gạch đầu dòng. Một bộ cắt sai làm
 * hai việc, cả hai đều âm thầm: nuốt mất dấu ngoặc chứa căn cứ, hoặc nén danh
 * sách thành một khối chữ liền. Không cái nào ném lỗi.
 *
 * Chạy: `npm run kiem-van-xuoi` (Node 22 đọc thẳng TypeScript, 0 thư viện mới).
 */
import assert from "node:assert/strict";
import { catDoan } from "../src/lib/van-xuoi.ts";

// 1. Một đoạn trơn vẫn là một đoạn.
{
  const dd = catDoan("Thời gian thử việc tối đa là 180 ngày.");
  assert.deepEqual(dd, [{ kieu: "doan", chu: "Thời gian thử việc tối đa là 180 ngày." }]);
}

// 2. Nhiều dòng vẫn ra nhiều đoạn — hành vi cũ không được đổi.
{
  const dd = catDoan("Đoạn một.\n\nĐoạn hai.\n");
  assert.deepEqual(dd, [
    { kieu: "doan", chu: "Đoạn một." },
    { kieu: "doan", chu: "Đoạn hai." },
  ]);
}

// 3. Câu dẫn + ba gạch đầu dòng → một đoạn rồi MỘT danh sách, không phải bốn đoạn.
{
  const dd = catDoan(
    "Dưới đây là 03 điều kiện cốt lõi:\n- Có thoả thuận bằng văn bản.\n- Không quá 180 ngày.\n- Lương ít nhất 85% lương chính thức.",
  );
  assert.equal(dd.length, 2);
  assert.deepEqual(dd[0], { kieu: "doan", chu: "Dưới đây là 03 điều kiện cốt lõi:" });
  assert.deepEqual(dd[1], {
    kieu: "danh_sach",
    muc: [
      "Có thoả thuận bằng văn bản.",
      "Không quá 180 ngày.",
      "Lương ít nhất 85% lương chính thức.",
    ],
  });
}

// 4. Bốn ký tự gạch đầu dòng đều nhận, và ký tự đó bị GỠ khỏi chữ hiển thị —
//    thẻ <ul> tự vẽ chấm, để lại dấu gạch là vẽ hai lần.
{
  const dd = catDoan("- một\n– hai\n— ba\n• bốn\n* năm");
  assert.deepEqual(dd, [{ kieu: "danh_sach", muc: ["một", "hai", "ba", "bốn", "năm"] }]);
}

// 5. Dấu gạch GIỮA câu KHÔNG phải gạch đầu dòng. Đây là ca hỏng nguy hiểm nhất:
//    tên cơ quan trong luật lao động có gạch nối.
{
  const cau = "Thông tư do Bộ Lao động - Thương binh và Xã hội ban hành.";
  assert.deepEqual(catDoan(cau), [{ kieu: "doan", chu: cau }]);
}

// 6. Dấu ngoặc chứa căn cứ phải qua NGUYÊN VẸN, ở cả đoạn lẫn mục danh sách.
{
  const trongDoan =
    "Chào bạn, theo quy định của Bộ luật Lao động số 45/2019/QH14, thời gian thử việc không quá 180 ngày đối với công việc của người quản lý doanh nghiệp (Điều 25, Khoản 1).";
  const dd = catDoan(`${trongDoan}\n- Áp dụng cho người quản lý doanh nghiệp (Điều 25, Khoản 1).`);
  assert.equal(dd[0]?.kieu, "doan");
  assert.equal(dd[0] && "chu" in dd[0] ? dd[0].chu : null, trongDoan);
  const ds = dd[1];
  assert.equal(ds?.kieu, "danh_sach");
  assert.equal(
    ds && "muc" in ds ? ds.muc[0] : null,
    "Áp dụng cho người quản lý doanh nghiệp (Điều 25, Khoản 1).",
  );
}

// 7. Hai danh sách tách nhau bởi một đoạn KHÔNG được dính làm một.
{
  const dd = catDoan("- a\n- b\nGiải thích ở giữa.\n- c\n- d");
  assert.deepEqual(
    dd.map((d) => d.kieu),
    ["danh_sach", "doan", "danh_sach"],
  );
  assert.deepEqual(dd[0], { kieu: "danh_sach", muc: ["a", "b"] });
  assert.deepEqual(dd[2], { kieu: "danh_sach", muc: ["c", "d"] });
}

// 8. Một dòng chỉ có mỗi ký tự gạch không sinh ra mục rỗng.
{
  assert.deepEqual(catDoan("- \n-\n- thật"), [{ kieu: "danh_sach", muc: ["thật"] }]);
}

// 9. Chuỗi rỗng hoặc chỉ khoảng trắng ra mảng rỗng — nơi gọi tự lo nhánh đó.
{
  for (const rong of ["", "   ", "\n\n\t"]) assert.deepEqual(catDoan(rong), []);
}

// 10. KHÔNG đụng vào bất cứ thứ gì khác: dấu nháy cong, số hiệu, phần trăm.
{
  const cau = "“85%” của mức lương — theo 45/2019/QH14 (Điều 26).";
  assert.deepEqual(catDoan(cau), [{ kieu: "doan", chu: cau }]);
}

console.info("kiem-van-xuoi: 10/10 đạt");
