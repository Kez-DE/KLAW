import { Link } from 'react-router-dom';
import { BadgeHieuLuc } from '../components/BadgeHieuLuc';

/**
 * Read — cột hẹp, phân cấp rõ, không hiệu ứng (site-spec.md). Nội dung thật
 * sự là hỏi-đáp nên JSON-LD FAQPage ở cuối file là hợp lệ, không phải đánh
 * dấu sai kiểu để lấy rich result (site-spec.md, mục SEO).
 */

interface MucHoiDap {
  hoi: string;
  /** Bản tóm tắt bằng chữ thường, dùng cho cả JSON-LD lẫn phần mở đầu hiển thị. */
  dapTom: string;
}

const CAC_MUC: MucHoiDap[] = [
  {
    hoi: 'Làm sao để đặt câu hỏi cho ra kết quả tốt?',
    dapTom:
      'Nêu rõ vai trò của mình, dùng từ ngữ của luật khi có thể, hỏi từng ý một, nêu rõ năm áp dụng khi hỏi về một mức tiền cụ thể, và giữ câu hỏi trong phạm vi sáu Bộ luật cùng cụm văn bản Lao động.',
  },
  {
    hoi: 'Bốn loại kết quả (result_type) nghĩa là gì?',
    dapTom:
      'answer là có căn cứ và đã qua kiểm chứng; partial_coverage là chỉ tìm được văn bản liên quan nhưng không đủ căn cứ để diễn giải; abstain là không tìm thấy căn cứ pháp lý — một câu trả lời HỢP LỆ, không phải lỗi; out_of_scope là câu hỏi nằm ngoài phạm vi hệ thống.',
  },
  {
    hoi: 'Nhãn hiệu lực trên mỗi trích dẫn nghĩa là gì?',
    dapTom:
      'Chấm xanh không kèm chữ là còn hiệu lực. Viền đỏ kèm tên văn bản thay thế là đã bị thay thế hoặc hết hiệu lực. Viền vàng là một phần không xác định vì cơ sở dữ liệu quốc gia không công bố dữ liệu ở cấp điều khoản đó. Chấm xám kèm "cần đối chiếu tay" là trường hợp hệ thống không tự xác định được.',
  },
  {
    hoi: 'Vì sao một lượt tra cứu mất 10–60 giây?',
    dapTom:
      'Mỗi câu hỏi có thể gọi mô hình ngôn ngữ tối đa năm lần, qua các bước tìm văn bản, mở rộng điều khoản, kiểm chứng trích dẫn và dựng câu trả lời — mỗi bước đều kiểm tra để bảo đảm trích dẫn có thật trước khi hiển thị.',
  },
  {
    hoi: 'Soạn thảo và Soát dùng để làm gì?',
    dapTom:
      'Soạn thảo sinh hợp đồng lao động, nội quy lao động hoặc quyết định kỷ luật từ thông tin bạn nhập vào, mỗi điều khoản kèm căn cứ pháp lý riêng. Soát nhận một văn bản có sẵn và trả về danh sách phát hiện, mỗi phát hiện neo vào một điều luật cụ thể.',
  },
];

const JSON_LD_HOI_DAP = JSON.stringify({
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: CAC_MUC.map((muc) => ({
    '@type': 'Question',
    name: muc.hoi,
    acceptedAnswer: { '@type': 'Answer', text: muc.dapTom },
  })),
});

