import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { layMau, soanThao } from '../lib/api';
import { useGoiApi, useHaiCot } from '../lib/hooks';
import type { FactField, LoaiVanBan, MauResponse, SoanThaoResponse } from '../types';
import { BaoLoi } from '../components/BaoLoi';
import { TrangThaiCho } from '../components/TrangThaiCho';
import { FormFacts } from '../components/soan-thao/FormFacts';
import { VanBanKetQua } from '../components/soan-thao/VanBanKetQua';
import { BaoCaoSoat } from '../components/soat/BaoCaoSoat';
import { KhungCanCu } from '../components/soat/KhungCanCu';

/**
 * Soạn thảo — nhập thông tin, máy sinh văn bản, rồi TỰ SOÁT chính văn bản đó
 * bằng cùng bộ quy tắc dùng cho văn bản bên ngoài.
 *
 * Form dựng từ `GET /api/v1/mau/{loai}`; không một trường nào được chép cứng
 * vào file này.
 */

interface LuaChonLoai {
  giaTri: LoaiVanBan;
  nhan: string;
}

// Ba giá trị của `LoaiVanBan` (src/models/schemas.py). Đây là ENUM của hợp
// đồng API, không phải nội dung sinh từ dữ liệu — còn nội dung của từng loại
// thì đến từ `/mau`, và hai loại dưới cùng hiện đang RỖNG. Chúng vẫn được
// liệt kê: giấu đi thì người dùng không bao giờ biết KLAW chưa làm gì.
const CAC_LOAI: LuaChonLoai[] = [
  { giaTri: 'hdld', nhan: 'Hợp đồng lao động' },
  { giaTri: 'noi_quy', nhan: 'Nội quy lao động' },
  { giaTri: 'quyet_dinh_ky_luat', nhan: 'Quyết định kỷ luật lao động' },
];

/**
 * Đổi giá trị ô nhập (luôn là chuỗi) sang kiểu server chờ.
 *
 * Ô trống bị BỎ HẲN khỏi `facts` thay vì gửi chuỗi rỗng: fact vắng mặt là một
 * input hợp lệ — rule engine trả "không kiểm được: thiếu …", một kết quả thật.
 * Gửi `""` sẽ biến nó thành một giá trị sai và nhận 422.
 */
function dungFacts(facts: FactField[], giaTri: Record<string, string>): Record<string, unknown> {
  const ra: Record<string, unknown> = {};
  for (const truong of facts) {
    const tho = (giaTri[truong.key] ?? '').trim();
    if (truong.kieu === 'bool') {
      ra[truong.key] = tho === 'true';
      continue;
    }
    if (tho === '') continue;
    if (truong.kieu === 'int') {
      ra[truong.key] = Number(tho);
      continue;
    }
    ra[truong.key] = tho;
  }
  return ra;
}

/** Chặn tại biên: một ô số không đọc được thì NÓI RA, không lặng lẽ bỏ đi. */
function oSoHong(facts: FactField[], giaTri: Record<string, string>): FactField | null {
  for (const truong of facts) {
    if (truong.kieu !== 'int') continue;
    const tho = (giaTri[truong.key] ?? '').trim();
    if (tho !== '' && !Number.isFinite(Number(tho))) return truong;
  }
  return null;
}

