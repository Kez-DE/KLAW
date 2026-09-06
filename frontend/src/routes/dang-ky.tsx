import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useState, type FormEvent } from "react";
import { AuthShell } from "@/components/auth/AuthShell";
import { locNext, type DichQuayLai } from "@/lib/quay-lai";
import type { NhaCungCapOAuth } from "@/lib/xac-thuc";
import { dangKy, dangNhapOAuth } from "@/lib/xac-thuc";
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
  validateSearch: (tho: Record<string, unknown>): { next?: DichQuayLai } => {
    const next = locNext(tho["next"]);
    return next === undefined ? {} : { next };
  },
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

// Tên `ma` là tên của SUPABASE, không phải tên thương hiệu: Microsoft là
// `azure` (Microsoft Entra ID). Một mảng, một nguồn sự thật cho cả nhãn, icon và
// mã provider — ba khối JSX viết tay là ba chỗ để chúng lệch nhau.
const OAUTH: readonly { ma: NhaCungCapOAuth; ten: string; icon: ReactNode }[] = [
  { ma: "google", ten: "Google", icon: <GoogleMark /> },
  { ma: "azure", ten: "Microsoft", icon: <MicrosoftMark /> },
  { ma: "facebook", ten: "Facebook", icon: <FacebookMark /> },
];

function SignUpPage() {
  const navigate = useNavigate();
  // Đặt tên khác `next` — `onSubmit` bên dưới đã dùng `next` cho object lỗi
  // xác thực, và shadow biến này sẽ khiến `navigate` gọi sai kiểu (không lỗi
  // biên dịch rõ ràng: TS suy luận theo biến local rồi báo lệch kiểu ở dòng gọi).
  const { next: dichQuayVe } = Route.useSearch();
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
    const next: Record<string, string> = {};
    if (form.name.trim().length < 2) next["name"] = "Vui lòng nhập họ và tên của bạn.";
    if (!EMAIL_RE.test(form.email.trim())) next["email"] = MSG_EMAIL;
    if (!PASSWORD_RE.test(form.password)) next["password"] = MSG_PASSWORD;
    setErrors(next);
    setBanner(null);
    if (Object.keys(next).length > 0) return;

    setLoading(true);
    // Đăng ký THẬT qua Supabase — xem ghi chú trong `lib/xac-thuc.ts`.
    void dangKy(form.email.trim(), form.password, form.name.trim()).then((ketQua) => {
      setLoading(false);
      if (ketQua.trangThai !== "xong") {
        setBanner(ketQua.thongDiep);
        return;
      }
      if (ketQua.canXacNhanEmail) {
        // Dự án bật xác nhận email thì CHƯA có phiên. Đẩy sang màn hỏi lúc này
        // là để cổng bảo vệ trả 401 cho một tài khoản vừa tạo thành công.
        setBanner("Đã tạo tài khoản. Kiểm tra hộp thư và bấm liên kết xác nhận, sau đó đăng nhập.");
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
          <SuccessCheck label="Tạo tài khoản thành công. Đang mở trợ lý KLAW…" />
        ) : (
          <>
            <h1 className="font-display text-[36px] leading-tight text-primary">
              Đăng ký tài khoản KLAW
            </h1>
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
