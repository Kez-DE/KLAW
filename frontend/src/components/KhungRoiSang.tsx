import { useEffect, useRef, useState } from 'react';
import { layVanBanQuanhDieu } from '../lib/api';
import { useGoiApi, useHaiCot } from '../lib/hooks';
import { catTheoTrichDan } from '../lib/trichDan';
import type { Citation, Provision, VanBanAroundResponse } from '../types';
import { BaoLoi } from './BaoLoi';
import { DuongDan } from './DuongDan';

/**
 * Khung rọi sáng — nguyên văn điều luật, câu trích được đánh dấu.
 *
 * Đây LÀ click-to-verify, đóng góp trung tâm của đề tài. Hai điểm không được
 * làm sai:
 *
 * 1. Fetch bằng `khop_tai_id`, KHÔNG phải `provision_id`. `provision_id`
 *    thường chỉ là tiêu đề Điều; nội dung nằm ở Khoản con, và hai id khác nhau
 *    ở 73,6% số Điều.
 * 2. `la_tam=true` áp cho Điều tâm VÀ mọi Khoản/Điểm con của nó — rọi sáng cả
 *    VÙNG đó, không phải một dòng.
 *
 * Panel tự lo vòng đời tải/lỗi/thử lại của chính nó, để hai màn hình còn lại
 * chỉ cần truyền vào một `Citation`.
 */

interface NhomDieu {
  /** Dòng cấp `dieu`; null nếu phản hồi mở đầu bằng một Khoản mồ côi. */
  dieu: Provision | null;
  con: Provision[];
  laTam: boolean;
}

function nhomTheoDieu(provisions: Provision[]): NhomDieu[] {
  const nhom: NhomDieu[] = [];
  for (const dieuKhoan of provisions) {
    const laDieu = dieuKhoan.cap === 'dieu';
    if (laDieu || nhom.length === 0) {
      nhom.push({
        dieu: laDieu ? dieuKhoan : null,
        con: laDieu ? [] : [dieuKhoan],
        laTam: dieuKhoan.la_tam,
      });
      continue;
    }
    const cuoi = nhom[nhom.length - 1];
    cuoi.con.push(dieuKhoan);
    cuoi.laTam = cuoi.laTam || dieuKhoan.la_tam;
  }
  return nhom;
}

const LE_THEO_CAP: Record<string, string | undefined> = {
  dieu: '0rem',
  khoan: '1rem',
  diem: '2rem',
};

interface DongNguyenVanProps {
  dieuKhoan: Provision;
  /** Câu trích cần đánh dấu; chỉ truyền vào đúng dòng đã khớp (`khop_tai_id`). */
  quote: string | null;
}

function DongNguyenVan({ dieuKhoan, quote }: DongNguyenVanProps) {
  const lat = quote === null ? null : catTheoTrichDan(dieuKhoan.noi_dung, quote);
  return (
    <p
      className="chu-tren-phim my-2 text-[1rem] leading-[1.75] whitespace-pre-wrap"
      style={{ marginInlineStart: LE_THEO_CAP[dieuKhoan.cap] ?? '0rem' }}
    >
      {lat === null || !lat.timThay ? (
        dieuKhoan.noi_dung.normalize('NFC')
      ) : (
        <>
          {lat.truoc}
          <mark className="cau-trich">{lat.trung}</mark>
          {lat.sau}
        </>
      )}
    </p>
  );
}

interface KhungRoiSangProps {
  citation: Citation;
  onDong: () => void;
}

