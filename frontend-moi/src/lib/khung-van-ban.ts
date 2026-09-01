/**
 * Dựng khung thân văn bản từ `cau_truc` của máy chủ — thuần dữ liệu, không JSX.
 *
 * Vì sao tách riêng khỏi `soan-thao.$loaiVanBan.tsx`: bộ dựng thân văn bản cũ
 * nằm thẳng trong route, viết cứng, và chỉ rẽ hai nhánh (`hdld` / thử việc).
 * Hai mươi ba loại còn lại rơi hết vào một khuôn HỢP ĐỒNG THƯƠNG MẠI HAI BÊN:
 * `/soan-thao/cong-van` mang tiêu đề CÔNG VĂN rồi dựng `BÊN A / BÊN B`, `Mã số
 * thuế`, `Điều 2. Giá trị hợp đồng`, `Điều 4. Phạt vi phạm hợp đồng` và khối ký
 * hai bên. Người dùng tải về một `.docx` đúng thể thức mà SAI LOẠI VĂN BẢN.
 *
 * Khung ở đây không phát minh gì. Nó đọc `cau_truc` — chính `checklist_*.yaml`
 * mà `/soan-thao` và `/soat` dùng — nên thân văn bản và bản soát không thể lệch
 * nhau. Máy chủ sinh `# {tieu_de}` rồi `## {don_vi_muc} {stt}. {ten}`, KHÔNG có
 * phần khung nào khác; với `cong_van` thì quốc hiệu / nơi nhận / chữ ký chính
 * là các `muc`, còn với `hdld` chúng vắng mặt vì BLLĐ Điều 21 không đòi.
 *
 * Kiểm: `npm run kiem-khung`.
 */
import type { CauTruc, MucCauTruc } from "./klaw";

/**
 * Ba năng lực soát KHÁC NHAU, nên ba nhãn khác nhau.
 *
 * `the_thuc_kem_rule` là ca lai và nó có thật: `quyet_dinh_bo_nhiem` trả về
 * `pham_vi_soat: "the_thuc"` NHƯNG `chi_soat_the_thuc: false`, vì ngoài 9 thành
 * phần thể thức nó còn một quy tắc nhiệm kỳ thật (LDN Điều 162 khoản 2, trần 05
 * năm). Gộp nó vào nhóm chỉ-thể-thức là giấu mất quy tắc duy nhất thực sự đọc
 * nội dung; gộp vào nhóm soát-nội-dung là hứa rằng KLAW đọc hiểu cả quyết định.
 */
export type PhamViSoat = "noi_dung" | "the_thuc" | "the_thuc_kem_rule";

export function phamViSoatCua(c: CauTruc): PhamViSoat {
  if (c.chi_soat_the_thuc) return "the_thuc";
  return c.pham_vi_soat === "the_thuc" ? "the_thuc_kem_rule" : "noi_dung";
}

export const NHAN_PHAM_VI: Record<PhamViSoat, string> = {
  noi_dung: "Soát được với KLAW",
  the_thuc: "Soát thể thức, không soát nội dung",
  the_thuc_kem_rule: "Soát thể thức + 01 quy tắc nhiệm kỳ",
};

/** Một mục đã sẵn sàng để hiển thị: tiêu đề đánh số và căn cứ đã tách. */
export type MucKhung = {
  key: string;
  stt: number;
  /** `Điều 1. Công việc và địa điểm làm việc` */
  tieuDe: string;
  ten: string;
  batBuoc: boolean;
  /** `null` khi `can_cu` rỗng hoặc không tách được số hiệu. */
  canCu: { soHieu: string; nhan: string } | null;
};

/**
 * Tách `45/2019/QH14 > Điều 21 > Khoản 1 > Điểm a` thành số hiệu và phần còn
 * lại. Chip căn cứ cần hai mảnh này rời nhau; trước đây chúng được ĐOÁN trong
 * route (`{ soHieu: "36/2005/QH11", nhan: "Điều 74" }` viết tay cạnh một điều
 * khoản chẳng liên quan), nay lấy đúng chuỗi máy chủ gửi kèm từng mục.
 */
export function tachCanCu(canCu: string): { soHieu: string; nhan: string } | null {
  const phan = canCu
    .split(">")
    .map((p) => p.trim())
    .filter(Boolean);
  if (phan.length === 0) return null;
  const [soHieu, ...con] = phan;
  if (soHieu === undefined || soHieu === "") return null;
  return { soHieu, nhan: con.join(", ") };
}

/** `Điều 1. Công việc và địa điểm làm việc` — đúng cách máy chủ đánh số. */
export function tieuDeMuc(donViMuc: string, m: MucCauTruc): string {
  return `${donViMuc} ${m.stt}. ${m.ten}`;
}

