import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Bản tối giản GIỮ CHỖ — một agent khác sẽ dựng đầy đủ trang giới thiệu (hero
 * 3D, luận đề chuyển động, mode Persuade). Không đầu tư gì thêm ở đây ngoài
 * một <h1> và một ô hỏi THẬT dẫn sang /tra-cuu (không phải nút liên kết —
 * DESIGN.md, "Màn hình giới thiệu").
 */
export default function GioiThieu() {
  const [cauHoi, datCauHoi] = useState('');
  const dieuHuong = useNavigate();

  const gui = (su: FormEvent<HTMLFormElement>) => {
    su.preventDefault();
    const sach = cauHoi.trim();
    dieuHuong(sach === '' ? '/tra-cuu' : `/tra-cuu?q=${encodeURIComponent(sach)}`);
  };

  return (
    <div className="mx-auto flex min-h-[70svh] w-full max-w-[46rem] flex-col justify-center px-4 py-10">
      <h1 className="mat-doc text-2xl font-semibold text-phim focus:outline-2 focus:outline-den-sang focus:outline-offset-4 md:text-3xl">
        KLAW — tra cứu pháp luật lao động Việt Nam có trích dẫn kiểm chứng được
      </h1>
      <p className="mat-doc mt-3 text-muc-nhat">
        Trang giới thiệu đầy đủ đang được dựng ở một phiên làm việc khác. Hỏi ngay bên dưới để
        dùng công cụ tra cứu.
      </p>

      <form onSubmit={gui} className="mt-6">
        <label htmlFor="cau-hoi-gioi-thieu" className="sr-only">
          Hỏi về pháp luật lao động Việt Nam
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            id="cau-hoi-gioi-thieu"
            name="cau-hoi-gioi-thieu"
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
    </div>
  );
}
