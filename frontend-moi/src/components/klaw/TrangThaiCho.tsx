import { useEffect, useState } from "react";
import type { BuocKhai, SuKienBuoc } from "@/lib/klaw";

/**
 * Trạng thái chờ cho một lượt gọi mất 10–60 giây — BONG BÓNG BA CHẤM.
 *
 * Nhìn thấy được đúng HAI thứ: ba chấm, và nút "Huỷ lượt tra cứu" ngay dưới.
 * Không thanh tiến trình, không đồng hồ giây, không mã truy vết, không câu
 * giải thích. Quyết định của chủ dự án.
 *
 * ## Vì sao bảng chín bước biến mất
 *
 * Bảng đó đúng về kỹ thuật và sai về người đọc. Nó phơi tên chín node của
 * graph (`tier1`, `tier2`, `verify`…) ra trước một người đang hỏi mình có bị
 * trừ lương trái luật hay không. Với họ, chín dòng thuật ngữ trôi qua không
 * phải thông tin — nó là tiếng ồn, và nó biến một khoảng chờ bình thường
 * thành cảm giác đang xem một cỗ máy vật lộn. Ba chấm nói đúng một điều họ cần
 * biết: **máy còn sống, chờ chút**. Đó là quy ước hội thoại ai cũng đọc được
 * mà không phải học.
 *
 * ## Nhưng dữ liệu bước KHÔNG bị vứt
 *
 * `cacBuoc` và `daPhat` vẫn vào, và vẫn được nói ra — qua vùng `aria-live`.
 * Người dùng trình đọc màn hình không thấy ba chấm nhấp nháy: với họ, một
 * bong bóng im lặng suốt 50 giây LÀ một màn hình đã chết. Nên họ nhận đúng
 * thứ bảng cũ có (`đã xong 5/9 bước — đang chạy: …`), chỉ khác là nó được
 * đọc chứ không được vẽ.
 *
 * Vùng đó chỉ đổi nội dung khi TÊN BƯỚC đổi, không đổi theo đồng hồ giây: một
 * `aria-live` cập nhật bốn lần mỗi giây là một cái loa, không phải một thông
 * báo.
 *
 * ## Ba chấm và `prefers-reduced-motion`
 *
 * Chuyển động ở đây là phản hồi trạng thái, không phải trang trí — tắt nó đi
 * là để người dùng nhìn một khay đứng im. `styles.css` đã có ngoại lệ đúng
 * cho `.thinking-dot`: dưới `prefers-reduced-motion` nó bỏ phần dịch chuyển và
 * chỉ còn nhịp mờ–tỏ, chậm hơn. Không viết lại ở đây.
 *
 * Sàn độ mờ của nhịp là **0,75**, không phải 0,25 như trước. Ba chấm nay là
 * chỉ báo DUY NHẤT nên chúng là đồ hoạ mang nghĩa: WCAG 1.4.11 đòi 3:1, và ở
 * sàn 0,25 chúng đo được 1,42:1 — gần như vô hình ở khung mờ nhất. Đo lại
 * trên DOM thật sau khi nâng sàn: **3,24:1**.
 */

/** Hoãn trước khi hiện: câu trả lời từ bộ đệm (3ms) không được loé rồi tắt. */
const HOAN_MS = 400;

/**
 * Số khung hình chờ trước khi bỏ cuộc khi trả tiêu điểm về ô hỏi.
 *
 * Ô hỏi mang `disabled` trong lúc chạy, và React bỏ cờ đó ở một lượt commit
 * KHÁC lượt huỷ — `focus()` gọi sớm một khung hình sẽ im lặng không làm gì.
 * Có trần rõ ràng, không có vòng lặp vô hạn.
 */
const SO_KHUNG_CHO_O_HOI = 5;

/**
 * Trả tiêu điểm về ô hỏi sau khi huỷ.
 *
 * Huỷ xong thì khay này biến mất cùng cái nút vừa được bấm, và tiêu điểm rơi về
 * `<body>`: người dùng bàn phím mất chỗ đứng, Tab tiếp lại bắt đầu từ đầu trang.
 * Trả về Ô HỎI chứ không phải nút gửi — nút gửi đang `disabled` nên trình duyệt
 * đã dời tiêu điểm khỏi nó từ trước, và huỷ là để sửa câu hỏi rồi gửi lại.
 */
function traTieuDiemVeOHoi(conLai = SO_KHUNG_CHO_O_HOI): void {
  requestAnimationFrame(() => {
    const chinh = document.getElementById("noi-dung-chinh") ?? document.body;
    const oHoi =
      chinh.querySelector<HTMLElement>("textarea:not([disabled])") ??
      chinh.querySelector<HTMLElement>("input:not([disabled])");
    if (oHoi === null) return;
    oHoi.focus();
    if (document.activeElement !== oHoi && conLai > 0) traTieuDiemVeOHoi(conLai - 1);
  });
}

