import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { CoMay } from '../components/gioi-thieu/CoMay';
import { PhamViThat } from '../components/gioi-thieu/PhamViThat';
import '../styles/gioi-thieu.css';

/**
 * Giới thiệu (`/`) — bề mặt DUY NHẤT ở mode Persuade. Ba màn hình công cụ vẫn
 * là Operate; đừng mang phong cách trang này sang chúng.
 *
 * Người vào lần đầu chưa biết KLAW khác gì một trợ lý biết nói. Trang này trả
 * lời đúng câu hỏi đó rồi để họ gõ câu hỏi thật ngay tại chỗ: ô hỏi ở hero LÀ
 * ô hỏi thật, không phải nút dẫn sang trang khác. Câu hỏi đi theo sang
 * `/tra-cuu?q=` và TraCuu.tsx đọc lại `?q=` — ô hỏi không được trông như bị
 * xoá rồi gõ lại (motion-spec.md, "Liên tục").
 *
 * Mục 4 (Phạm vi thật) và mục 5 (Giới hạn) nằm TRÊN trang này có chủ đích. Một
 * trang giới thiệu giấu giới hạn xuống footer là trang bán hàng; trang này
 * thuyết phục được VÌ nó nói ra giới hạn.
 */

const BON_KET_QUA = [
  {
    ma: 'answer',
    mau: 'var(--xanh-that)',
    mo: 'Có căn cứ, có câu trả lời bằng tiếng Việt thường, kèm từng trích dẫn bấm được tới nguyên văn.',
  },
  {
    ma: 'partial_coverage',
    mau: 'var(--vang-mo)',
    mo: 'Tìm được văn bản chi phối nhưng chưa có toàn văn ở cấp điều khoản. Máy nêu văn bản rồi dừng — mặt đọc để trống có chủ đích, không diễn giải.',
  },
  {
    ma: 'abstain',
    mau: 'var(--xam-cho)',
    mo: '“Không tìm thấy căn cứ pháp lý cho câu hỏi này.” Đây là một câu trả lời hợp lệ, không phải một lỗi — nên nó không mang màu đỏ, không icon cảnh báo.',
  },
  {
    ma: 'out_of_scope',
    mau: 'var(--xam-cho)',
    mo: 'Câu hỏi thuộc lĩnh vực corpus không phủ. Máy nói ra phạm vi thật thay vì cố trả lời cho có.',
  },
];

