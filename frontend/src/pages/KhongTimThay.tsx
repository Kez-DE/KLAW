import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';

/**
 * Operate — người lạc đường cần lối ra, không cần giải trí (site-spec.md).
 * Không hài hước, không hình minh hoạ to: nêu rõ tuyến không tồn tại, đưa một
 * ô hỏi THẬT, và ba liên kết chính.
 */
export default function KhongTimThay() {
  const [cauHoi, datCauHoi] = useState('');
  const dieuHuong = useNavigate();

  const gui = (su: FormEvent<HTMLFormElement>) => {
    su.preventDefault();
    const sach = cauHoi.trim();
    dieuHuong(sach === '' ? '/tra-cuu' : `/tra-cuu?q=${encodeURIComponent(sach)}`);
  };

  return (
    <div className="mx-auto w-full max-w-[46rem] px-4 py-10">
      <h1 className="mat-doc text-2xl font-semibold text-phim focus:outline-2 focus:outline-den-sang focus:outline-offset-4 md:text-3xl">Không tìm thấy trang</h1>
      <p className="mat-doc mt-3 text-phim">
        Đường dẫn này không khớp với bất kỳ tuyến nào của KLAW. Có thể liên kết đã đổi hoặc địa chỉ
        bị gõ sai.
      </p>

      <form onSubmit={gui} className="mt-6">
        <label htmlFor="cau-hoi-404" className="mat-doc mb-2 block font-medium text-phim">
          Hỏi về pháp luật lao động Việt Nam
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            id="cau-hoi-404"
            name="cau-hoi-404"
            type="text"
            value={cauHoi}
            onChange={(su) => datCauHoi(su.target.value)}
            placeholder="Ví dụ: Người lao động làm thêm giờ tối đa bao nhiêu giờ trong một năm?"
            className="mat-doc min-h-[var(--vung-cham-toi-thieu)] flex-1 rounded-vua border p-3 text-phim placeholder:text-muc-nhat focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
            style={{
              background: 'var(--nen-cao)',
              borderColor: 'color-mix(in srgb, var(--muc-nhat) 55%, transparent)',
            }}
          />
          <button
            type="submit"
            className="min-h-[var(--vung-cham-toi-thieu)] cursor-pointer rounded-vua px-5 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
            style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
          >
            Tra cứu
          </button>
        </div>
      </form>

      <nav aria-label="Liên kết chính" className="mt-8">
        <ul className="mat-doc m-0 flex list-none flex-wrap gap-x-6 gap-y-2 p-0 text-phim">
          <li>
            <Link
              to="/"
              className="inline-flex min-h-[var(--vung-cham-toi-thieu)] items-center underline underline-offset-4 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
            >
              Trang chủ
            </Link>
          </li>
          <li>
            <Link
              to="/tra-cuu"
              className="inline-flex min-h-[var(--vung-cham-toi-thieu)] items-center underline underline-offset-4 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
            >
              Tra cứu
            </Link>
          </li>
          <li>
            <Link
              to="/huong-dan"
              className="inline-flex min-h-[var(--vung-cham-toi-thieu)] items-center underline underline-offset-4 hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
            >
              Hướng dẫn
            </Link>
          </li>
        </ul>
      </nav>
    </div>
  );
}
