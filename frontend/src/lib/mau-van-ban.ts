import type { PhamViSoat } from "./khung-van-ban";

// Định nghĩa 28 mẫu văn bản: nhóm, ký hiệu, số trường, căn cứ pháp lý.
// Đây là CẤU HÌNH SẢN PHẨM, không phải dữ liệu pháp luật minh hoạ — nên nó ở
// lại sau khi kho văn bản giả bị xoá.
//
// 2026-09-03: **28/28 mẫu nối được backend**, khớp đúng 28 loại `/soan-thao`
// nhận — thêm `don_xin_nghi_viec` (đơn xin nghỉ việc, phía người lao động),
// đối trọng của `quyet_dinh_cham_dut_hdld` (phía người sử dụng lao động) vốn
// đã có sẵn. Danh mục không còn hứa nhiều hơn hệ thống làm được, và cũng
// không còn giấu mẫu nào: `quy_che_dan_chu` và `hop_dong_uy_quyen` từng dựng
// được, soát được, mà không có thẻ nào bấm tới.

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
const ND145 = {
  soHieu: "145/2020/NĐ-CP",
  ten: "Nghị định 145/2020/NĐ-CP hướng dẫn Bộ luật Lao động",
};

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
    // Đối trọng phía NGƯỜI LAO ĐỘNG của mẫu ngay trên (phía người sử dụng lao
    // động): cùng chương BLLĐ, hai bộ điều kiện khác nhau (BLLĐ Đ35 thay vì
    // Đ34/Đ36), nên KHÔNG dùng chung `LOAI_BACKEND` bên dưới.
    id: "don-xin-nghi-viec",
    ten: "Đơn xin nghỉ việc",
    moTa: "Người lao động đơn phương chấm dứt hợp đồng lao động, nêu thời hạn báo trước.",
    soTruong: 9,
    nhom: "lao-dong",
    kyHieu: "ĐXNV",
    canCu: [BLLD],
  },
  {
    // Mặt thứ ba của chấm dứt HĐLĐ: NLĐ đơn phương (Đ35, đơn xin nghỉ việc),
    // NSDLĐ đơn phương (Đ34/Đ36, quyết định chấm dứt) — và đây là HAI BÊN cùng
    // thoả thuận (Đ34.3). Backend `thoa_thuan_cham_dut_hdld`, checklist riêng.
    id: "thoa-thuan-cham-dut-hop-dong-lao-dong",
    ten: "Thoả thuận chấm dứt hợp đồng lao động",
    moTa: "Hai bên cùng thoả thuận chấm dứt hợp đồng lao động: thời điểm, các khoản thanh toán, giấy tờ.",
    soTruong: 7,
    nhom: "lao-dong",
    kyHieu: "TTCD",
    canCu: [BLLD],
  },
  {
    // KHÔNG phải `quy-che-noi-bo`. Quy chế nội bộ (nghĩa chung, soát THỂ THỨC
    // theo NĐ 30/2020) và quy chế dân chủ ở cơ sở là HAI văn bản khác nhau:
    // cái sau có nội dung bắt buộc riêng trong NĐ 145/2020 Đ37.2 điểm a–g và
    // soát được NỘI DUNG. Trỏ chung một kiểu backend là soát cái này bằng
    // checklist của cái kia.
    id: "quy-che-dan-chu-co-so",
    ten: "Quy chế dân chủ ở cơ sở tại nơi làm việc",
    moTa: "Nội dung đối thoại, công khai và tham gia ý kiến tại nơi làm việc.",
    soTruong: 10,
    nhom: "lao-dong",
    kyHieu: "QCDC",
    canCu: [ND145, BLLD],
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
    ten: "Thoả thuận bảo vệ bí mật kinh doanh (NDA)",
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
    // KHÔNG gộp với `giay-uy-quyen`. Giấy uỷ quyền là hành vi MỘT BÊN; hợp đồng
    // uỷ quyền là thoả thuận HAI BÊN (BLDS Đ562) — chính vì thế backend trả
    // `la_hop_dong=false` cho cái trước và `true` cho cái sau, nên chỉ cái sau
    // mới dựng khối các bên và bảng ký hai cột.
    id: "hop-dong-uy-quyen",
    ten: "Hợp đồng ủy quyền",
    moTa: "Thoả thuận hai bên về việc thực hiện công việc nhân danh bên uỷ quyền.",
    soTruong: 8,
    nhom: "thuong-mai",
    kyHieu: "HĐUQ",
    canCu: [BLDS],
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
    ten: "Hợp đồng thuê tài sản (nhà, mặt bằng)",
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
    ten: "Hợp đồng mua bán tài sản",
    moTa: "Chuyển nhượng quyền sở hữu tài sản, quyền tài sản.",
    soTruong: 10,
    nhom: "thuong-mai",
    kyHieu: "HĐCN",
    canCu: [BLDS],
  },

  // Nội bộ
  {
    id: "quyet-dinh-hoi-dong-quan-tri",
    ten: "Nghị quyết của Hội đồng quản trị",
    moTa: "Nghị quyết, quyết định thuộc thẩm quyền Hội đồng quản trị.",
    soTruong: 7,
    nhom: "noi-bo",
    kyHieu: "QĐ-HĐQT",
    canCu: [LDN],
  },
  {
    id: "bien-ban-hop",
    ten: "Biên bản họp Hội đồng quản trị",
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
    ten: "Đơn yêu cầu giải quyết việc dân sự",
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
 * Mẫu nào soát được với KLAW, soát được ĐẾN ĐÂU, và mẫu nào chưa nối.
 *
 * Bản đồ này chỉ chứa mẫu máy chủ THẬT SỰ soát được, và đó là một ràng buộc
 * hẹp hơn "máy chủ nhận `loai_van_ban` này".
 *
 * 2026-09-03: **28/28 mẫu đã nối backend** — 24 soát NỘI DUNG, 3 chỉ soát THỂ
 * THỨC, 1 (`quyet_dinh_bo_nhiem`) soát thể thức KÈM một quy tắc nhiệm kỳ. Danh
 * mục đếm cả ba con số từ chính bản đồ này nên chúng không thể trôi khỏi sự
 * thật — con số viết tay trong chú thích thì có, và đã trôi đúng một lần: dòng
 * này từng ghi 16 khi bản đồ đã có 17.
 *
 * `phamVi` là BẮT BUỘC trên mỗi dòng, và đó là chủ ý. Trước đây nó nằm trong
 * một `Set` riêng (`CHI_SOAT_HINH_THUC`) đặt cách bản đồ này gần trăm dòng, tức
 * là thêm một mẫu mà quên cập nhật `Set` thì mẫu mới lặng lẽ đeo nhãn "Soát
 * được với KLAW" — một lời hứa sai, không có gì đỏ lên. Nay bỏ sót `phamVi` là
 * một lỗi biên dịch. `npm run kiem-khung` đối chiếu tiếp từng dòng với cờ
 * `chi_soat_the_thuc` / `pham_vi_soat` mà máy chủ tính ra, nên bản đồ không
 * lệch được khỏi checklist mà không ai biết.
 *
 * KHÔNG ánh xạ `quyet-dinh-cham-dut-hop-dong-lao-dong` sang
 * `quyet_dinh_ky_luat`: chấm dứt hợp đồng và xử lý kỷ luật là hai chế định khác
 * nhau của Bộ luật Lao động, và soát một quyết định chấm dứt bằng checklist kỷ
 * luật sẽ sinh ra phát hiện sai — tệ hơn hẳn không soát.
 */
export type NoiBackend = { loai: LoaiVanBanBackend; phamVi: PhamViSoat };

export const LOAI_BACKEND: Record<string, NoiBackend> = {
  "hop-dong-lao-dong-xac-dinh-thoi-han": { loai: "hdld", phamVi: "noi_dung" },
  "hop-dong-lao-dong-khong-xac-dinh-thoi-han": { loai: "hdld", phamVi: "noi_dung" },
  // `hop_dong_thu_viec` chứ KHÔNG còn `hdld`: thử việc nay có checklist riêng
  // trên BLLĐ Đ24.2 (4 nội dung bắt buộc), khác hẳn Đ21.1 (10 nội dung của
  // HĐLĐ). Soát bản thử việc bằng checklist HĐLĐ báo thiếu sáu mục luật không
  // đòi.
  "hop-dong-thu-viec": { loai: "hop_dong_thu_viec", phamVi: "noi_dung" },
  "quyet-dinh-cham-dut-hop-dong-lao-dong": {
    loai: "quyet_dinh_cham_dut_hdld",
    phamVi: "noi_dung",
  },
  "noi-quy-lao-dong": { loai: "noi_quy", phamVi: "noi_dung" },
  "thoa-thuan-bao-mat-nda": { loai: "thoa_thuan_bao_mat", phamVi: "noi_dung" },
  "hop-dong-mua-ban-hang-hoa": { loai: "hop_dong_mua_ban", phamVi: "noi_dung" },
  "hop-dong-dich-vu": { loai: "hop_dong_dich_vu", phamVi: "noi_dung" },
  "hop-dong-nguyen-tac": { loai: "hop_dong_nguyen_tac", phamVi: "noi_dung" },
  "hop-dong-gia-cong": { loai: "hop_dong_gia_cong", phamVi: "noi_dung" },
  // Giới hạn phạm vi: checklist này dựng trên BLDS Đ472–482 (thuê TÀI SẢN).
  // Đúng cho mặt bằng; KHÔNG tự nhận đủ cho thuê NHÀ Ở, vì Luật Nhà ở không
  // có trong kho nên phần riêng của nhà ở không soát được.
  "hop-dong-thue-nha-mat-bang": { loai: "hop_dong_thue_tai_san", phamVi: "noi_dung" },
  "hop-dong-vay-tai-san": { loai: "hop_dong_vay", phamVi: "noi_dung" },
  "hop-dong-hop-tac-kinh-doanh": { loai: "hop_dong_hop_tac", phamVi: "noi_dung" },
  "bien-ban-hop": { loai: "bien_ban_hop_hdqt", phamVi: "noi_dung" },
  "don-khoi-kien": { loai: "don_khoi_kien", phamVi: "noi_dung" },
  "don-de-nghi": { loai: "don_yeu_cau", phamVi: "noi_dung" },
  "cong-van": { loai: "cong_van", phamVi: "the_thuc" },

  // Tám mẫu nối thêm 2026-09-02, đưa danh mục lên 25/25.
  //
  // `hop-dong-chuyen-nhuong-quyen-so-huu` → `hop_dong_mua_ban_tai_san`: chuyển
  // nhượng quyền sở hữu không phải một loại hợp đồng có tên riêng trong luật,
  // nó CHÍNH LÀ mua bán tài sản (BLDS Đ430), nên checklist Đ431–450 áp đúng.
  "hop-dong-chuyen-nhuong-quyen-so-huu": {
    loai: "hop_dong_mua_ban_tai_san",
    phamVi: "noi_dung",
  },
  // `giay_uy_quyen` nay là checklist RIÊNG dựng trên BLDS Đ138 (đại diện theo
  // uỷ quyền), không phải `hop_dong_uy_quyen` (Đ562, thoả thuận HAI BÊN). Đây
  // đúng là lý do trước kia mẫu này cố ý bị bỏ trống.
  "giay-uy-quyen": { loai: "giay_uy_quyen", phamVi: "noi_dung" },
  // Tương tự: `quyet_dinh_hdqt` là checklist của NGHỊ QUYẾT, tách khỏi
  // `bien_ban_hop_hdqt` (LDN Đ158 quy định nội dung BIÊN BẢN).
  "quyet-dinh-hoi-dong-quan-tri": { loai: "quyet_dinh_hdqt", phamVi: "the_thuc" },
  "don-khieu-nai": { loai: "don_khieu_nai", phamVi: "noi_dung" },
  // Ca LAI, và bản đồ phải nói ra: máy chủ trả `pham_vi_soat: "the_thuc"` nhưng
  // `chi_soat_the_thuc: false`, vì ngoài 9 thành phần thể thức nó còn một quy
  // tắc nhiệm kỳ thật (LDN Đ162.2, trần 05 năm) chạy trên hai fact
  // `co_tran_nhiem_ky_05_nam` và `nhiem_ky_thang`.
  "quyet-dinh-bo-nhiem": { loai: "quyet_dinh_bo_nhiem", phamVi: "the_thuc_kem_rule" },
  "quy-che-noi-bo": { loai: "quy_che_noi_bo", phamVi: "the_thuc" },
  "ban-tu-khai": { loai: "ban_tu_khai", phamVi: "noi_dung" },
  "van-ban-giai-trinh": { loai: "van_ban_giai_trinh", phamVi: "noi_dung" },

  // Hai mẫu nối 2026-09-02, đưa danh mục lên 27/27 — khớp đúng 27 loại
  // `/soan-thao` nhận. Trước đó cả hai dựng được, soát được, mà không có thẻ
  // nào bấm tới.
  //
  // `quy_che_dan_chu` soát NỘI DUNG (NĐ 145/2020 Đ37.2 a–g, cộng Đ43.2, Đ44.2,
  // Đ47.3), KHÔNG phải thể thức — và nó có một rule thật
  // (`so_dai_dien_doi_thoai_nsdld_toi_thieu`, sàn 03 người theo Đ38.1).
  "quy-che-dan-chu-co-so": { loai: "quy_che_dan_chu", phamVi: "noi_dung" },
  "hop-dong-uy-quyen": { loai: "hop_dong_uy_quyen", phamVi: "noi_dung" },

  // Một mẫu nối 2026-09-03, đưa danh mục lên 28/28 — khớp đúng 28 loại
  // `/soan-thao` nhận. Backend đã nhận `don_xin_nghi_viec` từ trước (checklist
  // + `LoaiVanBan`); giao diện thiếu thẻ này nên route 404.
  //
  // Soát NỘI DUNG (BLLĐ Đ35.1 — bốn mục bắt buộc bất kể trường hợp; Đ35.2 —
  // nhóm nghỉ-ngay không bắt buộc, không được báo thiếu). KHÔNG dùng chung
  // `quyet_dinh_cham_dut_hdld` (mẫu trên): đó là quyết định của NGƯỜI SỬ DỤNG
  // LAO ĐỘNG (Đ34/Đ36/Đ45/Đ46/Đ48), còn đây là đơn của NGƯỜI LAO ĐỘNG (Đ35) —
  // hai bộ điều kiện khác nhau của cùng một chương.
  "don-xin-nghi-viec": { loai: "don_xin_nghi_viec", phamVi: "noi_dung" },
  "thoa-thuan-cham-dut-hop-dong-lao-dong": { loai: "thoa_thuan_cham_dut_hdld", phamVi: "noi_dung" },
};

/**
 * Ba mẫu chỉ soát THỂ THỨC, và nhãn phải nói ra điều đó.
 *
 * NĐ 30/2020 Đ8.2 cho cả 29 loại văn bản hành chính CHUNG một danh mục 9 thành
 * phần (quốc hiệu, số hiệu, nơi nhận, chữ ký…), và không quy định nội dung
 * nghiệp vụ của loại nào. Với công văn thì đó KHÔNG phải thiếu sót: luật không
 * đặt nội dung bắt buộc nào cho công văn — thân văn bản là văn xuôi tự do —
 * nên "đủ 9 thành phần" đúng là toàn bộ những gì luật đòi.
 *
 * Nhưng ba thẻ này nằm cạnh những mẫu soát nội dung thật (nội quy lao động,
 * quyết định kỷ luật), nên một nhãn "Soát được với KLAW" giống hệt sẽ khiến
 * người dùng tưởng KLAW đọc được nội dung công văn của họ. Nó không đọc.
 *
 * Một giới hạn nữa, không hiện trên thẻ vì thuộc về ai phải tuân: NĐ 30/2020
 * Đ2.1 chỉ áp cho cơ quan, tổ chức nhà nước và doanh nghiệp nhà nước. Với
 * doanh nghiệp tư nhân đây là chuẩn mực tham khảo, không phải nghĩa vụ.
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
  | "cong_van"
  | "hop_dong_mua_ban_tai_san"
  | "giay_uy_quyen"
  | "quyet_dinh_hdqt"
  | "don_khieu_nai"
  | "quyet_dinh_bo_nhiem"
  | "quy_che_noi_bo"
  | "ban_tu_khai"
  | "van_ban_giai_trinh"
  | "quy_che_dan_chu"
  | "don_xin_nghi_viec"
  | "thoa_thuan_cham_dut_hdld";

/** `undefined` = KLAW chưa có kiểu nào cho mẫu này, nên chưa soát được. */
export const loaiBackendCua = (id: string): LoaiVanBanBackend | undefined => LOAI_BACKEND[id]?.loai;

/** `undefined` = chưa nối backend. Ba giá trị còn lại là ba nhãn khác nhau. */
export const phamViSoatCuaMau = (id: string): PhamViSoat | undefined => LOAI_BACKEND[id]?.phamVi;

/**
 * Đảo `LOAI_BACKEND`: mã checklist máy chủ → các slug thẻ. `hdld` trả hai slug
 * vì HĐLĐ xác định và không xác định thời hạn dùng chung checklist; loại chưa
 * có thẻ (vd. `quyet_dinh_ky_luat`) trả [] — card gợi ý rơi về nút chọn tay.
 */
export function slugCuaLoai(loai: string): string[] {
  return Object.entries(LOAI_BACKEND)
    .filter(([, v]) => v.loai === loai)
    .map(([slug]) => slug);
}
