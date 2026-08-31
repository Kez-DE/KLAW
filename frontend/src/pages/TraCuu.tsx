import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { traCuu } from '../lib/api';
import { chuyenCanh, dongKhung, moKhung } from '../lib/chuyenCanh';
import { useGoiApi, useHaiCot } from '../lib/hooks';
import type { TraCuuResponse } from '../types';
import { BaoLoi } from '../components/BaoLoi';
import { KhungRoiSang } from '../components/KhungRoiSang';
import { ResultCard } from '../components/ResultCard';
import { TrangThaiCho } from '../components/TrangThaiCho';

/**
 * Tra cứu — ô hỏi ở giữa khi trống, trượt lên đầu khi có kết quả; mặt đọc và
 * dải khung bên dưới; bấm một trích dẫn thì khung rọi sáng mở nguyên văn.
 */

const DAI_TOI_DA = 2000; // hợp đồng: query 1..2000 ký tự

function moTaKetQua(ketQua: TraCuuResponse): string {
  switch (ketQua.result_type) {
    case 'answer':
      return `Đã có câu trả lời, kèm ${ketQua.citations.length} trích dẫn căn cứ.`;
    case 'partial_coverage':
      return `Chỉ tìm được văn bản liên quan, không diễn giải. ${ketQua.citations.length} trích dẫn.`;
    case 'abstain':
      return 'Không tìm thấy căn cứ pháp lý cho câu hỏi này.';
    case 'out_of_scope':
      return 'Câu hỏi nằm ngoài phạm vi hệ thống.';
  }
}

