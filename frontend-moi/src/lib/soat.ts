/**
 * Trạng thái tổng của một lượt `POST /soat` — bảo đảm #11.
 *
 * `audit_report.dat` một mình KHÔNG đủ để chọn cách hiển thị, vì nó chỉ nói
 * "không có phát hiện chặn nào". Nó im lặng về việc bao nhiêu rule đã không
 * chạy được vì thiếu dữ kiện (`finding.khong_kiem_duoc`).
 *
 * Hai câu dưới đây rất khác nhau và người dùng phải phân biệt được ngay từ
 * hình dạng của khay, trước khi đọc chữ:
 *
 *   - "Đã soát, không thấy vấn đề gì."
 *   - "Đã soát phần soát được; những rule quan trọng nhất thì chưa chạy."
 *
 * ĐO TRÊN MÁY CHỦ ĐANG CHẠY: một hợp đồng đủ 10 nội dung bắt buộc trả về
 * `dat = true` với `completeness = 1.0` và NĂM rule `khong_kiem_duoc`, trong
 * đó có lương tối thiểu vùng và cấm phạt tiền người lao động. Gộp ca đó vào ca
 * sạch là in một dấu tích xanh lên một bản hợp đồng chưa ai kiểm.
 */
export type TrangThaiSoat = "dat" | "dat_mot_phan" | "khong_dat";

export function trangThaiSoat(dat: boolean, soRuleChuaKiem: number): TrangThaiSoat {
  if (!dat) return "khong_dat";
  // Không có ngưỡng "ít thì bỏ qua": một rule chưa chạy duy nhất vẫn có thể
  // chính là rule lương tối thiểu vùng.
  return soRuleChuaKiem > 0 ? "dat_mot_phan" : "dat";
}
