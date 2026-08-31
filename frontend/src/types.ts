/**
 * Types translated 1:1 from fe-contract.md (src/models/schemas.py). Keep this
 * file in sync with the contract — do not add fields that aren't there, and
 * do not narrow a field the contract left as a plain `string` unless a
 * concrete enum is documented (see the note on `HieuLuc` below).
 */

/** Bốn result_type — bốn cách hiển thị, không thương lượng (fe-contract.md). */
export type ResultType = 'answer' | 'partial_coverage' | 'abstain' | 'out_of_scope';

/**
 * Nhãn hiệu lực của một trích dẫn. Declared as a literal union for
 * compile-time ergonomics (badge rendering switches on these five cases),
 * but the runtime guard in lib/api.ts only checks `string | null` — a future
 * label the backend adds shouldn't fail the whole response, just fall
 * through the badge switch's default case.
 */
export type HieuLuc =
  | 'con_hieu_luc'
  | 'bi_thay_the'
  | 'het_hieu_luc'
  | 'mot_phan_khong_xac_dinh'
  | 'can_doi_chieu_tay';

export interface Citation {
  /** Điều luật mô hình dẫn. */
  provision_id: number;
  /** Dòng câu trích THẬT SỰ khớp — khác provision_id ở 73,6% số Điều.
   *  Panel click-to-verify PHẢI fetch bằng field này, không phải provision_id. */
  khop_tai_id: number;
  /** `documents.id` — TEXT ở DB, nên STRING chứ không phải number.
   *  URL click-to-verify: `/api/v1/van-ban/{doc_id}?around={khop_tai_id}`. */
  doc_id: string;
  /** "45/2019/QH14 > Điều 127 > Khoản 2" — một địa chỉ, hiển thị bằng font-dia-chi. */
  duong_dan: string;
  bo_luat: string;
  /** Định danh văn bản. Hiển thị cái này — KHÔNG BAO GIỜ hiển thị title/tên. */
  so_ky_hieu: string;
  quote: string;
  hieu_luc: HieuLuc | null;
  tin_cay: string | null;
}

/**
 * Văn bản chi phối câu hỏi — KHÔNG phải trích dẫn đã kiểm chứng, không có quote.
 * Chỉ `partial_coverage` điền. Nhánh đó luôn có `citations: []` theo thiết kế,
 * nên đây là thứ DUY NHẤT cho phép mở được văn bản đang nói tới.
 * Tuyệt đối không parse `coverage_note` để bịa link.
 */
export interface Nguon {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
}

export interface TraCuuRequest {
  /** 1..2000 ký tự. */
  query: string;
  /** ISO "2026-08-31"; server trả 422 nếu sai định dạng. */
  as_of_date?: string;
  /** Nhãn ablation — FE không cần gửi. */
  config_name?: string;
}

export interface TraCuuResponse {
  result_type: ResultType;
  answer: string | null;
  citations: Citation[];
  nguon: Nguon[];
  warnings: string[];
  coverage_note: string | null;
  trace_id: string;
  config_name: string;
}

/**
 * GET /van-ban/{doc_id}?around=<provision_id> — dạng lazy duy nhất FE dùng.
 * (Endpoint cũng có dạng không tham số và dạng ?so_dieu=, nhưng FE không tiêu
 * thụ hai dạng đó nên không model ở đây — YAGNI.)
 */
export type CapProvision = 'dieu' | 'khoan' | 'diem';

export interface Provision {
  id: number;
  cap: CapProvision;
  so_hieu_cap: string;
  duong_dan: string;
  tieu_de: string;
  noi_dung: string;
  /** true cho Điều được hỏi VÀ mọi Khoản/Điểm con của nó — dùng để tô cả
   *  VÙNG đang xem, không phải một dòng đơn lẻ. false cho 4 Điều lân cận. */
  la_tam: boolean;
}

export interface VanBanAroundResponse {
  /** TEXT ở DB (`documents.id`, vd "95942") — KHÔNG ép number. */
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  provisions: Provision[];
}

/* ──────────── GET /van-ban/{doc_id} không tham số — mục lục ────────────── */

/** CHỈ bốn cấp cấu trúc tài liệu. Không bao giờ 'dieu': mục lục không kéo nội
 *  dung Điều (BLDS có 689 Điều), đó chính là lý do endpoint này lazy. */
