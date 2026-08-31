export type DocStatus = "active" | "partial" | "expired";

export type LegalDoc = {
  soHieu: string;
  ten: string;
  coQuan: string;
  ngay: string;
  status: DocStatus;
  trichDan?: string;
};

/**
 * Dữ liệu minh hoạ cho bản dùng thử — không phải cơ sở dữ liệu pháp luật thật.
 */
const DOCS: Record<string, LegalDoc> = {
  "45/2019/QH14": {
    soHieu: "45/2019/QH14",
    ten: "Bộ luật Lao động 2019",
    coQuan: "Quốc hội",
    ngay: "20/11/2019",
    status: "active",
    trichDan:
      "Thời gian thử việc do hai bên thoả thuận căn cứ vào tính chất và mức độ phức tạp của công việc, không quá 180 ngày đối với công việc của người quản lý doanh nghiệp.",
  },
  "36/2005/QH11": {
    soHieu: "36/2005/QH11",
    ten: "Luật Thương mại 2005",
    coQuan: "Quốc hội",
    ngay: "14/06/2005",
    status: "active",
    trichDan:
      "Mức phạt vi phạm đối với vi phạm nghĩa vụ hợp đồng hoặc tổng mức phạt đối với nhiều vi phạm do các bên thoả thuận trong hợp đồng, nhưng không quá 8% giá trị phần nghĩa vụ hợp đồng bị vi phạm.",
  },
  "91/2015/QH13": {
    soHieu: "91/2015/QH13",
    ten: "Bộ luật Dân sự 2015",
    coQuan: "Quốc hội",
    ngay: "24/11/2015",
    status: "active",
    trichDan:
      "Hợp đồng là sự thoả thuận giữa các bên về việc xác lập, thay đổi hoặc chấm dứt quyền, nghĩa vụ dân sự.",
  },
  "13/2023/ND-CP": {
    soHieu: "13/2023/NĐ-CP",
    ten: "Nghị định về bảo vệ dữ liệu cá nhân",
    coQuan: "Chính phủ",
    ngay: "17/04/2023",
    status: "active",
    trichDan:
      "Nghị định này quy định về bảo vệ dữ liệu cá nhân và trách nhiệm bảo vệ dữ liệu cá nhân của cơ quan, tổ chức, cá nhân có liên quan.",
  },
  "91/2025/QH15": {
    soHieu: "91/2025/QH15",
    ten: "Luật Bảo vệ dữ liệu cá nhân (tham chiếu minh hoạ)",
    coQuan: "Quốc hội",
    ngay: "26/06/2025",
    status: "partial",
    trichDan:
      "Nội dung tham chiếu minh hoạ trong bản dùng thử — cần đối chiếu với công báo trước khi sử dụng.",
  },
};

export const MOCK_DOCS: Record<string, LegalDoc> = DOCS;

export const docBySoHieu = (soHieu: string): LegalDoc | undefined =>
  MOCK_DOCS[soHieu] ??
  Object.values(MOCK_DOCS).find(
    (d) => d.soHieu.toLowerCase() === decodeURIComponent(soHieu).toLowerCase(),
  );

export const STATUS_LABEL: Record<DocStatus, string> = {
  active: "Còn hiệu lực",
  partial: "Hiệu lực một phần",
  expired: "Hết hiệu lực",
};

/** Truy xuất văn bản minh hoạ theo số hiệu, đảm bảo kiểu không undefined. */
export const DOC = (soHieu: string): LegalDoc => {
  const found = docBySoHieu(soHieu);
  if (!found) throw new Error(`Không có văn bản minh hoạ: ${soHieu}`);
  return found;
};
