// Kho văn bản KLAW — kiểu dữ liệu, từ vựng bộ lọc và hàm truy vấn.

export type LoaiVanBan =
  | "Hiến pháp"
  | "Bộ luật"
  | "Luật"
  | "Pháp lệnh"
  | "Nghị quyết"
  | "Nghị định"
  | "Quyết định"
  | "Thông tư"
  | "Thông tư liên tịch"
  | "Công văn"
  | "Văn bản hợp nhất";

export const LOAI_VAN_BAN: LoaiVanBan[] = [
  "Hiến pháp",
  "Bộ luật",
  "Luật",
  "Pháp lệnh",
  "Nghị quyết",
  "Nghị định",
  "Quyết định",
  "Thông tư",
  "Thông tư liên tịch",
  "Công văn",
  "Văn bản hợp nhất",
];

export const CO_QUAN = [
  "Quốc hội",
  "Ủy ban Thường vụ Quốc hội",
  "Chính phủ",
  "Thủ tướng Chính phủ",
  "Bộ Lao động - Thương binh và Xã hội",
  "Bộ Tài chính",
  "Bộ Công an",
  "Hội đồng Thẩm phán Tòa án nhân dân tối cao",
];

// LINH_VUC đã gỡ: danh sách 10 lĩnh vực của bản Lovable gồm Đất đai, Thuế,
// Đầu tư, Sở hữu trí tuệ — đúng những lĩnh vực PRODUCT.md nói KLAW KHÔNG phủ.
// Cơ sở dữ liệu cũng chưa có cột linh_vuc nào (việc của pha 1).

export type TinhTrang =
  | "Còn hiệu lực"
  | "Chưa có hiệu lực"
  | "Hết hiệu lực một phần"
  | "Đã sửa đổi, bổ sung"
  | "Hết hiệu lực";

export const TINH_TRANG: TinhTrang[] = [
  "Còn hiệu lực",
  "Chưa có hiệu lực",
  "Hết hiệu lực một phần",
  "Đã sửa đổi, bổ sung",
  "Hết hiệu lực",
];

export type Diem = {
  ky: string; // a, b, c
  text: string;
  suaDoiBoi?: string;
  baiBo?: boolean;
};

export type Khoan = {
  so: number;
  text: string;
  diem?: Diem[];
  suaDoiBoi?: string;
  baiBo?: boolean;
};

export type Dieu = {
  so: number;
  tieuDe: string;
  muc?: string; // "Mục 1. ..." nếu có
  tieuMuc?: string;
  khoan: Khoan[];
  soVanBanSuaDoi?: number;
};

export type Chuong = {
  so: string; // I, II, III
  ten: string;
  phan?: string;
  dieu: Dieu[];
};

export type QuanHe = {
  nhom:
    | "Văn bản được dẫn chiếu"
    | "Văn bản sửa đổi, bổ sung"
    | "Văn bản bị thay thế"
    | "Văn bản hướng dẫn thi hành"
    | "Văn bản liên quan cùng lĩnh vực";
  items: { soHieu: string; ten: string }[];
};

export type VanBan = {
  soHieu: string;
  ten: string;
  tenNgan: string; // dùng cho chuỗi trích dẫn
  loai: LoaiVanBan;
  coQuan: string;
  nguoiKy: string;
  chucVu: string;
  ngayBanHanh: string;
  ngayHieuLuc: string;
  ngayHetHieuLuc?: string;
  linhVuc: string;
  tinhTrang: TinhTrang;
  canhBao?: string;
  chuong: Chuong[];
  quanHe: QuanHe[];
};

// Kho văn bản của KLAW. Cấu trúc kiểu và các hàm truy vấn ở đây là hợp đồng mà
// pha nối backend sẽ trỏ vào; DỮ LIỆU thì không có ở đây.
//
// Bản Lovable nhúng 491 dòng "SAMPLE DATA FOR UI DEMO ONLY" — điều luật bịa,
// trích dẫn bịa, tình trạng hiệu lực bịa. Với một sản phẩm pháp luật, đó là chế
// độ hỏng tệ nhất: người đọc không có cách nào phân biệt một điều khoản dựng
// sẵn với một điều khoản thật. Toàn bộ khối đó đã bị xoá, không được thay bằng
// một khối minh hoạ khác.
//
// Cho tới khi màn tra cứu gọi được API KLAW, kho rỗng và các màn dùng nó phải
// nói rõ là CHƯA NỐI — không phải "không tìm thấy kết quả", vì hai câu đó nói
// hai chuyện khác nhau.
export const KHO_DA_NOI = false;

export const VAN_BAN: VanBan[] = [];

/* ------------------------------ Tra cứu helpers --------------------------- */

export const boDau = (s: string) =>
  s
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/gi, "d")
    .toLowerCase();

export const VIET_TAT: Record<string, string> = {
  bllđ: "Bộ luật Lao động",
  blld: "Bộ luật Lao động",
  blds: "Bộ luật Dân sự",
  blhs: "Bộ luật Hình sự",
  ldn: "Luật Doanh nghiệp",
  ltm: "Luật Thương mại",
  nđ: "Nghị định",
  nd: "Nghị định",
  tt: "Thông tư",
  qđ: "Quyết định",
  qd: "Quyết định",
  nq: "Nghị quyết",
  vbhn: "Văn bản hợp nhất",
};

