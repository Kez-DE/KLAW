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
 * Bản đồ này chỉ chứa mẫu máy chủ THẬT SỰ soát được, và đó là một ràng buộc
 * hẹp hơn "máy chủ nhận `loai_van_ban` này".
 *
 * `POST /soat` khai ba giá trị (`hdld`, `noi_quy`, `quyet_dinh_ky_luat`) nhưng
 * chỉ `hdld` có checklist; ĐO TRÊN MÁY CHỦ ĐANG CHẠY hôm nay, `noi_quy` trả
 * **501** kèm câu `chưa có checklist/rules riêng (hiện chỉ hỗ trợ: ['hdld'])`,
 * và `GET /mau/noi_quy` trả `facts: []`. `noi-quy-lao-dong` từng bị gỡ khỏi bản
 * đồ này vì lý do đó — nó đeo nhãn "Soát được với KLAW" trong danh mục, một lời
 * hứa mà người dùng chỉ phát hiện là sai SAU khi soạn xong cả bản thảo rồi bấm
 * nút.
 *
 * 2026-09-01: nó có checklist thật (BLLĐ Đ118.2 a–i) nên đã quay lại, cùng 12
 * mẫu khác. **17/25 mẫu nối được backend: 16 soát NỘI DUNG, 1 (`cong-van`) chỉ
 * soát THỂ THỨC.** Danh mục đếm cả hai con số từ chính bản đồ này nên chúng
 * không thể trôi khỏi sự thật — con số viết tay trong chú thích thì có, và đã
 * trôi đúng một lần: dòng này từng ghi 16 khi bản đồ đã có 17.
 *
 * KHÔNG ánh xạ `quyet-dinh-cham-dut-hop-dong-lao-dong` sang
 * `quyet_dinh_ky_luat`: chấm dứt hợp đồng và xử lý kỷ luật là hai chế định khác
 * nhau của Bộ luật Lao động, và soát một quyết định chấm dứt bằng checklist kỷ
 * luật sẽ sinh ra phát hiện sai — tệ hơn hẳn không soát.
 */
export const LOAI_BACKEND: Record<string, LoaiVanBanBackend> = {
  "hop-dong-lao-dong-xac-dinh-thoi-han": "hdld",
  "hop-dong-lao-dong-khong-xac-dinh-thoi-han": "hdld",
  // `hop_dong_thu_viec` chứ KHÔNG còn `hdld`: thử việc nay có checklist riêng
  // trên BLLĐ Đ24.2 (4 nội dung bắt buộc), khác hẳn Đ21.1 (10 nội dung của
  // HĐLĐ). Soát bản thử việc bằng checklist HĐLĐ báo thiếu sáu mục luật không
  // đòi.
  "hop-dong-thu-viec": "hop_dong_thu_viec",
  "quyet-dinh-cham-dut-hop-dong-lao-dong": "quyet_dinh_cham_dut_hdld",
  "noi-quy-lao-dong": "noi_quy",
  "thoa-thuan-bao-mat-nda": "thoa_thuan_bao_mat",
  "hop-dong-mua-ban-hang-hoa": "hop_dong_mua_ban",
  "hop-dong-dich-vu": "hop_dong_dich_vu",
  "hop-dong-nguyen-tac": "hop_dong_nguyen_tac",
  "hop-dong-gia-cong": "hop_dong_gia_cong",
  // Giới hạn phạm vi: checklist này dựng trên BLDS Đ472–482 (thuê TÀI SẢN).
  // Đúng cho mặt bằng; KHÔNG tự nhận đủ cho thuê NHÀ Ở, vì Luật Nhà ở không
  // có trong kho nên phần riêng của nhà ở không soát được.
  "hop-dong-thue-nha-mat-bang": "hop_dong_thue_tai_san",
  "hop-dong-vay-tai-san": "hop_dong_vay",
  "hop-dong-hop-tac-kinh-doanh": "hop_dong_hop_tac",
  "bien-ban-hop": "bien_ban_hop_hdqt",
  "don-khoi-kien": "don_khoi_kien",
  "don-de-nghi": "don_yeu_cau",
  // CHỈ SOÁT THỂ THỨC — xem `CHI_SOAT_HINH_THUC` ngay dưới.
  "cong-van": "cong_van",
};

