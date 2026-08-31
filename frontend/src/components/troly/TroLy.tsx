import { useCallback, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import type { KeyboardEvent } from 'react';

/**
 * Trợ lý — NGƯỜI VẬN HÀNH MÁY, không phải bong bóng chat biết tuốt.
 *
 * Hình thái là ô đèn của máy: một vòng sáng `--den-sang` thở nhẹ khi rảnh.
 * Không mặt người, không nhân vật hoạt hình. Lý do ràng buộc này tồn tại: một
 * nhân vật AI hỏi "bạn cần giúp gì?" mặc định hứa hẹn sự thông thái vô hạn —
 * đúng cái cảm giác khiến người dùng tin output không kiểm chứng. Luận điểm
 * của sản phẩm này là ngược lại, nên sự hiện diện của nó phải trông như một bộ
 * phận của cỗ máy chứ không như một người biết tuốt.
 *
 * Bốn ràng buộc hành vi (DESIGN.md § "Trợ lý"), tất cả đều thi hành ở đây:
 *   1. Câu mở kèm câu hỏi mẫu CÓ THẬT, chạy được, nằm trong phạm vi corpus.
 *   2. NÊU GIỚI HẠN TRƯỚC KHI BỊ HỎI — không để người dùng chờ 60 giây rồi
 *      mới nhận `out_of_scope`.
 *   3. KHÔNG BAO GIỜ tự sinh nội dung pháp lý. Mọi thứ nó làm là điều hướng
 *      sang /tra-cuu; nó không đoán trước điều luật nào sẽ trả lời câu hỏi.
 *   4. Thu gọn được, trạng thái thu gọn được nhớ, KHÔNG BAO GIỜ tự bật lại.
 *
 * "Sáng ổn định khi đang chạy" chưa có trạng thái tương ứng ở đây: trợ lý này
 * không chạy tra cứu, nó chỉ dẫn đường. Trạng thái đèn chạy sống ở màn Tra cứu
 * (TrangThaiCho). Đừng thêm một hiệu ứng "đang nghĩ" giả vào đây.
 */

const KHOA_THU_GON = 'klaw:tro-ly-thu-gon';
const ID_BANG = 'tro-ly-bang';

/**
 * Ba câu chạy được thật, đã đối chiếu corpus trước khi viết vào đây:
 * 45/2019/QH14 > Điều 127 (các hành vi bị nghiêm cấm khi xử lý kỷ luật),
 * 45/2019/QH14 > Điều 107 (làm thêm giờ), 135/2020/NĐ-CP > Điều 4 (tuổi nghỉ
 * hưu trong điều kiện lao động bình thường) — cả ba đều nằm ở tầng có toàn văn.
 *
 * Cố ý KHÔNG in kèm số hiệu điều luật dự kiến: đoán trước điều nào sẽ trả lời
 * chính là tự sinh nội dung pháp lý chưa qua kiểm chứng.
 */
const CAU_MAU = [
  'Khi xử lý kỷ luật lao động, người sử dụng lao động bị nghiêm cấm làm những gì?',
  'Người lao động làm thêm giờ tối đa bao nhiêu giờ trong một năm?',
  'Tuổi nghỉ hưu trong điều kiện lao động bình thường được xác định thế nào?',
];

/**
 * Mặc định là THU GỌN, ở mọi khổ màn hình. Đã đo bằng mắt: bảng mở sẵn phủ hơn
 * nửa khung nhìn ở 390px, và ở 1440px nó vẫn liếm vào mép phải cột đọc 52rem —
 * tức là che chữ. Một trợ lý che mất thứ người ta đang đọc để chào thì đang làm
 * đúng cái việc mà DESIGN.md dựng nó lên để tránh. Câu mở không mất đi: nhãn
 * của viên nút thu gọn CHÍNH LÀ "Bạn cần tra điều gì?".
 *
 * localStorage có thể ném (chế độ riêng tư, chặn lưu trữ bên thứ ba). Cả đọc
 * lẫn ghi đều bọc try/catch; hỏng thì rơi về mặc định thu gọn, không sập trang.
 */
function docThuGon(): boolean {
  let daLuu: string | null = null;
  try {
    daLuu = window.localStorage.getItem(KHOA_THU_GON);
  } catch {
    daLuu = null;
  }
  // Chỉ lựa chọn ĐÃ LƯU mới mở được bảng. Không có nhánh nào khác trả về
  // false, nên không tồn tại đường để trợ lý tự bật lên.
  return daLuu !== '0';
}

function ghiThuGon(thuGon: boolean): void {
  try {
    window.localStorage.setItem(KHOA_THU_GON, thuGon ? '1' : '0');
  } catch {
    // Không nhớ được thì thôi — không có gì để báo cho người dùng ở đây.
  }
}

export function TroLy() {
  // Đọc MỘT LẦN lúc dựng. Không có effect nào ghi ngược lại state này, nên
  // không tồn tại đường nào để trợ lý tự bật lại sau khi người dùng thu gọn.
  const [mo, datMo] = useState(() => !docThuGon());
  const nut = useRef<HTMLButtonElement>(null);

  // Ghi localStorage NGOÀI hàm cập nhật state. Đặt nó bên trong là một tác dụng
  // phụ chạy ở pha render: StrictMode gọi updater hai lần, và React hoãn updater
  // tới lúc render nên thứ tự ghi có thể đảo so với các lệnh ghi đồng bộ khác.
  // Đã bắt được đúng lỗi đó khi kiểm bằng mắt — giao diện thu gọn mà bộ nhớ ghi
  // "đang mở", tức là lần vào sau trợ lý TỰ BẬT LẠI. Đó là điều bị cấm.
  const doiTrangThai = useCallback(() => {
    const sau = !mo;
    datMo(sau);
    ghiThuGon(!sau);
  }, [mo]);

  const khiGoPhim = useCallback((su: KeyboardEvent<HTMLDivElement>) => {
    if (su.key !== 'Escape') return;
    su.stopPropagation();
    datMo(false);
    ghiThuGon(true);
    nut.current?.focus();
  }, []);

  return (
    <div className="tl" onKeyDown={khiGoPhim}>
      <div id={ID_BANG} hidden={!mo} className="tl-bang" role="group" aria-label="Trợ lý KLAW">
        <h2 className="text-base leading-6 font-medium text-phim">Bạn cần tra điều gì?</h2>
        <p className="mt-2 text-[0.875rem] leading-6 text-muc-nhat">
          Tôi là ô đèn của máy: tôi biết trong kho có gì và đưa bạn tới đúng khay phim. Tôi không
          tự trả lời câu hỏi pháp luật — câu trả lời đến từ máy, kèm trích dẫn để bạn tự kiểm.
        </p>

        <p className="mt-3 text-[0.8125rem] leading-5 text-muc-nhat">
          Ba câu chạy được ngay, đều nằm trong kho:
        </p>
        <ul className="mt-2 flex list-none flex-col gap-2 p-0">
          {CAU_MAU.map((cau) => (
            <li key={cau}>
              <Link className="tl-mau" to={`/tra-cuu?q=${encodeURIComponent(cau)}`}>
                {cau}
              </Link>
            </li>
          ))}
        </ul>

        {/* Giới hạn nói TRƯỚC khi bị hỏi. Để người dùng gõ một câu về thuế rồi
            chờ 60 giây mới nhận out_of_scope là một cách nói dối bằng im lặng. */}
        <p className="mt-4 text-[0.8125rem] leading-5 text-muc-nhat">
          Nói trước để bạn khỏi mất công: kho chỉ có <strong className="font-medium">lao động</strong>{' '}
          ở mức đầy đủ, cộng năm Bộ luật khác không có văn bản hướng dẫn đi kèm. Thuế, đất đai, hôn
          nhân gia đình, doanh nghiệp <strong className="font-medium">không có trong kho</strong>.
          Một lượt tra cứu mất 10–60 giây vì máy đọc thật chứ không đoán.
        </p>
      </div>

      <button
        ref={nut}
        type="button"
        className="tl-nut"
        aria-expanded={mo}
        aria-controls={ID_BANG}
        onClick={doiTrangThai}
      >
        <span className="tl-den" aria-hidden="true" />
        {mo ? 'Thu gọn trợ lý' : 'Bạn cần tra điều gì?'}
      </button>
    </div>
  );
}
