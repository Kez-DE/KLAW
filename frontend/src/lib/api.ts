/**
 * Typed fetch client cho KLAW API (fe-contract.md). Mọi hàm trả về
 * `ApiResult<T>` — không throw cho lỗi HTTP/mạng/timeout, để màn hình bắt
 * buộc phải xử lý rõ ràng cả hai nhánh thay vì quên một try/catch.
 *
 * Dev: Vite proxy "/api" -> localhost:8000 (vite.config.ts).
 * Prod: cùng origin (FastAPI mount StaticFiles tại "/").
 * Cả hai trường hợp path tương đối "/api/v1/..." đều đúng — không cần base URL.
 */
import type {
  AuditReport,
  Citation,
  FactField,
  Finding,
  MauResponse,
  MucLucItem,
  Nguon,
  ResultType,
  SoanThaoRequest,
  SoanThaoResponse,
  SoatRequest,
  SoatResponse,
  TraCuuRequest,
  TraCuuResponse,
  VanBanAroundResponse,
  VanBanMucLucResponse,
  Provision,
} from '../types';

export type ApiErrorKind =
  | 'network' // fetch() tự nó thất bại — mất mạng, DNS, CORS bị chặn…
  | 'timeout' // vượt quá thời gian chờ nội bộ (xem TIMEOUT_*_MS)
  | 'aborted' // AbortSignal do caller truyền vào bị huỷ chủ động
  | 'not_implemented' // 501: loại văn bản chưa có nội dung pháp lý; hoặc 404 trên
  //                     một route chưa được phục vụ (uvicorn cũ, chưa --reload)
  | 'not_found' // 404 có nghĩa "không có" (vd. tài liệu/provision không tồn tại)
  | 'invalid_request' // 4xx khác (vd. 422 sai định dạng as_of_date)
  | 'server_error' // 5xx
  | 'invalid_response'; // 2xx nhưng body không đúng shape kỳ vọng

export interface ApiError {
  kind: ApiErrorKind;
  /** Thông điệp tiếng Việt, hiển thị được thẳng cho người dùng nếu cần. */
  message: string;
  status?: number;
  /** Body lỗi thô từ server (nếu parse được), phục vụ debug — không hiển thị thẳng. */
  detail?: unknown;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

const TIMEOUT_TRA_CUU_MS = 60_000; // "một request tra cứu mất 10–60 giây" (fe-contract.md)
const TIMEOUT_VAN_BAN_MS = 15_000; // tra bảng lazy, không gọi LLM — không cần cửa sổ rộng
// soan-thao/soat chưa tồn tại lúc viết file này; PRODUCT.md cho biết tra-cứu gọi LLM
// tối đa 5 lần, và soạn thảo gần như chắc cũng gọi LLM — giả định cùng ngưỡng 60s cho
// tới khi Task 5 xác nhận số thật. Not fabricating a number the contract doesn't give,
// just reusing the one documented ceiling we do have.
const TIMEOUT_SOAN_THAO_MS = 60_000;
const TIMEOUT_SOAT_MS = 60_000;

function isString(x: unknown): x is string {
  return typeof x === 'string';
}
function isNumber(x: unknown): x is number {
  return typeof x === 'number';
}
function isStringOrNull(x: unknown): x is string | null {
  return x === null || typeof x === 'string';
}
function isStringArray(x: unknown): x is string[] {
  return Array.isArray(x) && x.every(isString);
}
function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null;
}

function isCitation(x: unknown): x is Citation {
  if (!isRecord(x)) return false;
  return (
    isNumber(x.provision_id) &&
    isNumber(x.khop_tai_id) &&
    isString(x.doc_id) &&
    isString(x.duong_dan) &&
    isString(x.bo_luat) &&
    isString(x.so_ky_hieu) &&
    isString(x.quote) &&
    isStringOrNull(x.hieu_luc) &&
    isStringOrNull(x.tin_cay)
  );
}
function isCitationArray(x: unknown): x is Citation[] {
  return Array.isArray(x) && x.every(isCitation);
}

