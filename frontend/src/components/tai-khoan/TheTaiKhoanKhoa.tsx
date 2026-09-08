import { Link } from "@tanstack/react-router";

/**
 * Tài khoản bị admin khoá (spec 2B §7). Câu đầu là câu của máy chủ; câu sau nói việc còn làm
 * được: tra cứu luật và soát văn bản không tốn LLM nên vẫn mở. Không dùng màu hiệu lực
 * (đỏ dành cho luật hết hiệu lực — xem BaoLoi).
 */
export function TheTaiKhoanKhoa() {
  return (
    <div
      role="alert"
      className="mt-4 rounded-xl border border-border border-l-2 bg-[var(--color-paper-50)] p-4"
      style={{ borderLeftColor: "var(--color-status-neutral)" }}
    >
      <p className="doc-prose m-0 text-foreground">
        Tài khoản của bạn đang bị tạm khoá. Liên hệ hỗ trợ để được mở lại.
      </p>
      <p className="mt-2 mb-0 text-[14px] leading-6 text-muted-foreground">
        Tra cứu luật và soát văn bản vẫn dùng được; hỏi đáp và soạn văn bản mở lại sau khi tài khoản
        được mở.
      </p>
      <Link
        to="/huong-dan"
        className="focus-brass mt-3 inline-flex min-h-11 items-center rounded-lg border border-border px-4 text-[15px] font-medium text-primary hover:bg-[var(--color-paper-100)]"
      >
        Trợ giúp và liên hệ
      </Link>
    </div>
  );
}
