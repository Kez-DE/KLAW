import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Trạng thái chờ cho một lượt gọi mất 10–60 giây.
 *
 * Trên ngưỡng 10 giây, một chỉ báo KHÔNG XÁC ĐỊNH (vòng tròn quay) đọc như
 * treo máy. Nên ở đây có đủ bốn thứ: **tên bước đang chạy**, **tiến trình xác
 * định**, **nút huỷ thật**, và một đường dẫn tới **lỗi thật** khi quá hạn
 * (timeout do nơi gọi lo, hiện qua `BaoLoi`, kèm nút thử lại).
 *
 * TIẾN TRÌNH LÀ ƯỚC LƯỢNG, và giao diện nói thẳng như vậy. Máy chủ trả một lần,
 * không stream, nên không có cách nào biết bước nào đang chạy thật. Bốn bước
 * dưới đây CÓ THẬT trong đồ thị xử lý, nhưng mốc thời gian là ước lượng. Hệ
 * thống này tồn tại để chống việc trình bày phỏng đoán như dữ kiện; một thanh
 * tiến trình giả vờ là dữ liệu đo được sẽ phản bội chính nó. Khi backend có
 * SSE: thay nguồn của `chiSoBuoc`, giữ nguyên phần còn lại.
 */

interface Buoc {
  /** Giây trôi qua kể từ lúc gửi, từ đó bước này được coi là đang chạy. */
  tuGiay: number;
  ten: string;
}

const CAC_BUOC: Buoc[] = [
  { tuGiay: 0, ten: "Đang tìm văn bản" },
  { tuGiay: 5, ten: "Đang mở rộng điều khoản" },
  { tuGiay: 14, ten: "Đang kiểm chứng trích dẫn" },
  { tuGiay: 26, ten: "Đang dựng câu trả lời" },
];

/** Hoãn trước khi hiện chỉ báo: câu trả lời nhanh không được loé rồi tắt. */
const HOAN_MS = 400;
const NHIP_MS = 250;

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
 * `<body>`: người dùng bàn phím mất chỗ đứng, Tab tiếp lại bắt đầu từ đầu
 * trang. Trả về Ô HỎI chứ không phải nút gửi — nút gửi đang `disabled` nên
 * trình duyệt đã dời tiêu điểm khỏi nó từ trước, và huỷ là để sửa câu hỏi rồi
 * gửi lại.
 *
 * Tra ô hỏi SAU khi DOM đã cập nhật, không bắt tham chiếu từ trước: React có
 * thể đã thay hẳn nút DOM của ô hỏi, và `focus()` trên nút đã rời cây thì im
 * lặng không làm gì.
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
  /** Huỷ THẬT: nơi gọi phải `abort()` một `AbortController`, không chỉ ẩn khay. */
  onHuy: () => void;
}

export function TrangThaiCho({ onHuy }: TrangThaiChoProps) {
  const [giay, datGiay] = useState<number | null>(null);

  useEffect(() => {
    const batDau = Date.now();
    const hoan = setTimeout(() => datGiay((Date.now() - batDau) / 1000), HOAN_MS);
    const nhip = setInterval(() => datGiay((Date.now() - batDau) / 1000), NHIP_MS);
    return () => {
      clearTimeout(hoan);
      clearInterval(nhip);
    };
  }, []);

  if (giay === null) return null; // còn trong khoảng hoãn

  let chiSoBuoc = 0;
  for (let i = 0; i < CAC_BUOC.length; i += 1) {
    const buoc = CAC_BUOC[i];
    if (buoc !== undefined && giay >= buoc.tuGiay) chiSoBuoc = i;
  }
  const buocHienTai = CAC_BUOC[chiSoBuoc];
  if (buocHienTai === undefined) return null;
  const soBuoc = chiSoBuoc + 1;

  const huyVaTraTieuDiem = () => {
    onHuy();
    traTieuDiemVeOHoi();
  };

  return (
    <div className="mt-6 rounded-xl border border-border bg-card p-4 shadow-soft">
      <p className="m-0 text-[13px] leading-5 text-muted-foreground">
        Một lượt tra cứu mất 10–60 giây. Máy đang chạy.
      </p>

      <ol className="mt-3 mb-0 list-none p-0">
        {CAC_BUOC.map((buoc, i) => {
          const xong = i < chiSoBuoc;
          const dangChay = i === chiSoBuoc;
          return (
            <li
              key={buoc.ten}
              className={cn(
                "flex min-h-8 items-center gap-2.5 text-[15px] leading-6",
                dangChay ? "font-medium text-foreground" : "text-muted-foreground",
              )}
            >
              {/* Bước xong mang DẤU TÍCH, bước đang chạy mang chấm đặc, bước
                  chưa tới mang vòng rỗng: ba trạng thái phân biệt được bằng
                  HÌNH, không chỉ bằng độ đậm của chữ. */}
              <span
                aria-hidden="true"
                className={cn(
                  "grid size-4 shrink-0 place-items-center rounded-full border",
                  xong
                    ? "border-transparent text-[var(--color-status-active)]"
                    : dangChay
                      ? "border-primary bg-primary"
                      : "border-muted-foreground",
                )}
              >
                {xong ? (
                  <Check className="size-3.5" />
                ) : dangChay ? (
                  <span className="thinking-dot size-1.5 rounded-full bg-primary-foreground" />
                ) : null}
              </span>
              <span>{buoc.ten}</span>
            </li>
          );
        })}
      </ol>

      {/* Tiến trình XÁC ĐỊNH theo bước (1..4), không phải vòng tròn quay. */}
      <div
        role="progressbar"
        aria-valuemin={1}
        aria-valuemax={CAC_BUOC.length}
        aria-valuenow={soBuoc}
        aria-valuetext={`Bước ${soBuoc}/${CAC_BUOC.length} — ${buocHienTai.ten} (ước lượng)`}
        className="mt-3 h-1 w-full overflow-hidden rounded-full bg-[var(--color-paper-200)]"
      >
        <div
          className="h-full origin-left bg-primary transition-transform duration-500"
          style={{ transform: `scaleX(${soBuoc / CAC_BUOC.length})` }}
        />
      </div>

      <p role="status" className="mt-2 mb-0 text-[13px] leading-5 text-foreground">
        Bước {soBuoc}/{CAC_BUOC.length}: {buocHienTai.ten} — {Math.round(giay)} giây
      </p>

      <p className="mt-1 mb-0 text-[12px] leading-5 text-muted-foreground">
        Bốn bước này có thật trong hệ thống, nhưng máy chủ chưa gửi tiến trình theo thời gian thực:
        bước đang hiện là <strong className="font-medium">ước lượng theo thời gian đã trôi</strong>,
        không phải trạng thái đo được.
      </p>

      <button
        type="button"
        onClick={huyVaTraTieuDiem}
        className="focus-brass mt-3 min-h-11 cursor-pointer rounded-lg border border-border px-4 text-[15px] text-foreground transition-colors hover:bg-[var(--color-paper-100)]"
      >
        Huỷ lượt tra cứu
      </button>
    </div>
  );
}