function isNguon(x: unknown): x is Nguon {
  if (!isRecord(x)) return false;
  return isString(x.doc_id) && isString(x.so_ky_hieu) && isString(x.bo_luat);
}
function isNguonArray(x: unknown): x is Nguon[] {
  return Array.isArray(x) && x.every(isNguon);
}

function isNumberOrNull(x: unknown): x is number | null {
  return x === null || typeof x === 'number';
}

function isFinding(x: unknown): x is Finding {
  if (!isRecord(x)) return false;
  return (
    isString(x.loai) &&
    isString(x.muc_do) &&
    isString(x.thong_diep) &&
    isStringOrNull(x.dieu_khoan_lien_quan) &&
    isStringOrNull(x.can_cu) &&
    isStringOrNull(x.rule_id) &&
    isStringOrNull(x.doc_id) &&
    isNumberOrNull(x.khop_tai_id)
  );
}

function isAuditReport(x: unknown): x is AuditReport {
  if (!isRecord(x)) return false;
  return (
    typeof x.dat === 'boolean' &&
    isNumber(x.completeness) &&
    isNumber(x.so_dieu_khoan) &&
    // `self_audit` do SERVER đặt và là số liệu đánh giá của khoá luận: thiếu
    // nó thì màn hình không phân biệt được "soát output của KLAW" với "soát
    // văn bản người dùng", nên guard bắt buộc chứ không cho mặc định.
    typeof x.self_audit === 'boolean' &&
    Array.isArray(x.findings) &&
    x.findings.every(isFinding)
  );
}

const RESULT_TYPES: readonly string[] = ['answer', 'partial_coverage', 'abstain', 'out_of_scope'];

function isTraCuuResponse(x: unknown): x is TraCuuResponse {
  if (!isRecord(x)) return false;
  return (
    isString(x.result_type) &&
    RESULT_TYPES.includes(x.result_type as ResultType) &&
    isStringOrNull(x.answer) &&
    isCitationArray(x.citations) &&
    isNguonArray(x.nguon) &&
    isStringArray(x.warnings) &&
    isStringOrNull(x.coverage_note) &&
    isString(x.trace_id) &&
    isString(x.config_name)
  );
}

function isProvision(x: unknown): x is Provision {
  if (!isRecord(x)) return false;
  return (
    isNumber(x.id) &&
    // enum, không phải string bất kỳ: endpoint dạng ?around= chỉ trả ba cấp
    // này (mục lục dùng response khác). Guard lỏng sẽ để 'chuong' lọt qua và
    // vi phạm chính kiểu nó đang khẳng định.
    (x.cap === 'dieu' || x.cap === 'khoan' || x.cap === 'diem') &&
    isString(x.so_hieu_cap) &&
    isString(x.duong_dan) &&
    isString(x.tieu_de) &&
    isString(x.noi_dung) &&
    typeof x.la_tam === 'boolean'
  );
}

function isVanBanAroundResponse(x: unknown): x is VanBanAroundResponse {
  if (!isRecord(x)) return false;
  return (
    isString(x.doc_id) &&
    isString(x.so_ky_hieu) &&
    isString(x.bo_luat) &&
    Array.isArray(x.provisions) &&
    x.provisions.every(isProvision)
  );
}

function isSoanThaoResponse(x: unknown): x is SoanThaoResponse {
  if (!isRecord(x)) return false;
  return (
    isString(x.document) &&
    Array.isArray(x.clauses) &&
    isAuditReport(x.audit_report) &&
    isString(x.trace_id)
  );
}

function isSoatResponse(x: unknown): x is SoatResponse {
  if (!isRecord(x)) return false;
  return isAuditReport(x.audit_report) && isString(x.trace_id);
}

