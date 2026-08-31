import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, type FormEvent } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import {
  BrassButton,
  Divider,
  EMAIL_RE,
  ErrorBanner,
  Field,
  Fineprint,
  GoogleMark,
  MSG_EMAIL,
  MSG_PASSWORD,
  MicrosoftMark,
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
  component: SignInPage,
});

function SignInPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const next: { email?: string; password?: string } = {};
    if (!EMAIL_RE.test(email.trim())) next.email = MSG_EMAIL;
    if (!PASSWORD_RE.test(password)) next.password = MSG_PASSWORD;
    setErrors(next);
    setBanner(null);
    if (Object.keys(next).length > 0) return;

    setLoading(true);
    // TODO: replace with real authentication endpoint.
    setTimeout(() => {
      setLoading(false);
      if (password.toLowerCase() === "sai") {
        setBanner("Email hoặc mật khẩu không đúng.");
        return;
      }
      setDone(true);
      setTimeout(() => navigate({ to: "/dung-thu" }), 900);
    }, 1200);
  };

  return (
    <AuthShell>
      {banner ? <ErrorBanner message={banner} /> : null}

      <div className="rounded-2xl border border-transparent p-0">
        {done ? (
          <SuccessCheck label="Xác thực thành công. Đang mở phiên dùng thử…" />
        ) : (
          <>
            <h2 className="font-display text-[36px] leading-tight text-primary">
              Đăng nhập vào KLAW
            </h2>
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
              <SocialButton
                icon={<GoogleMark />}
                label="Tiếp tục với Google"
                disabled={loading}
              />
              <SocialButton
                icon={<MicrosoftMark />}
                label="Tiếp tục với Microsoft"
                disabled={loading}
              />
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
              Bằng việc đăng nhập, bạn đồng ý với Điều khoản sử dụng và Chính sách
              bảo vệ dữ liệu cá nhân của KLAW.
            </Fineprint>
          </>
        )}
      </div>
    </AuthShell>
  );
}
