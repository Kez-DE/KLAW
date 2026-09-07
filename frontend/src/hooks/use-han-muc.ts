import { useCallback, useEffect } from "react";
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
  return { hanMuc: g.ketQua, dangTai: g.dangChay, loi: g.loi, taiLai };
}
