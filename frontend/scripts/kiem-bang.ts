/**
 * Kiểm chạy được cho bộ đọc bảng (`lib/bang.ts`).
 *
 * Hai bất biến ở đây hỏng ÂM THẦM, và cả hai đều hỏng về phía nguy hiểm — một
 * cái bảng trông vẫn ra bảng nhưng SỐ LIỆU đứng sai cột:
 *
 *   1. `O.tu` phải trỏ đúng vị trí ký tự của ô trong bản NFC của `noi_dung`.
 *      Lệch một ký tự thì `<mark>` tô sang ô bên cạnh, và tô sáng câu trích là
 *      đóng góp trung tâm của đề tài.
 *   2. Hàng thiếu ô phải nhận ô TRỐNG ở cuối, không được ghép dồn. Bảng tuổi
 *      nghỉ hưu của 135/2020/NĐ-CP có hàng 2 ô đứng cạnh hàng 4 ô: dồn lại là
 *      đọc "2029 | 58 tuổi" thành cột "Lao động nam".
 *
 * Nguyên văn trong các ca dưới đây lấy NGUYÊN từ kho thật (293/2025/NĐ-CP và
 * 135/2020/NĐ-CP), không phải chuỗi bịa cho vừa bộ đọc.
 *
 * Chạy: `npm run kiem-bang`.
 */
import assert from "node:assert/strict";
import { gomHangBang, soCot, tachDoan, type O } from "../src/lib/bang.ts";
import type { Provision } from "../src/lib/klaw.ts";
import { vungTrichDan } from "../src/lib/trich-dan.ts";

function dong(tho: Partial<Provision> & Pick<Provision, "id" | "noi_dung">): Provision {
  return {
    cap: "khoan",
    so_hieu_cap: "",
    duong_dan: "",
    tieu_de: "",
    parent_id: null,
    la_tam: true,
    ...tho,
  };
}

/** Mọi ô phải cắt ra đúng bằng nguyên văn tại vị trí nó khai. */
function tuKhop(nfc: string, o: O[]): void {
  for (const mot of o) {
    assert.equal(
      nfc.slice(mot.tu, mot.tu + mot.text.length),
      mot.text,
      `ô ${JSON.stringify(mot.text)} khai sai vị trí ${mot.tu}`,
    );
  }
}

// 1. Dạng A — nguyên văn cha: văn xuôi rồi HÀNG TIÊU ĐỀ ở lại cuối.
const CHA =
  "1. Quy định mức lương tối thiểu tháng và mức lương tối thiểu giờ đối với người lao động làm việc cho người sử dụng lao động theo vùng như sau:\n\n| Vùng | Mức lương tối thiểu tháng (Đơn vị: đồng/tháng) | Mức lương tối thiểu giờ (Đơn vị: đồng/giờ) |";
{
  const doan = tachDoan(CHA);
  assert.equal(doan.length, 2, "cha phải ra đúng một đoạn văn + một khối bảng");
  const [van, bang] = doan;
  assert.equal(van?.loai, "van");
  assert.equal(bang?.loai, "bang");
  if (bang?.loai !== "bang" || van?.loai !== "van") throw new Error("hình dạng sai");
  assert.equal(bang.hang.length, 1, "chỉ hàng tiêu đề ở lại trong noi_dung của cha");
  assert.deepEqual(
    bang.hang[0]?.map((o) => o.text),
    [
      "Vùng",
      "Mức lương tối thiểu tháng (Đơn vị: đồng/tháng)",
      "Mức lương tối thiểu giờ (Đơn vị: đồng/giờ)",
    ],
  );
  // Văn xuôi KHÔNG được nuốt dòng bảng, và không kéo theo khoảng trắng cuối.
  assert.equal(van.text, CHA.slice(0, CHA.indexOf("\n")));
  assert.equal(van.tu, 0);
  tuKhop(CHA.normalize("NFC"), bang.hang[0] ?? []);
}

// 2. Dạng A — một hàng đã tách: đúng ba ô, đúng vị trí.
{
  const hang = "| Vùng II | 4.730.000 | 22.700 |";
  const doan = tachDoan(hang);
  assert.equal(doan.length, 1);
  const [bang] = doan;
  if (bang?.loai !== "bang") throw new Error("hàng tách phải ra khối bảng");
  assert.deepEqual(
    bang.hang[0]?.map((o) => o.text),
    ["Vùng II", "4.730.000", "22.700"],
  );
  tuKhop(hang.normalize("NFC"), bang.hang[0] ?? []);
}