function isFactField(x: unknown): x is FactField {
  if (!isRecord(x)) return false;
  return (
    isString(x.key) &&
    isString(x.nhan) &&
    isString(x.kieu) &&
    typeof x.bat_buoc === 'boolean' &&
    (x.lua_chon === null || isStringArray(x.lua_chon))
  );
}

function isMauResponse(x: unknown): x is MauResponse {
  if (!isRecord(x)) return false;
  return isString(x.loai_van_ban) && Array.isArray(x.facts) && x.facts.every(isFactField);
}

function isMucLucItem(x: unknown): x is MucLucItem {
  if (!isRecord(x)) return false;
  return (
    isNumber(x.id) &&
    // enum thật, không phải string bất kỳ: mục lục KHÔNG BAO GIỜ chứa 'dieu'
    // (đó là lý do endpoint này lazy). Guard lỏng sẽ để lọt một 'dieu' và
    // trang mục lục âm thầm biến thành trang kéo cả cây 689 Điều.
    (x.cap === 'phan' || x.cap === 'chuong' || x.cap === 'muc' || x.cap === 'tieu_muc') &&
    isString(x.so_hieu_cap) &&
    isString(x.tieu_de) &&
    isNumber(x.thu_tu)
  );
}

function isVanBanMucLucResponse(x: unknown): x is VanBanMucLucResponse {
  if (!isRecord(x)) return false;
  return (
    isString(x.doc_id) &&
    isString(x.so_ky_hieu) &&
    isString(x.bo_luat) &&
    Array.isArray(x.muc_luc) &&
    x.muc_luc.every(isMucLucItem)
  );
}

async function safeParseJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return undefined;
  }
}

/**
 * fetch có timeout + huỷ được, phân loại lỗi tường minh, và validate shape
 * body 2xx bằng type guard trước khi coi là thành công.
 *
 * @param on404 cách hiểu một 404 trên endpoint này — mặc định "not_found"
 *   (đúng nghĩa đen với /tra-cuu, /van-ban); /soan-thao và /soat truyền
 *   "not_implemented" vì 404 ở đó nghĩa là Task 5 chưa xây route.
 */
async function fetchJson<T>(
  path: string,
  init: RequestInit,
  timeoutMs: number,
  isValid: (x: unknown) => x is T,
  externalSignal?: AbortSignal,
  on404: ApiErrorKind = 'not_found',
): Promise<ApiResult<T>> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  // Không dùng AbortSignal.any — điện thoại đời cũ (một trong ba nhóm người
  // dùng chính) có thể chạy trình duyệt chưa hỗ trợ; addEventListener chạy
  // được ở bất kỳ đâu có AbortController.
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const res = await fetch(path, { ...init, signal: controller.signal });
    clearTimeout(timer);

    if (!res.ok) {
      const detail = await safeParseJson(res);
      if (res.status === 404) {
        return {
          ok: false,
          error: {
            kind: on404,
            message:
              on404 === 'not_implemented' ? 'Chức năng đang hoàn thiện.' : 'Không tìm thấy dữ liệu.',
            status: 404,
            detail,
          },
        };
      }
      // 501 KHÔNG phải lỗi máy chủ: server đang từ chối TRUNG THỰC vì loại văn
      // bản đó chưa có checklist/rule pháp lý. Gộp nó vào "server_error" sẽ
      // biến một câu trả lời đúng thành một lời than vãn sai.
      if (res.status === 501) {
        return {
          ok: false,
          error: {
            kind: 'not_implemented',
            message: 'Máy chủ từ chối: loại văn bản này chưa có danh mục nội dung và bộ quy tắc riêng.',
            status: 501,
            detail,
          },
        };
      }
      if (res.status >= 500) {
        return {
          ok: false,
          error: { kind: 'server_error', message: 'Máy chủ gặp lỗi, thử lại sau.', status: res.status, detail },
        };
      }
      return {
        ok: false,
        error: { kind: 'invalid_request', message: 'Yêu cầu không hợp lệ.', status: res.status, detail },
      };
    }

    const body = await safeParseJson(res);
    if (!isValid(body)) {
      return {
        ok: false,
        error: {
          kind: 'invalid_response',
          message: 'Phản hồi từ máy chủ không đúng định dạng.',
          status: res.status,
          detail: body,
        },
      };
    }
    return { ok: true, data: body };
  } catch (err) {
    clearTimeout(timer);
    if (err instanceof DOMException && err.name === 'AbortError') {
      return timedOut
        ? { ok: false, error: { kind: 'timeout', message: 'Quá thời gian chờ phản hồi.' } }
        : { ok: false, error: { kind: 'aborted', message: 'Yêu cầu đã bị huỷ.' } };
    }
    return { ok: false, error: { kind: 'network', message: 'Không thể kết nối máy chủ. Kiểm tra mạng.' } };
  }
}

