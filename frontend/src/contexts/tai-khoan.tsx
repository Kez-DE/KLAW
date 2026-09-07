import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useNavigate } from "@tanstack/react-router";
import type { User } from "@supabase/supabase-js";
import { useAuth } from "@/hooks/use-auth";
import { useHanMuc, type TrangThaiHanMuc } from "@/hooks/use-han-muc";
import { useHoiThoai, type TrangThaiHoiThoai } from "@/hooks/use-hoi-thoai";
import { catThreadKhach } from "@/lib/khach";
import type { LuotDaXong } from "@/lib/lich-su";

/**
 * Một nguồn duy nhất cho "người dùng này là ai và còn được làm gì" (spec 2A §7).
 *
 * Trước đây mỗi trang tự gọi `useAuth` + `useHoiThoai`, nên vỏ ứng dụng và nội
 * dung có thể bất đồng ý kiến về việc đã đăng nhập hay chưa, và danh sách phiên
 * bị tải hai lần. Gom vào một provider ở gốc: vỏ, trang và modal cùng đọc một
 * trạng thái, và phiên chỉ tải một lần cho cả cây.
 */
export interface TaiKhoan {
  user: User | null;
  dangKiemPhien: boolean;
  chuaCauHinh: boolean;
  daDangNhap: boolean;
  laKhach: boolean;
  hoiThoai: TrangThaiHoiThoai;
  hanMuc: TrangThaiHanMuc;
  nangGoiMo: boolean;
  moNangGoi: () => void;
  dongNangGoi: () => void;
  signOut: () => Promise<void>;
  /** `/dung-thu` đăng ký hàm "Phiên mới" của nó; nơi khác điều hướng về `/dung-thu`. */
  datHanhDongPhienMoi: (fn: (() => void) | null) => void;
  phienMoi: () => void;
  /** `/dung-thu` đăng ký hàm trả đoạn chat khách; nút Đăng nhập/Đăng ký cất nó trước khi rời. */
  datLayThreadKhach: (fn: (() => LuotDaXong[]) | null) => void;
  catThreadTruocKhiRoi: () => void;
}

const Ctx = createContext<TaiKhoan | null>(null);

export function TaiKhoanProvider({ children }: { children: ReactNode }) {
  const { user, loading: dangKiemPhien, chuaCauHinh, signOut } = useAuth();
  const daDangNhap = !chuaCauHinh && !dangKiemPhien && user !== null;
  const laKhach = !chuaCauHinh && !dangKiemPhien && user === null;
  const hoiThoai = useHoiThoai(daDangNhap);
  const hanMuc = useHanMuc(!chuaCauHinh && !dangKiemPhien); // khách cũng có thanh đo (X-Khach-Id)
  const [nangGoiMo, datNangGoiMo] = useState(false);
  const navigate = useNavigate();
  const hanhDongPhienMoi = useRef<(() => void) | null>(null);
  const layThread = useRef<(() => LuotDaXong[]) | null>(null);

  const phienMoi = useCallback(() => {
    if (hanhDongPhienMoi.current !== null) hanhDongPhienMoi.current();
    else void navigate({ to: "/dung-thu", search: {} });
  }, [navigate]);
  const catThreadTruocKhiRoi = useCallback(() => {
    const t = layThread.current?.();
    if (t !== undefined && t.length > 0) catThreadKhach(t);
  }, []);

  const gia = useMemo<TaiKhoan>(
    () => ({
      user,
      dangKiemPhien,
      chuaCauHinh,
      daDangNhap,
      laKhach,
      hoiThoai,
      hanMuc,
      nangGoiMo,
      moNangGoi: () => datNangGoiMo(true),
      dongNangGoi: () => datNangGoiMo(false),
      signOut,
      datHanhDongPhienMoi: (fn) => {
        hanhDongPhienMoi.current = fn;
      },
      phienMoi,
      datLayThreadKhach: (fn) => {
        layThread.current = fn;
      },
      catThreadTruocKhiRoi,
    }),
    [
      user,
      dangKiemPhien,
      chuaCauHinh,
      daDangNhap,
      laKhach,
      hoiThoai,
      hanMuc,
      nangGoiMo,
      signOut,
      phienMoi,
      catThreadTruocKhiRoi,
    ],
  );
  return (
    <Ctx.Provider value={gia}>
      {children}
      {/* Task 9 gắn <ModalNangGoi /> vào ĐÚNG chỗ này: modal đọc `nangGoiMo` và
          `dongNangGoi` từ context nên phải nằm trong Provider, và nằm sau
          `children` để lớp phủ vẽ trên mọi trang. */}
    </Ctx.Provider>
  );
}

export function useTaiKhoan(): TaiKhoan {
  const v = useContext(Ctx);
  if (v === null) throw new Error("useTaiKhoan phải nằm trong TaiKhoanProvider");
  return v;
}
