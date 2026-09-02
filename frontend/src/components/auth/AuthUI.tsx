import { useState, type InputHTMLAttributes, type ReactNode } from "react";
import { AlertTriangle, Eye, EyeOff, Loader2 } from "lucide-react";

export function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="size-4.5" aria-hidden>
      <path
        fill="#EA4335"
        d="M24 9.5c3.5 0 6.6 1.2 9 3.5l6.7-6.7C35.6 2.4 30.2 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.8 6.1C12.3 13.2 17.6 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.5 24.5c0-1.6-.1-2.8-.4-4.1H24v8.4h12.7c-.3 2.1-1.6 5.2-4.7 7.3l7.6 5.9c4.5-4.2 6.9-10.3 6.9-17.5z"
      />
      <path
        fill="#FBBC05"
        d="M10.4 28.7A14.6 14.6 0 0 1 9.6 24c0-1.6.3-3.2.8-4.7l-7.8-6.1A24 24 0 0 0 0 24c0 3.9.9 7.5 2.6 10.8l7.8-6.1z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.5 0 11.9-2.1 15.6-5.9l-7.6-5.9c-2 1.4-4.7 2.4-8 2.4-6.4 0-11.7-3.7-13.6-9.9l-7.8 6.1C6.5 42.6 14.6 48 24 48z"
      />
    </svg>
  );
}

export function MicrosoftMark() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden>
      <rect x="1" y="1" width="10" height="10" fill="#F25022" />
      <rect x="13" y="1" width="10" height="10" fill="#7FBA00" />
      <rect x="1" y="13" width="10" height="10" fill="#00A4EF" />
      <rect x="13" y="13" width="10" height="10" fill="#FFB900" />
    </svg>
  );
}

export function FacebookMark() {
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden>
      <path
        fill="#1877F2"
        d="M24 12.07C24 5.4 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.05V9.41c0-3.02 1.79-4.69 4.53-4.69 1.31 0 2.68.24 2.68.24v2.96h-1.51c-1.49 0-1.95.93-1.95 1.88v2.27h3.32l-.53 3.49h-2.79V24C19.61 23.1 24 18.1 24 12.07Z"
      />
    </svg>
  );
}

/**
 * Nút đăng nhập bằng bên thứ ba — bảo đảm #10.
 *
 * `onClick` từng là TUỲ CHỌN, và không một nơi gọi nào truyền nó. Bốn nút
 * (Google + Microsoft, trên cả `/dang-nhap` lẫn `/dang-ky`) vì thế hiện ra
 * đầy đủ màu thương hiệu, có hover, có vòng tiêu điểm, nằm NGAY TRÊN biểu mẫu
 * email như lối vào chính — và bấm vào thì không xảy ra gì. Không lỗi, không
 * chuyển trang, không một dấu hiệu nào.
 *
 * Đây đúng là chế độ hỏng mà `lib/xac-thuc.ts` đã gỡ cho đường mật khẩu: màn
 * đăng nhập nói sai về chính phiên của người dùng. Đường mật khẩu được chữa,
 * đường mạng xã hội thì không.
 *
 * Kiểu dưới đây bắt buộc CHỌN MỘT: hoặc có `onClick` thật, hoặc khai `chuaDung`
 * và nút tự hiện ra là chưa dựng. Không còn trạng thái thứ ba "trông bấm được
 * nhưng không làm gì" — nó là lỗi biên dịch, không phải một thứ phải nhớ.
 */
type SocialButtonProps = {
  icon: ReactNode;
  label: string;
  disabled?: boolean;
} & ({ onClick: () => void; chuaDung?: never } | { onClick?: never; chuaDung: string });