export default function GioiThieu() {
  const [cauHoi, datCauHoi] = useState('');
  const dieuHuong = useNavigate();

  const gui = (su: FormEvent<HTMLFormElement>) => {
    su.preventDefault();
    const sach = cauHoi.trim();
    dieuHuong(sach === '' ? '/tra-cuu' : `/tra-cuu?q=${encodeURIComponent(sach)}`);
  };

  return (
    <div className="mx-auto w-full max-w-[52rem] px-4 pt-8 pb-16">
      {/* ── 1. Hero ─────────────────────────────────────────────────────── */}
      <section aria-labelledby="tieu-de-chinh">
        <h1
          id="tieu-de-chinh"
          className="mat-doc text-2xl leading-tight font-semibold text-phim focus:outline-2 focus:outline-den-sang focus:outline-offset-4 md:text-[2rem]"
        >
          Hỏi một câu. Nhận đúng điều luật, kèm địa chỉ để tự kiểm.
        </h1>
        <p className="mat-doc mt-4 text-phim">
          KLAW tra pháp luật lao động Việt Nam trên corpus văn bản gốc. Mỗi trích dẫn là một dòng có
          thật trong cơ sở dữ liệu, mang một địa chỉ dạng{' '}
          <span className="dia-chi">45/2019/QH14 &gt; Điều 127 &gt; Khoản 2</span> — bấm vào là đọc
          được nguyên văn chỗ nó đến từ.
        </p>

        <form onSubmit={gui} className="mt-6">
          <label htmlFor="cau-hoi-gioi-thieu" className="mat-doc mb-2 block font-medium text-phim">
            Hỏi về pháp luật lao động Việt Nam
          </label>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              id="cau-hoi-gioi-thieu"
              name="cau-hoi-gioi-thieu"
              type="text"
              value={cauHoi}
              onChange={(su) => datCauHoi(su.target.value)}
              placeholder="Ví dụ: Người lao động làm thêm giờ tối đa bao nhiêu giờ trong một năm?"
              className="mat-doc min-h-[var(--vung-cham-toi-thieu)] max-w-none flex-1 rounded-vua border p-3 text-phim placeholder:text-muc-nhat focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
              style={{
                background: 'var(--nen-cao)',
                borderColor: 'color-mix(in srgb, var(--muc-nhat) 55%, transparent)',
              }}
            />
            <button
              type="submit"
              className="min-h-[var(--vung-cham-toi-thieu)] shrink-0 cursor-pointer rounded-vua px-5 text-[0.9375rem] font-medium transition-opacity duration-[var(--thoi-luong-nhanh)] ease-chuan hover:opacity-85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
              style={{ background: 'var(--den-sang)', color: 'var(--muc)' }}
            >
              Tra cứu
            </button>
          </div>
          <p className="mt-2 text-[0.8125rem] leading-5 text-muc-nhat">
            Một lượt mất 10–60 giây. Máy đi qua bốn bước có thật và cho bạn thấy đang ở bước nào.
          </p>
        </form>

        <div className="mt-8">
          <CoMay />
          <p className="mt-3 text-[0.8125rem] leading-5 text-muc-nhat">
            Cỗ máy vừa tiến một khung: dải phim trượt, một khung dừng dưới đèn và sáng lên. Đó là
            toàn bộ việc KLAW làm — đưa câu hỏi tới đúng một khung phim, rọi sáng, rồi để bạn đọc.
          </p>
        </div>
      </section>

      {/* ── 2. Vì sao khác ──────────────────────────────────────────────── */}
      <section className="mt-14" aria-labelledby="vi-sao-khac">
        <h2 id="vi-sao-khac" className="mat-doc text-xl font-medium text-phim md:text-2xl">
          Vì sao khác một trợ lý biết nói
        </h2>
        <p className="mat-doc mt-3 text-phim">
          Một mô hình ngôn ngữ có thể viết ra một số hiệu văn bản trông rất đúng mà không có văn bản
          nào như thế tồn tại. Vấn đề không nằm ở chỗ nó nói sai — mà ở chỗ bạn không có cách nào
          biết, trừ khi tự đi tra lại từ đầu.
        </p>
        <p className="mat-doc mt-3 text-phim">
          KLAW không sinh ra số hiệu. Mỗi trích dẫn được neo vào một bản ghi có thật, và giao diện
          đưa bạn tới đúng bản ghi đó. Kiểm chứng ở đây là <em>tra bảng</em>, không phải{' '}
          <em>suy luận</em>: bấm một trích dẫn, khung phim tương ứng tiến vào tiêu điểm và rọi
          nguyên văn Điều luật, câu được trích đánh dấu sẵn trong đó. Bạn không phải tin — bạn đọc.
        </p>
        <p className="mat-doc mt-3 text-phim">
          Nhãn hiệu lực đi kèm từng khung và <em>luôn thấy được</em>, không giấu trong tooltip. Khung
          được rọi sáng phía trên mang nhãn “một phần không xác định” vì cơ sở dữ liệu quốc gia
          không công bố hiệu lực ở cấp điều khoản cho văn bản đó — và trang này nói ra điều đó thay
          vì chọn một ví dụ sạch hơn để trưng.
        </p>
      </section>

      {/* ── 3. Bốn kết quả ──────────────────────────────────────────────── */}
      <section className="mt-14" aria-labelledby="bon-ket-qua">
        <h2 id="bon-ket-qua" className="mat-doc text-xl font-medium text-phim md:text-2xl">
          Bốn kết quả — và “không tìm thấy căn cứ” là một trong số đó
        </h2>
        <p className="mat-doc mt-3 text-phim">
          Máy không có chế độ “luôn luôn trả lời”. Nó phân biệt bốn tình huống, và ba trong số đó
          kết thúc bằng việc <em>không</em> đưa ra diễn giải pháp lý.
        </p>
        <ul className="mt-5 flex list-none flex-col gap-3 p-0">
          {BON_KET_QUA.map((ket) => (
            <li
              key={ket.ma}
              className="rounded-lon border p-4"
              style={{ background: 'var(--nen-cao)', borderColor: 'var(--vien)' }}
            >
              <span className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="size-2 shrink-0 rounded-tron"
                  style={{ background: ket.mau }}
                />
                <span className="dia-chi text-[0.875rem] leading-6 font-medium text-phim">
                  {ket.ma}
                </span>
              </span>
              <p className="mat-doc mt-1.5 text-phim">{ket.mo}</p>
            </li>
          ))}
        </ul>
        <p className="mat-doc mt-4 text-phim">
          Một hệ thống thà nói “tôi không đủ căn cứ” còn hơn bịa ra một điều luật. Nếu giao diện tô
          đỏ câu đó, nó dạy người dùng rằng sự trung thực là thất bại — nên ở đây{' '}
          <span className="dia-chi">abstain</span> mang màu trung tính của chính đồ đạc trong máy.
          Đỏ được để dành cho một việc duy nhất: <em>luật đã bị thay thế</em>, thứ thật sự khiến bạn
          hành động sai.
        </p>
      </section>

      {/* ── 4. Phạm vi thật — số liệu lấy từ API, không viết cứng ────────── */}
      <section className="mt-14" aria-labelledby="pham-vi-that">
        <h2 id="pham-vi-that" className="mat-doc text-xl font-medium text-phim md:text-2xl">
          Phạm vi thật
        </h2>
        <PhamViThat />
      </section>

      {/* ── 5. Giới hạn ─────────────────────────────────────────────────── */}
      <section className="mt-14" aria-labelledby="gioi-han">
        <h2 id="gioi-han" className="mat-doc text-xl font-medium text-phim md:text-2xl">
          Giới hạn — nói ở đây, không giấu xuống chân trang
        </h2>
        <p className="mat-doc mt-3 text-phim">
          Corpus là <em>văn bản gốc</em>, không phải bản hợp nhất. Hệ thống bảo đảm hai điều: trích
          dẫn đúng <em>nguyên văn</em>, và chỉ được đúng <em>nguồn gốc</em> của nó. Nó{' '}
          <strong className="font-medium">không</strong> bảo đảm đây là bản đang hiện hành sau mọi
          lần sửa đổi.
        </p>
        <p className="mat-doc mt-3 text-phim">
          Cơ sở dữ liệu quốc gia đánh sai hiệu lực của bốn nghị định lương tối thiểu. KLAW phát hiện
          và sửa lại, nhưng điều đó cũng có nghĩa: <em>nguồn chính thức có sai sót</em>. Bạn phải
          đối chiếu trước khi hành động.
        </p>
        <p className="mat-doc mt-3 text-phim">
          KLAW không phải tư vấn pháp lý và không thay thế luật sư. Mọi quyết định có hậu quả pháp lý
          cần người có chuyên môn kiểm lại. Đây là sản phẩm khoá luận tốt nghiệp — nói thẳng như vậy.
        </p>
        <p className="mt-4">
          <Link
            to="/mien-tru"
            className="mat-doc inline-flex min-h-[var(--vung-cham-toi-thieu)] items-center text-den-sang underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-den-sang"
          >
            Đọc miễn trừ trách nhiệm đầy đủ
          </Link>
        </p>
      </section>
    </div>
  );
}
