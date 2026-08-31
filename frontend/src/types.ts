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

/* ---- POST /soan-thao và POST /soat — Task 5, CHƯA TỒN TẠI khi Task 7 chạy ---- */

export type LoaiVanBan = 'hop_dong_lao_dong' | 'noi_quy_lao_dong' | 'quyet_dinh_ky_luat';

export interface SoanThaoRequest {
  loai: LoaiVanBan;
  facts: Record<string, unknown>;
}

export interface SoanThaoResponse {
  markdown: string;
  citations: Citation[];
  findings: Finding[];
  trace_id: string;
}

export interface SoatRequest {
  van_ban: string;
  loai: string;
  self_audit?: boolean;
}

export interface SoatResponse {
  findings: Finding[];
  trace_id: string;
}

export type MucDoPhatHien = 'chan' | 'canh_bao' | 'goi_y';

export interface Finding {
  muc_do: MucDoPhatHien;
  rule_id: string;
  thong_diep: string;
  /** duong_dan tới điều luật căn cứ — click được như citation. */
  can_cu: string;
  vi_tri?: string;
}
