import { useEffect, useState } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "@/integrations/supabase/client";

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
      const { data } = supabase.auth.onAuthStateChange((_e, s) => {
        setSession(s);
        setLoading(false);
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
