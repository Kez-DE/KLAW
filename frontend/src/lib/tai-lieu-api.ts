/**
 * Gọi API `/tai-lieu` (spec 2026-09-15). Kiểu dữ liệu và quy tắc trình bày
 * nằm ở `tai-lieu.ts`, vốn không nhập gì để kiểm được bằng `node` trần.
 */
import { apiGoc, goi, tieuDeXacThuc } from "./api";
import type { ApiError, ApiErrorKind, ApiResult } from "./klaw";
import { loiTruocKhiGui, type DuKien, type TaiLieu } from "./tai-lieu";

export type { DuKien, TaiLieu } from "./tai-lieu";

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
  loai: string,
  signal?: AbortSignal,
): Promise<ApiResult<TaiLieu>> {
  const loi = loiTruocKhiGui(tep.name, tep.size);
  if (loi) return { ok: false, error: _loi(loi, "invalid_request") };

  const form = new FormData();
  form.append("tep", tep);
  form.append("hoi_thoai_id", hoiThoaiId);
  form.append("loai", loai);

  let phanHoi: Response;
  try {
    phanHoi = await fetch(`${apiGoc()}/api/v1/tai-lieu`, {
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
  return goi<TaiLieu>(`/api/v1/tai-lieu/${viecId}`, laTaiLieu, signal ? { signal } : {});
}

export function suaDuKien(duKienId: string, giaTri: string) {
  return goi<DuKien>(`/api/v1/tai-lieu/du-kien/${duKienId}`, laDuKien, {
    method: "PATCH",
    body: { gia_tri: giaTri },
  });
}

export function xoaDuKien(duKienId: string) {
  return goi<null>(`/api/v1/tai-lieu/du-kien/${duKienId}`, (x): x is null => x === null, {
    method: "DELETE",
  });
}

export function xoaHet(hoiThoaiId: string) {
  return goi<null>(`/api/v1/tai-lieu/hoi-thoai/${hoiThoaiId}`, (x): x is null => x === null, {
    method: "DELETE",
  });
}
