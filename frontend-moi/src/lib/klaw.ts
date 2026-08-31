/**
 * Kiểu dữ liệu của hợp đồng KLAW ↔ FE.
 *
 * Pha 5 dựng THÀNH PHẦN TRÌNH BÀY, chưa nối máy chủ: chưa có hàm fetch nào ở
 * đây, và cũng chưa có type guard runtime. Cái có mặt là hình dạng dữ liệu mà
 * các thành phần nhận qua props, để ngày nối endpoint không phải sửa lại giao
 * diện — chỉ điền nguồn.
 *
 * Nguyên tắc giữ khi nối: KHÔNG thu hẹp một trường mà hợp đồng để `string`.
 * Backend thêm nhãn thứ bảy là chuyện bình thường; nó phải rơi vào nhánh an
 * toàn chứ không làm sập cả thẻ kết quả.
 */

/** Bốn `result_type` — bốn cách hiển thị, không thương lượng. */
export type ResultType = "answer" | "partial_coverage" | "abstain" | "out_of_scope";

/**
 * Sáu nhãn hiệu lực.
 *
 * Khai bằng union để lúc viết mã có gợi ý, NHƯNG mọi thành phần đọc nhãn đều
 * `switch` trên `string`: ràng buộc thật ở runtime chỉ là `string | null`.
 *
 * `bi_sua_doi` là nhãn mới (backend vừa dựng, `do_tin_cay: cao`) và KHÁC
 * `mot_phan_khong_xac_dinh` ở đúng một điểm, điểm quan trọng nhất: cái trước
 * biết đích danh điều khoản / văn bản / ngày sửa, cái sau nói thẳng là không
 * biết. Hai câu không được rút gọn thành một.
 */
export type HieuLuc =
  | "con_hieu_luc"
  | "bi_thay_the"
  | "bi_sua_doi"
  | "het_hieu_luc"
  | "mot_phan_khong_xac_dinh"
  | "can_doi_chieu_tay";

export interface Citation {
  /** Điều luật mô hình dẫn. */
  provision_id: number;
  /**
   * Dòng câu trích THẬT SỰ khớp. Khác `provision_id` ở **73,6% số Điều**, vì
   * phần lớn Điều chỉ có tiêu đề còn nội dung nằm ở Khoản/Điểm con. Panel đối
   * chiếu PHẢI mở bằng trường này.
   */
  khop_tai_id: number;
  /** `documents.id` — TEXT ở CSDL, nên `string`, không ép `number`. */
  doc_id: string;
  /** "45/2019/QH14 > Điều 127 > Khoản 2" — một địa chỉ, không phải một cái tên. */
  duong_dan: string;
  bo_luat: string;
  /** Định danh văn bản cho người đọc. KHÔNG BAO GIỜ hiển thị `ten`. */
  so_ky_hieu: string;
  quote: string;
  hieu_luc: HieuLuc | null;
  tin_cay: string | null;
}

/**
 * Văn bản chi phối câu hỏi — KHÔNG phải trích dẫn đã kiểm chứng, không có
 * `quote`, không có nhãn hiệu lực. Chỉ nhánh `partial_coverage` điền, và nhánh
 * đó luôn có `citations: []`, nên đây là thứ DUY NHẤT mở được văn bản đang
 * nói tới. Tuyệt đối không cạo `coverage_note` ra để bịa một liên kết.
 */
export interface Nguon {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
}

export interface TraCuuKetQua {
  result_type: ResultType;
  answer: string | null;
  citations: Citation[];
  nguon: Nguon[];
  warnings: string[];
  coverage_note: string | null;
  trace_id: string;
}

export type CapProvision = "dieu" | "khoan" | "diem";

export interface Provision {
  id: number;
  cap: CapProvision;
  so_hieu_cap: string;
  duong_dan: string;
  tieu_de: string;
  noi_dung: string;
  /**
   * true cho Điều được hỏi VÀ mọi Khoản/Điểm con của nó. Dùng để tô cả **VÙNG**
   * đang xem, không phải một dòng đơn lẻ. false cho các Điều lân cận.
   */
  la_tam: boolean;
}

export interface VanBanQuanhDieu {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  provisions: Provision[];
}

/**
 * Tám nhánh lỗi. Bản Klaw_FE chỉ có một trạng thái `error` chung, và một thông
 * báo chung nói được đúng một câu vô dụng cho tám tình huống rất khác nhau.
 *
 * `invalid_response` là nhánh dễ mất nhất và nguy hiểm nhất: máy chủ trả 2xx
 * nhưng body sai hình dạng. Nếu không có nhánh này thì giao diện hoặc sập, hoặc
 * — tệ hơn — render một câu trả lời rỗng như thể đó là câu trả lời thật.
 */
export type ApiErrorKind =
  | "network" // fetch() tự nó thất bại: mất mạng, DNS, CORS bị chặn
  | "timeout" // vượt thời gian chờ nội bộ
  | "aborted" // người dùng bấm huỷ, hoặc một lượt gọi mới thay thế lượt cũ
  | "not_implemented" // 501: loại văn bản chưa có nội dung pháp lý
  | "not_found" // 404 có nghĩa "không có"
  | "invalid_request" // 4xx khác, vd 422 sai định dạng as_of_date
  | "server_error" // 5xx
  | "invalid_response"; // 2xx nhưng body sai hình dạng

export interface ApiError {
  kind: ApiErrorKind;
  /** Tiếng Việt, hiển thị thẳng được cho người dùng. */
  message: string;
  status?: number;
  /** Chỉ để gỡ lỗi — không hiển thị thẳng. */
  detail?: unknown;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };
