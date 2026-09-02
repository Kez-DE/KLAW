import { useEffect, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "@/integrations/supabase/client";
import { ghiNhanNguoiDung } from "@/lib/xac-thuc";

/**
 * Điểm duy nhất trong FE chạm tới Supabase client, nên cũng là chỗ duy nhất
 * cần chịu được việc thiếu cấu hình.
 *
 * Trước đây thiếu biến môi trường Supabase là một throw không ai bắt trong lúc
 * render AppNav, và AppNav nằm trong AppShell — nên toàn bộ /huong-dan,
 * /tra-cuu, /soan-thao và /dung-thu rơi xuống trang lỗi cấp gốc. Một cấu hình
 * chưa điền không được phép hạ cả sản phẩm; nó chỉ được phép làm mất đăng nhập.
 *
 * Lỗi KHÔNG bị nuốt: `chuaCauHinh` đi ra ngoài để giao diện nói rõ với người
 * dùng, thay vì đẩy một dòng stack vào console trình duyệt mà không ai đọc.
 */
export function useAuth() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [chuaCauHinh, setChuaCauHinh] = useState(false);

  useEffect(() => {
    let huy: (() => void) | undefined;
    try {
      const { data } = supabase.auth.onAuthStateChange((e, s) => {
        setSession(s);
        setLoading(false);
        // Đường DUY NHẤT ghi nhận người dùng sau OAuth: `signInWithOAuth`
        // chuyển hướng cả trang nên handler bấm nút không chạy tiếp được, và
        // phiên chỉ xuất hiện ở đây khi browser quay về. Thiếu dòng này thì
        // đăng nhập Google thành công mà hạn mức theo-người không bao giờ áp,
        // im lặng hoàn toàn.
        //
        // Luồng mật khẩu VẪN tự gọi và `await` (xem `xac-thuc.ts`) để hạn mức
        // được ghi TRƯỚC khi điều hướng; gọi hai lần ở đó là vô hại vì
        // `POST /nguoi-dung` idempotent. Thà gọi thừa một lượt còn hơn để một
        // đường đăng nhập không được đếm.
        if (e === "SIGNED_IN" && s !== null) void ghiNhanNguoiDung().catch(() => {});
      });
      huy = () => data.subscription.unsubscribe();
      void supabase.auth.getSession().then(({ data: d }) => {
        setSession(d.session);
        setLoading(false);
      });
    } catch {
      setChuaCauHinh(true);
      setLoading(false);
    }
    return () => huy?.();
  }, []);

  const user: User | null = session?.user ?? null;

  return {
    session,
    user,
    loading,
    /** Thiếu VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY. */
    chuaCauHinh,
    signOut: async () => {
      try {
        await supabase.auth.signOut();
      } catch {
        setChuaCauHinh(true);
      }
      setSession(null);
    },
  };
}
