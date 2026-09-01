// Định nghĩa 25 mẫu văn bản: nhóm, ký hiệu, số trường, căn cứ pháp lý.
// Đây là CẤU HÌNH SẢN PHẨM, không phải dữ liệu pháp luật minh hoạ — nên nó ở
// lại sau khi kho văn bản giả bị xoá.
//
// Cảnh báo còn mở: backend hiện chỉ có checklist cho 'hdld'; noi_quy và
// quyet_dinh_ky_luat trả 501; 22 mẫu còn lại chưa có kiểu backend nào. Danh
// mục này vì thế đang hứa nhiều hơn hệ thống làm được — việc của pha nối FE.

export type NhomMau = "lao-dong" | "thuong-mai" | "noi-bo" | "to-tung";

export type MauVanBan = {
  id: string;
  ten: string;
  moTa: string;
  soTruong: number;
  nhom: NhomMau;
  kyHieu: string; // Số: .../HĐDV
  canCu: { soHieu: string; ten: string }[];
};

export const NHOM: { id: NhomMau; ten: string }[] = [
  { id: "lao-dong", ten: "Hợp đồng lao động & nhân sự" },
  { id: "thuong-mai", ten: "Hợp đồng thương mại & dân sự" },
  { id: "noi-bo", ten: "Văn bản nội bộ doanh nghiệp" },
  { id: "to-tung", ten: "Văn bản tố tụng & hành chính" },
];

const BLLD = { soHieu: "45/2019/QH14", ten: "Bộ luật Lao động 2019" };
const BLDS = { soHieu: "91/2015/QH13", ten: "Bộ luật Dân sự 2015" };
const LTM = { soHieu: "36/2005/QH11", ten: "Luật Thương mại 2005" };
const LDN = { soHieu: "59/2020/QH14", ten: "Luật Doanh nghiệp 2020" };

