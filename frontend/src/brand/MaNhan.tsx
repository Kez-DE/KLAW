import { useId } from 'react';

/**
 * Mã nhãn KLAW — MỘT KHUNG PHIM ĐANG ĐƯỢC RỌI SÁNG (DESIGN.md § "Mã nhãn — KLAW").
 *
 * Không phải búa thẩm phán, không phải cán cân, không phải tia lửa AI. Những hình
 * đó nói "pháp luật" và "AI" một cách chung chung; khung phim nói đúng một điều mà
 * chỉ KLAW làm: *đây là nguyên văn, và đây là chỗ nó đến từ.*
 *
 *   - hình vuông bo góc      → khung phim
 *   - bốn khía hai cạnh dọc  → lỗ kéo phim
 *   - quầng sáng ấm lệch tâm → chỗ đèn máy rọi qua
 *
 * Lệch tâm có chủ đích: khung vừa tiến tới, ánh sáng chưa nằm đúng giữa. Đó là
 * động tác trung tâm của sản phẩm ("tiến tới đúng khung"), đóng băng trong một hình.
 *
 * BẤT BIẾN (DESIGN.md § Bảng màu): `--den-sang` LUÔN là quầng sáng radial mờ dần,
 * KHÔNG BAO GIỜ là nền đặc — đó là thứ duy nhất tách nó khỏi `--vang-mo` cùng họ
 * vàng. Vì vậy đèn ở đây là một gradient có lõi nóng, không phải một đĩa tô đặc,
 * và quầng sáng được GIỮ ở mọi kích thước kể cả favicon 16px.
 *
 * Ba phép thử hình đã chạy bằng mắt, không phải bằng tự tin:
 *   1. 16px   — dưới NGUONG_KHIA khía răng cưa bị BỎ (ở đó chúng chỉ còn là nhiễu),
 *               không thu nhỏ tiếp. Còn khung + đèn vẫn nhận ra được.
 *   2. một màu — khung có khía + quầng lệch tâm vẫn đọc được khi đổ hết thành một
 *               màu. Quan trọng vì nền nâu và đèn vàng là hàng xóm trên vòng màu.
 *   3. nền sáng / nền tối — khung dùng `currentColor` nên tự đảo theo chủ đề.
 */

/** Dưới ngưỡng này (px), khía răng cưa thành nhiễu — bỏ hẳn, không thu nhỏ tiếp. */
const NGUONG_KHIA = 20;

/** Tâm đèn, lệch lên trái khỏi tâm khung (16, 16) trên lưới 32. */
const SANG_X = 13.5;
const SANG_Y = 13.5;

/**
 * Bán kính quầng sáng. Lõi nóng đặc tới 58% bán kính rồi mờ dần về 0.
 * 58% là con số ĐO ĐƯỢC, không phải chọn cho đẹp: rasterise ở 16px rồi phóng
 * nearest-neighbour, lõi 46% tãi thành vệt nhoè trên nền --phim, lõi 58% thành
 * khối đặc đọc được. Vẫn còn dải mờ dần nên bất biến "đèn máy là quầng sáng"
 * không gãy. Đã thử thêm một vành quanh đèn: ở 16px vành ăn hết chấm sáng, ở
 * 64px nó thành vòng cứng — bỏ.
 */
const SANG_R = 6.8;

/** Khía răng cưa: 2 mỗi cạnh dọc, cắt xuyên nét khung bằng mask. */
const KHIA = [
  { x: 2, y: 11 },
  { x: 2, y: 19 },
  { x: 26, y: 11 },
  { x: 26, y: 19 },
];

interface PropsMaNhan {
  size?: number;
  className?: string;
}

export function MaNhan({ size = 32, className }: PropsMaNhan) {
  // useId sinh chuỗi có dấu ':' — bỏ đi để url(#…) an toàn trong SVG.
  const goc = useId().replace(/:/g, '');
  const idQuang = `klaw-quang-${goc}`;
  const idKhia = `klaw-khia-${goc}`;
  const coKhia = size >= NGUONG_KHIA;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <defs>
        {/* Đèn máy: lõi nóng đặc, rồi mờ dần về 0 — quầng sáng, không phải đĩa tô. */}
        <radialGradient id={idQuang}>
          <stop offset="0" stopColor="var(--den-sang)" stopOpacity="1" />
          <stop offset="0.58" stopColor="var(--den-sang)" stopOpacity="1" />
          <stop offset="0.76" stopColor="var(--den-sang)" stopOpacity="0.5" />
          <stop offset="1" stopColor="var(--den-sang)" stopOpacity="0" />
        </radialGradient>
        {coKhia && (
          <mask id={idKhia} maskUnits="userSpaceOnUse" x="0" y="0" width="32" height="32">
            <rect width="32" height="32" fill="#fff" />
            {KHIA.map((khia) => (
              <rect
                key={`${khia.x}-${khia.y}`}
                x={khia.x}
                y={khia.y}
                width="4"
                height="2"
                rx="0.4"
                fill="#000"
              />
            ))}
          </mask>
        )}
      </defs>

      {/* Khung phim. currentColor: sống được trên cả nền sáng lẫn nền tối. */}
      <rect
        x="4"
        y="4"
        width="24"
        height="24"
        rx="4"
        stroke="currentColor"
        strokeWidth="2.5"
        mask={coKhia ? `url(#${idKhia})` : undefined}
      />

      {/* Đèn máy rọi qua phim. Bán kính 8 nên nằm trọn trong lòng khung. */}
      <circle cx={SANG_X} cy={SANG_Y} r={SANG_R} fill={`url(#${idQuang})`} />
    </svg>
  );
}

/**
 * Chữ hiệu: mã nhãn ĐẶT CẠNH chữ "KLAW", không lồng vào trong (DESIGN.md).
 * "KLAW" dùng font địa chỉ (mono) giãn nhẹ — cùng họ chữ với `so_ky_hieu`, vì
 * tên sản phẩm cũng là một địa chỉ để gõ, không phải văn xuôi.
 */
export function ChuHieu({ className }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className ?? ''}`}>
      <MaNhan size={26} />
      <span className="-mr-[0.16em] font-dia-chi text-[15px] leading-none font-medium tracking-[0.16em]">
        KLAW
      </span>
    </span>
  );
}
