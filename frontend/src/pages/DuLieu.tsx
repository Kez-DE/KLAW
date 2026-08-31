import { useTieuDeTrang } from '../lib/useTieuDeTrang';

/**
 * `/du-lieu` — BẢN KÊ dữ liệu, KHÔNG phải chính sách.
 *
 * Ô đồng ý ở `/dang-ky` dẫn chiếu "Chính sách bảo vệ dữ liệu cá nhân", mà chính
 * sách đó chưa tồn tại — agent dựng trang đó đã đúng khi không tạo một liên kết
 * chết và nói thẳng là đang hoàn thiện.
 *
 * Trang này KHÔNG lấp chỗ trống đó bằng một chính sách tự viết. Đặt tên nó là
 * "Chính sách" khi chưa có pháp chế duyệt là đúng loại hứa hộ mà cả sản phẩm tồn
 * tại để chống. Nó là một thứ khác và hữu ích hơn ngay bây giờ: **liệt kê dữ liệu
 * hệ thống thật sự chạm tới, đi đâu, lưu bao lâu** — mọi câu ở đây kiểm được bằng
 * code, và đây chính là đầu vào một luật sư cần để viết chính sách.
 */

interface Luong {
  man: string;
  gui: string;
  luu: string;
  ghi?: string;
}

const CAC_LUONG: Luong[] = [
  {
    man: 'Tra cứu',
    gui: 'Câu hỏi bạn gõ được gửi tới OpenRouter (nhà cung cấp mô hình, hạ tầng ngoài Việt Nam) để xử lý.',
    luu: 'Câu hỏi được lưu trong bảng traces. Hiện CHƯA CÓ thời hạn lưu trữ. Câu trả lời được cache 7 ngày.',
  },
  {
    man: 'Soạn thảo',
    gui: 'Thông tin bạn nhập — có thể gồm họ tên và số CCCD của các bên — được gửi tới OpenRouter cùng yêu cầu dựng bản thảo.',
    luu: 'Nội dung bạn nhập KHÔNG được lưu. Chỉ loại văn bản (ví dụ "hdld") được ghi lại để đo hiệu năng.',
  },
  {
    man: 'Soát văn bản',
    gui: 'Văn bản bạn dán vào KHÔNG được gửi đi đâu. Toàn bộ phép soát chạy tại máy chủ, không gọi mô hình lần nào.',
    luu: 'Nội dung văn bản KHÔNG được lưu — chỉ mã băm và độ dài, đủ để nhận ra hai lần soát cùng một văn bản.',
    ghi: 'Đây là màn hình duy nhất không gửi dữ liệu của bạn ra ngoài.',
  },
];

const CHUA_CO = [
  'Thời hạn lưu trữ cho bảng traces. Câu hỏi ở màn Tra cứu hiện được giữ vô thời hạn.',
  'Chính sách bảo vệ dữ liệu cá nhân chính thức, đã qua pháp chế.',
  'Quy trình để bạn yêu cầu xem, sửa, hoặc xoá dữ liệu của mình.',
  'Đăng nhập. Khi có, nó sẽ chạy qua Supabase — cũng là hạ tầng ngoài Việt Nam.',
];

