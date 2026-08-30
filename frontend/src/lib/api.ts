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
  Citation,
  Finding,
  ResultType,
  SoanThaoRequest,
  SoanThaoResponse,
  SoatRequest,
  SoatResponse,
  TraCuuRequest,
  TraCuuResponse,
  VanBanAroundResponse,
  Provision,
} from '../types';

export type ApiErrorKind =
  | 'network' // fetch() tự nó thất bại — mất mạng, DNS, CORS bị chặn…
  | 'timeout' // vượt quá thời gian chờ nội bộ (xem TIMEOUT_*_MS)
  | 'aborted' // AbortSignal do caller truyền vào bị huỷ chủ động
  | 'not_implemented' // 404 trên /soan-thao hoặc /soat — Task 5 chưa xây
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

function isFinding(x: unknown): x is Finding {
  if (!isRecord(x)) return false;
  return (
    isString(x.muc_do) &&
    isString(x.rule_id) &&
    isString(x.thong_diep) &&
    isString(x.can_cu) &&
    (x.vi_tri === undefined || isString(x.vi_tri))
  );
}
function isFindingArray(x: unknown): x is Finding[] {
  return Array.isArray(x) && x.every(isFinding);
}

const RESULT_TYPES: readonly string[] = ['answer', 'partial_coverage', 'abstain', 'out_of_scope'];

function isTraCuuResponse(x: unknown): x is TraCuuResponse {
  if (!isRecord(x)) return false;
  return (
    isString(x.result_type) &&
    RESULT_TYPES.includes(x.result_type as ResultType) &&
    isStringOrNull(x.answer) &&
    isCitationArray(x.citations) &&
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
    isString(x.cap) &&
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
    isNumber(x.doc_id) &&
    isString(x.so_ky_hieu) &&
    isString(x.bo_luat) &&
    Array.isArray(x.provisions) &&
    x.provisions.every(isProvision)
  );
}

function isSoanThaoResponse(x: unknown): x is SoanThaoResponse {
  if (!isRecord(x)) return false;
  return (
    isString(x.markdown) &&
    isCitationArray(x.citations) &&
    isFindingArray(x.findings) &&
    isString(x.trace_id)
  );
}

function isSoatResponse(x: unknown): x is SoatResponse {
  if (!isRecord(x)) return false;
  return isFindingArray(x.findings) && isString(x.trace_id);
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
  docId: number,
  provisionId: number,
  signal?: AbortSignal,
): Promise<ApiResult<VanBanAroundResponse>> {
  return fetchJson<VanBanAroundResponse>(
    `/api/v1/van-ban/${docId}?around=${provisionId}`,
    { method: 'GET' },
    TIMEOUT_VAN_BAN_MS,
    isVanBanAroundResponse,
    signal,
  );
}

/** POST /api/v1/soan-thao — Task 5. 404 trước khi Task 5 xong -> "not_implemented". */
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

/** POST /api/v1/soat — Task 5. 404 trước khi Task 5 xong -> "not_implemented". */
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
