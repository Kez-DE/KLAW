import { catTheoTrichDan } from '../../lib/trichDan';
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
 * `quote` là TUỲ CHỌN, và đó là điểm mấu chốt: một `Citation` mang câu trích
 * thật nên tô sáng được; một `Finding` KHÔNG mang câu trích nào (`can_cu` chỉ
 * là địa chỉ điều luật, `dieu_khoan_lien_quan` là trích đoạn của văn bản ĐANG
 * SOÁT chứ không phải của luật). Không có quote thì mở đúng Điều và im lặng —
 * đúng ra là không nói gì về một câu trích chưa từng tồn tại.
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

interface DongNguyenVanProps {
  dieuKhoan: Provision;
  /** Câu trích cần đánh dấu; null ở mọi dòng KHÔNG phải dòng đã khớp. */
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

interface NguyenVanDieuProps {
  provisions: Provision[];
  /** true khi mọi dòng đều `la_tam` (dạng `?so_dieu=`): không có Điều lân cận
   *  nào để đối chiếu, nên không rọi đèn — rọi tất cả thì đèn hết nghĩa. */
  khongRoiDen?: boolean;
  /** Câu trích cần tô sáng. Bỏ trống = không có câu trích nào để tô. */
  quote?: string | null;
  /** Dòng mang câu trích (`Citation.khop_tai_id`) — chỉ dòng này được tô. */
  khopTaiId?: number;
  /** false ở khung hình đầu tiên: `opacity` cần một giá trị đầu để chuyển từ
   *  0 lên 1, nếu không quầng đèn bật sẵn thay vì sáng dần. */
  daRoi?: boolean;
}

export function NguyenVanDieu({
  provisions,
  khongRoiDen = false,
  quote = null,
  khopTaiId,
  daRoi = true,
}: NguyenVanDieuProps) {
  return (
    <div className="rounded-vua p-3" style={{ background: 'var(--phim)' }}>
      {tachTheoTam(provisions).map((khoi) => (
        <section
          key={khoi.dong[0].id}
          data-vung-tam={khoi.laTam ? 'true' : undefined}
          data-roi={khoi.laTam && !khongRoiDen && daRoi ? 'true' : 'false'}
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
              <DongNguyenVan
                dieuKhoan={dieuKhoan}
                quote={dieuKhoan.id === khopTaiId ? quote : null}
              />
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
