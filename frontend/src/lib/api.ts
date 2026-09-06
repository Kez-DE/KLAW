/**
 * Tầng vận chuyển KLAW ↔ FE. Chỗ DUY NHẤT trong ứng dụng gọi `fetch`.
 *
 * Bốn việc, và cả bốn đều phải nằm ở một chỗ để không màn hình nào tự nghĩ ra
 * cách làm riêng:
 *
 * 1. **Hạn giờ THẬT.** Pha 5 đã có `AbortController` (nút huỷ là huỷ thật)
 *    nhưng chưa có hạn giờ, vì hạn giờ thuộc tầng này và tầng này chưa tồn
 *    tại. Nay dùng `AbortSignal.timeout` + `AbortSignal.any` — cơ chế gốc của
 *    trình duyệt, gắn thẳng vào `signal` của `fetch`. Không có bộ đếm giờ nào
 *    chạy song song với request rồi chỉ đổi state: một hạn giờ không huỷ được
 *    request là một hạn giờ giả.
 * 2. **Phân loại lỗi.** Mười nhánh, không phải một. `TimeoutError` và
 *    `AbortError` là hai DOMException KHÁC NHAU, nên hết giờ và người dùng bấm
 *    huỷ không bao giờ bị trộn làm một.
 * 3. **Kiểm hình dạng.** Mọi lời gọi bắt buộc truyền một type guard. Đó là
 *    cách duy nhất để `invalid_response` là một nhánh thật chứ không phải một
 *    dòng chú thích: 2xx kèm body sai hình dạng bị chặn ở đây, thay vì chảy
 *    xuống giao diện thành một câu trả lời rỗng trông như câu trả lời thật.
 * 4. **Danh tính.** Bearer của Supabase khi có; Supabase chưa cấu hình thì
 *    KHÔNG có header, và cổng bảo vệ phía máy chủ trả 401 thật. Không bịa
 *    token, không đoán rằng người dùng đã đăng nhập.
 */

import { supabase } from "@/integrations/supabase/client";
import type { ApiError, ApiResult } from "./klaw";

/**
 * Gốc API. Không đặt biến môi trường thì trỏ vào uvicorn chạy máy nhà — đúng
 * cấu hình phát triển, và sai rõ ràng (mọi lời gọi thất bại với `network`) khi
 * đem lên máy khác, thay vì sai âm thầm.
 */
export function apiGoc(): string {
  const tuMoiTruong: unknown = import.meta.env["VITE_API_GOC"];
  return typeof tuMoiTruong === "string" && tuMoiTruong !== ""
    ? tuMoiTruong.replace(/\/+$/, "")
    : "http://localhost:8000/api/v1";
}

/**
 * Endpoint đọc thuần. Đo được: `/bo-loc` ~30ms, `/tim-kiem` 118ms, ô lọc mục
 * lục 9,2ms. 15 giây không phải ngưỡng "chậm" mà là ngưỡng
 * "đường truyền đã chết" — dưới mức đó thì thà chờ còn hơn báo lỗi sai.
 */
export const HAN_GIO_DOC = 15_000;

/**
 * Đường tốn LLM (`/tra-cuu`, `/tra-cuu/luong`, `/soan-thao`, `/soat`).
 *
 * p95 ĐO ĐƯỢC là 50.289ms trên 204 dòng `traces`. Đặt hạn giờ ở 60s — con số
 * dự kiến ở pha 5 — sẽ cắt đúng cái đuôi 5% đó. Và vì graph chạy trong task
 * riêng phía máy chủ (huỷ vẫn bị tính tiền, cố ý), mỗi lần cắt nhầm là một lượt
 * ĐÃ TRẢ TIỀN bị vứt đi kèm một thông báo lỗi sai. 120 giây là gấp đôi p95:
 * đủ rộng để không cắt nhầm lượt thật, đủ hẹp để một stream chết không treo
 * giao diện mãi mãi.
 */
export const HAN_GIO_TRA_CUU = 120_000;

interface TuyChonGoi {
  /** Tín hiệu huỷ của nơi gọi (nút Huỷ, tháo component). */
  signal?: AbortSignal;
  hanGioMs?: number;
  method?: "GET" | "POST";
  body?: unknown;
}

const LOI_HINH_DANG =
  "Máy chủ trả về dữ liệu không đúng hình dạng đã thoả thuận nên không hiển thị được.";

