import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import type { BuocKhai, SuKienBuoc } from "@/lib/klaw";
import { cn } from "@/lib/utils";

/**
 * Trạng thái chờ cho một lượt gọi mất 10–60 giây.
 *
 * Trên ngưỡng 10 giây, một chỉ báo KHÔNG XÁC ĐỊNH (vòng tròn quay) đọc như treo
 * máy. Nên ở đây có đủ bốn thứ: **tên bước đang chạy**, **tiến trình xác định**,
 * **nút huỷ thật**, và một đường dẫn tới **lỗi thật** khi quá hạn.
 *
 * ## Bước là ĐO ĐƯỢC, không còn là ước lượng
 *
 * Pha 5 phải nói dối: máy chủ trả một lần, nên bước hiển thị chỉ suy từ thời
 * gian đã trôi, và giao diện tự khai điều đó ra ("ước lượng theo thời gian đã
 * trôi"). `POST /tra-cuu/luong` chấm dứt lời nói dối đó — mỗi `event: buoc` là
 * một node của graph ĐÃ CHẠY XONG ở máy chủ, kèm con số nó tính ra
 * (`so_dieu_khoan`, `so_luan_diem`, `so_trich_dan`). Danh sách bước cũng do máy
 * chủ khai trong `event: bat_dau`, KHÔNG viết cứng ở FE: thêm một node vào
 * graph thì thanh tiến trình dài thêm mà không ai phải nhớ sửa ở đây.
 *
 * ## Khoảng lặng 9,1 giây là BÌNH THƯỜNG
 *
 * Đo thật: `tier2` im 9,1 giây (16,61s − 7,51s). Trong khoảng đó không có sự
 * kiện nào tới, và giao diện KHÔNG được trông như đã chết. Hai thứ vẫn động
 * trong lúc im lặng: đồng hồ giây, và tên bước đang chạy — máy chủ đã nói nó
 * đang ở `tier2` trước khi im. Không thêm hoạt ảnh giả để lấp: một thanh chạy
 * qua lại lúc không có tin tức cũng là một khẳng định không có căn cứ.
 */

/** Hoãn trước khi hiện chỉ báo: câu trả lời từ bộ đệm (3ms) không được loé rồi tắt. */
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

/**
 * Con số máy chủ tính ra ở từng bước. Nhãn tiếng Việt cho khoá `chi_tiet`;
 * khoá lạ vẫn hiện (nguyên tên khoá) thay vì bị nuốt — một con số biến mất khỏi
 * màn hình là một bằng chứng biến mất.
 */
const NHAN_CHI_TIET: Record<string, string> = {
  so_dieu_khoan: "điều khoản truy hồi được",
  so_luan_diem: "luận điểm",
  so_luan_diem_dat: "luận điểm qua kiểm chứng",
  so_trich_dan: "trích dẫn",
};

function moTaChiTiet(chiTiet: SuKienBuoc["chi_tiet"]): string {
  const phan: string[] = [];
  for (const [khoa, gia] of Object.entries(chiTiet)) {
    if (gia === null) continue;
    phan.push(`${gia} ${NHAN_CHI_TIET[khoa] ?? khoa}`);
  }
  return phan.join(" · ");
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

  // Đếm theo `thu_tu` LỚN NHẤT đã phát, không theo SỐ sự kiện: lượt lấy từ bộ
  // đệm phát ĐÚNG MỘT bước (`cache`, `thu_tu: 9`) thay vì giả vờ chạy chín node
  // cho một lượt 3ms, và đếm sự kiện sẽ đọc lượt đó thành "mới xong 1/9".
  const soXong = daPhat.reduce((max, su) => Math.max(max, su.thu_tu ?? 0), 0);
  const tong = cacBuoc.length;
  const buocCuoi = daPhat[daPhat.length - 1];
  const dangChay = cacBuoc[soXong];
  const chiTiet = buocCuoi === undefined ? "" : moTaChiTiet(buocCuoi.chi_tiet);

  const huyVaTraTieuDiem = () => {
    onHuy();
    traTieuDiemVeOHoi();
  };

  return (
    <div className="mt-6 rounded-xl border border-border bg-card p-4 shadow-soft">
      <p className="m-0 text-[13px] leading-5 text-muted-foreground">
        Một lượt tra cứu mất 10–60 giây. Máy đang chạy.
      </p>

      {tong === 0 ? (
        <p role="status" className="mt-3 mb-0 text-[15px] leading-6 text-foreground">
          Đang mở kết nối tới máy chủ KLAW — {Math.round(giay)} giây
        </p>
      ) : (
        <>
          <ol className="mt-3 mb-0 list-none p-0">
            {cacBuoc.map((buoc, i) => {
              const xong = i < soXong;
              const nay = i === soXong;
              return (
                <li
                  key={buoc.buoc}
                  className={cn(
                    "flex min-h-8 items-center gap-2.5 text-[15px] leading-6",
                    nay ? "font-medium text-foreground" : "text-muted-foreground",
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
                        : nay
                          ? "border-primary bg-primary"
                          : "border-muted-foreground",
                    )}
                  >
                    {xong ? (
                      <Check className="size-3.5" />
                    ) : nay ? (
                      <span className="thinking-dot size-1.5 rounded-full bg-primary-foreground" />
                    ) : null}
                  </span>
                  <span>{buoc.nhan}</span>
                </li>
              );
            })}
          </ol>

          {/* Tiến trình XÁC ĐỊNH theo bước máy chủ đã phát, không phải vòng quay. */}
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={tong}
            aria-valuenow={soXong}
            aria-valuetext={`Đã xong ${soXong}/${tong} bước${
              dangChay === undefined ? "" : `, đang chạy: ${dangChay.nhan}`
            }`}
            className="mt-3 h-1 w-full overflow-hidden rounded-full bg-[var(--color-paper-200)]"
          >
            <div
              className="h-full origin-left bg-primary transition-transform duration-500"
              style={{ transform: `scaleX(${soXong / tong})` }}
            />
          </div>

          <p role="status" className="mt-2 mb-0 text-[13px] leading-5 text-foreground">
            Đã xong {soXong}/{tong} bước
            {dangChay === undefined ? "" : ` — đang chạy: ${dangChay.nhan}`} — {Math.round(giay)}{" "}
            giây
          </p>

          {chiTiet !== "" && (
            <p className="mt-1 mb-0 text-[12px] leading-5 text-muted-foreground">
              Máy chủ vừa báo: {chiTiet}
            </p>
          )}
        </>
      )}

      <button
        type="button"
        onClick={huyVaTraTieuDiem}
        className="focus-brass mt-3 min-h-11 cursor-pointer rounded-lg border border-border px-4 text-[15px] text-foreground transition-colors hover:bg-[var(--color-paper-100)]"
      >
        Huỷ lượt tra cứu
      </button>

      {/* Huỷ KHÔNG hoàn lại lượt gọi, và giao diện nói ra điều đó TRƯỚC khi
          người dùng bấm. Máy chủ chạy graph trong task riêng một cách cố ý: nếu
          socket đóng huỷ luôn graph thì mọi lượt bị huỷ là một lượt MIỄN PHÍ và
          hạn mức tháng thành trang trí. Giấu chi tiết này đi là để người dùng
          tin nút Huỷ làm một việc mà nó không làm. */}
      <p className="mt-2 mb-0 text-[12px] leading-5 text-muted-foreground">
        Huỷ dừng việc chờ, nhưng máy chủ vẫn chạy nốt lượt này và vẫn tính vào hạn mức.
      </p>
    </div>
  );
}
