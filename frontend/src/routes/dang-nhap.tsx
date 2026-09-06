import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useState, type FormEvent } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { locNext, type DichQuayLai } from "@/lib/quay-lai";
import type { NhaCungCapOAuth } from "@/lib/xac-thuc";
import { dangNhap, dangNhapOAuth } from "@/lib/xac-thuc";
import {
  BrassButton,
  Divider,
  EMAIL_RE,
  ErrorBanner,
  Field,
  Fineprint,
  FacebookMark,
  GoogleMark,
  MicrosoftMark,
  MSG_EMAIL,
  MSG_PASSWORD,
  PASSWORD_RE,
  PasswordField,
  SocialButton,
  SuccessCheck,
} from "@/components/auth/AuthUI";

export const Route = createFileRoute("/dang-nhap")({
  head: () => ({
    meta: [
      { title: "Đăng nhập KLAW — Trợ lý pháp luật Việt Nam" },
      {
        name: "description",
        content:
          "Đăng nhập KLAW để tra cứu pháp luật theo điều, khoản và soạn thảo văn bản pháp lý đúng thể thức.",
      },
      { property: "og:title", content: "Đăng nhập KLAW" },
      {
        property: "og:description",
        content: "Truy cập trợ lý pháp luật KLAW trên mọi thiết bị.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  validateSearch: (tho: Record<string, unknown>): { next?: DichQuayLai } => {
    const next = locNext(tho["next"]);
    return next === undefined ? {} : { next };
  },
  component: SignInPage,
});

// Tên `ma` là tên của SUPABASE, không phải tên thương hiệu: Microsoft là
// `azure` (Microsoft Entra ID). Một mảng, một nguồn sự thật cho cả nhãn, icon và
// mã provider — ba khối JSX viết tay là ba chỗ để chúng lệch nhau.
const OAUTH: readonly { ma: NhaCungCapOAuth; ten: string; icon: ReactNode }[] = [
  { ma: "google", ten: "Google", icon: <GoogleMark /> },
  { ma: "azure", ten: "Microsoft", icon: <MicrosoftMark /> },
  { ma: "facebook", ten: "Facebook", icon: <FacebookMark /> },
];

function SignInPage() {
  const navigate = useNavigate();
  // Đặt tên khác `next` — `onSubmit` bên dưới đã dùng `next` cho object lỗi
  // xác thực, và shadow biến này sẽ khiến `navigate` gọi sai kiểu (không lỗi
  // biên dịch rõ ràng: TS suy luận theo biến local rồi báo lệch kiểu ở dòng gọi).
  const { next: dichQuayVe } = Route.useSearch();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  // `signInWithOAuth` chuyển hướng cả trang, nên không có nhánh "thành công" ở
  // đây để điều hướng — chỉ có nhánh THẤT BẠI. `setLoading(false)` chạy đúng
  // khi chuyển hướng KHÔNG xảy ra (provider chưa bật ở Supabase, redirect URL
  // chưa whitelist), và lúc đó thông điệp của Supabase được hiện NGUYÊN VĂN:
  // "Unsupported provider" nói đúng vấn đề, còn một câu chung chung của KLAW
  // sẽ khiến người dùng thử lại mãi.
  const onOAuth = (nhaCungCap: NhaCungCapOAuth) => {
    setBanner(null);
    setLoading(true);
    void dangNhapOAuth(nhaCungCap).then((ketQua) => {
      setLoading(false);
      if (ketQua.trangThai !== "xong") setBanner(ketQua.thongDiep);
    });
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const next: { email?: string; password?: string } = {};
    if (!EMAIL_RE.test(email.trim())) next.email = MSG_EMAIL;
    if (!PASSWORD_RE.test(password)) next.password = MSG_PASSWORD;
    setErrors(next);
    setBanner(null);
    if (Object.keys(next).length > 0) return;

    setLoading(true);
    // Đăng nhập THẬT qua Supabase. Trước bản này, chỗ đây là một
    // `setTimeout(1200)` rồi báo "Xác thực thành công" cho mọi mật khẩu trừ
    // chuỗi "sai" — nói dối người dùng về chính phiên của họ, rồi đẩy họ sang
    // một màn hỏi mà cổng bảo vệ sẽ từ chối.
    void dangNhap(email.trim(), password).then((ketQua) => {
      setLoading(false);
      if (ketQua.trangThai !== "xong") {
        setBanner(ketQua.thongDiep);
        return;
      }
      setDone(true);
      setTimeout(() => navigate({ to: dichQuayVe ?? "/dung-thu" }), 900);
    });
  };

  return (
    <AuthShell>
      {banner ? <ErrorBanner message={banner} /> : null}

      <div className="rounded-2xl border border-transparent p-0">
        {done ? (
          <SuccessCheck label="Xác thực thành công. Đang mở trợ lý KLAW…" />
        ) : (
          <>
            <h1 className="font-display text-[36px] leading-tight text-primary">
              Đăng nhập vào KLAW
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Chưa có tài khoản?{" "}
              <Link
                to="/dang-ky"
                className="focus-brass rounded text-brass-600 underline-offset-4 hover:underline"
              >
                Đăng ký miễn phí
              </Link>
            </p>

            <div className="mt-7 space-y-3">
              {/* Ba provider chủ dự án chốt (2026-09-02). Dựng từ `OAUTH` chứ
                  không viết tay ba khối gần giống nhau — thêm provider thứ tư là
                  thêm MỘT dòng vào mảng, và không có bản sao nào lệch pha. */}
              {OAUTH.map((n) => (
                <SocialButton
                  key={n.ma}
                  icon={n.icon}
                  label={`Tiếp tục với ${n.ten}`}
                  disabled={loading}
                  onClick={() => onOAuth(n.ma)}
                />
              ))}
            </div>

            <Divider label="hoặc đăng nhập bằng email" />

            <form onSubmit={onSubmit} className="space-y-4">
              <fieldset disabled={loading} className="space-y-4">
                <Field
                  id="email"
                  label="Email công việc"
                  type="email"
                  autoComplete="email"
                  placeholder="ten@congty.vn"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  error={errors.email}
                />
                <PasswordField
                  id="password"
                  label="Mật khẩu"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  error={errors.password}
                />

                <div className="flex items-center justify-between pt-1">
                  <label className="flex cursor-pointer items-center gap-2 text-[13px] text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={remember}
                      onChange={(e) => setRemember(e.target.checked)}
                      className="focus-brass size-4 rounded border-border bg-card accent-brass-500"
                    />
                    Ghi nhớ đăng nhập
                  </label>
                  <Link
                    to="/huong-dan"
                    className="focus-brass rounded text-[13px] text-muted-foreground hover:text-brass-600"
                  >
                    Quên mật khẩu?
                  </Link>
                </div>
              </fieldset>

              <BrassButton loading={loading}>Đăng nhập</BrassButton>
            </form>

            <Fineprint>
              Bằng việc đăng nhập, bạn đồng ý với Điều khoản sử dụng và Chính sách bảo vệ dữ liệu cá
              nhân của KLAW.
            </Fineprint>
          </>
        )}
      </div>
    </AuthShell>
  );
}
