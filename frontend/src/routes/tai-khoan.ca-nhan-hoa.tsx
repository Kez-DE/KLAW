import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { BrassButton, Field, PasswordField } from "@/components/auth/AuthUI";
import { TheBoNho } from "@/components/tai-khoan/TheBoNho";
import { useTaiKhoan } from "@/contexts/tai-khoan";
import { supabase } from "@/integrations/supabase/client";

export const Route = createFileRoute("/tai-khoan/ca-nhan-hoa")({
  component: CaNhanHoaPage,
  head: () => ({ meta: [{ title: "Cá nhân hoá — KLAW" }] }),
});

const DO_DAI_TEN_TOI_DA = 60;
const DO_DAI_MK_TOI_THIEU = 8;

/**
 * Sau khi `updateUser` thành công, Supabase phát `USER_UPDATED` qua
 * `onAuthStateChange` với phiên MỚI — `useAuth` (hook gốc của `useTaiKhoan`)
 * đã lắng nghe sự kiện đó nên `user` ở khắp ứng dụng (kể cả thẻ tài khoản)
 * tự cập nhật, không cần refetch tay ở đây.
 */
function CaNhanHoaPage() {
  const { user, hanMuc } = useTaiKhoan();
  const navigate = useNavigate();
  const laEmail = user?.app_metadata?.["provider"] === "email";

  const [ten, datTen] = useState(
    String(user?.user_metadata?.["ten_hien_thi"] ?? user?.user_metadata?.["ho_ten"] ?? ""),
  );
  const [dangLuuTen, datDangLuuTen] = useState(false);
  const [thongBaoTen, datThongBaoTen] = useState<string | null>(null);

  const [mk, datMk] = useState("");
  const [mk2, datMk2] = useState("");
  const [dangDoiMk, datDangDoiMk] = useState(false);
  const [thongBaoMk, datThongBaoMk] = useState<string | null>(null);

  async function luuTen(e: FormEvent) {
    e.preventDefault();
    datDangLuuTen(true);
    datThongBaoTen(null);
    const { error } = await supabase.auth.updateUser({ data: { ten_hien_thi: ten.trim() } });
    datDangLuuTen(false);
    datThongBaoTen(error ? `Tôi chưa lưu được tên: ${error.message}` : "Đã lưu tên hiển thị.");
  }

  async function doiMatKhau(e: FormEvent) {
    e.preventDefault();
    if (mk.length < DO_DAI_MK_TOI_THIEU || mk !== mk2) {
      datThongBaoMk("Mật khẩu cần ít nhất 8 ký tự và hai lần nhập giống nhau.");
      return;
    }
    datDangDoiMk(true);
    datThongBaoMk(null);
    const { error } = await supabase.auth.updateUser({ password: mk });
    datDangDoiMk(false);
    if (error && /reauth|session|expired/i.test(error.message)) {
      void navigate({ to: "/dang-nhap", search: { next: "/tai-khoan/ca-nhan-hoa" } });
      return;
    }
    if (!error) {
      datMk("");
      datMk2("");
    }
    datThongBaoMk(error ? `Tôi chưa đổi được mật khẩu: ${error.message}` : "Đã đổi mật khẩu.");
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="font-display m-0 text-[26px] font-bold text-primary">Cá nhân hoá</h1>

      <form
        onSubmit={(e) => void luuTen(e)}
        className="mt-6 space-y-3 rounded-xl border border-border bg-card p-4"
      >
        <Field
          id="ten_hien_thi"
          label="Tên hiển thị"
          value={ten}
          onChange={(e) => datTen(e.target.value)}
          maxLength={DO_DAI_TEN_TOI_DA}
        />
        <BrassButton loading={dangLuuTen} disabled={ten.trim().length < 1}>
          Lưu tên
        </BrassButton>
        {thongBaoTen !== null && (
          <p role="status" className="m-0 text-[13px] text-muted-foreground">
            {thongBaoTen}
          </p>
        )}
      </form>

      {laEmail && (
        <form
          onSubmit={(e) => void doiMatKhau(e)}
          className="mt-6 space-y-3 rounded-xl border border-border bg-card p-4"
        >
          <h2 className="font-display m-0 text-[16px] font-bold text-primary">Đổi mật khẩu</h2>
          <PasswordField
            id="mk_moi"
            label="Mật khẩu mới"
            autoComplete="new-password"
            value={mk}
            onChange={(e) => datMk(e.target.value)}
          />
          <PasswordField
            id="mk_moi_2"
            label="Nhập lại mật khẩu mới"
            autoComplete="new-password"
            value={mk2}
            onChange={(e) => datMk2(e.target.value)}
          />
          <BrassButton loading={dangDoiMk}>Đổi mật khẩu</BrassButton>
          {thongBaoMk !== null && (
            <p role="status" className="m-0 text-[13px] text-muted-foreground">
              {thongBaoMk}
            </p>
          )}
        </form>
      )}

      {hanMuc.hanMuc?.plan === "pro" && <TheBoNho />}

      <p className="mt-6 text-[13px] text-muted-foreground">Xoá tài khoản và ngôn ngữ: sắp có.</p>
    </div>
  );
}
