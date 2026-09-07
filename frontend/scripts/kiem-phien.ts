/**
 * Kiểm chạy được cho phần phiên hội thoại (spec 2026-09-07 §8): câu "đang ẩn"
 * theo số, thời gian tương đối tất định, và hai predicate hình dạng với payload
 * thiếu trường — 2xx sai hình dạng phải rơi về `invalid_response`, không hiển
 * thị một danh sách rỗng trông như thật. Chạy: `npm run kiem-phien`.
 */
import assert from "node:assert/strict";
import { chuanHoaLuot, laChiTietPhien, laDanhSachPhien } from "../src/lib/klaw.ts";
import { cauPhienAn, tenGoi, thoiGianTuongDoi } from "../src/lib/phien.ts";

// 1. Tên gói và câu ẩn.
{
  assert.equal(tenGoi("free"), "Miễn phí");
  assert.equal(tenGoi("pro"), "Pro");
  assert.equal(tenGoi("la"), "la");
  assert.equal(
    cauPhienAn("free", 10, 3),
    "Gói Miễn phí giữ 10 phiên gần nhất. 3 phiên cũ hơn đang ẩn.",
  );
}

// 2. Thời gian tương đối — mốc cố định để kiểm không lệch theo giờ chạy.
{
  const moc = Date.parse("2026-09-07T10:00:00Z");
  const luc = (giay: number) => new Date(moc - giay * 1000).toISOString();
  assert.equal(thoiGianTuongDoi(luc(20), moc), "vừa xong");
  assert.equal(thoiGianTuongDoi(luc(5 * 60), moc), "5 phút trước");
  assert.equal(thoiGianTuongDoi(luc(3 * 3600), moc), "3 giờ trước");
  assert.equal(thoiGianTuongDoi(luc(26 * 3600), moc), "hôm qua");
  assert.equal(thoiGianTuongDoi(luc(4 * 86400), moc), "4 ngày trước");
  assert.equal(thoiGianTuongDoi(luc(40 * 86400), moc), "29/07/2026");
  assert.equal(thoiGianTuongDoi("không phải ngày", moc), "");
}

// 3. Predicate: đủ trường thì qua, thiếu `items`/`luot` thì chặn.
{
  const phien = { id: "a", tieu_de: "t", so_luot: 1, tao_luc: "x", cap_nhat_luc: "y" };
  assert.ok(laDanhSachPhien({ plan: "free", luot_moi_phien: 10, tong: 1, items: [phien] }));
  assert.equal(laDanhSachPhien({ plan: "free", tong: 1 }), false);
  assert.equal(laDanhSachPhien(null), false);
  assert.ok(laChiTietPhien({ id: "a", tieu_de: "t", tao_luc: "x", cap_nhat_luc: "y", luot: [] }));
  assert.equal(laChiTietPhien({ id: "a" }), false);
}

// 4. `chuanHoaLuot`: payload thiếu trường → `ketQua: null`, câu hỏi vẫn giữ.
{
  const l = chuanHoaLuot({
    thu_tu: 1,
    cau_hoi: "Hỏi?",
    tra_loi: { answer: "x" },
    trace_id: null,
    tao_luc: "z",
  });
  assert.equal(l.ketQua, null);
  assert.equal(l.cauHoi, "Hỏi?");
  assert.equal(l.thuTu, 1);
}
console.info("kiem-phien: 4/4 đạt");
