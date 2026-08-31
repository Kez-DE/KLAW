import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { soat } from '../lib/api';
import { useGoiApi, useHaiCot } from '../lib/hooks';
import type { LoaiVanBan, SoatResponse } from '../types';
import { BaoLoi } from '../components/BaoLoi';
import { TrangThaiCho } from '../components/TrangThaiCho';
import { BaoCaoSoat } from '../components/soat/BaoCaoSoat';
import { KhungCanCu } from '../components/soat/KhungCanCu';

/**
 * Soát — dán một văn bản có sẵn, máy trả danh sách phát hiện, mỗi cái neo vào
 * một điều luật cụ thể (không phải nhận xét chung chung).
 *
 * Khác `/soan-thao` ở đúng một điểm mà server tự đánh dấu: `self_audit=false`,
 * vì KLAW không sinh ra văn bản này. Báo cáo nói thẳng phân biệt đó.
 */

interface LuaChonLoai {
  giaTri: LoaiVanBan;
  nhan: string;
}

const CAC_LOAI: LuaChonLoai[] = [
  { giaTri: 'hdld', nhan: 'Hợp đồng lao động' },
  { giaTri: 'noi_quy', nhan: 'Nội quy lao động' },
  { giaTri: 'quyet_dinh_ky_luat', nhan: 'Quyết định kỷ luật lao động' },
];

/** `SoatRequest.text` có `min_length=20` ở server — chặn ở đây để không đổi
 *  một yêu cầu chắc chắn hỏng lấy một vòng 422. */
const DAI_TOI_THIEU = 20;