async function tieuDeXacThuc(): Promise<Record<string, string>> {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    return token === undefined || token === "" ? {} : { Authorization: `Bearer ${token}` };
  } catch {
    // Supabase chưa cấu hình. Đọc thuần vẫn chạy (5 endpoint không có cổng);
    // đường tốn LLM sẽ nhận 401 THẬT nếu deployment bật xác thực.
    return {};
  }
}

/**
 * `TimeoutError` (hết giờ) và `AbortError` (người dùng huỷ) là hai
 * DOMException khác nhau, và giao diện đối xử với chúng ngược nhau: một cái
 * hiện lỗi kèm nút thử lại, cái kia im lặng đưa màn hình về trạng thái nghỉ.
 */
function loiTruocKhiCoPhanHoi(loi: unknown): ApiError {
  const ten = loi instanceof Error ? loi.name : "";
  if (ten === "TimeoutError") {
    return {
      kind: "timeout",
      message: "Máy chủ KLAW không trả lời trong thời gian chờ, nên lượt này đã dừng.",
    };
  }
  if (ten === "AbortError") {
    return { kind: "aborted", message: "Lượt gọi đã dừng theo yêu cầu của bạn." };
  }
  return {
    kind: "network",
    message: "Không kết nối được tới máy chủ KLAW.",
    detail: loi,
  };
}

/**
 * Đọc `detail` của FastAPI. Hai hình dạng, cố ý phân biệt:
 *
 * - **chuỗi** — câu do backend viết cho người đọc. `/tim-kiem` trả 422 kèm
 *   NGUYÊN danh sách giá trị lọc thật trong CSDL; nuốt câu đó rồi hiện "không
 *   có kết quả" là biến một lỗi cấu hình thành một khẳng định sai về pháp luật.
 * - **mảng** — lỗi kiểm của pydantic, ngôn ngữ máy. Không ném nguyên vào mặt
 *   người dùng; giữ trong `detail` để gỡ lỗi.
 */
async function docDetail(phanHoi: Response): Promise<{ cau: string | null; tho: unknown }> {
  let than: unknown = null;
  try {
    than = await phanHoi.json();
  } catch {
    return { cau: null, tho: null };
  }
  if (typeof than === "object" && than !== null && !Array.isArray(than)) {
    const detail = (than as Record<string, unknown>)["detail"];
    if (typeof detail === "string" && detail !== "") return { cau: detail, tho: than };
  }
  return { cau: null, tho: than };
}

function loiTheoStatus(status: number, cau: string | null, tho: unknown): ApiError {
  const chung = (kind: ApiError["kind"], macDinh: string): ApiError => ({
    kind,
    status,
    message: cau ?? macDinh,
    detail: tho,
  });

  if (status === 401 || status === 403) {
    return chung("unauthorized", "Máy chủ KLAW từ chối yêu cầu vì thiếu quyền truy cập.");
  }
  if (status === 404) return chung("not_found", "Không tìm thấy trong kho văn bản của KLAW.");
  if (status === 429) {
    return chung("rate_limited", "Đã vượt giới hạn số lượt gọi cho phép.");
  }
  if (status === 501) {
    return chung("not_implemented", "Chức năng này chưa được dựng trong hệ thống.");
  }
  if (status >= 500) {
    // KHÔNG dùng `cau` cho 5xx: `detail` ở dải này mang tên lớp ngoại lệ
    // ("tra cứu thất bại: TransportError") — thông tin gỡ lỗi, không phải câu
    // nói được với người dùng.
    return {
      kind: "server_error",
      status,
      message: "Máy chủ KLAW gặp lỗi khi xử lý.",
      detail: tho,
    };
  }
  return chung("invalid_request", "Yêu cầu gửi lên máy chủ KLAW chưa hợp lệ.");
}

/**
 * Một lượt gọi JSON.
 *
 * `kiem` là BẮT BUỘC, không có mặc định: một lời gọi không kiểm hình dạng thì
 * `invalid_response` không bao giờ xảy ra được, và cái nhánh đó tồn tại chính
 * vì hỏng-âm-thầm là chế độ hỏng tệ nhất của một sản phẩm pháp luật.
 */
