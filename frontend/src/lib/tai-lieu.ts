/**
 * Dữ kiện rút từ tài liệu người dùng — kiểu dữ liệu và quy tắc TRÌNH BÀY
 * (spec 2026-09-15).
 *
 * File này cố ý KHÔNG nhập gì: nó chạy được bằng `node` trần, nên
 * `scripts/kiem-tai-lieu.ts` kiểm được nó mà không cần dựng cả ứng dụng.
 * Phần gọi mạng nằm ở `tai-lieu-api.ts`.
 *
 * Quy tắc trình bày quan trọng nhất của module này: **một dữ kiện nói là đến từ
 * tài liệu thì phải chỉ được chỗ nó đến.** Giao diện không bao giờ hiện một giá
 * trị người dùng đã sửa với nhãn "từ tài liệu", và đoạn trích gốc luôn còn để
 * đối chiếu — cùng lời hứa mà `KhungDoiChieu` giữ cho trích dẫn điều luật.
 */

export type NguonDuKien = "tai_lieu" | "nguoi_dung_nhap" | "nguoi_dung_sua";

export interface DuKien {
  id: string | null;
  khoa: string;
  nhan: string | null;
  gia_tri: string;
  nguon: NguonDuKien;
  trich: string | null;
  trich_goc: string | null;
  trang: number | null;
  chi_so_don_vi: number | null;
}

export interface TaiLieu {
  id: string;
  trang_thai: "dang_doc" | "xong" | "hong" | "huy";
  so_trang: number | null;
  chay_nen: boolean;
  ly_do_hong: string | null;
  thong_diep: string | null;
  du_kien: DuKien[];
}

/** Đúng hai định dạng backend đọc được — FR-001. Ảnh và bản scan không nằm ở đây. */
export const DINH_DANG_CHAP_NHAN = ".pdf,.docx";
export const TRAN_BYTE = 20 * 1024 * 1024;

const NHAN_NGUON: Record<NguonDuKien, string> = {
  tai_lieu: "Từ tài liệu",
  nguoi_dung_nhap: "Bạn nhập",
  nguoi_dung_sua: "Bạn sửa",
};

/**
 * Nhãn nguồn hiển thị cạnh mỗi dữ kiện — FR-014.
 *
 * Ba nguồn, ba nhãn, không gộp. Người dùng phải phân biệt được ngay điều gì đến
 * từ giấy tờ của họ và điều gì do chính họ gõ vào, vì hai thứ đó có độ tin cậy
 * khác hẳn nhau khi đưa vào một văn bản pháp lý.
 */
export function nhanNguon(nguon: NguonDuKien): string {
  return NHAN_NGUON[nguon];
}

/** Dữ kiện này có bằng chứng bấm xem được không — FR-006. */
export function coNeo(dk: DuKien): boolean {
  return dk.nguon === "tai_lieu" && !!dk.trich && dk.trang !== null;
}

/**
 * Đoạn trích nào được hiện cho một dữ kiện.
 *
 * Với dữ kiện đã sửa thì hiện TRÍCH GỐC kèm ghi chú, không hiện nó như bằng
 * chứng cho giá trị mới: đoạn trích chứng minh giá trị cũ, và bày nó cạnh giá
 * trị mới là trưng ra một bằng chứng cho điều nó không chứng minh (FR-015).
 */
export function trichHienThi(dk: DuKien): { chu: string; laGoc: boolean } | null {
  if (dk.nguon === "tai_lieu" && dk.trich) return { chu: dk.trich, laGoc: false };
  if (dk.nguon === "nguoi_dung_sua" && dk.trich_goc) return { chu: dk.trich_goc, laGoc: true };
  return null;
}

/** Nhóm dữ kiện theo trang để bảng đọc theo thứ tự tài liệu. */
export function theoTrang(du_kien: DuKien[]): { trang: number | null; items: DuKien[] }[] {
  const nhom = new Map<number | null, DuKien[]>();
  for (const dk of du_kien) {
    const t = dk.nguon === "tai_lieu" ? dk.trang : null;
    if (!nhom.has(t)) nhom.set(t, []);
    nhom.get(t)!.push(dk);
  }
  return [...nhom.entries()]
    .sort((a, b) => (a[0] ?? Number.MAX_SAFE_INTEGER) - (b[0] ?? Number.MAX_SAFE_INTEGER))
    .map(([trang, items]) => ({ trang, items }));
}

/** Tên tệp có nằm trong hai định dạng đọc được không — chặn trước khi tải lên. */
export function dinhDangHopLe(tenTep: string): boolean {
  const ten = tenTep.toLowerCase();
  return ten.endsWith(".pdf") || ten.endsWith(".docx");
}

/**
 * Câu từ chối cho một tệp không gửi được, nói ĐÚNG việc người dùng làm tiếp.
 *
 * Trả `null` khi tệp gửi được. Kiểm ở đây là để phản hồi tức thì, không thay
 * cho kiểm ở backend: giao diện là tiện lợi, backend là ranh giới tin cậy.
 */
export function loiTruocKhiGui(tenTep: string, soByte: number): string | null {
  if (!dinhDangHopLe(tenTep))
    return "Chỉ gửi được tệp PDF có lớp chữ và tệp DOCX. Ảnh và bản scan chưa đọc được.";
  if (soByte > TRAN_BYTE) return "Tệp vượt giới hạn 20 MB.";
  return null;
}
