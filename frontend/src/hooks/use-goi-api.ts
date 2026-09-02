import { useCallback, useEffect, useRef, useState } from "react";
import { goi } from "@/lib/api";
import type { ApiError, ApiResult } from "@/lib/klaw";

/**
 * Máy trạng thái cho một lượt gọi API HUỶ ĐƯỢC.
 *
 * `Klaw_FE` có **0 `AbortController`** trong toàn bộ `src/`: không nút huỷ,
 * không timeout, không cách nào dừng một lượt đã gửi. Với một lượt mất 10–60
 * giây thì "nút huỷ" vẽ ra mà chỉ ẩn giao diện đi, còn request vẫn chạy và vẫn
 * ghi kết quả đè lên màn hình sau đó, là một nút huỷ GIẢ. Hook này giữ
 * `AbortController` thật, nên `signal` đi thẳng vào `fetch` và lượt gọi thật
 * sự dừng.
 *
 * Ba hành vi được chốt ở đây, một lần, thay vì lặp lại ở từng màn hình:
 *
 * - **Lượt mới tự huỷ lượt cũ.** Không có chuyện hai câu trả lời chạy đua rồi
 *   câu cũ về sau ghi đè câu mới.
 * - **Huỷ chủ động KHÔNG phải lỗi.** Nút huỷ đưa giao diện về trạng thái nghỉ
 *   và giữ nguyên kết quả cũ, không nhá một thông báo lỗi vào mặt người vừa
 *   bấm huỷ.
 * - **Tháo component thì huỷ.** Rời trang giữa chừng không để lại một lượt gọi
 *   treo, và không set state trên một cây đã gỡ.
 *
 * Hook này CHỈ lo vòng đời: `chay` nhận vào một hàm gọi bất kỳ trả về
 * `ApiResult`. Lời gọi `fetch` thật nằm ở `lib/api.ts`, và hạn giờ đi kèm nó —
 * nên hai mối bận tâm không trộn vào nhau, và pha nối backend không phải sửa
 * một dòng nào ở đây.
 */
export interface TrangThaiGoi<T> {
  dangChay: boolean;
  ketQua: T | null;
  loi: ApiError | null;
  /** Gọi API. Lượt gọi mới tự huỷ lượt cũ. */
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
    dieuKhien.current = null;
    datDangChay(false);
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
    // Huỷ chủ động không phải lỗi — xem ghi chú đầu file.
    if (ketThuc.error.kind !== "aborted") datLoi(ketThuc.error);
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
 * Tải MỘT endpoint đọc thuần, một lần, khi màn hình dựng.
 *
 * Vỏ mỏng quanh `useGoiApi`, không phải một cơ chế thứ hai: cùng
 * `AbortController`, cùng hạn giờ, cùng cách phân loại lỗi. Có nó vì ba trang
 * thông tin (`/mien-tru`, `/du-lieu`) chỉ cần đúng hành vi này, và chép tay
 * `useEffect` + `goi` ở mỗi trang là cách một trang lặng lẽ quên `signal` rồi
 * set state trên cây đã gỡ.
 *
 * `kiem` phải là hàm ở cấp module (mọi type guard trong `lib/klaw.ts` đều
 * vậy), nếu không hiệu ứng chạy lại mỗi lần dựng.
 */
export function useTaiMot<T>(duongDan: string, kiem: (x: unknown) => x is T): TrangThaiGoi<T> {
  const trangThai = useGoiApi<T>();
  const { chay } = trangThai;
  useEffect(() => {
    void chay((signal) => goi(duongDan, kiem, { signal }));
  }, [chay, duongDan, kiem]);
  return trangThai;
}
