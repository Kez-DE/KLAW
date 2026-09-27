/**
 * Khuôn gốc ở giao diện (quyết định 2026-09-26, kế hoạch
 * `khuon-goc-dien-tai-cho.md`): nhãn và phần đổi của bảng ô điền, tên tệp tải
 * về, đường dẫn và câu lỗi của khung trang.
 *
 * Chỉ `import type`: chạy được bằng `node` trần, nên `scripts/kiem-khuon-goc.ts`
 * kiểm được mà không cần dựng ứng dụng. Lời gọi mạng ở `api.ts`.
 */
import type { ApiError, ChoTrongKhuon } from "./klaw";

/** Khoá của một ô trong bảng ô điền — `(don_vi, so)` là địa chỉ máy chủ nhận. */
export const khoaO = (o: Pick<ChoTrongKhuon, "don_vi" | "so">) => `${o.don_vi}.${o.so}`;

/** Nhãn hiển thị — CÙNG luật `ban_thao._nhan_o` phía máy chủ (dòng "Hiện thay
 *  đổi" dùng nhãn đó), để một ô mang một tên ở cả hai nơi. */
export function nhanO(o: ChoTrongKhuon): string {
  return o.nhan.trim().replace(/:+$/, "").trim() || `Ô ${o.don_vi}.${o.so}`;
}

/** Giá trị đang điền, như người dùng đọc: ô `tab` lưu kèm một dấu cách đầu. */
export const giaTriHienThi = (o: ChoTrongKhuon) => (o.gia_tri ?? "").trim();

/** Một phần tử `gia_tri` của `PATCH /ban-thao/{id}/o-dien`. */
export interface ODienGui {
  don_vi: number;
  cho_trong: number;
  gia_tri: string;
}

/**
 * Các ô ĐÃ ĐỔI so với phiên bản đang có, theo thứ tự đọc — MỘT lần lưu gửi
 * đúng chừng này. `nhap` chỉ giữ ô người dùng đã chạm (khoá `khoaO`).
 *
 * So SAU khi cắt khoảng trắng hai đầu, vì máy chủ cắt y hệt (`chuan_hoa_dien`):
 * gõ lại đúng giá trị cũ không được tốn một phiên bản của trần sửa. Giá trị gửi
 * đi vẫn NGUYÊN chữ người dùng gõ — chuẩn hoá là việc của máy chủ. `""` gỡ ô.
 */
export function oDaDoi(
  choTrong: ChoTrongKhuon[],
  nhap: Readonly<Record<string, string>>,
): ODienGui[] {
  return choTrong.flatMap((o) => {
    const moi = nhap[khoaO(o)];
    return moi !== undefined && moi.trim() !== giaTriHienThi(o)
      ? [{ don_vi: o.don_vi, cho_trong: o.so, gia_tri: moi }]
      : [];
  });
}

/**
 * Chữ đang gõ còn giữ khi LÙI khỏi phiên bản `choTrong`: chỉ ô ĐỔI THẬT so với
 * bản bị bỏ. Ô đã chạm mà không đổi (gõ lại đúng giá trị) phải rơi — giữ lại
 * thì trên bản lùi về nó thành "đổi", và một lần Lưu áp lại chữ của chính bản
 * người dùng vừa bỏ. Ô đổi thật là chữ người dùng gõ, còn hiện trên màn hình:
 * giữ, đừng bắt gõ lại.
 */
export function chiGiuThayDoi(
  choTrong: ChoTrongKhuon[],
  nhap: Readonly<Record<string, string>>,
): Record<string, string> {
  return Object.fromEntries(
    oDaDoi(choTrong, nhap).map((d) => [khoaO({ don_vi: d.don_vi, so: d.cho_trong }), d.gia_tri]),
  );
}

/** Lưu xong: bỏ ô đã gửi ĐÚNG chữ đó. Ô người dùng gõ tiếp trong lúc lưu (chữ
 *  đã khác chữ vừa gửi) còn nguyên để lưu lần sau. */
export function boDaGui(
  nhap: Readonly<Record<string, string>>,
  daGui: readonly ODienGui[],
): Record<string, string> {
  const ra = { ...nhap };
  for (const d of daGui) {
    const k = khoaO({ don_vi: d.don_vi, so: d.cho_trong });
    if (ra[k] === d.gia_tri) delete ra[k];
  }
  return ra;
}

/** Chỉ phần tên (không thư mục), không ký tự điều khiển; rỗng → `null`. */
function tenSach(ten: string): string | null {
  // eslint-disable-next-line no-control-regex -- đây đúng là bộ lọc ký tự điều khiển
  const chu = (ten.split(/[\\/]/).pop() ?? "").replace(/[\u0000-\u001f\u007f]/g, "").trim();
  return chu === "" || chu === "." || chu === ".." ? null : chu;
}