export type CapMucLuc = 'phan' | 'chuong' | 'muc' | 'tieu_muc';

export interface MucLucItem {
  id: number;
  cap: CapMucLuc;
  so_hieu_cap: string;
  tieu_de: string;
  thu_tu: number;
}

export interface VanBanMucLucResponse {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  /** Rỗng với 36 văn bản tầng NÔNG (chỉ có metadata, chưa có toàn văn) —
   *  trang phải nói ra sự thật đó, không được hiện như văn bản rỗng. */
  muc_luc: MucLucItem[];
}

/* ── POST /soan-thao · POST /soat · GET /mau/{loai} — shape THẬT (Task 5) ─── */

/** Chỉ `hdld` có nội dung pháp lý. Hai loại kia hợp lệ về kiểu nhưng
 *  `/soan-thao` và `/soat` trả 501, còn `/mau` trả `facts: []`. */
export type LoaiVanBan = 'hdld' | 'noi_quy' | 'quyet_dinh_ky_luat';

/** Một trường của form nhập fact — SINH TỪ `config/rules.yaml`. Form phải dựng
 *  từ danh sách này, không hardcode: hardcode sẽ trôi lệch khỏi YAML ngay lần
 *  sửa rule đầu tiên. */
export interface FactField {
  key: string;
  nhan: string;
  /** "int" | "bool" | "str" theo `facts_meta:` trong YAML. Để nguyên `string`:
   *  một kiểu mới thêm vào YAML phải rơi về ô chữ, không làm sập cả form. */
  kieu: string;
  bat_buoc: boolean;
  lua_chon: string[] | null;
}

export interface MauResponse {
  loai_van_ban: string;
  facts: FactField[];
}

export interface SoanThaoRequest {
  loai_van_ban: LoaiVanBan;
  /** Fact VẮNG MẶT không phải lỗi: rule engine báo "không kiểm được" — một
   *  kết quả hợp lệ. Chỉ fact CÓ MẶT mà sai giá trị mới bị 422. */
  facts: Record<string, unknown>;
  /** Mặc định "thuong_mai" ở server. */
  nganh?: string;
  config_name?: string;
}

export interface SoatRequest {
  loai_van_ban: LoaiVanBan;
  /** >= 20 ký tự (server trả 422 nếu ngắn hơn). */
  text: string;
  facts?: Record<string, unknown>;
  nganh?: string;
}

export interface Finding {
  /** thieu_noi_dung | trai_luat | citation_khong_hop_le */
  loai: string;
  /** "chan" | "canh_bao" — giữ `string` để nhãn mới không làm sập danh sách. */
  muc_do: string;
  /** Câu hiển thị cho người dùng. */
  thong_diep: string;
  /** TRÍCH ĐOẠN 120 ký tự đầu của điều khoản TRONG VĂN BẢN ĐANG SOÁT —
   *  KHÔNG phải vị trí, và cũng KHÔNG phải câu trích từ luật. Đừng hiển thị
   *  nó như toạ độ, và đừng đưa nó vào chỗ chờ một `quote`. */
  dieu_khoan_lien_quan: string | null;
  /** `duong_dan` của điều luật căn cứ. */
  can_cu: string | null;
  rule_id: string | null;
  /** Cùng `khop_tai_id` mở được panel đối chiếu. Cả hai `null` khi
   *  `loai === 'citation_khong_hop_le'` — chính căn cứ đó không tồn tại, nên
   *  KHÔNG dựng link hỏng. */
  doc_id: string | null;
  khop_tai_id: number | null;
}

export interface AuditReport {
  dat: boolean;
  /** 0..1 */
  completeness: number;
  so_dieu_khoan: number;
  /** Do SERVER đặt, không phải client gửi lên: true khi đang soát output của
   *  CHÍNH KLAW (bên trong /soan-thao), false khi soát văn bản người dùng dán
   *  vào. Phân biệt này là số liệu đánh giá của khoá luận — phải hiển thị. */
  self_audit: boolean;
  findings: Finding[];
}

export interface SoanThaoResponse {
  /** Markdown thuần. */
  document: string;
  /** `list[dict]` ở server — không có schema chốt nên không dựng kiểu giả. */
  clauses: unknown[];
  audit_report: AuditReport;
  trace_id: string;
}

export interface SoatResponse {
  audit_report: AuditReport;
  trace_id: string;
}