export function SocialButton({ icon, label, onClick, disabled, chuaDung }: SocialButtonProps) {
  const chuaCo = chuaDung !== undefined;
  return (
    <button
      type="button"
      {...(onClick === undefined ? {} : { onClick })}
      disabled={disabled === true || chuaCo}
      {...(chuaCo ? { title: chuaDung, "aria-description": chuaDung } : {})}
      className="focus-brass flex w-full items-center justify-center gap-3 rounded-lg border border-border bg-background/60 px-4 py-3 text-sm font-medium text-foreground transition-colors hover:border-brass-500/50 hover:bg-brass-500/10 disabled:cursor-default disabled:opacity-50 disabled:hover:border-border disabled:hover:bg-background/60"
    >
      {icon}
      {chuaCo ? `${label} — chưa dựng` : label}
    </button>
  );
}

export function Divider({ label }: { label: string }) {
  return (
    <div className="my-6 flex items-center gap-4">
      <span className="h-px flex-1 bg-border" />
      <span className="text-[12px] text-muted-foreground">{label}</span>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string | undefined;
  hint?: ReactNode;
};

export function Field({ label, error, hint, id, ...rest }: FieldProps) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-[13px] text-muted-foreground">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={!!error}
        className={`focus-brass w-full rounded-lg border bg-background/70 px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground transition-colors disabled:opacity-50 ${
          error ? "border-status-expired" : "border-border hover:border-border"
        }`}
        {...rest}
      />
      {hint}
      {error ? <p className="text-[12px] text-status-expired">{error}</p> : null}
    </div>
  );
}

export function PasswordField({ label, error, hint, id, ...rest }: FieldProps) {
  const [show, setShow] = useState(false);
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-[13px] text-muted-foreground">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={show ? "text" : "password"}
          aria-invalid={!!error}
          className={`focus-brass w-full rounded-lg border bg-background/70 px-3.5 py-2.5 pr-11 text-sm text-foreground placeholder:text-muted-foreground transition-colors disabled:opacity-50 ${
            error ? "border-status-expired" : "border-border hover:border-border"
          }`}
          {...rest}
        />
        <button
          type="button"
          onClick={() => setShow((v) => !v)}
          aria-label={show ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
          className="focus-brass absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-lg text-muted-foreground transition-colors hover:text-brass-600"
        >
          {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      {hint}
      {error ? <p className="text-[12px] text-status-expired">{error}</p> : null}
    </div>
  );
}

export function BrassButton({
  children,
  loading,
  loadingLabel = "Đang xác thực…",
  disabled,
}: {
  children: ReactNode;
  loading?: boolean;
  loadingLabel?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="submit"
      disabled={disabled || loading}
      className="focus-brass flex w-full items-center justify-center gap-2 rounded-lg bg-brass-500 px-4 py-3 text-sm font-semibold text-ink-950 transition-all hover:bg-brass-400 disabled:cursor-not-allowed disabled:opacity-45"
    >
      {loading ? (
        <>
          <Loader2 className="size-4 animate-spin" />
          {loadingLabel}
        </>
      ) : (
        children
      )}
    </button>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="animate-fade-up mb-5 flex items-start gap-3 rounded-lg border border-status-expired bg-status-expired/10 px-4 py-3 text-[13px] text-foreground"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-status-expired" />
      <span>{message}</span>
    </div>
  );
}

export function SuccessCheck({ label }: { label: string }) {
  return (
    <div className="animate-fade-up flex flex-col items-center gap-4 py-14 text-center">
      <span className="grid size-16 place-items-center rounded-full border border-brass-500/40 bg-brass-500/10">
        <svg viewBox="0 0 24 24" className="brass-check size-8" fill="none">
          <path
            d="M4 12.5 10 18.5 20 6.5"
            stroke="var(--color-brass-500)"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

export function Fineprint({ children }: { children: ReactNode }) {
  return <p className="mt-5 text-[12px] leading-relaxed text-muted-foreground">{children}</p>;
}

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
export const PASSWORD_RE = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;
export const MSG_EMAIL = "Vui lòng nhập email công việc hợp lệ.";
export const MSG_PASSWORD = "Mật khẩu cần tối thiểu 8 ký tự, gồm chữ và số.";
