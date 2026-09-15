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

export type NguonDuKien = "tai_lieu" | "tai_lieu_ocr" | "nguoi_dung_nhap" | "nguoi_dung_sua";

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
  /** 0–1, CHỈ có với `tai_lieu_ocr`. Chữ đọc thẳng không có gì để đoán. */
  do_tin: number | null;
}

export interface TaiLieu {
  id: string;
  trang_thai: "dang_doc" | "xong" | "hong" | "huy";
  so_trang: number | null;
  chay_nen: boolean;
  ly_do_hong: string | null;
  thong_diep: string | null;
  /** Tài liệu này có phần nào đọc bằng OCR — giao diện phải nói ra. */
  co_ocr: boolean;
  du_kien: DuKien[];
}

/** Định dạng backend đọc được. Ảnh và bản scan đi qua OCR. */
export const DINH_DANG_CHAP_NHAN = ".pdf,.docx,.png,.jpg,.jpeg,.tif,.tiff,.webp";
export const TRAN_BYTE = 20 * 1024 * 1024;

const DUOI_ANH = [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".heic"];

/**
 * Dưới ngưỡng này thì nói thẳng với người dùng là nên kiểm lại bằng mắt.
 * Cùng con số backend dùng để loại nhiễu, nhưng ở đây nó phục vụ việc khác:
 * backend quyết định GIỮ HAY BỎ, giao diện quyết định CÓ CẢNH BÁO HAY KHÔNG.
 */
export const NGUONG_TIN_CANH_BAO = 0.85;

const NHAN_NGUON: Record<NguonDuKien, string> = {
  tai_lieu: "Từ tài liệu",
  tai_lieu_ocr: "Máy đọc từ ảnh",
  nguoi_dung_nhap: "Bạn nhập",
  nguoi_dung_sua: "Bạn sửa",
};

/**
 * Nhãn nguồn hiển thị cạnh mỗi dữ kiện — FR-014.
 *
 * Bốn nguồn, bốn nhãn, không gộp. "Từ tài liệu" và "Máy đọc từ ảnh" đặc biệt
 * không được gộp: cái đầu nghĩa là tài liệu viết đúng câu đó, cái sau chỉ nghĩa
 * là máy nhìn ảnh và đoán ra câu đó. Người dùng sắp đưa con số này vào một văn
 * bản pháp lý, nên họ phải biết mình đang tin cái nào.
 */
export function nhanNguon(nguon: NguonDuKien): string {
  return NHAN_NGUON[nguon];
}

/** Dữ kiện này đến từ tài liệu (dù bằng lớp chữ hay bằng OCR). */
export function tuTaiLieu(dk: DuKien): boolean {
  return dk.nguon === "tai_lieu" || dk.nguon === "tai_lieu_ocr";
}

/** Dữ kiện này có bằng chứng bấm xem được không — FR-006. */
export function coNeo(dk: DuKien): boolean {
  return tuTaiLieu(dk) && !!dk.trich && dk.trang !== null;
}

/**
 * Câu cảnh báo khi bằng chứng yếu, hoặc `null` khi không cần cảnh báo gì.
 *
 * Chỉ OCR mới có cảnh báo, và chỉ khi độ tin thấp. Cảnh báo mọi dòng OCR sẽ
 * làm người dùng bỏ qua cảnh báo — đúng cách một lời nhắc tự vô hiệu hoá.
 */
export function canhBaoDoTin(dk: DuKien): string | null {
  if (dk.nguon !== "tai_lieu_ocr") return null;
  if (dk.do_tin !== null && dk.do_tin >= NGUONG_TIN_CANH_BAO) return null;
  return "Máy đọc chưa chắc chắn ở dòng này. Hãy đối chiếu với bản gốc trước khi dùng.";
}

/**
 * Đoạn trích nào được hiện cho một dữ kiện.
 *
 * Với dữ kiện đã sửa thì hiện TRÍCH GỐC kèm ghi chú, không hiện nó như bằng
 * chứng cho giá trị mới: đoạn trích chứng minh giá trị cũ, và bày nó cạnh giá
 * trị mới là trưng ra một bằng chứng cho điều nó không chứng minh (FR-015).
 */
export function trichHienThi(dk: DuKien): { chu: string; laGoc: boolean } | null {
  if (tuTaiLieu(dk) && dk.trich) return { chu: dk.trich, laGoc: false };
  if (dk.nguon === "nguoi_dung_sua" && dk.trich_goc) return { chu: dk.trich_goc, laGoc: true };
  return null;
}

/** Nhóm dữ kiện theo trang để bảng đọc theo thứ tự tài liệu. */
export function theoTrang(du_kien: DuKien[]): { trang: number | null; items: DuKien[] }[] {
  const nhom = new Map<number | null, DuKien[]>();
  for (const dk of du_kien) {
    const t = tuTaiLieu(dk) ? dk.trang : null;
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
  return ten.endsWith(".pdf") || ten.endsWith(".docx") || DUOI_ANH.some((d) => ten.endsWith(d));
}

/** Tệp này sẽ phải đi qua OCR — dùng để báo trước rằng kết quả là chữ máy đọc. */
export function seDungOcr(tenTep: string): boolean {
  return DUOI_ANH.some((d) => tenTep.toLowerCase().endsWith(d));
}

/**
 * Câu từ chối cho một tệp không gửi được, nói ĐÚNG việc người dùng làm tiếp.
 *
 * Trả `null` khi tệp gửi được. Kiểm ở đây là để phản hồi tức thì, không thay
 * cho kiểm ở backend: giao diện là tiện lợi, backend là ranh giới tin cậy.
 */
export function loiTruocKhiGui(tenTep: string, soByte: number): string | null {
  if (!dinhDangHopLe(tenTep)) return "Gửi được tệp PDF, DOCX, hoặc ảnh (PNG, JPG, TIFF, WEBP).";
  if (soByte > TRAN_BYTE) return "Tệp vượt giới hạn 20 MB.";
  return null;
}
