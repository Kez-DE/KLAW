/**
 * Kiểm chạy được cho `dungLichSu` — chỗ dựng `lich_su` gửi lên máy chủ.
 *
 * Vì sao phần này cần một kiểm: cả hai trần nó cưỡng chế đều gác một lỗi **422**
 * làm chết TRỌN lượt hỏi nối tiếp, và cả hai đều hỏng âm thầm.
 *
 * `TraCuuRequest.lich_su` có `max_length=3` và `LuotTruoc.tra_loi` có
 * `max_length=2000` ở phía pydantic — quá trần là 422, KHÔNG truncate. Một câu
 * trả lời ba tầng bảy luận điểm dễ dài hơn 2.000 ký tự, nên thiếu phép cắt thì
 * câu nối tiếp bị từ chối vì câu trả lời TRƯỚC quá dài: người dùng thấy "lỗi" ở
 * đúng lượt họ không làm gì sai.
 *
 * Chạy: `npm run kiem-lich-su` (Node 22 đọc thẳng TypeScript, 0 thư viện mới).
 */
import assert from "node:assert/strict";

import { TOI_DA_LUOT_LICH_SU, TOI_DA_TRA_LOI_LICH_SU } from "../src/lib/klaw.ts";
import { dungLichSu, TOI_DA_DUONG_DAN_LICH_SU, type LuotDaXong } from "../src/lib/lich-su.ts";

const kq = (answer: string | null, duongDan: string[] = []) =>
  ({
    result_type: "answer",
    answer,
    citations: duongDan.map((d) => ({ duong_dan: d })),
    nguon: [],
    warnings: [],
    coverage_note: null,
    trace_id: "t",
    cau_hoi_day_du: null,
  }) as unknown as LuotDaXong["ketQua"];

// Chỉ TOI_DA_LUOT_LICH_SU lượt CUỐI, và đúng thứ tự (mới nhất sau cùng).
// Nạp NHIỀU HƠN trần để phép cắt thật sự bị thử; kỳ vọng suy ra từ hằng số,
// không hard-code nhãn — nếu không, trần đổi thì test không còn thử gì cả.
{
  const tongSo = TOI_DA_LUOT_LICH_SU + 5;
  const cauHoiTatCa = Array.from({ length: tongSo }, (_, i) => `câu ${i + 1}`);
  const nam: LuotDaXong[] = cauHoiTatCa.map((cauHoi) => ({ cauHoi, ketQua: kq(`đáp ${cauHoi}`) }));
  const ra = dungLichSu(nam);
  assert.equal(ra.length, TOI_DA_LUOT_LICH_SU, "phải cắt còn đúng trần của máy chủ");
  assert.deepEqual(
    ra.map((l) => l.cau_hoi),
    cauHoiTatCa.slice(-TOI_DA_LUOT_LICH_SU),
    "phải giữ đúng TOI_DA_LUOT_LICH_SU lượt CUỐI, mới nhất sau cùng",
  );
}

// Câu trả lời dài bị cắt — nếu không, cả lượt nối tiếp bị 422.
{
  const dai = "x".repeat(TOI_DA_TRA_LOI_LICH_SU * 4);
  const [l] = dungLichSu([{ cauHoi: "c", ketQua: kq(dai) }]);
  assert.equal(l?.tra_loi.length, TOI_DA_TRA_LOI_LICH_SU, "tra_loi phải bị cắt đúng trần");
}

// `answer` null (abstain / out_of_scope) thành chuỗi rỗng, KHÔNG phải "null".
{
  const [l] = dungLichSu([{ cauHoi: "c", ketQua: kq(null) }]);
  assert.equal(l?.tra_loi, "", 'answer null phải thành "" — chuỗi "null" là rác gửi cho model');
}

// `duong_dan` lấy từ citations — thứ định danh điều khoản lượt trước đã dẫn.
{
  const [l] = dungLichSu([
    { cauHoi: "c", ketQua: kq("đ", ["45/2019/QH14 > Điều 35", "45/2019/QH14 > Điều 36"]) },
  ]);
  assert.deepEqual(l?.duong_dan, ["45/2019/QH14 > Điều 35", "45/2019/QH14 > Điều 36"]);
}

// `duong_dan` khử TRÙNG LẶP CHÍNH XÁC, giữ thứ tự xuất hiện ĐẦU TIÊN — không
// sort, không gộp theo phần con.
{
  const [l] = dungLichSu([
    {
      cauHoi: "c",
      ketQua: kq("đ", [
        "45/2019/QH14 > Điều 35",
        "45/2019/QH14 > Điều 36",
        "45/2019/QH14 > Điều 35", // trùng lặp CHÍNH XÁC, phải bị loại
      ]),
    },
  ]);
  assert.deepEqual(l?.duong_dan, ["45/2019/QH14 > Điều 35", "45/2019/QH14 > Điều 36"]);
}

// Trần `duong_dan`: máy chủ 422 (không truncate) nếu quá `max_length=50`.
// PHẢI khử trùng TRƯỚC rồi mới cắt — nếu thiếu trần này, một lượt 71 trích
// dẫn (đo được thật trên `traces`) làm MỌI lượt nối tiếp 422 cho tới khi lượt
// đó trôi khỏi cửa sổ 3 lượt.
{
  const trung = Array.from({ length: TOI_DA_DUONG_DAN_LICH_SU * 2 }, () => "lặp/Điều 1");
  const [chiMotPhanTu] = dungLichSu([{ cauHoi: "c", ketQua: kq("đ", trung) }]);
  assert.deepEqual(
    chiMotPhanTu?.duong_dan,
    ["lặp/Điều 1"],
    "khử trùng phải gộp mọi bản sao về đúng MỘT phần tử, không đụng trần",
  );

  const phanBiet = Array.from(
    { length: TOI_DA_DUONG_DAN_LICH_SU + 10 },
    (_, i) => `phân biệt/Điều ${i}`,
  );
  const [daCat] = dungLichSu([{ cauHoi: "c", ketQua: kq("đ", phanBiet) }]);
  assert.equal(daCat?.duong_dan.length, TOI_DA_DUONG_DAN_LICH_SU, "phải cắt còn đúng trần");
  assert.deepEqual(
    daCat?.duong_dan,
    phanBiet.slice(0, TOI_DA_DUONG_DAN_LICH_SU),
    "phải giữ các phần tử PHÂN BIỆT xuất hiện trước, đúng thứ tự cũ",
  );
}

// Hội thoại rỗng ⇒ mảng rỗng, để nơi gọi bỏ hẳn khoá `lich_su` (lượt đầu 0 token).
assert.deepEqual(dungLichSu([]), []);

console.log("kiem-lich-su: OK");
