import { Suspense, lazy, useEffect, useState } from 'react';
import { CoMay } from './CoMay';
import { VoMay } from './VoMay';

/**
 * Cửa vào của slot 3D ở hero. Quyết định DUY NHẤT ở đây: có được mount WebGL
 * hay không.
 *
 * `React.lazy` chỉ gọi factory khi component thật sự được render, nên nhánh
 * `!duRong` phía dưới chặn `import()` TRƯỚC lúc nó chạy — không phải sau. Đó là
 * điều §10.4 đòi: "Dưới 768px KHÔNG mount Canvas. Người dùng di động không được
 * tải `three`." Người lao động dùng điện thoại đời cũ, mạng yếu là một trong ba
 * nhóm người dùng chính của KLAW, không phải trường hợp biên — và
 * `research-zoom-3d.md` §8 vốn đã loại Three.js khỏi mọi màn hình vì đúng nhóm
 * này. Chủ dự án chọn bật WebGL sau khi được nêu rõ đánh đổi; cửa này là thứ
 * giữ cho lựa chọn đó không thành lỗi.
 *
 * Dưới 768px không phải là "không có gì": người dùng nhận CỖ MÁY CSS đầy đủ
 * (`CoMay`) — cùng ẩn dụ, cùng một Điều luật có thật được rọi sáng, 0 byte
 * `three`. Đó là bản hero thật của họ, không phải bản rút gọn.
 */
const KhoLuat = lazy(() => import('../hero3d/KhoLuat'));

/** Cùng breakpoint với `@media (min-width: 48rem)` trong gioi-thieu.css. */
const NGUONG_MAN = '(min-width: 48rem)';

export function SlotBaChieu() {
  // Đọc ngay trong initializer: nếu đợi `useEffect` thì lần render đầu ở desktop
  // sẽ ra CoMay rồi mới đổi sang Canvas — một cú nhấp nháy không cần thiết.
  const [duRong, datDuRong] = useState(() => window.matchMedia(NGUONG_MAN).matches);

  useEffect(() => {
    const truyVan = window.matchMedia(NGUONG_MAN);
    const doi = () => datDuRong(truyVan.matches);
    doi();
    truyVan.addEventListener('change', doi);
    return () => truyVan.removeEventListener('change', doi);
  }, []);

  // Chú thích đi CÙNG cảnh chứ không nằm ở trang: hai nhánh trưng hai thứ khác
  // nhau, nên một câu dùng chung thì có một nhánh bị mô tả sai. Câu của nhánh
  // CSS giữ nguyên nguyên văn bản cũ ở GioiThieu.tsx.
  if (!duRong) {
    return (
      <>
        <CoMay />
        <p className="mt-3 text-[0.8125rem] leading-5 text-muc-nhat">
          Cỗ máy vừa tiến một khung: dải phim trượt, một khung dừng dưới đèn và sáng lên. Đó là toàn
          bộ việc KLAW làm — đưa câu hỏi tới đúng một khung phim, rọi sáng, rồi để bạn đọc.
        </p>
      </>
    );
  }

  return (
    <>
      <Suspense fallback={<VoMay />}>
        <KhoLuat />
      </Suspense>
      <p className="mt-3 text-[0.8125rem] leading-5 text-muc-nhat">
        Kho văn bản của cỗ máy: mỗi phiến là một văn bản có thật trong corpus. Kéo để xoay, bấm một
        phiến để đọc nguyên văn một điều khoản kèm nhãn hiệu lực của nó.
      </p>
    </>
  );
}
