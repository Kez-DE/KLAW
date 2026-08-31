import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { Nguon, TraCuuResponse } from '../types';
import { DaiKhung } from './DaiKhung';
import { DuongDan } from './DuongDan';

/**
 * Bốn `result_type`, bốn cách hiển thị — không thương lượng.
 *
 * `abstain` là hành vi ĐÚNG, được tính điểm trong đánh giá: một hệ thống thà
 * nói "tôi không đủ căn cứ" còn hơn bịa một điều luật. Nên nó mang màu TRUNG
 * TÍNH (`--xam-cho`), giọng bình thường, không icon lỗi, không đỏ, không rung.
 * Tô đỏ nó là giao diện tranh luận chống lại chính luận điểm của sản phẩm.
 *
 * Đỏ (`--do-thay`) chỉ dành cho luật đã bị thay thế.
 */

/** Phạm vi corpus, chép từ PRODUCT.md — không suy đoán thêm lĩnh vực nào. */
const SAU_BO_LUAT = [
  'Dân sự',
  'Tố tụng dân sự',
  'Tố tụng hình sự',
  'Hình sự',
  'Hàng hải',
  'Lao động',
];
const KHONG_PHU = ['thuế', 'đất đai', 'hôn nhân gia đình', 'doanh nghiệp', 'đầu tư', 'sở hữu trí tuệ'];

const GOI_Y_DIEN_DAT_LAI = [
  'Nêu rõ vai trò trong quan hệ lao động: người lao động hay người sử dụng lao động.',
  'Dùng từ ngữ của luật thay cho từ thông tục (ví dụ: "đơn phương chấm dứt hợp đồng lao động" thay cho "đuổi việc").',
  'Tách câu hỏi dài thành từng ý riêng, hỏi lần lượt.',
  'Nếu hỏi về một mức tiền cụ thể, nêu rõ năm áp dụng.',
];

