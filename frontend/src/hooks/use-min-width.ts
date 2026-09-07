import { useCallback, useSyncExternalStore } from "react";

/**
 * true khi cửa sổ rộng ít nhất `rem`.
 *
 * Cùng khuôn `useHaiCot` trong `KhungDoiChieu.tsx`, nhưng ngưỡng là tham số:
 * khung đối chiếu tách cột ở 68rem, còn vỏ ứng dụng mở cột "Gần đây" ở 80rem
 * (đúng `xl` của Tailwind, nên lớp CSS và nhánh JS không lệch nhau được).
 *
 * Máy chủ không biết bề rộng cửa sổ. Đoán hẹp là đoán an toàn: bố cục hẹp
 * không bao giờ tràn ngang, còn đoán rộng thì có.
 */
export function useMinWidth(rem: number): boolean {
  const truyVan = `(min-width: ${rem}rem)`;
  const dangKy = useCallback(
    (doiY: () => void) => {
      const mq = window.matchMedia(truyVan);
      mq.addEventListener("change", doiY);
      return () => mq.removeEventListener("change", doiY);
    },
    [truyVan],
  );
  const doc = useCallback(() => window.matchMedia(truyVan).matches, [truyVan]);
  return useSyncExternalStore(dangKy, doc, () => false);
}
