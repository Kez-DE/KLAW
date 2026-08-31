import { useEffect } from 'react';
import { layPhamVi } from '../lib/api';
import type { PhamViResponse } from '../lib/api';
import { useGoiApi } from '../lib/hooks';
import { BaoLoi } from '../components/BaoLoi';

/**
 * Read. Cấu trúc corpus (tên Bộ luật, cụm Lao động, danh sách không phủ) là
 * QUYẾT ĐỊNH PHẠM VI của sản phẩm — chép từ PRODUCT.md, ổn định. Con số đo
 * được (số văn bản, số điều khoản) KHÔNG được viết cứng: lấy từ
 * GET /api/v1/pham-vi, endpoint chưa tồn tại tính đến lúc trang này được
 * dựng — 404 thì hiện trạng thái trung thực, không suy đoán số (site-spec.md).
 */

const SAU_BO_LUAT = [
  'Bộ luật Dân sự',
  'Bộ luật Tố tụng dân sự',
  'Bộ luật Tố tụng hình sự',
  'Bộ luật Hình sự',
  'Bộ luật Hàng hải',
  'Bộ luật Lao động',
];

const KHONG_PHU = [
  'thuế',
  'đất đai',
  'hôn nhân gia đình',
  'doanh nghiệp',
  'đầu tư',
  'sở hữu trí tuệ',
];

export default function PhamVi() {
  const { dangChay, ketQua, loi, chay } = useGoiApi<PhamViResponse>();

  useEffect(() => {
    void chay((signal) => layPhamVi(signal));
  }, [chay]);

  return (
    <div className="mx-auto w-full max-w-[46rem] px-4 py-10">
      <h1 className="mat-doc text-2xl font-semibold text-phim focus:outline-2 focus:outline-den-sang focus:outline-offset-4 md:text-3xl">
        Phạm vi dữ liệu và giới hạn
      </h1>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">Corpus gồm những gì</h2>
        <p className="mat-doc mt-3 text-phim">
          Hệ thống phủ <strong className="font-medium">sáu Bộ luật</strong>: {SAU_BO_LUAT.join(', ')}.
          Ngoài ra còn một cụm văn bản dưới luật về Lao động: nghị định hướng dẫn thi hành, nghị
          định xử phạt vi phạm hành chính, an toàn vệ sinh lao động, tuổi nghỉ hưu, thời giờ làm
          việc, và các mức lương tối thiểu theo từng thời kỳ.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">Độ sâu không đều</h2>
        <p className="mat-doc mt-3 text-phim">
          Chỉ riêng lĩnh vực Lao động có đủ luật, nghị định, thông tư và chế tài. Năm Bộ luật còn
          lại — Dân sự, Tố tụng dân sự, Tố tụng hình sự, Hình sự, Hàng hải — chỉ có bản thân bộ
          luật, không có văn bản hướng dẫn đi kèm. Đừng hiểu nhầm rằng mọi lĩnh vực được phủ như
          nhau.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">Không phủ</h2>
        <p className="mat-doc mt-3 text-phim">
          Hệ thống không trả lời câu hỏi thuộc các lĩnh vực sau: {KHONG_PHU.join(', ')}. Những câu
          hỏi này sẽ ra kết quả <span className="dia-chi">out_of_scope</span>.
        </p>
      </section>

      <section className="mt-8" aria-label="Số liệu đo được">
        <h2 className="text-lg font-medium text-phim">Số liệu đo được</h2>
        {dangChay && <p className="mat-doc mt-3 text-muc-nhat">Đang lấy số liệu phạm vi…</p>}
        {!dangChay && loi !== null && (
          <div className="mt-3">
            <BaoLoi
              loi={{ kind: loi.kind, message: 'Chưa lấy được số liệu phạm vi.', status: loi.status }}
              onThuLai={() => void chay((signal) => layPhamVi(signal))}
            />
          </div>
        )}
        {!dangChay && ketQua !== null && (
          <ul className="mat-doc mt-3 list-disc space-y-1.5 ps-5 text-phim">
            <li>
              {(ketQua.sau.so_van_ban + ketQua.nong.so_van_ban).toLocaleString('vi-VN')} văn bản,{' '}
              {(ketQua.sau.so_dieu_khoan + ketQua.nong.so_dieu_khoan).toLocaleString('vi-VN')} điều
              khoản.
            </li>
            <li>
              {ketQua.sau.so_van_ban.toLocaleString('vi-VN')} văn bản có toàn văn — trả lời được
              thành <span className="dia-chi">answer</span>.
            </li>
            <li>
              {ketQua.nong.so_van_ban.toLocaleString('vi-VN')} văn bản chỉ có metadata, chưa có
              toàn văn — đây chính là nguồn sinh ra kết quả{' '}
              <span className="dia-chi">partial_coverage</span>, không phải một nhánh lỗi.
            </li>
          </ul>
        )}
      </section>
    </div>
  );
}
