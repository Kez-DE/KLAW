// SAMPLE DATA FOR UI DEMO ONLY — must be replaced by a licensed legal database.

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

export const LINH_VUC = [
  "Lao động",
  "Doanh nghiệp",
  "Thương mại",
  "Dân sự",
  "Hình sự",
  "Đất đai",
  "Thuế",
  "Đầu tư",
  "Công nghệ thông tin",
  "Hành chính",
];

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

export const VAN_BAN: VanBan[] = [
  {
    soHieu: "45/2019/QH14",
    ten: "Bộ luật Lao động",
    tenNgan: "Bộ luật Lao động 2019",
    loai: "Bộ luật",
    coQuan: "Quốc hội",
    nguoiKy: "Nguyễn Thị Kim Ngân",
    chucVu: "Chủ tịch Quốc hội",
    ngayBanHanh: "20/11/2019",
    ngayHieuLuc: "01/01/2021",
    linhVuc: "Lao động",
    tinhTrang: "Còn hiệu lực",
    canhBao:
      "Văn bản này đã được sửa đổi, bổ sung. Xem văn bản hợp nhất mới nhất.",
    chuong: [
      {
        so: "I",
        ten: "Những quy định chung",
        dieu: [
          {
            so: 13,
            tieuDe: "Hợp đồng lao động",
            khoan: [
              {
                so: 1,
                text: "Hợp đồng lao động là sự thỏa thuận giữa người lao động và người sử dụng lao động về việc làm có trả công, tiền lương, điều kiện lao động, quyền và nghĩa vụ của mỗi bên trong quan hệ lao động.",
              },
              {
                so: 2,
                text: "Trước khi nhận người lao động vào làm việc, người sử dụng lao động phải giao kết hợp đồng lao động với người lao động.",
              },
            ],
          },
        ],
      },
      {
        so: "III",
        ten: "Hợp đồng lao động",
        dieu: [
          {
            so: 24,
            tieuDe: "Thử việc",
            muc: "Mục 1. Giao kết hợp đồng lao động",
            khoan: [
              {
                so: 1,
                text: "Người sử dụng lao động và người lao động có thể thỏa thuận nội dung thử việc ghi trong hợp đồng lao động hoặc thỏa thuận về thử việc bằng việc giao kết hợp đồng thử việc.",
              },
              {
                so: 2,
                text: "Nội dung chủ yếu của hợp đồng thử việc gồm thời gian thử việc và nội dung quy định tại các điểm a, b, c, đ, g và h khoản 1 Điều 21 của Bộ luật này.",
              },
              {
                so: 3,
                text: "Không áp dụng thử việc đối với người lao động giao kết hợp đồng lao động có thời hạn dưới 01 tháng.",
              },
            ],
            soVanBanSuaDoi: 0,
          },
          {
            so: 25,
            tieuDe: "Thời gian thử việc",
            muc: "Mục 1. Giao kết hợp đồng lao động",
            soVanBanSuaDoi: 3,
            khoan: [
              {
                so: 1,
                text: "Thời gian thử việc do hai bên thỏa thuận căn cứ vào tính chất và mức độ phức tạp của công việc nhưng chỉ được thử việc một lần đối với một công việc và bảo đảm điều kiện sau đây:",
                diem: [
                  {
                    ky: "a",
                    text: "Không quá 180 ngày đối với công việc của người quản lý doanh nghiệp theo quy định của Luật Doanh nghiệp, Luật Quản lý, sử dụng vốn nhà nước đầu tư vào sản xuất, kinh doanh tại doanh nghiệp;",
                    suaDoiBoi:
                      "Được sửa đổi bởi khoản 3 Điều 2 Luật sửa đổi, bổ sung một số điều của Bộ luật Lao động (dữ liệu minh hoạ)",
                  },
                  {
                    ky: "b",
                    text: "Không quá 60 ngày đối với công việc có chức danh nghề nghiệp cần trình độ chuyên môn, kỹ thuật từ cao đẳng trở lên;",
                  },
                  {
                    ky: "c",
                    text: "Không quá 30 ngày đối với công việc có chức danh nghề nghiệp cần trình độ chuyên môn, kỹ thuật trung cấp, công nhân kỹ thuật, nhân viên nghiệp vụ;",
                  },
                  {
                    ky: "d",
                    text: "Không quá 06 ngày làm việc đối với công việc khác.",
                  },
                ],
              },
              {
                so: 2,
                text: "Tiền lương của người lao động trong thời gian thử việc do hai bên thỏa thuận nhưng ít nhất phải bằng 85% mức lương của công việc đó.",
              },
              {
                so: 3,
                text: "Quy định về thời gian thử việc kéo dài đối với lao động theo mùa vụ đã bị bãi bỏ.",
                baiBo: true,
              },
            ],
          },
          {
            so: 35,
            tieuDe:
              "Quyền đơn phương chấm dứt hợp đồng lao động của người lao động",
            muc: "Mục 3. Chấm dứt hợp đồng lao động",
            soVanBanSuaDoi: 1,
            khoan: [
              {
                so: 1,
                text: "Người lao động có quyền đơn phương chấm dứt hợp đồng lao động nhưng phải báo trước cho người sử dụng lao động: ít nhất 45 ngày với hợp đồng không xác định thời hạn; ít nhất 30 ngày với hợp đồng xác định thời hạn từ 12 đến 36 tháng.",
              },
              {
                so: 2,
                text: "Người lao động có quyền đơn phương chấm dứt hợp đồng lao động không cần báo trước trong trường hợp không được bố trí theo đúng công việc, bị người sử dụng lao động ngược đãi, quấy rối tình dục hoặc không được trả đủ lương đúng thời hạn.",
              },
            ],
          },
        ],
      },
      {
        so: "VIII",
        ten: "Kỷ luật lao động, trách nhiệm vật chất",
        dieu: [
          {
            so: 125,
            tieuDe: "Áp dụng hình thức xử lý kỷ luật sa thải",
            khoan: [
              {
                so: 1,
                text: "Hình thức xử lý kỷ luật sa thải được người sử dụng lao động áp dụng khi người lao động có hành vi trộm cắp, tham nhũng, đánh bạc, cố ý gây thương tích, sử dụng ma túy tại nơi làm việc.",
              },
              {
                so: 2,
                text: "Người lao động tự ý bỏ việc 05 ngày cộng dồn trong thời hạn 30 ngày hoặc 20 ngày cộng dồn trong thời hạn 365 ngày mà không có lý do chính đáng cũng bị xử lý kỷ luật sa thải.",
              },
            ],
          },
        ],
      },
    ],
    quanHe: [
      {
        nhom: "Văn bản được dẫn chiếu",
        items: [
          { soHieu: "59/2020/QH14", ten: "Luật Doanh nghiệp 2020" },
          { soHieu: "91/2015/QH13", ten: "Bộ luật Dân sự 2015" },
        ],
      },
      {
        nhom: "Văn bản sửa đổi, bổ sung",
        items: [
          {
            soHieu: "356/2025/NĐ-CP",
            ten: "Nghị định hướng dẫn một số điều của Bộ luật Lao động (minh hoạ)",
          },
        ],
      },
      {
        nhom: "Văn bản bị thay thế",
        items: [{ soHieu: "10/2012/QH13", ten: "Bộ luật Lao động 2012" }],
      },
      {
        nhom: "Văn bản hướng dẫn thi hành",
        items: [
          {
            soHieu: "356/2025/NĐ-CP",
            ten: "Nghị định quy định chi tiết về hợp đồng lao động và thử việc (minh hoạ)",
          },
        ],
      },
      {
        nhom: "Văn bản liên quan cùng lĩnh vực",
        items: [{ soHieu: "58/2014/QH13", ten: "Luật Bảo hiểm xã hội 2014" }],
      },
    ],
  },
  {
    soHieu: "36/2005/QH11",
    ten: "Luật Thương mại",
    tenNgan: "Luật Thương mại 2005",
    loai: "Luật",
    coQuan: "Quốc hội",
    nguoiKy: "Nguyễn Văn An",
    chucVu: "Chủ tịch Quốc hội",
    ngayBanHanh: "14/06/2005",
    ngayHieuLuc: "01/01/2006",
    linhVuc: "Thương mại",
    tinhTrang: "Còn hiệu lực",
    chuong: [
      {
        so: "VII",
        ten: "Chế tài trong thương mại và giải quyết tranh chấp",
        dieu: [
          {
            so: 300,
            tieuDe: "Phạt vi phạm",
            khoan: [
              {
                so: 1,
                text: "Phạt vi phạm là việc bên bị vi phạm yêu cầu bên vi phạm trả một khoản tiền phạt do vi phạm hợp đồng nếu trong hợp đồng có thỏa thuận, trừ các trường hợp miễn trách nhiệm quy định tại Điều 294 của Luật này.",
              },
            ],
          },
          {
            so: 301,
            tieuDe: "Mức phạt vi phạm",
            soVanBanSuaDoi: 0,
            khoan: [
              {
                so: 1,
                text: "Mức phạt đối với vi phạm nghĩa vụ hợp đồng hoặc tổng mức phạt đối với nhiều vi phạm do các bên thỏa thuận trong hợp đồng, nhưng không quá 8% giá trị phần nghĩa vụ hợp đồng bị vi phạm, trừ trường hợp quy định tại Điều 266 của Luật này.",
              },
            ],
          },
          {
            so: 302,
            tieuDe: "Bồi thường thiệt hại",
            khoan: [
              {
                so: 1,
                text: "Bồi thường thiệt hại là việc bên vi phạm bồi thường những tổn thất do hành vi vi phạm hợp đồng gây ra cho bên bị vi phạm.",
              },
              {
                so: 2,
                text: "Giá trị bồi thường thiệt hại bao gồm giá trị tổn thất thực tế, trực tiếp mà bên bị vi phạm phải chịu và khoản lợi trực tiếp mà bên bị vi phạm đáng lẽ được hưởng nếu không có hành vi vi phạm.",
              },
            ],
          },
        ],
      },
    ],
    quanHe: [
      {
        nhom: "Văn bản được dẫn chiếu",
        items: [{ soHieu: "91/2015/QH13", ten: "Bộ luật Dân sự 2015" }],
      },
      {
        nhom: "Văn bản liên quan cùng lĩnh vực",
        items: [{ soHieu: "59/2020/QH14", ten: "Luật Doanh nghiệp 2020" }],
      },
    ],
  },
  {
    soHieu: "91/2015/QH13",
    ten: "Bộ luật Dân sự",
    tenNgan: "Bộ luật Dân sự 2015",
    loai: "Bộ luật",
    coQuan: "Quốc hội",
    nguoiKy: "Nguyễn Sinh Hùng",
    chucVu: "Chủ tịch Quốc hội",
    ngayBanHanh: "24/11/2015",
    ngayHieuLuc: "01/01/2017",
    linhVuc: "Dân sự",
    tinhTrang: "Còn hiệu lực",
    chuong: [
      {
        so: "XV",
        ten: "Quy định chung về hợp đồng",
        dieu: [
          {
            so: 385,
            tieuDe: "Khái niệm hợp đồng",
            khoan: [
              {
                so: 1,
                text: "Hợp đồng là sự thỏa thuận giữa các bên về việc xác lập, thay đổi hoặc chấm dứt quyền, nghĩa vụ dân sự.",
              },
            ],
          },
          {
            so: 418,
            tieuDe: "Thỏa thuận phạt vi phạm",
            khoan: [
              {
                so: 1,
                text: "Phạt vi phạm là sự thỏa thuận giữa các bên trong hợp đồng, theo đó bên vi phạm nghĩa vụ phải nộp một khoản tiền cho bên bị vi phạm.",
              },
              {
                so: 2,
                text: "Mức phạt vi phạm do các bên thỏa thuận, trừ trường hợp luật liên quan có quy định khác.",
              },
            ],
          },
        ],
      },
    ],
    quanHe: [
      {
        nhom: "Văn bản liên quan cùng lĩnh vực",
        items: [{ soHieu: "36/2005/QH11", ten: "Luật Thương mại 2005" }],
      },
    ],
  },
  {
    soHieu: "59/2020/QH14",
    ten: "Luật Doanh nghiệp",
    tenNgan: "Luật Doanh nghiệp 2020",
    loai: "Luật",
    coQuan: "Quốc hội",
    nguoiKy: "Nguyễn Thị Kim Ngân",
    chucVu: "Chủ tịch Quốc hội",
    ngayBanHanh: "17/06/2020",
    ngayHieuLuc: "01/01/2021",
    linhVuc: "Doanh nghiệp",
    tinhTrang: "Đã sửa đổi, bổ sung",
    canhBao:
      "Văn bản này đã được sửa đổi, bổ sung. Xem văn bản hợp nhất mới nhất.",
    chuong: [
      {
        so: "I",
        ten: "Những quy định chung",
        dieu: [
          {
            so: 4,
            tieuDe: "Giải thích từ ngữ",
            soVanBanSuaDoi: 2,
            khoan: [
              {
                so: 24,
                text: "Người quản lý doanh nghiệp là người quản lý doanh nghiệp tư nhân và người quản lý công ty, bao gồm chủ doanh nghiệp tư nhân, thành viên hợp danh, Chủ tịch Hội đồng thành viên, Giám đốc hoặc Tổng giám đốc và cá nhân giữ chức danh quản lý khác theo quy định tại Điều lệ công ty.",
                suaDoiBoi:
                  "Được sửa đổi bởi khoản 1 Điều 1 Luật sửa đổi, bổ sung một số điều của Luật Doanh nghiệp (dữ liệu minh hoạ)",
              },
            ],
          },
          {
            so: 12,
            tieuDe: "Người đại diện theo pháp luật của doanh nghiệp",
            khoan: [
              {
                so: 1,
                text: "Người đại diện theo pháp luật của doanh nghiệp là cá nhân đại diện cho doanh nghiệp thực hiện các quyền và nghĩa vụ phát sinh từ giao dịch của doanh nghiệp, đại diện cho doanh nghiệp với tư cách người yêu cầu giải quyết việc dân sự, nguyên đơn, bị đơn.",
              },
              {
                so: 2,
                text: "Công ty trách nhiệm hữu hạn và công ty cổ phần có thể có một hoặc nhiều người đại diện theo pháp luật; Điều lệ công ty quy định cụ thể số lượng, chức danh quản lý và quyền, nghĩa vụ của từng người.",
              },
            ],
          },
        ],
      },
    ],
    quanHe: [
      {
        nhom: "Văn bản sửa đổi, bổ sung",
        items: [
          {
            soHieu: "03/2022/QH15",
            ten: "Luật sửa đổi, bổ sung một số điều của Luật Doanh nghiệp (minh hoạ)",
          },
        ],
      },
      {
        nhom: "Văn bản liên quan cùng lĩnh vực",
        items: [{ soHieu: "45/2019/QH14", ten: "Bộ luật Lao động 2019" }],
      },
    ],
  },
  {
    soHieu: "13/2023/NĐ-CP",
    ten: "Nghị định về bảo vệ dữ liệu cá nhân",
    tenNgan: "Nghị định 13/2023/NĐ-CP",
    loai: "Nghị định",
    coQuan: "Chính phủ",
    nguoiKy: "Trần Lưu Quang",
    chucVu: "Phó Thủ tướng Chính phủ",
    ngayBanHanh: "17/04/2023",
    ngayHieuLuc: "01/07/2023",
    linhVuc: "Công nghệ thông tin",
    tinhTrang: "Còn hiệu lực",
    chuong: [
      {
        so: "II",
        ten: "Bảo vệ dữ liệu cá nhân và biện pháp bảo vệ",
        dieu: [
          {
            so: 11,
            tieuDe: "Sự đồng ý của chủ thể dữ liệu",
            khoan: [
              {
                so: 1,
                text: "Sự đồng ý của chủ thể dữ liệu được áp dụng đối với tất cả các hoạt động trong quy trình xử lý dữ liệu cá nhân, trừ trường hợp luật có quy định khác.",
              },
              {
                so: 2,
                text: "Sự đồng ý của chủ thể dữ liệu chỉ có hiệu lực khi chủ thể dữ liệu tự nguyện và biết rõ loại dữ liệu cá nhân được xử lý, mục đích xử lý, tổ chức, cá nhân được xử lý và các quyền, nghĩa vụ của chủ thể dữ liệu.",
                diem: [
                  {
                    ky: "a",
                    text: "Sự đồng ý phải được thể hiện rõ ràng, cụ thể bằng văn bản, giọng nói, đánh dấu vào ô đồng ý hoặc hình thức khác thể hiện được sự đồng ý;",
                  },
                  {
                    ky: "b",
                    text: "Sự im lặng hoặc không phản hồi của chủ thể dữ liệu không được coi là sự đồng ý.",
                  },
                ],
              },
            ],
          },
          {
            so: 24,
            tieuDe: "Đánh giá tác động xử lý dữ liệu cá nhân",
            soVanBanSuaDoi: 1,
            khoan: [
              {
                so: 1,
                text: "Bên Kiểm soát dữ liệu cá nhân, Bên Kiểm soát và xử lý dữ liệu cá nhân lập và lưu giữ Hồ sơ đánh giá tác động xử lý dữ liệu cá nhân của mình kể từ thời điểm bắt đầu xử lý dữ liệu cá nhân.",
              },
              {
                so: 2,
                text: "Hồ sơ đánh giá tác động xử lý dữ liệu cá nhân phải luôn có sẵn để phục vụ hoạt động kiểm tra, đánh giá của Bộ Công an và gửi Bộ Công an 01 bản chính trong thời gian 60 ngày kể từ ngày tiến hành xử lý dữ liệu cá nhân.",
              },
            ],
          },
        ],
      },
    ],
    quanHe: [
      {
        nhom: "Văn bản được dẫn chiếu",
        items: [{ soHieu: "91/2015/QH13", ten: "Bộ luật Dân sự 2015" }],
      },
      {
        nhom: "Văn bản hướng dẫn thi hành",
        items: [
          {
            soHieu: "356/2025/NĐ-CP",
            ten: "Nghị định hướng dẫn chuyển dữ liệu cá nhân ra nước ngoài (minh hoạ)",
          },
        ],
      },
    ],
  },
  {
    soHieu: "356/2025/NĐ-CP",
    ten: "Nghị định quy định chi tiết một số điều về thuế thu nhập doanh nghiệp",
    tenNgan: "Nghị định 356/2025/NĐ-CP",
    loai: "Nghị định",
    coQuan: "Chính phủ",
    nguoiKy: "Hồ Đức Phớc",
    chucVu: "Phó Thủ tướng Chính phủ",
    ngayBanHanh: "12/05/2025",
    ngayHieuLuc: "01/01/2027",
    linhVuc: "Thuế",
    tinhTrang: "Chưa có hiệu lực",
    canhBao:
      "Văn bản chưa có hiệu lực thi hành. Chỉ sử dụng để chuẩn bị tuân thủ, không viện dẫn làm căn cứ áp dụng.",
    chuong: [
      {
        so: "II",
        ten: "Thu nhập chịu thuế và chi phí được trừ",
        dieu: [
          {
            so: 15,
            tieuDe: "Chi phí được trừ khi xác định thu nhập chịu thuế",
            khoan: [
              {
                so: 1,
                text: "Doanh nghiệp được trừ mọi khoản chi nếu khoản chi thực tế phát sinh liên quan đến hoạt động sản xuất, kinh doanh, có đủ hóa đơn, chứng từ hợp pháp và có chứng từ thanh toán không dùng tiền mặt đối với hóa đơn từ 05 triệu đồng trở lên.",
                diem: [
                  {
                    ky: "a",
                    text: "Khoản chi cho hoạt động nghiên cứu và phát triển được trừ bổ sung 50% giá trị thực tế phát sinh trong kỳ tính thuế;",
                  },
                  {
                    ky: "b",
                    text: "Khoản chi vượt định mức nội bộ nhưng không vượt định mức do pháp luật quy định vẫn được trừ nếu có hồ sơ giải trình.",
                  },
                ],
              },
              {
                so: 2,
                text: "Các khoản chi không được trừ gồm tiền phạt vi phạm hành chính, khoản chi không có chứng từ hợp pháp và khoản chi tài trợ không đúng đối tượng theo quy định.",
              },
            ],
          },
        ],
      },
    ],
    quanHe: [
      {
        nhom: "Văn bản liên quan cùng lĩnh vực",
        items: [{ soHieu: "59/2020/QH14", ten: "Luật Doanh nghiệp 2020" }],
      },
    ],
  },
];

/* ------------------------------ Tra cứu helpers --------------------------- */

export const boDau = (s: string) =>
  s
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/gi, "d")
    .toLowerCase();

export const VIET_TAT: Record<string, string> = {
  "bllđ": "Bộ luật Lao động",
  blld: "Bộ luật Lao động",
  blds: "Bộ luật Dân sự",
  blhs: "Bộ luật Hình sự",
  ldn: "Luật Doanh nghiệp",
  ltm: "Luật Thương mại",
  "nđ": "Nghị định",
  nd: "Nghị định",
  tt: "Thông tư",
  "qđ": "Quyết định",
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
export function chuoiTrichDan(
  vb: VanBan,
  dieu: Dieu,
  khoan?: Khoan,
  diem?: Diem,
): string {
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
          const diemHit = khoan.diem?.find((d) =>
            terms.some((t) => boDau(d.text).includes(t)),
          );
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
export const idKhoan = (dieuSo: number, khoanSo: number) =>
  `dieu-${dieuSo}-khoan-${khoanSo}`;