export default function HuongDan() {
  return (
    <div className="mx-auto w-full max-w-[46rem] px-4 py-10">
      <h1 className="mat-doc text-2xl font-semibold text-phim focus:outline-2 focus:outline-den-sang focus:outline-offset-4 md:text-3xl">Hướng dẫn sử dụng</h1>
      <p className="mat-doc mt-3 text-muc-nhat">
        Cách hỏi cho ra kết quả tốt, cách đọc nhãn hiệu lực, ý nghĩa của bốn loại kết quả, và cách
        dùng hai công cụ Soạn thảo và Soát.
      </p>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">{CAC_MUC[0].hoi}</h2>
        <ul className="mat-doc mt-3 list-disc space-y-1.5 ps-5 text-phim">
          <li>Nêu rõ mình là người lao động hay người sử dụng lao động.</li>
          <li>
            Dùng từ ngữ của luật khi có thể (ví dụ{' '}
            <span className="dia-chi">"đơn phương chấm dứt hợp đồng lao động"</span> thay cho{' '}
            <span className="dia-chi">"bị đuổi việc"</span>) — câu hỏi bằng lời thường vẫn trả lời
            được, nhưng từ đúng giúp hệ thống tìm chính xác hơn.
          </li>
          <li>Hỏi từng ý một; một câu hỏi gộp nhiều tình huống dễ ra kết quả không đủ căn cứ.</li>
          <li>Nếu hỏi về một mức tiền hoặc mức phạt cụ thể, nêu rõ năm áp dụng.</li>
          <li>
            Giữ câu hỏi trong phạm vi hệ thống phủ — xem{' '}
            <Link
              to="/pham-vi"
              className="underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
            >
              Phạm vi dữ liệu
            </Link>
            .
          </li>
        </ul>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">{CAC_MUC[1].hoi}</h2>
        <dl className="mat-doc mt-3 text-phim">
          <div className="mt-3 first:mt-0">
            <dt className="dia-chi text-[0.8125rem] font-medium" style={{ color: 'var(--den-sang)' }}>
              answer
            </dt>
            <dd className="mt-1">
              Có căn cứ, đã qua kiểm chứng hai tầng — câu trả lời hiển thị kèm trích dẫn bấm được.
            </dd>
          </div>
          <div className="mt-3">
            <dt className="dia-chi text-[0.8125rem] font-medium" style={{ color: 'var(--den-sang)' }}>
              partial_coverage
            </dt>
            <dd className="mt-1">
              Hệ thống chỉ tìm được văn bản liên quan, chưa đủ căn cứ để diễn giải — nên KHÔNG bịa
              câu trả lời. Văn bản gốc được nêu đích danh để tự đối chiếu.
            </dd>
          </div>
          <div className="mt-3">
            <dt className="dia-chi text-[0.8125rem] font-medium" style={{ color: 'var(--xam-cho)' }}>
              abstain
            </dt>
            <dd className="mt-1">
              "Không tìm thấy căn cứ pháp lý cho câu hỏi này." Đây là câu trả lời{' '}
              <strong className="font-medium">hợp lệ</strong>, không phải lỗi — hệ thống thà từ
              chối còn hơn bịa một điều luật không có thật.
            </dd>
          </div>
          <div className="mt-3">
            <dt className="dia-chi text-[0.8125rem] font-medium" style={{ color: 'var(--xam-cho)' }}>
              out_of_scope
            </dt>
            <dd className="mt-1">
              Câu hỏi nằm ngoài phạm vi hệ thống (ví dụ thuế, đất đai, hôn nhân gia đình).
            </dd>
          </div>
        </dl>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">{CAC_MUC[2].hoi}</h2>
        <p className="mat-doc mt-3 text-phim">
          Nhãn hiệu lực luôn thấy được ngay trên khung trích dẫn, không nằm trong tooltip:
        </p>
        <ul className="mt-3 space-y-3">
          <li className="flex flex-wrap items-center gap-3">
            <BadgeHieuLuc hieuLuc="con_hieu_luc" />
            <span className="mat-doc text-phim">còn hiệu lực</span>
          </li>
          <li className="flex flex-wrap items-center gap-3">
            <BadgeHieuLuc hieuLuc="bi_thay_the" />
            <span className="mat-doc text-phim">
              đã bị thay thế — luôn kèm câu nêu đích danh văn bản thay thế
            </span>
          </li>
          <li className="flex flex-wrap items-center gap-3">
            <BadgeHieuLuc hieuLuc="mot_phan_khong_xac_dinh" />
            <span className="mat-doc text-phim">một phần không xác định</span>
          </li>
          <li className="flex flex-wrap items-center gap-3">
            <BadgeHieuLuc hieuLuc="can_doi_chieu_tay" />
            <span className="mat-doc text-phim">cần đối chiếu tay</span>
          </li>
        </ul>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">{CAC_MUC[3].hoi}</h2>
        <p className="mat-doc mt-3 text-phim">{CAC_MUC[3].dapTom}</p>
        <p className="mat-doc mt-2 text-muc-nhat">
          Đây là thời gian bình thường, không phải dấu hiệu lỗi. Màn hình Tra cứu hiện rõ bước nào
          đang chạy trong lúc chờ, và luôn có nút huỷ.
        </p>
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-phim">{CAC_MUC[4].hoi}</h2>
        <p className="mat-doc mt-3 text-phim">
          <Link
            to="/soan-thao"
            className="underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
          >
            Soạn thảo
          </Link>{' '}
          sinh hợp đồng lao động, nội quy lao động hoặc quyết định kỷ luật từ thông tin thực tế bạn
          nhập vào; mỗi điều khoản kèm căn cứ pháp lý riêng.
        </p>
        <p className="mat-doc mt-2 text-phim">
          <Link
            to="/soat"
            className="underline underline-offset-4 hover:text-phim focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
          >
            Soát
          </Link>{' '}
          nhận một văn bản có sẵn và trả về danh sách phát hiện; mỗi phát hiện neo vào một điều
          luật cụ thể, không phải nhận xét chung chung.
        </p>
      </section>

      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON_LD_HOI_DAP }} />
    </div>
  );
}