function KhoiCanhBao({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null;
  return (
    <section
      aria-label="Cảnh báo hiệu lực"
      className="mt-4 rounded-vua border-s-2 py-2 ps-3"
      style={{ borderColor: 'var(--do-thay)', background: 'var(--nen-cao)' }}
    >
      <h3 className="m-0 text-[0.8125rem] leading-5 font-medium" style={{ color: 'var(--do-thay)' }}>
        Cảnh báo hiệu lực
      </h3>
      <ul className="mt-1 mb-0 list-disc ps-4 text-[0.875rem] leading-6 text-phim">
        {warnings.map((canhBao) => (
          <li key={canhBao}>{canhBao}</li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Văn bản chi phối câu hỏi — CHỈ `partial_coverage` điền `nguon[]`.
 *
 * Nhánh đó luôn có `citations: []` theo thiết kế, nên đây là thứ DUY NHẤT cho
 * phép mở được văn bản đang nói tới. `coverage_note` có nêu tên văn bản trong
 * văn xuôi, nhưng cạo chuỗi đó ra để dựng link là bịa một địa chỉ — mỗi liên
 * kết dưới đây đến từ `doc_id` server trả về, không từ phép đoán.
 *
 * Đây KHÔNG phải trích dẫn đã kiểm chứng: không có `quote`, không có nhãn hiệu
 * lực. Câu dẫn phải nói đúng như vậy.
 */
function KhoiNguon({ nguon }: { nguon: Nguon[] }) {
  if (nguon.length === 0) return null;
  return (
    <section aria-label="Văn bản chi phối câu hỏi" className="mt-4">
      <h3 className="m-0 text-[0.8125rem] leading-5 text-muc-nhat">
        Văn bản chi phối câu hỏi này — mở để tự đối chiếu
      </h3>
      <ul className="mt-2 mb-0 flex list-none flex-col gap-2 p-0">
        {nguon.map((vanBan) => (
          <li key={vanBan.doc_id}>
            <Link
              to={`/van-ban/${vanBan.doc_id}`}
              className="block min-h-[var(--vung-cham-toi-thieu)] rounded-vua border p-3 transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
              style={{ background: 'var(--nen-cao)', borderColor: 'var(--vien)' }}
            >
              <DuongDan soKyHieu={vanBan.so_ky_hieu} boLuat={vanBan.bo_luat} />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Nhắc miễn trừ — CHỈ ở nhánh `answer` (site-spec.md).
 *
 * Ba nhánh kia đã tự nói ra giới hạn của chúng: `abstain` nói không đủ căn cứ,
 * `partial_coverage` nói không diễn giải, `out_of_scope` nói ngoài phạm vi.
 * `answer` là nhánh DUY NHẤT đưa ra một khẳng định pháp lý — và cũng là nhánh
 * duy nhất người dùng có thể hành động theo mà không nhận ra corpus là văn bản
 * GỐC chứ không phải bản hợp nhất. Nhắc ở chân trang là không đủ: người ta đọc
 * câu trả lời rồi đóng tab.
 */
function NhacMienTru() {
  return (
    <p className="mt-6 mb-0 text-[0.8125rem] leading-5 text-muc-nhat">
      Câu trả lời dựa trên văn bản gốc, không phải bản hợp nhất — KLAW bảo đảm nguồn gốc và đúng
      nguyên văn, không bảo đảm đây là bản hiện hành.{' '}
      <Link
        to="/mien-tru"
        className="underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
      >
        Đọc miễn trừ trách nhiệm
      </Link>
      .
    </p>
  );
}

function MatDoc({ children }: { children: ReactNode }) {
  return <div className="mat-doc text-phim">{children}</div>;
}

interface ResultCardProps {
  ketQua: TraCuuResponse;
  /** Khung đang mở trong khung rọi sáng, hoặc null. */
  chiSoDangMo: number | null;
  onChonTrichDan: (chiSo: number) => void;
}

export function ResultCard({ ketQua, chiSoDangMo, onChonTrichDan }: ResultCardProps) {
  const {
    result_type: loai,
    answer,
    citations,
    nguon,
    warnings,
    coverage_note: ghiChuPhamVi,
  } = ketQua;

  if (loai === 'abstain') {
    return (
      <section aria-label="Kết quả tra cứu">
        <div
          className="rounded-lon border-s-2 py-3 ps-4"
          style={{ borderColor: 'var(--xam-cho)', background: 'var(--nen-cao)' }}
        >
          <MatDoc>
            <p className="m-0">Không tìm thấy căn cứ pháp lý cho câu hỏi này.</p>
            {ghiChuPhamVi !== null && (
              <p className="mt-2 mb-0 text-[0.9375rem] text-muc-nhat">{ghiChuPhamVi}</p>
            )}
          </MatDoc>
        </div>
        <div className="mt-4">
          <h3 className="m-0 text-[0.8125rem] leading-5 text-muc-nhat">Thử diễn đạt lại</h3>
          <ul className="mat-doc mt-1 mb-0 list-disc ps-5 text-phim">
            {GOI_Y_DIEN_DAT_LAI.map((goiY) => (
              <li key={goiY}>{goiY}</li>
            ))}
          </ul>
        </div>
        <KhoiCanhBao warnings={warnings} />
      </section>
    );
  }

  if (loai === 'out_of_scope') {
    return (
      <section aria-label="Kết quả tra cứu">
        <div
          className="rounded-lon border-s-2 py-3 ps-4"
          style={{ borderColor: 'var(--xam-cho)', background: 'var(--nen-cao)' }}
        >
          <MatDoc>
            <p className="m-0">Câu hỏi này nằm ngoài phạm vi của hệ thống.</p>
            {ghiChuPhamVi !== null && (
              <p className="mt-2 mb-0 text-[0.9375rem] text-muc-nhat">{ghiChuPhamVi}</p>
            )}
          </MatDoc>
        </div>
        <div className="mat-doc mt-4 text-phim">
          <p className="m-0 text-[0.9375rem]">
            Hệ thống phủ <strong className="font-medium">6 Bộ luật</strong>:{' '}
            {SAU_BO_LUAT.join(', ')} — cùng cụm văn bản dưới luật về Lao động (nghị định hướng
            dẫn, xử phạt, an toàn vệ sinh lao động, tuổi nghỉ hưu, thời giờ làm việc, lương tối
            thiểu).
          </p>
          <p className="mt-2 mb-0 text-[0.9375rem] text-muc-nhat">
            Không phủ: {KHONG_PHU.join(', ')}. Chiều sâu cũng không đều giữa các lĩnh vực: chỉ
            riêng Lao động có đủ luật, nghị định, thông tư và chế tài.
          </p>
        </div>
        <KhoiCanhBao warnings={warnings} />
      </section>
    );
  }

  if (loai === 'partial_coverage') {
    return (
      <section aria-label="Kết quả tra cứu">
        <div
          className="rounded-lon border-s-2 py-3 ps-4"
          style={{ borderColor: 'var(--vang-mo)', background: 'var(--nen-cao)' }}
        >
          <MatDoc>
            <p className="m-0 text-[0.9375rem] text-muc-nhat">
              Chỉ tìm được văn bản liên quan, chưa đủ căn cứ để diễn giải thành câu trả lời. Hệ
              thống KHÔNG diễn giải trong trường hợp này — văn bản gốc được nêu đích danh dưới
              đây để đối chiếu.
            </p>
            {ghiChuPhamVi !== null && <p className="mt-2 mb-0">{ghiChuPhamVi}</p>}
          </MatDoc>
        </div>
        <KhoiCanhBao warnings={warnings} />
        <KhoiNguon nguon={nguon} />
        {/* Backend hiện luôn trả citations rỗng ở nhánh này (assemble.py::_base
            không gắn citation cho partial_coverage), nên dải khung tự ẩn. Giữ
            lời gọi để ngày endpoint kèm trích dẫn thì màn hình có sẵn chỗ, chứ
            KHÔNG dựng link giả từ chuỗi coverage_note. */}
        <DaiKhung
          citations={citations}
          chiSoDangMo={chiSoDangMo}
          onChon={onChonTrichDan}
          warnings={warnings}
        />
      </section>
    );
  }

  // result_type === 'answer'
  return (
    <section aria-label="Kết quả tra cứu">
      <MatDoc>
        {answer === null || answer === '' ? (
          <p className="m-0 text-muc-nhat">
            Máy chủ trả về trạng thái có căn cứ nhưng không kèm nội dung câu trả lời. Đọc nguyên
            văn các trích dẫn bên dưới.
          </p>
        ) : (
          answer
            .split('\n')
            .filter((doan) => doan.trim() !== '')
            .map((doan, i) => (
              <p key={`${i}-${doan.slice(0, 24)}`} className={i === 0 ? 'm-0' : 'mt-3 mb-0'}>
                {doan}
              </p>
            ))
        )}
      </MatDoc>
      <KhoiCanhBao warnings={warnings} />
      <DaiKhung
        citations={citations}
        chiSoDangMo={chiSoDangMo}
        onChon={onChonTrichDan}
        warnings={warnings}
      />
      <NhacMienTru />
    </section>
  );
}