export const MAU: MauVanBan[] = [
  // Lao động & nhân sự
  {
    id: "hop-dong-lao-dong-xac-dinh-thoi-han",
    ten: "Hợp đồng lao động xác định thời hạn",
    moTa: "Thuê lao động trong thời hạn từ 12 đến 36 tháng.",
    soTruong: 9,
    nhom: "lao-dong",
    kyHieu: "HĐLĐ",
    canCu: [BLLD, BLDS],
  },
  {
    id: "hop-dong-lao-dong-khong-xac-dinh-thoi-han",
    ten: "Hợp đồng lao động không xác định thời hạn",
    moTa: "Không ấn định thời hạn, thời điểm chấm dứt hiệu lực.",
    soTruong: 9,
    nhom: "lao-dong",
    kyHieu: "HĐLĐ",
    canCu: [BLLD],
  },
  {
    id: "hop-dong-thu-viec",
    ten: "Hợp đồng thử việc",
    moTa: "Thoả thuận thử việc riêng, có kiểm tra giới hạn thời gian.",
    soTruong: 8,
    nhom: "lao-dong",
    kyHieu: "HĐTV",
    canCu: [BLLD],
  },
  {
    id: "quyet-dinh-bo-nhiem",
    ten: "Quyết định bổ nhiệm",
    moTa: "Bổ nhiệm chức danh quản lý trong doanh nghiệp.",
    soTruong: 7,
    nhom: "lao-dong",
    kyHieu: "QĐ",
    canCu: [LDN, BLLD],
  },
  {
    id: "quyet-dinh-cham-dut-hop-dong-lao-dong",
    ten: "Quyết định chấm dứt hợp đồng lao động",
    moTa: "Chấm dứt quan hệ lao động, nêu căn cứ và thời điểm.",
    soTruong: 8,
    nhom: "lao-dong",
    kyHieu: "QĐ",
    canCu: [BLLD],
  },
  {
    id: "noi-quy-lao-dong",
    ten: "Nội quy lao động",
    moTa: "Quy định thời giờ làm việc, kỷ luật, an toàn lao động.",
    soTruong: 10,
    nhom: "lao-dong",
    kyHieu: "NQLĐ",
    canCu: [BLLD],
  },
  {
    id: "thoa-thuan-bao-mat-nda",
    ten: "Thỏa thuận bảo mật thông tin (NDA)",
    moTa: "Bảo vệ thông tin kinh doanh, dữ liệu và bí mật công nghệ.",
    soTruong: 8,
    nhom: "lao-dong",
    kyHieu: "NDA",
    // 13/2023/NĐ-CP đã hết hiệu lực toàn bộ từ 01/01/2026 và đã bị gỡ khỏi đây.
    // Chưa thay bằng văn bản kế nhiệm: KLAW chưa có thẩm quyền trong kho để
    // khẳng định văn bản nào đang điều chỉnh bảo vệ dữ liệu cá nhân.
    canCu: [BLDS],
  },

  // Thương mại & dân sự
  {
    id: "hop-dong-mua-ban-hang-hoa",
    ten: "Hợp đồng mua bán hàng hóa",
    moTa: "Mua bán hàng hóa giữa thương nhân, có giao nhận và bảo hành.",
    soTruong: 11,
    nhom: "thuong-mai",
    kyHieu: "HĐMB",
    canCu: [LTM, BLDS],
  },
  {
    id: "hop-dong-dich-vu",
    ten: "Hợp đồng dịch vụ",
    moTa: "Cung ứng dịch vụ theo phạm vi công việc và tiến độ thanh toán.",
    soTruong: 10,
    nhom: "thuong-mai",
    kyHieu: "HĐDV",
    canCu: [LTM, BLDS],
  },
  {
    id: "hop-dong-nguyen-tac",
    ten: "Hợp đồng nguyên tắc",
    moTa: "Khung hợp tác dài hạn, chi tiết theo từng đơn hàng.",
    soTruong: 8,
    nhom: "thuong-mai",
    kyHieu: "HĐNT",
    canCu: [LTM],
  },
  {
    id: "hop-dong-gia-cong",
    ten: "Hợp đồng gia công",
    moTa: "Gia công sản phẩm theo yêu cầu, định mức nguyên vật liệu.",
    soTruong: 10,
    nhom: "thuong-mai",
    kyHieu: "HĐGC",
    canCu: [LTM],
  },
  {
    id: "hop-dong-thue-nha-mat-bang",
    ten: "Hợp đồng thuê nhà, mặt bằng",
    moTa: "Thuê nhà ở hoặc mặt bằng kinh doanh, có đặt cọc.",
    soTruong: 10,
    nhom: "thuong-mai",
    kyHieu: "HĐTN",
    canCu: [BLDS],
  },
  {
    id: "hop-dong-vay-tai-san",
    ten: "Hợp đồng vay tài sản",
    moTa: "Vay tiền hoặc tài sản, lãi suất theo giới hạn luật định.",
    soTruong: 9,
    nhom: "thuong-mai",
    kyHieu: "HĐV",
    canCu: [BLDS],
  },
  {
    id: "hop-dong-hop-tac-kinh-doanh",
    ten: "Hợp đồng hợp tác kinh doanh",
    moTa: "Hợp tác góp vốn, phân chia lợi nhuận không thành lập pháp nhân.",
    soTruong: 11,
    nhom: "thuong-mai",
    kyHieu: "HĐHTKD",
    canCu: [BLDS, LDN],
  },
  {
    id: "hop-dong-chuyen-nhuong-quyen-so-huu",
    ten: "Hợp đồng chuyển nhượng quyền sở hữu",
    moTa: "Chuyển nhượng quyền sở hữu tài sản, quyền tài sản.",
    soTruong: 10,
    nhom: "thuong-mai",
    kyHieu: "HĐCN",
    canCu: [BLDS],
  },

  // Nội bộ
  {
    id: "quyet-dinh-hoi-dong-quan-tri",
    ten: "Quyết định của Hội đồng quản trị",
    moTa: "Nghị quyết, quyết định thuộc thẩm quyền Hội đồng quản trị.",
    soTruong: 7,
    nhom: "noi-bo",
    kyHieu: "QĐ-HĐQT",
    canCu: [LDN],
  },
  {
    id: "bien-ban-hop",
    ten: "Biên bản họp",
    moTa: "Ghi nhận diễn biến, ý kiến và kết quả biểu quyết.",
    soTruong: 8,
    nhom: "noi-bo",
    kyHieu: "BB",
    canCu: [LDN],
  },
  {
    id: "cong-van",
    ten: "Công văn",
    moTa: "Trao đổi, đề nghị, trả lời giữa các tổ chức.",
    soTruong: 7,
    nhom: "noi-bo",
    kyHieu: "CV",
    canCu: [LDN],
  },
  {
    id: "giay-uy-quyen",
    ten: "Giấy ủy quyền",
    moTa: "Ủy quyền thực hiện công việc, phạm vi và thời hạn rõ ràng.",
    soTruong: 8,
    nhom: "noi-bo",
    kyHieu: "GUQ",
    canCu: [BLDS],
  },
  {
    id: "quy-che-noi-bo",
    ten: "Quy chế nội bộ",
    moTa: "Quy chế quản trị, chi tiêu, phân cấp thẩm quyền.",
    soTruong: 9,
    nhom: "noi-bo",
    kyHieu: "QC",
    canCu: [LDN],
  },

  // Tố tụng & hành chính
  {
    id: "don-khoi-kien",
    ten: "Đơn khởi kiện",
    moTa: "Khởi kiện vụ án dân sự, kinh doanh thương mại, lao động.",
    soTruong: 10,
    nhom: "to-tung",
    kyHieu: "ĐKK",
    canCu: [BLDS],
  },
  {
    id: "don-de-nghi",
    ten: "Đơn đề nghị",
    moTa: "Đề nghị cơ quan, tổ chức giải quyết một yêu cầu.",
    soTruong: 7,
    nhom: "to-tung",
    kyHieu: "ĐĐN",
    canCu: [BLDS],
  },
  {
    id: "don-khieu-nai",
    ten: "Đơn khiếu nại",
    moTa: "Khiếu nại quyết định, hành vi trái pháp luật.",
    soTruong: 8,
    nhom: "to-tung",
    kyHieu: "ĐKN",
    canCu: [BLDS],
  },
  {
    id: "ban-tu-khai",
    ten: "Bản tự khai",
    moTa: "Trình bày nội dung sự việc theo yêu cầu của toà án.",
    soTruong: 7,
    nhom: "to-tung",
    kyHieu: "BTK",
    canCu: [BLDS],
  },
  {
    id: "van-ban-giai-trinh",
    ten: "Văn bản giải trình",
    moTa: "Giải trình với cơ quan quản lý về nội dung bị yêu cầu.",
    soTruong: 8,
    nhom: "to-tung",
    kyHieu: "GT",
    canCu: [LDN],
  },
];

