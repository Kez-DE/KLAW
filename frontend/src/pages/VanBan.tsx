import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useParams } from 'react-router-dom';
import { layDieu, layMucLucVanBan } from '../lib/api';
import { useGoiApi, useHaiCot } from '../lib/hooks';
import type { CapMucLuc, VanBanAroundResponse, VanBanMucLucResponse } from '../types';
import { BaoLoi } from '../components/BaoLoi';
import { DuongDan } from '../components/DuongDan';
import { NguyenVanDieu } from '../components/soat/NguyenVanDieu';

/**
 * Một văn bản: mục lục Chương/Mục, và nguyên văn từng Điều mở theo yêu cầu.
 *
 * LAZY là ràng buộc cứng, không phải tối ưu: Bộ luật Dân sự có 689 Điều
 * (19.135 điều khoản trong toàn corpus). Trang này gọi
 * `GET /van-ban/{doc_id}` không tham số — chỉ metadata + danh mục Chương/Mục,
 * KHÔNG kéo nội dung Điều nào — rồi `?so_dieu=` cho đúng Điều người dùng mở.
 *
 * Vì sao Chương/Mục KHÔNG bấm được: mục lục trả `id` của Chương, nhưng không
 * endpoint nào liệt kê các Điều thuộc một Chương (`?around=<id Chương>` trả
 * 404 — "provision không thuộc Điều nào", đã thử trên dữ liệu thật). Suy id
 * Điều đầu tiên từ `id Chương + 1` thì "đúng" trên dữ liệu hôm nay và sai
 * lặng lẽ ở lần seed sau — đúng loại khẳng định không kiểm chứng được mà dự
 * án này tồn tại để chống. Nên mục lục ở đây là cấu trúc để đọc, và ô "Mở
 * Điều" là đường đi thật tới nguyên văn.
 */

const LE_THEO_CAP: Record<CapMucLuc, string> = {
  phan: '0rem',
  chuong: '0rem',
  muc: '1rem',
  tieu_muc: '2rem',
};

