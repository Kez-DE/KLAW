/**
 * Kiểm chạy được cho phần phiên hội thoại (spec 2026-09-07 §8): thời gian
 * tương đối tất định, và hai predicate hình dạng với payload thiếu trường —
 * 2xx sai hình dạng phải rơi về `invalid_response`, không hiển thị một danh
 * sách rỗng trông như thật. Chạy: `npm run kiem-phien`.
 */
import assert from "node:assert/strict";
import { chuanHoaLuot, laChiTietPhien, laDanhSachPhien } from "../src/lib/klaw.ts";
import { thoiGianTuongDoi, vaBanThaoGanDay } from "../src/lib/phien.ts";

// 1. Thời gian tương đối — mốc cố định để kiểm không lệch theo giờ chạy.
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

// 2. Predicate: đủ trường thì qua, thiếu `items`/`luot` thì chặn.
{
  const phien = { id: "a", tieu_de: "t", so_luot: 1, tao_luc: "x", cap_nhat_luc: "y" };
  assert.ok(laDanhSachPhien({ plan: "free", luot_moi_phien: 10, tong: 1, items: [phien] }));
  assert.equal(laDanhSachPhien({ plan: "free", tong: 1 }), false);
  assert.equal(laDanhSachPhien(null), false);
  assert.ok(laChiTietPhien({ id: "a", tieu_de: "t", tao_luc: "x", cap_nhat_luc: "y", luot: [] }));
  assert.equal(laChiTietPhien({ id: "a" }), false);
}

// 3. `chuanHoaLuot`: payload thiếu trường → `ketQua: null`, câu hỏi vẫn giữ.
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

// 4. `vaBanThaoGanDay`: lưu/lùi/lượt chat ra phiên bản mới → danh sách "Bản
// thảo" của vỏ trang đổi TẠI CHỖ (không gọi lại máy chủ), bản đó lên đầu.
{
  const tt = (id: string, phien_ban: number) => ({
    id,
    loai: "tong_quat",
    ten: `Bản ${id}`,
    phien_ban,
    cap_nhat_luc: "2026-09-27T08:00:00Z",
    hoi_thoai_id: "p",
  });
  const ds = [tt("a", 1), tt("b", 1)];
  const LUC = "2026-09-27T09:00:00Z";
  assert.deepEqual(
    vaBanThaoGanDay(ds, { id: "b", ten: "Bản b", phien_ban: 3 }, LUC),
    [{ ...tt("b", 3), cap_nhat_luc: LUC }, tt("a", 1)],
    "phiên bản 1 → 3: đúng số mới, lên đầu, giữ `hoi_thoai_id`",
  );
  assert.equal(
    vaBanThaoGanDay(ds, { id: "a", ten: "Bản a", phien_ban: 1 }, LUC),
    ds,
    "cùng phiên bản (lượt chat trả bản có sẵn): giữ nguyên danh sách",
  );
  assert.equal(
    vaBanThaoGanDay(ds, { id: "c", ten: "Bản c", phien_ban: 1 }, LUC),
    null,
    "bản chưa có trong danh sách (vừa tạo): nơi gọi tải lại",
  );
}
console.info("kiem-phien: 4/4 đạt");