export default function SoanThao() {
  const [loai, datLoai] = useState<LoaiVanBan>('hdld');
  const [giaTri, datGiaTri] = useState<Record<string, string>>({});
  const [loiNhap, datLoiNhap] = useState<string | null>(null);
  const [chiSoDangMo, datChiSoDangMo] = useState<number | null>(null);
  const nutTraTieuDiem = useRef<number | null>(null);
  const haiCot = useHaiCot();

  const mau = useGoiApi<MauResponse>();
  const ketQua = useGoiApi<SoanThaoResponse>();
  const { chay: chayMau } = mau;
  const { chay: chayKetQua, datLai: datLaiKetQua } = ketQua;

  useEffect(() => {
    void chayMau((signal) => layMau(loai, signal));
  }, [chayMau, loai]);

  // Mẫu của lượt gọi TRƯỚC còn nằm trong state cho tới khi lượt mới xong —
  // đối chiếu `loai_van_ban` để không bao giờ dựng form của loại này bằng
  // trường của loại khác.
  const truongNhap: FactField[] | null =
    mau.ketQua !== null && mau.ketQua.loai_van_ban === loai ? mau.ketQua.facts : null;

  const doiLoai = (moi: LoaiVanBan) => {
    datLoai(moi);
    datGiaTri({});
    datLoiNhap(null);
    datChiSoDangMo(null);
    nutTraTieuDiem.current = null;
    datLaiKetQua();
  };

  const gui = (su: FormEvent<HTMLFormElement>) => {
    su.preventDefault();
    if (ketQua.dangChay) return;
    const hong = oSoHong(truongNhap ?? [], giaTri);
    if (hong !== null) {
      datLoiNhap(`Ô “${hong.nhan}” chưa phải một con số đọc được.`);
      return;
    }
    datLoiNhap(null);
    datChiSoDangMo(null);
    nutTraTieuDiem.current = null;
    void chayKetQua((signal) =>
      soanThao({ loai_van_ban: loai, facts: dungFacts(truongNhap ?? [], giaTri) }, signal),
    );
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
    ketQua.ketQua !== null && chiSoDangMo !== null
      ? (ketQua.ketQua.audit_report.findings[chiSoDangMo] ?? null)
      : null;
  const docId = phatHienDangMo?.doc_id ?? null;
  const khopTaiId = phatHienDangMo?.khop_tai_id ?? null;
  const panelMo = docId !== null && khopTaiId !== null;

  const cotChinh = (
    <div className="min-w-0">
      <h1 className="mat-doc m-0 text-[1.5rem] leading-9 font-medium text-phim focus:outline-2 focus:outline-offset-4 focus:outline-den-sang">
        Soạn thảo văn bản
      </h1>
      <p className="mat-doc mt-2 mb-6 text-[0.9375rem] text-muc-nhat">
        Máy sinh văn bản từ thông tin bạn nhập, rồi tự soát chính văn bản đó bằng bộ quy tắc pháp
        lý — mỗi phát hiện đều mở được nguyên văn điều luật làm căn cứ.
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
                  name="loai-van-ban"
                  value={lua.giaTri}
                  checked={loai === lua.giaTri}
                  onChange={() => doiLoai(lua.giaTri)}
                  disabled={ketQua.dangChay}
                  className="size-5 shrink-0 accent-[var(--den-sang)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
                />
                {lua.nhan}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="mt-6">
          {mau.dangChay && truongNhap === null && (
            <p role="status" className="m-0 text-[0.9375rem] text-muc-nhat">
              Đang tải danh sách thông tin cần nhập…
            </p>
          )}

          {mau.loi !== null && (
            <BaoLoi
              loi={mau.loi}
              onThuLai={() => {
                void chayMau((signal) => layMau(loai, signal));
              }}
            />
          )}

          {truongNhap !== null && truongNhap.length === 0 && (
            <div
              className="rounded-lon border-s-2 py-3 ps-4"
              style={{ borderColor: 'var(--vang-mo)', background: 'var(--nen-cao)' }}
            >
              <p className="mat-doc m-0 text-[0.9375rem] text-phim">
                Loại văn bản này chưa có nội dung pháp lý trong hệ thống.
              </p>
              <p className="mat-doc mt-2 mb-0 text-[0.875rem] text-muc-nhat">
                KLAW mới xây danh mục nội dung bắt buộc và bộ quy tắc cho hợp đồng lao động. Nội
                quy lao động và quyết định kỷ luật cần một nghiên cứu pháp lý riêng — nội dung bắt
                buộc của chúng hoàn toàn khác Điều 21 Bộ luật Lao động. Máy chủ sẽ từ chối yêu cầu
                thay vì soạn bằng danh mục của hợp đồng lao động.
              </p>
            </div>
          )}

          {truongNhap !== null && truongNhap.length > 0 && (
            <>
              <FormFacts
                facts={truongNhap}
                giaTri={giaTri}
                voHieu={ketQua.dangChay}
                onDoi={(key, moi) => datGiaTri((cu) => ({ ...cu, [key]: moi }))}
              />
              <p className="mt-3 mb-0 text-[0.8125rem] leading-5 text-muc-nhat">
                Bỏ trống một ô là hợp lệ: báo cáo soát sẽ ghi rõ quy tắc nào chưa kiểm được vì
                thiếu thông tin, thay vì đoán thay bạn.
              </p>
            </>
          )}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={ketQua.dangChay || truongNhap === null}
            className="min-h-[var(--vung-cham-toi-thieu)] cursor-pointer rounded-vua px-5 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang disabled:cursor-not-allowed disabled:opacity-45"
            style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
          >
            Soạn văn bản
          </button>
          <p className="m-0 text-[0.75rem] leading-5 text-muc-nhat">
            Một lượt soạn thảo mất 10–60 giây.
          </p>
        </div>

        {loiNhap !== null && (
          <p role="alert" className="mt-3 mb-0 text-[0.875rem] leading-6 text-phim">
            {loiNhap}
          </p>
        )}
      </form>

      <p role="status" className="sr-only">
        {ketQua.dangChay
          ? 'Đang soạn thảo.'
          : ketQua.ketQua !== null
            ? `Đã soạn xong văn bản, báo cáo tự soát có ${ketQua.ketQua.audit_report.findings.length} phát hiện.`
            : ketQua.loi !== null
              ? ketQua.loi.message
              : ''}
      </p>

      {ketQua.dangChay && <TrangThaiCho onHuy={ketQua.huy} />}

      {!ketQua.dangChay && ketQua.loi !== null && <BaoLoi loi={ketQua.loi} />}

      {!ketQua.dangChay && ketQua.ketQua !== null && (
        <div className="mt-8 flex flex-col gap-8">
          <VanBanKetQua document={ketQua.ketQua.document} />
          <BaoCaoSoat
            baoCao={ketQua.ketQua.audit_report}
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
        {/* Một cột: panel là lớp phủ toàn màn hình, phần dưới nó phải ngừng
            nhận tiêu điểm — `inert` là cách gốc của trình duyệt. */}
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
