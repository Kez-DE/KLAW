/**
 * Khuôn gốc ở giao diện (quyết định 2026-09-26, kế hoạch
 * `khuon-goc-dien-tai-cho.md`): nhãn, vị trí và thứ tự của chỗ trống điền tại
 * chỗ trên trang, tên tệp tải về, đường dẫn và câu lỗi của khung trang.
 *
 * Chỉ `import type`: chạy được bằng `node` trần, nên `scripts/kiem-khuon-goc.ts`
 * kiểm được mà không cần dựng ứng dụng. Lời gọi mạng ở `api.ts`.
 */
import type { ApiError, ChoTrongKhuon, KhuonBanThao } from "./klaw";

/** Khoá của một chỗ trống — `(don_vi, so)` là địa chỉ máy chủ nhận. */
export const khoaO = (o: Pick<ChoTrongKhuon, "don_vi" | "so">) => `${o.don_vi}.${o.so}`;

/** Nhãn hiển thị: bỏ dấu hai chấm cuối; không có nhãn thì "chỗ trống" — KHÔNG
 *  bịa một mã như "Ô 9.0" mà người dùng không đọc ra được gì. */
export function nhanO(o: Pick<ChoTrongKhuon, "nhan">): string {
  return o.nhan.trim().replace(/:+$/, "").trim() || "chỗ trống";
}

/** Giá trị đang điền, như người dùng đọc: ô `tab` lưu kèm một dấu cách đầu. */
export const giaTriHienThi = (o: Pick<ChoTrongKhuon, "gia_tri">) => (o.gia_tri ?? "").trim();

/** Tên đọc lên của nút phủ một chỗ trống: việc sẽ làm, tên chỗ, và giá trị
 *  đang có — người dùng trình đọc màn hình không đọc được chữ trên ảnh trang.
 *  `o.gia_tri` = giá trị ĐÃ LƯU của bản thảo; `choLuu` = chữ đã gõ mà chưa lưu
 *  xong (`nhapODien`), `dangLuu` = lượt lưu của nó đang chờ máy chủ. Gõ lại đúng
 *  giá trị đã lưu thì không phải một thay đổi (cùng luật `oDaDoi`). */
export function nhanNutDien(
  o: Pick<ChoTrongKhuon, "nhan" | "gia_tri">,
  choLuu?: string,
  dangLuu = false,
): string {
  const gt = giaTriHienThi(o);
  const moi = choLuu?.trim();
  const duoi =
    moi !== undefined && moi !== gt
      ? dangLuu
        ? moi === ""
          ? " — đang lưu: để trống"
          : ` — đang lưu “${moi}”`
        : moi === ""
          ? " — chưa lưu, sẽ để trống"
          : ` — chưa lưu “${moi}”`
      : gt === ""
        ? " — còn trống"
        : ` — đang là “${gt}”`;
  return `Điền: ${nhanO(o)}${duoi}`;
}

/**
 * Nghỉ bao lâu sau lần lưu một chỗ trống cuối cùng thì mới dựng lại ảnh trang.
 * Mỗi lần lưu là một phiên bản, còn một lượt dựng giữ suất LibreOffice của CẢ
 * tài khoản 1,5–3 giây (lượt thứ hai cùng lúc là 503): điền liền tay năm chỗ
 * chỉ dựng MỘT lần, lúc người dùng dừng tay. Trong lúc chờ, chữ vừa lưu hiện đè
 * lên chỗ trống của ảnh cũ.
 */
export const NGHI_DUNG_TRANG_MS = 1200;

/** Một phần tử `gia_tri` của `PATCH /ban-thao/{id}/o-dien`. */
export interface ODienGui {
  don_vi: number;
  cho_trong: number;
  gia_tri: string;
}

/**
 * Các ô có chữ đã gõ KHÁC giá trị đã lưu của phiên bản đang có, theo thứ tự đọc
 * — chữ trên trang mà tệp tải về chưa có (lượt lưu bị từ chối, hay còn đang
 * gõ). `nhap` chỉ giữ ô người dùng đã chạm (khoá `khoaO`).
 *
 * So SAU khi cắt khoảng trắng hai đầu, vì máy chủ cắt y hệt (`chuan_hoa_dien`):
 * gõ lại đúng giá trị cũ không phải một thay đổi. Giá trị trả ra vẫn NGUYÊN chữ
 * người dùng gõ — chuẩn hoá là việc của máy chủ. `""` gỡ ô.
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
 * thì trên bản lùi về nó thành "đổi", và lần lưu kế áp lại chữ của chính bản
 * người dùng vừa bỏ. Ô đổi thật là chữ người dùng gõ, còn hiện trên trang:
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

/** Lưu xong: bỏ ô đã gửi ĐÚNG chữ đó. Ô người dùng gõ lại trong lúc lưu (chữ
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

/**
 * Hộp của một chỗ trống (pt, gốc trên-trái của trang) → vị trí trên ảnh trang,
 * theo PHẦN TRĂM khổ trang. Ảnh vẽ đúng tỉ lệ `kho`, nên phần trăm của khung
 * bọc ảnh LÀ `pt × (bề rộng ảnh đang vẽ / kho[0])` px ở mọi mức thu phóng và
 * mọi bề rộng — CSS tự tính lại, không đo DOM, không `ResizeObserver`.
 *
 * `coChu`: cỡ chữ ô nhập theo đơn vị `cqw` (phần trăm bề rộng trang): 80% chiều
 * cao hộp, cỡ chữ gần đúng của dòng chữ quanh chỗ trống.
 */
export function viTriO(
  hop: readonly [number, number, number, number],
  kho: readonly [number, number],
): { trai: number; tren: number; rong: number; cao: number; coChu: number } {
  const [x0, y0, x1, y1] = hop;
  const [w, h] = kho;
  return {
    trai: (x0 * 100) / w,
    tren: (y0 * 100) / h,
    rong: ((x1 - x0) * 100) / w,
    cao: ((y1 - y0) * 100) / h,
    coChu: ((y1 - y0) * 80) / w,
  };
}

/** Khoá của chỗ trống kế tiếp (`huong` 1) hay trước đó (-1) theo thứ tự đọc
 *  của `ds`; `null` ở hai đầu hay khi `khoa` không có trong `ds`. */
export function oKeTiep(
  ds: readonly Pick<ChoTrongKhuon, "don_vi" | "so">[],
  khoa: string,
  huong: 1 | -1,
): string | null {
  const i = ds.findIndex((o) => khoaO(o) === khoa);
  const ke = i < 0 ? undefined : ds[i + huong];
  return ke === undefined ? null : khoaO(ke);
}

/** Dòng phụ của thẻ bản thảo khuôn gốc trong chat: đếm chỗ ĐÃ điền (giá trị
 *  không rỗng), không đếm "dữ kiện" hay "mục" — hai thứ đó không có trên một
 *  biểu mẫu tải lên. */
export function phuDeKhuon(k: Pick<KhuonBanThao, "so_trang" | "cho_trong">): string {
  const da = k.cho_trong.filter((o) => giaTriHienThi(o) !== "").length;
  return `Biểu mẫu · ${k.so_trang} trang · đã điền ${da} chỗ`;
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
