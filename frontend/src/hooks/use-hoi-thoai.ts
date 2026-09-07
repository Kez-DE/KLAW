import { useCallback, useEffect, useMemo } from "react";
import { goi, laKhongThan } from "@/lib/api";
import type { ApiError, ApiResult, ChiTietPhien, DanhSachPhien, PhienTomTat } from "@/lib/klaw";
import { laChiTietPhien, laDanhSachPhien, laPhienTomTat } from "@/lib/klaw";
import { useGoiApi } from "./use-goi-api";

/**
 * Phiên hội thoại của tài khoản (spec 2026-09-07 §6). Hai máy trạng thái
 * `useGoiApi` — danh sách và chi tiết — vì chúng sống độc lập: đổi tên một
 * phiên không được xoá các lượt đang hiện, và mở một phiên không được nhấp
 * nháy cả cột. Đổi tên/xoá xong thì tải lại danh sách từ máy chủ thay vì
 * sửa tay mảng ở client: `tong_an`/thứ tự do máy chủ tính, tự tính lại là
 * chép logic ẩn theo gói sang FE.
 */
export interface TrangThaiHoiThoai {
  danhSach: DanhSachPhien | null;
  dangTai: boolean;
  loi: ApiError | null;
  taiLai: () => void;
  chiTiet: ChiTietPhien | null;
  dangTaiChiTiet: boolean;
  loiChiTiet: ApiError | null;
  taiChiTiet: (id: string) => void;
  xoaChiTiet: () => void;
  doiTen: (id: string, tieuDe: string) => Promise<ApiResult<PhienTomTat>>;
  xoa: (id: string) => Promise<ApiResult<null>>;
}

const DUONG_DAN = "/hoi-thoai";

export function useHoiThoai(daDangNhap: boolean): TrangThaiHoiThoai {
  const ds = useGoiApi<DanhSachPhien>();
  const ct = useGoiApi<ChiTietPhien>();
  const { chay: chayDs } = ds;
  const { chay: chayCt, datLai: datLaiCt } = ct;

  const taiLai = useCallback(() => {
    void chayDs((signal) => goi(`${DUONG_DAN}?limit=50`, laDanhSachPhien, { signal }));
  }, [chayDs]);

  useEffect(() => {
    if (daDangNhap) taiLai();
  }, [daDangNhap, taiLai]);

  const taiChiTiet = useCallback(
    (id: string) => {
      void chayCt((signal) =>
        goi(`${DUONG_DAN}/${encodeURIComponent(id)}`, laChiTietPhien, { signal }),
      );
    },
    [chayCt],
  );

  const doiTen = useCallback(
    async (id: string, tieuDe: string) => {
      const kq = await goi(`${DUONG_DAN}/${encodeURIComponent(id)}`, laPhienTomTat, {
        method: "PATCH",
        body: { tieu_de: tieuDe },
      });
      // 404 = phiên đã biến mất (tab khác vừa xoá): tải lại để nó rời cột, thay vì
      // để người dùng nhìn một lỗi "chưa xoá được" về một phiên không còn tồn tại.
      if (kq.ok || kq.error.status === 404) taiLai();
      return kq;
    },
    [taiLai],
  );

  const xoa = useCallback(
    async (id: string) => {
      const kq = await goi(`${DUONG_DAN}/${encodeURIComponent(id)}`, laKhongThan, {
        method: "DELETE",
      });
      if (kq.ok || kq.error.status === 404) taiLai();
      return kq;
    },
    [taiLai],
  );

  // Nhớ theo giá trị thật, cùng lý do như `use-han-muc.ts`: hai `useGoiApi` bên
  // trong trả object mới mỗi lần dựng, còn `TaiKhoanProvider` thì gói trạng thái
  // này trong `useMemo`. Chỉ là phép nhớ — không đổi một dòng logic nào.
  return useMemo(
    () => ({
      danhSach: ds.ketQua,
      dangTai: ds.dangChay,
      loi: ds.loi,
      taiLai,
      chiTiet: ct.ketQua,
      dangTaiChiTiet: ct.dangChay,
      loiChiTiet: ct.loi,
      taiChiTiet,
      xoaChiTiet: datLaiCt,
      doiTen,
      xoa,
    }),
    [
      ds.ketQua,
      ds.dangChay,
      ds.loi,
      taiLai,
      ct.ketQua,
      ct.dangChay,
      ct.loi,
      taiChiTiet,
      datLaiCt,
      doiTen,
      xoa,
    ],
  );
}