export default function DuLieu() {
  useTieuDeTrang();
  return (
    <article className="mx-auto max-w-[68ch] px-4 py-8">
      <h1 className="m-0 text-[1.75rem] leading-[1.2] font-semibold text-phim">
        Dữ liệu KLAW xử lý
      </h1>

      <p className="mat-doc mt-4 text-phim">
        Đây là <strong>bản kê</strong>, không phải chính sách. Nó nói hệ thống thật sự chạm tới dữ
        liệu gì, gửi đi đâu, và lưu bao lâu — mỗi câu ở đây kiểm được trong mã nguồn. Chính sách
        bảo vệ dữ liệu cá nhân chính thức chưa được công bố; trang này không thay thế nó.
      </p>

      <h2 className="mt-8 mb-0 text-[1.25rem] leading-[1.3] font-semibold text-phim">
        Ba màn hình, ba luồng khác nhau
      </h2>
      {CAC_LUONG.map((l) => (
        <section
          key={l.man}
          className="mt-4 rounded-lon border-s-2 py-3 ps-4"
          style={{ borderColor: 'var(--vien)', background: 'var(--nen-cao)' }}
        >
          <h3 className="m-0 text-[0.9375rem] leading-6 font-medium text-phim">{l.man}</h3>
          <dl className="mat-doc m-0 mt-2 text-phim">
            <dt className="text-[0.8125rem] leading-5 text-muc-nhat">Gửi ra ngoài</dt>
            <dd className="m-0 mb-2">{l.gui}</dd>
            <dt className="text-[0.8125rem] leading-5 text-muc-nhat">Lưu lại</dt>
            <dd className="m-0">{l.luu}</dd>
          </dl>
          {l.ghi !== undefined && (
            <p
              className="mt-2 mb-0 text-[0.875rem] leading-6"
              style={{ color: 'var(--xanh-that)' }}
            >
              {l.ghi}
            </p>
          )}
        </section>
      ))}

      <h2 className="mt-8 mb-0 text-[1.25rem] leading-[1.3] font-semibold text-phim">
        Chuyển dữ liệu qua biên giới
      </h2>
      <p className="mat-doc mt-3 text-phim">
        Màn Tra cứu và màn Soạn thảo gửi nội dung bạn nhập tới OpenRouter, đặt ngoài Việt Nam. Với
        màn Soạn thảo, nội dung đó có thể bao gồm dữ liệu cá nhân của{' '}
        <strong>người khác</strong> — người lao động có tên trong hợp đồng bạn đang soạn. Người đó
        không dùng KLAW và không được hỏi ý.
      </p>
      <p className="mat-doc mt-3 text-phim">
        Việc này thuộc phạm vi Luật Bảo vệ dữ liệu cá nhân 2025 và Nghị định 356/2025/NĐ-CP. KLAW
        chưa có xác nhận của pháp chế về việc đã tuân thủ đủ yêu cầu chuyển dữ liệu qua biên giới.
        Nói ra điều này thay vì im lặng là quyết định có chủ ý.
      </p>

      <h2 className="mt-8 mb-0 text-[1.25rem] leading-[1.3] font-semibold text-phim">
        Huấn luyện mô hình
      </h2>
      <p className="mat-doc mt-3 text-phim">
        KLAW <strong>không huấn luyện mô hình nào</strong> — hệ thống gọi mô hình có sẵn qua API,
        không có bước huấn luyện trong toàn bộ mã nguồn. Nhưng dữ liệu đã gửi tới OpenRouter chịu
        điều khoản của OpenRouter và của nhà cung cấp mô hình phía sau, không phải điều khoản của
        KLAW. Câu trả lời đầy đủ cho câu hỏi &ldquo;dữ liệu tôi nhập có bị dùng để huấn luyện
        không?&rdquo; cần xác nhận từ họ; KLAW chưa có xác nhận đó và không đoán thay.
      </p>

      <h2 className="mt-8 mb-0 text-[1.25rem] leading-[1.3] font-semibold text-phim">
        Những gì chưa có
      </h2>
      <ul className="mat-doc mt-3 mb-0 list-disc ps-5 text-phim">
        {CHUA_CO.map((c) => (
          <li key={c} className="mt-1">
            {c}
          </li>
        ))}
      </ul>
      <p className="mt-4 mb-0 text-[0.875rem] leading-6 text-muc-nhat">
        Danh sách này để mở có chủ ý. Một trang dữ liệu chỉ liệt kê việc đã làm xong thì không giúp
        được ai quyết định có nên nhập dữ liệu vào hay không.
      </p>
    </article>
  );
}
