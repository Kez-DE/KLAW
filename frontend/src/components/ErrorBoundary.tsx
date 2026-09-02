import { Component } from 'react';
import type { ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  loi: Error | null;
}

/**
 * Ở gốc cây render (App.tsx) — lỗi render KHÔNG được ra màn hình trắng
 * (site-spec.md). Hiện lỗi THẬT (message) và một nút tải lại. Không nuốt
 * lỗi: không nhánh nào bắt rồi lặng thinh trả về null — nếu có lỗi, luôn có
 * UI thay thế nói rõ có lỗi.
 *
 * React error boundary bắt buộc là class component — không có hook tương
 * đương ở React 19.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { loi: null };

  static getDerivedStateFromError(loi: Error): ErrorBoundaryState {
    return { loi };
  }

  taiLai = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    const { loi } = this.state;
    if (loi === null) return this.props.children;

    return (
      <div className="mx-auto flex min-h-svh w-full max-w-[46rem] flex-col justify-center px-4 py-10">
        <h1 className="mat-doc text-2xl font-semibold text-phim focus:outline-2 focus:outline-den-sang focus:outline-offset-4 md:text-3xl">
          Đã có lỗi khi hiển thị trang
        </h1>
        <p className="mat-doc mt-3 text-muc-nhat">
          Đây là lỗi thật của ứng dụng — không phải một trang trắng im lặng. Chi tiết lỗi:
        </p>
        <pre
          className="dia-chi mt-3 overflow-x-auto rounded-vua border p-3 text-[0.8125rem] leading-6 whitespace-pre-wrap text-phim"
          style={{
            background: 'var(--nen-cao)',
            borderColor: 'color-mix(in srgb, var(--muc-nhat) 55%, transparent)',
          }}
        >
          {loi.message}
        </pre>
        <button
          type="button"
          onClick={this.taiLai}
          className="mt-6 min-h-[var(--vung-cham-toi-thieu)] w-fit cursor-pointer rounded-vua px-5 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
          style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
        >
          Tải lại trang
        </button>
      </div>
    );
  }
}
