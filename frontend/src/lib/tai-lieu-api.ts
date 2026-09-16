/**
 * Gọi API `/tai-lieu` (spec 2026-09-15). Kiểu dữ liệu và quy tắc trình bày
 * nằm ở `tai-lieu.ts`, vốn không nhập gì để kiểm được bằng `node` trần.
 */
import { apiGoc, goi, tieuDeXacThuc } from "./api";
import type { ApiError, ApiErrorKind, ApiResult } from "./klaw";
import {
  DUONG_DAN,
  loiTruocKhiGui,
  type DonViTaiLieu,
  type DuKien,
  type TaiLieu,
} from "./tai-lieu";

export type { DonVi, DonViTaiLieu, DuKien, TaiLieu } from "./tai-lieu";

/** Lỗi phía giao diện, cùng hình dạng `ApiError` để chỗ hiển thị không phải rẽ nhánh. */
function _loi(message: string, kind: ApiErrorKind, status?: number): ApiError {
  return status === undefined ? { kind, message } : { kind, message, status };
}

function laTaiLieu(x: unknown): x is TaiLieu {
  const o = x as TaiLieu;
  return (
    !!o && typeof o.id === "string" && typeof o.trang_thai === "string" && Array.isArray(o.du_kien)
  );
}

function laDuKien(x: unknown): x is DuKien {
  const o = x as DuKien;
  return !!o && typeof o.khoa === "string" && typeof o.gia_tri === "string";
}

/** `POST /tai-lieu` — multipart, nên không đi qua `goi()` vốn chỉ gửi JSON. */
export async function taiLen(
  tep: File,
  hoiThoaiId: string,
  /** `null` = để hệ thống tự nhận ra loại văn bản từ chính tài liệu. */
  loai: string | null,
  signal?: AbortSignal,
): Promise<ApiResult<TaiLieu>> {
  const loi = loiTruocKhiGui(tep.name, tep.size);
  if (loi) return { ok: false, error: _loi(loi, "invalid_request") };

  const form = new FormData();
  form.append("tep", tep);
  form.append("hoi_thoai_id", hoiThoaiId);
  if (loai) form.append("loai", loai);

  let phanHoi: Response;
  try {
    phanHoi = await fetch(`${apiGoc()}${DUONG_DAN.taiLen()}`, {
      method: "POST",
      body: form,
      headers: await tieuDeXacThuc(),
      ...(signal ? { signal } : {}),
    });
  } catch {
    return {
      ok: false,
      error: _loi("Không gửi được tệp. Kiểm tra kết nối rồi thử lại.", "network"),
    };
  }
  const than = await phanHoi.json().catch(() => null);
  if (!phanHoi.ok || !laTaiLieu(than)) {
    const cau = (than as { detail?: string } | null)?.detail ?? "Không đọc được tệp này.";
    return {
      ok: false,
      error: _loi(cau, phanHoi.status >= 500 ? "server_error" : "invalid_request", phanHoi.status),
    };
  }
  return { ok: true, data: than };
}

export function chiTiet(viecId: string, signal?: AbortSignal) {
  return goi<TaiLieu>(DUONG_DAN.chiTiet(viecId), laTaiLieu, signal ? { signal } : {});
}

/** Kiểm đúng hai thứ mà sai đi sẽ hỏng ÂM THẦM: định danh và MẢNG đơn vị —
 *  mảng vắng render thành một khung trống đọc như "tài liệu không có gì". */
function laDonViTaiLieu(x: unknown): x is DonViTaiLieu {
  const o = x as DonViTaiLieu;
  return !!o && typeof o.id === "string" && Array.isArray(o.don_vi);
}

/**
 * Toàn bộ phần đã đọc của một tài liệu — nền của khung xem và của mọi neo.
 *
 * Tách khỏi `chiTiet()` vì hai thứ khác nhau: `chiTiet` trả DỮ KIỆN đã rút
 * (ít, đã lọc), còn đây trả NGUYÊN VĂN đã đọc (nhiều, chưa diễn giải). Một
 * lượt hỏi chỉ cần cái trước; bấm vào neo mới cần cái sau.
 */
export function donVi(viecId: string, signal?: AbortSignal) {
  return goi<DonViTaiLieu>(DUONG_DAN.donVi(viecId), laDonViTaiLieu, signal ? { signal } : {});
}

export function suaDuKien(duKienId: string, giaTri: string) {
  return goi<DuKien>(DUONG_DAN.duKien(duKienId), laDuKien, {
    method: "PATCH",
    body: { gia_tri: giaTri },
  });
}

export function xoaDuKien(duKienId: string) {
  return goi<null>(DUONG_DAN.duKien(duKienId), (x): x is null => x === null, {
    method: "DELETE",
  });
}

export function xoaHet(hoiThoaiId: string) {
  return goi<null>(DUONG_DAN.theoHoiThoai(hoiThoaiId), (x): x is null => x === null, {
    method: "DELETE",
  });
}

export interface SangSoanThao {
  loai: string;
  facts: Record<string, string>;
  con_thieu: { key: string; nhan: string }[];
  da_ghi_vao_hoi_thoai: boolean;
}

function laSangSoanThao(x: unknown): x is SangSoanThao {
  const o = x as SangSoanThao;
  return !!o && typeof o.loai === "string" && !!o.facts && Array.isArray(o.con_thieu);
}

/**
 * Đưa tập dữ kiện đã duyệt sang soạn thảo.
 *
 * `ghi = true` ghi thẳng vào trạng thái soạn thảo của cuộc hội thoại, nên lượt
 * trò chuyện kế tiếp đã biết tài liệu nói gì và chỉ còn hỏi phần thiếu. Dữ kiện
 * người dùng đã tự nhập được giữ nguyên — tài liệu bổ sung vào chỗ trống, không
 * ghi đè thứ họ tự khẳng định.
 */
export function sangSoanThao(hoiThoaiId: string, loai: string, ghi = false) {
  return goi<SangSoanThao>(DUONG_DAN.sangSoanThao(hoiThoaiId, loai, ghi), laSangSoanThao, {});
}