export function KhungRoiSang({ citation, onDong }: KhungRoiSangProps) {
  const haiCot = useHaiCot();
  const { dangChay, ketQua, loi, chay } = useGoiApi<VanBanAroundResponse>();
  const tieuDe = useRef<HTMLHeadingElement>(null);
  const vungCuon = useRef<HTMLDivElement>(null);
  // Giữ CHÍNH phản hồi đã được rọi sáng, thay vì một cờ boolean phải tay reset:
  // phản hồi mới là một object mới, nên quầng đèn tự tắt rồi sáng lại.
  const [ketQuaDaRoi, datKetQuaDaRoi] = useState<VanBanAroundResponse | null>(null);

  const { doc_id: docId, khop_tai_id: khopTaiId, quote } = citation;

  useEffect(() => {
    // khop_tai_id, KHÔNG phải provision_id — xem ghi chú đầu file.
    void chay((signal) => layVanBanQuanhDieu(docId, khopTaiId, signal));
  }, [chay, docId, khopTaiId]);

  // Esc đóng panel, kể cả khi tiêu điểm đã đi khỏi panel.
  useEffect(() => {
    const nghe = (su: KeyboardEvent) => {
      if (su.key === 'Escape') onDong();
    };
    window.addEventListener('keydown', nghe);
    return () => window.removeEventListener('keydown', nghe);
  }, [onDong]);

  // Mở panel: đưa tiêu điểm vào tiêu đề của nó. Trả tiêu điểm về chip khi đóng
  // là việc của trang gọi — chỉ trang đó biết chip nào.
  useEffect(() => {
    tieuDe.current?.focus();
  }, []);

  // Một cột: panel phủ toàn màn hình, khoá cuộn nền phía sau.
  useEffect(() => {
    if (haiCot) return;
    const cu = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = cu;
    };
  }, [haiCot]);

  // Rọi sáng: bật sau khi nguyên văn đã dựng xong, để `opacity` có cái để
  // chuyển từ 0 lên 1 — câu trích sáng DẦN, không bật sẵn.
  useEffect(() => {
    if (ketQua === null) return;
    const khung = requestAnimationFrame(() => datKetQuaDaRoi(ketQua));
    vungCuon.current?.querySelector('[data-vung-tam]')?.scrollIntoView({ block: 'center' });
    return () => cancelAnimationFrame(khung);
  }, [ketQua]);

  const daRoi = ketQua !== null && ketQuaDaRoi === ketQua;
  const nhom = ketQua === null ? [] : nhomTheoDieu(ketQua.provisions);
  const dongKhop = ketQua?.provisions.find((dieuKhoan) => dieuKhoan.id === khopTaiId) ?? null;
  const khongDinhVi = dongKhop !== null && !catTheoTrichDan(dongKhop.noi_dung, quote).timThay;

  return (
    <aside
      role={haiCot ? 'region' : 'dialog'}
      aria-modal={haiCot ? undefined : true}
      aria-label="Nguyên văn điều luật"
      className={
        haiCot
          ? 'sticky top-4 self-start'
          : 'fixed inset-0 z-[var(--z-khung-roi-sang)] flex flex-col bg-nen p-3'
      }
    >
      <div
        className="khung-nguyen-van flex min-h-0 flex-1 flex-col overflow-hidden rounded-lon border shadow-noi-3"
        style={{ background: 'var(--nen-cao)', borderColor: 'var(--den-sang)' }}
      >
        <header
          className="flex items-start gap-3 border-b p-3"
          style={{ borderColor: 'color-mix(in srgb, var(--muc-nhat) 40%, transparent)' }}
        >
          <h2
            ref={tieuDe}
            tabIndex={-1}
            className="m-0 min-w-0 flex-1 text-[0.9375rem] leading-6 font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
          >
            <span className="mb-1 block text-[0.75rem] text-muc-nhat">Nguyên văn</span>
            <DuongDan
              soKyHieu={ketQua?.so_ky_hieu ?? citation.so_ky_hieu}
              duongDan={citation.duong_dan}
              boLuat={ketQua?.bo_luat ?? citation.bo_luat}
            />
          </h2>
          <button
            type="button"
            onClick={onDong}
            className="min-h-[var(--vung-cham-toi-thieu)] min-w-[var(--vung-cham-toi-thieu)] shrink-0 cursor-pointer rounded-vua border text-[0.875rem] text-phim transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
            style={{ borderColor: 'var(--muc-nhat)' }}
          >
            Đóng
          </button>
        </header>

        <div
          ref={vungCuon}
          className={`min-h-0 flex-1 overflow-y-auto p-3 ${haiCot ? 'max-h-[calc(100svh-9rem)]' : ''}`}
        >
          {dangChay && (
            <p role="status" className="m-0 text-[0.9375rem] text-muc-nhat">
              Đang mở nguyên văn…
            </p>
          )}

          {loi !== null && (
            <BaoLoi
              loi={loi}
              onThuLai={() => {
                void chay((signal) => layVanBanQuanhDieu(docId, khopTaiId, signal));
              }}
            />
          )}

          {ketQua !== null && (
            <>
              {khongDinhVi && (
                <p className="mt-0 mb-3 text-[0.8125rem] leading-5 text-muc-nhat">
                  Không định vị được câu trích trong nguyên văn bên dưới, nên chưa đánh dấu. Câu
                  trích hệ thống dẫn: “{quote}”
                </p>
              )}

              {/* Mặt phim: nền sáng, chữ serif, nguyên văn không rút gọn. */}
              <div className="rounded-vua p-3" style={{ background: 'var(--phim)' }}>
                {nhom.map((khoi, i) => (
                  <section
                    key={khoi.dieu?.id ?? khoi.con[0]?.id ?? i}
                    data-vung-tam={khoi.laTam ? 'true' : undefined}
                    data-roi={khoi.laTam && daRoi ? 'true' : 'false'}
                    className={`rounded-vua px-2 py-1 ${khoi.laTam ? 'vung-roi-sang' : 'ngoai-vung-roi'}`}
                  >
                    {khoi.dieu !== null && (
                      <>
                        <DuongDan duongDan={khoi.dieu.duong_dan} trenPhim className="mt-2 mb-1" />
                        <DongNguyenVan
                          dieuKhoan={khoi.dieu}
                          quote={khoi.dieu.id === khopTaiId ? quote : null}
                        />
                      </>
                    )}
                    {khoi.con.map((dieuKhoan) => (
                      <DongNguyenVan
                        key={dieuKhoan.id}
                        dieuKhoan={dieuKhoan}
                        quote={dieuKhoan.id === khopTaiId ? quote : null}
                      />
                    ))}
                  </section>
                ))}
              </div>

              <p className="mt-3 mb-0 text-[0.75rem] leading-5 text-muc-nhat">
                Hiển thị Điều được dẫn cùng 2 Điều liền trước và liền sau. Nguyên văn lấy từ CSDL,
                không rút gọn, không sửa chính tả.
              </p>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