export default function VanBan() {
  const { docId } = useParams<{ docId: string }>();
  const [soDieu, datSoDieu] = useState('');
  const haiCot = useHaiCot();

  const mucLuc = useGoiApi<VanBanMucLucResponse>();
  const dieu = useGoiApi<VanBanAroundResponse>();
  const { chay: chayMucLuc } = mucLuc;
  const { chay: chayDieu, datLai: datLaiDieu } = dieu;

  useEffect(() => {
    if (docId === undefined) return;
    void chayMucLuc((signal) => layMucLucVanBan(docId, signal));
  }, [chayMucLuc, docId]);

  // `lib/useTieuDeTrang.ts` (ngoài phạm vi task này) chưa biết tuyến
  // `/van-ban/:docId`, nên nó đặt tiêu đề thành "Không tìm thấy trang". Đặt
  // lại bằng ĐỊNH DANH thật sau khi metadata về — effect này luôn chạy sau
  // effect của App vì nó chờ một lượt fetch.
  const soKyHieu = mucLuc.ketQua?.so_ky_hieu;
  useEffect(() => {
    if (soKyHieu === undefined) return;
    document.title = `${soKyHieu} — KLAW`;
    const vungThongBao = document.getElementById('thong-bao-chuyen-trang');
    if (vungThongBao !== null) vungThongBao.textContent = `Đã chuyển đến văn bản ${soKyHieu}`;
  }, [soKyHieu]);

  const moDieu = (su: FormEvent<HTMLFormElement>) => {
    su.preventDefault();
    const sach = soDieu.trim();
    if (sach === '' || docId === undefined || dieu.dangChay) return;
    void chayDieu((signal) => layDieu(docId, sach, signal));
  };

  if (docId === undefined) return null;

  const khungMucLuc = (
    <div className="min-w-0">
      <h1 className="mat-doc m-0 text-[1.5rem] leading-9 font-medium text-phim focus:outline-2 focus:outline-offset-4 focus:outline-den-sang">Văn bản</h1>

      {mucLuc.dangChay && (
        <p role="status" className="mt-4 mb-0 text-[0.9375rem] text-muc-nhat">
          Đang tải mục lục…
        </p>
      )}

      {mucLuc.loi !== null && (
        <BaoLoi
          loi={mucLuc.loi}
          onThuLai={() => {
            void chayMucLuc((signal) => layMucLucVanBan(docId, signal));
          }}
        />
      )}

      {mucLuc.ketQua !== null && (
        <>
          <div
            className="mt-4 rounded-lon border p-4"
            style={{ background: 'var(--nen-cao)', borderColor: 'var(--vien)' }}
          >
            <DuongDan soKyHieu={mucLuc.ketQua.so_ky_hieu} boLuat={mucLuc.ketQua.bo_luat} />
          </div>

          {mucLuc.ketQua.muc_luc.length === 0 ? (
            <div
              className="mt-4 rounded-lon border-s-2 py-3 ps-4"
              style={{ borderColor: 'var(--vang-mo)', background: 'var(--nen-cao)' }}
            >
              {/* `muc_luc` rỗng KHÔNG chứng minh văn bản thiếu toàn văn: đo
                  trên corpus thật, 8 trong 21 văn bản CÓ đủ điều khoản vẫn trả
                  mục lục rỗng vì chúng đánh số thẳng theo Điều (293/2025/NĐ-CP
                  có 30 điều khoản, mục lục rỗng). Nói "chưa có toàn văn" ở đây
                  là một khẳng định không kiểm chứng được — nêu đúng hai khả
                  năng và chỉ ra cách người dùng tự xác minh. */}
              <p className="mat-doc m-0 text-[0.9375rem] text-phim">
                Văn bản này không có danh mục Chương/Mục.
              </p>
              <p className="mat-doc mt-2 mb-0 text-[0.875rem] text-muc-nhat">
                Hoặc vì nó đánh số thẳng theo Điều — nghị định và thông tư thường vậy — hoặc vì hệ
                thống mới nạp metadata chứ chưa nạp toàn văn. Mở thử một Điều theo số để biết
                chắc: không Điều nào mở được thì đây là trường hợp thứ hai.
              </p>
            </div>
          ) : (
            <>
              <h2 className="mt-8 mb-2 text-[1rem] leading-6 font-medium text-phim">Mục lục</h2>
              <p className="mt-0 mb-3 text-[0.8125rem] leading-5 text-muc-nhat">
                Danh mục Chương và Mục. Nội dung từng Điều chỉ được tải khi bạn mở, để không kéo
                cả cây điều khoản về máy.
              </p>
              <ol className="m-0 flex list-none flex-col gap-1 p-0">
                {mucLuc.ketQua.muc_luc.map((muc) => (
                  <li
                    key={muc.id}
                    className="text-[0.875rem] leading-6 text-phim"
                    style={{ marginInlineStart: LE_THEO_CAP[muc.cap] }}
                  >
                    {muc.tieu_de}
                  </li>
                ))}
              </ol>
            </>
          )}
        </>
      )}
    </div>
  );

  const khungDieu = (
    // Giới hạn bề rộng đọc: nguyên văn là văn xuôi để ĐỌC, dòng dài hết màn
    // hình 1440px thì mắt lạc dòng (DESIGN.md — tối đa 68 ký tự ở mặt đọc).
    <div className="min-w-0 max-w-[46rem]">
      <form onSubmit={moDieu} className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <label htmlFor="so-dieu" className="mb-1 block text-[0.875rem] leading-6 text-phim">
            Mở Điều số
          </label>
          <input
            id="so-dieu"
            name="so-dieu"
            value={soDieu}
            disabled={dieu.dangChay}
            onChange={(su) => datSoDieu(su.target.value)}
            // Ô CHỮ, không phải ô số: số hiệu Điều trong luật Việt Nam có dạng
            // "27a" (điều được thêm bằng luật sửa đổi). Ô số sẽ chặn đúng những
            // Điều mới nhất.
            inputMode="text"
            placeholder="ví dụ: 21, hoặc 27a"
            className="block w-full rounded-vua border p-2 text-[0.9375rem] text-phim placeholder:text-muc-nhat focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang disabled:opacity-50"
            style={{
              background: 'var(--nen-cao)',
              borderColor: 'color-mix(in srgb, var(--muc-nhat) 55%, transparent)',
              minHeight: 'var(--vung-cham-toi-thieu)',
            }}
          />
        </div>
        <button
          type="submit"
          disabled={soDieu.trim() === '' || dieu.dangChay}
          className="min-h-[var(--vung-cham-toi-thieu)] cursor-pointer rounded-vua px-5 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang disabled:cursor-not-allowed disabled:opacity-45"
          style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
        >
          Mở
        </button>
      </form>

      <p role="status" className="sr-only">
        {dieu.dangChay
          ? 'Đang mở điều luật.'
          : dieu.ketQua !== null
            ? 'Đã mở nguyên văn điều luật.'
            : ''}
      </p>

      {dieu.dangChay && (
        <p className="mt-4 mb-0 text-[0.9375rem] text-muc-nhat">Đang mở nguyên văn…</p>
      )}

      {/* 404 ở đây có nghĩa đen: Điều đó không tồn tại trong văn bản này. Đó là
          một câu trả lời, không phải một sự cố — nên nó không mang khay lỗi. */}
      {!dieu.dangChay && dieu.loi !== null && dieu.loi.kind === 'not_found' && (
        <p className="mat-doc mt-4 mb-0 text-[0.9375rem] text-muc-nhat">
          Không có Điều “{soDieu.trim()}” trong văn bản này.
        </p>
      )}
      {!dieu.dangChay && dieu.loi !== null && dieu.loi.kind !== 'not_found' && (
        <BaoLoi loi={dieu.loi} />
      )}

      {!dieu.dangChay && dieu.ketQua !== null && (
        <div className="mt-4">
          <NguyenVanDieu provisions={dieu.ketQua.provisions} khongRoiDen />
          <div className="mt-3 flex flex-wrap items-center gap-4">
            <p className="m-0 text-[0.75rem] leading-5 text-muc-nhat">
              Nguyên văn lấy từ CSDL, không rút gọn, không sửa chính tả.
            </p>
            <button
              type="button"
              onClick={() => {
                datLaiDieu();
                datSoDieu('');
              }}
              className="min-h-[var(--vung-cham-toi-thieu)] cursor-pointer text-[0.875rem] text-muc-nhat underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
            >
              Đóng Điều này
            </button>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="mx-auto w-full max-w-[104rem] px-4 py-6">
      <div
        className={
          haiCot
            ? 'grid grid-cols-[minmax(0,26rem)_minmax(0,1fr)] items-start gap-8'
            : 'grid grid-cols-1 gap-8'
        }
      >
        {khungMucLuc}
        {khungDieu}
      </div>
    </div>
  );
}