export default function Soat() {
  const [loai, datLoai] = useState<LoaiVanBan>('hdld');
  const [vanBan, datVanBan] = useState('');
  const [chiSoDangMo, datChiSoDangMo] = useState<number | null>(null);
  const nutTraTieuDiem = useRef<number | null>(null);
  const haiCot = useHaiCot();
  const { dangChay, ketQua, loi, chay, huy } = useGoiApi<SoatResponse>();

  const conThieu = DAI_TOI_THIEU - vanBan.trim().length;
  const guiDuoc = conThieu <= 0 && !dangChay;

  const gui = (su: FormEvent<HTMLFormElement>) => {
    su.preventDefault();
    if (!guiDuoc) return;
    datChiSoDangMo(null);
    nutTraTieuDiem.current = null;
    void chay((signal) => soat({ loai_van_ban: loai, text: vanBan.trim() }, signal));
  };

  const dong = useCallback(() => {
    datChiSoDangMo(null);
  }, []);

  const chonPhatHien = useCallback(
    (chiSo: number) => {
      if (chiSo === chiSoDangMo) {
        dong();
        return;
      }
      nutTraTieuDiem.current = chiSo;
      datChiSoDangMo(chiSo);
    },
    [chiSoDangMo, dong],
  );

  // Đóng panel: trả tiêu điểm về đúng phát hiện vừa xem.
  useEffect(() => {
    if (chiSoDangMo !== null) return;
    const chiSo = nutTraTieuDiem.current;
    if (chiSo === null) return;
    nutTraTieuDiem.current = null;
    document.querySelector<HTMLElement>(`[data-phat-hien="${chiSo}"]`)?.focus();
  }, [chiSoDangMo]);

  const phatHienDangMo =
    ketQua !== null && chiSoDangMo !== null
      ? (ketQua.audit_report.findings[chiSoDangMo] ?? null)
      : null;
  const docId = phatHienDangMo?.doc_id ?? null;
  const khopTaiId = phatHienDangMo?.khop_tai_id ?? null;
  const panelMo = docId !== null && khopTaiId !== null;

  const cotChinh = (
    <div className="min-w-0">
      <h1 className="mat-doc m-0 text-[1.5rem] leading-9 font-medium text-phim focus:outline-2 focus:outline-offset-4 focus:outline-den-sang">Soát văn bản</h1>
      <p className="mat-doc mt-2 mb-6 text-[0.9375rem] text-muc-nhat">
        Dán một văn bản có sẵn để máy rà soát. Mỗi phát hiện neo vào một điều luật cụ thể và mở
        được nguyên văn điều luật đó — không phải nhận xét chung chung.
      </p>

      <form onSubmit={gui}>
        <fieldset className="m-0 border-0 p-0">
          <legend className="mb-2 text-[0.9375rem] leading-6 font-medium text-phim">
            Loại văn bản
          </legend>
          <div className="flex flex-col gap-1">
            {CAC_LOAI.map((lua) => (
              <label
                key={lua.giaTri}
                className="flex min-h-[var(--vung-cham-toi-thieu)] cursor-pointer items-center gap-3 text-[0.9375rem] leading-6 text-phim"
              >
                <input
                  type="radio"
                  name="loai-van-ban-soat"
                  value={lua.giaTri}
                  checked={loai === lua.giaTri}
                  onChange={() => datLoai(lua.giaTri)}
                  disabled={dangChay}
                  className="size-5 shrink-0 accent-[var(--den-sang)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
                />
                {lua.nhan}
              </label>
            ))}
          </div>
        </fieldset>

        {loai !== 'hdld' && (
          <div
            className="mt-4 rounded-lon border-s-2 py-3 ps-4"
            style={{ borderColor: 'var(--vang-mo)', background: 'var(--nen-cao)' }}
          >
            <p className="mat-doc m-0 text-[0.9375rem] text-phim">
              Loại văn bản này chưa có nội dung pháp lý trong hệ thống.
            </p>
            <p className="mat-doc mt-2 mb-0 text-[0.875rem] text-muc-nhat">
              Máy chủ sẽ từ chối yêu cầu thay vì soát bằng danh mục của hợp đồng lao động — soát
              nhầm bộ quy tắc còn tệ hơn không soát.
            </p>
          </div>
        )}

        <div className="mt-6">
          <label htmlFor="van-ban-soat" className="mb-2 block text-[0.9375rem] font-medium text-phim">
            Văn bản cần soát
          </label>
          <textarea
            id="van-ban-soat"
            name="van-ban-soat"
            rows={12}
            value={vanBan}
            disabled={dangChay}
            onChange={(su) => datVanBan(su.target.value)}
            placeholder="Dán toàn văn hợp đồng lao động vào đây."
            aria-describedby="goi-y-soat"
            className="mat-doc block w-full max-w-none resize-y rounded-vua border p-3 text-phim placeholder:text-muc-nhat focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang disabled:opacity-50"
            style={{
              background: 'var(--nen-cao)',
              borderColor: 'color-mix(in srgb, var(--muc-nhat) 55%, transparent)',
            }}
          />
          <p id="goi-y-soat" className="mt-2 mb-0 text-[0.75rem] leading-5 text-muc-nhat">
            {conThieu > 0
              ? `Cần thêm ít nhất ${conThieu} ký tự nữa.`
              : `${vanBan.trim().length} ký tự. Máy tách điều khoản theo dòng “Điều N.” — văn bản giữ nguyên cách đánh số sẽ được đọc đúng nhất.`}
          </p>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={!guiDuoc}
            className="min-h-[var(--vung-cham-toi-thieu)] cursor-pointer rounded-vua px-5 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang disabled:cursor-not-allowed disabled:opacity-45"
            style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
          >
            Soát văn bản
          </button>
        </div>
      </form>

      <p role="status" className="sr-only">
        {dangChay
          ? 'Đang soát văn bản.'
          : ketQua !== null
            ? `Soát xong, ${ketQua.audit_report.findings.length} phát hiện.`
            : loi !== null
              ? loi.message
              : ''}
      </p>

      {dangChay && <TrangThaiCho onHuy={huy} />}

      {!dangChay && loi !== null && <BaoLoi loi={loi} />}

      {!dangChay && ketQua !== null && (
        <div className="mt-8">
          <BaoCaoSoat
            baoCao={ketQua.audit_report}
            chiSoDangMo={chiSoDangMo}
            onChonPhatHien={chonPhatHien}
          />
        </div>
      )}
    </div>
  );

  return (
    <div className="mx-auto w-full max-w-[104rem] px-4 py-6">
      <div
        className={
          panelMo && haiCot
            ? 'grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-start gap-8'
            : 'grid grid-cols-1 gap-8'
        }
      >
        <div inert={panelMo && !haiCot} className="mx-auto w-full max-w-[46rem]">
          {cotChinh}
        </div>
        {docId !== null && khopTaiId !== null && (
          <KhungCanCu
            key={`${docId}-${khopTaiId}`}
            docId={docId}
            khopTaiId={khopTaiId}
            canCu={phatHienDangMo?.can_cu ?? null}
            onDong={dong}
          />
        )}
      </div>
    </div>
  );
}