export const DONG_NGHIA: Record<string, string[]> = {
  "sa thai": ["kỷ luật lao động", "đơn phương chấm dứt hợp đồng lao động"],
  "thu viec": ["hợp đồng thử việc", "tiền lương thử việc"],
  "phat hop dong": ["phạt vi phạm", "bồi thường thiệt hại"],
  "du lieu ca nhan": ["sự đồng ý của chủ thể dữ liệu", "đánh giá tác động xử lý dữ liệu"],
};

const SO_HIEU_RE = /^\s*\d{1,4}\/\d{4}\/[A-Za-zĐđ\-.]+\s*$/;

export const laSoHieu = (q: string) => SO_HIEU_RE.test(q);

export const timVanBanTheoSoHieu = (q: string): VanBan | undefined => {
  const n = boDau(decodeURIComponent(q).trim());
  return VAN_BAN.find((v) => boDau(v.soHieu) === n);
};

/** Mở rộng truy vấn: bỏ dấu + bung viết tắt. */
export function moRongTruyVan(q: string): string[] {
  const raw = q.trim();
  const terms = new Set<string>();
  if (raw) terms.add(boDau(raw));
  for (const w of raw.split(/\s+/)) {
    const key = w.toLowerCase();
    const full = VIET_TAT[key] ?? VIET_TAT[boDau(key)];
    if (full) terms.add(boDau(full));
  }
  return [...terms];
}

export function goiYDongNghia(q: string): string[] {
  const n = boDau(q);
  for (const [k, v] of Object.entries(DONG_NGHIA)) {
    if (n.includes(k)) return v;
  }
  return [];
}

/** Chuỗi trích dẫn tiếng Việt: đơn vị nhỏ nhất trước. */
export function chuoiTrichDan(vb: VanBan, dieu: Dieu, khoan?: Khoan, diem?: Diem): string {
  const parts: string[] = [];
  if (diem) parts.push(`Điểm ${diem.ky}`);
  if (khoan) parts.push(`${diem ? "khoản" : "Khoản"} ${khoan.so}`);
  parts.push(`${parts.length ? "Điều" : "Điều"} ${dieu.so}`);
  return `${parts.join(" ")} ${vb.tenNgan}`;
}

export type KetQua = {
  vb: VanBan;
  dieu: Dieu;
  khoan: Khoan;
  diaChi: string; // "Khoản 1 Điều 25"
  trichDan: string;
  diem?: Diem;
  score: number;
};

export type BoLoc = {
  loai: string[];
  coQuan: string[];
  linhVuc: string[];
  tinhTrang: string[];
  namTu: number;
  namDen: number;
};

export function timKiem(query: string, loc: BoLoc): KetQua[] {
  const terms = moRongTruyVan(query).filter(Boolean);
  const out: KetQua[] = [];

  for (const vb of VAN_BAN) {
    const nam = Number(vb.ngayBanHanh.slice(-4));
    if (loc.loai.length && !loc.loai.includes(vb.loai)) continue;
    if (loc.coQuan.length && !loc.coQuan.includes(vb.coQuan)) continue;
    if (loc.linhVuc.length && !loc.linhVuc.includes(vb.linhVuc)) continue;
    if (loc.tinhTrang.length && !loc.tinhTrang.includes(vb.tinhTrang)) continue;
    if (nam < loc.namTu || nam > loc.namDen) continue;

    const meta = boDau(`${vb.soHieu} ${vb.ten} ${vb.tenNgan} ${vb.linhVuc} ${vb.coQuan}`);

    for (const ch of vb.chuong) {
      for (const dieu of ch.dieu) {
        for (const khoan of dieu.khoan) {
          const hayKhoan = boDau(`${dieu.tieuDe} ${khoan.text}`);
          const diemHit = khoan.diem?.find((d) => terms.some((t) => boDau(d.text).includes(t)));
          let score = 0;
          if (!terms.length) score = 1;
          for (const t of terms) {
            if (hayKhoan.includes(t)) score += 4;
            if (boDau(dieu.tieuDe).includes(t)) score += 3;
            if (meta.includes(t)) score += 2;
            if (diemHit) score += 3;
          }
          if (!score) continue;
          out.push({
            vb,
            dieu,
            khoan,
            ...(diemHit ? { diem: diemHit } : {}),
            diaChi: `Khoản ${khoan.so} Điều ${dieu.so}`,
            trichDan: chuoiTrichDan(vb, dieu, khoan, diemHit),
            score,
          });
        }
      }
    }
  }
  return out.sort((a, b) => b.score - a.score);
}

export const vanBanTheoSoHieu = (soHieu: string): VanBan | undefined => {
  const n = boDau(decodeURIComponent(soHieu));
  return VAN_BAN.find((v) => boDau(v.soHieu) === n);
};

export const idDieu = (so: number) => `dieu-${so}`;
export const idKhoan = (dieuSo: number, khoanSo: number) => `dieu-${dieuSo}-khoan-${khoanSo}`;
