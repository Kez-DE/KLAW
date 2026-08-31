import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { layPhamVi } from '../../lib/api';
import type { PhamViResponse } from '../../lib/api';
import { useGoiApi } from '../../lib/hooks';
import { BaoLoi } from '../BaoLoi';

/**
 * Câu hỏi thường gặp ở `/bang-gia` — bộ sáu câu của BUILD-SPEC §15.6.
 *
 * Spec để TRỐNG câu 2 và câu 4 có chủ đích: *"Không viết câu trả lời khi chưa
 * chốt nguồn."* Hai câu được xử lý khác nhau, vì tình trạng của chúng khác
 * nhau:
 *
 *   - **Câu 2 (nguồn dữ liệu)** — CHỐT ĐƯỢC, nên trả lời, bằng sự thật đo được
 *     của dự án. Nói ra rằng corpus là văn bản gốc chứ không phải bản hợp nhất,
 *     và rằng Cơ sở dữ liệu quốc gia đánh sai hiệu lực bốn nghị định lương tối
 *     thiểu, làm sản phẩm đáng tin hơn chứ không kém đi: nó cho thấy hệ thống
 *     biết giới hạn của chính nguồn nó dùng. Con số phạm vi lấy từ
 *     `GET /api/v1/pham-vi`, KHÔNG viết cứng.
 *   - **Câu 4 (dữ liệu huấn luyện)** — CHƯA CÓ chính sách, nên vẫn là một câu
 *     hỏi chưa có câu trả lời. Viết "chúng tôi không dùng dữ liệu của bạn" khi
 *     chưa có chính sách nào là đúng loại hứa hộ mà §17 của chính spec cảnh
 *     báo, và là câu khách hàng doanh nghiệp sẽ kiểm lại đầu tiên.
 *
 * Câu 5 và câu 6 CÓ sẵn đáp án trong spec nhưng đáp án đó SAI với hệ thống
 * này; chúng được viết lại theo hiện trạng — xem chú thích tại chỗ.
 *
 * Cố ý KHÔNG có JSON-LD `FAQPage` ở đây: hai trong sáu mục không phải câu trả
 * lời, và đánh dấu một câu "chưa có chính sách" thành `acceptedAnswer` là nói
 * với công cụ tìm kiếm một điều không đúng.
 */

function So({ gia }: { gia: number }) {
  return <strong className="font-dia-chi font-medium">{gia.toLocaleString('vi-VN')}</strong>;
}

/** Câu 2 — nguồn dữ liệu và cách cập nhật. Số liệu từ API, không viết cứng. */
function NguonDuLieu() {
  const { dangChay, ketQua, loi, chay } = useGoiApi<PhamViResponse>();

  useEffect(() => {
    void chay((signal) => layPhamVi(signal));
  }, [chay]);

  return (
    <>
      <p className="mat-doc mt-0 text-phim">
        Nguồn duy nhất là <strong className="font-medium">Cơ sở dữ liệu quốc gia về văn bản pháp
        luật</strong> — cổng của Bộ Tư pháp. Không lấy từ trang tổng hợp của bên thứ ba.
      </p>

      {dangChay && (
        <p role="status" className="mat-doc mt-3 text-muc-nhat">
          Đang đếm corpus từ cơ sở dữ liệu…
        </p>
      )}

      {!dangChay && loi !== null && (
        <BaoLoi
          loi={{
            kind: loi.kind,
            message: 'Chưa lấy được số liệu phạm vi, nên câu trả lời này không nêu con số nào.',
            status: loi.status,
          }}
          onThuLai={() => void chay((signal) => layPhamVi(signal))}
        />
      )}

      {!dangChay && ketQua !== null && (
        <p className="mat-doc mt-3 text-phim">
          Hiện có <So gia={ketQua.sau.so_van_ban} /> văn bản đọc được nguyên văn tới cấp điều khoản,
          gồm <So gia={ketQua.sau.so_dieu_khoan} /> điều khoản, cộng{' '}
          <So gia={ketQua.nong.so_van_ban} /> văn bản chỉ có số hiệu và tên. Hai con số này đọc
          thẳng từ cơ sở dữ liệu mỗi lần bạn mở trang.
        </p>
      )}

      <p className="mat-doc mt-3 text-phim">
        Corpus là <em>văn bản gốc</em>, không phải <em>bản hợp nhất</em>: trên cổng Bộ Tư pháp, mọi
        văn bản hợp nhất chỉ có bản PDF scan, không có toàn văn máy đọc được. Vì vậy hệ thống bảo
        đảm hai điều — trích dẫn đúng <strong className="font-medium">nguồn gốc</strong> và đúng{' '}
        <strong className="font-medium">nguyên văn</strong> — và{' '}
        <strong className="font-medium">không</strong> bảo đảm đây là{' '}
        <strong className="font-medium">bản hiện hành</strong> sau mọi lần sửa đổi.
      </p>

      <p className="mat-doc mt-3 text-phim">
        Về cập nhật, nói thẳng: corpus hiện được thu thập <em>một lần</em>, chưa có cơ chế cập nhật
        tự động theo ngày. Khi có, mốc cập nhật sẽ hiện ngay trên trang này.
      </p>

      <p className="mat-doc mt-3 text-phim">
        Một điều đáng nói ra hơn là giấu đi: chính Cơ sở dữ liệu quốc gia đánh dấu{' '}
        <strong className="font-medium">bốn nghị định về mức lương tối thiểu</strong> là còn hiệu lực
        dù chúng đã bị thay thế. KLAW phát hiện và sửa cả bốn. Nguồn chính thức cũng có sai sót, nên
        hãy đối chiếu trước khi hành động —{' '}
        <Link
          to="/pham-vi"
          className="underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
        >
          xem từng văn bản trong corpus
        </Link>
        .
      </p>
    </>
  );
}

