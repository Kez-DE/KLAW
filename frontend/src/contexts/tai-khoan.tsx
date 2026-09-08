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
import { ModalNangGoi } from "@/components/tai-khoan/ModalNangGoi";
import { useAuth } from "@/hooks/use-auth";
import { useHanMuc, type TrangThaiHanMuc } from "@/hooks/use-han-muc";
import { useHoiThoai, type TrangThaiHoiThoai } from "@/hooks/use-hoi-thoai";
import { useThongBao } from "@/hooks/use-thong-bao";
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
  /** I2: một luồng `/thong-bao/luong` cho cả phiên — hoisted lên đây vì
   *  `ChuongThongBao` dựng ở cả dải icon lẫn sheet di động cùng lúc (dải bị
   *  `hidden` bằng CSS, không unmount), nên gọi hook tại chỗ sẽ mở hai luồng. */
  thongBao: ReturnType<typeof useThongBao>;
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
  // M2: một thông báo khoá/mở tài khoản tới qua SSE thì tải lại `hanMuc` ngay,
  // vì đó là cách duy nhất một thay đổi giữa phiên (admin khoá tài khoản) tới
  // được client mà không cần người dùng tự làm mới trang.
  const thongBao = useThongBao(daDangNhap, hanMuc.taiLai);
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
      thongBao,
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
      thongBao,
      nangGoiMo,
      signOut,
      phienMoi,
      catThreadTruocKhiRoi,
    ],
  );
  return (
    <Ctx.Provider value={gia}>
      {children}
      <ModalNangGoi />
    </Ctx.Provider>
  );
}

export function useTaiKhoan(): TaiKhoan {
  const v = useContext(Ctx);
  if (v === null) throw new Error("useTaiKhoan phải nằm trong TaiKhoanProvider");
  return v;
}
