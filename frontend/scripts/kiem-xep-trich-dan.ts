/**
 * Kiểm chạy được cho thứ tự dải trích dẫn (`xepTrichDan` / `nhomHieuLuc`).
 *
 * Vì sao phần này cần một kiểm: quy tắc "điều còn hiệu lực đọc trước, quy định
 * cũ xuống cuối" không có gì trong kiểu dữ liệu giữ nó lại. Một lần refactor
 * đổi `sort` thành `toSorted` trên mảng đã lọc, hay thêm một nhãn hiệu lực mới
 * mà quên xếp nhóm, đều làm dải trích dẫn trôi về thứ tự cũ mà KHÔNG có gì đỏ
 * lên. Hậu quả đúng bằng lỗi đã phải sửa: bốn mức lương đã chết xếp trước mức
 * đang áp dụng, đọc ra bốn câu trả lời cho một câu hỏi.
 *
 * Kiểm số 3 là cái quan trọng nhất — nó canh `chiSoGoc`. Sắp lại mà đánh số
 * theo mảng ĐÃ SẮP thì bấm một chip sẽ mở nguyên văn của một điều khác, tức
 * phá đúng lời hứa trung tâm của sản phẩm.
 *
 * Chạy: `npm run kiem-xep-trich-dan` (Node 22 đọc thẳng TypeScript, 0 thư viện).
 */
import assert from "node:assert/strict";
import { ghiChuHieuLuc, nhomHieuLuc, xepTrichDan } from "../src/lib/trich-dan.ts";

/** Đủ hình dạng cho `xepTrichDan` — nó chỉ đọc `hieu_luc`. */
const td = (ten: string, hieu_luc: string | null) => ({ ten, hieu_luc });

// 1. Bốn nhóm rơi đúng bậc.
{
  assert.equal(nhomHieuLuc("con_hieu_luc"), 1);
  assert.equal(nhomHieuLuc("chua_hieu_luc"), 2);
  assert.equal(nhomHieuLuc("bi_sua_doi"), 3);
  assert.equal(nhomHieuLuc("mot_phan_khong_xac_dinh"), 3);
  assert.equal(nhomHieuLuc("can_doi_chieu_tay"), 3);
  assert.equal(nhomHieuLuc("bi_thay_the"), 4);
  assert.equal(nhomHieuLuc("het_hieu_luc"), 4);
}

// 2. Nhãn lạ và `null` KHÔNG được rơi xuống nhóm 4. Nhóm 4 mang tiêu đề "đã
//    hết hiệu lực hoặc bị thay thế"; xếp một nhãn mình không hiểu vào đó là
//    tuyên bố một điều luật đã chết mà không có căn cứ nào.
{
  assert.equal(nhomHieuLuc(null), 3);
  assert.equal(nhomHieuLuc("chua_xac_dinh"), 3);
  assert.equal(nhomHieuLuc("mot_nhan_backend_them_sau"), 3);
}

// 3. Lượt lương tối thiểu THẬT (đo ngày 2026-09-01): backend trả mức đang áp
//    dụng ở giữa đám đã chết. Sau khi sắp, nó phải đứng đầu — và `chiSoGoc`
//    phải vẫn trỏ về vị trí cũ trong mảng gốc.
{
  const goc = [
    td("74/2024", "het_hieu_luc"),
    td("90/2019", "bi_thay_the"),
    td("293/2025", "con_hieu_luc"),
    td("157/2018", "bi_thay_the"),
    td("122/2015", "bi_thay_the"),
  ];
  const daSap = xepTrichDan(goc);

  assert.deepEqual(
    daSap.map((m) => m.trichDan.ten),
    ["293/2025", "74/2024", "90/2019", "157/2018", "122/2015"],
  );
  // Chỉ số gốc đi theo đúng phần tử của nó, không theo chỗ đứng mới.
  for (const muc of daSap) assert.equal(goc[muc.chiSoGoc], muc.trichDan);
  assert.equal(daSap[0]?.chiSoGoc, 2);
}

// 4. Sắp ỔN ĐỊNH: thứ tự backend trả về trong CÙNG một nhóm mang tín hiệu liên
//    quan, không được xáo.
{
  const goc = [
    td("cu-1", "bi_thay_the"),
    td("moi-1", "con_hieu_luc"),
    td("cu-2", "het_hieu_luc"),
    td("moi-2", "con_hieu_luc"),
    td("cu-3", "bi_thay_the"),
    td("dieu-kien", "bi_sua_doi"),
  ];
  assert.deepEqual(
    xepTrichDan(goc).map((m) => m.trichDan.ten),
    ["moi-1", "moi-2", "dieu-kien", "cu-1", "cu-2", "cu-3"],
  );
}

// 5. Không mất và không thêm phần tử nào — sắp lại, KHÔNG lọc. Trích dẫn hết
//    hiệu lực là bằng chứng của phát hiện trung tâm, xoá đi là vứt nó đi.
{
  const goc = [
    td("a", "bi_thay_the"),
    td("b", null),
    td("c", "con_hieu_luc"),
    td("d", "het_hieu_luc"),
  ];
  const daSap = xepTrichDan(goc);
  assert.equal(daSap.length, goc.length);
  assert.deepEqual([...daSap.map((m) => m.trichDan.ten)].sort(), ["a", "b", "c", "d"]);
  // Mảng gốc không bị sắp tại chỗ.
  assert.deepEqual(
    goc.map((m) => m.ten),
    ["a", "b", "c", "d"],
  );
}

// 6. Mảng rỗng không nổ.
{
  assert.deepEqual(xepTrichDan([]), []);
}

// 7. `ghiChuHieuLuc` lấy đúng câu của văn bản mình, và không nuốt câu của một
//    số hiệu khác có cùng phần đầu. Câu cảnh báo là nơi DUY NHẤT có ngày hiệu
//    lực — `Citation` không mang trường ngày nào.
{
  const canhBao = [
    "293/2025/NĐ-CP chưa có hiệu lực: ngày hiệu lực 2026-01-01 còn ở tương lai so với 2019-06-01",
    "90/2019/NĐ-CP chưa có hiệu lực: ngày hiệu lực 2020-01-01 còn ở tương lai so với 2019-06-01",
  ];
  assert.match(ghiChuHieuLuc("90/2019/NĐ-CP", canhBao) ?? "", /2020-01-01/);
  assert.equal(ghiChuHieuLuc("157/2018/NĐ-CP", canhBao), undefined);
  assert.equal(ghiChuHieuLuc("0/2019/NĐ-CP", canhBao), undefined);
  assert.equal(ghiChuHieuLuc("293/2025/NĐ-CP", []), undefined);
}

console.log("kiem-xep-trich-dan: 7 nhóm kiểm — ĐẠT");
