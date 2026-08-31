import type { Provision } from '../../types';
import { DuongDan } from '../DuongDan';

/**
 * Nguyên văn Điều luật trên mặt phim — nền sáng, chữ serif, KHÔNG rút gọn,
 * KHÔNG sửa chính tả (DESIGN.md).
 *
 * `la_tam` áp cho Điều tâm VÀ mọi Khoản/Điểm con của nó, nên vùng rọi sáng là
 * cả một VÙNG chứ không phải một dòng. Các Điều lân cận mờ đi bằng `opacity`,
 * không bằng màu — chữ trên phim không bao giờ đổi màu theo trạng thái.
 *
 * Không có `<mark>` câu trích ở đây: một `Finding` chỉ dẫn tới một điều khoản
 * căn cứ, nó KHÔNG mang câu trích. Chỗ nào cần tô câu trích thì dùng
 * `KhungRoiSang` (màn Tra cứu), nơi `Citation.quote` là dữ liệu có thật.
 */

const LE_THEO_CAP: Record<string, string | undefined> = {
  dieu: '0rem',
  khoan: '1rem',
  diem: '2rem',
};

interface Khoi {
  laTam: boolean;
  dong: Provision[];
}

/** Gộp các dòng liên tiếp cùng trạng thái `la_tam` thành một khối. */
function tachTheoTam(provisions: Provision[]): Khoi[] {
  const khoi: Khoi[] = [];
  for (const dieuKhoan of provisions) {
    const cuoi = khoi[khoi.length - 1];
    if (cuoi !== undefined && cuoi.laTam === dieuKhoan.la_tam) cuoi.dong.push(dieuKhoan);
    else khoi.push({ laTam: dieuKhoan.la_tam, dong: [dieuKhoan] });
  }
  return khoi;
}

interface NguyenVanDieuProps {
  provisions: Provision[];
  /** true khi mọi dòng đều `la_tam` (dạng `?so_dieu=`): không có Điều lân cận
   *  nào để đối chiếu, nên không rọi đèn — rọi tất cả thì đèn hết nghĩa. */
  khongRoiDen?: boolean;
}

export function NguyenVanDieu({ provisions, khongRoiDen = false }: NguyenVanDieuProps) {
  return (
    <div className="rounded-vua p-3" style={{ background: 'var(--phim)' }}>
      {tachTheoTam(provisions).map((khoi) => (
        <section
          key={khoi.dong[0].id}
          data-vung-tam={khoi.laTam ? 'true' : undefined}
          data-roi={khoi.laTam && !khongRoiDen ? 'true' : 'false'}
          className={
            khongRoiDen
              ? 'px-2 py-1'
              : `rounded-vua px-2 py-1 ${khoi.laTam ? 'vung-roi-sang' : 'ngoai-vung-roi'}`
          }
        >
          {khoi.dong.map((dieuKhoan) => (
            <div key={dieuKhoan.id}>
              {dieuKhoan.cap === 'dieu' && (
                <DuongDan duongDan={dieuKhoan.duong_dan} trenPhim className="mt-2 mb-1" />
              )}
              <p
                className="chu-tren-phim my-2 text-[1rem] leading-[1.75] whitespace-pre-wrap"
                style={{ marginInlineStart: LE_THEO_CAP[dieuKhoan.cap] ?? '0rem' }}
              >
                {dieuKhoan.noi_dung.normalize('NFC')}
              </p>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
