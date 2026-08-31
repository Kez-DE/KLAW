import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { layPhamVi } from '../../lib/api';
import type { PhamViResponse } from '../../lib/api';
import { useGoiApi } from '../../lib/hooks';
import { BaoLoi } from '../BaoLoi';

/**
 * Mục 4 của trang giới thiệu — "Phạm vi thật".
 *
 * Con số ĐO ĐƯỢC lấy từ `GET /api/v1/pham-vi`, không bao giờ viết cứng vào
 * JSX. Một con số viết cứng sẽ sai ngay lần seed tiếp theo, và một dự án tồn
 * tại để chống khẳng định không kiểm chứng được thì không được phép tự khẳng
 * định không kiểm chứng được (site-spec.md).
 *
 * Endpoint chưa được phục vụ thì mục này hiện trạng thái trung thực và một nút
 * thử lại — KHÔNG suy đoán số, KHÔNG giữ lại một con số cũ để lấp chỗ trống.
 */

function So({ gia }: { gia: number }) {
  return <strong className="font-dia-chi font-medium">{gia.toLocaleString('vi-VN')}</strong>;
}

export function PhamViThat() {
  const { dangChay, ketQua, loi, chay } = useGoiApi<PhamViResponse>();

  useEffect(() => {
    void chay((signal) => layPhamVi(signal));
  }, [chay]);

  return (
    <>
      <p className="mat-doc mt-3 text-phim">
        Corpus có <em>hai tầng</em>, và sự khác nhau giữa chúng là thứ quyết định bạn nhận được
        loại kết quả nào. Tầng sâu có toàn văn tới cấp Điều, Khoản, Điểm — đây là nơi câu trả lời
        kèm trích dẫn kiểm chứng được sinh ra. Tầng nông chỉ có thông tin nhận dạng văn bản, không
        có nội dung điều khoản; hỏi trúng nó thì máy nêu tên văn bản rồi dừng, và đó chính là
        kết quả <span className="dia-chi">partial_coverage</span>.
      </p>

      {dangChay && (
        <p role="status" className="mat-doc mt-4 text-muc-nhat">
          Đang đếm corpus từ cơ sở dữ liệu…
        </p>
      )}

      {!dangChay && loi !== null && (
        <BaoLoi
          loi={{
            kind: loi.kind,
            message: 'Chưa lấy được số liệu phạm vi, nên trang này không hiện con số nào.',
            status: loi.status,
          }}
          onThuLai={() => void chay((signal) => layPhamVi(signal))}
        />
      )}

      {!dangChay && ketQua !== null && (
        <dl className="mt-5 grid gap-3 sm:grid-cols-2">
          <div
            className="rounded-lon border p-4"
            style={{ background: 'var(--nen-cao)', borderColor: 'var(--vien)' }}
          >
            <dt className="text-[0.8125rem] leading-5 text-muc-nhat">Tầng sâu — có toàn văn</dt>
            <dd className="mat-doc mt-1 text-phim">
              <So gia={ketQua.sau.so_van_ban} /> văn bản, <So gia={ketQua.sau.so_dieu_khoan} /> điều
              khoản đọc được nguyên văn.
            </dd>
          </div>
          <div
            className="rounded-lon border p-4"
            style={{ background: 'var(--nen-cao)', borderColor: 'var(--vien)' }}
          >
            <dt className="text-[0.8125rem] leading-5 text-muc-nhat">Tầng nông — chỉ metadata</dt>
            <dd className="mat-doc mt-1 text-phim">
              <So gia={ketQua.nong.so_van_ban} /> văn bản chỉ có số hiệu và tên, không có điều khoản
              nào.
            </dd>
          </div>
        </dl>
      )}

      <p className="mat-doc mt-4 text-phim">
        Độ sâu <em>không đều</em> giữa các lĩnh vực: chỉ Lao động có đủ luật, nghị định, thông tư và
        chế tài. Năm Bộ luật còn lại chỉ có bản thân bộ luật, không có văn bản hướng dẫn đi kèm.
        Thuế, đất đai, hôn nhân gia đình, doanh nghiệp, đầu tư, sở hữu trí tuệ đều{' '}
        <em>không được phủ</em> — hỏi vào đó sẽ ra{' '}
        <span className="dia-chi">out_of_scope</span>, không phải một câu trả lời đoán mò.
      </p>

      <p className="mt-4">
        <Link
          to="/pham-vi"
          className="mat-doc inline-flex min-h-[var(--vung-cham-toi-thieu)] items-center text-den-sang underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        >
          Xem danh sách từng văn bản trong corpus
        </Link>
      </p>
    </>
  );
}