/**
 * Tên tệp trong `Content-Disposition` của `GET /ban-thao/{id}/tai-xuong`:
 * `filename*` (RFC 5987, UTF-8 — tên thật có dấu) trước, rồi `filename` (ASCII
 * dự phòng máy chủ luôn gửi kèm). `null` khi không đọc ra tên nào dùng được —
 * nơi gọi tự đặt tên.
 *
 * Tên đi thẳng vào `<a download>`, nên bỏ thư mục và ký tự điều khiển ở ĐÂY,
 * không tin rằng máy chủ đã làm.
 */
export function tenTepTuContentDisposition(dau: string | null): string | null {
  if (!dau) return null;
  const sao = /(?:^|;)\s*filename\*\s*=\s*([^;]*)/i.exec(dau)?.[1]?.trim();
  const utf8 = sao === undefined ? null : /^utf-8'[^']*'(.+)$/i.exec(sao)?.[1];
  if (utf8) {
    try {
      const ten = tenSach(decodeURIComponent(utf8));
      if (ten !== null) return ten;
    } catch {
      // Mã phần trăm hỏng: rơi về `filename`.
    }
  }
  const tron = /(?:^|;)\s*filename\s*=\s*(?:"((?:[^"\\]|\\.)*)"|([^;\s]+))/i.exec(dau);
  const ten = tron?.[1]?.replace(/\\(.)/g, "$1") ?? tron?.[2];
  return ten === undefined ? null : tenSach(ten);
}

/** Đường dẫn TÍNH TỪ GỐC API (`apiGoc()` đã chứa `/api/v1`) — cùng luật
 *  `tai-lieu.ts::DUONG_DAN`. `phien_ban` luôn TƯỜNG MINH: trang của một phiên
 *  bản không bao giờ đổi, nên trình duyệt giữ được (`private, max-age=3600`). */
export const DUONG_DAN_KHUON = {
  trangTaiLieu: (viecId: string) => `/tai-lieu/${encodeURIComponent(viecId)}/trang`,
  trangBanThao: (id: string, phienBan: number) =>
    `/ban-thao/${encodeURIComponent(id)}/trang?phien_ban=${phienBan}`,
  taiXuong: (id: string, dang: "docx" | "pdf", phienBan: number) =>
    `/ban-thao/${encodeURIComponent(id)}/tai-xuong?dang=${dang}&phien_ban=${phienBan}`,
  oDien: (id: string) => `/ban-thao/${encodeURIComponent(id)}/o-dien`,
  moBanThao: (viecId: string) => `/tai-lieu/${encodeURIComponent(viecId)}/ban-thao`,
  docLai: (viecId: string) => `/tai-lieu/${encodeURIComponent(viecId)}/doc-lai`,
} as const;

/** Mọi lượt dựng trang và tải tệp của MỘT tài khoản đi qua một suất, và cả hệ
 *  thống có ba suất LibreOffice: lượt thứ hai trong lúc lượt đầu chạy là 503. */
export const CAU_MAY_BAN =
  "Máy chủ đang bận dựng một bản khác cho tài khoản này. Chờ vài giây rồi thử lại.";

/**
 * Câu hiện trong khung trang khi tải hỏng, và có đáng thử lại không. `503`
 * (`qua_tai`) là bận — `loiTheoStatus` cố ý bỏ `detail` của dải 5xx nên câu nói
 * ở đây. `404` không tự hết: khuôn gốc đã bị xoá cùng hội thoại, hay (chỉ bản
 * thảo) phiên bản HTML. `duongDan` (`DUONG_DAN_KHUON`) cho biết khung nào: khung
 * "Bản tải lên" không có phiên bản, nên câu của nó không nhắc tới phiên bản.
 * Mọi lỗi khác giữ nguyên câu của tầng gọi API.
 */
export function loiTrang(
  loi: Pick<ApiError, "kind" | "status" | "message">,
  duongDan: string,
): {
  cau: string;
  thuLai: boolean;
} {
  if (loi.status === 503) return { cau: CAU_MAY_BAN, thuLai: true };
  if (loi.status === 404 || loi.kind === "not_found")
    return {
      cau: duongDan.startsWith("/tai-lieu/")
        ? "Không hiển thị được bản tải lên: KLAW không còn giữ tệp này."
        : "Không hiển thị được phiên bản này dưới dạng trang: KLAW không còn giữ tài liệu tải lên, hoặc phiên bản này không điền trên tài liệu đó.",
      thuLai: false,
    };
  return { cau: loi.message, thuLai: true };
}
