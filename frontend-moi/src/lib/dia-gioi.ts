// Danh mục đơn vị hành chính dùng cho ô địa chỉ khi soạn thảo. Chưa đối chiếu
// với danh mục chính thức của Tổng cục Thống kê — phải đối chiếu trước khi
// bản thảo nào rời khỏi máy người dùng.
// Cấu trúc chính quyền địa phương 2 cấp từ 01/7/2025:
// Tỉnh/Thành phố trực thuộc trung ương → Phường/Xã/Đặc khu. KHÔNG còn cấp quận/huyện.

export type Tinh = { ten: string; capDuoi: string[] };

export const TINH_THANH: Tinh[] = [
  {
    ten: "Thành phố Hà Nội",
    capDuoi: [
      "Phường Ba Đình",
      "Phường Hoàn Kiếm",
      "Phường Cầu Giấy",
      "Phường Hà Đông",
      "Xã Sóc Sơn",
      "Xã Đông Anh",
    ],
  },
  {
    ten: "Thành phố Hồ Chí Minh",
    capDuoi: [
      "Phường Sài Gòn",
      "Phường Bến Thành",
      "Phường Tân Sơn Nhất",
      "Phường Thủ Đức",
      "Xã Bình Chánh",
      "Đặc khu Côn Đảo",
    ],
  },
  {
    ten: "Thành phố Đà Nẵng",
    capDuoi: [
      "Phường Hải Châu",
      "Phường Thanh Khê",
      "Phường Ngũ Hành Sơn",
      "Xã Hoà Vang",
      "Đặc khu Hoàng Sa",
    ],
  },
  {
    ten: "Thành phố Hải Phòng",
    capDuoi: ["Phường Hồng Bàng", "Phường Lê Chân", "Phường Ngô Quyền", "Xã An Dương", "Đặc khu Bạch Long Vĩ"],
  },
  {
    ten: "Thành phố Cần Thơ",
    capDuoi: ["Phường Ninh Kiều", "Phường Bình Thuỷ", "Phường Cái Khế", "Xã Phong Điền"],
  },
  {
    ten: "Thành phố Huế",
    capDuoi: ["Phường Phú Xuân", "Phường Thuận Hoá", "Xã Phong Điền", "Xã A Lưới"],
  },
  {
    ten: "Tỉnh Quảng Ninh",
    capDuoi: ["Phường Hạ Long", "Phường Bãi Cháy", "Xã Ba Chẽ", "Đặc khu Vân Đồn", "Đặc khu Cô Tô"],
  },
  {
    ten: "Tỉnh Khánh Hòa",
    capDuoi: ["Phường Nha Trang", "Phường Cam Ranh", "Xã Diên Khánh", "Đặc khu Trường Sa"],
  },
  {
    ten: "Tỉnh Đồng Nai",
    capDuoi: ["Phường Biên Hoà", "Phường Trảng Dài", "Xã Long Thành", "Xã Nhơn Trạch"],
  },
  {
    ten: "Tỉnh Nghệ An",
    capDuoi: ["Phường Trường Vinh", "Phường Cửa Lò", "Xã Nam Đàn", "Xã Kỳ Sơn"],
  },
  {
    ten: "Tỉnh Bắc Ninh",
    capDuoi: ["Phường Bắc Ninh", "Phường Từ Sơn", "Xã Yên Phong", "Xã Lương Tài"],
  },
  {
    ten: "Tỉnh Bình Dương",
    capDuoi: ["Phường Thủ Dầu Một", "Phường Dĩ An", "Xã Bến Cát", "Xã Dầu Tiếng"],
  },
];

export const capDuoiCua = (tenTinh: string) =>
  TINH_THANH.find((t) => t.ten === tenTinh)?.capDuoi ?? [];