export const mauTheoId = (id: string) => MAU.find((m) => m.id === id);

export const laHopDongLaoDong = (m: MauVanBan) => m.nhom === "lao-dong";
export const laHopDongThuongMai = (m: MauVanBan) => m.nhom === "thuong-mai";
export const laThuViec = (m: MauVanBan) => m.id === "hop-dong-thu-viec";

/**
 * Mẫu nào soát được với KLAW, và mẫu nào KHÔNG.
 *
 * Backend nhận đúng ba `loai_van_ban` (`hdld`, `noi_quy`, `quyet_dinh_ky_luat`)
 * và hiện chỉ `hdld` có checklist + rules thật (`_LOAI_CO_CHECKLIST = {"hdld"}`);
 * hai loại kia trả **501**. Danh mục 25 mẫu ở trên là cấu hình sản phẩm, không
 * phải lời hứa về năng lực soát — nên bản đồ này nói ra chính xác chỗ hai thứ
 * đó lệch nhau, thay vì để màn soạn thảo mời người dùng bấm một nút chỉ ra lỗi.
 *
 * KHÔNG ánh xạ `quyet-dinh-cham-dut-hop-dong-lao-dong` sang
 * `quyet_dinh_ky_luat`: chấm dứt hợp đồng và xử lý kỷ luật là hai chế định khác
 * nhau của Bộ luật Lao động, và soát một quyết định chấm dứt bằng checklist kỷ
 * luật sẽ sinh ra phát hiện sai — tệ hơn hẳn không soát.
 */
export const LOAI_BACKEND: Record<string, LoaiVanBanBackend> = {
  "hop-dong-lao-dong-xac-dinh-thoi-han": "hdld",
  "hop-dong-lao-dong-khong-xac-dinh-thoi-han": "hdld",
  "hop-dong-thu-viec": "hdld",
  "noi-quy-lao-dong": "noi_quy",
};

export type LoaiVanBanBackend = "hdld" | "noi_quy" | "quyet_dinh_ky_luat";

/** `undefined` = KLAW chưa có kiểu nào cho mẫu này, nên chưa soát được. */
export const loaiBackendCua = (id: string): LoaiVanBanBackend | undefined => LOAI_BACKEND[id];