// 3. Tô sáng phải theo được VÀO TRONG ô — bất biến trung tâm.
//    `4.730.000` là câu trích; ô mang nó phải giao đúng khoảng tô.
{
  const hang = "| Vùng II | 4.730.000 | 22.700 |";
  const vung = vungTrichDan(hang, "4.730.000");
  assert.notEqual(vung, null, "câu trích nằm trong hàng thì phải định vị được");
  if (vung === null) throw new Error("không định vị được");
  const [bang] = tachDoan(hang);
  if (bang?.loai !== "bang") throw new Error("hình dạng sai");
  const o = bang.hang[0] ?? [];
  const trong = o.filter((mot) => vung[0] < mot.tu + mot.text.length && vung[1] > mot.tu);
  assert.equal(trong.length, 1, "đúng MỘT ô được tô, không lem sang ô bên cạnh");
  assert.equal(trong[0]?.text, "4.730.000");
  // Và phần tô bên trong ô phải phủ trọn ô, không lệch ký tự nào.
  const mot = trong[0];
  if (mot === undefined) throw new Error("thiếu ô");
  assert.equal(Math.max(0, vung[0] - mot.tu), 0);
  assert.equal(Math.min(mot.text.length, vung[1] - mot.tu), mot.text.length);
}

// 4. Dạng B — cả bảng trong MỘT noi_dung, số ô không đều (135/2020/NĐ-CP Điều 4).
const DANG_B =
  "2. Lộ trình điều chỉnh tuổi nghỉ hưu của người lao động quy định tại khoản 1 Điều này được thực hiện theo bảng dưới đây:\n\n| Lao động nam | Lao động nữ |\n| Năm nghỉ hưu | Tuổi nghỉ hưu | Năm nghỉ hưu | Tuổi nghỉ hưu |\n| 2021 | 60 tuổi 3 tháng | 2021 | 55 tuổi 4 tháng |\n| Từ năm 2028 trở đi | 62 tuổi | 2028 | 57 tuổi 8 tháng |\n|  |  | 2029 | 58 tuổi |";
{
  const doan = tachDoan(DANG_B);
  assert.equal(doan.length, 2, "văn xuôi + đúng MỘT khối bảng (5 dòng liền nhau)");
  const bang = doan[1];
  if (bang?.loai !== "bang") throw new Error("hình dạng sai");
  assert.equal(bang.hang.length, 5);
  // Số ô mỗi hàng giữ NGUYÊN như dữ liệu: 2 rồi 4. Không bên nào bị nắn.
  assert.deepEqual(
    bang.hang.map((h) => h.length),
    [2, 4, 4, 4, 4],
  );
  assert.equal(soCot(bang.hang), 4, "số cột = hàng nhiều ô nhất, không hơn không kém");
  // Ô gộp để trống vẫn là hai ô rỗng đứng đầu hàng, không bị bỏ đi.
  assert.deepEqual(
    bang.hang[4]?.map((o) => o.text),
    ["", "", "2029", "58 tuổi"],
  );
  for (const hang of bang.hang) tuKhop(DANG_B.normalize("NFC"), hang);
}

// 5. `gomHangBang` thu hàng về đúng cha, giữ thứ tự, và không đánh rơi dòng nào.
{
  const phang: Provision[] = [
    dong({ id: 258769, cap: "dieu", noi_dung: "Điều 3. Mức lương tối thiểu" }),
    dong({ id: 258770, noi_dung: CHA, parent_id: 258769 }),
    dong({ id: 258771, cap: "hang_bang", noi_dung: "| Vùng I | 5.310.000 |", parent_id: 258770 }),
    dong({ id: 258772, cap: "hang_bang", noi_dung: "| Vùng II | 4.730.000 |", parent_id: 258770 }),
    dong({ id: 258775, noi_dung: "2. Danh mục địa bàn…", parent_id: 258769 }),
  ];
  const gom = gomHangBang(phang);
  assert.deepEqual(
    gom.map((g) => g.dieuKhoan.id),
    [258769, 258770, 258775],
  );
  assert.deepEqual(
    gom[1]?.hangCon.map((h) => h.id),
    [258771, 258772],
    "hàng con giữ nguyên thứ tự backend trả",
  );
  assert.equal(gom[0]?.hangCon.length, 0);
}

// 6. Hàng bảng MỒ CÔI (cha nằm ngoài cửa sổ tải) vẫn phải hiện, không biến mất.
{
  const gom = gomHangBang([
    dong({ id: 258771, cap: "hang_bang", noi_dung: "| Vùng I | 5.310.000 |", parent_id: 999999 }),
  ]);
  assert.equal(gom.length, 1, "nguyên văn không được rơi mất chỉ vì thiếu dòng cha");
  assert.equal(gom[0]?.dieuKhoan.id, 258771);
}

// 7. Nguyên văn KHÔNG có bảng đi qua nguyên vẹn: một đoạn văn, giữ cả xuống
//    dòng bên trong, và vị trí bắt đầu là 0.
{
  const van = "a) Người sử dụng lao động hoạt động trên địa bàn thuộc vùng nào\nthì áp dụng.";
  const doan = tachDoan(van);
  assert.equal(doan.length, 1);
  assert.deepEqual(doan[0], { loai: "van", text: van, tu: 0 });
}

console.info("kiem-bang: 7/7 đạt");
