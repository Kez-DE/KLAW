import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { ApiError, ApiResult } from './api';

/**
 * Máy trạng thái cho một lượt gọi API huỷ được. Cả ba màn hình (Tra cứu, Soạn
 * thảo, Soát) đều cần đúng bốn thứ này: đang chạy / kết quả / lỗi / huỷ thật —
 * nên nó nằm ở đây chứ không nằm trong một trang.
 *
 * Huỷ chủ động KHÔNG phải lỗi: nút huỷ đưa giao diện về trạng thái nghỉ và giữ
 * nguyên kết quả cũ, không nhá một thông báo đỏ vào mặt người vừa bấm huỷ.
 */
export interface TrangThaiGoi<T> {
  dangChay: boolean;
  ketQua: T | null;
  loi: ApiError | null;
  /** Gọi API; lượt gọi mới tự huỷ lượt cũ. */
  chay: (goi: (signal: AbortSignal) => Promise<ApiResult<T>>) => Promise<void>;
  huy: () => void;
  datLai: () => void;
}

export function useGoiApi<T>(): TrangThaiGoi<T> {
  const [dangChay, datDangChay] = useState(false);
  const [ketQua, datKetQua] = useState<T | null>(null);
  const [loi, datLoi] = useState<ApiError | null>(null);
  const dieuKhien = useRef<AbortController | null>(null);
  const daThao = useRef(false);

  useEffect(() => {
    daThao.current = false;
    return () => {
      daThao.current = true;
      dieuKhien.current?.abort();
    };
  }, []);

  const huy = useCallback(() => {
    dieuKhien.current?.abort();
  }, []);

  const chay = useCallback(async (goi: (signal: AbortSignal) => Promise<ApiResult<T>>) => {
    dieuKhien.current?.abort();
    const dieuKhienLuotNay = new AbortController();
    dieuKhien.current = dieuKhienLuotNay;
    datDangChay(true);
    datLoi(null);

    const ketThuc = await goi(dieuKhienLuotNay.signal);

    // Đã tháo component, hoặc đã có lượt gọi mới thay thế: bỏ kết quả này đi.
    if (daThao.current || dieuKhien.current !== dieuKhienLuotNay) return;

    dieuKhien.current = null;
    datDangChay(false);
    if (ketThuc.ok) {
      datKetQua(ketThuc.data);
      return;
    }
    if (ketThuc.error.kind !== 'aborted') datLoi(ketThuc.error);
  }, []);

  const datLai = useCallback(() => {
    dieuKhien.current?.abort();
    dieuKhien.current = null;
    datDangChay(false);
    datKetQua(null);
    datLoi(null);
  }, []);

  return { dangChay, ketQua, loi, chay, huy, datLai };
}

/**
 * Điểm gãy theo NỘI DUNG, không theo tên thiết bị: hai cột chỉ bật khi còn đủ
 * chỗ cho 68 ký tự ở mặt đọc VÀ một khung phim đọc được cạnh nó (DESIGN.md).
 * 68rem ≈ mặt đọc 34rem + khung rọi sáng 30rem + khoảng thở.
 */
const TRUY_VAN_HAI_COT = '(min-width: 68rem)';

function dangKyHaiCot(doiY: () => void): () => void {
  const truyVan = window.matchMedia(TRUY_VAN_HAI_COT);
  truyVan.addEventListener('change', doiY);
  return () => truyVan.removeEventListener('change', doiY);
}

function docHaiCot(): boolean {
  return window.matchMedia(TRUY_VAN_HAI_COT).matches;
}

/** true khi đọc được câu trả lời và nguyên văn CÙNG LÚC (bố cục hai cột). */
export function useHaiCot(): boolean {
  return useSyncExternalStore(dangKyHaiCot, docHaiCot);
}