/** POST /api/v1/tra-cuu — mất 10–60 giây, đây là hành vi bình thường. */
export async function traCuu(req: TraCuuRequest, signal?: AbortSignal): Promise<ApiResult<TraCuuResponse>> {
  if (req.query.length < 1 || req.query.length > 2000) {
    return {
      ok: false,
      error: { kind: 'invalid_request', message: 'Câu hỏi phải từ 1 đến 2000 ký tự.' },
    };
  }
  return fetchJson<TraCuuResponse>(
    '/api/v1/tra-cuu',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(req) },
    TIMEOUT_TRA_CUU_MS,
    isTraCuuResponse,
    signal,
  );
}

/**
 * GET /api/v1/van-ban/{docId}?around={provisionId} — dạng lazy duy nhất FE
 * dùng (Điều được hỏi + 2 Điều trước/sau). Endpoint có thể chưa tồn tại lúc
 * bạn gọi (agent khác đang xây song song) — 404 trả về kind "not_found",
 * hiện trạng thái tải/lỗi tử tế, KHÔNG mock dữ liệu giả.
 */
export async function layVanBanQuanhDieu(
  docId: string,
  provisionId: number,
  signal?: AbortSignal,
): Promise<ApiResult<VanBanAroundResponse>> {
  return fetchJson<VanBanAroundResponse>(
    `/api/v1/van-ban/${encodeURIComponent(docId)}?around=${provisionId}`,
    { method: 'GET' },
    TIMEOUT_VAN_BAN_MS,
    isVanBanAroundResponse,
    signal,
  );
}

/**
 * GET /api/v1/van-ban/{docId} — KHÔNG tham số: metadata + danh mục
 * Chương/Mục, không kéo nội dung Điều nào. Đây là dạng lazy bắt buộc cho một
 * văn bản như BLDS (689 Điều).
 *
 * `muc_luc` RỖNG là chuyện bình thường, không phải lỗi: 36 văn bản tầng nông
 * của corpus chỉ có metadata. Trang phải nói ra điều đó.
 */
export async function layMucLucVanBan(
  docId: string,
  signal?: AbortSignal,
): Promise<ApiResult<VanBanMucLucResponse>> {
  return fetchJson<VanBanMucLucResponse>(
    `/api/v1/van-ban/${encodeURIComponent(docId)}`,
    { method: 'GET' },
    TIMEOUT_VAN_BAN_MS,
    isVanBanMucLucResponse,
    signal,
  );
}

/**
 * GET /api/v1/van-ban/{docId}?so_dieu={soDieu} — MỘT Điều kèm Khoản/Điểm con.
 *
 * `soDieu` là CHUỖI, không phải số: số hiệu Điều trong luật Việt Nam không
 * liên tục và có dạng "27a". Ép về number sẽ mất đúng những Điều được thêm
 * sau bằng luật sửa đổi.
 */
export async function layDieu(
  docId: string,
  soDieu: string,
  signal?: AbortSignal,
): Promise<ApiResult<VanBanAroundResponse>> {
  return fetchJson<VanBanAroundResponse>(
    `/api/v1/van-ban/${encodeURIComponent(docId)}?so_dieu=${encodeURIComponent(soDieu)}`,
    { method: 'GET' },
    TIMEOUT_VAN_BAN_MS,
    isVanBanAroundResponse,
    signal,
  );
}

