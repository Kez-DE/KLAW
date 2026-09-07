import { useCallback, useEffect, useMemo } from "react";
import { goi } from "@/lib/api";
import { laHanMuc, type ApiError, type HanMuc } from "@/lib/klaw";
import { useGoiApi } from "./use-goi-api";

export interface TrangThaiHanMuc {
  hanMuc: HanMuc | null;
  dangTai: boolean;
  loi: ApiError | null;
  taiLai: () => void;
}

/** `/han-muc` cho cả tài khoản và khách (`api.ts` tự gửi bearer hoặc `X-Khach-Id`). */
export function useHanMuc(kichHoat: boolean): TrangThaiHanMuc {
  const g = useGoiApi<HanMuc>();
  const { chay } = g;
  const taiLai = useCallback(() => {
    void chay((signal) => goi("/han-muc", laHanMuc, { signal }));
  }, [chay]);
  useEffect(() => {
    if (kichHoat) taiLai();
  }, [kichHoat, taiLai]);
  // Nhớ theo giá trị thật: `useGoiApi` trả một object mới mỗi lần dựng, và
  // `TaiKhoanProvider` gói trạng thái này trong `useMemo` — không nhớ ở đây thì
  // memo của provider không bao giờ giữ được, và cả cây dựng lại mỗi lượt.
  return useMemo(
    () => ({ hanMuc: g.ketQua, dangTai: g.dangChay, loi: g.loi, taiLai }),
    [g.ketQua, g.dangChay, g.loi, taiLai],
  );
}