export default function TraCuu() {
  const [cauHoi, datCauHoi] = useState('');
  const [chiSoDangMo, datChiSoDangMo] = useState<number | null>(null);
  const chipTraTieuDiem = useRef<number | null>(null);
  const haiCot = useHaiCot();
  const { dangChay, ketQua, loi, chay, huy, datLai } = useGoiApi<TraCuuResponse>();

  const daBatDau = dangChay || ketQua !== null || loi !== null;
  const trichDanDangMo =
    ketQua !== null && chiSoDangMo !== null ? (ketQua.citations[chiSoDangMo] ?? null) : null;
  const panelMo = trichDanDangMo !== null;

  const gui = useCallback(
    (cau: string) => {
      const sach = cau.trim();
      if (sach === '' || dangChay) return;
      datChiSoDangMo(null);
      chuyenCanh(() => {
        void chay((signal) => traCuu({ query: sach }, signal));
      });
    },
    [chay, dangChay],
  );

  const khiGui = (su: FormEvent<HTMLFormElement>) => {
    su.preventDefault();
    gui(cauHoi);
  };

  // Ctrl/Cmd + Enter gửi từ trong ô hỏi — Enter thường vẫn xuống dòng, vì câu
  // hỏi dài nhiều dòng là chuyện bình thường ở đây.
  const khiGoPhim = (su: KeyboardEvent<HTMLTextAreaElement>) => {
    if (su.key === 'Enter' && (su.metaKey || su.ctrlKey)) {
      su.preventDefault();
      gui(cauHoi);
    }
  };

  const dong = useCallback(() => {
    const chiSo = chipTraTieuDiem.current;
    if (chiSo === null) return;
    dongKhung(chiSo, () => datChiSoDangMo(null));
  }, []);

  const chon = useCallback(
    (chiSo: number) => {
      if (chiSo === chiSoDangMo) {
        dong();
        return;
      }
      chipTraTieuDiem.current = chiSo;
      moKhung(chiSo, () => datChiSoDangMo(chiSo));
    },
    [chiSoDangMo, dong],
  );

  // Đóng panel: trả tiêu điểm về đúng khung vừa xem, không thả nó về đầu trang.
  useEffect(() => {
    if (chiSoDangMo !== null) return;
    const chiSo = chipTraTieuDiem.current;
    if (chiSo === null) return;
    chipTraTieuDiem.current = null;
    document.querySelector<HTMLElement>(`[data-khung="${chiSo}"]`)?.focus();
  }, [chiSoDangMo]);

  const oHoi = (
    <form onSubmit={khiGui} className="o-hoi w-full">
      <label htmlFor="cau-hoi" className="mat-doc mb-2 block font-medium text-phim">
        Hỏi về pháp luật lao động Việt Nam
      </label>
      <textarea
        id="cau-hoi"
        name="cau-hoi"
        rows={daBatDau ? 2 : 3}
        maxLength={DAI_TOI_DA}
        value={cauHoi}
        onChange={(su) => datCauHoi(su.target.value)}
        onKeyDown={khiGoPhim}
        placeholder="Ví dụ: Người lao động làm thêm giờ tối đa bao nhiêu giờ trong một năm?"
        aria-describedby="goi-y-o-hoi"
        className="mat-doc block w-full max-w-none resize-y rounded-vua border p-3 text-phim placeholder:text-muc-nhat focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        style={{
          background: 'var(--nen-cao)',
          borderColor: 'color-mix(in srgb, var(--muc-nhat) 55%, transparent)',
        }}
      />
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={cauHoi.trim() === '' || dangChay}
          className="min-h-[var(--vung-cham-toi-thieu)] cursor-pointer rounded-vua px-5 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang disabled:cursor-not-allowed disabled:opacity-45"
          style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
        >
          Tra cứu
        </button>
        <p id="goi-y-o-hoi" className="m-0 text-[0.75rem] leading-5 text-muc-nhat">
          Ctrl/⌘ + Enter để gửi. Một lượt tra cứu mất 10–60 giây.
        </p>
      </div>
    </form>
  );

  const cotDoc = (
    <div className="min-w-0">
      {oHoi}

      <p role="status" className="sr-only">
        {dangChay
          ? 'Đang tra cứu.'
          : ketQua !== null
            ? moTaKetQua(ketQua)
            : loi !== null
              ? loi.message
              : ''}
      </p>

      {dangChay && <TrangThaiCho onHuy={huy} />}

      {!dangChay && loi !== null && <BaoLoi loi={loi} onThuLai={() => gui(cauHoi)} />}

      {!dangChay && ketQua !== null && (
        <div className="mt-6">
          <ResultCard ketQua={ketQua} chiSoDangMo={chiSoDangMo} onChonTrichDan={chon} />
          <button
            type="button"
            onClick={() => {
              datChiSoDangMo(null);
              chipTraTieuDiem.current = null;
              chuyenCanh(() => {
                datLai();
                datCauHoi('');
              });
            }}
            className="mt-6 min-h-[var(--vung-cham-toi-thieu)] cursor-pointer text-[0.875rem] text-muc-nhat underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
          >
            Hỏi câu khác
          </button>
        </div>
      )}
    </div>
  );

  return (
    <div className="mx-auto w-full max-w-[104rem] px-4 py-6">
      {!daBatDau && (
        <div className="grid min-h-[60svh] place-items-center">
          <div className="w-full max-w-[46rem]">
            {oHoi}
            <div className="mat-doc mt-6 text-muc-nhat">
              <p className="m-0 text-[0.9375rem]">
                Mỗi câu trả lời đều neo vào trích dẫn kiểm chứng được: bấm một trích dẫn để mở
                nguyên văn điều luật và xem đúng chỗ câu trích đến từ.
              </p>
              <p className="mt-2 mb-0 text-[0.875rem]">
                Phạm vi: 6 Bộ luật (Dân sự, Tố tụng dân sự, Tố tụng hình sự, Hình sự, Hàng hải,
                Lao động) và cụm văn bản dưới luật về Lao động. Không phủ thuế, đất đai, hôn nhân
                gia đình.
              </p>
            </div>
          </div>
        </div>
      )}

      {daBatDau && (
        <div
          className={
            panelMo && haiCot
              ? 'grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-start gap-8'
              : 'grid grid-cols-1 gap-8'
          }
        >
          {/* Một cột: panel là lớp phủ toàn màn hình, nên phần dưới nó phải
              ngừng nhận tiêu điểm — `inert` là cách gốc của trình duyệt, không
              cần tự dựng bẫy tiêu điểm. */}
          <div inert={panelMo && !haiCot} className="mx-auto w-full max-w-[46rem]">
            {cotDoc}
          </div>
          {trichDanDangMo !== null && (
            <KhungRoiSang
              key={`${trichDanDangMo.doc_id}-${trichDanDangMo.khop_tai_id}`}
              citation={trichDanDangMo}
              onDong={dong}
            />
          )}
        </div>
      )}
    </div>
  );
}
