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

/** Chữ của một đơn vị đến từ đâu: lớp chữ của tệp, hay máy nhìn ảnh đoán ra. */
export type NguonChu = "lop_chu" | "ocr";

/** Đơn vị nằm ở thân tài liệu, ở đầu trang hay ở chân trang. */
export type VungTaiLieu = "than" | "dau_trang" | "chan_trang";

/**
 * Một **đơn vị văn bản** đã đọc — mẩu liền mạch nhỏ nhất mà một neo chỉ tới
 * được (`CONTEXT.md`, mục "User documents").
 *
 * `chi_so` là số thứ tự trong tài liệu, KHÔNG phải số đoạn của người đọc: neo
 * do backend kiểm bằng cách dò chuỗi trong đúng đơn vị mang chỉ số này, nên hai
 * bên phải đếm cùng một kiểu.
 */
export interface DonVi {
  chi_so: number;
  trang: number | null;
  offset_dau: number;
  noi_dung: string;
  nguon_chu: NguonChu;
  do_tin: number | null;
  vung: VungTaiLieu;
  /** `[bảng, hàng, cột]`, hoặc `null` khi đơn vị không nằm trong bảng nào. */
  bang: [number, number, number] | null;
}

/** Thân của `GET /tai-lieu/{id}/don-vi` — toàn bộ phần đã đọc của một tài liệu. */
export interface DonViTaiLieu {
  id: string;
  ten_tep: string;
  so_trang: number | null;
  don_vi: DonVi[];
}

export interface TaiLieu {
  id: string;
  /** Cuộc trò chuyện tài liệu này thuộc về. Đính kèm ở một đoạn chat CHƯA mở
   *  không gửi `hoi_thoai_id` nào, và máy chủ mở phiên hộ — đây là chỗ giao
   *  diện biết phiên đó là phiên nào để ghim lên `?phien=` và hỏi tiếp vào nó. */
  hoi_thoai_id: string;
  /** `can_chon_loai` CHỈ còn ở bản ghi cũ: từ 2026-09-16 một tài liệu không
   *  khớp mẫu nào vẫn về `xong` với `du_kien: []` — xem `docs/plans/active/
   *  tai-lieu-tong-quat.md`. Giữ nhãn để lượt đã lưu trước đó còn hiện được. */
  trang_thai: "dang_doc" | "can_chon_loai" | "xong" | "hong" | "huy";
  so_trang: number | null;
  /** Số đơn vị văn bản đọc được. Đây là thứ nói với người dùng rằng máy ĐÃ đọc
   *  được tài liệu, kể cả khi không rút được dữ kiện nào theo mẫu. */
  so_don_vi: number;
  /** Một câu máy tự mô tả tài liệu này, hoặc `null` khi chưa có. */
  mo_ta: string | null;
  ten_tep: string;
  chay_nen: boolean;
  ly_do_hong: string | null;
  thong_diep: string | null;
  /** Tài liệu này có phần nào đọc bằng OCR — giao diện phải nói ra. */
  co_ocr: boolean;
  loai: string | null;
  loai_ten: string | null;
  /** Hệ thống tự nhận ra, không phải người dùng chọn. Giả định phải hiện thành
   *  chữ và sửa được một chạm — `docs/bo-luat-agent.md` QT-5. */
  loai_tu_doan: boolean;
  /** Dòng trong tài liệu đã dẫn tới kết luận. */
  loai_can_cu: string | null;
  du_kien: DuKien[];
  /** Tệp được giữ làm khuôn gốc (quyết định 2026-09-26): "Bản tải lên" vẽ
   *  được nó đúng như tệp, và "Điền biểu mẫu" điền được tại chỗ. Vắng ở máy chủ
   *  cũ; `false` với ảnh và tài liệu tải lên trước đó. */
  co_khuon_goc?: boolean;
}

/** Định dạng backend đọc được. Ảnh và bản scan đi qua OCR. */
export const DINH_DANG_CHAP_NHAN = ".pdf,.docx,.doc,.png,.jpg,.jpeg,.tif,.tiff,.webp";
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

const CAU_CANH_BAO_OCR =
  "Máy đọc chưa chắc chắn ở dòng này. Hãy đối chiếu với bản gốc trước khi dùng.";