/**
 * GET /api/v1/van-ban/{docId}?trong_chuong={provisionId} — TIÊU ĐỀ các Điều
 * thuộc một Chương/Mục, KHÔNG kèm Khoản/Điểm.
 *
 * Đây là đường đi thật để mục lục bấm được. Trước khi endpoint này tồn tại,
 * `?around=<id Chương>` trả 404 và không có cách nào liệt kê Điều của một
 * Chương — mục lục là một danh sách chết.
 *
 * Endpoint cố ý chỉ trả cấp Điều: Chương lớn nhất corpus có 156 Điều nhưng
 * 1.231 dòng hậu duệ. FE giữ nguyên ràng buộc đó — duyệt mục lục thì hiện tiêu
 * đề Điều, nội dung chỉ tải khi người dùng mở đúng một Điều.
 *
 * 422 (đưa nhầm id của một Điều, hay một cấp không chứa Điều) là một câu trả
 * lời có nghĩa, KHÔNG được nuốt thành "chương này rỗng" — `fetchJson` để nó
 * nổi lên thành lỗi thật.
 */
export async function layDieuTrongChuong(
  docId: string,
  provisionId: number,
  signal?: AbortSignal,
): Promise<ApiResult<VanBanAroundResponse>> {
  return fetchJson<VanBanAroundResponse>(
    `/api/v1/van-ban/${encodeURIComponent(docId)}?trong_chuong=${provisionId}`,
    { method: 'GET' },
    TIMEOUT_VAN_BAN_MS,
    isVanBanAroundResponse,
    signal,
  );
}

const TIMEOUT_MAU_MS = 10_000; // đọc YAML đã nạp sẵn, không gọi LLM

/**
 * GET /api/v1/mau/{loai} — mô tả form nhập fact, SINH TỪ `config/rules.yaml`.
 *
 * Form PHẢI dựng từ danh sách này. Hardcode danh sách trường ở FE sẽ trôi lệch
 * khỏi YAML ngay lần sửa rule đầu tiên, và không ai phát hiện ra cho tới khi
 * một rule im lặng không được kiểm.
 *
 * `facts: []` cho `noi_quy`/`quyet_dinh_ky_luat` là câu trả lời THẬT (hai loại
 * đó chưa có checklist), không phải lỗi tải.
 */
export async function layMau(loai: string, signal?: AbortSignal): Promise<ApiResult<MauResponse>> {
  return fetchJson<MauResponse>(
    `/api/v1/mau/${encodeURIComponent(loai)}`,
    { method: 'GET' },
    TIMEOUT_MAU_MS,
    isMauResponse,
    signal,
    'not_implemented',
  );
}

/**
 * POST /api/v1/soan-thao — gọi LLM, chờ lâu là bình thường.
 *
 * 501 với `noi_quy`/`quyet_dinh_ky_luat`: hai loại đó chưa có nội dung pháp
 * lý. Hiện đúng câu từ chối, KHÔNG âm thầm soát bằng checklist HĐLĐ.
 */
export async function soanThao(
  req: SoanThaoRequest,
  signal?: AbortSignal,
): Promise<ApiResult<SoanThaoResponse>> {
  return fetchJson<SoanThaoResponse>(
    '/api/v1/soan-thao',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(req) },
    TIMEOUT_SOAN_THAO_MS,
    isSoanThaoResponse,
    signal,
    'not_implemented',
  );
}

/**
 * POST /api/v1/soat — soát văn bản người dùng dán vào. Bốn phép kiểm đều tra
 * bảng, không gọi LLM, nên nhanh; giữ chung ngưỡng chờ vì `extract_clauses`
 * chạy trên văn bản dài tuỳ ý.
 *
 * Cùng quy tắc 501 như `/soan-thao`.
 */