export async function goi<T>(
  duongDan: string,
  kiem: (x: unknown) => x is T,
  tuyChon: TuyChonGoi = {},
): Promise<ApiResult<T>> {
  const { signal, hanGioMs = HAN_GIO_DOC, method = "GET", body } = tuyChon;
  const hetGio = AbortSignal.timeout(hanGioMs);
  const tinHieu = signal === undefined ? hetGio : AbortSignal.any([signal, hetGio]);

  let phanHoi: Response;
  try {
    phanHoi = await fetch(`${apiGoc()}${duongDan}`, {
      method,
      signal: tinHieu,
      headers: {
        ...(await tieuDeXacThuc()),
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (loi) {
    return { ok: false, error: loiTruocKhiCoPhanHoi(loi) };
  }

  if (!phanHoi.ok) {
    const { cau, tho } = await docDetail(phanHoi);
    return { ok: false, error: loiTheoStatus(phanHoi.status, cau, tho) };
  }

  let than: unknown;
  try {
    than = await phanHoi.json();
  } catch (loi) {
    return {
      ok: false,
      error: {
        kind: "invalid_response",
        message: LOI_HINH_DANG,
        status: phanHoi.status,
        detail: loi,
      },
    };
  }

  if (!kiem(than)) {
    return {
      ok: false,
      error: {
        kind: "invalid_response",
        message: LOI_HINH_DANG,
        status: phanHoi.status,
        detail: than,
      },
    };
  }
  return { ok: true, data: than };
}

/** Dựng query string, bỏ qua giá trị rỗng. Tham số lặp lại được (`loai`, `co_quan`). */
export function thamSo(cap: [string, string | number | undefined | null][]): string {
  const ts = new URLSearchParams();
  for (const [khoa, gia] of cap) {
    if (gia === undefined || gia === null || gia === "") continue;
    ts.append(khoa, String(gia));
  }
  const chuoi = ts.toString();
  return chuoi === "" ? "" : `?${chuoi}`;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * POST /tra-cuu/luong — SSE
 *
 * `fetch` + `ReadableStream`, KHÔNG `EventSource`: `EventSource` chỉ gửi được
 * GET và không đặt được header, nên nó không mang nổi `Authorization: Bearer`
 * mà cổng bảo vệ yêu cầu. Cũng không thêm thư viện — một bộ tách khung SSE là
 * mười lăm dòng, và `@microsoft/fetch-event-source` sẽ là một phụ thuộc mới
 * cho đúng mười lăm dòng đó.
 *
 * Máy chủ stream BƯỚC, không stream token: văn xuôi chỉ sinh ở node CUỐI, nên
 * stream token cho đúng một trải nghiệm là im lặng ~50 giây rồi chảy chữ.
 * Khoảng lặng dài nhất ĐO ĐƯỢC nằm ở `tier2`: **9,1 giây**. Giao diện phải
 * chịu được khoảng đó mà không trông như treo — đó là việc của `TrangThaiCho`,
 * còn việc của tầng này là không tự ý bỏ cuộc giữa khoảng lặng ấy.
 * ═══════════════════════════════════════════════════════════════════════════ */

import {
  chuanHoaBang,
  chuanHoaDocuments,
  laTraCuuKetQua,
  type LuotTruoc,
  type SuKienBatDau,
  type SuKienBuoc,
  type TraCuuKetQua,
} from "./klaw";
import { catCacKhung } from "./sse-khung";

export interface YeuCauTraCuu {
  query: string;
  /** ISO "2026-09-01". Sai định dạng → 422 từ pydantic, không nuốt. */
  as_of_date?: string;
  config_name?: string;
  /**
   * Tối đa `TOI_DA_LUOT_LICH_SU` lượt gần nhất, mới nhất SAU CÙNG. Quá trần là
   * **422**, không truncate — nên nơi gọi phải tự cắt (`dungLichSu`).
   *
   * Vắng mặt hoặc rỗng ⇒ máy chủ KHÔNG chạy `giai_nghia`, tức lượt đầu không
   * tốn thêm một token nào.
   */
  lich_su?: LuotTruoc[];
}

export interface XuLyLuong {
  /** Danh sách bước THẬT do máy chủ khai, kèm `trace_id`. */
  onBatDau?: (su: SuKienBatDau) => void;
  /** Một bước đã chạy xong ở máy chủ — không phải ước lượng theo thời gian. */
  onBuoc?: (su: SuKienBuoc) => void;
}

const laBanGhiTho = (x: unknown): x is Record<string, unknown> =>
  typeof x === "object" && x !== null && !Array.isArray(x);

/**
 * Chạy một lượt tra cứu qua SSE.
 *
 * Hai đường lỗi, cả hai đều phải xử: 422 / 401 / 429 / 503 xảy ra TRƯỚC khi
 * stream mở thì về như một response HTTP bình thường; lỗi phát sinh SAU khi
 * stream đã mở thì tới qua `event: loi`. Bỏ đường thứ hai nghĩa là một lượt
 * hỏng giữa chừng sẽ kết thúc im lặng và màn hình chờ quay mãi.
 */
export async function traCuuLuong(
  yeuCau: YeuCauTraCuu,
  xuLy: XuLyLuong = {},
  signal?: AbortSignal,
): Promise<ApiResult<TraCuuKetQua>> {
  const hetGio = AbortSignal.timeout(HAN_GIO_TRA_CUU);
  const tinHieu = signal === undefined ? hetGio : AbortSignal.any([signal, hetGio]);

  let phanHoi: Response;
  try {
    phanHoi = await fetch(`${apiGoc()}/tra-cuu/luong`, {
      method: "POST",
      signal: tinHieu,
      headers: {
        ...(await tieuDeXacThuc()),
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(yeuCau),
    });
  } catch (loi) {
    return { ok: false, error: loiTruocKhiCoPhanHoi(loi) };
  }

  if (!phanHoi.ok) {
    const { cau, tho } = await docDetail(phanHoi);
    return { ok: false, error: loiTheoStatus(phanHoi.status, cau, tho) };
  }

  const than = phanHoi.body;
  if (than === null) {
    return {
      ok: false,
      error: { kind: "invalid_response", message: LOI_HINH_DANG, status: phanHoi.status },
    };
  }

  const doc = than.getReader();
  const giaiMa = new TextDecoder();
  let dem = "";
  let ketQua: TraCuuKetQua | null = null;
  let loiTrongLuong: ApiError | null = null;

  try {
    for (;;) {
      const { done, value } = await doc.read();
      if (done) break;
      const cat = catCacKhung(`${dem}${giaiMa.decode(value, { stream: true })}`);
      dem = cat.con;

      for (const khung of cat.khung) {
        const du = khung.duLieu;
        if (khung.ten === "bat_dau" && laBanGhiTho(du)) {
          if (typeof du["trace_id"] === "string" && Array.isArray(du["cac_buoc"])) {
            xuLy.onBatDau?.(du as unknown as SuKienBatDau);
          }
        } else if (khung.ten === "buoc" && laBanGhiTho(du)) {
          if (typeof du["buoc"] === "string") xuLy.onBuoc?.(du as unknown as SuKienBuoc);
        } else if (khung.ten === "ket_qua") {
          // FE chỉ còn gọi `/tra-cuu/luong` (không còn call site FE nào gọi
          // `/tra-cuu` không-streaming) nhưng máy chủ vẫn phục vụ cả hai
          // (`src/api/routes.py`), cùng response shape. Guard này giữ mức
          // nghiêm ngặt khớp với `laTraCuuKetQua` dùng cho `/tra-cuu`, để hai
          // endpoint phía máy chủ không lệch hình dạng dữ liệu được chấp nhận.
          //
          // `chuanHoaBang` chạy TRƯỚC guard — guard là một predicate thuần,
          // không sửa `du`, nên chuẩn hoá `bang` (thiếu khoá → `[]`, bảng lệch
          // cột → loại) phải làm ở đây, chỗ raw JSON biến thành `TraCuuKetQua`.
          const duChuanHoa = chuanHoaDocuments(chuanHoaBang(du));
          if (laTraCuuKetQua(duChuanHoa)) ketQua = duChuanHoa;
          else loiTrongLuong = { kind: "invalid_response", message: LOI_HINH_DANG, detail: du };
        } else if (khung.ten === "loi" && laBanGhiTho(du)) {
          const status = du["status"];
          const chiTiet = du["detail"];
          loiTrongLuong = loiTheoStatus(
            typeof status === "number" ? status : 500,
            typeof chiTiet === "string" ? chiTiet : null,
            du,
          );
        }
      }
    }
  } catch (loi) {
    return { ok: false, error: loiTruocKhiCoPhanHoi(loi) };
  } finally {
    doc.releaseLock();
  }

  if (loiTrongLuong !== null) return { ok: false, error: loiTrongLuong };
  if (ketQua !== null) return { ok: true, data: ketQua };
  // Stream đóng mà không có `ket_qua` lẫn `loi`: proxy cắt giữa chừng, hoặc máy
  // chủ chết. Im lặng ở đây sẽ để màn hình chờ quay mãi mãi.
  return {
    ok: false,
    error: {
      kind: "invalid_response",
      message: "Máy chủ đóng kết nối giữa chừng, chưa gửi kết quả nào.",
    },
  };
}