/**
 * Câu cảnh báo cho một mẩu chữ máy đọc từ ảnh, hoặc `null` khi không cần.
 *
 * Chỉ OCR mới có cảnh báo, và chỉ khi độ tin thấp. Cảnh báo mọi dòng OCR sẽ
 * làm người dùng bỏ qua cảnh báo — đúng cách một lời nhắc tự vô hiệu hoá.
 *
 * Dữ kiện (`canhBaoDoTin`) và neo tài liệu (`nguon_chu === "ocr"`) đi qua CÙNG
 * hàm này: hai chỗ hiển thị, một ngưỡng, một câu chữ. Tách đôi là để hai màn
 * hình dần nói hai điều khác nhau về cùng một mức tin cậy.
 */
export function canhBaoOcr(laOcr: boolean, doTin: number | null): string | null {
  if (!laOcr) return null;
  if (doTin !== null && doTin >= NGUONG_TIN_CANH_BAO) return null;
  return CAU_CANH_BAO_OCR;
}

/** Câu cảnh báo khi bằng chứng của một dữ kiện yếu, hoặc `null`. */
export function canhBaoDoTin(dk: DuKien): string | null {
  return canhBaoOcr(dk.nguon === "tai_lieu_ocr", dk.do_tin);
}

const NHAN_VUNG: Record<string, string> = {
  than: "thân tài liệu",
  dau_trang: "đầu trang",
  chan_trang: "chân trang",
};

/** Tên vùng đọc được. Vùng lạ (backend thêm sau) rơi về chính mã của nó. */
export function nhanVung(vung: string): string {
  return NHAN_VUNG[vung] ?? vung;
}

/**
 * Nhãn của một neo tài liệu — chữ trên con chip bấm để mở đúng chỗ đó.
 *
 * Nhãn phải ĐỊNH VỊ ĐƯỢC BẰNG MẮT trên tờ giấy người dùng đang cầm: "tr. 1 ·
 * bảng 1, h5 c2" tìm được trong ba giây, còn "đơn vị #28" thì không tìm được
 * bao giờ. Đầu trang và chân trang thay chỗ số trang vì chúng lặp ở mọi trang —
 * nói "tr. 3" cho một dòng chân trang là chỉ sai chỗ.
 */
export function nhanNeo(neo: {
  trang: number | null;
  chi_so_don_vi: number;
  vung?: string | undefined;
  bang?: [number, number, number] | null | undefined;
}): string {
  const viTri =
    neo.vung !== undefined && neo.vung !== "than"
      ? nhanVung(neo.vung)
      : neo.trang === null
        ? "không rõ trang"
        : `tr. ${neo.trang}`;
  const trong = neo.bang
    ? `bảng ${neo.bang[0]}, h${neo.bang[1]} c${neo.bang[2]}`
    : `đoạn ${neo.chi_so_don_vi}`;
  return `${viTri} · ${trong}`;
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
  return (
    ten.endsWith(".pdf") ||
    ten.endsWith(".docx") ||
    ten.endsWith(".doc") ||
    DUOI_ANH.some((d) => ten.endsWith(d))
  );
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
  if (!dinhDangHopLe(tenTep))
    return "Gửi được tệp PDF, DOCX, DOC, hoặc ảnh (PNG, JPG, TIFF, WEBP).";
  if (soByte > TRAN_BYTE) return "Tệp vượt giới hạn 20 MB.";
  return null;
}

/**
 * Đường dẫn của từng endpoint, TÍNH TỪ GỐC API.
 *
 * `apiGoc()` đã chứa `/api/v1`, nên đường dẫn ở đây KHÔNG được lặp lại nó. Sai
 * chỗ này cho `/api/v1/api/v1/...` và một 404 mà mọi test phía máy chủ đều
 * không thấy — chúng gọi thẳng ứng dụng FastAPI, không đi qua client này. Tách
 * ra thành hàm thuần để `scripts/kiem-tai-lieu.ts` khoá được lớp lỗi đó.
 */
export const DUONG_DAN = {
  taiLen: () => "/tai-lieu",
  chiTiet: (viecId: string) => `/tai-lieu/${encodeURIComponent(viecId)}`,
  donVi: (viecId: string) => `/tai-lieu/${encodeURIComponent(viecId)}/don-vi`,
  huy: (viecId: string) => `/tai-lieu/${encodeURIComponent(viecId)}/huy`,
  duKien: (duKienId: string) => `/tai-lieu/du-kien/${encodeURIComponent(duKienId)}`,
  theoHoiThoai: (hoiThoaiId: string) => `/tai-lieu/hoi-thoai/${encodeURIComponent(hoiThoaiId)}`,
  sangSoanThao: (hoiThoaiId: string, loai: string, ghi: boolean) =>
    `/tai-lieu/hoi-thoai/${encodeURIComponent(hoiThoaiId)}/du-kien?loai=${encodeURIComponent(loai)}` +
    (ghi ? "&ghi=true" : ""),
} as const;