/** Toàn bộ thân văn bản, theo đúng thứ tự và cách đánh số của `cau_truc`. */
export function dungKhung(c: CauTruc): MucKhung[] {
  return c.muc.map((m) => ({
    key: m.key,
    stt: m.stt,
    tieuDe: tieuDeMuc(c.don_vi_muc, m),
    ten: m.ten,
    batBuoc: m.bat_buoc,
    canCu: tachCanCu(m.can_cu),
  }));
}

/**
 * Mục nào là một BÊN của văn bản, và bên đó lấy dữ liệu từ ô nào của biểu mẫu.
 *
 * Khoá ở đây là khoá THẬT máy chủ gửi trong `cau_truc.muc`, không phải nhãn do
 * giao diện đặt. Nhờ vậy khối các bên chỉ hiện ra khi chính checklist đòi một
 * bên — `cong_van` không có mục nào như thế nên không còn `BÊN A / BÊN B`, còn
 * `hdld` có `nsdld` và `nld` nên hai khối ấy vẫn dựng như cũ.
 */
export const MUC_BEN: Record<string, "A" | "B"> = {
  // lao động — BLLĐ Điều 21 khoản 1 điểm a, b
  nsdld: "A",
  nld: "B",
  // uỷ quyền — BLDS Điều 138 khoản 1
  ben_uy_quyen: "A",
  ben_duoc_uy_quyen: "B",
  // tố tụng — BLTTDS Điều 189, Luật Khiếu nại Điều 8 khoản 2
  nguoi_khoi_kien: "A",
  nguoi_bi_kien: "B",
  nguoi_yeu_cau: "A",
  nguoi_khieu_nai: "A",
  nguoi_bi_khieu_nai: "B",
  // xử phạt hành chính — Luật XLVPHC Điều 61 khoản 2
  nguoi_giai_trinh: "A",
  nguoi_co_tham_quyen: "B",
  // cơ quan ban hành — NĐ 30/2020 Điều 8 khoản 2 điểm b
  ten_co_quan: "A",
  ten_doanh_nghiep: "A",
};

/**
 * Mục nào chỉ đòi CÁI TÊN, không đòi hồ sơ đầy đủ của bên đó.
 *
 * NĐ 30/2020 Điều 8 khoản 2 điểm b đòi đúng "tên cơ quan, tổ chức ban hành văn
 * bản" — không mã số thuế, không số điện thoại, không người đại diện. Đổ cả
 * khối hồ sơ doanh nghiệp vào đấy là dựng lại đúng thói quen vừa gỡ: in lên
 * công văn những dòng chỉ hợp đồng thương mại mới cần.
 */
export const MUC_CHI_TEN = new Set(["ten_co_quan", "ten_doanh_nghiep"]);

/**
 * Mục nào LUÔN LUÔN là một thể nhân, bất kể ô "loại bên" trên biểu mẫu chọn gì.
 *
 * BLLĐ Điều 21 khoản 1 điểm b đòi "họ tên, ngày sinh, giới tính, nơi cư trú, số
 * CCCD của NGƯỜI LAO ĐỘNG" — người lao động không thể là một tổ chức. Để ô chọn
 * của biểu mẫu quyết định chỗ này thì mặc định "tổ chức" sẽ in ra một hợp đồng
 * lao động ký với một doanh nghiệp, kèm mục "Người đại diện theo pháp luật" ở
 * đúng chỗ luật đòi ngày sinh và số CCCD.
 *
 * Chỉ `nld` nằm ở đây. Người khởi kiện, người khiếu nại, bên uỷ quyền đều có
 * thể là tổ chức, nên chúng vẫn theo ô chọn của biểu mẫu.
 */
export const MUC_CA_NHAN = new Set(["nld"]);

/** Mục nào là ô ký. Chỉ những mục này mới dựng khối chữ ký. */
export const MUC_KY = new Set(["chu_ky", "ky_ten", "chuc_vu_chu_ky"]);

/**
 * Mục nào lấy được nội dung từ biểu mẫu hiện có, và lấy phần nào.
 *
 * CỐ Ý HẸP. Ghép bừa một ô vào một mục nghe na ná là dựng lại đúng cái lỗi vừa
 * sửa, chỉ ở quy mô nhỏ hơn: đổ `giaTri` (giá trị hợp đồng) vào mục `luong`
 * của HĐLĐ sẽ in một con số sai vào chỗ luật đòi mức lương. Mục nào không có ô
 * khớp một–một thì để trống có nhãn, và ô trống nói thật.
 */
export type PhanND = "cong_viec" | "dich_vu" | "thoi_han" | "thu_viec" | "luong" | "tien";

export const MUC_ND: Record<string, PhanND> = {
  cong_viec: "cong_viec",
  cong_viec_dich_vu: "dich_vu",
  thoi_han: "thoi_han",
  thoi_gian_thu_viec: "thu_viec",
  luong: "luong",
  gia: "tien",
  gia_va_thanh_toan: "tien",
  gia_thanh_toan: "tien",
  tien_dich_vu: "tien",
};