/**
 * Mẫu mà KLAW chỉ soát được THỂ THỨC, không soát nội dung.
 *
 * NĐ 30/2020 Đ8.2 cho cả 29 loại văn bản hành chính CHUNG một danh mục 9 thành
 * phần (quốc hiệu, số hiệu, nơi nhận, chữ ký…), và không quy định nội dung
 * nghiệp vụ của loại nào. Với công văn thì đó KHÔNG phải thiếu sót: luật không
 * đặt nội dung bắt buộc nào cho công văn — thân văn bản là văn xuôi tự do —
 * nên "đủ 9 thành phần" đúng là toàn bộ những gì luật đòi.
 *
 * Nhưng nhãn phải nói ra. Thẻ này nằm cạnh những mẫu soát nội dung thật (nội
 * quy lao động, quyết định kỷ luật), nên một nhãn "Soát được với KLAW" giống
 * hệt sẽ khiến người dùng tưởng KLAW đọc được nội dung công văn của họ. Nó
 * không đọc.
 *
 * Một giới hạn nữa, không hiện trên thẻ vì thuộc về ai phải tuân: NĐ 30/2020
 * Đ2.1 chỉ áp cho cơ quan, tổ chức nhà nước và doanh nghiệp nhà nước. Với
 * doanh nghiệp tư nhân đây là chuẩn mực tham khảo, không phải nghĩa vụ.
 */
export const CHI_SOAT_HINH_THUC: ReadonlySet<string> = new Set(["cong-van"]);

/**
 * Ba mẫu CỐ Ý không ánh xạ dù backend có kiểu trông na ná — cùng lý lẽ đã dùng
 * cho cặp chấm-dứt/kỷ-luật ở trên: soát bằng checklist của một chế định khác
 * sinh ra phát hiện SAI, tệ hơn hẳn không soát.
 *
 * `giay-uy-quyen` ↛ `hop_dong_uy_quyen` — giấy uỷ quyền là hành vi MỘT BÊN;
 *   hợp đồng uỷ quyền là thoả thuận HAI BÊN (BLDS Đ562). Checklist hợp đồng
 *   đòi chữ ký bên nhận uỷ quyền, mà giấy uỷ quyền không có bên đó.
 * `quyet-dinh-hoi-dong-quan-tri` ↛ `bien_ban_hop_hdqt` — nghị quyết và biên
 *   bản họp là hai văn bản khác nhau; LDN Đ158 quy định nội dung BIÊN BẢN.
 * `hop-dong-chuyen-nhuong-quyen-so-huu` — không phải loại hợp đồng có tên
 *   trong luật, trùng mua bán tài sản (BLDS Đ430).
 *
 * Còn lại chưa có backend vì kho thiếu văn bản nguồn: `cong-van` (NĐ 30/2020
 * văn thư), `don-khieu-nai` (Luật Khiếu nại 02/2011), `quy-che-noi-bo`,
 * `ban-tu-khai`, `van-ban-giai-trinh`, `quyet-dinh-bo-nhiem`.
 */
export type LoaiVanBanBackend =
  | "hdld"
  | "noi_quy"
  | "quyet_dinh_ky_luat"
  | "hop_dong_thu_viec"
  | "quyet_dinh_cham_dut_hdld"
  | "thoa_thuan_bao_mat"
  | "hop_dong_mua_ban"
  | "hop_dong_dich_vu"
  | "hop_dong_nguyen_tac"
  | "hop_dong_gia_cong"
  | "hop_dong_thue_tai_san"
  | "hop_dong_vay"
  | "hop_dong_hop_tac"
  | "hop_dong_uy_quyen"
  | "bien_ban_hop_hdqt"
  | "don_khoi_kien"
  | "don_yeu_cau"
  | "cong_van";

/** `undefined` = KLAW chưa có kiểu nào cho mẫu này, nên chưa soát được. */
export const loaiBackendCua = (id: string): LoaiVanBanBackend | undefined => LOAI_BACKEND[id];