interface TrangThaiChoProps {
  /** Bước do MÁY CHỦ khai (`event: bat_dau`). Rỗng = chưa nhận được khai báo. */
  cacBuoc: BuocKhai[];
  /** Bước máy chủ đã phát, theo thứ tự tới. */
  daPhat: SuKienBuoc[];
  /** Huỷ THẬT: nơi gọi `abort()` một `AbortController`, không chỉ ẩn khay. */
  onHuy: () => void;
}

export function TrangThaiCho({ cacBuoc, daPhat, onHuy }: TrangThaiChoProps) {
  const [hienRa, datHienRa] = useState(false);

  // Chỉ còn MỘT hẹn giờ. Nhịp 500ms trước đây tồn tại để chạy đồng hồ giây;
  // đồng hồ đã bỏ, nên giữ nhịp lại là dựng lại component hai lần mỗi giây
  // suốt 50 giây để vẽ đúng cùng một khung hình.
  useEffect(() => {
    const hoan = setTimeout(() => datHienRa(true), HOAN_MS);
    return () => clearTimeout(hoan);
  }, []);

  if (!hienRa) return null; // còn trong khoảng hoãn

  // Đếm theo `thu_tu` LỚN NHẤT đã phát, không theo SỐ sự kiện: lượt lấy từ bộ
  // đệm phát ĐÚNG MỘT bước (`cache`, `thu_tu: 9`) thay vì giả vờ chạy chín node
  // cho một lượt 3ms, và đếm sự kiện sẽ đọc lượt đó thành "mới xong 1/9".
  const soXong = daPhat.reduce((max, su) => Math.max(max, su.thu_tu ?? 0), 0);
  const tong = cacBuoc.length;
  const dangChay = cacBuoc[soXong];

  // Câu cho trình đọc màn hình. KHÔNG kèm số giây: `aria-live` phải đổi khi có
  // TIN MỚI, và đồng hồ chạy không phải tin.
  const loiNhan =
    tong === 0
      ? "Đang mở kết nối tới máy chủ KLAW."
      : dangChay === undefined
        ? `Đã xong ${soXong}/${tong} bước, đang hoàn tất.`
        : `Đã xong ${soXong}/${tong} bước, đang chạy: ${dangChay.nhan}.`;

  const huyVaTraTieuDiem = () => {
    onHuy();
    traTieuDiemVeOHoi();
  };

  return (
    <div className="mt-4">
      {/* Bong bóng. `aria-hidden` vì nó không mang chữ nào — câu tương đương
          nằm ở vùng `aria-live` ngay dưới, và để cả hai cùng đọc được sẽ thành
          đọc hai lần. */}
      <div
        aria-hidden="true"
        className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-4 py-3 shadow-soft"
      >
        <span className="thinking-dot size-2 rounded-full bg-[var(--color-status-neutral)]" />
        <span className="thinking-dot size-2 rounded-full bg-[var(--color-status-neutral)]" />
        <span className="thinking-dot size-2 rounded-full bg-[var(--color-status-neutral)]" />
      </div>

      <p role="status" aria-live="polite" className="sr-only">
        {loiNhan}
      </p>

      {/* Huỷ ở mức THỨ YẾU: một nút viền đầy đủ cạnh bong bóng sẽ mời người ta
          bấm, mà bấm thì mất lượt đã trả tiền. Nó vẫn phải với tới được bằng
          bàn phím và vẫn cao đủ 44px để chạm được trên điện thoại. */}
      {/* HÀNH VI không đổi: nút này chỉ `abort()` phía trình duyệt. Nó KHÔNG
          gửi thêm request nào để cố huỷ phía máy chủ, và máy chủ vẫn chạy nốt
          graph trong task riêng để lượt đã trả tiền vẫn ghi được `traces`. Câu
          nói ra điều đó đã gỡ theo quyết định của chủ dự án — chỉ gỡ CHỮ, đừng
          gỡ luôn ghi chú này rồi tưởng huỷ là miễn phí. */}
      <p className="mt-2 mb-0 text-[12px] leading-5 text-muted-foreground">
        <button
          type="button"
          onClick={huyVaTraTieuDiem}
          className="focus-brass -mx-1 inline-flex min-h-11 cursor-pointer items-center rounded px-1 underline underline-offset-2 hover:text-foreground"
        >
          Huỷ lượt tra cứu
        </button>
      </p>
    </div>
  );
}
