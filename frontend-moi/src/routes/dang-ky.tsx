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

export const Route = createFileRoute("/dang-ky")({
  head: () => ({
    meta: [
      { title: "Đăng ký tài khoản KLAW miễn phí" },
      {
        name: "description",
        content:
          "Tạo tài khoản KLAW để tra cứu pháp luật có trích dẫn và soạn thảo văn bản pháp lý theo mẫu chuẩn.",
      },
      { property: "og:title", content: "Đăng ký KLAW" },
      {
        property: "og:description",
        content: "Tạo tài khoản KLAW miễn phí trong một phút.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: SignUpPage,
});

const ROLES = ["Luật sư", "Pháp chế nội bộ", "Nhân sự", "Kế toán", "Chủ doanh nghiệp", "Khác"];

const RULES = [
  { label: "Tối thiểu 8 ký tự", test: (v: string) => v.length >= 8 },
  { label: "Có ít nhất một chữ cái", test: (v: string) => /[A-Za-z]/.test(v) },
  { label: "Có ít nhất một chữ số", test: (v: string) => /\d/.test(v) },
  { label: "Nên có ký tự đặc biệt", test: (v: string) => /[^A-Za-z0-9]/.test(v) },
];

function StrengthMeter({ value }: { value: string }) {
  const score = RULES.filter((r) => r.test(value)).length;
  const labels = ["Rất yếu", "Yếu", "Khá", "Mạnh"];
  return (
    <div className="space-y-2 pt-1">
      <div className="flex gap-1.5">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
              i < score ? "bg-brass-500" : "bg-border"
            }`}
          />
        ))}
      </div>
      <p className="text-[12px] text-muted-foreground">
        Độ mạnh: {value ? labels[Math.max(score - 1, 0)] : "—"}
      </p>
      <ul className="space-y-0.5 text-[12px]">
        {RULES.map((r) => (
          <li key={r.label} className={r.test(value) ? "text-brass-600" : "text-muted-foreground"}>
            {r.test(value) ? "✓" : "•"} {r.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

function SignUpPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    email: "",
    org: "",
    role: ROLES[0]!,
    password: "",
  });
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (form.name.trim().length < 2) next["name"] = "Vui lòng nhập họ và tên của bạn.";
    if (!EMAIL_RE.test(form.email.trim())) next["email"] = MSG_EMAIL;
    if (!PASSWORD_RE.test(form.password)) next["password"] = MSG_PASSWORD;
    setErrors(next);
    setBanner(null);
    if (Object.keys(next).length > 0) return;

    setLoading(true);
    // TODO: replace with real authentication endpoint.
    setTimeout(() => {
      setLoading(false);
      if (form.email.trim().toLowerCase() === "trung@klaw.vn") {
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
          <SuccessCheck label="Tạo tài khoản thành công. Đang mở phiên dùng thử…" />
        ) : (
          <>
            <h2 className="font-display text-[36px] leading-tight text-primary">
              Đăng ký tài khoản KLAW
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Đã có tài khoản?{" "}
              <Link
                to="/dang-nhap"
                className="focus-brass rounded text-brass-600 underline-offset-4 hover:underline"
              >
                Đăng nhập
              </Link>
            </p>

            <div className="mt-7 space-y-3">
              <SocialButton icon={<GoogleMark />} label="Tiếp tục với Google" disabled={loading} />
              <SocialButton
                icon={<MicrosoftMark />}
                label="Tiếp tục với Microsoft"
                disabled={loading}
              />
            </div>

            <Divider label="hoặc đăng ký bằng email" />

            <form onSubmit={onSubmit} className="space-y-4">
              <fieldset disabled={loading} className="space-y-4">
                <Field
                  id="name"
                  label="Họ và tên"
                  placeholder="Nguyễn Văn A"
                  value={form.name}
                  onChange={(e) => set("name")(e.target.value)}
                  error={errors["name"]}
                />
                <Field
                  id="email"
                  label="Email công việc"
                  type="email"
                  autoComplete="email"
                  placeholder="ten@congty.vn"
                  value={form.email}
                  onChange={(e) => set("email")(e.target.value)}
                  error={errors["email"]}
                />
                <Field
                  id="org"
                  label="Tên tổ chức (không bắt buộc)"
                  placeholder="Công ty TNHH ..."
                  value={form.org}
                  onChange={(e) => set("org")(e.target.value)}
                />
                <div className="space-y-1.5">
                  <label htmlFor="role" className="block text-[13px] text-muted-foreground">
                    Vai trò
                  </label>
                  <select
                    id="role"
                    value={form.role}
                    onChange={(e) => set("role")(e.target.value)}
                    className="focus-brass w-full rounded-lg border border-border bg-background/70 px-3.5 py-2.5 text-sm text-foreground transition-colors hover:border-border disabled:opacity-50"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r} className="bg-card">
                        {r}
                      </option>
                    ))}
                  </select>
                </div>
                <PasswordField
                  id="password"
                  label="Mật khẩu"
                  autoComplete="new-password"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={(e) => set("password")(e.target.value)}
                  error={errors["password"]}
                  hint={<StrengthMeter value={form.password} />}
                />

                <label className="flex cursor-pointer items-start gap-3 pt-1 text-[13px] leading-relaxed text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(e) => setConsent(e.target.checked)}
                    className="focus-brass mt-0.5 size-4 shrink-0 rounded border-border bg-card accent-brass-500"
                  />
                  Tôi đồng ý cho KLAW xử lý dữ liệu cá nhân của tôi theo Chính sách bảo vệ dữ liệu
                  cá nhân.
                </label>
              </fieldset>

              <BrassButton loading={loading} disabled={!consent} loadingLabel="Đang xác thực…">
                Tạo tài khoản
              </BrassButton>
            </form>

            <Fineprint>
              Bằng việc đăng ký, bạn đồng ý với Điều khoản sử dụng và Chính sách bảo vệ dữ liệu cá
              nhân của KLAW.
            </Fineprint>
          </>
        )}
      </div>
    </AuthShell>
  );
}