export async function soat(req: SoatRequest, signal?: AbortSignal): Promise<ApiResult<SoatResponse>> {
  return fetchJson<SoatResponse>(
    '/api/v1/soat',
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(req) },
    TIMEOUT_SOAT_MS,
    isSoatResponse,
    signal,
    'not_implemented',
  );
}

const TIMEOUT_PHAM_VI_MS = 10_000; // tra bảng đếm sẵn, không gọi LLM

/**
 * GET /api/v1/pham-vi — hợp đồng lấy từ `src/models/schemas.py` (commit
 * bf60f7b, đã chốt trong lúc trang /pham-vi đang được viết). Hai tầng, vì
 * corpus thật có hai tầng: `sau` có toàn văn (trả lời được thành `answer`),
 * `nong` chỉ có metadata (chính là thứ sinh ra `partial_coverage`) — giấu
 * tầng `nong` đi là mô tả sai sản phẩm. `on404` vẫn để "not_implemented" vì
 * uvicorn dev đang chạy KHÔNG có --reload nên chưa phục vụ route mới ngay cả
 * khi code đã có (bài học ghi trong progress.md); guard vẫn kiểm shape đầy đủ
 * phòng khi hợp đồng đổi tiếp trước khi FE này được xem lại.
 */
export interface VanBanPhamVi {
  doc_id: string;
  so_ky_hieu: string;
  bo_luat: string;
  loai_van_ban: string;
  so_dieu_khoan: number;
  tinh_trang_moj: string | null;
}

export interface TangPhamVi {
  so_van_ban: number;
  so_dieu_khoan: number;
  van_ban: VanBanPhamVi[];
}

export interface PhamViResponse {
  sau: TangPhamVi;
  nong: TangPhamVi;
}

function isVanBanPhamVi(x: unknown): x is VanBanPhamVi {
  if (!isRecord(x)) return false;
  return (
    isString(x.doc_id) &&
    isString(x.so_ky_hieu) &&
    isString(x.bo_luat) &&
    isString(x.loai_van_ban) &&
    isNumber(x.so_dieu_khoan) &&
    isStringOrNull(x.tinh_trang_moj)
  );
}

function isTangPhamVi(x: unknown): x is TangPhamVi {
  if (!isRecord(x)) return false;
  return (
    isNumber(x.so_van_ban) &&
    isNumber(x.so_dieu_khoan) &&
    Array.isArray(x.van_ban) &&
    x.van_ban.every(isVanBanPhamVi)
  );
}

function isPhamViResponse(x: unknown): x is PhamViResponse {
  if (!isRecord(x)) return false;
  return isTangPhamVi(x.sau) && isTangPhamVi(x.nong);
}

/**
 * Nhớ trong PHIÊN: `/` (mục "Phạm vi thật") và `/pham-vi` cùng hỏi endpoint
 * này, và số liệu corpus không đổi giữa hai lần bấm trong một phiên — gọi lại
 * chỉ tốn một vòng mạng để nhận đúng con số cũ.
 *
 * CHỈ nhớ lượt THÀNH CÔNG. Nhớ cả lỗi thì nút "Thử lại" của trang trở thành
 * nút giả: nó sẽ trả về đúng lỗi cũ mà không hỏi lại máy chủ lần nào.
 */
let phamViDaNho: PhamViResponse | null = null;

/** GET /api/v1/pham-vi. 404 -> "not_implemented" (trang tự hiện trạng thái trung thực). */
export async function layPhamVi(signal?: AbortSignal): Promise<ApiResult<PhamViResponse>> {
  if (phamViDaNho !== null) return { ok: true, data: phamViDaNho };
  const ketQua = await fetchJson<PhamViResponse>(
    '/api/v1/pham-vi',
    { method: 'GET' },
    TIMEOUT_PHAM_VI_MS,
    isPhamViResponse,
    signal,
    'not_implemented',
  );
  if (ketQua.ok) phamViDaNho = ketQua.data;
  return ketQua;
}