interface MucHoi {
  hoi: string;
  dap: ReactNode;
}

const CAC_MUC: MucHoi[] = [
  {
    hoi: 'KLAW có thay thế luật sư không?',
    dap: (
      <p className="mat-doc mt-0 text-phim">
        Không. KLAW là công cụ hỗ trợ tra cứu và soạn thảo. Kết quả do KLAW tạo ra không phải ý kiến
        tư vấn pháp lý và cần được luật sư hoặc bộ phận pháp chế rà soát trước khi sử dụng cho mục
        đích ràng buộc.
      </p>
    ),
  },
  {
    hoi: 'Dữ liệu pháp luật của KLAW lấy từ đâu và cập nhật thế nào?',
    dap: <NguonDuLieu />,
  },
  {
    hoi: 'Câu trả lời của KLAW có thể sai không?',
    dap: (
      <p className="mat-doc mt-0 text-phim">
        Có. Mọi hệ thống AI đều có thể trả lời thiếu hoặc sai ngữ cảnh. Vì vậy KLAW hiển thị nguồn
        tới từng khoản, từng điểm để bạn đối chiếu trực tiếp với văn bản gốc. Khi không tìm được căn
        cứ rõ ràng, KLAW từ chối trả lời thay vì suy đoán.
      </p>
    ),
  },
  {
    hoi: 'Dữ liệu tôi nhập vào có được dùng để huấn luyện mô hình không?',
    dap: (
      <p className="mat-doc mt-0 text-phim">
        Chính sách này đang được hoàn thiện; sẽ công bố trước khi KLAW mở đăng ký. Đây là câu khách
        hàng doanh nghiệp hỏi đầu tiên và nó cần một câu trả lời dứt khoát, nên trang này không đưa
        ra một câu trả lời tạm trước khi chính sách được chốt.
      </p>
    ),
  },
  {
    // Spec §15.6 nêu "hợp đồng thương mại và dân sự, văn bản nội bộ doanh
    // nghiệp, văn bản tố tụng — hành chính". KHÔNG dùng: `/api/v1/mau/{loai}`
    // hiện chỉ có ba loại văn bản lao động, và corpus chỉ phủ cụm Lao động.
    hoi: 'KLAW soạn được những loại văn bản nào?',
    dap: (
      <p className="mat-doc mt-0 text-phim">
        Hiện có ba loại, đều thuộc cụm lao động: hợp đồng lao động, nội quy lao động, và quyết định
        kỷ luật lao động. Bản thảo trả về dưới dạng văn bản thuần, mỗi điều khoản kèm căn cứ pháp lý
        riêng. Các loại văn bản khác chưa có, vì corpus chưa phủ lĩnh vực của chúng.
      </p>
    ),
  },
  {
    // Spec §15.6 nêu "bản dùng thử 14 ngày, 20 lượt hỏi, 3 bản thảo". KHÔNG
    // dùng: chưa có tài khoản, chưa có hạn mức, chưa có thanh toán — nên chưa
    // có bản dùng thử nào để đặt điều kiện.
    hoi: 'Chi phí và giới hạn hiện tại là gì?',
    dap: (
      <p className="mat-doc mt-0 text-phim">
        Hiện KLAW dùng được ngay, không cần tài khoản, không thu phí và không áp hạn mức — vì chưa
        có hệ thống tài khoản hay thanh toán nào. Điều kiện dùng thử, hạn mức và điều khoản thanh
        toán sẽ công bố cùng lúc với giá chính thức.
      </p>
    ),
  },
];

export function HoiDapGia() {
  return (
    <ul className="mt-5 flex list-none flex-col gap-2.5 p-0">
      {CAC_MUC.map((muc) => (
        <li key={muc.hoi} className="tm-len">
          <details
            className="tm-hoi rounded-lon border"
            style={{ background: 'var(--nen-cao)', borderColor: 'var(--vien)' }}
          >
            <summary className="flex min-h-[var(--vung-cham-toi-thieu)] items-center justify-between gap-3 p-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang">
              <span className="mat-doc max-w-none font-medium text-phim">{muc.hoi}</span>
              <span
                aria-hidden="true"
                className="tm-dau font-dia-chi shrink-0 text-lg leading-none text-den-sang"
              />
            </summary>
            <div className="px-4 pb-4">{muc.dap}</div>
          </details>
        </li>
      ))}
    </ul>
  );
}
