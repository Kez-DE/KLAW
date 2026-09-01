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
  | "unauthorized" // 401/403: thiếu API key, hoặc chưa đăng nhập
  | "rate_limited" // 429: quá nhịp, hết hạn mức tháng, hoặc chạm trần chi phí ngày
  | "invalid_request" // 4xx khác, vd 422 sai định dạng as_of_date
  | "server_error" // 5xx
  | "invalid_response"; // 2xx nhưng body sai hình dạng

/*
 * Hai nhánh `unauthorized` / `rate_limited` thêm ở pha nối backend, sau khi đọc
 * `bao_ve.py`: cổng bảo vệ trả 401 (API key / bearer) và 429 (nhịp, hạn mức
 * tháng, trần chi phí ngày) như hai tình huống riêng biệt, kèm `Retry-After`.
 * Gộp chúng vào `invalid_request` sẽ khiến `BaoLoi` khuyên "kiểm tra lại nội
 * dung đã nhập" — một câu SAI về câu hỏi của người dùng khi nguyên nhân thật là
 * hết lượt hoặc chưa đăng nhập. Đúng loại khẳng định không kiểm chứng được mà
 * dự án này tồn tại để loại bỏ, chỉ khác là ở tầng thông báo lỗi.
 */

export interface ApiError {
  kind: ApiErrorKind;
  /** Tiếng Việt, hiển thị thẳng được cho người dùng. */
  message: string;
  status?: number;
  /** Chỉ để gỡ lỗi — không hiển thị thẳng. */
  detail?: unknown;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

/* ═══════════════════════════════════════════════════════════════════════════
 * Hợp đồng 8 endpoint của Pha 2 — chép từ `src/models/schemas.py`.
 *
 * Ngày tháng là `string` ISO ("2019-11-20"), KHÔNG phải `Date`: đó là thứ JSON
 * mang được, và mọi phép so sánh/hiển thị ở FE làm trên chuỗi ISO là đủ. Ép
 * sang `Date` ở tầng kiểu sẽ nói dối về thứ `JSON.parse` thật sự trả về.
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Phán quyết hiệu lực của KLAW (`effectivity.py`).
 *
 * `verdict` để `string`, KHÔNG thu hẹp về `HieuLuc`: backend nói thẳng rằng
 * nhãn mới có thể xuất hiện, và `BadgeHieuLuc` đã có nhánh `default` cho đúng
 * việc đó. Thu hẹp ở đây chỉ chuyển một nhãn lạ từ "hiện nguyên chuỗi" thành
 * "TypeScript nói dối là chuyện đó không xảy ra được".
 */
export interface HieuLucChiTiet {
  verdict: string;
  tin_cay: string;
  ly_do: string;
}

/* ── GET /bo-loc — nguồn DUY NHẤT cho giá trị bộ lọc ─────────────────────── */

export interface GiaTriLoc {
  gia_tri: string;
  so_van_ban: number;
}

export interface BoLoc {
  tong_van_ban: number;
  loai_van_ban: GiaTriLoc[];
  co_quan_ban_hanh: GiaTriLoc[];
  /** 79/126 văn bản KHÔNG khai cơ quan: tổng theo cơ quan ≠ tổng corpus. */
  co_quan_khong_ro: number;
  nam_min: number | null;
  nam_max: number | null;
  sap_xep: string[];
}

/* ── GET /tim-kiem — BM25, chất lượng TỪ KHOÁ (không phải ngữ nghĩa) ─────── */

export interface DongTimKiem {
  provision_id: number;
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  loai_van_ban: string;
  co_quan_ban_hanh: string | null;
  ngay_ban_hanh: string | null;
  cap: string;
  so_hieu_cap: string;
  duong_dan: string;
  tieu_de: string;
  trich: string;
  score: number;
  hieu_luc: HieuLucChiTiet;
}

export interface TimKiem {
  q: string;
  /** Của TOÀN tập khớp, không phải của trang đang xem. */
  tong_dieu_khoan: number;
  tong_van_ban: number;
  limit: number;
  offset: number;
  sap_xep: string;
  ket_qua: DongTimKiem[];
}

/* ── GET /van-ban/{doc_id}/hieu-luc — nguồn hiệu lực DUY NHẤT ────────────── */

export interface SuaBoi {
  /** Vị trí VBHN nêu; có thể KHÁC `duong_dan` khi là khoản mới thêm ("8a"). */
  vi_tri: string;
  so_ky_hieu: string | null;
  duong_dan: string | null;
  tu_ngay: string | null;
  nguon: string;
  do_tin_cay: string;
}

export interface DieuKhoanHieuLuc {
  provision_id: number;
  duong_dan: string;
  cap: string;
  so_hieu_cap: string;
  tieu_de: string;
  hieu_luc: HieuLucChiTiet;
  sua_boi: SuaBoi[];
}

export interface VanBanHieuLuc {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  as_of: string;
  van_ban: HieuLucChiTiet;
  /**
   * Bản đồ sửa đổi cấp điều khoản mới phủ 1/126 văn bản (4 dòng, đều của
   * `45/2019/QH14`). **Rỗng là BÌNH THƯỜNG, không phải lỗi** — giao diện phải
   * đọc mảng rỗng như "chưa có bằng chứng cấp điều khoản", không như "hỏng".
   */
  dieu_khoan: DieuKhoanHieuLuc[];
}

/* ── GET /van-ban/{doc_id}/lien-quan — bản đồ ĐIỀU HƯỚNG, không phán quyết ─ */

export interface VanBanLienQuanItem {
  /** null ⇒ văn bản nằm NGOÀI corpus ⇒ KHÔNG dựng link (link đó ra 404). */
  doc_id: string | null;
  so_ky_hieu: string;
  bo_luat: string | null;
  trong_corpus: boolean;
}

export interface NhomLienQuan {
  loai: number;
  nhan: string;
  chieu: "di_ra" | "di_vao";
  /**
   * false ⇒ chiều ngữ nghĩa CHƯA ĐO. Hiện nhãn quan hệ, tuyệt đối không viết
   * thành câu "Văn bản này thay thế X" — câu đó có 50% khả năng ngược.
   */
  chieu_da_do: boolean;
  so_luong: number;
  van_ban: VanBanLienQuanItem[];
}

export interface VanBanLienQuan {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  nhom: NhomLienQuan[];
  dan_chieu_noi_bo: { so_luong: number; ghi_chu: string };
}

/* ── GET /van-ban/{doc_id} — metadata 10 trường, KHÔNG có `tinh_trang` ───── */

export interface VanBanMeta {
  doc_id: string;
  so_ky_hieu: string;
  /** = `documents.ten`. HIỂN THỊ, không bao giờ là khoá định danh. */
  bo_luat: string;
  loai_van_ban: string;
  /** NULL trên 79/126: KHÔNG BIẾT, không phải "không có cơ quan". */
  co_quan_ban_hanh: string | null;
  ngay_ban_hanh: string | null;
  ngay_hieu_luc: string | null;
  /** NULL trên 95/126. Trường của CHÍNH CSDL quốc gia và tin được. */
  ngay_het_hieu_luc: string | null;
  nguoi_ky: string | null;
  chuc_danh_nguoi_ky: string | null;
}

export interface MucLucItem {
  id: number;
  cap: "phan" | "chuong" | "muc" | "tieu_muc";
  so_hieu_cap: string;
  tieu_de: string;
  thu_tu: number;
}

export type VanBanMucLuc = VanBanMeta & { muc_luc: MucLucItem[] };
export type VanBanProvisions = VanBanMeta & { provisions: Provision[] };

/* ── GET /van-ban/{doc_id}/tim — ô lọc mục lục ───────────────────────────── */

export interface DongTimTrongVanBan {
  provision_id: number;
  cap: string;
  so_hieu_cap: string;
  duong_dan: string;
  tieu_de: string;
  trich: string;
  /** Thứ tự TRONG CÂY — khoá sắp xếp. Đây là mục lục, không phải bảng xếp hạng. */
  thu_tu: number;
}

export interface TimTrongVanBan {
  doc_id: string;
  so_ky_hieu: string;
  q: string;
  tong: number;
  limit: number;
  ket_qua: DongTimTrongVanBan[];
}

/* ── GET /han-muc ───────────────────────────────────────────────────────── */

export interface HanMuc {
  /** false ⇒ ẨN widget hạn mức. Bốn trường số là `null`, KHÔNG phải 0. */
  ap_dung: boolean;
  plan: string | null;
  han_muc: number | null;
  da_dung: number | null;
  con_lai: number | null;
  dat_lai_luc: string;
  ghi_chu: string;
}

/* ── GET /pham-vi — hai tầng, vì corpus thật có hai tầng ─────────────────── */

export interface VanBanPhamVi {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  loai_van_ban: string;
  so_dieu_khoan: number;
  /** Tuyên bố của CSDL quốc gia, KHÔNG phải phán quyết của KLAW. */
  tinh_trang_moj: string | null;
}

export interface TangPhamVi {
  so_van_ban: number;
  so_dieu_khoan: number;
  van_ban: VanBanPhamVi[];
}

export interface PhamVi {
  /** Có toàn văn — trả lời được thành `answer`. */
  sau: TangPhamVi;
  /** Chỉ metadata — CHÍNH LÀ thứ sinh ra `partial_coverage`. */
  nong: TangPhamVi;
}

/* ── GET /mau/{loai} · POST /soan-thao · POST /soat ──────────────────────── */

export type LoaiVanBanBackend = "hdld" | "noi_quy" | "quyet_dinh_ky_luat";

export interface TruongFact {
  key: string;
  nhan: string;
  kieu: string;
  bat_buoc: boolean;
  lua_chon: string[] | null;
}

export interface Mau {
  loai_van_ban: string;
  facts: TruongFact[];
}

export interface PhatHien {
  loai: string;
  muc_do: string;
  thong_diep: string;
  dieu_khoan_lien_quan: string | null;
  can_cu: string | null;
  rule_id: string | null;
  doc_id: string | null;
  /** Mở panel đối chiếu bằng trường này. null cho `citation_khong_hop_le`. */
  khop_tai_id: number | null;
  /**
   * true = rule KHÔNG được kiểm (thiếu fact), **không phải** văn bản sai. Tô
   * nó như một vi phạm là nói với người dùng rằng văn bản của họ trái luật
   * trong khi máy chỉ thiếu dữ liệu.
   */
  khong_kiem_duoc: boolean;
}

export interface BaoCaoSoat {
  dat: boolean;
  completeness: number;
  so_dieu_khoan: number;
  self_audit: boolean;
  findings: PhatHien[];
}

export interface SoanThaoKetQua {
  /** Markdown. */
  document: string;
  clauses: unknown[];
  audit_report: BaoCaoSoat;
  trace_id: string;
}

/* ── POST /tra-cuu/luong — SSE, stream BƯỚC (không stream token) ─────────── */

export interface BuocKhai {
  buoc: string;
  nhan: string;
  thu_tu: number;
}

export interface SuKienBatDau {
  trace_id: string;
  config_name: string;
  cac_buoc: BuocKhai[];
}

export interface SuKienBuoc {
  buoc: string;
  nhan: string;
  thu_tu: number | null;
  tong: number;
  chi_tiet: Record<string, number | string | null>;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * Kiểm hình dạng runtime.
 *
 * `ApiErrorKind.invalid_response` chỉ có nghĩa nếu có ai đó thật sự kiểm. Kiểm
 * ĐÚNG những trường mà sai đi sẽ hỏng ÂM THẦM — mảng thiếu render thành màn
 * trống đọc như "không có gì", `result_type` lạ rơi vào nhánh `answer` và hiện
 * một câu trả lời rỗng như thể đó là câu trả lời. Không kiểm những trường mà
 * sai đi thì thấy ngay bằng mắt (một tiêu đề trống là một tiêu đề trống).
 * ═══════════════════════════════════════════════════════════════════════════ */

const laBanGhi = (x: unknown): x is Record<string, unknown> =>
  typeof x === "object" && x !== null && !Array.isArray(x);

const LOAI_KET_QUA: readonly string[] = ["answer", "partial_coverage", "abstain", "out_of_scope"];

export function laTraCuuKetQua(x: unknown): x is TraCuuKetQua {
  return (
    laBanGhi(x) &&
    typeof x["result_type"] === "string" &&
    LOAI_KET_QUA.includes(x["result_type"]) &&
    Array.isArray(x["citations"]) &&
    Array.isArray(x["warnings"]) &&
    typeof x["trace_id"] === "string"
  );
}

export function laVanBanProvisions(x: unknown): x is VanBanProvisions {
  return laBanGhi(x) && typeof x["doc_id"] === "string" && Array.isArray(x["provisions"]);
}

export function laVanBanMucLuc(x: unknown): x is VanBanMucLuc {
  return laBanGhi(x) && typeof x["doc_id"] === "string" && Array.isArray(x["muc_luc"]);
}

export function laVanBanHieuLuc(x: unknown): x is VanBanHieuLuc {
  const vb = laBanGhi(x) ? x["van_ban"] : null;
  return (
    laBanGhi(x) &&
    laBanGhi(vb) &&
    typeof vb["verdict"] === "string" &&
    Array.isArray(x["dieu_khoan"])
  );
}

export function laVanBanLienQuan(x: unknown): x is VanBanLienQuan {
  return laBanGhi(x) && Array.isArray(x["nhom"]) && laBanGhi(x["dan_chieu_noi_bo"]);
}

export function laTimKiem(x: unknown): x is TimKiem {
  return (
    laBanGhi(x) &&
    Array.isArray(x["ket_qua"]) &&
    typeof x["tong_dieu_khoan"] === "number" &&
    typeof x["tong_van_ban"] === "number"
  );
}

export function laBoLoc(x: unknown): x is BoLoc {
  return (
    laBanGhi(x) &&
    Array.isArray(x["loai_van_ban"]) &&
    Array.isArray(x["co_quan_ban_hanh"]) &&
    Array.isArray(x["sap_xep"])
  );
}

export function laTimTrongVanBan(x: unknown): x is TimTrongVanBan {
  return laBanGhi(x) && Array.isArray(x["ket_qua"]) && typeof x["tong"] === "number";
}

export function laMau(x: unknown): x is Mau {
  return laBanGhi(x) && Array.isArray(x["facts"]);
}

export function laSoanThaoKetQua(x: unknown): x is SoanThaoKetQua {
  const bc = laBanGhi(x) ? x["audit_report"] : null;
  return (
    laBanGhi(x) &&
    typeof x["document"] === "string" &&
    laBanGhi(bc) &&
    Array.isArray(bc["findings"])
  );
}

export function laHanMuc(x: unknown): x is HanMuc {
  return laBanGhi(x) && typeof x["ap_dung"] === "boolean";
}

export function laPhamVi(x: unknown): x is PhamVi {
  const sau = laBanGhi(x) ? x["sau"] : null;
  const nong = laBanGhi(x) ? x["nong"] : null;
  return laBanGhi(sau) && laBanGhi(nong) && Array.isArray(sau["van_ban"]);
}
